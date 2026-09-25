"""
SQLite database management with async support.
Handles schema creation, migrations, and connection pooling.
"""

import aiosqlite
import logging
from pathlib import Path
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


async def get_db() -> aiosqlite.Connection:
    """Get a database connection. Used as a FastAPI dependency."""
    settings = get_settings()
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
    logger.info(f"Initializing database at {settings.DATABASE_PATH}")

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
            "clinical_notes": "TEXT"
        }
        for col, col_type in new_patient_cols.items():
            if col not in patient_cols:
                await db.execute(f"ALTER TABLE patients ADD COLUMN {col} {col_type}")

        cursor = await db.execute("PRAGMA table_info(screening_sessions)")
        session_cols = [row[1] for row in await cursor.fetchall()]
        new_session_cols = {
            "notes": "TEXT",
            "is_deleted": "INTEGER DEFAULT 0"
        }
        for col, col_type in new_session_cols.items():
            if col not in session_cols:
                await db.execute(f"ALTER TABLE screening_sessions ADD COLUMN {col} {col_type}")

        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_is_deleted ON screening_sessions(is_deleted)")
        await db.commit()

    logger.info("Database initialized successfully with migrations applied")


async def seed_demo_user():
    """Create a default demo user if no users exist."""
    import bcrypt

    settings = get_settings()

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
