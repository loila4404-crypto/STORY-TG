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

            cur.execute("""
                CREATE TABLE IF NOT EXISTS stories_queue (
                    id BIGSERIAL PRIMARY KEY,
                    owner_id BIGINT NOT NULL,
                    account_name TEXT NOT NULL,
                    display_name TEXT,
                    storage_path TEXT,
                    media_type TEXT DEFAULT 'photo',
                    caption TEXT,
                    publish_time TEXT NOT NULL,
                    status TEXT DEFAULT 'scheduled',
                    error_text TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    published_at TIMESTAMP,
                    error_at TIMESTAMP
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

                    proxy_host,
                    proxy_port,
                    proxy_user,
                    proxy_pass,

                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    NOW()
                )

                ON CONFLICT (account_name)
                DO UPDATE SET
                    owner_id = EXCLUDED.owner_id,
                    display_name = EXCLUDED.display_name,
                    phone = EXCLUDED.phone,
                    telegram_id = EXCLUDED.telegram_id,
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    session_string = EXCLUDED.session_string,

                    proxy_host = EXCLUDED.proxy_host,
                    proxy_port = EXCLUDED.proxy_port,
                    proxy_user = EXCLUDED.proxy_user,
                    proxy_pass = EXCLUDED.proxy_pass,

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

                    account_data.get("proxy_host"),
                    account_data.get("proxy_port"),
                    account_data.get("proxy_user"),
                    account_data.get("proxy_pass"),
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


def add_story_to_queue(story):
    init_db()

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO stories_queue (
                    owner_id,
                    account_name,
                    display_name,
                    storage_path,
                    media_type,
                    caption,
                    publish_date,
                    publish_time,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'scheduled')
                RETURNING id
                """,
                (
                    story.get("owner_id"),
                    story.get("account_name"),
                    story.get("display_name"),
                    story.get("storage_path"),
                    story.get("media_type", "photo"),
                    story.get("caption", ""),
                    story.get("publish_date"),
                    story.get("publish_time"),
                )
            )

            row = cur.fetchone()

        conn.commit()

    return row["id"]


def get_all_stories():
    init_db()

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT *
                FROM stories_queue
                WHERE status = 'scheduled'
                ORDER BY id ASC
            """)
            rows = cur.fetchall()

    return [dict(row) for row in rows]


def mark_story_published(story_id):
    init_db()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE stories_queue
                SET status = 'published',
                    published_at = NOW()
                WHERE id = %s
                """,
                (story_id,)
            )

        conn.commit()


def mark_story_error(story_id, error_text):
    init_db()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE stories_queue
                SET status = 'error',
                    error_text = %s,
                    error_at = NOW()
                WHERE id = %s
                """,
                (str(error_text), story_id)
            )

        conn.commit()


def delete_published_stories():
    init_db()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM stories_queue
                WHERE status = 'published'
            """)

        conn.commit()


def get_next_proxy():
    init_db()

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT *
                FROM proxy_pool
                WHERE is_active = TRUE
                ORDER BY used_count ASC, id ASC
                LIMIT 1
            """)

            proxy = cur.fetchone()

            if not proxy:
                return None

            cur.execute(
                """
                UPDATE proxy_pool
                SET used_count = used_count + 1
                WHERE id = %s
                """,
                (proxy["id"],)
            )

        conn.commit()

    return dict(proxy)
