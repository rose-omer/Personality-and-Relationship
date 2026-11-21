import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai import AnalysisError, FakeAnalyzer  # noqa: E402
from app import QUESTIONS, create_app  # noqa: E402
from db import MemoryStore  # noqa: E402

TEST_CONFIG = {
    "SECRET_KEY": "test-anahtari",
    "TESTING": True,
    "WTF_CSRF_ENABLED": False,
    "RATELIMIT_ENABLED": False,
}


class CountingAnalyzer(FakeAnalyzer):
    """Sahte analizci: çağrıları sayar, istenirse hata verir."""

    def __init__(self) -> None:
        self.single_calls: list[tuple] = []
        self.couple_calls: list[tuple] = []
        self.fail = False

    def analyze_single(self, pairs, nickname):
        self.single_calls.append((pairs, nickname))
        if self.fail:
            raise AnalysisError("sahte hata")
        return super().analyze_single(pairs, nickname)

    def analyze_couple(self, name1, pairs1, name2, pairs2):
        self.couple_calls.append((name1, pairs1, name2, pairs2))
        if self.fail:
            raise AnalysisError("sahte hata")
        return super().analyze_couple(name1, pairs1, name2, pairs2)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ("DATABASE_URL", "AI_FAKE", "RENDER", "GEMINI_MODEL"):
        monkeypatch.delenv(key, raising=False)
    # .env dosyası testleri etkilemesin.
    monkeypatch.setattr("app.load_dotenv", lambda: None)


@pytest.fixture
def store():
    return MemoryStore()


@pytest.fixture
def analyzer():
    return CountingAnalyzer()


@pytest.fixture
def make_app(store, analyzer):
    def factory(**overrides):
        return create_app({**TEST_CONFIG, **overrides}, store=store, analyzer=analyzer)

    return factory


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def client(app):
    return app.test_client()


def valid_answers(pick: int = 0) -> dict[str, str]:
    return {q["id"]: q["options"][pick % len(q["options"])] for q in QUESTIONS}


@pytest.fixture
def answers():
    return valid_answers()
