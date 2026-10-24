import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from shazamio import Shazam

shazam = Shazam()

async def get_top_world_tracks(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Shazam / Apple Music rasmiy Global TOP musiqalar reytingi
    """
    url = f"https://itunes.apple.com/us/rss/topsongs/limit={limit}/json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
                entries = data.get("feed", {}).get("entry", [])
                tracks = []
                for entry in entries[:limit]:
                    title = entry.get("im:name", {}).get("label", "Noma'lum")
                    artist = entry.get("im:artist", {}).get("label", "Noma'lum ijrochi")
                    
                    # Rasm (eng kattasi)
                    images = entry.get("im:image", [])
                    img_url = images[-1].get("label") if images else None
                    
                    # Havola
                    link = entry.get("link", [{}])
                    share_url = link[0].get("attributes", {}).get("href", "") if isinstance(link, list) else ""

                    tracks.append({
                        "title": title,
                        "subtitle": artist,
                        "share_url": share_url,
                        "image": img_url,
                    })
                return tracks
    except Exception as e:
        print(f"Top world chart olishda xatolik: {e}")
        return []

async def get_top_country_tracks(country_code: str = "uz", limit: int = 10) -> List[Dict[str, Any]]:
    """
    Shazam / Apple Music rasmiy O'zbekiston yoki boshqa davlat TOP reytingi
    """
    cc = country_code.lower()
    url = f"https://itunes.apple.com/{cc}/rss/topsongs/limit={limit}/json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    # Agar UZ da bo'lmasa, global chartga o'tamiz
                    return await get_top_world_tracks(limit=limit)
                data = await resp.json(content_type=None)
                entries = data.get("feed", {}).get("entry", [])
                if not entries:
                    return await get_top_world_tracks(limit=limit)

                tracks = []
                for entry in entries[:limit]:
                    title = entry.get("im:name", {}).get("label", "Noma'lum")
                    artist = entry.get("im:artist", {}).get("label", "Noma'lum ijrochi")
                    
                    images = entry.get("im:image", [])
                    img_url = images[-1].get("label") if images else None
                    
                    link = entry.get("link", [{}])
                    share_url = link[0].get("attributes", {}).get("href", "") if isinstance(link, list) else ""

                    tracks.append({
                        "title": title,
                        "subtitle": artist,
                        "share_url": share_url,
                        "image": img_url,
                    })
                return tracks
    except Exception as e:
        print(f"Top country chart xatosi: {e}")
        return await get_top_world_tracks(limit=limit)

async def search_track(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Musiqa qidirish (Apple/Shazam Search API)
    """
    url = "https://itunes.apple.com/search"
    params = {
        "term": query,
        "entity": "song",
        "limit": limit,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
                results = data.get("results", [])
                tracks = []
                for r in results:
                    # Katta rasm olish (100x100 -> 600x600)
                    img = r.get("artworkUrl100", "")
                    if img:
                        img = img.replace("100x100bb.jpg", "600x600bb.jpg")
                    tracks.append({
                        "title": r.get("trackName", "Noma'lum"),
                        "subtitle": r.get("artistName", "Noma'lum ijrochi"),
                        "share_url": r.get("trackViewUrl", ""),
                        "image": img,
                    })
                return tracks
    except Exception as e:
        print(f"Musiqa qidirishda xatolik: {e}")
        return []

async def recognize_audio(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Audio fayl orqali musiqani aniqlash (Shazam)
    """
    try:
        out = await shazam.recognize(file_path)
        track = out.get("track")
        if not track:
            return None
        return {
            "title": track.get("title", "Noma'lum"),
            "subtitle": track.get("subtitle", "Noma'lum ijrochi"),
            "genre": track.get("genres", {}).get("primary", ""),
            "share_url": track.get("share", {}).get("href", ""),
            "image": track.get("images", {}).get("coverart"),
        }
    except Exception as e:
        print(f"Audio aniqlash xatosi: {e}")
        return None
