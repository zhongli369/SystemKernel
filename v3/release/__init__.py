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
]
