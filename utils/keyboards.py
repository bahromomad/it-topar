from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Foydalanuvchi qidirish", callback_data="search_user"),
            InlineKeyboardButton(text="👥 Guruh qidirish", callback_data="search_group"),
        ],
        [
            InlineKeyboardButton(text="👁 Kuzatish", callback_data="my_tracks"),
            InlineKeyboardButton(text="📊 Statistika", callback_data="statistics"),
        ],
        [
            InlineKeyboardButton(text="❓ Yordam", callback_data="help"),
        ]
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="main_menu")]
    ])


def user_detail_kb(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🕒 Ism tarixi", callback_data=f"names_{tg_id}"),
            InlineKeyboardButton(text="👥 Guruhlari", callback_data=f"ugroups_{tg_id}"),
        ],
        [
            InlineKeyboardButton(text="💬 Xabarlari", callback_data=f"umessages_{tg_id}"),
            InlineKeyboardButton(text="👁 Kuzatish", callback_data=f"track_{tg_id}"),
        ],
        [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="main_menu")]
    ])


def group_detail_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 A'zolar ro'yxati", callback_data=f"gmembers_{group_id}"),
            InlineKeyboardButton(text="📊 Statistika", callback_data=f"gstats_{group_id}"),
        ],
        [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="main_menu")]
    ])


def tracks_kb(tracks: list) -> InlineKeyboardMarkup:
    buttons = []
    for t in tracks:
        name = f"@{t.target_username}" if t.target_username else f"ID {t.target_id}"
        buttons.append([
            InlineKeyboardButton(text=f"👤 {name}", callback_data=f"trackinfo_{t.target_id}"),
            InlineKeyboardButton(text="❌ To'xtatish", callback_data=f"untrack_{t.id}"),
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
