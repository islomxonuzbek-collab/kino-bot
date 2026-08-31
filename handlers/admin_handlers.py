import asyncio

from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import database as db

router = Router()


async def _is_admin(event) -> bool:
    # Bazadan tekshiriladi (statik ADMIN_IDS ham init_db orqali shu jadvalga
    # qo'shib qo'yilgan), shu sababli "Admin qo'shish" orqali qo'shilgan yangi
    # admin ham qayta ishga tushirmasdan darhol to'liq panelga ega bo'ladi.
    return db.is_admin(event.from_user.id)


router.message.filter(_is_admin)
router.callback_query.filter(_is_admin)


class AddContent(StatesGroup):
    choosing_type = State()
    waiting_film_code = State()
    waiting_film_video = State()
    waiting_serial_code = State()
    waiting_serial_part = State()


class UserSearch(StatesGroup):
    waiting_user_id = State()


class DeleteMovie(StatesGroup):
    waiting_code = State()


class AddAdmin(StatesGroup):
    waiting_id = State()


class Broadcast(StatesGroup):
    waiting_content = State()


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Foydalanuvchilarni nazorat qilish", callback_data="admin_users")],
            [InlineKeyboardButton(text="🎬 Kino joylash", callback_data="admin_add_content")],
            [InlineKeyboardButton(text="🗑 Kinoni o'chirish", callback_data="admin_delete_movie")],
            [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="admin_add_admin")],
            [InlineKeyboardButton(text="📋 Adminlar ro'yxati", callback_data="admin_list")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📨 Xabar yuborish", callback_data="admin_broadcast")],
        ]
    )


def user_block_keyboard(user_id: int, blocked: bool) -> InlineKeyboardMarkup:
    if blocked:
        text, cb = "✅ Blokdan chiqarish", f"admin_unblock:{user_id}"
    else:
        text, cb = "🚫 Botdan bloklash", f"admin_block:{user_id}"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=cb)]])


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
    blocked = bool(row["is_blocked"])
    status = "🚫 Bloklangan" if blocked else "✅ Faol"
    await message.answer(
        f"🆔 <code>{row['user_id']}</code>\n"
        f"👤 {uname}\n"
        f"🎬 Ko'rilgan kinolar soni: <b>{row['watched_count']}</b>\n"
        f"📌 Holati: <b>{status}</b>",
        reply_markup=user_block_keyboard(row["user_id"], blocked),
    )


# ---------- Foydalanuvchini bloklash / blokdan chiqarish ----------

@router.callback_query(F.data.startswith("admin_block:"))
async def admin_block_user(callback: CallbackQuery) -> None:
    target_id = int(callback.data.split(":", 1)[1])
    db.block_user(target_id)
    await callback.answer("🚫 Foydalanuvchi bloklandi.", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=user_block_keyboard(target_id, blocked=True))
    except Exception:
        pass


@router.callback_query(F.data.startswith("admin_unblock:"))
async def admin_unblock_user(callback: CallbackQuery) -> None:
    target_id = int(callback.data.split(":", 1)[1])
    db.unblock_user(target_id)
    await callback.answer("✅ Foydalanuvchi blokdan chiqarildi.", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=user_block_keyboard(target_id, blocked=False))
    except Exception:
        pass


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


# ---------- Kinoni o'chirish ----------

@router.callback_query(F.data == "admin_delete_movie")
async def admin_delete_movie_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await state.set_state(DeleteMovie.waiting_code)
    await callback.message.answer(
        "🗑 O'chirmoqchi bo'lgan kino/serial kodini kiriting:",
        reply_markup=cancel_keyboard(),
    )


@router.message(StateFilter(DeleteMovie.waiting_code))
async def admin_delete_movie_code(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip()
    await state.clear()

    if not code:
        await message.answer("❌ Kod bo'sh bo'lishi mumkin emas.")
        return

    movie = db.get_movie(code)
    if movie is None:
        await message.answer(f"😕 <code>{code}</code> kodli kino topilmadi.")
        return

    type_label = "Film" if movie["type"] == "film" else "Serial"
    views = movie["views"]
    db.delete_movie(code)
    await message.answer(
        f"✅ <code>{code}</code> kodli {type_label.lower()} butunlay o'chirildi.\n"
        f"👁 O'chirilgunga qadar ko'rishlar soni: {views}"
    )


# ---------- Admin qo'shish ----------

@router.callback_query(F.data == "admin_add_admin")
async def admin_add_admin_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await state.set_state(AddAdmin.waiting_id)
    await callback.message.answer(
        "➕ Yangi admin qilmoqchi bo'lgan foydalanuvchining Telegram ID sini yuboring:\n"
        "(ID ni bilish uchun foydalanuvchi @userinfobot ga /start yozishi mumkin)",
        reply_markup=cancel_keyboard(),
    )


@router.message(StateFilter(AddAdmin.waiting_id))
async def admin_add_admin_id(message: Message, state: FSMContext, bot: Bot) -> None:
    text = (message.text or "").strip()
    await state.clear()

    if not text.lstrip("-").isdigit():
        await message.answer("❌ Iltimos, faqat raqamli Telegram ID yuboring.")
        return

    new_id = int(text)
    if db.is_admin(new_id):
        await message.answer("⚠️ Bu foydalanuvchi allaqachon admin.")
        return

    db.add_admin(new_id)
    await message.answer(
        f"✅ <code>{new_id}</code> endi admin!\n"
        "U botga /start yozganda (yoki qayta yozganda) to'liq admin panelga ega bo'ladi."
    )

    try:
        await bot.send_message(
            new_id,
            "🎉 Tabriklaymiz! Sizga ushbu botda <b>admin huquqi</b> berildi.\n"
            "Admin panelga kirish uchun botga /start deb yozing.",
        )
    except Exception:
        # Yangi admin botni bloklagan yoki hali botga /start bosmagan bo'lishi mumkin
        pass


@router.callback_query(F.data == "admin_list")
async def admin_list_view(callback: CallbackQuery) -> None:
    await callback.answer()
    admins = db.list_admins()

    lines = ["📋 <b>Adminlar ro'yxati</b>\n"]
    if admins:
        for i, admin_id in enumerate(admins, start=1):
            lines.append(f"{i}. <code>{admin_id}</code>")
    else:
        lines.append("Hozircha adminlar yo'q.")

    await callback.message.answer("\n".join(lines))


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


# ---------- Xabar yuborish (hammaga broadcast) ----------

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await state.set_state(Broadcast.waiting_content)
    await callback.message.answer(
        "📨 Barcha foydalanuvchilarga yuboriladigan xabarni yuboring.\n"
        "Matn, rasm, video, ovozli xabar — istalgan turdagi xabarni yuborishingiz mumkin.\n"
        "Xabar aynan qanday yuborsangiz, foydalanuvchilarga ham shundayligicha yetib boradi.",
        reply_markup=cancel_keyboard(),
    )


@router.message(StateFilter(Broadcast.waiting_content))
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    user_ids = db.get_all_user_ids()
    await message.answer(f"⏳ Yuborilmoqda... Jami: {len(user_ids)} ta foydalanuvchiga.")

    success = 0
    failed = 0
    for user_id in user_ids:
        try:
            await message.copy_to(chat_id=user_id)
            success += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # Telegram flood-limitiga tushib qolmaslik uchun

    await message.answer(
        "✅ <b>Xabar yuborish yakunlandi!</b>\n\n"
        f"✔️ Yetib bordi: <b>{success}</b>\n"
        f"❌ Yetib bormadi (bloklagan/o'chirilgan): <b>{failed}</b>"
    )
