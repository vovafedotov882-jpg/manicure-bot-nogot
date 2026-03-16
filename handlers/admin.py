# ============================================================
#  handlers/admin.py — административная панель
# ============================================================

import logging
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_ID
from database.queries import (
    add_work_day, close_day, open_day,
    get_all_work_days, get_free_slots, get_all_slots,
    add_time_slot, delete_time_slot,
    get_appointments_by_date, cancel_appointment,
    get_available_days,
)
from utils.calendar_kb import build_calendar
from utils.scheduler import cancel_reminder

from datetime import date

logger = logging.getLogger(__name__)
router = Router()


# ── Фильтр: только администратор ────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ── FSM для добавления слота ─────────────────────────────────

class AdminFSM(StatesGroup):
    add_day_input      = State()
    add_slot_day       = State()
    add_slot_time      = State()
    del_slot_day       = State()
    del_slot_time      = State()
    view_schedule_day  = State()
    view_cal_choose    = State()


# ── Главное меню админа ──────────────────────────────────────

def admin_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить рабочий день",   callback_data="adm_add_day"))
    builder.row(InlineKeyboardButton(text="⏰ Добавить слот",           callback_data="adm_add_slot"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить слот",            callback_data="adm_del_slot"))
    builder.row(InlineKeyboardButton(text="🔒 Закрыть день",            callback_data="adm_close_day"))
    builder.row(InlineKeyboardButton(text="🔓 Открыть день",            callback_data="adm_open_day"))
    builder.row(InlineKeyboardButton(text="📋 Расписание на дату",      callback_data="adm_view_schedule"))
    builder.row(InlineKeyboardButton(text="❌ Отменить запись клиента",  callback_data="adm_cancel_appt"))
    return builder.as_markup()


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    await message.answer(
        "🛠 <b>Панель администратора</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )


@router.callback_query(F.data == "adm_menu")
async def adm_menu_cb(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    await call.message.edit_text(
        "🛠 <b>Панель администратора</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )


# ── Добавить рабочий день ────────────────────────────────────

@router.callback_query(F.data == "adm_add_day")
async def adm_add_day(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(AdminFSM.add_day_input)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="adm_menu"))
    await call.message.edit_text(
        "Введите дату в формате <b>YYYY-MM-DD</b> (например: 2025-08-15):",
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )


@router.message(AdminFSM.add_day_input)
async def adm_add_day_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    day = message.text.strip()
    try:
        date.fromisoformat(day)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите YYYY-MM-DD:")
        return
    add_work_day(day)
    await state.clear()
    await message.answer(
        f"✅ Рабочий день <b>{day}</b> добавлен вместе со слотами по умолчанию.",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )


# ── Добавить слот ────────────────────────────────────────────

@router.callback_query(F.data == "adm_add_slot")
async def adm_add_slot(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(AdminFSM.add_slot_day)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="adm_menu"))
    await call.message.edit_text(
        "Введите дату для добавления слота (YYYY-MM-DD):",
        reply_markup=kb.as_markup(),
    )


@router.message(AdminFSM.add_slot_day)
async def adm_add_slot_day(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    day = message.text.strip()
    try:
        date.fromisoformat(day)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите YYYY-MM-DD:")
        return
    await state.update_data(slot_day=day)
    await state.set_state(AdminFSM.add_slot_time)
    await message.answer("Введите время в формате <b>HH:MM</b> (например: 14:30):", parse_mode="HTML")


@router.message(AdminFSM.add_slot_time)
async def adm_add_slot_time(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    time_str = message.text.strip()
    data = await state.get_data()
    add_time_slot(data["slot_day"], time_str)
    await state.clear()
    await message.answer(
        f"✅ Слот <b>{time_str}</b> добавлен для <b>{data['slot_day']}</b>.",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )


# ── Удалить слот ─────────────────────────────────────────────

@router.callback_query(F.data == "adm_del_slot")
async def adm_del_slot(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(AdminFSM.del_slot_day)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="adm_menu"))
    await call.message.edit_text(
        "Введите дату для удаления слота (YYYY-MM-DD):",
        reply_markup=kb.as_markup(),
    )


@router.message(AdminFSM.del_slot_day)
async def adm_del_slot_day(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    day = message.text.strip()
    slots = get_free_slots(day)
    if not slots:
        await message.answer("Нет свободных слотов на эту дату.")
        return
    await state.update_data(del_slot_day=day)
    await state.set_state(AdminFSM.del_slot_time)

    builder = InlineKeyboardBuilder()
    for t in slots:
        builder.button(text=f"🗑 {t}", callback_data=f"adm_do_del_slot:{day}:{t}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="adm_menu"))
    await message.answer(
        f"Выберите слот для удаления ({day}):",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("adm_do_del_slot:"))
async def adm_do_del_slot(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    parts = call.data.split(":")
    day, time_str = parts[1], ":".join(parts[2:])
    delete_time_slot(day, time_str)
    await state.clear()
    await call.message.edit_text(
        f"✅ Слот <b>{time_str}</b> на <b>{day}</b> удалён.",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )


# ── Закрыть день ─────────────────────────────────────────────

@router.callback_query(F.data == "adm_close_day")
async def adm_close_day(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    days = get_all_work_days()
    open_days = [d for d in days if not d["closed"]]
    if not open_days:
        await call.answer("Нет открытых рабочих дней.", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    for d in open_days:
        builder.button(
            text=f"🔒 {d['date']}",
            callback_data=f"adm_do_close:{d['date']}"
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="adm_menu"))
    await call.message.edit_text("Выберите день для закрытия:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("adm_do_close:"))
async def adm_do_close(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    day = call.data.split(":")[1]
    close_day(day)
    await call.message.edit_text(
        f"🔒 День <b>{day}</b> закрыт для записи.",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )


# ── Открыть день ─────────────────────────────────────────────

@router.callback_query(F.data == "adm_open_day")
async def adm_open_day_cb(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    days = get_all_work_days()
    closed_days = [d for d in days if d["closed"]]
    if not closed_days:
        await call.answer("Нет закрытых дней.", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    for d in closed_days:
        builder.button(
            text=f"🔓 {d['date']}",
            callback_data=f"adm_do_open:{d['date']}"
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="adm_menu"))
    await call.message.edit_text("Выберите день для открытия:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("adm_do_open:"))
async def adm_do_open(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    day = call.data.split(":")[1]
    open_day(day)
    await call.message.edit_text(
        f"🔓 День <b>{day}</b> открыт для записи.",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )


# ── Просмотр расписания ──────────────────────────────────────

@router.callback_query(F.data == "adm_view_schedule")
async def adm_view_schedule(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    today = date.today()
    available = get_available_days(60)
    await state.set_state(AdminFSM.view_cal_choose)
    await state.update_data(available_dates=available, cal_year=today.year, cal_month=today.month)
    cal = build_calendar(available, today.year, today.month)
    await call.message.edit_text("📅 Выберите дату для просмотра:", reply_markup=cal)


@router.callback_query(F.data.startswith("cal_prev:"), AdminFSM.view_cal_choose)
async def adm_cal_prev(call: CallbackQuery, state: FSMContext):
    _, y, m = call.data.split(":")
    y, m = int(y), int(m)
    m -= 1
    if m < 1: m, y = 12, y - 1
    data = await state.get_data()
    cal = build_calendar(data["available_dates"], y, m)
    await state.update_data(cal_year=y, cal_month=m)
    await call.message.edit_reply_markup(reply_markup=cal)


@router.callback_query(F.data.startswith("cal_next:"), AdminFSM.view_cal_choose)
async def adm_cal_next(call: CallbackQuery, state: FSMContext):
    _, y, m = call.data.split(":")
    y, m = int(y), int(m)
    m += 1
    if m > 12: m, y = 1, y + 1
    data = await state.get_data()
    cal = build_calendar(data["available_dates"], y, m)
    await state.update_data(cal_year=y, cal_month=m)
    await call.message.edit_reply_markup(reply_markup=cal)


@router.callback_query(F.data.startswith("cal_day:"), AdminFSM.view_cal_choose)
async def adm_view_day(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    day = call.data.split(":")[1]
    await state.clear()

    appts = get_appointments_by_date(day)
    slots = get_all_slots(day)

    lines = [f"📅 <b>Расписание на {day}</b>\n"]
    for slot in slots:
        status = "🔴 Занято" if slot["booked"] else "🟢 Свободно"
        lines.append(f"⏰ {slot['time']} — {status}")

    if appts:
        lines.append("\n👥 <b>Записи:</b>")
        for a in appts:
            lines.append(
                f"• {a['time']} — {a['name']} | {a['phone']} "
                f"[<code>{a['user_id']}</code>] (id:{a['id']})"
            )

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="adm_menu"))
    await call.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )


# ── Отменить запись клиента ──────────────────────────────────

@router.callback_query(F.data == "adm_cancel_appt")
async def adm_cancel_appt(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    today = date.today().isoformat()
    # Показываем записи на ближайшие даты
    from database.db import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM appointments WHERE date >= ? ORDER BY date, time LIMIT 20",
            (today,),
        ).fetchall()
    if not rows:
        await call.answer("Нет активных записей.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for r in rows:
        builder.button(
            text=f"{r['date']} {r['time']} — {r['name']}",
            callback_data=f"adm_do_cancel:{r['id']}",
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="adm_menu"))
    await call.message.edit_text(
        "Выберите запись для отмены:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("adm_do_cancel:"))
async def adm_do_cancel(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id): return
    appt_id = int(call.data.split(":")[1])
    appt = cancel_appointment(appt_id)
    if appt:
        cancel_reminder(appt_id)
        # Уведомление клиенту
        try:
            await bot.send_message(
                appt["user_id"],
                f"😔 Ваша запись на <b>{appt['date']}</b> в <b>{appt['time']}</b> "
                f"была отменена администратором. Приносим извинения.",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await call.message.edit_text(
        f"✅ Запись отменена. Слот освобождён.",
        reply_markup=admin_menu_kb(),
    )
