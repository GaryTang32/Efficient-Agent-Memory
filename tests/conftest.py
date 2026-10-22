import pytest

from eam.models import load_models


@pytest.fixture
def models():
    return load_models()
