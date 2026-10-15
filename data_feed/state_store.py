"""Atomic decision state and append-only audit events; never store credentials here."""
import json
from contextlib import contextmanager
import sqlite3
from pathlib import Path


class StateStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS engine_state (
                    symbol TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, symbol TEXT NOT NULL,
                    time REAL NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def process(self, symbol, callback):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT value FROM engine_state WHERE symbol=?", (symbol,)).fetchone()
            state = json.loads(row[0]) if row else {}
            updated, result, events = callback(state)
            connection.execute(
                "INSERT INTO engine_state VALUES (?,?) ON CONFLICT(symbol) "
                "DO UPDATE SET value=excluded.value",
                (symbol, json.dumps(updated, allow_nan=False)))
            for event in events:
                connection.execute(
                    "INSERT INTO events(symbol,time,kind,value) VALUES (?,?,?,?)",
                    (symbol, event["time"], event["kind"], json.dumps(event, allow_nan=False)))
            return result
