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
                is_blocked INTEGER NOT NULL DEFAULT 0,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Eski bazalarda "users" jadvali is_blocked ustunisiz yaratilgan bo'lishi
        # mumkin, shuning uchun bu yerda migratsiya qilamiz.
        existing_cols = [row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "is_blocked" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS movies (
                code TEXT PRIMARY KEY,
                type TEXT NOT NULL,              -- 'film' | 'serial'
                caption TEXT,                    -- film uchun izoh, serial uchun nomi
                file_id TEXT,                    -- faqat 'film' uchun
                poster_file_id TEXT,              -- serial uchun logo/plakat rasmi (ixtiyoriy)
                views INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Eski bazalarda "movies" jadvali poster_file_id ustunisiz yaratilgan
        # bo'lishi mumkin, shuning uchun bu yerda migratsiya qilamiz.
        movie_cols = [row["name"] for row in conn.execute("PRAGMA table_info(movies)").fetchall()]
        if "poster_file_id" not in movie_cols:
            conn.execute("ALTER TABLE movies ADD COLUMN poster_file_id TEXT")
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS movie_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                request_text TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS movie_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                movie_name TEXT NOT NULL,
                comment_text TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
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


def get_all_user_ids() -> list[int]:
    """Xabar (broadcast) yuborish uchun barcha foydalanuvchilar ID ro'yxati."""
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT user_id FROM users")
        return [row["user_id"] for row in cur.fetchall()]


def is_user_blocked(user_id: int) -> bool:
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return bool(row["is_blocked"]) if row else False


def block_user(user_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
        conn.commit()


def unblock_user(user_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,))
        conn.commit()


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


def create_serial(code: str, name: str, poster_file_id: Optional[str] = None) -> None:
    """Serialni (yoki uning nomi/logosini) yaratadi yoki yangilaydi.

    Agar shu kod bilan serial allaqachon mavjud bo'lsa (masalan, unga yana
    qism qo'shish uchun qayta ochilgan bo'lsa), nomi va logosi yangilanadi;
    poster_file_id berilmagan (None) bo'lsa, avvalgi logo saqlanib qoladi.
    """
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO movies (code, type, caption, poster_file_id)
            VALUES (?, 'serial', ?, ?)
            ON CONFLICT(code) DO UPDATE SET caption = excluded.caption,
                                             poster_file_id = COALESCE(excluded.poster_file_id, movies.poster_file_id)
            """,
            (code, name, poster_file_id),
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


# ---------- Kino/serial so'rovlari ("Qanday kino kerak?") ----------

def add_movie_request(user_id: int, username: Optional[str], full_name: Optional[str], text: str) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO movie_requests (user_id, username, full_name, request_text)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, username, full_name, text),
        )
        conn.commit()


def count_movie_requests() -> int:
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT COUNT(*) AS c FROM movie_requests")
        return cur.fetchone()["c"]


# ---------- Fikrlar ("kino nomi + izoh" ro'yxati, screenshot uslubida) ----------

def add_movie_review(
    user_id: int, username: Optional[str], full_name: Optional[str], movie_name: str, comment_text: str
) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO movie_reviews (user_id, username, full_name, movie_name, comment_text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, username, full_name, movie_name, comment_text),
        )
        conn.commit()


def count_movie_reviews() -> int:
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT COUNT(*) AS c FROM movie_reviews")
        return cur.fetchone()["c"]


def get_movie_reviews_page(offset: int, limit: int) -> list[sqlite3.Row]:
    """Eng yangi fikrlar birinchi bo'lib chiqadi (id DESC), sahifalab olinadi."""
    with closing(_connect()) as conn:
        cur = conn.execute(
            "SELECT * FROM movie_reviews ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return cur.fetchall()


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
