"""
users_db.py — tiny, readable SQLite wrapper for a Users table,
with hardened writes: DB file is read-only by default; write ops
temporarily make it writable and then force it back to 0444.

Schema:
  users(username TEXT PRIMARY KEY,
        address  TEXT NOT NULL,
        date_of_birth TEXT NOT NULL)
"""

from __future__ import annotations

import functools
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Optional

# ---------- Decorators ----------


def temporary_write_access(fn):
    """
    Temporarily make the SQLite file writable (0644) while executing `fn`,
    then ALWAYS set it to read-only (0444) afterward.
    """

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        db_file = Path(self.db_path)

        # Try to enable writes before the operation (file may not exist yet).
        try:
            os.chmod(db_file, 0o644)
        except FileNotFoundError:
            # First-time create: SQLite will create the file; we'll chmod after.
            pass
        except PermissionError:
            # If we lack permission to flip bits, still attempt the DB op;
            # cleanup will try to enforce 0444 afterward.
            pass

        try:
            return fn(self, *args, **kwargs)
        finally:
            # Force read-only regardless of the initial state.
            try:
                if db_file.exists():
                    os.chmod(db_file, 0o444)
            except Exception:
                # Never raise from cleanup; at worst the file remains writable.
                pass

    return wrapper


def write_op(fn):
    """
    Mutating DB operation:
      - grants temporary file write access
      - disables PRAGMA query_only for the duration
      - commits on success
      - re-enables query_only afterward
    """

    @functools.wraps(fn)
    @temporary_write_access
    def wrapper(self, *args, **kwargs):
        self.conn.execute("PRAGMA query_only = OFF;")
        try:
            result = fn(self, *args, **kwargs)
            self.conn.commit()
            return result
        finally:
            self.conn.execute("PRAGMA query_only = ON;")

    return wrapper


# ---------- Data model ----------


@dataclass(frozen=True, slots=True)
class User:
    username: str
    address: str
    date_of_birth: date

    @staticmethod
    def _parse_date(d: date | str) -> date:
        if isinstance(d, date):
            return d
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("date_of_birth must be YYYY-MM-DD") from exc

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "User":
        return cls(
            username=row["username"],
            address=row["address"],
            date_of_birth=cls._parse_date(row["date_of_birth"]),
        )

    def as_db_tuple(self) -> tuple[str, str, str]:
        return (self.username, self.address, self.date_of_birth.isoformat())


# ---------- Database wrapper ----------


class UsersDB:
    """
    Simple SQLite wrapper for a 'users' table.
    Default connection runs with PRAGMA query_only=ON (read-only).
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> "UsersDB":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # --- connection management ---

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        assert self._conn is not None  # ensures type is narrowed for type checkers
        return self._conn

    def connect(self) -> None:
        if self._conn:
            return
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA query_only = ON;")  # default to read-only

    def close(self) -> None:
        if self._conn:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    # --- schema ---

    @write_op
    def create_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                address  TEXT NOT NULL,
                date_of_birth TEXT NOT NULL
            );
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_address ON users(address);"
        )

    # --- CRUD ---

    @write_op
    def add(self, user: User) -> None:
        self.conn.execute(
            "INSERT INTO users(username, address, date_of_birth) VALUES (?, ?, ?)",
            user.as_db_tuple(),
        )

    def get(self, username: str) -> Optional[User]:
        cur = self.conn.execute(
            "SELECT username, address, date_of_birth FROM users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        return User.from_row(row) if row else None

    @write_op
    def update(
        self,
        username: str,
        *,
        address: Optional[str] = None,
        date_of_birth: Optional[date | str] = None,
    ) -> bool:
        sets, params = [], []
        if address is not None:
            address = address.strip()
            if not address:
                raise ValueError("address cannot be empty")
            sets.append("address = ?")
            params.append(address)
        if date_of_birth is not None:
            dob = User._parse_date(date_of_birth).isoformat()
            sets.append("date_of_birth = ?")
            params.append(dob)
        if not sets:
            return False
        params.append(username)
        cur = self.conn.execute(
            f"UPDATE users SET {', '.join(sets)} WHERE username = ?",
            tuple(params),
        )
        return cur.rowcount > 0

    @write_op
    def delete(self, username: str) -> bool:
        cur = self.conn.execute("DELETE FROM users WHERE username = ?", (username,))
        return cur.rowcount > 0

    # --- read-only queries ---

    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "username",
        desc: bool = False,
    ) -> Iterator[User]:
        allowed = {"username", "address", "date_of_birth"}
        if order_by not in allowed:
            raise ValueError(f"order_by must be one of {sorted(allowed)}")
        order_clause = f"{order_by} {'DESC' if desc else 'ASC'}"
        cur = self.conn.execute(
            f"""
            SELECT username, address, date_of_birth
            FROM users
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        for row in cur:
            yield User.from_row(row)

    def search_address(
        self, substring: str, *, limit: int = 100, offset: int = 0
    ) -> Iterator[User]:
        q = f"%{substring.strip()}%"
        cur = self.conn.execute(
            """
            SELECT username, address, date_of_birth
            FROM users
            WHERE lower(address) LIKE lower(?)
            ORDER BY username ASC
            LIMIT ? OFFSET ?
            """,
            (q, limit, offset),
        )
        for row in cur:
            yield User.from_row(row)


# ---------- Optional CLI demo ----------

if __name__ == "__main__":
    import argparse
    from datetime import date as _date

    parser = argparse.ArgumentParser(
        description="Users DB demo (force 0444 after writes)"
    )
    parser.add_argument("--db", default="users.sqlite", help="Path to SQLite file")
    args = parser.parse_args()

    with UsersDB(args.db) as db:
        db.create_schema()

        # Start locked down (0444). If it fails, that's OK.
        try:
            os.chmod(args.db, 0o444)
        except Exception:
            pass

        if not any(db.list(limit=1)):
            db.add(User("alice", "123 Paper St", _date(1990, 1, 2)))
            db.add(User("bob", "456 Elm Ave", _date(1985, 7, 14)))
        else:
            db.update("alice", address="789 Oak Blvd")

        print("All users:")
        for u in db.list():
            print(" -", u)

        print("Search 'Elm':")
        for u in db.search_address("Elm"):
            print(" -", u)
