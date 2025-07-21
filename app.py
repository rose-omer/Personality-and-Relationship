from flask import Flask, render_template, request, redirect, url_for
import json
import uuid
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = 'gizli-anahtar'

GEMINI_API_KEY = "AIzaSyDUwoo_Dr30nqdOYJZb_K7wMZg7tS_GGXM"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-flash-latest")

with open("questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

SESSIONS = {}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/test/single", methods=["GET", "POST"])
def test_single():
    if request.method == "POST":
        answers = [request.form.get(q["id"]) for q in QUESTIONS]
        result = analyze_single(answers)
        return render_template("result.html", result=result)
    return render_template("test_single.html", questions=QUESTIONS)

@app.route("/test/couple", methods=["GET"])
def test_couple_start():
    # GET isteğinde isim formu gösterilir
    return render_template("start_couple.html")

@app.route("/test/couple", methods=["POST"])
def test_couple_start_post():
    # POST isteğinde isimleri alıp session oluştur ve link göster
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

        if session["user1"]["answers"] and session["user2"]["answers"]:
            return redirect(url_for("analyze_couple", session_id=session_id))
        else:
            return render_template("wait.html", name=session[user]["name"])

    return render_template("test_single.html", questions=QUESTIONS, user_name=session[user]["name"])

@app.route("/analyze/couple")
def analyze_couple():
    session_id = request.args.get("session_id")
    session = SESSIONS.get(session_id)

    if not session or not session["user1"]["answers"] or not session["user2"]["answers"]:
        return "Eksik oturum verisi", 400

    answers1 = session["user1"]["answers"]
    answers2 = session["user2"]["answers"]

    prompt = f"""
    Kullanıcı 1: {session["user1"]["name"]}
    Cevapları: {answers1}

    Kullanıcı 2: {session["user2"]["name"]}
    Cevapları: {answers2}

    Bu iki kişinin cevaplarına göre detaylı bir ilişki uyumluluk analizi yapmanı istiyorum. Analiz şu başlıkları içermeli:

    1. 🔢 **Uyum Skoru:** 0 ile 100 arasında bir oran ver. Sadece sayı değil, bu skoru etkileyen temel benzerlik ve farklılık noktalarını da açıkla.
    2. 🤝 **Ortak Yönler:** Hangi cevaplarda benzer düşünceler paylaştılar? Bu benzerliklerin ilişki açısından anlamını yorumla.
    3. ⚖️ **Zıt Yönler:** Farklı yanıt verdikleri soruları değerlendir ve bu farklılıkların ilişki dinamiğini nasıl etkileyebileceğini belirt.
    4. 🧠 **Duygusal ve Sosyal Uyum:** Empati, iletişim, duygusal zekâ gibi konularda nasıl bir uyum içindeler?
    5. 💡 **Genel Değerlendirme:** Tüm verileri göz önünde bulundurarak ilişkisel uyum hakkında genel bir analiz yaz. Güçlü ve zayıf yönleri objektif biçimde belirt.
    6. 📝 **Tavsiye:** Uyumun artırılması ya da çatışmaların azaltılması için kişiselleştirilmiş önerilerde bulun.

    Cevapları kullanıcı dostu, samimi ve açıklayıcı bir dille yaz. Analizlerin yapay zekâdan çıktığı hissedilmesin, bir insanın detaylı değerlendirmesi gibi olsun.
    """

    try:
        response = model.generate_content(prompt)
        yorum = response.text
    except Exception as e:
        yorum = f"AI analiz hatası: {str(e)}"

    return render_template("result.html", yorum=yorum)

def analyze_single(answers):
    positive = answers.count("Evet")
    neutral = answers.count("Biraz")
    score = int((positive + 0.5 * neutral) / len(answers) * 100)
    return {
        "başlık": "Kişilik Analizi",
        "güçlü_yönler": "Sosyal ve dengeli bir kişiliğe sahipsiniz.",
        "zayıf_yönler": "Zaman zaman kararsızlık yaşayabilirsiniz.",
        "puan": f"%{score} uyum"
    }

if __name__ == "__main__":
    app.run(debug=True)
