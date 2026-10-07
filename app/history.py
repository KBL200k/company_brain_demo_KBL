"""Conversation history, stored locally in SQLite (data/history/chat.db; git-ignored).

Each assistant message keeps the full pipeline result (route, sources, timings, checks) so an old
conversation can be reopened with its details. API keys are never stored: results only carry
Settings.public(), which omits the key.
"""
import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "history" / "chat.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    result TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def create_conversation(title="Cuộc trò chuyện mới"):
    cid = uuid.uuid4().hex[:12]
    with closing(_connect()) as conn, conn:
        conn.execute("INSERT INTO conversations VALUES (?, ?, ?, ?)", (cid, title[:80], _now(), _now()))
    return cid


def conversation_exists(cid):
    with closing(_connect()) as conn:
        return conn.execute("SELECT 1 FROM conversations WHERE id = ?", (cid,)).fetchone() is not None


def list_conversations(limit=50):
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT c.id, c.title, c.updated_at, COUNT(m.id) AS n FROM conversations c "
            "LEFT JOIN messages m ON m.conversation_id = c.id GROUP BY c.id ORDER BY c.updated_at DESC LIMIT ?",
            (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_messages(cid):
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT role, content, result, created_at FROM messages WHERE conversation_id = ? "
                            "ORDER BY id", (cid,)).fetchall()
    return [{"role": r["role"], "content": r["content"], "created_at": r["created_at"],
             "result": json.loads(r["result"]) if r["result"] else None} for r in rows]


def add_message(cid, role, content, result=None):
    with closing(_connect()) as conn, conn:
        conn.execute("INSERT INTO messages (conversation_id, role, content, result, created_at) VALUES (?, ?, ?, ?, ?)",
                     (cid, role, content, json.dumps(result, ensure_ascii=False, default=str) if result else None,
                      _now()))
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (_now(), cid))
        # name the conversation after its first question
        if role == "user":
            n = conn.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = ? AND role = 'user'",
                             (cid,)).fetchone()[0]
            if n == 1:
                conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (content.strip()[:80], cid))


def delete_conversation(cid):
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))


def recent_turns(messages, turns=3):
    """The last `turns` question/answer pairs as compact dicts for the pipeline's context:
    [{"role", "content", "product_ids"?}, ...]. Long answers are trimmed."""
    out = []
    for m in [m for m in messages if not m.get("error")][-turns * 2:]:  # skip error notices shown in the UI
        item = {"role": m["role"], "content": m["content"][:1500]}
        if m["role"] == "assistant" and m.get("result"):
            route = m["result"].get("route") or {}
            item["product_ids"] = route.get("product_ids") or []
            if route.get("standalone_question"):
                item["standalone"] = route["standalone_question"]
        out.append(item)
    return out
