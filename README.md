# Kişilik ve İlişki Testi

[![CI](https://github.com/rose-omer/Personality-and-Relationship/actions/workflows/ci.yml/badge.svg)](https://github.com/rose-omer/Personality-and-Relationship/actions/workflows/ci.yml)
![Python 3.13](https://img.shields.io/badge/python-3.13-1f6b52)

16 soruluk bir kişilik testi ve iki kişilik uyum testi. Cevapları Google Gemini yorumlar; model serbest metin yerine JSON şemasına uyan yapılandırılmış çıktı döndürür. Sonuç, dört eksenli bir kart olarak gösterilir ve paylaşılabilir bir bağlantıyla (Open Graph görseliyle birlikte) açılır.

Canlı demo: https://personality-and-relationship.onrender.com
İlk açılış yaklaşık 1 dakika sürebilir (Render Free servisi 15 dakika trafiksizlikte uyur).

## Mimari

```
Tarayıcı ──► Flask (app.py)
               ├─ ai.py ──► Google Gemini API (response_json_schema, Pydantic ile doğrulama)
               ├─ db.py ──► Postgres (results, couple_sessions)
               └─ og_image.py ──► Pillow ile 1200x630 paylaşım görseli
```

| Dosya | Görev |
|---|---|
| `app.py` | Rotalar, doğrulama, hata sayfaları, CSRF, hız sınırı |
| `ai.py` | Gemini istemcisi, istemler, `FakeAnalyzer` |
| `models.py` | `SingleResult`, `CoupleResult` şemaları |
| `db.py` | `PostgresStore` (canlı), `MemoryStore` (test ve yerel) |
| `schema.sql`, `migrations/` | Veritabanı şeması ve göçler |
| `templates/`, `static/` | Tek `base.html`, tek `app.css`, aşamalı geliştirilmiş `app.js` |

## Teknik kararlar

- **JSON şeması:** Gemini `response_json_schema` ile şemaya uygun çıktı üretir. Pydantic aralıkları (0–100) ve liste uzunluklarını yeniden doğrular. Kart alanları güvenilir biçimde dolar; ham Markdown görünmez.
- **Oturumlar Postgres'te:** Çift testi oturumları `couple_sessions` tablosunda. Servis yeniden başlasa da açık oturum kaybolmaz; birden çok worker aynı veriyi görür.
- **Tek çalıştırma:** İkinci kişi bitirince koşullu `UPDATE ... RETURNING` analizi bir kez başlatır. Sonuç sayfası yalnız kayıtlı sonucu okur; yenileme Gemini'yi yeniden çağırmaz.
- **KVKK:** IP adresi veritabanına yazılmaz. Test başında aydınlatma metni ve onay kutusu var. Sonuçlar 30 gün, çift oturumları 7 gün saklanır. "Sonucumu sil" kaydı hemen siler. Aydınlatma metni: `/gizlilik`.
- **Güvenlik:** `SECRET_KEY` ortamdan okunur (yoksa uygulama açılmaz), bütün `POST` formlarında CSRF, `ProxyFix(x_for=1)`, analiz rotalarında `5/dakika; 50/gün` sınırı, sıkı CSP.
- **Hız sınırı deposu:** Sayaç varsayılan olarak bellekte (`memory://`) ve süreç başınadır. Bu yüzden servis tek worker ve 4 iş parçacığıyla koşar; sınır tam uygulanır. Worker sayısını artırırsan `RATELIMIT_STORAGE_URI` ile paylaşımlı bir depo (ör. Redis) tanımla; yoksa sınır worker sayısıyla katlanır.
- **Arayüz:** JS kapalıyken bütün sorular tek formda görünür. JS açıkken her ekranda bir soru, ilerleme çubuğu, klavyeyle tam kullanım, açık/koyu tema ve `prefers-reduced-motion` desteği var.

## Yerelde çalıştırma

Bu makinede 8000 portunu kullanma; örnekler 8100 kullanır.

```bash
python -m venv .venv
.venv/Scripts/activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env              # SECRET_KEY değerini doldur
flask --app app run --port 8100
```

- Gemini anahtarı olmadan denemek için `.env` içinde `AI_FAKE=1` yaz. Uygulama sabit bir örnek analiz döndürür.
- `DATABASE_URL` tanımsızsa veriler bellekte tutulur ve yeniden başlatmada silinir.

## Testler

```bash
ruff check .
ruff format --check .
pytest -q
```

Testler Gemini'ye gerçek çağrı yapmaz; sahte analizci kullanır. `tests/test_postgres_store.py` yalnız `TEST_DATABASE_URL` tanımlıysa çalışır (CI'da Postgres servis kapsayıcısıyla).

## Veritabanı

Yeni kurulum:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f schema.sql
```

Eski tabloların bulunduğu mevcut veritabanı:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/001_drop_ip_columns.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/002_results_and_couple_sessions.sql
# İsteğe bağlı, yedekten sonra: migrations/003_drop_legacy_tables.sql
```

Önerilen sağlayıcı: Neon Free (`sslmode=require`). Render Free Postgres 30 günde sona erer.

## Dağıtım (Render)

`render.yaml` servis ayarlarını taşır. Panodan elle kurulan mevcut serviste şunları güncelle:

- Başlatma komutu: `gunicorn "app:create_app()" --workers 1 --threads 4 --timeout 60`
- Ortam değişkenleri: `SECRET_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-3.5-flash-lite`, `DATABASE_URL`
- `GEMINI_API_KEY` ve `GOOGLE_API_KEY` birlikte tanımlanırsa `GOOGLE_API_KEY` kazanır; yalnız birini tanımla.
- Python sürümü `.python-version` dosyasından okunur (`3.13`).

## Proje geçmişi

Bu proje EMAR bünyesindeki yapay zekâ stajında başladı. Staj sürecinde Flask, yapay zekâ API entegrasyonu ve kullanıcı etkileşimli test tasarımı üzerinde çalışıldı.

Soru görselleri Unsplash'ten alınmıştır ve Unsplash lisansıyla kullanılır.

Sonuçlar eğlence amaçlıdır; klinik değerlendirme değildir.
