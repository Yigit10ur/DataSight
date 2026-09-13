import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    """Hold the whole suite to the promise that it needs no key and calls nobody.

    The explanation layer reads settings at call time, so a key in the developer's
    own .env leaked into the tests: the endpoint test that asserts the no-key
    degradation path reached the real API instead, and billed for it. Every test
    that wants a model injects a fake client, so clearing the key here costs
    nothing and makes a network call impossible rather than merely unlikely.
    """
    monkeypatch.setattr(settings, "anthropic_api_key", "")
