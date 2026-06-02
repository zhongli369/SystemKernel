# SystemKernel v3.0 — Quickstart

5 minutes from zero to understanding.

## Prerequisites

- Python 3.10+
- Standard library only (no pip install required)

## 1. Check System Status (10 seconds)

```bash
cd SystemKernel
python v3/cli/systemkernel.py status
```

You should see:
```
Kernel Purity:        100/100
Test Suites:          14
Total Tests:          268
Memory Removable:     YES
Events Source of Truth: YES
Complexity Verdict:   REVIEW
```

## 2. Run the Golden Path (30 seconds)

```bash
python examples/golden_path/run_golden_path.py
```

This demonstrates the complete pipeline: events → observability → memory → quality gate.
Output goes to `examples/golden_path/output/`.

## 3. View Reports (10 seconds)

```bash
python v3/cli/systemkernel.py reports summary
```

Shows subsystem status for kernel, tests, memory, and complexity.

## 4. Run Health Check (15 seconds)

```bash
python v3/cli/systemkernel.py doctor
```

19 checks covering directories, reports, banned imports, and boundary integrity.

## 5. Verify Purity

SystemKernel's core principle: **the kernel must stay pure.**

```bash
python v3/tests/test_kernel_invariants.py
```

Look for:
```
purity_score == 100:     [+]
memory fully removable:  [+]
zero external AI deps:   [+]
```

## 6. Verify Memory is Removable

Memory is an optional external projection. Delete it and the kernel still works:

```bash
# Run kernel tests WITHOUT memory
python v3/tests/test_event_runtime.py
python v3/tests/test_checkpoint_runtime.py
```

All kernel tests pass with or without `v3/memory/` present.

## What Next?

- Read `docs/ARCHITECTURE_OVERVIEW.md` for the big picture
- Run `python examples/golden_path/run_golden_path.py` and read the output
- Check `v3/exports/` for all generated reports
- Read `v3/kernel/CLAUDE.md` (referenced via `CLAUDE.md` at repo root) for the kernel constitution
