# ============================================================
#  utils/calendar_kb.py — inline-календарь
# ============================================================

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import date, timedelta
from typing import List

MONTHS_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def build_calendar(available_dates: List[str],
                   year: int, month: int) -> InlineKeyboardMarkup:
    """
    Строит inline-клавиатуру с календарём.
    available_dates — список 'YYYY-MM-DD', которые можно нажать.
    """
    builder = InlineKeyboardBuilder()

    # Заголовок месяца
    builder.row(
        InlineKeyboardButton(
            text=f"◀", callback_data=f"cal_prev:{year}:{month}"
        ),
        InlineKeyboardButton(
            text=f"{MONTHS_RU[month]} {year}", callback_data="cal_ignore"
        ),
        InlineKeyboardButton(
            text=f"▶", callback_data=f"cal_next:{year}:{month}"
        ),
    )

    # Дни недели
    builder.row(*[
        InlineKeyboardButton(text=d, callback_data="cal_ignore")
        for d in DAYS_RU
    ])

    # Определяем первый день месяца
    first = date(year, month, 1)
    start_weekday = first.weekday()  # 0=Пн

    # Сдвиг в начало недели
    cells: list = [None] * start_weekday

    # Заполняем дни
    day = first
    while day.month == month:
        cells.append(day)
        day += timedelta(days=1)

    # Добираем до кратного 7
    while len(cells) % 7 != 0:
        cells.append(None)

    today = date.today()

    for i in range(0, len(cells), 7):
        week = cells[i:i + 7]
        row_buttons = []
        for d in week:
            if d is None:
                row_buttons.append(
                    InlineKeyboardButton(text=" ", callback_data="cal_ignore")
                )
            elif d < today:
                row_buttons.append(
                    InlineKeyboardButton(text=f"✗{d.day}", callback_data="cal_ignore")
                )
            elif d.isoformat() in available_dates:
                row_buttons.append(
                    InlineKeyboardButton(
                        text=str(d.day),
                        callback_data=f"cal_day:{d.isoformat()}"
                    )
                )
            else:
                row_buttons.append(
                    InlineKeyboardButton(text=f"·{d.day}", callback_data="cal_ignore")
                )
        builder.row(*row_buttons)

    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")
    )
    return builder.as_markup()
