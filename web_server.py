import os
import json
import shutil
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI()

app.mount("/webapp", StaticFiles(directory="webapp"), name="webapp")

ACCOUNTS_FILE = "accounts.json"
STORIES_QUEUE_FILE = "stories_queue.json"
STORIES_DIR = "stories"

os.makedirs(STORIES_DIR, exist_ok=True)


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


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/stories")
async def stories():
    return FileResponse("webapp/index.html")


@app.get("/api/accounts")
async def api_accounts():
    accounts = load_accounts()

    result = []

    for account_name, info in accounts.items():
        result.append({
            "account_name": account_name,
            "display_name": info.get("display_name", account_name)
        })

    return result


@app.get("/health")
async def health():
    return {"status": "alive"}


@app.post("/api/story")
async def api_story(
    account_name: str = Form(...),
    caption: str = Form(...),
    publish_time: str = Form(...),
    photo: UploadFile = File(...)
):
    accounts = load_accounts()

    if account_name not in accounts:
        return JSONResponse(
            status_code=400,
            content={"error": "Аккаунт не найден"}
        )

    filename = (
        f"{account_name}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    )

    file_path = os.path.join(STORIES_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(photo.file, buffer)

    stories = load_stories()

    stories.append({
        "owner_id": accounts[account_name].get("owner_id"),
        "account_name": account_name,
        "display_name": accounts[account_name].get(
            "display_name",
            account_name
        ),
        "photo_path": file_path,
        "caption": caption,
        "publish_time": publish_time,
        "status": "scheduled"
    })

    save_stories(stories)

    return {
        "success": True,
        "message": "Сторис поставлена в очередь"
    }
