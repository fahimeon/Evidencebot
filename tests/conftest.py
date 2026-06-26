import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(autouse=True)
def _disable_llm_polish_by_default(monkeypatch):
    """Tests must be deterministic and offline regardless of whatever is in a
    local .env file. Individual tests in test_llm_fallback.py explicitly
    re-enable/mock this via their own monkeypatch calls."""
    monkeypatch.setenv("ENABLE_LLM_POLISH", "false")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
