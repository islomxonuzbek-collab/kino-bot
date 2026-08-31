from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import database as db
from config import ADMIN_USERNAME, CHANNEL_USERNAME

router = Router()

WELCOME_PHOTO = "assets/welcome.jpg"


def _pe(emoji: str, emoji_id: str) -> str:
    """Premium custom emojini HTML tg-emoji tegi bilan qaytaradi."""
    return f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>'


WELCOME_TEXT = (
    f'{_pe("🎬", "5375464961822695044")} <b>ZANGORAFILM</b> ga xush kelibsiz! '
    f'{_pe("🍿", "5371081166013078244")}\n'
    f'Assalomu alaykum! {_pe("👋", "5859691201250201986")}\n\n'
    "Siz izlagan kino va seriallarni bizning bot orqali tez va oson "
    f'topishingiz mumkin. {_pe("🎞️", "5188311512791393083")}\n'
    f'{_pe("🔎", "5377599075237502153")} Kino kodini qidirish uchun pastdagi tugmalardan foydalaning.\n'
    f'{_pe("🎟️", "5463297803235113601")} Kino kodini kiriting:\n\n'
    "Masalan: <code>125</code>\n"
    f'{_pe("✨", "5343726841427405712")} Kino kodini yozing va kerakli filmingizni bir zumda toping!\n\n'
    f'{_pe("❤️", "5861735798956627072")} ZANGORAFILM — Sifatli kino, maroqli tomosha!'
)

JOIN_TEXT = (
    f'{_pe("👋", "5859691201250201986")} <b>Salom!</b>\n\n'
    "Botdan foydalanish uchun avval quyidagi kanalimizga a'zo bo'ling, "
    f'so\'ngra <b>{_pe("✅", "5864038172010222653")} Tekshirish</b> tugmasini bosing.'
)

CODE_NOT_FOUND_TEXT = (
    f'{_pe("😕", "5375533492320880898")} Bunday kodli kino yoki serial topilmadi.\n'
    "Kodni tekshirib, qaytadan yuboring."
)

BLOCKED_TEXT = (
    "🚫 Siz botdan foydalanish huquqidan mahrum qilingansiz.\n"
    "Savol yoki e'tiroz bo'lsa, administratsiyaga murojaat qiling."
)


def _channel_link() -> str:
    return f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"


def _admin_link() -> str:
    return f"https://t.me/{ADMIN_USERNAME.lstrip('@')}"


def subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga qo'shilish", url=_channel_link())],
            [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")],
        ]
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    # Admin panel tugmasi barcha foydalanuvchilarga ko'rinadi, lekin uni bosganda
    # faqat admin ma'lumotlarni ko'radi (pastdagi admin_panel_denied handleriga qarang).
    bottom_row = [
        InlineKeyboardButton(text="📢 Reklama", url=_admin_link()),
        InlineKeyboardButton(text="⚙️ Admin panel", callback_data="admin_panel"),
    ]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kino kodlari", url=_channel_link())],
            bottom_row,
        ]
    )


def after_movie_keyboard() -> InlineKeyboardMarkup:
    # Kino/qism yuborilgandan so'ng uning tagida chiqadigan tugma —
    # foydalanuvchini kanalga taklif qiladi.
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga a'zo bo'ling", url=_channel_link())],
        ]
    )


def series_parts_keyboard(code: str, parts: list) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=f"{row['part_number']}-qism", callback_data=f"part:{code}:{row['part_number']}"
        )
        for row in parts
    ]
    # Har qatorda 3 tadan tugma
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """Foydalanuvchi majburiy kanalga a'zo yoki yo'qligini tekshiradi."""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status not in ("left", "kicked")
    except TelegramBadRequest:
        # Bot kanalda admin bo'lmasa yoki foydalanuvchi topilmasa
        return False


def _user_block_keyboard(user_id: int, blocked: bool) -> InlineKeyboardMarkup:
    if blocked:
        text, cb = "✅ Blokdan chiqarish", f"admin_unblock:{user_id}"
    else:
        text, cb = "🚫 Botdan bloklash", f"admin_block:{user_id}"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=cb)]])


async def notify_admins_about_start(bot: Bot, user) -> None:
    """Bot start bosilganda barcha adminlarga foydalanuvchi haqida to'liq
    ma'lumot yuboradi, tagida bloklash tugmasi bilan."""
    username = f"@{user.username}" if user.username else "yo'q"
    text = (
        "🆕 <b>Foydalanuvchi botga kirdi</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Ism: {user.full_name}\n"
        f"📛 Username: {username}\n"
        f"🌐 Til: {user.language_code or 'nomaʼlum'}\n"
        f"🔗 Profil: <a href=\"tg://user?id={user.id}\">havola</a>"
    )
    keyboard = _user_block_keyboard(user.id, blocked=False)
    for admin_id in db.list_admins():
        if admin_id == user.id:
            continue
        try:
            await bot.send_message(admin_id, text, reply_markup=keyboard)
        except Exception:
            # Admin botni bloklagan yoki hali /start bosmagan bo'lishi mumkin
            pass


async def send_welcome(bot: Bot, chat_id: int, user_id: int) -> None:
    photo = FSInputFile(WELCOME_PHOTO)
    await bot.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=WELCOME_TEXT,
        reply_markup=main_menu_keyboard(),
    )


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    db.touch_user(user_id, message.from_user.username, message.from_user.full_name)

    if db.is_user_blocked(user_id):
        await message.answer(BLOCKED_TEXT)
        return

    await notify_admins_about_start(bot, message.from_user)

    if await is_subscribed(bot, user_id):
        await send_welcome(bot, message.chat.id, user_id)
    else:
        await message.answer(JOIN_TEXT, reply_markup=subscribe_keyboard())


@router.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery, bot: Bot) -> None:
    user_id = callback.from_user.id

    if db.is_user_blocked(user_id):
        await callback.answer(BLOCKED_TEXT, show_alert=True)
        return

    if await is_subscribed(bot, user_id):
        await callback.answer("✅ Rahmat, a'zo bo'lgansiz!")
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await send_welcome(bot, callback.message.chat.id, user_id)
    else:
        await callback.answer("❌ Siz hali kanalga a'zo bo'lmagansiz!", show_alert=True)


@router.callback_query(F.data == "admin_panel")
async def admin_panel_denied(callback: CallbackQuery) -> None:
    # Bu handlerga faqat admin bo'lmagan foydalanuvchilar yetib keladi,
    # chunki asosiy "admin_panel" handleri admin_handlers.py da bo'lib,
    # u faqat ADMIN_IDS uchun ishlaydi va birinchi bo'lib ro'yxatdan o'tgan.
    await callback.answer("🚫 Bu bo'lim faqat administratorlar uchun mo'ljallangan.", show_alert=True)


@router.callback_query(F.data.startswith("part:"))
async def send_series_part(callback: CallbackQuery, bot: Bot) -> None:
    if db.is_user_blocked(callback.from_user.id):
        await callback.answer(BLOCKED_TEXT, show_alert=True)
        return

    _, code, part_number = callback.data.split(":", 2)
    row = db.get_series_part(code, int(part_number))
    if row is None:
        await callback.answer("❌ Bu qism topilmadi.", show_alert=True)
        return

    await callback.answer()
    await bot.send_video(
        chat_id=callback.message.chat.id,
        video=row["file_id"],
        reply_markup=after_movie_keyboard(),
    )
    db.increment_views(code)
    db.increment_watched(callback.from_user.id)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_film_code(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    db.touch_user(user_id, message.from_user.username, message.from_user.full_name)

    if db.is_user_blocked(user_id):
        await message.answer(BLOCKED_TEXT)
        return

    if not await is_subscribed(bot, user_id):
        await message.answer(JOIN_TEXT, reply_markup=subscribe_keyboard())
        return

    code = message.text.strip()
    movie = db.get_movie(code)

    if movie is None:
        await message.answer(CODE_NOT_FOUND_TEXT)
        return

    if movie["type"] == "film":
        await bot.send_video(
            chat_id=message.chat.id,
            video=movie["file_id"],
            caption=movie["caption"] or None,
            reply_markup=after_movie_keyboard(),
        )
        db.increment_views(code)
        db.increment_watched(user_id)
    else:
        parts = db.get_series_parts(code)
        if not parts:
            await message.answer(CODE_NOT_FOUND_TEXT)
            return
        await message.answer(
            movie["caption"]
            or f'{_pe("📺", "5373330964372004748")} Serial — kod: <code>{code}</code>\nQismni tanlang:',
            reply_markup=series_parts_keyboard(code, parts),
        )
