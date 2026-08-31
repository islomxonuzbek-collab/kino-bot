from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import database as db
from config import ADMIN_IDS

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


class AddContent(StatesGroup):
    choosing_type = State()
    waiting_film_code = State()
    waiting_film_video = State()
    waiting_serial_code = State()
    waiting_serial_part = State()


class UserSearch(StatesGroup):
    waiting_user_id = State()


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Foydalanuvchilarni nazorat qilish", callback_data="admin_users")],
            [InlineKeyboardButton(text="🎬 Kino joylash", callback_data="admin_add_content")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        ]
    )


def add_content_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 Film joylash", callback_data="add_film"),
                InlineKeyboardButton(text="📺 Serial joylash", callback_data="add_serial"),
            ],
        ]
    )


def users_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 ID orqali qidirish", callback_data="admin_search_user")],
        ]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")],
        ]
    )


# ---------- Admin panelni ochish (faqat admin ko'radi) ----------

@router.callback_query(F.data == "admin_panel")
async def open_admin_panel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer("⚙️ <b>Admin panel</b>\n\nKerakli bo'limni tanlang:", reply_markup=admin_panel_keyboard())


# ---------- Foydalanuvchilarni nazorat qilish ----------

@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery) -> None:
    await callback.answer()
    total = db.count_users()
    top = db.top_users(limit=10)

    lines = [f"👥 <b>Jami foydalanuvchilar:</b> {total}\n", "🏆 <b>Eng faol 10 ta:</b>"]
    if top:
        for i, row in enumerate(top, start=1):
            uname = f"@{row['username']}" if row["username"] else row["full_name"] or "—"
            lines.append(f"{i}. <code>{row['user_id']}</code> ({uname}) — {row['watched_count']} ta kino")
    else:
        lines.append("Hozircha ma'lumot yo'q.")

    await callback.message.answer("\n".join(lines), reply_markup=users_menu_keyboard())


@router.callback_query(F.data == "admin_search_user")
async def admin_search_user_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(UserSearch.waiting_user_id)
    await callback.message.answer("🔎 Foydalanuvchining Telegram ID raqamini yuboring:")


@router.message(StateFilter(UserSearch.waiting_user_id))
async def admin_search_user_result(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().lstrip("-").isdigit():
        await message.answer("❌ Iltimos, faqat raqamli Telegram ID yuboring.")
        return

    user_id = int(message.text.strip())
    row = db.get_user(user_id)
    await state.clear()

    if row is None:
        await message.answer("😕 Bu ID bo'yicha foydalanuvchi topilmadi.")
        return

    uname = f"@{row['username']}" if row["username"] else row["full_name"] or "—"
    await message.answer(
        f"🆔 <code>{row['user_id']}</code>\n"
        f"👤 {uname}\n"
        f"🎬 Ko'rilgan kinolar soni: <b>{row['watched_count']}</b>"
    )


# ---------- Bekor qilish ----------

@router.callback_query(F.data == "admin_cancel", StateFilter("*"))
async def admin_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    current_state = await state.get_state()
    await state.clear()
    await callback.answer("❌ Bekor qilindi")

    if current_state is None:
        return

    await callback.message.answer(
        "❌ Amal bekor qilindi.\n\n⚙️ <b>Admin panel</b>\n\nKerakli bo'limni tanlang:",
        reply_markup=admin_panel_keyboard(),
    )


# ---------- Kino joylash ----------

@router.callback_query(F.data == "admin_add_content")
async def admin_add_content(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer("Nimani joylaysiz?", reply_markup=add_content_type_keyboard())


@router.callback_query(F.data == "add_film")
async def add_film_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AddContent.waiting_film_code)
    await callback.message.answer(
        "🎟️ Film uchun kod raqamini kiriting (masalan: 125):",
        reply_markup=cancel_keyboard(),
    )


@router.message(StateFilter(AddContent.waiting_film_code))
async def add_film_code(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip()
    if not code:
        await message.answer(
            "❌ Kod bo'sh bo'lishi mumkin emas. Qaytadan kiriting:",
            reply_markup=cancel_keyboard(),
        )
        return
    if db.code_exists(code):
        await message.answer("⚠️ Bu kod band. Boshqa kod kiriting yoki mavjud filmni qayta yuborsangiz, u yangilanadi.")

    await state.update_data(code=code)
    await state.set_state(AddContent.waiting_film_video)
    await message.answer(
        "🎬 Endi filmni video va izoh (caption) bilan birga yuboring:",
        reply_markup=cancel_keyboard(),
    )


@router.message(StateFilter(AddContent.waiting_film_video), F.video)
async def add_film_video(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    code = data["code"]

    db.add_film(code=code, caption=message.caption, file_id=message.video.file_id)
    await state.clear()
    await message.answer(f"✅ Film saqlandi! Kod: <code>{code}</code>")


@router.message(StateFilter(AddContent.waiting_film_video))
async def add_film_video_invalid(message: Message) -> None:
    await message.answer(
        "❌ Iltimos, video (film) yuboring.",
        reply_markup=cancel_keyboard(),
    )


@router.callback_query(F.data == "add_serial")
async def add_serial_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AddContent.waiting_serial_code)
    await callback.message.answer(
        "🎟️ Serial uchun kod raqamini kiriting (masalan: 200):",
        reply_markup=cancel_keyboard(),
    )


@router.message(StateFilter(AddContent.waiting_serial_code))
async def add_serial_code(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip()
    if not code:
        await message.answer(
            "❌ Kod bo'sh bo'lishi mumkin emas. Qaytadan kiriting:",
            reply_markup=cancel_keyboard(),
        )
        return

    db.create_serial(code)
    await state.update_data(code=code)
    await state.set_state(AddContent.waiting_serial_part)
    existing = db.get_series_parts(code)
    next_part = (existing[-1]["part_number"] + 1) if existing else 1
    await state.update_data(next_part=next_part)
    await message.answer(
        f"📺 <b>{next_part}-qism</b> videosini yuboring.\n"
        f"Barcha qismlarni joylab bo'lgach, /done deb yozing.",
        reply_markup=cancel_keyboard(),
    )


@router.message(StateFilter(AddContent.waiting_serial_part), Command("done"))
async def add_serial_done(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    code = data["code"]
    await state.clear()
    parts = db.get_series_parts(code)
    await message.answer(f"✅ Serial saqlandi! Kod: <code>{code}</code>\nJami qismlar: {len(parts)} ta.")


@router.message(StateFilter(AddContent.waiting_serial_part), F.video)
async def add_serial_part(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    code = data["code"]
    part_number = data["next_part"]

    db.add_series_part(code=code, part_number=part_number, file_id=message.video.file_id)
    await state.update_data(next_part=part_number + 1)
    await message.answer(
        f"✅ {part_number}-qism saqlandi.\n"
        f"Keyingi ({part_number + 1}-qism) videoni yuboring yoki /done deb yozing.",
        reply_markup=cancel_keyboard(),
    )


@router.message(StateFilter(AddContent.waiting_serial_part))
async def add_serial_part_invalid(message: Message) -> None:
    await message.answer(
        "❌ Iltimos, video yuboring yoki tugatish uchun /done deb yozing.",
        reply_markup=cancel_keyboard(),
    )


# ---------- Statistika ----------

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery) -> None:
    await callback.answer()
    counts = db.count_movies()
    total_users = db.count_users()
    total_views = db.total_views()

    text = (
        "📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{total_users}</b>\n"
        f"🎬 Filmlar soni: <b>{counts['film']}</b>\n"
        f"📺 Seriallar soni: <b>{counts['serial']}</b>\n"
        f"👁 Jami ko'rishlar/yuklab olishlar: <b>{total_views}</b>"
    )
    await callback.message.answer(text)
