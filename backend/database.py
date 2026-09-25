"""
SQLite database management with async support.
Handles schema creation, migrations, and connection pooling.
"""

import asyncio
import json
import logging
import urllib.request
from pathlib import Path
import aiosqlite
from config import get_settings

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'technician',
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

-- Patients table
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT UNIQUE NOT NULL,
    infant_name TEXT,
    gender TEXT,
    mother_name TEXT,
    father_name TEXT,
    date_of_birth TEXT,
    gestational_age_weeks INTEGER,
    gestational_age_days INTEGER,
    birth_weight_grams INTEGER,
    postnatal_age_days INTEGER,
    clinical_history TEXT,
    clinical_notes TEXT,
    hospital_name TEXT,
    city_town_village TEXT,
    contact_number TEXT,
    healthcare_worker_name TEXT,
    healthcare_worker_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);

-- Screening sessions
CREATE TABLE IF NOT EXISTS screening_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    patient_id TEXT NOT NULL,
    screening_date TEXT NOT NULL,
    status TEXT DEFAULT 'created',
    notes TEXT,
    is_deleted INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- Screening images
CREATE TABLE IF NOT EXISTS screening_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id TEXT UNIQUE NOT NULL,
    session_id TEXT NOT NULL,
    eye_label TEXT DEFAULT 'unspecified',
    original_filename TEXT,
    stored_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size_bytes INTEGER,
    mime_type TEXT,
    quality_status TEXT DEFAULT 'pending',
    quality_score REAL,
    quality_details TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES screening_sessions(session_id)
);

-- Screening results
CREATE TABLE IF NOT EXISTS screening_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id TEXT UNIQUE NOT NULL,
    session_id TEXT NOT NULL,
    image_id TEXT NOT NULL,
    classification TEXT,
    confidence REAL,
    probabilities TEXT,
    is_demo INTEGER DEFAULT 0,
    model_name TEXT,
    model_version TEXT,
    status TEXT DEFAULT 'pending',
    heatmap_path TEXT,
    overlay_path TEXT,
    recommendation TEXT,
    recommendation_urgency TEXT,
    screening_limitations TEXT,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES screening_sessions(session_id),
    FOREIGN KEY (image_id) REFERENCES screening_images(image_id)
);

-- Generated reports
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT UNIQUE NOT NULL,
    session_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    language TEXT DEFAULT 'en',
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES screening_sessions(session_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_patients_patient_id ON patients(patient_id);
CREATE INDEX IF NOT EXISTS idx_patients_is_deleted ON patients(is_deleted);
CREATE INDEX IF NOT EXISTS idx_sessions_patient_id ON screening_sessions(patient_id);
CREATE INDEX IF NOT EXISTS idx_sessions_screening_date ON screening_sessions(screening_date);
CREATE INDEX IF NOT EXISTS idx_images_session_id ON screening_images(session_id);
CREATE INDEX IF NOT EXISTS idx_results_session_id ON screening_results(session_id);
CREATE INDEX IF NOT EXISTS idx_reports_session_id ON reports(session_id);
"""


class TursoRow(dict):
    """Row object that supports both dict indexing (row['name']) and integer indexing (row[0])."""
    def __init__(self, mapping, values):
        super().__init__(mapping)
        self._values = values

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)

    def get(self, key, default=None):
        if isinstance(key, int):
            return self._values[key] if key < len(self._values) else default
        return super().get(key, default)

    def keys(self):
        return super().keys()


class TursoCursor:
    """Cursor compatible with aiosqlite Cursor interface."""
    def __init__(self, result_dict):
        self._result = result_dict or {}
        cols_meta = self._result.get("cols", [])
        self.columns = [c.get("name") for c in cols_meta]
        self._rows = []
        for raw_row in self._result.get("rows", []):
            vals = []
            for col in raw_row:
                if col.get("type") == "null":
                    vals.append(None)
                elif col.get("type") == "integer":
                    vals.append(int(col.get("value", 0)))
                elif col.get("type") == "float":
                    vals.append(float(col.get("value", 0.0)))
                else:
                    vals.append(col.get("value"))
            mapping = dict(zip(self.columns, vals))
            self._rows.append(TursoRow(mapping, vals))

        self._idx = 0
        self.lastrowid = self._result.get("last_insert_rowid")
        self.rowcount = self._result.get("affected_row_count", 0)

    async def fetchone(self):
        if self._idx < len(self._rows):
            row = self._rows[self._idx]
            self._idx += 1
            return row
        return None

    async def fetchall(self):
        return self._rows


class TursoConnection:
    """Async connection wrapper for Turso HTTP Pipeline API."""
    def __init__(self, pipeline_url: str, token: str):
        self.pipeline_url = pipeline_url
        self.token = token

    def _to_turso_arg(self, val):
        if val is None:
            return {"type": "null"}
        elif isinstance(val, int):
            return {"type": "integer", "value": str(val)}
        elif isinstance(val, float):
            return {"type": "float", "value": val}
        elif isinstance(val, (bytes, bytearray)):
            import base64
            return {"type": "blob", "base64": base64.b64encode(val).decode()}
        else:
            return {"type": "text", "value": str(val)}

    def _sync_execute(self, sql: str, parameters=None):
        args = [self._to_turso_arg(p) for p in (parameters or [])]
        req_body = {"requests": [{"type": "execute", "stmt": {"sql": sql, "args": args}}]}
        req = urllib.request.Request(
            self.pipeline_url,
            data=json.dumps(req_body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            if results and results[0].get("type") == "error":
                raise RuntimeError(f"Turso Error: {results[0].get('error')}")
            return results[0].get("response", {}).get("result", {})

    async def execute(self, sql: str, parameters=None):
        res = await asyncio.to_thread(self._sync_execute, sql, parameters)
        return TursoCursor(res)

    async def executescript(self, script: str):
        for stmt in script.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await self.execute(stmt + ";")

    async def commit(self):
        pass  # Auto-committed in HTTP pipeline

    async def rollback(self):
        pass

    async def close(self):
        pass


def _get_turso_pipeline_url(database_url: str) -> str:
    url = database_url.replace("libsql://", "https://")
    if not url.startswith("http"):
        url = f"https://{url}"
    return f"{url.rstrip('/')}/v2/pipeline"


async def get_db():
    """Get a database connection (Turso cloud or local SQLite). Used as a FastAPI dependency."""
    settings = get_settings()

    if settings.is_turso_enabled:
        pipeline_url = _get_turso_pipeline_url(settings.TURSO_DATABASE_URL)
        yield TursoConnection(pipeline_url, settings.TURSO_AUTH_TOKEN)
    else:
        db = await aiosqlite.connect(settings.DATABASE_PATH)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            await db.close()


async def init_database():
    """Initialize the database with schema and run migrations."""
    settings = get_settings()

    if settings.is_turso_enabled:
        pipeline_url = _get_turso_pipeline_url(settings.TURSO_DATABASE_URL)
        logger.info(f"Initializing Turso Cloud database at {pipeline_url}")
        turso = TursoConnection(pipeline_url, settings.TURSO_AUTH_TOKEN)
        await turso.executescript(SCHEMA_SQL)
        logger.info("Turso Cloud database schema verified successfully")
    else:
        logger.info(f"Initializing SQLite database at {settings.DATABASE_PATH}")
        db_path = Path(settings.DATABASE_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(settings.DATABASE_PATH) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.executescript(SCHEMA_SQL)

            # Migration: ensure newly added columns exist in older SQLite files
            cursor = await db.execute("PRAGMA table_info(patients)")
            patient_cols = [row[1] for row in await cursor.fetchall()]

            new_patient_cols = {
                "gender": "TEXT",
                "mother_name": "TEXT",
                "father_name": "TEXT",
                "city_town_village": "TEXT",
                "contact_number": "TEXT",
                "clinical_notes": "TEXT",
            }
            for col, col_type in new_patient_cols.items():
                if col not in patient_cols:
                    await db.execute(f"ALTER TABLE patients ADD COLUMN {col} {col_type}")

            cursor = await db.execute("PRAGMA table_info(screening_sessions)")
            session_cols = [row[1] for row in await cursor.fetchall()]
            new_session_cols = {
                "notes": "TEXT",
                "is_deleted": "INTEGER DEFAULT 0",
            }
            for col, col_type in new_session_cols.items():
                if col not in session_cols:
                    await db.execute(f"ALTER TABLE screening_sessions ADD COLUMN {col} {col_type}")

            await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_is_deleted ON screening_sessions(is_deleted)")
            await db.commit()

        logger.info("Local SQLite database initialized successfully with migrations applied")


async def seed_demo_user():
    """Create a default demo user if no users exist."""
    import bcrypt

    settings = get_settings()

    if settings.is_turso_enabled:
        pipeline_url = _get_turso_pipeline_url(settings.TURSO_DATABASE_URL)
        turso = TursoConnection(pipeline_url, settings.TURSO_AUTH_TOKEN)
        cursor = await turso.execute("SELECT COUNT(*) as cnt FROM users")
        row = await cursor.fetchone()
        if row and row["cnt"] == 0:
            password_hash = bcrypt.hashpw("rop2024".encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")
            await turso.execute(
                """INSERT INTO users (username, full_name, role, password_hash)
                   VALUES (?, ?, ?, ?)""",
                ("admin", "Dr. Demo User", "doctor", password_hash),
            )
            logger.info("Demo user verified on Turso: username='admin', password='rop2024'")
    else:
        async with aiosqlite.connect(settings.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT COUNT(*) as cnt FROM users")
            row = await cursor.fetchone()

            if row["cnt"] == 0:
                password_hash = bcrypt.hashpw("rop2024".encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")
                await db.execute(
                    """INSERT INTO users (username, full_name, role, password_hash)
                       VALUES (?, ?, ?, ?)""",
                    ("admin", "Dr. Demo User", "doctor", password_hash),
                )
                await db.commit()
                logger.info("Demo user created: username='admin', password='rop2024'")
