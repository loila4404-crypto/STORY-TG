import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_accounts():
    result = supabase.table("accounts").select("*").execute()
    return result.data or []


def get_accounts_dict():
    accounts = get_accounts()
    return {
        item["account_name"]: {
            "owner_id": item["owner_id"],
            "display_name": item.get("display_name"),
            "phone": item.get("phone"),
            "session": item.get("session_path"),
        }
        for item in accounts
    }


def save_account(account_name, data):
    supabase.table("accounts").upsert({
        "owner_id": data.get("owner_id"),
        "account_name": account_name,
        "display_name": data.get("display_name"),
        "phone": data.get("phone"),
        "telegram_id": data.get("telegram_id"),
        "username": data.get("username"),
        "first_name": data.get("first_name"),
        "session_path": data.get("session"),
    }).execute()


def delete_account(account_name):