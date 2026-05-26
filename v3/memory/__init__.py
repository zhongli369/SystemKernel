"""
SystemKernel v3.0 — Memory Subsystem.

OUTSIDE kernel boundary. LLM allowed (isolated to this package).
Removable: delete this directory → kernel behavior unchanged.

Layers:
  - Working memory  (in-process dict, session lifetime)
  - Episodic memory (local JSONL store, Phase 4D-2)
  - Semantic memory (graphiti knowledge graph, future)

Communication:
  - Write: Kernel → MemoryGateway → MemoryAdapter.handle_event()
  - Read:  Kernel → MemoryGateway → MemoryAdapter.handle_query()
  - All read operations are deterministic (zero LLM at query time)
"""

from v3.memory.memory_service import (
    MemoryService, MemoryEntry, MemoryQuery, MemoryResult, MemoryType,
    InProcessMemoryService,
)
from v3.memory.memory_adapter_base import (
    MemoryAdapter, InProcessMemoryAdapter,
)
from v3.memory.adapter_stub import MemoryAdapterStub
from v3.memory.episodic_store import (
    EpisodicMemoryRecord, EpisodicMemoryStore,
    compute_record_hash, compute_source_hash, derive_tags,
)
from v3.memory.episodic_adapter import EpisodicMemoryAdapter
from v3.memory.integrity import (
    IntegrityReport, check_integrity, quick_integrity_check,
    generate_integrity_report_json,
)
from v3.memory.semantic_index import (
    SemanticIndexEntry, SemanticSearchResult, SemanticMemoryIndex,
    tokenize,
)
from v3.memory.retrieval import MemoryRetrievalRuntime
from v3.memory.index_integrity import (
    IndexIntegrityReport, check_index_integrity,
    quick_index_check, generate_index_integrity_report_json,
)
from v3.memory.provenance import (
    RecallProvenance, extract_provenance, verify_provenance,
    verify_provenance_chain, compute_provenance_hash,
)
from v3.memory.recall import (
    RecallResult, RecallBundle, TruthLinkedRecallRuntime,
    compute_recall_hash, compute_bundle_hash,
)
from v3.memory.compaction import (
    CompactionPolicy, CompactedMemoryRecord, CompactionResult,
    MemoryCompactor, compute_content_fingerprint, compute_compacted_hash,
    compute_result_hash,
)
from v3.memory.compaction_integrity import (
    CompactionIntegrityReport, check_compaction_integrity,
    quick_compaction_check, generate_compaction_integrity_report_json,
)
from v3.memory.runtime import (
    MemoryRuntimeConfig, MemoryRuntimeResult, MemoryRuntime,
    compute_runtime_hash,
)
from v3.memory.system_report import (
    MemorySystemReport, generate_system_report, write_system_report_json,
)

__all__ = [
    "MemoryService",
    "MemoryEntry",
    "MemoryQuery",
    "MemoryResult",
    "MemoryType",
    "MemoryAdapter",
    "InProcessMemoryService",
    "InProcessMemoryAdapter",
    "MemoryAdapterStub",
    "EpisodicMemoryRecord",
    "EpisodicMemoryStore",
    "EpisodicMemoryAdapter",
    "compute_record_hash",
    "compute_source_hash",
    "derive_tags",
    "IntegrityReport",
    "check_integrity",
    "quick_integrity_check",
    "generate_integrity_report_json",
    "SemanticIndexEntry",
    "SemanticSearchResult",
    "SemanticMemoryIndex",
    "tokenize",
    "MemoryRetrievalRuntime",
    "IndexIntegrityReport",
    "check_index_integrity",
    "quick_index_check",
    "generate_index_integrity_report_json",
    "RecallProvenance",
    "extract_provenance",
    "verify_provenance",
    "verify_provenance_chain",
    "compute_provenance_hash",
    "RecallResult",
    "RecallBundle",
    "TruthLinkedRecallRuntime",
    "compute_recall_hash",
    "compute_bundle_hash",
    "CompactionPolicy",
    "CompactedMemoryRecord",
    "CompactionResult",
    "MemoryCompactor",
    "compute_content_fingerprint",
    "compute_compacted_hash",
    "compute_result_hash",
    "CompactionIntegrityReport",
    "check_compaction_integrity",
    "quick_compaction_check",
    "generate_compaction_integrity_report_json",
    "MemoryRuntimeConfig",
    "MemoryRuntimeResult",
    "MemoryRuntime",
    "compute_runtime_hash",
    "MemorySystemReport",
    "generate_system_report",
    "write_system_report_json",
]
