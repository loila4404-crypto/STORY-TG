import os
import uuid
import tempfile
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "stories")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)


def make_safe_name(value):
    value = str(value or "")

    safe = "".join(
        c for c in value
        if c.isascii() and (c.isalnum() or c in "_-")
    )

    if not safe:
        safe = "account"

    return safe


def upload_story_file(local_path, owner_id, account_name, original_name):
    ext = os.path.splitext(original_name)[1].lower()

    if not ext:
        ext = os.path.splitext(local_path)[1].lower()

    if not ext:
        ext = ".bin"

    safe_account_name = make_safe_name(account_name)

    storage_path = f"{owner_id}/{safe_account_name}/{uuid.uuid4().hex}{ext}"

    with open(local_path, "rb") as f:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            storage_path,
            f,
            file_options={
                "upsert": "true"
            }
        )

    return storage_path


def download_story_file(storage_path):
    data = supabase.storage.from_(SUPABASE_BUCKET).download(storage_path)

    ext = os.path.splitext(storage_path)[1].lower()

    if not ext:
        ext = ".bin"

    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=ext
    )

    temp_file.write(data)
    temp_file.close()

    return temp_file.name


def delete_story_file(storage_path):
    try:
        supabase.storage.from_(SUPABASE_BUCKET).remove([storage_path])
    except Exception as e:
        print(f"Storage delete error: {e}", flush=True)import os
import uuid
import tempfile
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "stories")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)


def make_safe_name(value):
    value = str(value or "")

    safe = "".join(
        c for c in value
        if c.isascii() and (c.isalnum() or c in "_-")
    )

    if not safe:
        safe = "account"

    return safe


def upload_story_file(local_path, owner_id, account_name, original_name):
    ext = os.path.splitext(original_name)[1].lower()

    if not ext:
        ext = os.path.splitext(local_path)[1].lower()

    if not ext:
        ext = ".bin"

    safe_account_name = make_safe_name(account_name)

    storage_path = f"{owner_id}/{safe_account_name}/{uuid.uuid4().hex}{ext}"

    with open(local_path, "rb") as f:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            storage_path,
            f,
            file_options={
                "upsert": "true"
            }
        )

    return storage_path


def download_story_file(storage_path):
    data = supabase.storage.from_(SUPABASE_BUCKET).download(storage_path)

    ext = os.path.splitext(storage_path)[1].lower()

    if not ext:
        ext = ".bin"

    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=ext
    )

    temp_file.write(data)
    temp_file.close()

    return temp_file.name


def delete_story_file(storage_path):
    try:
        supabase.storage.from_(SUPABASE_BUCKET).remove([storage_path])
    except Exception as e:
        print(f"Storage delete error: {e}", flush=True)
