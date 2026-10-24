import asyncio
import os
import uuid
import re
import glob
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import yt_dlp
from config import DOWNLOAD_DIR, FFMPEG_EXE

URL_PATTERN = re.compile(
    r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|'
    r'www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|'
    r'https?:\/\/[a-zA-Z0-9]+\.[^\s]{2,})',
    re.IGNORECASE
)

def is_valid_url(text: str) -> bool:
    return bool(URL_PATTERN.search(text))

def extract_url(text: str) -> Optional[str]:
    match = URL_PATTERN.search(text)
    if match:
        return match.group(0)
    return None

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
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['translated_subs']
            }
        },
        'headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            )
        }
    }
    if FFMPEG_EXE and os.path.exists(FFMPEG_EXE):
        opts['ffmpeg_location'] = FFMPEG_EXE
    return opts

def _download_video_fast_sync(url: str, output_template: str) -> Optional[Dict[str, Any]]:
    opts = _get_fast_opts()
    opts.update({
        'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[height<=720]/best',
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
    })
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None
            
            filepath = ydl.prepare_filename(info)
            if not filepath.endswith('.mp4'):
                base, _ = os.path.splitext(filepath)
                if os.path.exists(base + '.mp4'):
                    filepath = base + '.mp4'

            return {
                'filepath': filepath,
                'title': info.get('title', 'Video'),
                'description': info.get('description', ''),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader') or info.get('channel') or 'Media',
            }
    except Exception as e:
        print(f"Video yuklashda xatolik: {e}")
        return None

async def download_video_fast(url: str) -> Optional[Dict[str, Any]]:
    unique_id = uuid.uuid4().hex[:10]
    output_tmpl = str(DOWNLOAD_DIR / f"vid_{unique_id}.%(ext)s")
    return await asyncio.to_thread(_download_video_fast_sync, url, output_tmpl)

def extract_audio_from_local_video(video_path: str, output_path: str, duration: Optional[int] = None) -> bool:
    """
    Mahalliy diskdagi videodan bir zumda to'liq yoki qisqa audio ajratib olish (ffmpeg)
    """
    try:
        cmd = [FFMPEG_EXE, '-y', '-i', video_path, '-vn']
        if duration:
            cmd.extend(['-ss', '0', '-t', str(duration)])
        cmd.extend(['-acodec', 'libmp3lame', '-q:a', '3', output_path])
        
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=20)
        return os.path.exists(output_path)
    except Exception as e:
        print(f"Mahalliy videodan audio ajratishda xato: {e}")
        return False

def _download_full_song_sync(query: str, output_template: str) -> Optional[Dict[str, Any]]:
    """
    Qo'shiq nomidan kamida 2-5 minutlik to'liq original musiqani topib yuklaydi
    """
    # 1-qadam: YouTube qidiruvidan to'liq original trekni topish
    search_opts = {
        'quiet': True,
        'extract_flat': True,
        'geo_bypass': True,
    }
    if FFMPEG_EXE and os.path.exists(FFMPEG_EXE):
        search_opts['ffmpeg_location'] = FFMPEG_EXE

    selected_url = None
    selected_title = query
    selected_dur = 0

    try:
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            res = ydl.extract_info(f"ytsearch5:{query} official audio", download=False)
            entries = res.get('entries', []) if res else []
            
            # Davomiyligi 120 soniyadan oshgan (to'liq original trek) ni tanlash
            for e in entries:
                dur = e.get('duration') or 0
                if 120 <= dur <= 600:
                    selected_url = e.get('url')
                    selected_title = e.get('title') or query
                    selected_dur = dur
                    break

            # Agar topilmasa, istalgan 60s dan katta audio
            if not selected_url and entries:
                for e in entries:
                    dur = e.get('duration') or 0
                    if dur >= 60:
                        selected_url = e.get('url')
                        selected_title = e.get('title') or query
                        selected_dur = dur
                        break

            if not selected_url and entries:
                selected_url = entries[0].get('url')
                selected_title = entries[0].get('title') or query
                selected_dur = entries[0].get('duration') or 0
    except Exception as e:
        print(f"To'liq qo'shiq qidiruvida xato: {e}")

    if not selected_url:
        selected_url = f"ytsearch1:{query} audio"

    # 2-qadam: Tanlangan to'liq audioni yuklab olish
    dl_opts = _get_fast_opts()
    dl_opts.update({
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': output_template,
    })
    try:
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            info = ydl.extract_info(selected_url, download=True)
            if not info:
                return None
            if 'entries' in info:
                entries = list(info['entries'])
                if entries and entries[0]:
                    info = entries[0]
            filepath = ydl.prepare_filename(info)
            return {
                'filepath': filepath,
                'title': selected_title,
                'duration': selected_dur or info.get('duration', 0),
            }
    except Exception as e:
        print(f"To'liq musiqani yuklashda xatolik: {e}")
        return None

async def download_full_song_by_query(query: str) -> Optional[Dict[str, Any]]:
    unique_id = uuid.uuid4().hex[:10]
    output_tmpl = str(DOWNLOAD_DIR / f"full_{unique_id}.%(ext)s")
    return await asyncio.to_thread(_download_full_song_sync, query, output_tmpl)

async def download_audio_fast(target: str) -> Optional[Dict[str, Any]]:
    clean_q = target.replace('ytsearch1:', '').replace('audio', '').strip()
    return await download_full_song_by_query(clean_q)

def remove_file(filepath: Optional[str]):
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception:
            pass
