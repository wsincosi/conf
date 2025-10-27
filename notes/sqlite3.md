Contents

Why SQLite

Installing & Version Checks

Connections & Cursors

Creating Tables & Schema Design

CRUD: Insert, Select, Update, Delete

Parameters: Avoiding SQL Injection

Transactions & Concurrency

Row Factories (Dict-like Access)

Types, Adapters & Converters (incl. datetime)

BLOBs (binary data)

Batch Ops: executemany, executemapping, executescript

Metadata & Introspection

Indexes, Constraints & Foreign Keys

Performance Tuning (PRAGMAs, WAL, query planning)

Migrations & Evolving Schemas

Backups & Restores

Advanced Features: UPSERT, FTS5, JSON1

Threading & Multiprocessing

Testing Patterns

Common Pitfalls & Gotchas

Mini Utility Layer (Optional)

Why SQLite

Zero-config, serverless: a single file on disk (or in memory).

Transactional with ACID guarantees.

Great for CLIs, small services, caches, experiments, local apps, and tests.

Installing & Version Checks

sqlite3 ships with Python’s standard library.

import sqlite3
print(sqlite3.sqlite_version)   # SQLite library version
print(sqlite3.version)          # Python sqlite3 module version


Use a file DB:

conn = sqlite3.connect("app.db")     # creates if not exists


Use an in-memory DB:

conn = sqlite3.connect(":memory:")


Use a URI (e.g., read-only):

conn = sqlite3.connect("file:app.db?mode=ro", uri=True)

Connections & Cursors

Prefer context managers to commit/rollback automatically:

import sqlite3

with sqlite3.connect("app.db") as conn:
    conn.execute("PRAGMA foreign_keys = ON")  # enable FK enforcement
    with conn:  # Transaction scope (commit on success, rollback on error)
        conn.execute("CREATE TABLE IF NOT EXISTS user (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL)")
        conn.execute("INSERT INTO user (email) VALUES (?)", ("a@example.com",))

# Outside the 'with', connection is closed.


Create a cursor when you need fetch* or description:

with sqlite3.connect("app.db") as conn:
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print(cur.fetchone())  # (1,)

Creating Tables & Schema Design
schema = """
CREATE TABLE IF NOT EXISTS user (
  id     INTEGER PRIMARY KEY,                   -- alias for rowid, autoincrements monotonically
  email  TEXT NOT NULL UNIQUE,
  name   TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS post (
  id        INTEGER PRIMARY KEY,
  user_id   INTEGER NOT NULL,
  title     TEXT NOT NULL,
  body      TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);
"""
with sqlite3.connect("app.db") as conn:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema)


Tips

Use INTEGER PRIMARY KEY for the canonical row id.

Add UNIQUE constraints to enforce invariants.

Consider CHECK constraints (e.g., CHECK (length(title) > 0)).

Store timestamps in UTC (TEXT ISO 8601) or use adapters (see below).

CRUD: Insert, Select, Update, Delete
Insert
with sqlite3.connect("app.db") as conn:
    cur = conn.execute("INSERT INTO user (email, name) VALUES (?, ?)", ("a@example.com", "Ada"))
    user_id = cur.lastrowid

Select
with sqlite3.connect("app.db") as conn:
    cur = conn.execute("SELECT id, email, name FROM user WHERE email = ?", ("a@example.com",))
    row = cur.fetchone()
    if row: print(row)  # (1, 'a@example.com', 'Ada')

Update
with sqlite3.connect("app.db") as conn:
    conn.execute("UPDATE user SET name = ? WHERE id = ?", ("Ada Lovelace", 1))

Delete
with sqlite3.connect("app.db") as conn:
    conn.execute("DELETE FROM user WHERE id = ?", (1,))

Iterating Results
with sqlite3.connect("app.db") as conn:
    for row in conn.execute("SELECT id, email FROM user ORDER BY id"):
        print(row)  # tuples by default

Parameters: Avoiding SQL Injection

Always use placeholders; never format SQL with f-strings or %.

# Positional
conn.execute("SELECT * FROM user WHERE email = ?", (email,))

# Named
conn.execute("SELECT * FROM user WHERE email = :email", {"email": email})


Placeholders are always ? in sqlite3 (even for named parameters in the SQL string).

Transactions & Concurrency

By default, sqlite3 opens a transaction implicitly before a DML statement and commits on conn.commit().

Use with conn: to auto-commit/rollback.

Manual control:

conn.isolation_level = None  # autocommit mode
conn.execute("BEGIN IMMEDIATE")  # or BEGIN, or BEGIN EXCLUSIVE
try:
    conn.execute(...)
    conn.execute("COMMIT")
except:
    conn.execute("ROLLBACK")
    raise


Savepoints (nested transactions):

with sqlite3.connect("app.db") as conn:
    conn.execute("SAVEPOINT sp1")
    try:
        conn.execute("INSERT INTO user (email) VALUES (?)", ("b@ex.com",))
        conn.execute("RELEASE sp1")
    except:
        conn.execute("ROLLBACK TO sp1")
        conn.execute("RELEASE sp1")
        raise


SQLite has a single writer at a time. Readers don’t block readers; writers block writers. See WAL mode
 for better concurrency.

Row Factories (Dict-like Access)
import sqlite3
with sqlite3.connect("app.db") as conn:
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT id, email FROM user LIMIT 1")
    row = cur.fetchone()
    print(row["email"])  # dict-style

Types, Adapters & Converters (incl. datetime)

SQLite is dynamically typed; columns have affinity. Python maps:

None → NULL

int → INTEGER

float → REAL

str → TEXT

bytes → BLOB

Datetime via detect_types

Option 1: Store ISO strings, parse in app (simple, portable).

Option 2: Adapters & converters:

import sqlite3, datetime

sqlite3.register_adapter(datetime.datetime, lambda dt: dt.isoformat(" "))
sqlite3.register_converter("timestamp", lambda b: datetime.datetime.fromisoformat(b.decode()))

conn = sqlite3.connect(
    "app.db",
    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
)

with conn:
    conn.execute("CREATE TABLE IF NOT EXISTS event (id INTEGER PRIMARY KEY, at timestamp)")
    now = datetime.datetime.utcnow()
    conn.execute("INSERT INTO event (at) VALUES (?)", (now,))
    row = conn.execute('SELECT at as "at [timestamp]" FROM event').fetchone()
    assert isinstance(row[0], datetime.datetime)

BLOBs (binary data)
data = b"\x00\x01\x02..."
with sqlite3.connect("app.db") as conn:
    conn.execute("CREATE TABLE IF NOT EXISTS blobstore(id INTEGER PRIMARY KEY, payload BLOB)")
    conn.execute("INSERT INTO blobstore (payload) VALUES (?)", (sqlite3.Binary(data),))

    row = conn.execute("SELECT payload FROM blobstore WHERE id = 1").fetchone()
    payload: bytes = row[0]


For large writes/reads, use memoryview slices and stream in chunks.

Batch Ops: executemany, executemapping, executescript
rows = [("a@ex.com",), ("b@ex.com",)]
with sqlite3.connect("app.db") as conn:
    conn.executemany("INSERT INTO user (email) VALUES (?)", rows)

# Python 3.12+: executemany with dicts
rows = [{"email":"c@ex.com"}, {"email":"d@ex.com"}]
conn.executemany("INSERT INTO user (email) VALUES (:email)", rows)

# 3.12+: executescript for multi-statements (DDL, seed data)
conn.executescript("""
BEGIN;
INSERT INTO user(email) VALUES('seed@example.com');
INSERT INTO post(user_id, title, body) VALUES(1, 'Hello', 'World');
COMMIT;
""")

Metadata & Introspection
with sqlite3.connect("app.db") as conn:
    # Table list
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    # Columns
    cols = conn.execute("PRAGMA table_info(user)").fetchall()  # cid,name,type,notnull,dflt_value,pk
    # Foreign keys
    fks = conn.execute("PRAGMA foreign_key_list(post)").fetchall()
    # Indices
    idx = conn.execute("PRAGMA index_list(user)").fetchall()


cursor.description gives selected column names:

cur = conn.execute("SELECT id, email FROM user")
col_names = [d[0] for d in cur.description]

Indexes, Constraints & Foreign Keys
with sqlite3.connect("app.db") as conn:
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_user_email ON user(email)")
    conn.execute("PRAGMA foreign_keys = ON")  # required per-connection


Tip: Composite indexes must match your most frequent WHERE/ORDER BY patterns.

Performance Tuning (PRAGMAs, WAL, query planning)

Enable WAL for better concurrency and fewer writer blocks:

with sqlite3.connect("app.db") as conn:
    conn.execute("PRAGMA journal_mode = WAL")     # persisted in DB
    conn.execute("PRAGMA synchronous = NORMAL")   # durability/speed tradeoff


Other useful PRAGMAs (set thoughtfully):

conn.execute("PRAGMA foreign_keys = ON")
conn.execute("PRAGMA cache_size = -20000")   # ~20k pages in KB if negative (temp for connection)
conn.execute("PRAGMA temp_store = MEMORY")


Measure with EXPLAIN QUERY PLAN:

plan = conn.execute("EXPLAIN QUERY PLAN SELECT * FROM user WHERE email = ?", (email,)).fetchall()
print(plan)


Analyze statistics:

conn.execute("ANALYZE")


Vacuum to rebuild/defragment (blocks database while running):

conn.execute("VACUUM")

Migrations & Evolving Schemas

Pattern: version table + transactional migrations.

with sqlite3.connect("app.db") as conn:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    cur = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
    ver = cur.fetchone()[0]

    if ver < 1:
        with conn:
            conn.executescript("""
            ALTER TABLE user ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;
            """)
            conn.execute("INSERT INTO schema_version(version) VALUES (1)")


Safe ALTERs: SQLite supports a subset (ADD COLUMN, RENAME TO, RENAME COLUMN). For complex changes use table rebuild: create new table, copy data, drop old, rename.

Backups & Restores

Use the Python backup API (safe and online):

with sqlite3.connect("app.db") as src, sqlite3.connect("backup.db") as dst:
    src.backup(dst)  # optionally: pages=0, progress=callback, name='main'


You can also ATTACH and copy between schemas.

Advanced Features: UPSERT, FTS5, JSON1
UPSERT (requires SQLite ≥ 3.24.0)
conn.execute("""
INSERT INTO user (email, name)
VALUES (?, ?)
ON CONFLICT(email) DO UPDATE SET name=excluded.name
""", ("a@example.com", "Ada L."))

Full-Text Search (FTS5)
conn.executescript("""
CREATE VIRTUAL TABLE IF NOT EXISTS post_fts USING fts5(title, body, content='post', content_rowid='id');
-- Populate from existing table
INSERT INTO post_fts(rowid, title, body)
  SELECT id, title, body FROM post;

-- Query
""")
rows = conn.execute("SELECT rowid, snippet(post_fts) FROM post_fts WHERE post_fts MATCH ?", ("hello",)).fetchall()


Keep FTS index in sync via triggers or by writing to both tables.

JSON1
conn.execute("CREATE TABLE IF NOT EXISTS cfg(id INTEGER PRIMARY KEY, doc TEXT NOT NULL)")
conn.execute("INSERT INTO cfg(doc) VALUES (json(?))", ('{"a":1,"b":{"c":2}}',))
val = conn.execute("SELECT json_extract(doc, '$.b.c') FROM cfg").fetchone()[0]  # -> 2

Threading & Multiprocessing

Use one connection per thread. Default check_same_thread=True enforces this.

If you must share a connection across threads, set check_same_thread=False and protect it with your own locks.

conn = sqlite3.connect("app.db", check_same_thread=False)


For multiprocessing, don’t share connections; open fresh connections in each process.

Testing Patterns

Use :memory: for unit tests, or a temp file.

Seed test data with executescript.

For pytest, create a fixture:

import sqlite3, tempfile, os, pytest

@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"

@pytest.fixture
def conn(db_path):
    c = sqlite3.connect(db_path)
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()

Common Pitfalls & Gotchas

Forgetting PRAGMA foreign_keys = ON: FKs aren’t enforced unless you enable it per connection.

String SQL with f-strings: Use parameters; never interpolate values.

Assuming strict types: SQLite is flexible; add CHECKs for invariants.

Long-running transactions: They block writers. Keep transactions short.

Not using WAL for concurrency: Switch to WAL for write-heavy workloads.

Relying on implicit commits: Prefer with conn: scopes for clarity and safety.

Mini Utility Layer (Optional)

A tiny helper to keep code DRY.

# db.py
from contextlib import contextmanager
import sqlite3
from typing import Iterable, Mapping, Any, Sequence, Optional

def connect(path: str = "app.db") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        conn.execute("BEGIN")
        yield
        conn.execute("COMMIT")
    except:
        conn.execute("ROLLBACK")
        raise

def query(conn: sqlite3.Connection, sql: str, params: Sequence[Any] | Mapping[str, Any] = ()):
    return conn.execute(sql, params).fetchall()

def execute(conn: sqlite3.Connection, sql: str, params: Sequence[Any] | Mapping[str, Any] = ()):
    cur = conn.execute(sql, params)
    return cur.lastrowid, cur.rowcount

def executemany(conn: sqlite3.Connection, sql: str, rows: Iterable[Sequence[Any] | Mapping[str, Any]]):
    conn.executemany(sql, rows)


Usage:

from db import connect, transaction, query, execute

conn = connect()
with transaction(conn):
    execute(conn, "INSERT INTO user(email,name) VALUES(?,?)", ("new@ex.com","New"))
users = query(conn, "SELECT id,email FROM user ORDER BY id")
for u in users:
    print(dict(u))
conn.close()

Appendix: Handy Snippets

URI with WAL and busy timeout

conn = sqlite3.connect(
    "file:app.db?cache=shared",
    uri=True,
    timeout=10.0,  # wait up to 10s for locks
)
conn.execute("PRAGMA journal_mode = WAL")


ATTACH another database

conn.execute("ATTACH DATABASE 'analytics.db' AS analytics")
rows = conn.execute("SELECT * FROM main.user u JOIN analytics.events e ON e.user_id = u.id").fetchall()
conn.execute("DETACH DATABASE analytics")


Upgrading safely with table rebuild

conn.executescript("""
BEGIN;
CREATE TABLE user_new(
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  name TEXT,
  is_active INTEGER NOT NULL DEFAULT 1
);
INSERT INTO user_new(id,email,name,is_active)
  SELECT id,email,name,1 FROM user;
DROP TABLE user;
ALTER TABLE user_new RENAME TO user;
COMMIT;
""")
