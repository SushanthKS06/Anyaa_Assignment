"""M0 pytest: extraction validity + fallback + db. Full engine tests ship in M1."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.agent.llm import chat  # noqa: E402
from app.store.db import init_db  # noqa: E402
from scripts.smoke_test import TOOL_TRIALS, UTTERANCES, deterministic_extract  # noqa: E402


def test_extraction_all_utterances_yield_members() -> None:
    for u in UTTERANCES:
        c = deterministic_extract(u)
        assert len(c.members) >= 1
        c.model_validate(c.model_dump())  # round-trip


def test_tool_validation_matrix() -> None:
    from app.engine.models import Member

    for t in TOOL_TRIALS:
        if t["valid"]:
            Member(name=t["name"], age_group=t["age_group"], diet=t["diet"])  # type: ignore
        else:
            try:
                Member(name=t["name"], age_group=t["age_group"], diet=t["diet"])  # type: ignore
            except Exception:
                continue
            raise AssertionError(f"expected validation failure: {t}")


def test_forced_429_falls_back_to_mock() -> None:
    r = chat([{"role": "user", "content": "hi"}], force_429=True, use_mock=False)
    assert r["model"].startswith("mock:")
    assert r["fallback"] is not None


def test_retry_path_raises_ratelimit_before_chat_fallback() -> None:
    """Proves tenacity retry wiring offline: providers raise, chat() still mocks."""
    from app.agent.llm import RateLimitError, _primary_with_retry

    try:
        _primary_with_retry([{"role": "user", "content": "hi"}], True)
    except (RateLimitError, Exception):
        pass
    else:
        raise AssertionError("expected provider failure with force_429=True")
    r = chat([{"role": "user", "content": "retry-path unique probe"}], force_429=True, use_mock=False)
    assert r["model"].startswith("mock:")


def test_db_inits(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = init_db(str(tmp_path / "t.db"))
    import os

    assert os.path.exists(p)
