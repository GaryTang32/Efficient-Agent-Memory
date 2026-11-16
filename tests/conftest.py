import pytest

from eam.models import load_models


@pytest.fixture
def models():
    return load_models()


@pytest.fixture(autouse=True)
def _no_traces_in_the_repository(monkeypatch):
    """Bench runs write traces to results/traces by default; tests must not (tests that check traces set their own)."""
    monkeypatch.setenv("EAM_TRACES", "off")
