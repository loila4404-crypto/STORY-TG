import os
import json
import shutil
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI()

from fastapi import Request, HTTPException

ALLOWED_API_IPS = {
    "5.63.19.65",
    "5.63.19.66",
    "5.63.19.67",
    "5.63.19.68",
    "5.63.19.71",
    "5.63.19.74",
    "5.63.19.75",
    "5.63.19.82",
    "5.63.19.84",
    "5.63.19.86",
    "5.63.19.87",
    "5.63.19.88",
    "5.63.19.89",
    "5.63.19.91",
    "5.63.19.136",
    "5.63.19.85",
    "192.142.54.51",
    "192.142.10.199",
    "192.142.53.117",
    "192.142.53.150",
    "192.142.53.154",
    "192.142.10.193",
    "185.163.45.96",
    "5.181.157.49",
    "5.181.157.54",
    "5.181.157.50",
    "5.181.157.51",
    "5.181.157.52",
    "5.181.157.53",
    "192.142.54.193",
    "192.142.53.212",
    "192.142.53.199",
    "192.142.45.8",
    "192.142.45.5",
    "192.142.45.173",
    "192.142.45.104",
    "192.142.18.207",
    "192.142.18.142",
    "192.142.18.109",
    "38.7.145.131",
    "38.7.145.207",
    "38.7.145.208",
    "38.7.145.210",
    "38.7.145.211",
    "38.7.145.235",
    "45.141.56.44",
    "45.141.56.123",
    "2.56.10.23",
    "2.56.10.26",
    "2.56.10.34",
    "85.121.149.215",
    "85.121.149.216",
    "85.121.149.217",
    "85.121.149.218",
    "85.121.149.219",
    "196.196.208.56",
    "196.196.208.55",
    "196.196.208.54",
    "196.196.208.53",
    "196.196.208.52",
    "196.196.208.51",
    "192.142.55.66",
    "192.142.54.171",
    "192.142.54.150",
    "192.142.54.121",
    "192.142.54.118",
    "192.142.54.101",
    "192.142.53.84",
    "192.142.53.218",
    "192.142.53.111",
    "192.142.53.110",
    "192.142.45.69",
    "192.142.45.161",
    "192.142.18.53",
    "192.142.18.237",
    "192.142.18.211",
    "192.142.18.183",
    "192.142.18.115",
    "192.142.10.164",
    "192.142.10.156",
    "192.142.10.121",
    "45.82.64.24",
    "45.82.64.29",
    "45.82.64.59",
    "45.82.64.74",
    "45.82.64.176",
    "85.121.149.223",
    "85.121.149.224",
    "85.121.149.225",
    "85.121.149.227",
    "85.121.149.228",
    "185.153.198.162",
    "185.153.198.68",
    "185.153.198.69",
    "185.153.198.130",
    "185.153.198.131",
    "185.153.198.132",
    "185.153.198.133",
    "185.153.198.135",
    "185.153.198.137",
    "185.153.198.140",
}

@app.middleware("http")
async def api_ip_whitelist(request: Request, call_next):

    path = request.url.path

    # Разрешаем healthcheck и Telegram
    if path in ["/", "/health", "/webhook"]:
        return await call_next(request)

    client_ip = request.headers.get("x-forwarded-for", request.client.host)

    if client_ip:
        client_ip = client_ip.split(",")[0].strip()

    if client_ip not in ALLOWED_API_IPS:
        raise HTTPException(status_code=403, detail="⛔ Доступ запрещен")

    return await call_next(request)

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
