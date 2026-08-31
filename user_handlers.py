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

from config import ADMIN_IDS, CHANNEL_USERNAME

router = Router()

WELCOME_PHOTO = "assets/welcome.jpg"

WELCOME_TEXT = (
    "🎬 <b>Zangora Film</b> botiga xush kelibsiz!\n\n"
    "Bu yerda siz eng sara filmlarni <b>kod</b> orqali topib, "
    "bir zumda tomosha qilishingiz mumkin. ✨\n\n"
    "👇 Film kodini yuboring va zavqlaning!"
)

JOIN_TEXT = (
    "👋 <b>Salom!</b>\n\n"
    "Botdan foydalanish uchun avval quyidagi kanalimizga a'zo bo'ling, "
    "so'ngra <b>✅ Tekshirish</b> tugmasini bosing."
)


def _channel_link() -> str:
    return f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"


def subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga qo'shilish", url=_channel_link())],
            [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")],
        ]
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kino kodlari", url=_channel_link())],
            [InlineKeyboardButton(text="⚙️ Admin panel", callback_data="admin_panel")],
        ]
    )


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """Foydalanuvchi majburiy kanalga a'zo yoki yo'qligini tekshiradi."""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status not in ("left", "kicked")
    except TelegramBadRequest:
        # Bot kanalda admin bo'lmasa yoki foydalanuvchi topilmasa
        return False


async def send_welcome(bot: Bot, chat_id: int) -> None:
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
    if await is_subscribed(bot, user_id):
        await send_welcome(bot, message.chat.id)
    else:
        await message.answer(JOIN_TEXT, reply_markup=subscribe_keyboard())


@router.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery, bot: Bot) -> None:
    user_id = callback.from_user.id
    if await is_subscribed(bot, user_id):
        await callback.answer("✅ Rahmat, a'zo bo'lgansiz!")
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await send_welcome(bot, callback.message.chat.id)
    else:
        await callback.answer("❌ Siz hali kanalga a'zo bo'lmagansiz!", show_alert=True)


@router.callback_query(F.data == "admin_panel")
async def open_admin_panel(callback: CallbackQuery) -> None:
    if callback.from_user.id in ADMIN_IDS:
        await callback.answer()
        await callback.message.answer(
            "⚙️ <b>Admin panel</b>\n\nBu bo'lim keyingi bosqichda to'ldiriladi."
        )
    else:
        await callback.answer("🚫 Bu bo'lim faqat admin uchun.", show_alert=True)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_film_code(message: Message, bot: Bot) -> None:
    """Foydalanuvchi film kodi yuborganda ishlaydigan handler (keyingi bosqichda to'ldiriladi)."""
    user_id = message.from_user.id
    if not await is_subscribed(bot, user_id):
        await message.answer(JOIN_TEXT, reply_markup=subscribe_keyboard())
        return

    # TODO: bazadan kod bo'yicha film qidirish keyingi bosqichda qo'shiladi
    await message.answer(
        "🔎 Kod qabul qilindi, lekin filmlar bazasi hali ulanmagan.\n"
        "Bu funksiyani keyingi bosqichda birga qo'shamiz."
    )
