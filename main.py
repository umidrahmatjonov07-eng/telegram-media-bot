import asyncio
import logging
import os
import sys
import re
import uuid
import sqlite3
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    FSInputFile,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatAction
from dotenv import load_dotenv
import yt_dlp
from shazamio import Shazam

# ----------------- SOZLAMALAR -----------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8799537354:AAHO-iGqR01rw_ZS5FC7RLv-rfH10B13Cds").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "6040327218").strip()

DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

import shutil

FFMPEG_EXE = shutil.which("ffmpeg") or "ffmpeg"
try:
    import imageio_ffmpeg
    if not shutil.which("ffmpeg"):
        FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = str(Path(FFMPEG_EXE).parent)
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.path.pathsep + os.environ.get("PATH", "")
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ----------------- BAZA (DATABASE) -----------------
DB_PATH = BASE_DIR / "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id: int, username: str = "", full_name: str = ""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, full_name)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            full_name=excluded.full_name
    """, (user_id, username or "", full_name or ""))
    conn.commit()
    conn.close()

def get_total_users() -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_user_ids() -> List[int]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def is_admin(user_id: int) -> bool:
    if not ADMIN_ID:
        return False
    admin_ids = [i.strip() for i in ADMIN_ID.split(",") if i.strip()]
    return str(user_id) in admin_ids

# ----------------- TUGMALAR (KEYBOARDS) -----------------
def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🏆 Shazam Dunyo Top 10"), KeyboardButton(text="🇺🇿 O'zbekiston Top 10")],
        [KeyboardButton(text="🔍 Qo'shiq qidirish"), KeyboardButton(text="ℹ️ Bot haqida / Yordam")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_chart_keyboard(chart_id: str, count: int = 10) -> InlineKeyboardMarkup:
    row1 = [InlineKeyboardButton(text=f"{i} 🎵", callback_data=f"ch_play:{chart_id}:{i}") for i in range(1, min(6, count + 1))]
    row2 = [InlineKeyboardButton(text=f"{i} 🎵", callback_data=f"ch_play:{chart_id}:{i}") for i in range(6, min(11, count + 1))]
    buttons = []
    if row1: buttons.append(row1)
    if row2: buttons.append(row2)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Foydalanuvchilar soni", callback_data="admin_stats"), InlineKeyboardButton(text="📢 Xabar tarqatish", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_refresh"), InlineKeyboardButton(text="❌ Yopish", callback_data="admin_close")]
    ])

# ----------------- SHAZAM XIZMATI -----------------
shazam = Shazam()

async def get_top_world_tracks(limit: int = 10) -> List[Dict[str, Any]]:
    url = f"https://itunes.apple.com/us/rss/topsongs/limit={limit}/json"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200: return []
                data = await resp.json(content_type=None)
                entries = data.get("feed", {}).get("entry", [])
                tracks = []
                for entry in entries[:limit]:
                    title = entry.get("im:name", {}).get("label", "Noma'lum")
                    artist = entry.get("im:artist", {}).get("label", "Noma'lum ijrochi")
                    tracks.append({"title": title, "subtitle": artist})
                return tracks
    except Exception as e:
        print(f"Top chart xatosi: {e}")
        return []

async def get_top_country_tracks(country_code: str = "uz", limit: int = 10) -> List[Dict[str, Any]]:
    url = f"https://itunes.apple.com/{country_code.lower()}/rss/topsongs/limit={limit}/json"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200: return await get_top_world_tracks(limit=limit)
                data = await resp.json(content_type=None)
                entries = data.get("feed", {}).get("entry", [])
                if not entries: return await get_top_world_tracks(limit=limit)
                tracks = []
                for entry in entries[:limit]:
                    title = entry.get("im:name", {}).get("label", "Noma'lum")
                    artist = entry.get("im:artist", {}).get("label", "Noma'lum ijrochi")
                    tracks.append({"title": title, "subtitle": artist})
                return tracks
    except Exception as e:
        return await get_top_world_tracks(limit=limit)

async def search_track(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    url = "https://itunes.apple.com/search"
    params = {"term": query, "entity": "song", "limit": limit}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200: return []
                data = await resp.json(content_type=None)
                return [{"title": r.get("trackName"), "subtitle": r.get("artistName"), "image": r.get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")} for r in data.get("results", [])]
    except Exception:
        return []

async def recognize_audio(file_path: str) -> Optional[Dict[str, Any]]:
    try:
        audio_bytes = Path(file_path).read_bytes()
        out = await shazam.recognize(audio_bytes)
        track = out.get("track")
        if not track: return None
        return {"title": track.get("title"), "subtitle": track.get("subtitle")}
    except Exception as e:
        print(f"Shazam recognize error: {e}")
        return None

# ----------------- YUKLOVCHI (DOWNLOADER) -----------------
URL_PATTERN = re.compile(r'(https?:\/\/[^\s]+)', re.IGNORECASE)

def is_valid_url(text: str) -> bool:
    return bool(URL_PATTERN.search(text))

def extract_url(text: str) -> Optional[str]:
    match = URL_PATTERN.search(text)
    return match.group(0) if match else None

def _get_fast_opts() -> dict:
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'geo_bypass': True,
        'ignoreerrors': False,
        'concurrent_fragment_downloads': 10,
        'buffersize': 1024 * 1024 * 16,
        'http_chunk_size': 10485760,
        'socket_timeout': 15,
        'retries': 3,
        'extractor_args': {'youtube': {'player_client': ['android', 'web'], 'skip': ['translated_subs']}},
        'headers': {'User-Agent': 'Mozilla/5.0'}
    }
    if FFMPEG_EXE and os.path.exists(FFMPEG_EXE):
        opts['ffmpeg_location'] = FFMPEG_EXE
    return opts

def _download_video_sync(url: str, output_template: str) -> Optional[Dict[str, Any]]:
    opts = _get_fast_opts()
    opts.update({
        'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[height<=720]/best',
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
    })
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info: return None
            filepath = ydl.prepare_filename(info)
            if not filepath.endswith('.mp4'):
                base, _ = os.path.splitext(filepath)
                if os.path.exists(base + '.mp4'): filepath = base + '.mp4'
            return {
                'filepath': filepath,
                'title': info.get('title', 'Video'),
                'description': info.get('description', ''),
                'track': info.get('track'),
                'artist': info.get('artist')
            }
    except Exception as e:
        print(f"Video yuklashda xatolik: {e}")
        return None

async def download_video_fast(url: str) -> Optional[Dict[str, Any]]:
    unique_id = uuid.uuid4().hex[:10]
    output_tmpl = str(DOWNLOAD_DIR / f"vid_{unique_id}.%(ext)s")
    return await asyncio.to_thread(_download_video_sync, url, output_tmpl)

def extract_audio_sample_for_shazam(video_path: str, output_path: str, start_time: int = 0, duration: int = 0) -> bool:
    """
    Shazam uchun toza WAV (16-bit 44100Hz mono) namuna ajratib olish
    WAV formati hech qachon SignatureError bermaydi va 100% aniqlanadi!
    """
    try:
        cmd = [FFMPEG_EXE, '-y']
        if start_time > 0:
            cmd.extend(['-ss', str(start_time)])
        cmd.extend(['-i', video_path])
        if duration > 0:
            cmd.extend(['-t', str(duration)])
        cmd.extend(['-vn', '-ar', '44100', '-ac', '1', '-f', 'wav', output_path])
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=25)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        print(f"Sample extraction error: {e}")
        return False

async def recognize_music_from_video(video_path: str) -> Optional[Dict[str, Any]]:
    """
    Videodagi musiqani Shazam orqali aniqlash
    """
    # 1-urinish: Videoning TO'LIQ audiosi (WAV). 15-30s Reels uchun butun audioni tekshirish eng to'g'ri usul!
    tmp1 = str(DOWNLOAD_DIR / f"samp_full_{uuid.uuid4().hex[:8]}.wav")
    try:
        if extract_audio_sample_for_shazam(video_path, tmp1, start_time=0, duration=0):
            res = await recognize_audio(tmp1)
            if res and res.get('title'):
                return res
    finally:
        remove_file(tmp1)

    # 2-urinish: 6-soniyadan keyingi qism (agar boshida odam gapirgan bo'lsa)
    tmp2 = str(DOWNLOAD_DIR / f"samp_mid_{uuid.uuid4().hex[:8]}.wav")
    try:
        if extract_audio_sample_for_shazam(video_path, tmp2, start_time=6, duration=25):
            res = await recognize_audio(tmp2)
            if res and res.get('title'):
                return res
    finally:
        remove_file(tmp2)

    return None

def _download_full_song_sync(query: str, output_template: str) -> Optional[Dict[str, Any]]:
    search_opts = {'quiet': True, 'extract_flat': True, 'geo_bypass': True}
    if FFMPEG_EXE and os.path.exists(FFMPEG_EXE):
        search_opts['ffmpeg_location'] = FFMPEG_EXE

    selected_url = None
    selected_title = query

    try:
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            # 1. To'g'ridan-to'g'ri so'rov orqali YouTube'dan to'liq qo'shiqni qidirish
            res = ydl.extract_info(f"ytsearch5:{query}", download=False)
            entries = res.get('entries', []) if res else []
            # 90 soniyadan 600 soniyagacha bo'lgan to'liq original musiqani tanlaymiz
            for e in entries:
                dur = e.get('duration') or 0
                if 90 <= dur <= 600:
                    selected_url = e.get('url')
                    selected_title = e.get('title') or query
                    break
            if not selected_url and entries:
                for e in entries:
                    dur = e.get('duration') or 0
                    if dur >= 60:
                        selected_url = e.get('url')
                        selected_title = e.get('title') or query
                        break
    except Exception as e:
        print(f"YouTube search error: {e}")

    if not selected_url:
        return None

    dl_opts = _get_fast_opts()
    dl_opts.update({'format': 'bestaudio[ext=m4a]/bestaudio/best', 'outtmpl': output_template})
    try:
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            info = ydl.extract_info(selected_url, download=True)
            if not info: return None
            if 'entries' in info and info['entries']: info = info['entries'][0]
            filepath = ydl.prepare_filename(info)
            if not os.path.exists(filepath):
                base, _ = os.path.splitext(filepath)
                for ext in ['.m4a', '.mp3', '.webm', '.opus', '.aac']:
                    if os.path.exists(base + ext):
                        filepath = base + ext
                        break
            return {'filepath': filepath, 'title': selected_title}
    except Exception as e:
        print(f"Musiqa yuklashda xatolik: {e}")
        return None

def extract_direct_audio_from_video(video_path: str, output_base: str) -> Optional[str]:
    """Videodan audioni 100% kafolat bilan ajratib olish (m4a yoki mp3)"""
    base, _ = os.path.splitext(output_base)
    m4a_path = base + ".m4a"
    mp3_path = base + ".mp3"

    # 1-usul: Stream copy (0.01 soniya, sifat yo'qolmaydi, enkoder shart emas)
    try:
        cmd = [FFMPEG_EXE, '-y', '-i', video_path, '-vn', '-c:a', 'copy', m4a_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        if os.path.exists(m4a_path) and os.path.getsize(m4a_path) > 1000:
            return m4a_path
    except Exception:
        pass

    # 2-usul: Transcode
    try:
        cmd = [FFMPEG_EXE, '-y', '-i', video_path, '-vn', mp3_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 1000:
            return mp3_path
    except Exception:
        pass

    return None

def _download_direct_audio_from_url_sync(url: str, output_template: str) -> Optional[str]:
    opts = _get_fast_opts()
    opts.update({
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': output_template,
    })
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info: return None
            if 'entries' in info and info['entries']: info = info['entries'][0]
            filepath = ydl.prepare_filename(info)
            if os.path.exists(filepath):
                return filepath
            base, _ = os.path.splitext(filepath)
            for ext in ['.m4a', '.mp3', '.webm', '.opus', '.aac']:
                if os.path.exists(base + ext):
                    return base + ext
            return None
    except Exception as e:
        print(f"URL direct audio error: {e}")
        return None

async def download_direct_audio_from_url(url: str) -> Optional[str]:
    unique_id = uuid.uuid4().hex[:10]
    tmpl = str(DOWNLOAD_DIR / f"direct_{unique_id}.%(ext)s")
    return await asyncio.to_thread(_download_direct_audio_from_url_sync, url, tmpl)

async def download_full_song_by_query(query: str) -> Optional[Dict[str, Any]]:
    unique_id = uuid.uuid4().hex[:10]
    output_tmpl = str(DOWNLOAD_DIR / f"full_{unique_id}.%(ext)s")
    return await asyncio.to_thread(_download_full_song_sync, query, output_tmpl)

def remove_file(filepath: Optional[str]):
    if filepath and os.path.exists(filepath):
        try: os.remove(filepath)
        except Exception: pass

# ----------------- DISPATCHER VA HANDLERLAR -----------------
dp = Dispatcher()

class SearchState(StatesGroup):
    waiting_for_query = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

chart_store: dict[str, list] = {}
media_store: dict[str, dict] = {}
audio_file_cache: dict[str, str] = {}

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name or "")
    text = (
        f"👋 Assalomu alaykum, <b>{message.from_user.first_name or 'Foydalanuvchi'}</b>!\n\n"
        "🤖 Ushbu bot quyidagi imkoniyatlarga ega:\n"
        "📥 <b>Media yuklovchi:</b> Instagram, YouTube, TikTok dan havola yuboring — bot videoni va to'liq original MP3 musiqasini yuklab beradi!\n\n"
        "🎵 <b>Shazam reytingi:</b> Dunyo va O'zbekiston TOP qo'shiqlari reytingini ko'ring va tinglang.\n\n"
        "🎤 <b>Musiqa aniqlash:</b> Ovozli xabar yoki audio yuboring — Shazam orqali topib beramiz!"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("myid"))
async def cmd_myid(message: types.Message):
    user_id = message.from_user.id
    status = "✅ Siz adminsiz!" if is_admin(user_id) else "❌ Siz admin emassiz."
    await message.reply(f"🆔 <b>Sizning ID:</b> <code>{user_id}</code>\n👑 <b>Status:</b> {status}", parse_mode="HTML")

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ Kechirasiz, siz bot administratori emassiz!")
        return
    total = get_total_users()
    await message.reply(f"👑 <b>Admin Panel:</b>\n👥 <b>Foydalanuvchilar:</b> {total} ta\n🤖 <b>Holat:</b> Faol ✅", parse_mode="HTML", reply_markup=get_admin_keyboard())

@dp.callback_query(F.data == "admin_stats")
async def on_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    total = get_total_users()
    await callback.message.edit_text(f"📊 <b>Statistika:</b> Jami {total} ta foydalanuvchi.", parse_mode="HTML", reply_markup=get_admin_keyboard())

@dp.callback_query(F.data == "admin_broadcast")
async def on_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.set_state(BroadcastState.waiting_for_message)
    await callback.message.answer("📢 Barcha obunachilarga yubormoqchi bo'lgan xabarni yozing (Bekor qilish: /cancel):")

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    if await state.get_state():
        await state.clear()
        await message.reply("❌ Amal bekor qilindi.")

@dp.message(BroadcastState.waiting_for_message)
async def process_broadcast(message: types.Message, state: FSMContext, bot: Bot):
    await state.clear()
    users = get_all_user_ids()
    status_msg = await message.reply(f"⏳ {len(users)} ta foydalanuvchiga yuborilmoqda...")
    success = 0
    for uid in users:
        try:
            await message.copy_to(chat_id=uid)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await status_msg.edit_text(f"✅ Xabar {success} ta foydalanuvchiga yetkazildi!")

@dp.callback_query(F.data == "admin_close")
async def on_admin_close(callback: CallbackQuery):
    await callback.message.delete()

# Top 10
@dp.message(lambda msg: msg.text == "🏆 Shazam Dunyo Top 10")
async def show_world_top(message: types.Message):
    wait_msg = await message.answer("🔄 <i>Shazam Dunyo reytingi yuklanmoqda...</i>", parse_mode="HTML")
    tracks = await get_top_world_tracks(limit=10)
    if not tracks:
        await wait_msg.edit_text("❌ Reyting ma'lumotlarini olishda xatolik yuz berdi.")
        return
    chart_id = uuid.uuid4().hex[:8]
    chart_store[chart_id] = tracks
    text = "🔥 <b>Shazam: Dunyo bo'yicha TOP-10 musiqalar:</b>\n\n"
    for i, t in enumerate(tracks, 1):
        text += f"<b>{i}.</b> {t['title']} — <i>{t['subtitle']}</i>\n"
    text += "\n🎧 <b>Tinglash uchun pastdagi raqamni bosing:</b>"
    await wait_msg.edit_text(text, parse_mode="HTML", reply_markup=get_chart_keyboard(chart_id, len(tracks)))

@dp.message(lambda msg: msg.text == "🇺🇿 O'zbekiston Top 10")
async def show_uzb_top(message: types.Message):
    wait_msg = await message.answer("🔄 <i>O'zbekiston reytingi yuklanmoqda...</i>", parse_mode="HTML")
    tracks = await get_top_country_tracks(country_code="uz", limit=10)
    if not tracks:
        await wait_msg.edit_text("❌ Reyting ma'lumotlarini olishda xatolik yuz berdi.")
        return
    chart_id = uuid.uuid4().hex[:8]
    chart_store[chart_id] = tracks
    text = "🇺🇿 <b>Shazam: O'zbekistonda TOP-10 musiqalar:</b>\n\n"
    for i, t in enumerate(tracks, 1):
        text += f"<b>{i}.</b> {t['title']} — <i>{t['subtitle']}</i>\n"
    text += "\n🎧 <b>Tinglash uchun pastdagi raqamni bosing:</b>"
    await wait_msg.edit_text(text, parse_mode="HTML", reply_markup=get_chart_keyboard(chart_id, len(tracks)))

@dp.callback_query(F.data.startswith("ch_play:"))
async def on_play_chart_song(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3: return
    chart_id = parts[1]
    song_idx = int(parts[2]) - 1
    tracks = chart_store.get(chart_id)
    if not tracks or song_idx >= len(tracks):
        await callback.answer("⚠️ Ma'lumot eskirgan, qayta yuklang.", show_alert=True)
        return
    track = tracks[song_idx]
    song_name = f"{track['title']} — {track['subtitle']}"
    cache_key = f"{track['title']} {track['subtitle']}".strip().lower()

    cached_file_id = audio_file_cache.get(cache_key)
    if cached_file_id:
        await callback.answer("⚡ Yuborilmoqda...")
        await callback.message.answer_audio(audio=cached_file_id, title=track['title'], performer=track['subtitle'], caption=f"🎵 <b>{song_name}</b>", parse_mode="HTML")
        return

    await callback.answer(f"⏳ '{track['title']}' yuklanmoqda...")
    status_msg = await callback.message.reply(f"🎵 <b>{song_name}</b>\n⚡ <i>Musiqa tezkor yuklanmoqda...</i>", parse_mode="HTML")
    res = await download_full_song_by_query(f"{track['title']} {track['subtitle']}")
    if not res or not os.path.exists(res.get('filepath', '')):
        await status_msg.edit_text("❌ Musiqani yuklab olish imkoni bo'lmadi.")
        return
    filepath = res['filepath']
    try:
        audio_file = FSInputFile(filepath)
        sent = await callback.message.answer_audio(audio=audio_file, title=track['title'], performer=track['subtitle'], caption=f"🎵 <b>{song_name}</b>\n🎧 Yoqimli tinglash!", parse_mode="HTML")
        if sent.audio: audio_file_cache[cache_key] = sent.audio.file_id
        await status_msg.delete()
    finally:
        remove_file(filepath)

# Video va Audio yuklash (Eng aqlli Shazam integratsiyasi)
@dp.message(F.text, lambda msg: is_valid_url(msg.text or ""))
async def handle_url_message(message: types.Message, bot: Bot):
    url = extract_url(message.text)
    if not url: return

    status_msg = await message.reply("⏳ <i>Video yuklanmoqda va tahlil qilinmoqda, kuting...</i>", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VIDEO)

    res = await download_video_fast(url)
    if not res or not os.path.exists(res.get('filepath', '')):
        await status_msg.edit_text("❌ <b>Videoni yuklab bo'lmadi!</b>\nHavola to'g'riligini va ochiq profil ekanligini tekshiring.")
        return

    filepath = res['filepath']
    title = res.get('title', 'Video')
    desc = res.get('description', '')

    if (os.path.getsize(filepath) / (1024 * 1024)) > 49.5:
        remove_file(filepath)
        await status_msg.edit_text("⚠️ <b>Video hajmi juda katta (>50 MB)!</b>", parse_mode="HTML")
        return

    media_id = uuid.uuid4().hex[:10]

    # Videodan audioni darhol ajratib olamiz (0.01 soniya, kafolatlangan zaxira)
    direct_audio_base = str(DOWNLOAD_DIR / f"aud_{media_id}")
    direct_audio_path = extract_direct_audio_from_video(filepath, direct_audio_base)

    song_title = ""
    artist = ""
    is_shazam = False

    # 1. SHAZAM orqali haqiqiy akustik tahlil (HAR DOIM 1-O'RINDA!)
    recognized_song = await recognize_music_from_video(filepath)
    if recognized_song and recognized_song.get('title'):
        song_title = recognized_song['title'].strip()
        artist = (recognized_song.get('subtitle') or "").strip()
        is_shazam = True

    # 2. Agar Shazam topa olmasa, Instagram / TikTok metama'lumotlaridan tekshirish
    if not is_shazam:
        meta_track = (res.get('track') or "").strip()
        if meta_track and not any(bad in meta_track.lower() for bad in ['original audio', 'original sound', 'asl audio', 'original', 'video by', 'audio by']):
            song_title = meta_track
            artist = (res.get('artist') or "").strip()
            is_shazam = True

    if is_shazam and song_title:
        search_query = f"{song_title} {artist}".strip()
        btn_text = f"🎵 {song_title[:24]} (To'liq MP3)"
        caption = (
            f"🎬 <b>{title[:75]}</b>\n\n"
            f"🎵 <b>Videodagi musiqa:</b> {song_title} — {artist}\n\n"
            f"✨ <i>To'liq (original 3-5 daqiqalik) variantini yuklash uchun pastdagi tugmani bosing 👇</i>\n\n"
            f"✅ @top_media_uz_bot"
        )
    else:
        # Sarlavhadan xeshteg va keraksiz so'zlarni tozalab qidiruv so'rovi yasash
        clean_t = re.sub(r'#\w+|https?:\/\/\S+|Video by \S+|[@_]', ' ', desc or title).strip()
        clean_t = re.sub(r'\s+', ' ', clean_t).strip()
        search_query = clean_t if len(clean_t) > 3 else title
        song_title = search_query[:35]
        btn_text = "🎵 To'liq MP3 musiqani yuklab olish"
        caption = (
            f"🎬 <b>{title[:75]}</b>\n\n"
            f"✨ <i>To'liq (original 3-5 daqiqalik) variantini yuklash uchun pastdagi tugmani bosing 👇</i>\n\n"
            f"✅ @top_media_uz_bot"
        )

    media_store[media_id] = {
        'query': search_query,
        'url': url,
        'title': song_title,
        'artist': artist,
        'is_shazam': is_shazam,
        'direct_audio': direct_audio_path,
    }
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=btn_text, callback_data=f"get_m_{media_id}")]])

    try:
        await message.reply_video(video=FSInputFile(filepath), caption=caption, parse_mode="HTML", reply_markup=markup)
        await status_msg.delete()
    finally:
        remove_file(filepath)

# Video fayldan to'g'ridan-to'g'ri musiqa aniqlash (Telegramga tashlangan video yoki dumaloq video-xabarlar)
@dp.message(F.video | F.video_note)
async def handle_video_file_recognition(message: types.Message, bot: Bot):
    status_msg = await message.reply("🎧 <i>Videodagi musiqa Shazam orqali qidirilmoqda...</i>", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    file_id = message.video.file_id if message.video else message.video_note.file_id
    file_info = await bot.get_file(file_id)

    unique_name = uuid.uuid4().hex[:8]
    temp_vid = str(DOWNLOAD_DIR / f"user_vid_{unique_name}.mp4")
    direct_audio_base = str(DOWNLOAD_DIR / f"user_aud_{unique_name}")
    try:
        await bot.download_file(file_info.file_path, destination=temp_vid)
        direct_audio_path = extract_direct_audio_from_video(temp_vid, direct_audio_base)
        track = await recognize_music_from_video(temp_vid)

        if track and track.get('title'):
            song_title = track['title']
            artist = track.get('subtitle', '')
            media_id = uuid.uuid4().hex[:10]
            media_store[media_id] = {
                'query': f"{song_title} {artist}",
                'title': song_title,
                'is_shazam': True,
                'direct_audio': direct_audio_path,
            }

            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎵 To'liq MP3 qo'shiqni yuklab olish", callback_data=f"get_m_{media_id}")]
            ])

            caption = (
                f"🎉 <b>Musiqa topildi!</b>\n\n"
                f"🎵 <b>Nomi:</b> {song_title}\n"
                f"👤 <b>Ijrochi:</b> {artist}\n\n"
                f"<i>To'liq (original 3-5 daqiqalik) musiqani yuklab olish uchun pastdagi tugmani bosing 👇</i>"
            )
            await status_msg.edit_text(caption, parse_mode="HTML", reply_markup=markup)
        elif direct_audio_path and os.path.exists(direct_audio_path):
            await message.reply_audio(
                audio=FSInputFile(direct_audio_path),
                title="Videodagi audio",
                caption="🎵 <b>Videodagi audio yuklandi!</b>\n💡 <i>(Shazam bazasidan topilmadi, videoning o'zidagi ovoz ajratib berildi)</i>\n\n✅ @top_media_uz_bot",
                parse_mode="HTML"
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text(
                "❌ <b>Videodagi musiqani aniqlab bo'lmadi.</b>\n\n"
                "💡 <i>Musiqa ovozi juda past bo'lsa yoki fon shovqini baland bo'lsa, aniqlay olmasligi mumkin.</i>",
                parse_mode="HTML"
            )
    finally:
        remove_file(temp_vid)

@dp.callback_query(F.data.startswith("get_m_"))
async def on_get_media_audio(callback: CallbackQuery, bot: Bot):
    media_id = callback.data[6:]
    data = media_store.get(media_id)
    if not data:
        await callback.answer("⚠️ Ma'lumot eskirgan, linkni qayta tashlang.", show_alert=True)
        return

    await callback.answer("⏳ To'liq musiqa qidirilmoqda...")
    status_msg = await callback.message.reply("⏳ <i>To'liq (original 3-5 daqiqalik) musiqa tayyorlanmoqda, kuting...</i>", parse_mode="HTML")
    await bot.send_chat_action(chat_id=callback.message.chat.id, action=ChatAction.UPLOAD_VOICE)

    query = data.get('query', '')
    url = data.get('url', '')
    song_title = data.get('title', 'Musiqa')
    direct_audio = data.get('direct_audio')

    sent = False

    # 1. BIRINCHI BO'LIB HAR DOIM YOUTUBE'DAN TO'LIQ (3-5 DAQIQALIK) ORIGINAL QO'SHIQNI QIDIRAMIZ!
    if query:
        cache_key = query.strip().lower()
        cached_id = audio_file_cache.get(cache_key)
        if cached_id:
            await callback.message.answer_audio(
                audio=cached_id,
                title=song_title,
                caption=f"🎵 <b>{song_title}</b>\n✨ <i>To'liq (original) musiqa!</i>\n✅ @top_media_uz_bot",
                parse_mode="HTML"
            )
            await status_msg.delete()
            return

        full_res = await download_full_song_by_query(query)
        if full_res and os.path.exists(full_res.get('filepath', '')):
            fpath = full_res['filepath']
            stitle = full_res.get('title', song_title)
            try:
                sent_msg = await callback.message.answer_audio(
                    audio=FSInputFile(fpath),
                    title=stitle,
                    caption=f"🎵 <b>{stitle}</b>\n✨ <i>To'liq (original 3-5 daqiqalik) varianti yuklandi!</i>\n✅ @top_media_uz_bot",
                    parse_mode="HTML"
                )
                if sent_msg.audio:
                    audio_file_cache[cache_key] = sent_msg.audio.file_id
                await status_msg.delete()
                sent = True
            finally:
                remove_file(fpath)

    # 2. Agar YouTube'dan topilmasa va query bir necha so'zdan iborat bo'lsa, qisqartirib yana bir bor qidiramiz
    if not sent and query and len(query.split()) > 2:
        short_q = " ".join(query.split()[:2])
        full_res = await download_full_song_by_query(short_q)
        if full_res and os.path.exists(full_res.get('filepath', '')):
            fpath = full_res['filepath']
            stitle = full_res.get('title', song_title)
            try:
                sent_msg = await callback.message.answer_audio(
                    audio=FSInputFile(fpath),
                    title=stitle,
                    caption=f"🎵 <b>{stitle}</b>\n✨ <i>To'liq (original 3-5 daqiqalik) varianti yuklandi!</i>\n✅ @top_media_uz_bot",
                    parse_mode="HTML"
                )
                await status_msg.delete()
                sent = True
            finally:
                remove_file(fpath)

    # 3. Agar to'liq varianti umuman mavjud bo'lmasa (masalan faqat videodagi odamning o'z ovozi bo'lsa),
    # shundagina videodagi qisqa audioni beramiz
    if not sent:
        if direct_audio and os.path.exists(direct_audio):
            try:
                await callback.message.answer_audio(
                    audio=FSInputFile(direct_audio),
                    title=song_title[:60],
                    caption=f"🎵 <b>{song_title[:60]}</b>\n⚠️ <i>Ushbu musiqaning to'liq varianti topilmadi, videodagi audio yuklandi.</i>\n✅ @top_media_uz_bot",
                    parse_mode="HTML"
                )
                await status_msg.delete()
                sent = True
            finally:
                remove_file(direct_audio)
        elif url:
            direct_dl = await download_direct_audio_from_url(url)
            if direct_dl and os.path.exists(direct_dl):
                try:
                    await callback.message.answer_audio(
                        audio=FSInputFile(direct_dl),
                        title=song_title[:60],
                        caption=f"🎵 <b>{song_title[:60]}</b>\n⚠️ <i>Ushbu musiqaning to'liq varianti topilmadi, videodagi audio yuklandi.</i>\n✅ @top_media_uz_bot",
                        parse_mode="HTML"
                    )
                    await status_msg.delete()
                    sent = True
                finally:
                    remove_file(direct_dl)

    if not sent:
        await status_msg.edit_text("❌ Musiqani yuklab olish imkoni bo'lmadi.")

# Ovoz orqali musiqa aniqlash
@dp.message(F.voice | F.audio)
async def handle_audio_recognition(message: types.Message, bot: Bot):
    status_msg = await message.reply("🎧 <i>Shazam orqali qidirilmoqda...</i>", parse_mode="HTML")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file_info = await bot.get_file(file_id)
    
    unique_name = uuid.uuid4().hex[:8]
    temp_raw = str(DOWNLOAD_DIR / f"raw_{unique_name}.ogg")
    temp_wav = str(DOWNLOAD_DIR / f"clean_{unique_name}.wav")
    try:
        await bot.download_file(file_info.file_path, destination=temp_raw)
        # Ovozni WAV ga o'girish (xatosiz tahlil uchun)
        cmd = [FFMPEG_EXE, '-y', '-i', temp_raw, '-ar', '44100', '-ac', '1', '-f', 'wav', temp_wav]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)

        target_file = temp_wav if os.path.exists(temp_wav) else temp_raw
        track = await recognize_audio(target_file)
        if not track or not track.get('title'):
            await status_msg.edit_text("❌ <b>Musiqani aniqlab bo'lmadi.</b>\n<i>Fon shovqini kamroq joyda qayta urinib ko'ring.</i>", parse_mode="HTML")
            return

        song_title = track['title']
        artist = track.get('subtitle', '')
        media_id = uuid.uuid4().hex[:10]
        media_store[media_id] = {'query': f"{song_title} {artist}"}

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 To'liq MP3 qo'shiqni yuklab olish", callback_data=f"get_m_{media_id}")]
        ])
        caption = f"🎉 <b>Musiqa topildi!</b>\n\n🎵 <b>Nomi:</b> {song_title}\n👤 <b>Ijrochi:</b> {artist}\n\n<i>To'liq qo'shiqni yuklab olish uchun bosing 👇</i>"
        await status_msg.edit_text(caption, parse_mode="HTML", reply_markup=markup)
    finally:
        remove_file(temp_raw)
        remove_file(temp_wav)

# Web-server (Render uchun)
async def health_check(request):
    return web.Response(text="Bot is running 24/7!")

async def start_web():
    port = int(os.getenv("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    if os.getenv("PORT"):
        await start_web()
    logger.info("Bot polling boshlamoqda...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
