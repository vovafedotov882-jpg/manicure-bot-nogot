# ============================================================
#  handlers/booking.py — запись клиента (FSM)
# ============================================================

import logging
from datetime import date

from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_ID, SCHEDULE_CHANNEL_ID, CHANNEL_ID, CHANNEL_LINK
from database.queries import (
    get_available_days, get_free_slots,
    create_appointment, get_user_appointment,
    cancel_appointment,
)
from utils.calendar_kb import build_calendar
from utils.scheduler import schedule_reminder, cancel_reminder

logger = logging.getLogger(__name__)
router = Router()


# ── FSM состояния ────────────────────────────────────────────

class BookFSM(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    entering_name = State()
    entering_phone = State()
    confirming = State()


# ── Проверка подписки ────────────────────────────────────────

async def check_subscription(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in ("left", "kicked", "restricted")
    except Exception as e:
        logger.warning(f"Ошибка проверки подписки: {e}")
        return False


def subscription_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Подписаться", url=CHANNEL_LINK))
    builder.row(InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub"))
    return builder.as_markup()


# ── Старт записи ─────────────────────────────────────────────

@router.callback_query(F.data == "book_start")
async def book_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    # Проверка подписки
    if not await check_subscription(bot, call.from_user.id):
        await call.message.edit_text(
            "🔒 Для записи необходимо подписаться на наш канал:",
            reply_markup=subscription_kb(),
        )
        return

    # Проверка: уже есть запись?
    existing = get_user_appointment(call.from_user.id)
    if existing:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel_my"))
        kb.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main"))
        await call.message.edit_text(
            f"⚠️ У вас уже есть запись:\n\n"
            f"📅 <b>{existing['date']}</b> в <b>{existing['time']}</b>\n"
            f"Имя: {existing['name']}\n\n"
            f"Одновременно можно иметь только одну запись.",
            parse_mode="HTML",
            reply_markup=kb.as_markup(),
        )
        return

    today = date.today()
    available = get_available_days()
    if not available:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
        await call.message.edit_text(
            "😔 К сожалению, свободных дат нет. Попробуйте позже.",
            reply_markup=kb.as_markup(),
        )
        return

    await state.set_state(BookFSM.choosing_date)
    await state.update_data(
        available_dates=available,
        cal_year=today.year,
        cal_month=today.month,
    )
    cal = build_calendar(available, today.year, today.month)
    await call.message.edit_text(
        "📅 <b>Выберите удобную дату:</b>\n"
        "Доступные дни выделены числами.",
        parse_mode="HTML",
        reply_markup=cal,
    )


# ── Проверка подписки по кнопке ──────────────────────────────

@router.callback_query(F.data == "check_sub")
async def check_sub_cb(call: CallbackQuery, state: FSMContext, bot: Bot):
    if await check_subscription(bot, call.from_user.id):
        await call.answer("✅ Подписка подтверждена!", show_alert=True)
        # Перезапускаем запись
        await book_start(call, state, bot)
    else:
        await call.answer("❌ Вы ещё не подписались.", show_alert=True)


# ── Навигация по календарю ───────────────────────────────────

@router.callback_query(F.data.startswith("cal_prev:"), BookFSM.choosing_date)
async def cal_prev(call: CallbackQuery, state: FSMContext):
    _, y, m = call.data.split(":")
    y, m = int(y), int(m)
    m -= 1
    if m < 1:
        m, y = 12, y - 1
    data = await state.get_data()
    cal = build_calendar(data["available_dates"], y, m)
    await state.update_data(cal_year=y, cal_month=m)
    await call.message.edit_reply_markup(reply_markup=cal)


@router.callback_query(F.data.startswith("cal_next:"), BookFSM.choosing_date)
async def cal_next(call: CallbackQuery, state: FSMContext):
    _, y, m = call.data.split(":")
    y, m = int(y), int(m)
    m += 1
    if m > 12:
        m, y = 1, y + 1
    data = await state.get_data()
    cal = build_calendar(data["available_dates"], y, m)
    await state.update_data(cal_year=y, cal_month=m)
    await call.message.edit_reply_markup(reply_markup=cal)


@router.callback_query(F.data == "cal_ignore")
async def cal_ignore(call: CallbackQuery):
    await call.answer()


# ── Выбор даты ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("cal_day:"), BookFSM.choosing_date)
async def choose_date(call: CallbackQuery, state: FSMContext):
    day = call.data.split(":")[1]
    slots = get_free_slots(day)
    if not slots:
        await call.answer("Нет свободного времени на эту дату.", show_alert=True)
        return

    await state.update_data(chosen_date=day)
    await state.set_state(BookFSM.choosing_time)

    builder = InlineKeyboardBuilder()
    for t in slots:
        builder.button(text=f"🕐 {t}", callback_data=f"slot:{t}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="book_start"))

    await call.message.edit_text(
        f"📅 Дата: <b>{day}</b>\n\n⏰ Выберите время:",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


# ── Выбор времени ────────────────────────────────────────────

@router.callback_query(F.data.startswith("slot:"), BookFSM.choosing_time)
async def choose_time(call: CallbackQuery, state: FSMContext):
    time = call.data.split(":")[1]
    await state.update_data(chosen_time=time)
    await state.set_state(BookFSM.entering_name)
    await call.message.edit_text(
        f"✅ Время <b>{time}</b> выбрано!\n\n"
        "Введите ваше <b>имя</b>:",
        parse_mode="HTML",
    )


# ── Ввод имени ───────────────────────────────────────────────

@router.message(BookFSM.entering_name)
async def enter_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Имя слишком короткое, попробуйте ещё раз.")
        return
    await state.update_data(client_name=name)
    await state.set_state(BookFSM.entering_phone)
    await message.answer("📱 Введите ваш <b>номер телефона</b>:", parse_mode="HTML")


# ── Ввод телефона ────────────────────────────────────────────

@router.message(BookFSM.entering_phone)
async def enter_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if len(phone) < 7:
        await message.answer("⚠️ Некорректный номер, попробуйте ещё раз.")
        return
    await state.update_data(client_phone=phone)
    data = await state.get_data()

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_booking"),
        InlineKeyboardButton(text="❌ Отменить",    callback_data="back_to_main"),
    )
    await state.set_state(BookFSM.confirming)
    await message.answer(
        f"📋 <b>Проверьте данные:</b>\n\n"
        f"📅 Дата:    <b>{data['chosen_date']}</b>\n"
        f"⏰ Время:   <b>{data['chosen_time']}</b>\n"
        f"👤 Имя:     <b>{data['client_name']}</b>\n"
        f"📱 Телефон: <b>{data['client_phone']}</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


# ── Подтверждение ────────────────────────────────────────────

@router.callback_query(F.data == "confirm_booking", BookFSM.confirming)
async def confirm_booking(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()

    appt_id = create_appointment(
        user_id=call.from_user.id,
        username=call.from_user.username,
        name=data["client_name"],
        phone=data["client_phone"],
        day=data["chosen_date"],
        time=data["chosen_time"],
    )

    # Планируем напоминание
    schedule_reminder(
        bot, appt_id,
        call.from_user.id,
        data["chosen_date"],
        data["chosen_time"],
    )

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main"))

    await call.message.edit_text(
        f"🎉 <b>Вы успешно записаны!</b>\n\n"
        f"📅 {data['chosen_date']} в {data['chosen_time']}\n"
        f"💅 Ждём вас!",
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )

    # Уведомление администратору
    admin_text = (
        f"📬 <b>Новая запись!</b>\n\n"
        f"👤 {data['client_name']} (@{call.from_user.username or '—'})\n"
        f"📱 {data['client_phone']}\n"
        f"📅 {data['chosen_date']} в {data['chosen_time']}\n"
        f"🆔 user_id: <code>{call.from_user.id}</code>"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Не удалось уведомить админа: {e}")

    # Публикация в канал расписания
    channel_text = (
        f"🗓 <b>Новая запись</b>\n"
        f"📅 {data['chosen_date']} — {data['chosen_time']}\n"
        f"👤 {data['client_name']}"
    )
    try:
        await bot.send_message(SCHEDULE_CHANNEL_ID, channel_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Не удалось опубликовать в канал: {e}")


# ── Отмена записи клиентом ───────────────────────────────────

@router.callback_query(F.data == "cancel_my")
async def cancel_my_booking(call: CallbackQuery, bot: Bot):
    appt = get_user_appointment(call.from_user.id)
    if not appt:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main"))
        await call.message.edit_text(
            "ℹ️ У вас нет активной записи.",
            reply_markup=kb.as_markup(),
        )
        return

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Да, отменить",
            callback_data=f"do_cancel:{appt['id']}"
        ),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"),
    )
    await call.message.edit_text(
        f"⚠️ Отменить запись на <b>{appt['date']}</b> в <b>{appt['time']}</b>?",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("do_cancel:"))
async def do_cancel(call: CallbackQuery, bot: Bot):
    appt_id = int(call.data.split(":")[1])
    appt = cancel_appointment(appt_id)
    if appt:
        cancel_reminder(appt_id)
        # Уведомление администратору
        try:
            await bot.send_message(
                ADMIN_ID,
                f"❌ <b>Отмена записи</b>\n\n"
                f"📅 {appt['date']} — {appt['time']}\n"
                f"👤 {appt['name']} (user_id: <code>{appt['user_id']}</code>)",
                parse_mode="HTML",
            )
        except Exception:
            pass

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main"))
    await call.message.edit_text(
        "✅ Ваша запись отменена. Слот снова доступен.",
        reply_markup=kb.as_markup(),
    )
