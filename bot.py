import json
import os
import asyncio
import re
from datetime import datetime

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from storage import get_accounts_dict, save_account, delete_account
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")

SESSIONS_DIR = "sessions"
STORIES_DIR = "stories"

ACCOUNTS_FILE = "accounts.json"
STORIES_QUEUE_FILE = "stories_queue.json"

os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(STORIES_DIR, exist_ok=True)

ACCOUNT_NAME, PHONE, CODE, PASSWORD, STORY_ACCOUNT, STORY_PHOTO, STORY_CAPTION, STORY_TIME, DELETE_ACCOUNT = range(9)

menu = ReplyKeyboardMarkup(
    [
        ["📱 Мои аккаунты", "➕ Добавить аккаунт"],
        ["🗑 Удалить аккаунт", "📸 Добавить сторис"],
        ["📊 Статистика", "⚙️ Настройки"],
        ["🔗 Ссылка доступа"],
    ],
    resize_keyboard=True
)


def load_accounts():
    return get_accounts_dict()


def save_accounts(data):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_stories_queue():
    if not os.path.exists(STORIES_QUEUE_FILE):
        return []
    with open(STORIES_QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_stories_queue(data):
    with open(STORIES_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def valid_time(text):
    try:
        datetime.strptime(text, "%H:%M")
        return True
    except ValueError:
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    # ТВОЙ TELEGRAM ID
    ALLOWED_USERS = {
        7565144360
    }

    # Секретные invite коды
    INVITE_CODES = {
        "mysecretcode"
    }

    args = context.args

    # Если юзер уже есть в whitelist
    if user_id in ALLOWED_USERS:
        pass

    # Если зашел по invite ссылке
    elif args and args[0] in INVITE_CODES:
        ALLOWED_USERS.add(user_id)

    # Если просто открыл бота
    else:
        await update.message.reply_text("⛔ Доступ запрещен")
        return

    await update.message.reply_text(
        "Бот для Telegram Stories запущен ✅\n\n"
        "➕ Добавить аккаунт — подключить Telegram\n"
        "📸 Добавить сторис — загрузить фото, подпись и время\n"
        "🗑 Удалить аккаунт — удалить подключенную сессию",
        reply_markup=menu
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    user_id = update.effective_user.id
    text = update.message.text

    if "Ссылка доступа" in text:
        bot_username = context.bot.username
        invite_link = f"https://t.me/{bot_username}?start=mysecretcode"

        await update.message.reply_text(
            f"🔗 Ссылка доступа:\n\n{invite_link}"
        )
        return

    if "Мои аккаунты" in text:
        accounts = load_accounts()
        my_accounts = []

        for name, info in accounts.items():
            if info.get("owner_id") != user_id:
                continue

            session_path = info.get("session", "").replace(".session", "")

            try:
                client = TelegramClient(
                    session_path,
                    API_ID,
                    API_HASH
                )

                await client.connect()

                if await client.is_user_authorized():
                    my_accounts.append((name, info))

                await client.disconnect()

            except Exception:
                try:
                    await client.disconnect()
                except Exception:
                    pass

        if not my_accounts:
            await update.message.reply_text(
                "📲 У тебя пока нет активных подключенных аккаунтов."
            )
            return

        buttons = []
        row = []

        for name, info in my_accounts:
            row.append(
                InlineKeyboardButton(
                    info.get("display_name", name),
                    callback_data="noop"
                )
            )

            if len(row) == 2:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        await update.message.reply_text(
            "📲 Твои активные подключенные аккаунты:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif "Статистика" in text:
        accounts = load_accounts()
        stories = load_stories_queue()

        my_accounts = [
            name for name, info in accounts.items()
            if info.get("owner_id") == user_id
        ]

        my_stories = [
            story for story in stories
            if story.get("owner_id") == user_id
        ]

        scheduled = [s for s in my_stories if s.get("status") == "scheduled"]
        published = [s for s in my_stories if s.get("status") == "published"]
        errors = [s for s in my_stories if s.get("status") == "error"]

        await update.message.reply_text(
            f"📊 Статистика:\n\n"
            f"Аккаунтов: {len(my_accounts)}\n"
            f"Сторис всего: {len(my_stories)}\n"
            f"В очереди: {len(scheduled)}\n"
            f"Опубликовано: {len(published)}\n"
            f"Ошибок: {len(errors)}"
        )

    elif "Настройки" in text:
        await update.message.reply_text("⚙️ Настройки пока базовые.")


async def add_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "➕ Введи название аккаунта.\n\n"
        "Например:\n"
        "SofiVip\n"
    )
    return ACCOUNT_NAME


async def account_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.message.text.strip().lower().replace(" ", "_")

    if not name:
        await update.message.reply_text("Название не может быть пустым.")
        return ACCOUNT_NAME

    accounts = load_accounts()
    final_name = f"{user_id}_{name}"

    if final_name in accounts:

        old_info = accounts[final_name]
        session_path = old_info.get("session", "").replace(".session", "")

        is_active = False

        try:
            client = TelegramClient(
                session_path,
                API_ID,
                API_HASH
            )

            await client.connect()

            is_active = await client.is_user_authorized()

            await client.disconnect()

        except Exception:
            try:
                await client.disconnect()
            except Exception:
                pass

        if is_active:
            await update.message.reply_text(
                "Такое название уже есть. Введи другое."
            )
            return ACCOUNT_NAME

        del accounts[final_name]
        save_accounts(accounts)

    context.user_data["account_name"] = final_name
    context.user_data["display_name"] = name

    await update.message.reply_text(
        "Теперь введи номер телефона.\n\n"
        "Пример:\n"
        "+380636062796"
    )

    return PHONE


async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_phone = update.message.text.strip()

    phone_number = re.sub(r"[^\d+]", "", raw_phone)
    user_id = update.effective_user.id
    accounts = load_accounts()

    accounts_changed = False

    for existing_name, existing_info in list(accounts.items()):
        if (
            existing_info.get("owner_id") == user_id
            and existing_info.get("phone") == phone_number
        ):
            old_session_path = existing_info.get("session", "").replace(".session", "")

            is_active = False

            try:
                old_client = TelegramClient(
                    old_session_path,
                    API_ID,
                    API_HASH
                )

                await old_client.connect()
                is_active = await old_client.is_user_authorized()
                await old_client.disconnect()

            except Exception:
                try:
                    await old_client.disconnect()
                except Exception:
                    pass

            if is_active:
                await update.message.reply_text(
                    f"⚠️ Этот номер уже подключен.\n\n"
                    f"Аккаунт: {existing_info.get('display_name', existing_name)}",
                    reply_markup=menu
                )
                context.user_data.clear()
                return ConversationHandler.END

            del accounts[existing_name]
            accounts_changed = True

    if accounts_changed:
        save_accounts(accounts)

    account_name = context.user_data["account_name"]
    session_path = os.path.join(SESSIONS_DIR, account_name)

    client = TelegramClient(session_path, API_ID, API_HASH)

    try:
        await client.connect()

        if await client.is_user_authorized():
            context.user_data["client"] = client
            context.user_data["phone"] = phone_number
            return await finish_account(update, context)

        await update.message.reply_text("Отправляю код в Telegram, подожди...")

        await asyncio.wait_for(
            client.send_code_request(phone_number),
            timeout=30
        )

    except asyncio.TimeoutError:
        await client.disconnect()
        await update.message.reply_text(
            "❌ Telegram долго не отвечает при отправке кода.\n\n"
            "Попробуй ещё раз через минуту.",
            reply_markup=menu
        )
        context.user_data.clear()
        return ConversationHandler.END

    except Exception:
        await client.disconnect()
        await update.message.reply_text(
            "⛔ Доступ запрещен",
            reply_markup=menu
        )

        context.user_data.clear()
        return ConversationHandler.END

    context.user_data["client"] = client
    context.user_data["phone"] = phone_number

    await update.message.reply_text("Код отправлен ✅\n\nВведи код из Telegram.")
    return CODE


async def code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code_text = update.message.text.strip().replace(" ", "")
    client = context.user_data["client"]
    phone_number = context.user_data["phone"]

    try:
        await client.sign_in(phone=phone_number, code=code_text)

    except PhoneCodeInvalidError:
        await update.message.reply_text(
            "❌ Неверный код. Введи код еще раз."
        )
        return CODE

    except SessionPasswordNeededError:

        WEBAPP_URL = "https://story-tg-fbm0.onrender.com/webapp/2fa.html"

        await update.message.reply_text(
            "🔐 На аккаунте включен пароль 2FA.\n\n"
            "Нажми кнопку ниже и введи пароль безопасно.",
            reply_markup=ReplyKeyboardMarkup(
                [
                    [
                        KeyboardButton(
                            "🔐 Ввести 2FA пароль",
                            web_app=WebAppInfo(url=WEBAPP_URL)
                        )
                    ]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )

        return PASSWORD

    except Exception as e:
        await client.disconnect()

        await update.message.reply_text(
            f"❌ Ошибка входа:\n{e}"
        )

        return ConversationHandler.END

    return await finish_account(update, context)


async def password(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        await update.message.delete()
    except Exception:
        pass

    if update.message.web_app_data:
        data = json.loads(update.message.web_app_data.data)
        password_text = data.get("password", "").strip()

    else:
        password_text = update.message.text.strip()

        try:
            await update.message.delete()
        except Exception:
            pass

    client = context.user_data["client"]

    try:
        await client.sign_in(password=password_text)

        password_text = None

        await update.message.reply_text(
            "✅ Аккаунт успешно подключен.",
            reply_markup=menu
        )

        return await finish_account(update, context)

    except Exception:

        password_text = None

        await update.message.reply_text(
            "❌ Неверный пароль 2FA.\n\nПопробуй еще раз.",
            reply_markup=ReplyKeyboardMarkup(
                [
                    [
                        KeyboardButton(
                            "🔐 Ввести 2FA пароль",
                            web_app=WebAppInfo(
                                url="https://story-tg-fbm0.onrender.com/webapp/2fa.html"
                            )
                        )
                    ]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )

        return PASSWORD


async def finish_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    client = context.user_data["client"]
    account_name = context.user_data["account_name"]
    display_name = context.user_data["display_name"]

    me = await client.get_me()
    accounts = load_accounts()

    accounts_changed = False

    for existing_name, existing_info in list(accounts.items()):
        if (
            existing_info.get("owner_id") == user_id
            and existing_info.get("telegram_id") == me.id
        ):
            old_session_path = existing_info.get("session", "").replace(".session", "")

            is_active = False

            try:
                old_client = TelegramClient(
                    old_session_path,
                    API_ID,
                    API_HASH
                )

                await old_client.connect()
                is_active = await old_client.is_user_authorized()
                await old_client.disconnect()

            except Exception:
                try:
                    await old_client.disconnect()
                except Exception:
                    pass

            if is_active:
                username_text = f"@{me.username}" if me.username else "нет username"

                await update.message.reply_text(
                    f"⚠️ Этот Telegram уже добавлен.\n\n"
                    f"Название: {existing_info.get('display_name', existing_name)}\n"
                    f"Username: {username_text}",
                    reply_markup=menu
                )

                await client.disconnect()
                context.user_data.clear()
                return ConversationHandler.END

            del accounts[existing_name]
            accounts_changed = True

    if accounts_changed:
        save_accounts(accounts)

    account_data = {
        "owner_id": user_id,
        "display_name": display_name,
        "phone": context.user_data.get("phone"),
        "telegram_id": me.id,
        "username": me.username,
        "first_name": me.first_name,
        "session": f"sessions/{account_name}.session"
    }

    save_account(account_name, account_data)

    username = f"@{me.username}" if me.username else "нет username"

    await update.message.reply_text(
        f"✅ Аккаунт подключен!\n\n"
        f"Название: {display_name}\n"
        f"Имя: {me.first_name}\n"
        f"Username: {username}\n\n"
        f"Теперь можно выкладывать сторис через этот аккаунт.",
        reply_markup=menu
    )

    await client.disconnect()
    context.user_data.clear()
    return ConversationHandler.END


async def delete_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    accounts = load_accounts()

    my_accounts = []

    for name, info in accounts.items():

        if info.get("owner_id") != user_id:
            continue

        session_path = info.get("session", "").replace(".session", "")

        is_active = False

        try:
            client = TelegramClient(
                session_path,
                API_ID,
                API_HASH
            )

            await client.connect()

            is_active = await client.is_user_authorized()

            await client.disconnect()

        except Exception:
            try:
                await client.disconnect()
            except Exception:
                pass

        if is_active:
            my_accounts.append((name, info))

    if not my_accounts:
        await update.message.reply_text(
            "У тебя пока нет активных аккаунтов для удаления."
        )
        return ConversationHandler.END

    context.user_data["delete_accounts"] = my_accounts

    msg = "🗑 Выбери аккаунт для удаления:\n\n"

    for i, (name, info) in enumerate(my_accounts, start=1):
        msg += f"{i}. {info.get('display_name', name)}\n"

    msg += "\nВведи номер аккаунта."

    await update.message.reply_text(msg)

    return DELETE_ACCOUNT


async def delete_account_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text("Введи номер аккаунта цифрой.")
        return DELETE_ACCOUNT

    index = int(text) - 1
    my_accounts = context.user_data.get("delete_accounts", [])

    if index < 0 or index >= len(my_accounts):
        await update.message.reply_text("Такого номера нет. Введи ещё раз.")
        return DELETE_ACCOUNT

    account_name, info = my_accounts[index]
    display_name = info.get("display_name", account_name)
    session_file = info.get("session")

    accounts = load_accounts()

    if account_name in accounts:
        delete_account(account_name)

    deleted_files = []

    if session_file and os.path.exists(session_file):
        os.remove(session_file)
        deleted_files.append(session_file)

    session_journal = f"{session_file}-journal" if session_file else None
    if session_journal and os.path.exists(session_journal):
        os.remove(session_journal)
        deleted_files.append(session_journal)

    await update.message.reply_text(
        f"✅ Аккаунт удалён.\n\n"
        f"Аккаунт: {display_name}\n"
        f"Сессия: {'удалена' if deleted_files else 'файл сессии не найден'}",
        reply_markup=menu
    )

    context.user_data.clear()
    return ConversationHandler.END


async def add_story_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    accounts = load_accounts()

    my_accounts = []

    for name, info in accounts.items():
        if info.get("owner_id") != user_id:
            continue

        session_path = info.get("session", "").replace(".session", "")

        is_active = False

        try:
            client = TelegramClient(
                session_path,
                API_ID,
                API_HASH
            )

            await client.connect()
            is_active = await client.is_user_authorized()
            await client.disconnect()

        except Exception:
            try:
                await client.disconnect()
            except Exception:
                pass

        if is_active:
            my_accounts.append((name, info))

    if not my_accounts:
        await update.message.reply_text("У тебя пока нет активных подключенных аккаунтов.")
        return ConversationHandler.END

    context.user_data["story_accounts"] = my_accounts

    buttons = []
    row = []

    for i, (name, info) in enumerate(my_accounts):
        row.append(
            InlineKeyboardButton(
                info.get("display_name", name),
                callback_data=f"story_acc_{i}"
            )
        )

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    await update.message.reply_text(
        "📸 Выбери аккаунт для сторис:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    return STORY_ACCOUNT


async def story_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if not data.startswith("story_acc_"):
        return STORY_ACCOUNT

    index = int(data.replace("story_acc_", ""))
    accounts = context.user_data.get("story_accounts", [])

    if index < 0 or index >= len(accounts):
        await query.message.reply_text("Ошибка выбора аккаунта.")
        return STORY_ACCOUNT

    account_name, info = accounts[index]

    context.user_data["story_account_name"] = account_name
    context.user_data["story_display_name"] = info.get("display_name", account_name)

    await query.message.reply_text("Теперь отправь фото или видео для сторис.")

    return STORY_PHOTO


async def story_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text("Введи номер аккаунта цифрой.")
        return STORY_ACCOUNT

    index = int(text) - 1
    accounts = context.user_data.get("story_accounts", [])

    if index < 0 or index >= len(accounts):
        await update.message.reply_text("Такого номера нет. Введи ещё раз.")
        return STORY_ACCOUNT

    account_name, info = accounts[index]

    context.user_data["story_account_name"] = account_name
    context.user_data["story_display_name"] = info.get("display_name", account_name)

    await update.message.reply_text("Теперь отправь фото для сторис.")
    return STORY_PHOTO


async def story_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo and not update.message.video and not update.message.video_note:
        await update.message.reply_text("Нужно отправить фото или видео.")
        return STORY_PHOTO

    account_name = context.user_data["story_account_name"]

    if update.message.video or update.message.video_note:
        video = update.message.video or update.message.video_note
        file = await video.get_file()

        filename = f"{account_name}_{update.effective_user.id}_{update.message.message_id}.mp4"
        file_path = os.path.join(STORIES_DIR, filename)

        await file.download_to_drive(file_path)

        context.user_data["story_file_path"] = file_path
        context.user_data["story_photo_path"] = file_path
        context.user_data["story_media_type"] = "video"

        await update.message.reply_text("Видео сохранено ✅\nТеперь напиши подпись для сторис.")
        return STORY_CAPTION

    photo = update.message.photo[-1]
    file = await photo.get_file()

    filename = f"{account_name}_{update.effective_user.id}_{update.message.message_id}.jpg"
    file_path = os.path.join(STORIES_DIR, filename)

    await file.download_to_drive(file_path)

    context.user_data["story_file_path"] = file_path
    context.user_data["story_photo_path"] = file_path
    context.user_data["story_media_type"] = "photo"

    await update.message.reply_text("Фото сохранено ✅\nТеперь напиши подпись для сторис.")
    return STORY_CAPTION


async def story_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.text.strip()
    context.user_data["story_caption"] = caption

    await update.message.reply_text(
        "⏰ Теперь введи время публикации.\n\n"
    )

    return STORY_TIME


async def story_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_time = update.message.text.strip()

    cleaned = re.sub(r"[^\d]", "", raw_time)

    if len(cleaned) == 3:
        cleaned = "0" + cleaned

    if len(cleaned) != 4:
        await update.message.reply_text(
            "❌ Неверное время.\n\nПримеры:\n16:30\n1630\n16 30"
        )
        return STORY_TIME

    hours = int(cleaned[:2])
    minutes = int(cleaned[2:])

    if hours > 23 or minutes > 59:
        await update.message.reply_text(
            "❌ Неверное время.\n\nПример:\n16:30"
        )
        return STORY_TIME

    publish_time = f"{hours:02d}:{minutes:02d}"

    story = {
        "owner_id": update.effective_user.id,
        "account_name": context.user_data["story_account_name"],
        "display_name": context.user_data["story_display_name"],
        "file_path": context.user_data.get("story_file_path") or context.user_data.get("story_photo_path"),
        "photo_path": context.user_data.get("story_photo_path") or context.user_data.get("story_file_path"),
        "media_type": context.user_data.get("story_media_type", "photo"),
        "caption": context.user_data["story_caption"],
        "publish_time": publish_time,
        "status": "scheduled",
    }

    stories = load_stories_queue()
    stories.append(story)
    save_stories_queue(stories)

    await update.message.reply_text(
        f"✅ Сторис поставлена в очередь!\n\n"
        f"Аккаунт: {story['display_name']}\n"
        f"Время: {publish_time}\n"
        f"Подпись: {story['caption']}",
        reply_markup=menu
    )

    context.user_data.clear()

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = context.user_data.get("client")

    if client:
        await client.disconnect()

    context.user_data.clear()
    await update.message.reply_text("❌ Действие отменено.", reply_markup=menu)
    return ConversationHandler.END


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Это просто список аккаунтов.")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не найден в .env")

    if not API_ID or not API_HASH:
        raise RuntimeError("API_ID или API_HASH не найдены в .env")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(noop_callback, pattern="^noop$"))

    main_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Добавить аккаунт$"), add_account_start),
            MessageHandler(filters.Regex("^🗑 Удалить аккаунт$"), delete_account_start),
            MessageHandler(filters.Regex("^📸 Добавить сторис$"), add_story_start),
            
            MessageHandler(filters.Regex("^➕ Добавить аккаунт$"), add_account_start),
            MessageHandler(filters.Regex("^🗑 Удалить аккаунт$"), delete_account_start),
            MessageHandler(filters.Regex("^📸 Добавить сторис$"), add_story_start),
        ],
        states={
            ACCOUNT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, account_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, code)],
            PASSWORD: [
                MessageHandler(filters.StatusUpdate.WEB_APP_DATA, password),
                MessageHandler(filters.TEXT & ~filters.COMMAND, password),
          ],

            DELETE_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_account_choose)],

            STORY_ACCOUNT: [
              CallbackQueryHandler(story_account_callback, pattern="^story_acc_")
            ],
            STORY_PHOTO: [MessageHandler(filters.PHOTO | filters.VIDEO | filters.VIDEO_NOTE, story_photo)],
            STORY_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, story_caption)],
            STORY_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, story_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(main_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот Stories запущен...")
    print("STARTING POLLING...", flush=True)
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
