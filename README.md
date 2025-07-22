# 🧠 AI Destekli Görselli Kişilik & İlişki Testi
[🔗 Uygulamayı hemen deneyin](https://personality-and-relationship.onrender.com)
## 📌 EMAR Yapay Zeka Staj Projesi

Bu proje, Emar bünyesindeki staj sürecim boyunca geliştirdiğim yenilikçi bir yapay zekâ uygulamasıdır. Staj süresi boyunca Python (Flask), yapay zekâ API entegrasyonları ve modern web teknolojileri üzerinde pratik çalışmalar gerçekleştirdim. Özellikle kullanıcı etkileşimli testler tasarlayarak, verilerin anlamlı çıktılara dönüştürülmesini sağlayan sistemler geliştirdim. Geliştirme süreci boyunca yazılım mimarisi, kullanıcı deneyimi ve veri analitiği konularında derinlemesine bilgi sahibi oldum.


Bu proje, kullanıcıların kişilik özelliklerini ve çiftlerin ilişkisel uyumlarını analiz eden yapay zeka destekli bir test uygulamasıdır. Flask altyapısı üzerine kurulmuş olan bu sistem, Google Gemini API kullanarak analizler yapar ve sonucu kullanıcıya sunar.

Testler iki modda çalışır:
- **Tekli Mod (Single):** Bireyin kişilik analizi yapılır.
- **İkili Mod (Couple):** İki kullanıcının cevapları karşılaştırılarak ilişki uyumu hesaplanır.

---

## 🖼️ Özellikler

- 📸 Resimli ve metin tabanlı sorular (toplam 16 soru)
- ✨ Google Gemini Pro AI ile analiz
- 👤 Kişilik değerlendirmesi
- 💑 İlişki uyumu testi
- 🌐 Render.com üzerinden canlı dağıtım
- 📝 Kolay arayüz, sade HTML + Jinja2 şablon yapısı

---

## 📂 Proje Yapısı
```bash

proje-klasörü/
│
├── app.py # Ana Flask uygulaması
├── requirements.txt # Gerekli kütüphaneler
├── Procfile # Render için çalışma komutu
├── questions.json # Soru listesi (görselli ve metinli)
├── templates/ # HTML şablonları
│ ├── index.html
│ ├── test_single.html
│ ├── start_couple.html
│ ├── wait.html
│ └── result.html

```


---

## 🚀 Render.com Üzerinden Yayınlama (Deployment)

### 1. GitHub’a Yükleyin

Projeyi bir GitHub reposu olarak paylaşın. Aşağıdaki dosyaların eksiksiz olduğundan emin olun:

- `app.py`
- `requirements.txt`
- `Procfile`
- `questions.json`
- `templates/`  

### 2. Render.com’a Giriş Yapın

- [https://render.com](https://render.com) adresine gidin
- Giriş yapın ve **"New + → Web Service"** seçin
- GitHub hesabınızı bağlayın ve projenizi seçin

### 3. Servis Ayarları

- **Environment:** Python
- **Start Command:**



## 🔐 API Anahtarı
- Gemini API'yi kullanabilmek için bir Google API Key'e ihtiyacınız var. Şuradan alınabilir:

👉 https://makersuite.google.com/app/apikey
## Ekran Görüntüleri
<img width="1912" height="881" alt="image" src="https://github.com/user-attachments/assets/84d3a338-2087-46ca-aff4-efac49d8808c" />
<img width="1918" height="909" alt="image" src="https://github.com/user-attachments/assets/04627064-681c-4111-a469-cd627285328a" />
<img width="1910" height="890" alt="image" src="https://github.com/user-attachments/assets/99ba90b1-9cea-4c71-8949-e3bdff51713d" />

## 👨‍💻 Geliştirici Notları
- Proje sade, modüler ve genişletilebilir şekilde tasarlanmıştır.

- Görseller Unsplash üzerinden alınmıştır, telif haklarına dikkat edilmelidir.

- questions.json dosyasına yeni sorular ekleyerek sistemi kolayca büyütebilirsiniz.

## 🧠 Yapay Zeka Modeli
- Proje, Google'ın Gemini-Pro modelini kullanmaktadır. API üzerinden doğal dilde analiz yapar ve sonuçları kullanıcı dostu şekilde sunar.

