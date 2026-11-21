import re
import uuid
from datetime import UTC, datetime, timedelta

from tests.conftest import valid_answers


def start_session(client) -> str:
    response = client.post("/test/couple", data={"name1": "Ada", "name2": "Can", "onay": "1"})
    assert response.status_code == 200
    match = re.search(r"/test/couple/([0-9a-f-]{36})/user1", response.get_data(as_text=True))
    assert match
    return match.group(1)


def answer(client, session_id, user, pick=0):
    return client.post(
        f"/test/couple/{session_id}/{user}", data={**valid_answers(pick), "onay": "1"}
    )


def test_first_user_waits_for_partner(client, analyzer):
    session_id = start_session(client)
    response = answer(client, session_id, "user1")
    assert response.status_code == 303
    page = client.get(f"/test/couple/{session_id}/user1").get_data(as_text=True)
    assert "Can henüz bitirmedi" in page
    assert analyzer.couple_calls == []
    assert client.get(f"/api/check_analysis/{session_id}").get_json() == {
        "status": "bekliyor",
        "result_url": None,
    }


def test_analysis_runs_once_and_refresh_does_not_call_again(client, analyzer):
    session_id = start_session(client)
    answer(client, session_id, "user1")
    response = answer(client, session_id, "user2", pick=1)
    assert response.status_code == 303
    assert len(analyzer.couple_calls) == 1

    # Yenileme ve tekrar gönderim yeni çağrı yapmaz.
    for _ in range(3):
        page = client.get(f"/analyze/couple?session_id={session_id}")
        assert page.status_code == 302
    answer(client, session_id, "user2")
    assert len(analyzer.couple_calls) == 1

    status = client.get(f"/api/check_analysis/{session_id}").get_json()
    assert status["status"] == "hazir"
    result = client.get(status["result_url"], follow_redirects=True).get_data(as_text=True)
    assert "İlişki uyumunuz" in result
    assert "Ortak yönleriniz" in result
    assert "Ada ve Can" in result  # Katılımcı adları görür.


def test_first_finisher_owns_result_after_polling(app):
    """İlk bitiren bekleme sayfasından yoklamayla sonuca gider; adları ve sil düğmesini görür."""
    first, second = app.test_client(), app.test_client()
    session_id = start_session(first)
    answer(first, session_id, "user1")
    answer(second, session_id, "user2")

    status = first.get(f"/api/check_analysis/{session_id}").get_json()
    assert status["status"] == "hazir"
    page = first.get(status["result_url"], follow_redirects=True).get_data(as_text=True)
    assert "Ada ve Can" in page
    assert "Sonucumu sil" in page


def test_stranger_does_not_see_names_on_shared_couple_result(app, client):
    session_id = start_session(client)
    answer(client, session_id, "user1")
    answer(client, session_id, "user2")
    status_url = client.get(f"/api/check_analysis/{session_id}").get_json()["result_url"]
    url = client.get(status_url).headers["Location"]
    assert url.startswith("/r/")
    stranger_page = app.test_client().get(url).get_data(as_text=True)
    assert "İlişki uyumunuz" in stranger_page
    assert "Ada ve Can" not in stranger_page


def test_session_survives_app_restart(make_app, analyzer):
    first = make_app().test_client()
    session_id = start_session(first)
    answer(first, session_id, "user1")

    # Yeni uygulama örneği = yeniden başlatılmış servis; veri depoda kalır.
    second = make_app().test_client()
    assert second.get(f"/test/couple/{session_id}/user2").status_code == 200
    answer(second, session_id, "user2")
    assert len(analyzer.couple_calls) == 1
    assert second.get(f"/api/check_analysis/{session_id}").get_json()["status"] == "hazir"


def test_claim_is_single_shot(store):
    session_id = str(uuid.uuid4())
    store.create_couple(session_id, "Ada", "Can")
    assert store.claim_analysis(session_id) is False  # Cevaplar eksik.
    store.save_answers(session_id, "user1", ["a"])
    store.save_answers(session_id, "user2", ["b"])
    assert store.claim_analysis(session_id) is True
    assert store.claim_analysis(session_id) is False


def test_answers_cannot_be_overwritten(store):
    session_id = str(uuid.uuid4())
    store.create_couple(session_id, "Ada", "Can")
    assert store.save_answers(session_id, "user1", ["ilk"]) is True
    assert store.save_answers(session_id, "user1", ["ikinci"]) is False
    assert store.get_couple(session_id).answers1 == ["ilk"]


def test_failed_analysis_can_be_retried(client, analyzer):
    session_id = start_session(client)
    answer(client, session_id, "user1")
    analyzer.fail = True
    answer(client, session_id, "user2")

    page = client.get(f"/analyze/couple?session_id={session_id}")
    assert page.status_code == 503
    assert "Cevaplarınız kaydedildi" in page.get_data(as_text=True)

    analyzer.fail = False
    retry = client.post("/analyze/couple/retry", data={"session_id": session_id})
    assert retry.status_code == 303
    assert len(analyzer.couple_calls) == 2
    assert client.get(f"/api/check_analysis/{session_id}").get_json()["status"] == "hazir"


def test_retry_does_not_rerun_finished_analysis(client, analyzer):
    session_id = start_session(client)
    answer(client, session_id, "user1")
    answer(client, session_id, "user2")
    client.post("/analyze/couple/retry", data={"session_id": session_id})
    assert len(analyzer.couple_calls) == 1


def test_unknown_or_bad_session_returns_404(client):
    assert client.get(f"/test/couple/{uuid.uuid4()}/user1").status_code == 404
    assert client.get("/test/couple/bozuk-kimlik/user1").status_code == 404
    session_id = start_session(client)
    assert client.get(f"/test/couple/{session_id}/user3").status_code == 404
    assert client.get("/api/check_analysis/bozuk").status_code == 404


def test_expired_session_returns_404(client, store):
    session_id = start_session(client)
    store._couples[session_id]["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
    response = client.get(f"/test/couple/{session_id}/user1")
    assert response.status_code == 404
    assert "7 gün" in response.get_data(as_text=True)


def test_purge_removes_expired_rows(store):
    session_id = str(uuid.uuid4())
    store.create_couple(session_id, "Ada", "Can")
    store.save_result("abcdefghijkl", None, [], {"x": 1})
    store._couples[session_id]["expires_at"] = datetime.now(UTC) - timedelta(days=1)
    store._results["abcdefghijkl"]["expires_at"] = datetime.now(UTC) - timedelta(days=1)
    assert store.purge_expired() == 2


def test_each_partner_gets_own_ink(client):
    """Birinci kişi pembe, ikinci kişi mavi mürekkeple basılır."""
    session_id = start_session(client)
    first = client.get(f"/test/couple/{session_id}/user1").get_data(as_text=True)
    second = client.get(f"/test/couple/{session_id}/user2").get_data(as_text=True)
    assert "ink-blue" not in first
    assert "Sen, pembe mürekkep" in first
    assert "ink-blue" in second
    assert "Sen, mavi mürekkep" in second


def test_stranger_sees_letters_instead_of_names_in_diagram(app):
    owner, stranger = app.test_client(), app.test_client()
    session_id = start_session(owner)
    answer(owner, session_id, "user1")
    answer(owner, session_id, "user2", pick=1)
    status = owner.get(f"/api/check_analysis/{session_id}").get_json()
    location = owner.get(status["result_url"]).headers["Location"]
    owner_page = owner.get(location).get_data(as_text=True)
    stranger_page = stranger.get(location).get_data(as_text=True)
    assert "pembe daire Ada, mavi daire Can" in owner_page
    assert "pembe daire A, mavi daire B" in stranger_page
    assert "Ada" not in stranger_page


def test_couple_result_overlays_both_axes(client, store):
    """Çift sonucunda dört eksen iki mürekkeple üst üste basılır."""
    session_id = start_session(client)
    answer(client, session_id, "user1")
    answer(client, session_id, "user2", pick=1)
    status = client.get(f"/api/check_analysis/{session_id}").get_json()
    page = client.get(status["result_url"], follow_redirects=True).get_data(as_text=True)
    result = store.get_couple(session_id).result
    assert "Dört eksen üst üste" in page
    assert page.count('class="bar bar--duo"') == 4
    a, b = result["eksenler_a"]["sosyallik"], result["eksenler_b"]["sosyallik"]
    assert f"Ada {a}, Can {b}" in page


def test_old_couple_result_without_axes_still_renders(client, store):
    """Eksensiz eski kayıt bozulmaz; eksen bölümü gizlenir."""
    session_id = str(uuid.uuid4())
    store.create_couple(session_id, "Ada", "Can")
    old = {
        "uyum_skoru": 60,
        "ozet": "Özet.",
        "ortak_yonler": ["a", "b"],
        "farklar": ["c"],
        "iletisim_onerisi": "Konuşun.",
    }
    store.finish_analysis(session_id, old, "abcdefghijkm")
    page = client.get("/r/abcdefghijkm")
    assert page.status_code == 200
    assert "Dört eksen üst üste" not in page.get_data(as_text=True)
