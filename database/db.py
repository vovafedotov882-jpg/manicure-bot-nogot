# ============================================================
#  database/db.py — инициализация и вспомогательные функции
# ============================================================

import sqlite3
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_conn() -> sqlite3.Connection:
    """Возвращает соединение с БД с включёнными foreign keys."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Создаёт таблицы, если они не существуют."""
    with get_conn() as conn:
        conn.executescript("""
        -- Рабочие дни
        CREATE TABLE IF NOT EXISTS work_days (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            date    TEXT UNIQUE NOT NULL,   -- YYYY-MM-DD
            closed  INTEGER DEFAULT 0       -- 1 = день полностью закрыт
        );

        -- Временные слоты
        CREATE TABLE IF NOT EXISTS time_slots (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            date    TEXT NOT NULL,          -- YYYY-MM-DD
            time    TEXT NOT NULL,          -- HH:MM
            booked  INTEGER DEFAULT 0,      -- 1 = занято
            UNIQUE(date, time)
        );

        -- Записи клиентов
        CREATE TABLE IF NOT EXISTS appointments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            username    TEXT,
            name        TEXT NOT NULL,
            phone       TEXT NOT NULL,
            date        TEXT NOT NULL,      -- YYYY-MM-DD
            time        TEXT NOT NULL,      -- HH:MM
            created_at  TEXT DEFAULT (datetime('now')),
            reminder_sent INTEGER DEFAULT 0
        );
        """)
    logger.info("База данных инициализирована.")
