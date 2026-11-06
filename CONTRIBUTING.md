# Contributing

Thanks for helping make long-running agents cheaper. This repository measures methods; a contribution is useful when
someone else can trust and reproduce its numbers.

## What helps most

- **A new method** from a paper or repository, ported faithfully.
- **A new task**, especially real work (another repository, another benchmark) with automatic grading.
- **Another backend or price list**, or a re-run of existing cells on your provider (Bedrock, OpenAI-compatible).
- **Bug reports** with the command, the backend and the row (or log lines) that show the problem.

## Rules for a method

1. **Follow the source.** Use the official prompts and algorithm when they exist; quote them verbatim and keep
   their licence (add vendored code or quoted prompts to `eam/techniques/third_party/NOTICE.md`).
2. **Document every deviation** in the module's docstring: what the API forced, what is ours.
3. **Register it** in `eam/techniques/__init__.py` with a provenance label (official, ported, baseline, provisional).
4. **Test it offline**: a mock-backend test in `tests/` that runs it on every long task.

## Rules for a measurement

- Place every method between the same model's floor (`naive`) and ceiling (`naive@native`) on the same instances
  (`docs/methodology.md`).
- Report score, cost relative to the ceiling, runs fully solved and peak context, with the number of runs per cell.
  Differences under about 0.1 in score or 15 points in cost are within run-to-run noise at 2–4 runs.
- Include the exact command (the scripts in `scripts/` are the pattern). Raw rows stay out of the repository.

## Workflow

```bash
python -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest -q          # offline, no API keys needed
```

Open a pull request against `main` with what changed, why, and the measured cells (or "not measured yet").
