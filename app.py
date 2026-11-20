"""Kişilik ve ilişki testi: Flask rotaları."""

import json
import logging
import os
import re
import secrets
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import (
    Blueprint,
    Flask,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

import og_image
from ai import AnalysisError, Analyzer, create_analyzer
from db import CoupleSession, Store, StoreError, create_store
from models import AXIS_LABELS

BASE_DIR = Path(__file__).resolve().parent
NAME_MAX = 40
ANALYSIS_LIMIT = "5/minute;50/day"
SHARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{12}$")
USERS = ("user1", "user2")
OWNED_MAX = 20

with open(BASE_DIR / "questions.json", encoding="utf-8") as f:
    QUESTIONS: list[dict[str, Any]] = json.load(f)

csrf = CSRFProtect()
# Depo RATELIMIT_STORAGE_URI ile seçilir (create_app). memory:// süreç başınadır;
# bu yüzden canlıda tek worker + iş parçacığı koşar (Procfile, render.yaml).
limiter = Limiter(get_remote_address)
bp = Blueprint("main", __name__)


class FormError(Exception):
    """Form doğrulanamadı. `errors` alan adını kullanıcı mesajına eşler."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__(", ".join(errors))
        self.errors = errors


# --- Yardımcılar -----------------------------------------------------------------


def clean_name(value: str | None) -> str:
    """Boşlukları sadeleştirir, denetim karakterlerini atar, 40 karakterle keser."""
    text = "".join(ch for ch in (value or "") if ch.isprintable())
    return " ".join(text.split())[:NAME_MAX]


def validate_answers(form: MultiDict) -> list[str]:
    """Her soru için değer zorunlu ve seçeneklerden biri olmalı."""
    answers: list[str] = []
    errors: dict[str, str] = {}
    for q in QUESTIONS:
        value = form.get(q["id"])
        if value not in q["options"]:
            errors[q["id"]] = "Bu soruyu cevapla."
        answers.append(value or "")
    if not form.get("onay"):
        errors["onay"] = "Teste başlamak için aydınlatma metnini onayla."
    if errors:
        raise FormError(errors)
    return answers


def qa_pairs(answers: list[str]) -> list[tuple[str, str]]:
    return [(q["text"], answer) for q, answer in zip(QUESTIONS, answers, strict=True)]


def store() -> Store:
    return current_app.extensions["store"]


def analyzer() -> Analyzer:
    return current_app.extensions["analyzer"]


def new_share_id() -> str:
    return secrets.token_urlsafe(9)


def remember_owned(share_id: str) -> None:
    owned = [s for s in session.get("owned", []) if s != share_id]
    session["owned"] = (owned + [share_id])[-OWNED_MAX:]


def owns(share_id: str) -> bool:
    return share_id in session.get("owned", [])


def load_couple(session_id: str) -> CoupleSession:
    try:
        uuid.UUID(session_id)
    except ValueError:
        abort(404)
    couple = store().get_couple(session_id)
    if couple is None:
        abort(404)
    return couple


def run_couple_analysis(couple_id: str) -> None:
    """Yalnız claim_analysis True döndüren istek çağırır; analiz bir kez çalışır."""
    couple = store().get_couple(couple_id)
    if couple is None or couple.answers1 is None or couple.answers2 is None:
        return
    try:
        result = analyzer().analyze_couple(
            couple.name1, qa_pairs(couple.answers1), couple.name2, qa_pairs(couple.answers2)
        )
    except AnalysisError:
        current_app.logger.exception("Çift analizi üretilemedi (%s)", couple_id)
        store().finish_analysis(couple_id, None, None)
        return
    store().finish_analysis(couple_id, result.model_dump(), new_share_id())


def render_quiz(mode: str, status: int = 200, **context):
    return (
        render_template(
            "test_single.html",
            questions=QUESTIONS,
            mode=mode,
            errors=context.pop("errors", {}),
            selected=context.pop("selected", {}),
            **context,
        ),
        status,
    )


# --- Sayfalar --------------------------------------------------------------------


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/saglik")
def health():
    return {"durum": "ok"}


@bp.get("/gizlilik")
def privacy():
    return render_template("privacy.html")


@bp.get("/test/single")
def test_single():
    return render_quiz("single")[0]


@bp.post("/test/single")
@limiter.limit(ANALYSIS_LIMIT)
def test_single_post():
    nickname = clean_name(request.form.get("username")) or None
    show_name = bool(request.form.get("karta_ekle")) and nickname is not None
    try:
        answers = validate_answers(request.form)
    except FormError as exc:
        return render_quiz(
            "single", 400, errors=exc.errors, selected=request.form, nickname=nickname
        )

    try:
        result = analyzer().analyze_single(qa_pairs(answers), nickname)
    except AnalysisError:
        current_app.logger.exception("Tekli analiz üretilemedi")
        return render_template(
            "analysis_error.html",
            mode="single",
            answers=dict(zip((q["id"] for q in QUESTIONS), answers, strict=True)),
            nickname=nickname or "",
            show_name=show_name,
        ), 503

    share_id = new_share_id()
    data = result.model_dump()
    try:
        store().save_result(share_id, nickname if show_name else None, answers, data)
    except StoreError:
        # Sonuç kaybolmasın: kaydedemesek de kartı göster, paylaşım bağlantısı olmadan.
        current_app.logger.exception("Tekli sonuç kaydedilemedi")
        return render_template(
            "result.html",
            kind="single",
            result=data,
            share_id=None,
            owner=True,
            display_name=nickname,
            axis_labels=AXIS_LABELS,
        )
    remember_owned(share_id)
    return redirect(url_for("main.shared_result", share_id=share_id), code=303)


@bp.get("/test/couple")
def test_couple_start():
    return render_template("start_couple.html", errors={}, form={})


@bp.post("/test/couple")
@limiter.limit("10/minute;100/day")
def test_couple_start_post():
    name1 = clean_name(request.form.get("name1"))
    name2 = clean_name(request.form.get("name2"))
    errors = {}
    if not name1:
        errors["name1"] = "Birinci kişi için bir takma ad yaz."
    if not name2:
        errors["name2"] = "İkinci kişi için bir takma ad yaz."
    if not request.form.get("onay"):
        errors["onay"] = "Devam etmek için aydınlatma metnini onayla."
    if errors:
        return render_template("start_couple.html", errors=errors, form=request.form), 400

    session_id = str(uuid.uuid4())
    store().create_couple(session_id, name1, name2)
    links = {
        user: url_for("main.test_couple_user", session_id=session_id, user=user, _external=True)
        for user in USERS
    }
    return render_template("start_couple_links.html", name1=name1, name2=name2, links=links)


@bp.route("/test/couple/<session_id>/<user>", methods=["GET", "POST"])
@limiter.limit(ANALYSIS_LIMIT, methods=["POST"])
def test_couple_user(session_id, user):
    if user not in USERS:
        abort(404)
    couple = load_couple(session_id)
    partner = "user2" if user == "user1" else "user1"
    own_link = url_for("main.test_couple_user", session_id=session_id, user=user, _external=True)

    if couple.status == "hazir" and couple.share_id:
        remember_owned(couple.share_id)
        return redirect(url_for("main.shared_result", share_id=couple.share_id))

    if couple.answers_of(user) is not None:
        if request.method == "POST":
            return redirect(own_link, code=303)
        if couple.status == "hata":
            return redirect(url_for("main.analyze_couple", session_id=session_id))
        return render_template(
            "wait.html",
            name=couple.name_of(user),
            partner=couple.name_of(partner),
            session_id=session_id,
            own_link=own_link,
            status=couple.status,
            user=user,
        )

    context = {
        "nickname": couple.name_of(user),
        "partner": couple.name_of(partner),
        "user": user,
    }
    if request.method == "GET":
        return render_quiz("couple", **context)[0]

    try:
        answers = validate_answers(request.form)
    except FormError as exc:
        return render_quiz("couple", 400, errors=exc.errors, selected=request.form, **context)

    store().save_answers(session_id, user, answers)
    if store().claim_analysis(session_id):
        run_couple_analysis(session_id)
        return redirect(url_for("main.analyze_couple", session_id=session_id), code=303)
    return redirect(own_link, code=303)


@bp.get("/analyze/couple")
def analyze_couple():
    """Yalnız kayıtlı sonucu okur; Gemini'yi asla çağırmaz."""
    couple = load_couple(request.args.get("session_id", ""))
    if couple.status == "hazir" and couple.share_id:
        remember_owned(couple.share_id)
        return redirect(url_for("main.shared_result", share_id=couple.share_id))
    if couple.status == "hata":
        return render_template("analysis_error.html", mode="couple", session_id=couple.id), 503
    return render_template(
        "wait.html",
        name=None,
        partner=None,
        session_id=couple.id,
        own_link=request.url,
        status=couple.status,
    )


@bp.post("/analyze/couple/retry")
@limiter.limit(ANALYSIS_LIMIT)
def analyze_couple_retry():
    couple = load_couple(request.form.get("session_id", ""))
    if store().claim_analysis(couple.id):
        run_couple_analysis(couple.id)
    return redirect(url_for("main.analyze_couple", session_id=couple.id), code=303)


@bp.get("/api/check_analysis/<session_id>")
def check_analysis(session_id):
    try:
        uuid.UUID(session_id)
    except ValueError:
        return {"status": "yok"}, 404
    couple = store().get_couple(session_id)
    if couple is None:
        return {"status": "yok"}, 404
    result_url = None
    if couple.status in ("hazir", "hata"):
        # analyze_couple sahipliği oturuma yazar; ilk bitiren de adları ve sil düğmesini görür.
        result_url = url_for("main.analyze_couple", session_id=session_id)
    return {"status": couple.status, "result_url": result_url}


def _load_shared(share_id: str):
    if not SHARE_ID_RE.match(share_id):
        abort(404)
    shared = store().get_shared(share_id)
    if shared is None:
        abort(404, description="sonuc")
    return shared


@bp.get("/r/<share_id>")
def shared_result(share_id):
    try:
        store().purge_expired()
    except StoreError:
        current_app.logger.exception("Süresi dolan kayıtlar silinemedi")
    shared = _load_shared(share_id)
    owner = owns(share_id)
    names = None
    if shared.kind == "single":
        display_name = shared.nickname
    else:
        # Çift adları yalnız katılımcıya görünür; bağlantıyı alan başkası görmez.
        display_name = f"{shared.name1} ve {shared.name2}" if owner else None
        names = (shared.name1, shared.name2) if owner else None
    return render_template(
        "result.html",
        kind=shared.kind,
        result=shared.result,
        share_id=share_id,
        owner=owner,
        display_name=display_name,
        names=names,
        axis_labels=AXIS_LABELS,
    )


@bp.get("/r/<share_id>.png")
def shared_image(share_id):
    shared = _load_shared(share_id)
    render = og_image.render_single if shared.kind == "single" else og_image.render_couple
    response = current_app.response_class(render(shared.result), mimetype="image/png")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@bp.post("/r/<share_id>/sil")
def delete_result(share_id):
    if not SHARE_ID_RE.match(share_id) or not owns(share_id):
        abort(404)
    store().delete_shared(share_id)
    session["owned"] = [s for s in session.get("owned", []) if s != share_id]
    flash("Sonucun silindi.")
    return redirect(url_for("main.index"), code=303)


# --- Hata sayfaları --------------------------------------------------------------

ERROR_TEXT = {
    400: ("İstek tamamlanamadı", "Formdaki bilgiler eksik ya da geçersiz. Geri dönüp tekrar dene."),
    404: (
        "Bu sayfa bulunamadı",
        "Bağlantı yanlış ya da süresi dolmuş olabilir. Çift testi bağlantıları 7 gün, "
        "sonuçlar 30 gün geçerlidir.",
    ),
    429: ("Çok fazla deneme", "Çok fazla deneme; 1 dakika sonra tekrar dene."),
    500: ("Beklenmeyen bir hata oluştu", "Sorun kaydedildi. Birazdan tekrar dene."),
    503: (
        "Hizmet şu an yanıt vermiyor",
        "Veritabanına şu an ulaşılamıyor. Birkaç dakika sonra tekrar dene.",
    ),
}


def render_error(code: int, title: str | None = None, message: str | None = None):
    default_title, default_message = ERROR_TEXT.get(code, ERROR_TEXT[500])
    return render_template(
        "error.html", code=code, title=title or default_title, message=message or default_message
    ), code


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(CSRFError)
    def csrf_error(_exc):
        return render_error(
            400,
            "Form süresi doldu",
            "Güvenlik kodu eksik ya da eski. Sayfayı yenileyip tekrar dene.",
        )

    @app.errorhandler(StoreError)
    def store_error(_exc):
        app.logger.exception("Veritabanı hatası")
        return render_error(503)

    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException):
        if exc.code == 404 and exc.description == "sonuc":
            return render_error(
                404,
                "Bu sonuç artık yok",
                "Sonuç silinmiş ya da 30 günlük saklama süresi dolmuş olabilir.",
            )
        return render_error(exc.code or 500)

    @app.errorhandler(Exception)
    def unexpected_error(_exc):
        app.logger.exception("Beklenmeyen hata")
        return render_error(500)


# --- Uygulama --------------------------------------------------------------------


def create_app(
    config: dict[str, Any] | None = None,
    store: Store | None = None,
    analyzer: Analyzer | None = None,
) -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        SESSION_COOKIE_SAMESITE="Lax",
        # Render HTTPS arkasında çalışır ve RENDER değişkenini tanımlar.
        SESSION_COOKIE_SECURE=bool(os.getenv("RENDER")),
        MAX_CONTENT_LENGTH=64 * 1024,
        RATELIMIT_HEADERS_ENABLED=True,
        RATELIMIT_STORAGE_URI=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
    )
    app.config.update(config or {})
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY ortam değişkeni tanımlı değil; uygulama başlatılmadı.")

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    app.logger.setLevel(logging.INFO)
    app.extensions["store"] = store or create_store()
    app.extensions["analyzer"] = analyzer or create_analyzer()

    csrf.init_app(app)
    limiter.init_app(app)
    app.register_blueprint(bp)
    register_error_handlers(app)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' https://images.unsplash.com data:; "
            "script-src 'self'; style-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'",
        )
        return response

    return app


if __name__ == "__main__":
    create_app().run(port=int(os.getenv("PORT", "8100")), debug=os.getenv("FLASK_DEBUG") == "1")
