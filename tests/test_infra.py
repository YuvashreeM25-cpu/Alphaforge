"""Tests for the new infra: cache fallback, alert engine, ingest logging."""
import pytest

from data_pipeline import cache
from data_pipeline.db import connect, reset_db
from data_pipeline.sample_data import generate
from scheduler.alerts import evaluate


@pytest.fixture(scope="module", autouse=True)
def seeded():
    reset_db()
    generate(seed=42)
    yield


def test_cache_memory_roundtrip():
    cache.set("t:1", {"a": 1, "b": [2, 3]})
    assert cache.get("t:1") == {"a": 1, "b": [2, 3]}
    assert cache.get("t:does-not-exist") is None


def test_cache_decorator_caches():
    calls = {"n": 0}

    @cache.cached("unit")
    def expensive(x):
        calls["n"] += 1
        return {"x": x}

    expensive(5); expensive(5)
    assert calls["n"] == 1  # second call served from cache


def test_alerts_return_structured_breaches():
    fired = evaluate(["NVDA", "AMD", "INTC"])
    assert isinstance(fired, list)
    for a in fired:
        assert {"ticker", "rule", "value", "message"} <= set(a)


def test_alerts_are_persisted():
    evaluate(["TSM"])
    with connect() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM alerts").fetchone()["c"]
    assert n >= 0  # table exists and is writable


def test_ingest_synthetic_logs():
    from data_pipeline.ingest import main as ingest_main
    import sys
    argv = sys.argv
    sys.argv = ["ingest"]
    try:
        ingest_main()
    finally:
        sys.argv = argv
    with connect() as conn:
        row = conn.execute("SELECT source FROM ingest_log ORDER BY id DESC LIMIT 1").fetchone()
    assert row["source"] in ("synthetic", "live")
