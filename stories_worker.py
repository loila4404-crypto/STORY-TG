import asyncio
import json
import os
import subprocess
from datetime import datetime
from datetime import datetime, timedelta
from supabase_files import download_story_file, delete_story_file

from dotenv import load_dotenv
from PIL import Image, ImageOps
from telegram import Bot
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.stories import SendStoryRequest
from telethon.tl.types import (
    InputPrivacyValueAllowAll,
    InputMediaUploadedPhoto,
    InputMediaUploadedDocument,
    DocumentAttributeVideo
)
from storage import (
    get_accounts_dict,
    get_all_stories,
    mark_story_published,
    mark_story_error,
    delete_published_stories
)

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
    return get_accounts_dict()


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


def prepare_story_video(video_path):
    base_name = os.path.basename(video_path)

    prepared_path = os.path.join(
        PREPARED_DIR,
        f"prepared_{base_name}"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-t", "60",

        "-vf",
        "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1",

        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "32",
        "-maxrate", "800k",
        "-bufsize", "1200k",
        "-pix_fmt", "yuv420p",
        "-threads", "1",

        "-c:a", "aac",
        "-b:a", "96k",

        "-movflags", "+faststart",

        prepared_path
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=180
        )

        if result.returncode != 0:
            print("FFMPEG ERROR:", result.stderr, flush=True)
            return video_path

        print(f"Видео подготовлено: {prepared_path}", flush=True)

        return prepared_path

    except Exception as e:
        print(f"Ошибка ffmpeg: {e}", flush=True)
        return video_path


async def publish_story(story, accounts):
    account_name = story["account_name"]

    if account_name not in accounts:
        print(f"Аккаунт {account_name} не найден", flush=True)
        return False, "Аккаунт не найден"

    info = accounts[account_name]
    session_string = info.get("session_string")

    if not session_string:
        print(f"У аккаунта {account_name} нет session_string", flush=True)
        return False, "Аккаунт нужно переподключить"

    client = TelegramClient(
        StringSession(session_string),
        API_ID,
        API_HASH
    )

    temp_file_path = None

    try:
        await client.connect()

        if not await client.is_user_authorized():
            print(f"{account_name} не авторизован", flush=True)
            await client.disconnect()
            return False, "Сессия не авторизована"

        storage_path = story.get("storage_path") or story.get("story_storage_path")
        file_path = story.get("file_path") or story.get("photo_path")
        media_type = story.get("media_type", "photo")
        caption = story.get("caption", "")

        if storage_path:
            print(f"Скачиваю файл из Supabase Storage: {storage_path}", flush=True)
            temp_file_path = download_story_file(storage_path)
            file_path = temp_file_path

        if not file_path or not os.path.exists(file_path):
            print(f"Файл не найден: {file_path}", flush=True)
            await client.disconnect()
            return False, "Файл не найден"

        print(f"Публикую сторис: {account_name}", flush=True)

        if media_type == "video" or file_path.lower().endswith((".mp4", ".mov", ".m4v")):
            print(f"Готовлю видео: {file_path}", flush=True)

            prepared_path = prepare_story_video(file_path)
            file = await client.upload_file(prepared_path)

            media = InputMediaUploadedDocument(
                file=file,
                mime_type="video/mp4",
                attributes=[
                    DocumentAttributeVideo(
                        duration=15,
                        w=1080,
                        h=1920,
                        supports_streaming=True
                    )
                ]
            )

        else:
            print(f"Готовлю фото: {file_path}", flush=True)

            prepared_path = prepare_story_image(file_path)
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

        print(f"Сторис опубликована: {account_name}", flush=True)

        if storage_path:
            delete_story_file(storage_path)

        await client.disconnect()

        try:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        except Exception:
            pass

        return True, None

    except Exception as e:
        print(f"Ошибка публикации {account_name}: {e}", flush=True)

        try:
            await client.disconnect()
        except Exception:
            pass

        try:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        except Exception:
            pass

        return False, str(e)


async def main():
    print("Stories worker запущен...", flush=True)

    while True:
        try:
            now_dt = datetime.now() + timedelta(hours=3)
            now_time = now_dt.strftime("%H:%M")

            accounts = load_accounts()
            stories = get_all_stories()

            print(f"Проверка очереди: {now_time}", flush=True)
            print(f"Сторис в Supabase очереди: {len(stories)}", flush=True)

            for story in stories:
                story_id = story.get("id")

                publish_time = story.get("publish_time")

                if not publish_time:
                    mark_story_error(story_id, "Нет времени публикации")
                    continue

                try:
                    publish_dt = datetime.strptime(publish_time, "%H:%M").replace(
                        year=now_dt.year,
                        month=now_dt.month,
                        day=now_dt.day
                    )

                except ValueError:
                    mark_story_error(story_id, "Неверный формат времени")
                    continue

                if publish_dt > now_dt:
                    continue

                print(
                    f"Нашел сторис для публикации: {story.get('display_name')} / {publish_time}",
                    flush=True
                )

                success, error_text = await publish_story(story, accounts)

                await asyncio.sleep(30)

                display_name = story.get("display_name", story.get("account_name"))
                caption = story.get("caption", "")
                published_time = datetime.now().strftime("%H:%M")

                if success:
                    mark_story_published(story_id)
                    delete_published_stories()

                    await notify_owner(
                        story,
                        f"✅ Сторис опубликована\n\n"
                        f"Аккаунт: {display_name}\n"
                        f"Время: {published_time}\n"
                        f"Подпись: {caption}"
                    )

                else:
                    mark_story_error(story_id, error_text)

                    raw_error = str(error_text).lower()
                    nice_error = "Неизвестная ошибка"

                    if "premium account is required" in raw_error:
                        nice_error = "Требуется Telegram Premium"
                    elif "not authorized" in raw_error or "не авторизован" in raw_error:
                        nice_error = "Аккаунт не авторизован"
                    elif "photo not found" in raw_error or "фото не найдено" in raw_error:
                        nice_error = "Фото не найдено"
                    elif "file not found" in raw_error or "файл не найден" in raw_error:
                        nice_error = "Файл не найден"
                    elif "stories_too_much" in raw_error:
                        nice_error = "Слишком много сторис подряд. Попробуй позже"
                    elif "failure while processing image" in raw_error:
                        nice_error = "Telegram не принял фото. Попробуй другое изображение"
                    elif "video" in raw_error:
                        nice_error = "Telegram не принял видео. Попробуй mp4 до 60 секунд"

                    await notify_owner(
                        story,
                        f"⚠️ Не удалось опубликовать сторис\n\n"
                        f"Аккаунт: {display_name}\n"
                        f"Причина: {nice_error}"
                    )

        except Exception as e:
            print(f"WORKER GLOBAL ERROR: {e}", flush=True)

        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
