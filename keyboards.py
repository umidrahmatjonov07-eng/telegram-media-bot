from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Asosiy menyu klaviaturasi
    """
    keyboard = [
        [
            KeyboardButton(text="🏆 Shazam Dunyo Top 10"),
            KeyboardButton(text="🇺🇿 O'zbekiston Top 10"),
        ],
        [
            KeyboardButton(text="🔍 Qo'shiq qidirish"),
            KeyboardButton(text="ℹ️ Bot haqida / Yordam"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_media_action_keyboard(media_id: str) -> InlineKeyboardMarkup:
    """
    Link yuborilganda Video yoki Audio tanlash tugmalari
    """
    buttons = [
        [
            InlineKeyboardButton(text="🎬 Videoni yuklash", callback_data=f"dl_vid:{media_id}"),
            InlineKeyboardButton(text="🎵 Musiqani (MP3) yuklash", callback_data=f"dl_aud:{media_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_dl"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_chart_keyboard(chart_id: str, count: int = 10) -> InlineKeyboardMarkup:
    """
    Top chart musiqalarini bitta bosishda eshitish/yuklash uchun raqamli tugmalar
    """
    row1 = [
        InlineKeyboardButton(text=f"{i} 🎵", callback_data=f"ch_play:{chart_id}:{i}")
        for i in range(1, min(6, count + 1))
    ]
    row2 = [
        InlineKeyboardButton(text=f"{i} 🎵", callback_data=f"ch_play:{chart_id}:{i}")
        for i in range(6, min(11, count + 1))
    ]
    buttons = []
    if row1:
        buttons.append(row1)
    if row2:
        buttons.append(row2)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_song_download_keyboard(song_id: str, share_url: str = "") -> InlineKeyboardMarkup:
    """
    Qidiruv natijasidagi qo'shiqni yuklab olish tugmasi
    """
    buttons = [
        [
            InlineKeyboardButton(text="📥 MP3 yuklab olish", callback_data=f"play_s:{song_id}")
        ]
    ]
    if share_url:
        buttons.append([
            InlineKeyboardButton(text="🌐 Shazam / Apple'da ko'rish", url=share_url)
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
