#!/usr/bin/env python3
"""
Скрипт для поиска мастеров маникюра в Telegram-группах.
Использует библиотеку Telethon для работы с Telegram API.
"""

import asyncio
import random
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError

# =============================================================================
# КОНФИГУРАЦИЯ — вставьте ваши данные здесь
# Получить api_id и api_hash можно на https://my.telegram.org
# =============================================================================
API_ID = 123456          # ← замените на ваш api_id (целое число)
API_HASH = "your_hash"  # ← замените на ваш api_hash (строка)
SESSION_NAME = "manicure_session"

# Список чатов для сканирования (от 3 до 5)
TARGET_CHATS = [
    "@chat1",
    "@chat2",
    "@chat3",
]

# Количество сообщений для анализа в каждом чате
MESSAGES_LIMIT = 5000

# Ключевые слова для фильтрации по био (поиск без учёта регистра)
BIO_KEYWORDS = [
    "маникюр", "ногти", "запись",
    "nails", "manicure", "lashes", "брови",
]

# Задержка между запросами профилей (сек) — защита от FloodWait
DELAY_MIN = 6.0
DELAY_MAX = 10.0

# Пауза между сканированием чатов (сек)
CHAT_PAUSE_MIN = 30
CHAT_PAUSE_MAX = 60

# Файл для сохранения результатов
OUTPUT_FILE = "masters.txt"


def bio_contains_keywords(bio: str) -> bool:
    """Проверяет наличие хотя бы одного ключевого слова в тексте био."""
    bio_lower = bio.lower()
    return any(keyword in bio_lower for keyword in BIO_KEYWORDS)


async def get_active_users_from_chat(client: TelegramClient, chat: str) -> dict:
    """
    Сканирует последние MESSAGES_LIMIT сообщений в чате.
    Возвращает словарь {user_id: username} для всех пользователей с username.
    """
    active_users = {}
    print(f"\n[→] Сканируем чат: {chat}")

    try:
        async for message in client.iter_messages(chat, limit=MESSAGES_LIMIT):
            if not message.sender_id:
                continue

            sender = message.sender
            if sender is None or getattr(sender, "bot", False):
                continue

            username = getattr(sender, "username", None)
            if username and sender.id not in active_users:
                active_users[sender.id] = username

    except Exception as e:
        print(f"    [!] Ошибка при сканировании {chat}: {e}")

    print(f"    [✓] Найдено пользователей с username: {len(active_users)}")
    return active_users


async def fetch_user_bio(client: TelegramClient, user_id: int) -> str | None:
    """
    Запрашивает полный профиль пользователя и возвращает текст Bio.
    Обрабатывает ошибки приватности и FloodWait.
    """
    try:
        full_user = await client.get_entity(user_id)
        full_info = await client(
            __import__("telethon").tl.functions.users.GetFullUserRequest(full_user)
        )
        about = full_info.full_user.about
        return about if about else ""

    except FloodWaitError as e:
        wait_seconds = e.seconds + 5
        print(f"    [⚠] FloodWait: ждём {wait_seconds} секунд...")
        await asyncio.sleep(wait_seconds)
        return None

    except UserPrivacyRestrictedError:
        return None

    except Exception:
        return None


async def main():
    print("=" * 60)
    print("  Поиск мастеров маникюра в Telegram")
    print("=" * 60)

    masters: set[str] = set()  # set() автоматически исключает дубликаты

    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        # ── Шаг 1: Собираем пользователей из всех чатов ──
        all_users: dict[int, str] = {}

        for idx, chat in enumerate(TARGET_CHATS):
            chat_users = await get_active_users_from_chat(client, chat)
            all_users.update(chat_users)

            # Пауза между чатами (кроме последнего)
            if idx < len(TARGET_CHATS) - 1:
                pause = random.uniform(CHAT_PAUSE_MIN, CHAT_PAUSE_MAX)
                print(f"    [⏳] Пауза между чатами: {pause:.1f} сек...")
                await asyncio.sleep(pause)

        print(f"\n[→] Всего уникальных пользователей: {len(all_users)}")

        # ── Шаг 2: Проверяем Bio каждого пользователя ──
        print(f"[→] Начинаем проверку профилей (задержка {DELAY_MIN}–{DELAY_MAX} сек)...\n")

        for idx, (user_id, username) in enumerate(all_users.items(), 1):
            print(f"    [{idx}/{len(all_users)}] @{username} — запрашиваем Bio...")

            bio = await fetch_user_bio(client, user_id)

            if bio is not None and bio_contains_keywords(bio):
                masters.add(f"@{username}")
                print(f"        [★] МАСТЕР НАЙДЕН! Bio: '{bio[:60]}...'")
            else:
                print(f"        [–] Пропускаем (нет ключевых слов в Bio)")

            # Антифлуд-задержка между запросами профилей
            delay = random.uniform(DELAY_MIN, DELAY_MAX)
            await asyncio.sleep(delay)

    # ── Шаг 3: Сохраняем результаты ──
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for master in sorted(masters):
            f.write(master + "\n")

    print("\n" + "=" * 60)
    print(f"  Готово! Найдено мастеров: {len(masters)}")
    print(f"  Результаты сохранены в: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
