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

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = "ffmpeg"

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
        out = await shazam.recognize(file_path)
        track = out.get("track")
        if not track: return None
        return {"title": track.get("title"), "subtitle": track.get("subtitle")}
    except Exception:
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
            return {'filepath': filepath, 'title': info.get('title', 'Video'), 'description': info.get('description', '')}
    except Exception as e:
        print(f"Video xatosi: {e}")
        return None

async def download_video_fast(url: str) -> Optional[Dict[str, Any]]:
    unique_id = uuid.uuid4().hex[:10]
    output_tmpl = str(DOWNLOAD_DIR / f"vid_{unique_id}.%(ext)s")
    return await asyncio.to_thread(_download_video_sync, url, output_tmpl)

def extract_audio_from_local_video(video_path: str, output_path: str) -> bool:
    try:
        cmd = [FFMPEG_EXE, '-y', '-i', video_path, '-vn', '-acodec', 'libmp3lame', '-q:a', '3', output_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=20)
        return os.path.exists(output_path)
    except Exception:
        return False

def _download_full_song_sync(query: str, output_template: str) -> Optional[Dict[str, Any]]:
    search_opts = {'quiet': True, 'extract_flat': True, 'geo_bypass': True}
    if FFMPEG_EXE and os.path.exists(FFMPEG_EXE):
        search_opts['ffmpeg_location'] = FFMPEG_EXE

    selected_url = None
    selected_title = query

    try:
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            res = ydl.extract_info(f"ytsearch5:{query} official audio", download=False)
            entries = res.get('entries', []) if res else []
            for e in entries:
                dur = e.get('duration') or 0
                if 120 <= dur <= 600:
                    selected_url = e.get('url')
                    selected_title = e.get('title') or query
                    break
            if not selected_url and entries:
                selected_url = entries[0].get('url')
                selected_title = entries[0].get('title') or query
    except Exception:
        pass

    if not selected_url:
        selected_url = f"ytsearch1:{query} audio"

    dl_opts = _get_fast_opts()
    dl_opts.update({'format': 'bestaudio[ext=m4a]/bestaudio/best', 'outtmpl': output_template})
    try:
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            info = ydl.extract_info(selected_url, download=True)
            if not info: return None
            if 'entries' in info and info['entries']: info = info['entries'][0]
            return {'filepath': ydl.prepare_filename(info), 'title': selected_title}
    except Exception:
        return None

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
song_store: dict[str, str] = {}
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

# Video va Audio yuklash
@dp.message(F.text, lambda msg: is_valid_url(msg.text or ""))
async def handle_url_message(message: types.Message, bot: Bot):
    url = extract_url(message.text)
    if not url: return

    status_msg = await message.reply("⏳ <i>Video tayyorlanmoqda, kuting...</i>", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VIDEO)

    res = await download_video_fast(url)
    if not res or not os.path.exists(res.get('filepath', '')):
        await status_msg.edit_text("❌ <b>Videoni yuklab bo'lmadi!</b>\nHavola ochiqligini tekshiring.")
        return

    filepath = res['filepath']
    title = res.get('title', 'Video')
    desc = res.get('description', '')

    if (os.path.getsize(filepath) / (1024 * 1024)) > 49.5:
        remove_file(filepath)
        await status_msg.edit_text("⚠️ <b>Video hajmi juda katta (>50 MB)!</b>", parse_mode="HTML")
        return

    media_id = uuid.uuid4().hex[:10]
    sample_audio = str(DOWNLOAD_DIR / f"samp_{media_id}.mp3")
    recognized_song = None
    if extract_audio_from_local_video(filepath, sample_audio):
        try: recognized_song = await recognize_audio(sample_audio)
        except Exception: pass
        finally: remove_file(sample_audio)

    if recognized_song and recognized_song.get('title'):
        search_query = f"{recognized_song['title']} {recognized_song.get('subtitle', '')}"
        btn_text = f"🎵 {recognized_song['title'][:24]} (To'liq MP3)"
    else:
        clean_t = re.sub(r'#\w+|https?:\/\/\S+|Video by \S+|[@_]', ' ', desc or title).strip()
        search_query = clean_t if len(clean_t) > 3 else title
        btn_text = "🎵 Musiqani to'liq (original) yuklash"

    media_store[media_id] = {'query': search_query}
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=btn_text, callback_data=f"get_m_{media_id}")]])

    try:
        await message.reply_video(video=FSInputFile(filepath), caption=f"🎬 <b>{title[:100]}</b>\n\n✅ <i>Yuklab beruvchi:</i> @top_media_uz_bot", parse_mode="HTML", reply_markup=markup)
        await status_msg.delete()
    finally:
        remove_file(filepath)

@dp.callback_query(F.data.startswith("get_m_"))
async def on_get_media_audio(callback: CallbackQuery, bot: Bot):
    media_id = callback.data[6:]
    data = media_store.get(media_id)
    if not data:
        await callback.answer("⚠️ Ma'lumot eskirgan, linkni qayta tashlang.", show_alert=True)
        return

    await callback.answer("⏳ Musiqa tayyorlanmoqda...")
    status_msg = await callback.message.reply("⏳ <i>To'liq musiqa tayyorlanmoqda, kuting...</i>", parse_mode="HTML")
    await bot.send_chat_action(chat_id=callback.message.chat.id, action=ChatAction.UPLOAD_VOICE)

    query = data.get('query', '')
    cache_key = query.strip().lower()

    cached_id = audio_file_cache.get(cache_key)
    if cached_id:
        await callback.message.answer_audio(audio=cached_id, title=query, caption=f"🎵 <b>{query}</b>\n✨ <i>To'liq musiqa!</i>", parse_mode="HTML")
        await status_msg.delete()
        return

    full_res = await download_full_song_by_query(query)
    if full_res and os.path.exists(full_res.get('filepath', '')):
        fpath = full_res['filepath']
        stitle = full_res.get('title', query)
        try:
            sent = await callback.message.answer_audio(audio=FSInputFile(fpath), title=stitle, caption=f"🎵 <b>{stitle}</b>\n✨ <i>Videodagi musiqa to'liq (original) varianti yuklandi!</i>\n✅ @top_media_uz_bot", parse_mode="HTML")
            if sent.audio: audio_file_cache[cache_key] = sent.audio.file_id
            await status_msg.delete()
        finally:
            remove_file(fpath)
    else:
        await status_msg.edit_text("❌ Musiqani yuklab olish imkoni bo'lmadi.")

# Ovoz orqali musiqa aniqlash
@dp.message(F.voice | F.audio)
async def handle_audio_recognition(message: types.Message, bot: Bot):
    status_msg = await message.reply("🎧 <i>Shazam orqali qidirilmoqda...</i>", parse_mode="HTML")
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file_info = await bot.get_file(file_id)
    temp_path = str(DOWNLOAD_DIR / f"shazam_{uuid.uuid4().hex[:8]}.ogg")
    try:
        await bot.download_file(file_info.file_path, destination=temp_path)
        track = await recognize_audio(temp_path)
        if not track or not track.get('title'):
            await status_msg.edit_text("❌ Musiqani aniqlab bo'lmadi.")
            return
        caption = f"🎉 <b>Musiqa topildi!</b>\n\n🎵 <b>Nomi:</b> {track['title']}\n👤 <b>Ijrochi:</b> {track['subtitle']}"
        await status_msg.edit_text(caption, parse_mode="HTML")
    finally:
        remove_file(temp_path)

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
