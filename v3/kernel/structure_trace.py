"""
Structural Trace — Backward-compatibility re-exports from truth_model.

All functionality has been unified into truth_model.ExecutionTruthSnapshot.
This module remains for existing importers but delegates entirely.
"""

from v3.kernel.truth_model import (
    ExecutionTruthSnapshot as StructuralTrace,
    capture_truth as capture_trace,
    write_truth as write_trace,
    read_truths as read_traces,
    diff_truths as compare_traces,
    TruthDiff as TraceDiff,
)
