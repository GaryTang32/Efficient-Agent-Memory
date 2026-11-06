"""Artifact store for *recoverable* compression (Manus): full content lives
outside the context window and the context keeps only a pointer.

In-memory by default; pass ``root`` to also write artifacts to disk. Swap in an
S3-backed store for production by implementing ``put``/``get``.
"""

from __future__ import annotations

from pathlib import Path


class ArtifactStore:
    def __init__(self, root: str | Path | None = None):
        self._items: dict[str, str] = {}
        self._labels: dict[str, str] = {}
        self.root = Path(root) if root else None
        if self.root:
            self.root.mkdir(parents=True, exist_ok=True)

    def put(self, text: str, label: str = "") -> str:
        aid = f"a{len(self._items) + 1:04d}"
        self._items[aid] = text
        self._labels[aid] = label
        if self.root:
            (self.root / f"{aid}.txt").write_text(text)
        return aid

    def get(self, aid: str) -> str | None:
        return self._items.get(aid.removeprefix("artifact://"))

    def label(self, aid: str) -> str:
        return self._labels.get(aid, "")

    @staticmethod
    def pointer(aid: str) -> str:
        return f"artifact://{aid}"

    def __len__(self) -> int:
        return len(self._items)
