from flask import Flask, render_template, request, redirect, url_for
import uuid
import google.generativeai as genai
import json
from datetime import datetime
import os
from db import get_db_connection

app = Flask(__name__)
app.secret_key = 'gizli-anahtar'

# Gemini API yapılandırması
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-flash-latest")

# Soruları yükle
with open("questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

# Bellek içi oturumlar
SESSIONS = {}

@app.route("/")
def index():
    return render_template("index.html")

def get_user_ip():
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0]
    return request.remote_addr

@app.route("/test/single", methods=["GET", "POST"])
def test_single():
    if request.method == "POST":
        user_name = request.form.get("username")
        ip_address = get_user_ip()  # 👈 IP adresi çekiliyor

        if user_name and all(q["id"] not in request.form for q in QUESTIONS):
            return render_template("test_single.html", questions=QUESTIONS, user_name=user_name)

        answers = [request.form.get(q["id"]) for q in QUESTIONS]
        result = analyze_single_ai(answers)

        save_test_result(user_name or "Anonim", "single", answers, result["yorum"], ip_address)

        return render_template("result.html", result=result)

    return render_template("test_single.html", questions=QUESTIONS)

@app.route("/test/couple", methods=["GET"])
def test_couple_start():
    return render_template("start_couple.html")

@app.route("/test/couple", methods=["POST"])
def test_couple_start_post():
    name1 = request.form.get("name1").strip()
    name2 = request.form.get("name2").strip()

    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "user1": {"name": name1, "answers": None},
        "user2": {"name": name2, "answers": None}
    }

    link1 = url_for("test_couple_user", session_id=session_id, user="user1", _external=True)
    link2 = url_for("test_couple_user", session_id=session_id, user="user2", _external=True)

    return render_template("start_couple_links.html", name1=name1, name2=name2, link1=link1, link2=link2)

@app.route("/test/couple/<session_id>/<user>", methods=["GET", "POST"])
def test_couple_user(session_id, user):
    session = SESSIONS.get(session_id)
    if not session or user not in session:
        return "Geçersiz oturum veya kullanıcı", 404

    if request.method == "POST":
        answers = [request.form.get(q["id"]) for q in QUESTIONS]
        session[user]["answers"] = answers
        session[user]["ip"] = get_user_ip()  # 👈 IP kaydı burada

        if session["user1"]["answers"] and session["user2"]["answers"]:
            return redirect(url_for("analyze_couple", session_id=session_id))
        else:
            return render_template("wait.html", name=session[user]["name"], session_id=session_id)

    return render_template("test_single.html", questions=QUESTIONS, user_name=session[user]["name"])

@app.route("/analyze/couple")
def analyze_couple():
    session_id = request.args.get("session_id")
    session = SESSIONS.get(session_id)

    if not session or not session["user1"]["answers"] or not session["user2"]["answers"]:
        return "Eksik oturum verisi", 400

    answers1 = session["user1"]["answers"]
    answers2 = session["user2"]["answers"]

    ip1 = session["user1"].get("ip") or "Bilinmiyor"
    ip2 = session["user2"].get("ip") or "Bilinmiyor"

    prompt = f"""Kullanıcı 1: {session["user1"]["name"]}
    Cevapları: {answers1}

    Kullanıcı 2: {session["user2"]["name"]}
    Cevapları: {answers2}

    Bu iki kişinin cevaplarına göre detaylı bir ilişki uyumluluk analizi yapmanı istiyorum:
    - 🔢 Uyum Skoru (%)
    - 🤝 Ortak Yönler
    - ⚖️ Zıt Yönler
    - 🧠 Sosyal & Duygusal Uyum
    - 💡 Genel Yorum
    - 📝 Tavsiye
    """

    try:
        response = model.generate_content(prompt)
        yorum = response.text
        session["yorum"] = yorum

        save_couple_result(
            session_id,
            session["user1"]["name"],
            session["user2"]["name"],
            answers1,
            answers2,
            yorum,
            ip1,
            ip2
        )
    except Exception as e:
        yorum = f"AI analiz hatası: {str(e)}"

    return render_template("result.html", yorum=yorum)


def analyze_single_ai(answers):
    prompt = f"""
    Kullanıcı aşağıdaki çoktan seçmeli kişilik testi sorularını cevapladı:

    Cevaplar: {answers}

    Bu cevaplara göre aşağıdaki başlıklarda kişisel bir analiz yapmanı istiyorum:
    - 💪 Güçlü Yönler
    - 🧱 Geliştirilebilir Alanlar
    - 🧠 Genel Kişilik Yorumu
    - 📊 Uyum Skoru (%)

    Lütfen açıklayıcı, kullanıcı dostu ve kişisel bir dille yaz.
    """

    try:
        response = model.generate_content(prompt)
        return {
            "başlık": "Kişilik Analizi",
            "yorum": response.text
        }
    except Exception as e:
        return {
            "başlık": "Kişilik Analizi",
            "yorum": f"AI hatası: {str(e)}"
        }

# 🔽 Veritabanı fonksiyonları

def save_test_result(user_name, test_type, answers, analysis, ip_address):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO test_results (user_name, test_type, answers, analysis, ip_address)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_name, test_type, json.dumps(answers), analysis, ip_address)
        )
        conn.commit()
        cur.close()
    except Exception as e:
        if conn:
            conn.rollback()
        print("DB kaydı sırasında hata:", e)
        raise
    finally:
        if conn:
            conn.close()

def save_couple_result(session_id, user1_name, user2_name, answers1, answers2, analysis, ip1, ip2):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO couple_test_results
            (session_id, user1_name, user2_name, user1_answers, user2_answers, analysis, user1_ip, user2_ip)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session_id,
                user1_name,
                user2_name,
                json.dumps(answers1),
                json.dumps(answers2),
                analysis,
                ip1,
                ip2
            )
        )
        conn.commit()
        cur.close()
    except Exception as e:
        if conn:
            conn.rollback()
        print("Couple testi DB hatası:", e)
        raise
    finally:
        if conn:
            conn.close()

@app.route("/api/check_analysis/<session_id>")
def check_analysis(session_id):
    session = SESSIONS.get(session_id)
    if session and "yorum" in session:
        return {"analiz": session["yorum"]}
    return {"analiz": None}


if __name__ == "__main__":
    app.run(debug=True)
