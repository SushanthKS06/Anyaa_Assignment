"""Pytest configuration for evaluation suite.
Ensures unit tests run deterministically against the mock engine,
while the live application uses the real LLM."""
import pytest
from app.config import CONFIG

@pytest.fixture(autouse=True)
def force_test_environment():
    orig = CONFIG.mock_default
    object.__setattr__(CONFIG, "mock_default", True)
    yield
    object.__setattr__(CONFIG, "mock_default", orig)
