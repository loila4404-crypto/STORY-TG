import asyncio
import json
import os
from datetime import datetime
from datetime import datetime, timedelta

from dotenv import load_dotenv
from PIL import Image, ImageOps
from telegram import Bot
from telethon import TelegramClient
from telethon.tl.functions.stories import SendStoryRequest
from telethon.tl.types import InputPrivacyValueAllowAll, InputMediaUploadedPhoto

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

ACCOUNTS_FILE = "accounts.json"
STORIES_QUEUE_FILE = "stories_queue.json"
PREPARED_DIR = "stories_prepared"

os.makedirs(PREPARED_DIR, exist_ok=True)

bot = Bot(token=BOT_TOKEN)


def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return {}

    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_stories():
    if not os.path.exists(STORIES_QUEUE_FILE):
        return []

    with open(STORIES_QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_stories(data):
    with open(STORIES_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def notify_owner(story, text):
    owner_id = story.get("owner_id")

    if not owner_id:
        return

    try:
        await bot.send_message(chat_id=owner_id, text=text)
    except Exception as e:
        print(f"Ошибка отправки уведомления владельцу: {e}")


def prepare_story_image(photo_path):
    img = Image.open(photo_path)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    target_w, target_h = 1080, 1920

    img_ratio = img.width / img.height
    target_ratio = target_w / target_h

    if img_ratio > target_ratio:
        new_h = target_h
        new_w = int(target_h * img_ratio)
    else:
        new_w = target_w
        new_h = int(target_w / img_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))

    base_name = os.path.basename(photo_path)
    prepared_path = os.path.join(PREPARED_DIR, f"prepared_{base_name}")

    img.save(prepared_path, "JPEG", quality=90, optimize=True)

    return prepared_path


async def publish_story(story, accounts):
    account_name = story["account_name"]

    if account_name not in accounts:
        print(f"Аккаунт {account_name} не найден")
        return False, "Аккаунт не найден"

    info = accounts[account_name]
    session_path = info["session"].replace(".session", "")

    client = TelegramClient(session_path, API_ID, API_HASH)

    try:
        await client.connect()

        if not await client.is_user_authorized():
            print(f"{account_name} не авторизован")
            await client.disconnect()
            return False, "Сессия не авторизована"

        photo_path = story["photo_path"]

        if not os.path.exists(photo_path):
            print(f"Фото не найдено: {photo_path}")
            await client.disconnect()
            return False, "Фото не найдено"

        caption = story.get("caption", "")

        print(f"Готовлю фото: {photo_path}")
        prepared_path = prepare_story_image(photo_path)

        print(f"Публикую сторис: {account_name}")

        file = await client.upload_file(prepared_path)
        media = InputMediaUploadedPhoto(file=file)

        await client(
            SendStoryRequest(
                peer="me",
                media=media,
                caption=caption,
                privacy_rules=[InputPrivacyValueAllowAll()],
                pinned=False,
                noforwards=False,
                period=86400,
            )
        )

        print(f"Сторис опубликована: {account_name}")

        await client.disconnect()

        return True, None

    except Exception as e:
        print(f"Ошибка публикации {account_name}: {e}")

        try:
            await client.disconnect()
        except Exception:
            pass

        return False, str(e)


async def main():
    print("Stories worker запущен...")

    while True:
        now_dt = datetime.now() + timedelta(hours=3)
        now_time = now_dt.strftime("%H:%M")

        accounts = load_accounts()
        stories = load_stories()

        updated = False

        print(f"Проверка очереди: {now_time}")

        for story in stories:
            if story.get("status") != "scheduled":
                continue

            publish_time = story.get("publish_time")

            if not publish_time:
                continue

            try:
                publish_dt = datetime.strptime(publish_time, "%H:%M").replace(
                    year=now_dt.year,
                    month=now_dt.month,
                    day=now_dt.day
                )
            except ValueError:
                story["status"] = "error"
                story["error_text"] = "Неверный формат времени"
                updated = True
                continue

            if publish_dt > now_dt:
                continue

            print(f"Нашел сторис для публикации: {story.get('display_name')} / {publish_time}")

            success, error_text = await publish_story(story, accounts)

            display_name = story.get("display_name", story.get("account_name"))
            caption = story.get("caption", "")
            published_time = datetime.now().strftime("%H:%M")

            if success:
                story["status"] = "published"
                story["published_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                updated = True

                await notify_owner(
                    story,
                    f"✅ Сторис опубликована\n\n"
                    f"Аккаунт: {display_name}\n"
                    f"Время: {published_time}\n"
                    f"Подпись: {caption}"
                )

            else:
                story["status"] = "error"
                story["error_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                story["error_text"] = error_text
                updated = True

                raw_error = str(error_text).lower()

                nice_error = "Неизвестная ошибка"

                if "premium account is required" in raw_error:
                    nice_error = "Требуется Telegram Premium"

                elif "not authorized" in raw_error or "не авторизован" in raw_error:
                    nice_error = "Аккаунт не авторизован"

                elif "photo not found" in raw_error or "фото не найдено" in raw_error:
                    nice_error = "Фото не найдено"

                elif "stories_too_much" in raw_error:
                    nice_error = "Слишком много сторис подряд. Попробуй позже"

                elif "failure while processing image" in raw_error:
                    nice_error = "Telegram не принял фото. Попробуй другое изображение"

                await notify_owner(
                    story,
                    f"⚠️ Не удалось опубликовать сторис\n\n"
                    f"Аккаунт: {display_name}\n"
                    f"Причина: {nice_error}"
                )

        if updated:
            save_stories(stories)

        await asyncio.sleep(15)


if __name__ == "__main__":
    asyncio.run(main())
