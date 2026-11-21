import pytest

from app import FormError, clean_name, validate_answers
from tests.conftest import valid_answers


def couple_form(**overrides):
    form = {"name1": "Ada", "name2": "Can", "onay": "1"}
    form.update(overrides)
    return {k: v for k, v in form.items() if v is not None}


@pytest.mark.parametrize("missing", ["name1", "name2"])
def test_couple_start_without_name_returns_400(client, missing):
    response = client.post("/test/couple", data=couple_form(**{missing: None}))
    assert response.status_code == 400
    assert "takma ad yaz" in response.get_data(as_text=True)


def test_couple_start_with_blank_name_returns_400(client):
    response = client.post("/test/couple", data=couple_form(name1="   "))
    assert response.status_code == 400


def test_couple_start_without_consent_returns_400(client):
    response = client.post("/test/couple", data=couple_form(onay=None))
    assert response.status_code == 400
    assert "aydınlatma metnini onayla" in response.get_data(as_text=True)


def test_long_name_is_cut_to_40_characters(client, store):
    long_name = "A" * 60
    response = client.post("/test/couple", data=couple_form(name1=long_name))
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "A" * 40 in body
    assert "A" * 41 not in body


def test_clean_name_strips_control_characters_and_spaces():
    assert clean_name("  Ada \n\t Lovelace\x00 ") == "Ada Lovelace"
    assert clean_name(None) == ""


def test_single_answer_outside_options_returns_400(client, answers):
    answers["q1"] = "Belki de"
    response = client.post("/test/single", data={**answers, "onay": "1"})
    assert response.status_code == 400
    assert "Bu soruyu cevapla." in response.get_data(as_text=True)


def test_single_missing_answer_returns_400(client, answers, analyzer):
    del answers["q16"]
    response = client.post("/test/single", data={**answers, "onay": "1"})
    assert response.status_code == 400
    assert analyzer.single_calls == []


def test_single_without_consent_returns_400(client, answers, analyzer):
    response = client.post("/test/single", data=answers)
    assert response.status_code == 400
    assert analyzer.single_calls == []


def test_empty_post_returns_400_not_500(client):
    assert client.post("/test/single", data={}).status_code == 400
    assert client.post("/test/couple", data={}).status_code == 400


def test_validate_answers_keeps_question_order():
    form = {**valid_answers(1), "onay": "1"}
    answers = validate_answers(form)
    assert len(answers) == 16
    assert answers[0] == form["q1"]


def test_validate_answers_reports_each_missing_field():
    with pytest.raises(FormError) as exc_info:
        validate_answers({"q1": "Evet"})
    assert "q1" not in exc_info.value.errors
    assert {"q2", "q16", "onay"} <= set(exc_info.value.errors)
