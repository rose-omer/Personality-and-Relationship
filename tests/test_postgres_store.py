"""Gerçek Postgres ile depo testi. Yalnız TEST_DATABASE_URL tanımlıysa çalışır (CI)."""

import os
import uuid
from pathlib import Path

import pytest

DSN = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL tanımlı değil")

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def pg_store():
    import psycopg

    from db import PostgresStore

    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS couple_sessions, results")
        conn.execute((ROOT / "schema.sql").read_text(encoding="utf-8"))
    return PostgresStore(DSN)


def test_result_roundtrip_and_delete(pg_store):
    pg_store.save_result("abcdefghijkl", "Ada", ["Evet"], {"tip_adi": "X"})
    shared = pg_store.get_shared("abcdefghijkl")
    assert shared.kind == "single"
    assert shared.result == {"tip_adi": "X"}
    assert pg_store.delete_shared("abcdefghijkl") is True
    assert pg_store.get_shared("abcdefghijkl") is None


def test_couple_flow_single_claim(pg_store):
    session_id = str(uuid.uuid4())
    pg_store.create_couple(session_id, "Ada", "Can")
    assert pg_store.claim_analysis(session_id) is False
    assert pg_store.save_answers(session_id, "user1", ["a"]) is True
    assert pg_store.save_answers(session_id, "user1", ["b"]) is False
    assert pg_store.save_answers(session_id, "user2", ["c"]) is True
    assert pg_store.claim_analysis(session_id) is True
    assert pg_store.claim_analysis(session_id) is False

    pg_store.finish_analysis(session_id, {"uyum_skoru": 50}, "mnopqrstuvwx")
    couple = pg_store.get_couple(session_id)
    assert couple.status == "hazir"
    assert couple.answers1 == ["a"]
    shared = pg_store.get_shared("mnopqrstuvwx")
    assert shared.kind == "couple"
    assert shared.name1 == "Ada"


def test_failed_analysis_can_be_claimed_again(pg_store):
    session_id = str(uuid.uuid4())
    pg_store.create_couple(session_id, "Ada", "Can")
    pg_store.save_answers(session_id, "user1", ["a"])
    pg_store.save_answers(session_id, "user2", ["b"])
    assert pg_store.claim_analysis(session_id) is True
    pg_store.finish_analysis(session_id, None, None)
    assert pg_store.get_couple(session_id).status == "hata"
    assert pg_store.claim_analysis(session_id) is True


def test_purge_expired(pg_store):
    import psycopg

    pg_store.save_result("abcdefghijkl", None, [], {})
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE results SET expires_at = now() - interval '1 second'")
    assert pg_store.purge_expired() == 1
