import re


def test_post_without_token_returns_400(make_app):
    client = make_app(WTF_CSRF_ENABLED=True).test_client()
    response = client.post("/test/couple", data={"name1": "Ada", "name2": "Can", "onay": "1"})
    assert response.status_code == 400
    assert "Form süresi doldu" in response.get_data(as_text=True)


def test_post_with_token_succeeds(make_app):
    client = make_app(WTF_CSRF_ENABLED=True).test_client()
    page = client.get("/test/couple").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    response = client.post(
        "/test/couple", data={"name1": "Ada", "name2": "Can", "onay": "1", "csrf_token": token}
    )
    assert response.status_code == 200


def test_polling_get_needs_no_token(make_app):
    client = make_app(WTF_CSRF_ENABLED=True).test_client()
    assert client.get("/api/check_analysis/bozuk").status_code == 404
