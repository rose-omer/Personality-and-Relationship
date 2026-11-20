import io

from PIL import Image

from db import StoreError


def submit(client, answers, **extra):
    return client.post("/test/single", data={**answers, "onay": "1", **extra})


def test_single_flow_redirects_to_share_page(client, answers, analyzer):
    response = submit(client, answers)
    assert response.status_code == 303
    assert response.headers["Location"].startswith("/r/")
    assert len(analyzer.single_calls) == 1


def test_prompt_pairs_contain_question_text(client, answers, analyzer):
    submit(client, answers)
    pairs, _ = analyzer.single_calls[0]
    assert pairs[0] == ("Genellikle sosyal bir ortamda kendini rahat hisseder misin?", "Evet")


def test_result_page_shows_structured_fields(client, answers):
    location = submit(client, answers).headers["Location"]
    body = client.get(location).get_data(as_text=True)
    assert "Meraklı Planlayıcı" in body
    assert "Dört eksende sen" in body
    assert "Güçlü yönlerin" in body
    assert "Gelişim alanların" in body
    assert "Eğlence amaçlıdır, klinik değerlendirme değildir." in body
    assert "**" not in body
    assert 'property="og:image"' in body


def test_nickname_hidden_on_card_by_default(client, answers):
    location = submit(client, answers, username="Gizli Kedi").headers["Location"]
    assert "Gizli Kedi" not in client.get(location).get_data(as_text=True)


def test_nickname_shown_when_user_opts_in(client, answers):
    location = submit(client, answers, username="Gizli Kedi", karta_ekle="1").headers["Location"]
    assert "Gizli Kedi" in client.get(location).get_data(as_text=True)


def test_analysis_error_keeps_answers_for_retry(client, answers, analyzer):
    analyzer.fail = True
    response = submit(client, answers)
    body = response.get_data(as_text=True)
    assert response.status_code == 503
    assert "Analiz şu an yapılamadı" in body
    assert 'name="q16"' in body
    assert "sahte hata" not in body  # İstisna ayrıntısı kullanıcıya sızmaz.

    analyzer.fail = False
    assert submit(client, answers).status_code == 303


def test_store_failure_still_shows_result(client, answers, store, monkeypatch):
    def broken(*_args, **_kwargs):
        raise StoreError("bağlantı yok")

    monkeypatch.setattr(store, "save_result", broken)
    response = submit(client, answers)
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Meraklı Planlayıcı" in body
    assert "kaydedilemedi" in body


def test_owner_can_delete_result(client, answers):
    location = submit(client, answers).headers["Location"]
    share_id = location.rsplit("/", 1)[-1]
    assert "Sonucumu sil" in client.get(location).get_data(as_text=True)

    response = client.post(f"/r/{share_id}/sil")
    assert response.status_code == 303
    gone = client.get(location)
    assert gone.status_code == 404
    assert "Bu sonuç artık yok" in gone.get_data(as_text=True)


def test_other_visitor_cannot_delete_result(app, client, answers):
    location = submit(client, answers).headers["Location"]
    share_id = location.rsplit("/", 1)[-1]
    stranger = app.test_client()
    assert "Sonucumu sil" not in stranger.get(location).get_data(as_text=True)
    assert stranger.post(f"/r/{share_id}/sil").status_code == 404
    assert client.get(location).status_code == 200


def test_share_image_is_1200x630_png(client, answers):
    location = submit(client, answers).headers["Location"]
    response = client.get(f"{location}.png")
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert Image.open(io.BytesIO(response.data)).size == (1200, 630)


def test_unknown_share_id_returns_404(client):
    assert client.get("/r/abcdefghijkl").status_code == 404
    assert client.get("/r/../etc").status_code == 404
    assert client.get("/r/kisa").status_code == 404


def test_pages_render(client):
    for path in ("/", "/test/single", "/test/couple", "/gizlilik"):
        response = client.get(path)
        assert response.status_code == 200, path
    assert client.get("/saglik").get_json() == {"durum": "ok"}


def test_question_images_have_alt_and_lazy_loading(client):
    body = client.get("/test/single").get_data(as_text=True)
    assert 'alt="Soru görseli"' not in body
    assert 'alt="Renkli bir bulutsu ve yıldızlarla dolu uzay görüntüsü"' in body
    assert 'loading="lazy"' in body
