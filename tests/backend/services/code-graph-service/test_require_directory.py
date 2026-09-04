"""require_directory reports permission vs missing path."""

from __future__ import annotations

from pathlib import Path

import pytest

from code_graph_service.domain.errors import ValidationError
from code_graph_service.domain.fs_paths import require_directory


def test_require_directory_ok(tmp_path: Path):
    assert require_directory(str(tmp_path)) == tmp_path.resolve()


def test_require_directory_missing(tmp_path: Path):
    with pytest.raises(ValidationError, match="does not exist"):
        require_directory(str(tmp_path / "nope"))


def test_require_directory_file_not_dir(tmp_path: Path):
    f = tmp_path / "x.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ValidationError, match="not a directory"):
        require_directory(str(f))
