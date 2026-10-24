# 🤖 Telegram Media Downloader & Shazam Bot

Ushbu bot **Instagram, YouTube, TikTok va boshqa platformalardan** video va audio (MP3) larni yuklab beradi hamda **Shazam musiqalar reytingi (Top 10)** va musiqa qidirish imkoniyatini taqdim etadi!

---

## 🚀 Imkoniyatlari

1. 📥 **Video va Musiqa yuklash (Instagram, YouTube, TikTok va h.k.):**
   - Havolani botga yuborishingiz bilan bot videoni tahlil qiladi.
   - **🎬 Videoni yuklash** yoki **🎵 Musiqani (MP3) yuklash** tugmalari orqali xohlagan formatda yuklab olasiz.
2. 🏆 **Shazam Musiqalar Reytingi (Top Chart):**
   - 🌍 **Shazam Dunyo Top 10** — Dunyo bo'yicha eng mashhur top taronalar reytingi.
   - 🇺🇿 **O'zbekiston Top 10** — Hozirda O'zbekistonda eng ommabop musiqalar.
3. 🔍 **Musiqa qidirish & MP3 yuklash:**
   - Qo'shiq nomi yoki ijrochini yozib, Shazamdan qidirish va to'g'ridan-to'g'ri MP3 qilib yuklab olish.
4. 🎧 **Shazam Ovozli Aniqlash:**
   - Botga ovozli xabar (voice) yoki audio yuborsangiz, Shazam tahlil qilib, qo'shiq nomi, ijrochi va rasmini topib beradi!

---

## 💻 PyCharmda Ochish va Ishga Tushirish

### 1-qadam: Loyihani PyCharmda ochish
1. **PyCharm** dasturini oching.
2. **File -> Open...** menyusini bosing.
3. Quyidagi manzilni tanlang va oching:
   ```text
   C:\Users\umidj\.gemini\antigravity\scratch\telegram_media_bot
   ```

### 2-qadam: Python Interpreterni sozlash
Loyiha ichida barcha kerakli kutubxonalar (`aiogram`, `yt-dlp`, `shazamio` va h.k.) oldindan o'rnatilgan tayyor `.venv` muhiti mavjud.
1. PyCharmda: **File -> Settings -> Project: telegram_media_bot -> Python Interpreter**.
2. **Add Interpreter -> Add Local Interpreter...** ni bosing.
3. **Existing environment** ni tanlang va quyidagi faylni ko'rsating:
   ```text
   C:\Users\umidj\.gemini\antigravity\scratch\telegram_media_bot\.venv\Scripts\python.exe
   ```
4. **OK** tugmasini bosing.

### 3-qadam: Bot Tokenini kiritish
1. Telegramda [@BotFather](https://t.me/BotFather) ga kiring va `/newbot` buyrug'i orqali yangi bot yarating.
2. BotFather bergan tokenni nusxalang (masalan: `7123456789:AAH...`).
3. Loyiha ichidagi `.env` faylini oching va tokenni yozing:
   ```env
   BOT_TOKEN=sizning_bot_tokeningiz
   ```
4. Faylni saqlang (`Ctrl + S`).

### 4-qadam: Botni ishga tushirish
1. PyCharmda `main.py` fayli ustida sichqonchaning o'ng tugmasini bosing va **Run 'main'** ni tanlang.
2. Telegramga o'tib botingizga `/start` yuboring!

---

## 📁 Loyiha Strukturasi

```text
telegram_media_bot/
├── .venv/                 # Tayyor virtual muhit (kutubxonalar o'rnatilgan)
├── downloads/             # Vaqtinchalik fayllar papkasi
├── handlers/
│   ├── __init__.py        # Routerlarni birlashtiruvchi
│   ├── start.py           # /start, /help menyulari
│   ├── media.py           # Video & MP3 yuklash mexanizmi
│   └── shazam.py          # Shazam reytingi & ovoz orqali musiqa aniqlash
├── config.py              # Sozlamalar va FFmpeg integratsiyasi
├── downloader.py          # yt-dlp media yuklovchi moduli
├── shazam_service.py      # Shazam API xizmati
├── keyboards.py           # Foydalanuvchi tugmalari (menyu)
├── main.py                # Asosiy ishga tushiruvchi fayl
├── requirements.txt       # Kutubxonalar ro'yxati
└── .env                   # Bot tokeni saqlanadigan fayl
```
