from datetime import datetime, timezone

import aiosqlite

from config import DB_PATH

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS codes (
    code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    photo_file_id TEXT NOT NULL,
    added_at TEXT NOT NULL,
    uses INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT UNIQUE NOT NULL,   -- @username или числовой chat_id для вызовов Bot API
    username TEXT,                     -- нужен для кнопки-ссылки на канал
    title TEXT,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stats (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES)
        for key in ("successful_searches", "failed_searches"):
            await db.execute(
                "INSERT OR IGNORE INTO stats (key, value) VALUES (?, 0)", (key,)
            )
        await db.commit()


# ---------------------------------------------------------------- Коды ----

async def add_code(code: str, title: str, photo_file_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO codes (code, title, photo_file_id, added_at) VALUES (?, ?, ?, ?)",
                (code, title, photo_file_id, _now()),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def update_code(code: str, title: str, photo_file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE codes SET title = ?, photo_file_id = ? WHERE code = ?",
            (title, photo_file_id, code),
        )
        await db.commit()


async def delete_code(code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM codes WHERE code = ?", (code,))
        await db.commit()
        return cur.rowcount > 0


async def get_code(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM codes WHERE code = ?", (code,))
        return await cur.fetchone()


async def count_codes() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM codes")
        row = await cur.fetchone()
        return row[0]


async def increment_code_uses(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE codes SET uses = uses + 1 WHERE code = ?", (code,))
        await db.commit()


async def top_codes(limit: int = 5):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT code, title, uses FROM codes ORDER BY uses DESC LIMIT ?", (limit,)
        )
        return await cur.fetchall()


# ------------------------------------------------------------- Каналы ----

async def add_channel(identifier: str, username: str | None, title: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO channels (identifier, username, title, added_at) VALUES (?, ?, ?, ?)",
                (identifier, username, title, _now()),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def delete_channel(identifier: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM channels WHERE identifier = ? OR username = ?",
            (identifier, identifier),
        )
        await db.commit()
        return cur.rowcount > 0


async def list_channels():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM channels ORDER BY id")
        return await cur.fetchall()


# ---------------------------------------------------------- Пользователи ----

async def add_user(user_id: int):
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (user_id, first_seen, last_seen) VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET last_seen = excluded.last_seen""",
            (user_id, now, now),
        )
        await db.commit()


async def count_users() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        row = await cur.fetchone()
        return row[0]


# ------------------------------------------------------------ Статистика ----

async def bump_stat(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE stats SET value = value + 1 WHERE key = ?", (key,))
        await db.commit()


async def get_stat(key: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM stats WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else 0
