"""Shared fixtures for Alfred tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def otlp_sample_path() -> Path:
    return FIXTURES_DIR / "otlp_sample.json"


@pytest.fixture
def otlp_sample_payload(otlp_sample_path: Path) -> dict[str, object]:
    return json.loads(otlp_sample_path.read_text(encoding="utf-8"))
