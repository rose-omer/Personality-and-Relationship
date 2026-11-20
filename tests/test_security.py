import pytest

from app import create_app
from db import MemoryStore
from tests.conftest import TEST_CONFIG, CountingAnalyzer


def test_app_refuses_to_start_without_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({"TESTING": True}, store=MemoryStore(), analyzer=CountingAnalyzer())


def test_secret_key_read_from_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "ortamdan")
    app = create_app({"TESTING": True}, store=MemoryStore(), analyzer=CountingAnalyzer())
    assert app.secret_key == "ortamdan"


def test_security_headers(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_forwarded_for_spoofing_is_ignored(app):
    seen = []

    @app.get("/_ip")
    def _ip():
        from flask import request

        seen.append(request.remote_addr)
        return "ok"

    # Proxy tek bir değer ekler (ProxyFix x_for=1): istemcinin yazdığı ilk değer kullanılmaz.
    app.test_client().get(
        "/_ip",
        headers={"X-Forwarded-For": "6.6.6.6, 10.0.0.7"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert seen == ["10.0.0.7"]


def test_rate_limit_returns_429_page(answers):
    app = create_app(
        {**TEST_CONFIG, "RATELIMIT_ENABLED": True},
        store=MemoryStore(),
        analyzer=CountingAnalyzer(),
    )
    client = app.test_client()
    data = {**answers, "onay": "1"}
    codes = [client.post("/test/single", data=data).status_code for _ in range(6)]
    assert codes[:5] == [303] * 5
    assert codes[5] == 429
    assert "1 dakika sonra tekrar dene" in client.post("/test/single", data=data).get_data(
        as_text=True
    )


@pytest.mark.parametrize("path", ["Procfile", "render.yaml"])
def test_single_worker_keeps_memory_rate_limit_exact(path):
    # memory:// sayacı süreç başınadır; 2 worker sınırı iki katına çıkarırdı.
    source = open(path, encoding="utf-8").read()
    assert "--workers 1" in source
    assert "--threads" in source


def test_debug_is_off_by_default():
    source = open("app.py", encoding="utf-8").read()
    assert 'debug=os.getenv("FLASK_DEBUG") == "1"' in source
    assert "gizli-anahtar" not in source
