# ============================================================
#  database/queries.py — все SQL-запросы
# ============================================================

from datetime import date, timedelta
from typing import List, Optional
from database.db import get_conn
from config import DEFAULT_TIME_SLOTS


# ────────────────────────────────────────────────────────────
#  Рабочие дни
# ────────────────────────────────────────────────────────────

def add_work_day(day: str) -> bool:
    """Добавить рабочий день (YYYY-MM-DD). Возвращает False при дубликате."""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO work_days (date) VALUES (?)", (day,)
            )
            # Автоматически добавляем слоты по умолчанию
            for t in DEFAULT_TIME_SLOTS:
                conn.execute(
                    "INSERT OR IGNORE INTO time_slots (date, time) VALUES (?, ?)",
                    (day, t),
                )
        return True
    except Exception:
        return False


def close_day(day: str) -> None:
    """Полностью закрыть день (недоступен для записи)."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE work_days SET closed = 1 WHERE date = ?", (day,)
        )


def open_day(day: str) -> None:
    """Открыть закрытый день."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE work_days SET closed = 0 WHERE date = ?", (day,)
        )


def get_available_days(limit_days: int = 30) -> List[str]:
    """Вернуть список дат с хотя бы одним свободным слотом."""
    today = date.today().isoformat()
    until = (date.today() + timedelta(days=limit_days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT DISTINCT ts.date
            FROM time_slots ts
            JOIN work_days wd ON wd.date = ts.date
            WHERE ts.booked = 0
              AND wd.closed = 0
              AND ts.date >= ?
              AND ts.date <= ?
            ORDER BY ts.date
        """, (today, until)).fetchall()
    return [r["date"] for r in rows]


def get_all_work_days() -> List[dict]:
    """Все рабочие дни для админа."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM work_days ORDER BY date"
        ).fetchall()
    return [dict(r) for r in rows]


# ────────────────────────────────────────────────────────────
#  Временные слоты
# ────────────────────────────────────────────────────────────

def add_time_slot(day: str, time: str) -> bool:
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO time_slots (date, time) VALUES (?, ?)",
                (day, time),
            )
        return True
    except Exception:
        return False


def delete_time_slot(day: str, time: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM time_slots WHERE date = ? AND time = ? AND booked = 0",
            (day, time),
        )


def get_free_slots(day: str) -> List[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT time FROM time_slots WHERE date = ? AND booked = 0 ORDER BY time",
            (day,),
        ).fetchall()
    return [r["time"] for r in rows]


def get_all_slots(day: str) -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM time_slots WHERE date = ? ORDER BY time",
            (day,),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_slot_booked(day: str, time: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE time_slots SET booked = 1 WHERE date = ? AND time = ?",
            (day, time),
        )


def mark_slot_free(day: str, time: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE time_slots SET booked = 0 WHERE date = ? AND time = ?",
            (day, time),
        )


# ────────────────────────────────────────────────────────────
#  Записи
# ────────────────────────────────────────────────────────────

def create_appointment(
    user_id: int, username: Optional[str],
    name: str, phone: str, day: str, time: str,
) -> int:
    """Создать запись и заблокировать слот. Возвращает ID записи."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO appointments
               (user_id, username, name, phone, date, time)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, name, phone, day, time),
        )
        appt_id = cur.lastrowid
        conn.execute(
            "UPDATE time_slots SET booked = 1 WHERE date = ? AND time = ?",
            (day, time),
        )
    return appt_id


def get_user_appointment(user_id: int) -> Optional[dict]:
    """Активная запись пользователя (только одна)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM appointments WHERE user_id = ? ORDER BY date, time LIMIT 1",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def cancel_appointment(appt_id: int) -> Optional[dict]:
    """Отменить запись и освободить слот."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM appointments WHERE id = ?", (appt_id,)
        ).fetchone()
        if not row:
            return None
        appt = dict(row)
        conn.execute("DELETE FROM appointments WHERE id = ?", (appt_id,))
        conn.execute(
            "UPDATE time_slots SET booked = 0 WHERE date = ? AND time = ?",
            (appt["date"], appt["time"]),
        )
    return appt


def get_appointments_by_date(day: str) -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM appointments WHERE date = ? ORDER BY time",
            (day,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_upcoming_appointments_without_reminder() -> List[dict]:
    """Все будущие записи, для которых напоминание ещё не отправлено."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM appointments
               WHERE reminder_sent = 0
                 AND datetime(date || ' ' || time) > datetime('now')""",
        ).fetchall()
    return [dict(r) for r in rows]


def mark_reminder_sent(appt_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE appointments SET reminder_sent = 1 WHERE id = ?",
            (appt_id,),
        )
