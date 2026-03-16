# ============================================================
#  utils/scheduler.py — планировщик напоминаний
# ============================================================

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore

from database.queries import (
    get_upcoming_appointments_without_reminder,
    mark_reminder_sent,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(
    jobstores={"default": MemoryJobStore()},
    timezone="Europe/Moscow",  # поменяйте на нужный часовой пояс
)


async def _send_reminder(bot, user_id: int, time_str: str, appt_id: int) -> None:
    """Отправляет напоминание пользователю."""
    text = (
        f"⏰ <b>Напоминание!</b>\n\n"
        f"Напоминаем, что вы записаны на маникюр завтра в <b>{time_str}</b>.\n"
        f"Ждём вас! 💅"
    )
    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
        mark_reminder_sent(appt_id)
        logger.info(f"Напоминание отправлено user_id={user_id}, appt_id={appt_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки напоминания: {e}")


def schedule_reminder(bot, appt_id: int, user_id: int,
                      day: str, time: str) -> bool:
    """
    Планирует напоминание за 24 ч до записи.
    Возвращает True если задача добавлена, False — если < 24 ч.
    """
    time_clean = str(time).strip()
    day_clean = str(day).strip()[:10]
    # Если время без минут (например "10"), добавляем ":00"
    if ":" not in time_clean:
        time_clean = time_clean + ":00"
    # Обрезаем до HH:MM если есть секунды
    time_clean = time_clean[:5]
    appt_dt = datetime.strptime(f"{day_clean} {time_clean}", "%Y-%m-%d %H:%M")
    remind_dt = appt_dt - timedelta(hours=24)

    if remind_dt <= datetime.now():
        logger.info(f"Запись {appt_id}: до визита < 24 ч, напоминание не создаётся.")
        return False

    job_id = f"reminder_{appt_id}"
    scheduler.add_job(
        _send_reminder,
        trigger="date",
        run_date=remind_dt,
        args=[bot, user_id, time, appt_id],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info(f"Напоминание запланировано: job_id={job_id}, send_at={remind_dt}")
    return True


def cancel_reminder(appt_id: int) -> None:
    """Удаляет задачу напоминания при отмене записи."""
    job_id = f"reminder_{appt_id}"
    try:
        scheduler.remove_job(job_id)
        logger.info(f"Напоминание отменено: job_id={job_id}")
    except Exception:
        pass  # задача могла уже выполниться


def restore_reminders(bot) -> None:
    """
    Восстанавливает напоминания из БД после перезапуска бота.
    Вызывать после запуска scheduler.start().
    """
    appointments = get_upcoming_appointments_without_reminder()
    count = 0
    for appt in appointments:
        added = schedule_reminder(
            bot,
            appt["id"],
            appt["user_id"],
            str(appt["date"]).strip()[:10],
            str(appt["time"]).strip()[:5],
        )
        if added:
            count += 1
    logger.info(f"Восстановлено напоминаний: {count}")
