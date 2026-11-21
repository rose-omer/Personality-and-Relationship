"""Kalıcı veri katmanı.

`PostgresStore` canlıda çalışır (şema: schema.sql). `MemoryStore` aynı arayüzü bellekte
uygular; testlerde ve DATABASE_URL tanımsız yerel denemede kullanılır.
"""

import copy
import logging
import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

log = logging.getLogger(__name__)

RESULT_TTL = timedelta(days=30)
COUPLE_TTL = timedelta(days=7)
# Analiz bu süreden uzun "analiz" durumunda kalırsa (worker öldüyse) yeniden başlatılabilir.
STALE_ANALYSIS = timedelta(minutes=2)

Status = Literal["bekliyor", "analiz", "hazir", "hata"]
User = Literal["user1", "user2"]


class StoreError(Exception):
    """Veritabanına ulaşılamadı ya da sorgu başarısız oldu."""


@dataclass(frozen=True)
class CoupleSession:
    id: str
    name1: str
    name2: str
    answers1: list[str] | None
    answers2: list[str] | None
    status: Status
    result: dict[str, Any] | None
    share_id: str | None

    def name_of(self, user: User) -> str:
        return self.name1 if user == "user1" else self.name2

    def answers_of(self, user: User) -> list[str] | None:
        return self.answers1 if user == "user1" else self.answers2


@dataclass(frozen=True)
class SharedResult:
    share_id: str
    kind: Literal["single", "couple"]
    result: dict[str, Any]
    nickname: str | None = None
    name1: str | None = None
    name2: str | None = None


class Store(Protocol):
    def save_result(
        self, share_id: str, nickname: str | None, answers: list[str], result: dict
    ) -> None: ...
    def get_shared(self, share_id: str) -> SharedResult | None: ...
    def delete_shared(self, share_id: str) -> bool: ...
    def create_couple(self, session_id: str, name1: str, name2: str) -> None: ...
    def get_couple(self, session_id: str) -> CoupleSession | None: ...
    def save_answers(self, session_id: str, user: User, answers: list[str]) -> bool: ...
    def claim_analysis(self, session_id: str) -> bool: ...
    def finish_analysis(
        self, session_id: str, result: dict | None, share_id: str | None
    ) -> None: ...
    def purge_expired(self) -> int: ...


def _now() -> datetime:
    return datetime.now(UTC)


class MemoryStore:
    """Süreç içi depo. Kalıcı değildir; çoklu worker ile paylaşılmaz."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._results: dict[str, dict] = {}
        self._couples: dict[str, dict] = {}

    def save_result(self, share_id, nickname, answers, result):
        with self._lock:
            self._results[share_id] = {
                "nickname": nickname,
                "answers": list(answers),
                "result": copy.deepcopy(result),
                "expires_at": _now() + RESULT_TTL,
            }

    def get_shared(self, share_id):
        with self._lock:
            row = self._results.get(share_id)
            if row and row["expires_at"] > _now():
                return SharedResult(
                    share_id, "single", copy.deepcopy(row["result"]), nickname=row["nickname"]
                )
            for row in self._couples.values():
                if row["share_id"] == share_id and row["expires_at"] > _now():
                    return SharedResult(
                        share_id,
                        "couple",
                        copy.deepcopy(row["result"]),
                        name1=row["name1"],
                        name2=row["name2"],
                    )
        return None

    def delete_shared(self, share_id):
        with self._lock:
            if self._results.pop(share_id, None):
                return True
            for key, row in list(self._couples.items()):
                if row["share_id"] == share_id:
                    del self._couples[key]
                    return True
        return False

    def create_couple(self, session_id, name1, name2):
        with self._lock:
            now = _now()
            self._couples[session_id] = {
                "name1": name1,
                "name2": name2,
                "answers1": None,
                "answers2": None,
                "status": "bekliyor",
                "result": None,
                "share_id": None,
                "updated_at": now,
                "expires_at": now + COUPLE_TTL,
            }

    def get_couple(self, session_id):
        with self._lock:
            row = self._couples.get(session_id)
            if not row or row["expires_at"] <= _now():
                return None
            return CoupleSession(
                id=session_id,
                name1=row["name1"],
                name2=row["name2"],
                answers1=copy.copy(row["answers1"]),
                answers2=copy.copy(row["answers2"]),
                status=row["status"],
                result=copy.deepcopy(row["result"]),
                share_id=row["share_id"],
            )

    def save_answers(self, session_id, user, answers):
        column = "answers1" if user == "user1" else "answers2"
        with self._lock:
            row = self._couples.get(session_id)
            if not row or row["expires_at"] <= _now() or row[column] is not None:
                return False
            row[column] = list(answers)
            row["updated_at"] = _now()
            return True

    def claim_analysis(self, session_id):
        with self._lock:
            row = self._couples.get(session_id)
            if not row or row["answers1"] is None or row["answers2"] is None:
                return False
            stale = row["status"] == "analiz" and row["updated_at"] < _now() - STALE_ANALYSIS
            if row["status"] in ("bekliyor", "hata") or stale:
                row["status"] = "analiz"
                row["updated_at"] = _now()
                return True
            return False

    def finish_analysis(self, session_id, result, share_id):
        with self._lock:
            row = self._couples.get(session_id)
            if not row:
                return
            row["status"] = "hazir" if result is not None else "hata"
            row["result"] = copy.deepcopy(result)
            row["share_id"] = share_id
            row["updated_at"] = _now()

    def purge_expired(self):
        with self._lock:
            now = _now()
            old_results = [k for k, v in self._results.items() if v["expires_at"] <= now]
            old_couples = [k for k, v in self._couples.items() if v["expires_at"] <= now]
            for key in old_results:
                del self._results[key]
            for key in old_couples:
                del self._couples[key]
            return len(old_results) + len(old_couples)


class PostgresStore:
    """psycopg 3 ile Postgres deposu. Her işlem kısa ömürlü bir bağlantı açar."""

    def __init__(self, dsn: str, connect_timeout: int = 5) -> None:
        self._dsn = dsn
        self._connect_timeout = connect_timeout

    def _run(self, sql: str, params: tuple = (), fetch: str | None = None):
        import psycopg
        from psycopg.rows import dict_row

        try:
            with psycopg.connect(
                self._dsn, connect_timeout=self._connect_timeout, row_factory=dict_row
            ) as conn:
                cur = conn.execute(sql, params)
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "count":
                    return cur.rowcount
                return None
        except psycopg.Error as exc:
            raise StoreError(type(exc).__name__) from exc

    @staticmethod
    def _json(value):
        from psycopg.types.json import Jsonb

        return None if value is None else Jsonb(value)

    def save_result(self, share_id, nickname, answers, result):
        self._run(
            "INSERT INTO results (share_id, nickname, answers, result, expires_at) "
            "VALUES (%s, %s, %s, %s, now() + %s)",
            (share_id, nickname, self._json(answers), self._json(result), RESULT_TTL),
        )

    def get_shared(self, share_id):
        row = self._run(
            "SELECT nickname, result FROM results WHERE share_id = %s AND expires_at > now()",
            (share_id,),
            fetch="one",
        )
        if row:
            return SharedResult(share_id, "single", row["result"], nickname=row["nickname"])
        row = self._run(
            "SELECT name1, name2, result FROM couple_sessions "
            "WHERE share_id = %s AND status = 'hazir' AND expires_at > now()",
            (share_id,),
            fetch="one",
        )
        if row:
            return SharedResult(
                share_id, "couple", row["result"], name1=row["name1"], name2=row["name2"]
            )
        return None

    def delete_shared(self, share_id):
        deleted = self._run("DELETE FROM results WHERE share_id = %s", (share_id,), fetch="count")
        if deleted:
            return True
        deleted = self._run(
            "DELETE FROM couple_sessions WHERE share_id = %s", (share_id,), fetch="count"
        )
        return bool(deleted)

    def create_couple(self, session_id, name1, name2):
        self._run(
            "INSERT INTO couple_sessions (id, name1, name2, expires_at) "
            "VALUES (%s, %s, %s, now() + %s)",
            (session_id, name1, name2, COUPLE_TTL),
        )

    def get_couple(self, session_id):
        row = self._run(
            "SELECT id::text AS id, name1, name2, answers1, answers2, status, result, share_id "
            "FROM couple_sessions WHERE id = %s AND expires_at > now()",
            (session_id,),
            fetch="one",
        )
        return CoupleSession(**row) if row else None

    def save_answers(self, session_id, user, answers):
        # Sütun adı yalnız iki sabit değerden biri olabilir; kullanıcı girdisi SQL'e girmez.
        column = {"user1": "answers1", "user2": "answers2"}[user]
        row = self._run(
            f"UPDATE couple_sessions SET {column} = %s, updated_at = now() "
            f"WHERE id = %s AND {column} IS NULL AND expires_at > now() RETURNING id",
            (self._json(answers), session_id),
            fetch="one",
        )
        return row is not None

    def claim_analysis(self, session_id):
        # Tek çalıştırma: koşullu UPDATE satır kilidi alır; yarışta yalnız biri satır döndürür.
        row = self._run(
            "UPDATE couple_sessions SET status = 'analiz', updated_at = now() "
            "WHERE id = %s AND answers1 IS NOT NULL AND answers2 IS NOT NULL "
            "AND (status IN ('bekliyor', 'hata') "
            "     OR (status = 'analiz' AND updated_at < now() - %s)) "
            "RETURNING id",
            (session_id, STALE_ANALYSIS),
            fetch="one",
        )
        return row is not None

    def finish_analysis(self, session_id, result, share_id):
        self._run(
            "UPDATE couple_sessions SET status = %s, result = %s, share_id = %s, "
            "updated_at = now() WHERE id = %s",
            ("hazir" if result is not None else "hata", self._json(result), share_id, session_id),
        )

    def purge_expired(self):
        removed = self._run("DELETE FROM results WHERE expires_at <= now()", fetch="count")
        removed += self._run("DELETE FROM couple_sessions WHERE expires_at <= now()", fetch="count")
        return removed


def create_store() -> Store:
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return PostgresStore(dsn)
    log.warning("DATABASE_URL tanımsız: veriler bellekte tutulur ve yeniden başlatmada silinir.")
    return MemoryStore()
