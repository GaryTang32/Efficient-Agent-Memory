"""Adapter for the official long-term memory systems (MemoryOS, LightMem, Nemori), used through their own
packages in a sidecar process (scripts/memory_sidecar.py, run by .venv-memory/bin/python).

They are conversational memories: what goes in is a session's task and the agent's final answer, what comes out
is whatever their own retrieval returns for the next session's task, put at the top of its first message — the
same place AutoMemory's recall uses, so the comparison isolates the memory system. Within a session they do
nothing; combine with a compaction method for the window (e.g. `ext_memory:backend=memoryos+resum:...`).

The memory systems' own LLM calls go through a private gateway (eam.gateway, Claude Code CLI, `model`), whose log
is read after every add/retrieve so their cost is billed to the run under the tag `aux:memory`.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import weakref
from pathlib import Path

from eam.llm.types import Usage
from eam.techniques.base import Technique

ROOT = Path(__file__).resolve().parents[2]
RECALL = "Memories from earlier sessions (retrieved by {backend}):\n\n{text}\n\nUse them where they help."


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _stop(procs):
    for p in procs:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


class ExternalMemory(Technique):
    name = "ext_memory"
    source = "MemoryOS (EMNLP'25) / LightMem (ICLR'26) / Nemori (ACL'26) via their official packages"
    provenance = "official package via adapter (runtime fixes listed in scripts/memory_sidecar.py)"

    def __init__(self, backend: str = "memoryos", limit: int = 10, model: str = "cc-haiku",
                 timeout: float = 900):
        self.backend = str(backend)
        self.limit = int(limit)
        self.model = str(model)
        self.timeout = float(timeout)
        self._sessions = 0
        self._sidecar = None
        self._gateway = None
        self._log: Path | None = None
        self._log_pos = 0

    # ---- processes -----------------------------------------------------------------------------------------
    def _start(self):
        work = Path(tempfile.mkdtemp(prefix=f"eam-{self.backend}-"))
        port = _free_port()
        self._log = work / "gateway.jsonl"
        self._gateway = subprocess.Popen(
            [sys.executable, "-m", "eam.gateway", "--chat", "claude-cli", "--embed", "hashing", "--port", str(port),
             "--log", str(self._log)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.2)
        python = os.environ.get("EAM_MEMORY_PYTHON", str(ROOT / ".venv-memory" / "bin" / "python"))
        self._sidecar = subprocess.Popen([python, str(ROOT / "scripts" / "memory_sidecar.py")], cwd=work,
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=open(work / "sidecar.log", "w"), text=True)
        weakref.finalize(self, _stop, [self._sidecar, self._gateway])
        self._call({"op": "init", "backend": self.backend, "base_url": f"http://127.0.0.1:{port}/v1",
                    "model": self.model, "dir": str(work / "store")})

    def _call(self, msg: dict) -> dict:
        self._sidecar.stdin.write(json.dumps(msg) + "\n")
        self._sidecar.stdin.flush()
        line = self._sidecar.stdout.readline()
        if not line:
            raise RuntimeError(f"{self.backend} sidecar exited (see its sidecar.log)")
        out = json.loads(line)
        if not out.get("ok"):
            raise RuntimeError(f"{self.backend}: {out.get('error')}")
        return out

    def _bill(self, ctx) -> None:
        """Record the memory system's own LLM calls (from the private gateway's log) on the run's meter."""
        if not self._log or not self._log.exists():
            return
        with self._log.open() as fh:
            fh.seek(self._log_pos)
            rows = [json.loads(l) for l in fh if l.strip()]
            self._log_pos = fh.tell()
        profile = (ctx.models or {}).get(self.model, ctx.aux_model)
        for r in rows:
            if r.get("kind") == "chat":
                u = r.get("usage", {})
                ctx.meter.record("aux:memory", profile, Usage(u.get("input_tokens", 0), u.get("output_tokens", 0),
                                                               u.get("cache_read_tokens", 0),
                                                               u.get("cache_write_tokens", 0)),
                                 r.get("latency_ms", 0.0), r.get("cost_usd"))

    # ---- hooks ---------------------------------------------------------------------------------------------
    def on_session_start(self, ctx):
        if self._sidecar is None:
            self._start()
        self._sessions += 1
        if self._sessions == 1:
            return
        text = self._call({"op": "retrieve", "query": ctx.task, "limit": self.limit}).get("text", "")
        self._bill(ctx)
        if text.strip():
            ctx.preamble.append(RECALL.format(backend=self.backend, text=text))
            ctx.log("ext_memory_recall", chars=len(text))

    def on_session_end(self, ctx, answer):
        if answer and self._sidecar is not None:
            self._call({"op": "add", "task": ctx.task, "answer": answer, "session": self._sessions})
            self._bill(ctx)
            ctx.log("ext_memory_add", chars=len(answer))

    def describe(self) -> str:
        return f"ext_memory(backend={self.backend}, limit={self.limit}, model={self.model})"
