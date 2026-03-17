# ============================================================
#  handlers/common.py — /start, главное меню, прайс, портфолио
# ============================================================

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Записаться",     callback_data="book_start"))
    builder.row(InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel_my"))
    builder.row(
        InlineKeyboardButton(text="💅 Прайсы",      callback_data="show_prices"),
        InlineKeyboardButton(text="🖼 Портфолио",   callback_data="show_portfolio"),
    )
    return builder.as_markup()


WELCOME_TEXT = (
    "👋 <b>Привет!</b> Я помогу вам записаться на маникюр.\n\n"
    "Выберите действие:"
)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(WELCOME_TEXT, parse_mode="HTML", reply_markup=main_menu_kb())


@router.callback_query(F.data == "back_to_main")
async def back_to_main(call: CallbackQuery):
    await call.message.edit_text(WELCOME_TEXT, parse_mode="HTML", reply_markup=main_menu_kb())


# ── Прайсы ──────────────────────────────────────────────────

PRICES_TEXT = (
    "💅 <b>Прайс-лист</b>\n\n"
    "• Френч — <b>1 000 ₽</b>\n"
    "• Квадрат — <b>500 ₽</b>\n"
)


@router.callback_query(F.data == "show_prices")
async def show_prices(call: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    await call.message.edit_text(PRICES_TEXT, parse_mode="HTML",
                                 reply_markup=kb.as_markup())


# ── Портфолио ────────────────────────────────────────────────

@router.callback_query(F.data == "show_portfolio")
async def show_portfolio(call: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="🌸 Смотреть портфолио",
        url="https://t.me/gggyyyiiiooo777aaabot"
    ))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    await call.message.edit_text(
        "🖼 <b>Портфолио мастера</b>\n\nПосмотрите мои работы на Pinterest:",
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )
