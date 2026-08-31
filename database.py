import os
import sqlite3
from contextlib import closing
from typing import Optional

from config import ADMIN_IDS

# Ma'lumotlar bazasi fayli. Hosting platformasida (Railway, Render va h.k.)
# fayl tizimi har deploy'da tozalanadigan bo'lsa, DB_PATH ni persistent disk/volume
# ichidagi papkaga ko'rsating (masalan, /data/kino.db), aks holda statistikalar
# har safar bot qayta ishga tushganda yo'qolib qoladi.
DB_PATH = os.getenv("DB_PATH", "data/kino.db")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(_connect()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                watched_count INTEGER NOT NULL DEFAULT 0,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS movies (
                code TEXT PRIMARY KEY,
                type TEXT NOT NULL,              -- 'film' | 'serial'
                caption TEXT,
                file_id TEXT,                    -- faqat 'film' uchun
                views INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS series_parts (
                code TEXT NOT NULL,
                part_number INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                PRIMARY KEY (code, part_number)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # .env dagi ADMIN_IDS ham admins jadvaliga qo'shib qo'yiladi, shunda
        # "Admin qo'shish" orqali qo'shilgan adminlar bilan bitta ro'yxatda yuradi.
        for admin_id in ADMIN_IDS:
            conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
        conn.commit()


# ---------- Foydalanuvchilar ----------

def touch_user(user_id: int, username: Optional[str], full_name: Optional[str]) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username,
                                                full_name = excluded.full_name
            """,
            (user_id, username, full_name),
        )
        conn.commit()


def increment_watched(user_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            "UPDATE users SET watched_count = watched_count + 1 WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone()


def top_users(limit: int = 10) -> list[sqlite3.Row]:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "SELECT * FROM users ORDER BY watched_count DESC, user_id ASC LIMIT ?",
            (limit,),
        )
        return cur.fetchall()


def count_users() -> int:
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT COUNT(*) AS c FROM users")
        return cur.fetchone()["c"]


# ---------- Kinolar / seriallar ----------

def code_exists(code: str) -> bool:
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT 1 FROM movies WHERE code = ?", (code,))
        return cur.fetchone() is not None


def add_film(code: str, caption: Optional[str], file_id: str) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO movies (code, type, caption, file_id)
            VALUES (?, 'film', ?, ?)
            ON CONFLICT(code) DO UPDATE SET caption = excluded.caption,
                                             file_id = excluded.file_id
            """,
            (code, caption, file_id),
        )
        conn.commit()


def create_serial(code: str, caption: Optional[str] = None) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO movies (code, type, caption)
            VALUES (?, 'serial', ?)
            ON CONFLICT(code) DO NOTHING
            """,
            (code, caption),
        )
        conn.commit()


def add_series_part(code: str, part_number: int, file_id: str) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO series_parts (code, part_number, file_id)
            VALUES (?, ?, ?)
            ON CONFLICT(code, part_number) DO UPDATE SET file_id = excluded.file_id
            """,
            (code, part_number, file_id),
        )
        conn.commit()


def get_movie(code: str) -> Optional[sqlite3.Row]:
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT * FROM movies WHERE code = ?", (code,))
        return cur.fetchone()


def get_series_parts(code: str) -> list[sqlite3.Row]:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "SELECT * FROM series_parts WHERE code = ? ORDER BY part_number ASC",
            (code,),
        )
        return cur.fetchall()


def get_series_part(code: str, part_number: int) -> Optional[sqlite3.Row]:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "SELECT * FROM series_parts WHERE code = ? AND part_number = ?",
            (code, part_number),
        )
        return cur.fetchone()


def increment_views(code: str) -> None:
    with closing(_connect()) as conn:
        conn.execute("UPDATE movies SET views = views + 1 WHERE code = ?", (code,))
        conn.commit()


def count_movies() -> dict:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "SELECT type, COUNT(*) AS c FROM movies GROUP BY type"
        )
        result = {"film": 0, "serial": 0}
        for row in cur.fetchall():
            result[row["type"]] = row["c"]
        return result


def total_views() -> int:
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT COALESCE(SUM(views), 0) AS s FROM movies")
        return cur.fetchone()["s"]


def delete_movie(code: str) -> None:
    """Kino/serialni va uning barcha qismlarini bazadan butunlay o'chiradi."""
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM movies WHERE code = ?", (code,))
        conn.execute("DELETE FROM series_parts WHERE code = ?", (code,))
        conn.commit()


# ---------- Adminlar ----------

def is_admin(user_id: int) -> bool:
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        return cur.fetchone() is not None


def add_admin(user_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        conn.commit()


def remove_admin(user_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()


def list_admins() -> list[int]:
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT user_id FROM admins ORDER BY added_at ASC")
        return [row["user_id"] for row in cur.fetchall()]
