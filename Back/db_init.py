# db_init.py
# -*- coding: utf-8 -*-
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "quiz.db")

schema = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    uniandes_code TEXT NOT NULL,
    magistral TEXT NOT NULL,
    complementarios TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    success INTEGER NOT NULL,
    ts TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id);
"""

if __name__ == "__main__":
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript(schema)
    con.commit()
    con.close()
    print("DB inicializada en", DB_PATH)
