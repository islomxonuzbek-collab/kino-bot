"""Menyularni "bitta oyna" tarzida boshqarish uchun yordamchi funksiyalar.

Muammo: avval har bir tugma bosilganda bot yangi xabar yuborardi, natijada
chat pastga surilib ketaverardi. Endi tugma bosilganda eski xabarning matni/
tugmalari shunchaki yangilanadi (edit_text) — foydalanuvchi bitta "oyna"
ichida harakatlanadi.

Bu holat FSMContext ichidagi ma'lumotlarga bog'liq emas (state.clear() dan
ta'sirlanmasligi uchun), shuning uchun har bir chat uchun "oyna" xabarining
ID si shu modul ichida, xotirada saqlanadi.
"""
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

# chat_id -> hozirgi "oyna" xabarining message_id si
_panel_messages: dict[int, int] = {}


async def open_panel(
    callback: CallbackQuery,
    text: str,
    keyboard: Optional[InlineKeyboardMarkup] = None,
) -> None:
    """Tugma (callback) bosilganda chaqiriladi.

    Joriy xabar matnli bo'lsa — o'sha xabar tahrirlanadi (bitta oyna davom
    etadi). Agar tahrirlab bo'lmasa (masalan, u rasm/caption bo'lgani uchun,
    yoki matn aynan bir xil bo'lgani uchun Telegram xato qaytarsa), yangi
    xabar yuboriladi va shu yangi xabar endi "oyna" hisoblanadi.
    """
    message = callback.message
    chat_id = message.chat.id
    try:
        await message.edit_text(text, reply_markup=keyboard)
        _panel_messages[chat_id] = message.message_id
        return
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            _panel_messages[chat_id] = message.message_id
            return
    sent = await message.answer(text, reply_markup=keyboard)
    _panel_messages[chat_id] = sent.message_id


async def update_panel(
    bot: Bot,
    chat_id: int,
    text: str,
    keyboard: Optional[InlineKeyboardMarkup] = None,
) -> None:
    """Foydalanuvchi matn yuborgandan so'ng (masalan ID, kod, izoh) chaqiriladi.

    Yangi xabar yuborish o'rniga, shu chat uchun saqlangan "oyna" xabari
    tahrirlanadi — shunda chat pastga surilib ketmaydi.
    """
    message_id = _panel_messages.get(chat_id)
    if message_id is not None:
        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=keyboard)
            return
        except TelegramBadRequest:
            pass
    sent = await bot.send_message(chat_id, text, reply_markup=keyboard)
    _panel_messages[chat_id] = sent.message_id


def forget_panel(chat_id: int) -> None:
    """Oynani "unutish" — masalan foydalanuvchi butunlay boshqa joyga o'tganda."""
    _panel_messages.pop(chat_id, None)
