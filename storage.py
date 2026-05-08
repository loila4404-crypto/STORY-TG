import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL не найден в .env / Render Environment")

    return psycopg2.connect(DATABASE_URL)


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_name TEXT PRIMARY KEY,
                    owner_id BIGINT NOT NULL,
                    display_name TEXT,
                    phone TEXT,
                    telegram_id BIGINT,
                    username TEXT,
                    first_name TEXT,
                    session_string TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
        conn.commit()


def get_accounts_dict():
    init_db()

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM accounts")
            rows = cur.fetchall()

    accounts = {}

    for row in rows:
        account_name = row["account_name"]
        accounts[account_name] = dict(row)

    return accounts


def save_account(account_name, account_data):
    init_db()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO accounts (
                    account_name,
                    owner_id,
                    display_name,
                    phone,
                    telegram_id,
                    username,
                    first_name,
                    session_string,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (account_name)
                DO UPDATE SET
                    owner_id = EXCLUDED.owner_id,
                    display_name = EXCLUDED.display_name,
                    phone = EXCLUDED.phone,
                    telegram_id = EXCLUDED.telegram_id,
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    session_string = EXCLUDED.session_string,
                    updated_at = NOW()
                """,
                (
                    account_name,
                    account_data.get("owner_id"),
                    account_data.get("display_name"),
                    account_data.get("phone"),
                    account_data.get("telegram_id"),
                    account_data.get("username"),
                    account_data.get("first_name"),
                    account_data.get("session_string"),
                )
            )

        conn.commit()


def delete_account(account_name):
    init_db()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM accounts WHERE account_name = %s",
                (account_name,)
            )

        conn.commit()


def save_accounts(accounts):
    init_db()

    existing = get_accounts_dict()

    for old_name in existing.keys():
        if old_name not in accounts:
            delete_account(old_name)

    for account_name, account_data in accounts.items():
        save_account(account_name, account_data)
