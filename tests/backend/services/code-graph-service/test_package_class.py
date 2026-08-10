"""Unit tests for shared-package finding classification."""

from __future__ import annotations

from code_graph_service.domain.unused_candidates.package_class import (
    classify_shared_package,
    shared_package_top,
)


def test_shared_package_top():
    assert (
        shared_package_top("backend/packages/code-metadata/code_metadata/loader.py")
        == "code-metadata"
    )
    assert shared_package_top("pkg/orphan/a.py") is None


def test_classify_keep_public_and_retire(tmp_path):
    keep = classify_shared_package("backend/packages/adapter_harness")
    assert keep.finding_kind == "unwired_shared_package"
    assert keep.recommendation == "keep_public"

    orphan = classify_shared_package(
        "backend/packages/lonely-lib/lonely_lib",
        repo_root=str(tmp_path),
    )
    assert orphan.finding_kind == "zombie_package"
    assert orphan.recommendation == "retire"

    (tmp_path / "backend" / "configs" / "lonely-lib-profiles").mkdir(parents=True)
    wire = classify_shared_package(
        "backend/packages/lonely-lib/lonely_lib",
        repo_root=str(tmp_path),
    )
    assert wire.finding_kind == "unwired_shared_package"
    assert wire.recommendation == "wire"
