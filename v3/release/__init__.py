"""
SystemKernel v3.0 — Release Freeze Package.

Phase 5F: Release-grade validation, inventory, and release notes.
No new runtime capabilities. No architectural changes.
Freeze the v3.0 baseline.
"""

from v3.release.validation_matrix import (
    VALIDATION_CATEGORIES,
    ValidationCheck,
    ValidationMatrix,
    build_validation_matrix,
    run_static_validation,
    write_validation_matrix,
)

from v3.release.inventory import (
    InventoryEntry,
    ProjectInventory,
    build_inventory,
    compute_inventory_hash,
    write_inventory,
)

from v3.release.release_notes import (
    generate_release_notes,
    write_release_notes,
)

from v3.release.package_manifest import (
    PackageManifestEntry,
    PackageManifest,
    build_package_manifest,
    write_package_manifest,
    verify_package_manifest,
)

from v3.release.handoff import (
    HandoffChecklistItem,
    OperationalHandoff,
    build_handoff,
    write_handoff_json,
    write_handoff_md,
)

from v3.release.tag_metadata import (
    TagMetadata,
    build_tag_metadata,
    write_tag_metadata,
    verify_tag_metadata,
)

from v3.release.archive_manifest import (
    ArchiveManifest,
    build_archive_manifest,
    write_archive_manifest,
    verify_archive_manifest,
)

# ── V4 Release (Phase 12) ──────────────────────────────────────────────
from v3.release.v4_validation_matrix import (
    V4ValidationCheck,
    V4ValidationMatrix,
    build_v4_validation_matrix,
    run_v4_static_validation,
    write_v4_validation_matrix,
)

from v3.release.v4_inventory import (
    V4InventoryEntry,
    V4ReleaseInventory,
    build_v4_release_inventory,
    write_v4_release_inventory,
    verify_v4_release_inventory,
)

from v3.release.v4_release_notes import (
    V4ReleaseNotes,
    build_v4_release_notes,
    write_v4_release_notes,
)

from v3.release.v4_tag_metadata import (
    V4TagMetadata,
    build_v4_tag_metadata,
    write_v4_tag_metadata,
    verify_v4_tag_metadata,
)

from v3.release.v4_package_manifest import (
    V4PackageManifest,
    build_v4_package_manifest,
    write_v4_package_manifest,
    verify_v4_package_manifest,
)

__all__ = [
    # Validation
    "ValidationCheck",
    "ValidationMatrix",
    "build_validation_matrix",
    "run_static_validation",
    "write_validation_matrix",
    "VALIDATION_CATEGORIES",
    # Inventory
    "InventoryEntry",
    "ProjectInventory",
    "build_inventory",
    "compute_inventory_hash",
    "write_inventory",
    # Release notes
    "generate_release_notes",
    "write_release_notes",
    # Package manifest
    "PackageManifestEntry",
    "PackageManifest",
    "build_package_manifest",
    "write_package_manifest",
    "verify_package_manifest",
    # Handoff
    "HandoffChecklistItem",
    "OperationalHandoff",
    "build_handoff",
    "write_handoff_json",
    "write_handoff_md",
    # Tag metadata
    "TagMetadata",
    "build_tag_metadata",
    "write_tag_metadata",
    "verify_tag_metadata",
    # Archive manifest
    "ArchiveManifest",
    "build_archive_manifest",
    "write_archive_manifest",
    "verify_archive_manifest",
    # V4 Release (Phase 12)
    "V4ValidationCheck",
    "V4ValidationMatrix",
    "build_v4_validation_matrix",
    "run_v4_static_validation",
    "write_v4_validation_matrix",
    "V4InventoryEntry",
    "V4ReleaseInventory",
    "build_v4_release_inventory",
    "write_v4_release_inventory",
    "verify_v4_release_inventory",
    "V4ReleaseNotes",
    "build_v4_release_notes",
    "write_v4_release_notes",
    "V4TagMetadata",
    "build_v4_tag_metadata",
    "write_v4_tag_metadata",
    "verify_v4_tag_metadata",
    "V4PackageManifest",
    "build_v4_package_manifest",
    "write_v4_package_manifest",
    "verify_v4_package_manifest",
]
