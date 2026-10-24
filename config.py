import os
from pathlib import Path
from dotenv import load_dotenv

# .env faylini yuklash
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()

# Yuklab olinadigan fayllar uchun vaqtinchalik papka
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# FFmpeg manzilini aniqlash (imageio-ffmpeg orqali avtomatik topiladi)
try:
    import imageio_ffmpeg
    import pydub
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
    pydub.AudioSegment.converter = FFMPEG_EXE
    # PATH ga ham qo'shib qo'yamiz
    ffmpeg_dir = str(Path(FFMPEG_EXE).parent)
    if ffmpeg_dir not in os.environ["PATH"]:
        os.environ["PATH"] += os.path.pathsep + ffmpeg_dir
except Exception:
    FFMPEG_EXE = "ffmpeg"
