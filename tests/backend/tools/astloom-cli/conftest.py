from __future__ import annotations

import pytest

from astloom_cli.process_containers import clear_process_containers


@pytest.fixture(autouse=True)
def isolate_process_containers():
    clear_process_containers()
    yield
    clear_process_containers()
