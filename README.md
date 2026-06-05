# 🛡️ Sentinel-X: Data Intelligence Dashboard

Sentinel-X adalah platform *batch-processing* dan *monitoring* intelijen media sosial yang ditenagai oleh kecerdasan buatan (Gemini AI). Aplikasi ini dirancang untuk membaca data ekstraksi/scraping dari platform X (Twitter) secara mentah dan mengubahnya menjadi *dashboard* laporan interaktif berskala profesional layaknya sistem buatan korporasi.

## ✨ Fitur Utama (X Edition)
Sentinel-X melakukan otomasi analisis mendalam ke dalam **9 Dimensi Fitur Utama**:
1. **Volume & Trend Analysis:** Memetakan agregat *mention*, interaksi, dan pergerakan tren isu dari waktu ke waktu (*Peak Time*).
2. **Sentiment Analysis:** Memilah polarisasi opini audiens (Positif, Negatif, Netral) beserta pergerakannya setiap jam.
3. **Emotion Analysis:** Mengekstraksi emosi spesifik di balik teks (Marah, Sedih, Takut, Antisipasi, dll).
4. **Social Network Analysis (SNA):** Merender graf jaringan interaksi (*Nodes* & *Edges*) secara interaktif langsung di *dashboard* untuk memetakan kubu Pro dan Kontra.
5. **KOL & Actor Analysis:** Mendeteksi akun *Top Influencers (Hubs)* serta menebak kecenderungan karakter akun (Organik vs Terkoordinasi/Buzzer).
6. **Issue & Stakeholder Analysis:** Mengelompokkan jutaan twit ke dalam klaster narasi (topik) utama yang mendominasi percakapan.
7. **Top Post & Engagement:** Menyusun katalog otomatis konten mana yang mendulang views dan likes tertinggi.
8. **Wordcloud (Leksikon):** Visualisasi kata kunci yang paling sering muncul (dengan pembersihan *stopwords* khusus bahasa Indonesia gaul).
9. **Hashtag Analysis:** Pemetaan *Top Hashtags* penggerak kampanye.

## 🛠️ Tech Stack
- **Frontend / Dashboard:** [Streamlit](https://streamlit.io/)
- **Data Manipulation:** Pandas, Regex
- **AI Engine:** Google Gemini (`google-genai` SDK) dengan model `gemini-3.1-flash-lite`.
- **Visualisasi Grafik:** Plotly Express, Matplotlib, WordCloud.
- **SNA Map:** NetworkX, PyVis.

---

## ⚙️ Cara Instalasi & Setup

1. **Instalasi Dependensi**
   Pastikan Anda telah menginstal Python 3.10 ke atas. Buka terminal dan jalankan perintah:
   ```bash
   pip install -r requirements.txt
   ```

2. **Pengaturan API Key**
   Sistem ini menggunakan kecerdasan Gemini AI. Anda memerlukan API Key gratis dari [Google AI Studio](https://aistudio.google.com/).
   - Salin file `.env.example` dan ubah namanya menjadi `.env`
   - Buka file `.env` dan masukkan API Key Anda:
     ```ini
     GEMINI_API_KEY=KODE_API_KEY_ANDA_DISINI
     ```

## 🚀 Cara Menjalankan Aplikasi

Jalankan perintah ini di dalam folder proyek melalui terminal/CMD:
```bash
streamlit run app.py
```
*Browser* Anda akan otomatis terbuka ke alamat `http://localhost:8501`.

## 📁 Struktur Format Dataset
Sistem membaca file bertipe `.csv` atau `.xlsx`. Pastikan kolom-kolom berikut ada secara tepat di baris pertama file Anda:
`['Tanggal', 'Waktu', 'X akun', 'Konten', 'Komentar', 'Repost', 'Likes', 'Views', 'Link']`

*Catatan: Jika ada kolom metrik (seperti Views atau Likes) yang kosong, sistem secara otomatis akan membersihkannya dan menganggap nilainya 0, sehingga proses AI tidak akan terhenti.*

## 💡 Keunggulan Sistem Batch & Checkpoint
Sistem dibekali mekanisme proteksi kegagalan. Model AI akan menarik data sebanyak **25 baris per sekali jalan**. 
Jika API Key Anda menyentuh limit harian atau server Google mengalami kelebihan beban, skrip telah dilindungi dengan `tenacity` yang bertugas untuk melakukan jeda sesaat lalu otomatis mengirim ulang (*auto-retry*), sehingga tidak ada satu data pun yang terlewati dengan pesan *error* fatal.
