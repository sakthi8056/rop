"""
Migration script: Migrate local SQLite data into Turso (libSQL) cloud database.
"""

import sqlite3
import json
import urllib.request
import logging
from pathlib import Path
from config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'technician',
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

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

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT UNIQUE NOT NULL,
    session_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    language TEXT DEFAULT 'en',
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES screening_sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_patients_patient_id ON patients(patient_id);
CREATE INDEX IF NOT EXISTS idx_patients_is_deleted ON patients(is_deleted);
CREATE INDEX IF NOT EXISTS idx_sessions_patient_id ON screening_sessions(patient_id);
CREATE INDEX IF NOT EXISTS idx_sessions_screening_date ON screening_sessions(screening_date);
CREATE INDEX IF NOT EXISTS idx_sessions_is_deleted ON screening_sessions(is_deleted);
CREATE INDEX IF NOT EXISTS idx_images_session_id ON screening_images(session_id);
CREATE INDEX IF NOT EXISTS idx_results_session_id ON screening_results(session_id);
CREATE INDEX IF NOT EXISTS idx_reports_session_id ON reports(session_id);
"""


def execute_turso_pipeline(pipeline_url: str, token: str, statements: list[dict]):
    """Execute a batch of statements using Turso HTTP pipeline API."""
    requests = []
    for stmt in statements:
        requests.append({"type": "execute", "stmt": stmt})

    payload = {"requests": requests}
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        pipeline_url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))
        for item in resp_data.get("results", []):
            if item.get("type") == "error":
                raise RuntimeError(f"Turso Error: {item.get('error')}")
        return resp_data


def to_turso_arg(val):
    """Convert python value to Turso argument format."""
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


def main():
    settings = get_settings()
    if not settings.is_turso_enabled:
        logger.error("TURSO_DATABASE_URL or TURSO_AUTH_TOKEN is not configured in .env")
        return

    # Convert libsql:// to https://
    turso_url = settings.TURSO_DATABASE_URL.replace("libsql://", "https://")
    if not turso_url.startswith("http"):
        turso_url = f"https://{turso_url}"
    pipeline_url = f"{turso_url.rstrip('/')}/v2/pipeline"

    logger.info(f"Target Turso Database: {pipeline_url}")

    # 1. Initialize Schema on Turso
    logger.info("Step 1: Initializing Schema on Turso...")
    schema_stmts = [
        {"sql": stmt.strip() + ";"}
        for stmt in SCHEMA_SQL.strip().split(";")
        if stmt.strip()
    ]
    execute_turso_pipeline(pipeline_url, settings.TURSO_AUTH_TOKEN, schema_stmts)
    logger.info("Schema and indexes successfully initialized on Turso!")

    # 2. Read from local SQLite
    db_file = Path(settings.DATABASE_PATH)
    if not db_file.exists():
        logger.error(f"Local database file {db_file} not found!")
        return

    local_conn = sqlite3.connect(str(db_file))
    local_cur = local_conn.cursor()

    tables = ["users", "patients", "screening_sessions", "screening_images", "screening_results", "reports"]

    # 3. Migrate each table
    logger.info("Step 2: Migrating data table by table...")
    for table in tables:
        local_cur.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in local_cur.fetchall()]
        col_list_str = ", ".join(columns)
        placeholders = ", ".join(["?"] * len(columns))

        local_cur.execute(f"SELECT {col_list_str} FROM {table}")
        rows = local_cur.fetchall()

        logger.info(f"Migrating {table}: {len(rows)} rows...")

        if not rows:
            continue

        # Clean existing rows in Turso before seeding to prevent PK conflicts
        execute_turso_pipeline(pipeline_url, settings.TURSO_AUTH_TOKEN, [{"sql": f"DELETE FROM {table};"}])

        batch_size = 50
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            batch_stmts = []
            for row in batch:
                args = [to_turso_arg(val) for val in row]
                batch_stmts.append({
                    "sql": f"INSERT OR REPLACE INTO {table} ({col_list_str}) VALUES ({placeholders});",
                    "args": args
                })
            execute_turso_pipeline(pipeline_url, settings.TURSO_AUTH_TOKEN, batch_stmts)

        logger.info(f"Successfully migrated {len(rows)} rows to {table}!")

    local_conn.close()

    # 4. Verification on Turso
    logger.info("Step 3: Verifying row counts on Turso online database...")
    verify_stmts = [{"sql": f"SELECT COUNT(*) as cnt FROM {t};"} for t in tables]
    resp = execute_turso_pipeline(pipeline_url, settings.TURSO_AUTH_TOKEN, verify_stmts)

    print("\n==========================================")
    print(" TURSO CLOUD DATABASE MIGRATION VERIFICATION")
    print("==========================================")
    for idx, table in enumerate(tables):
        res = resp["results"][idx]["response"]["result"]
        count = res["rows"][0][0]["value"]
        print(f"  [✓] {table:20s}: {count} rows")
    print("==========================================")
    print("MIGRATION COMPLETED SUCCESSFULLY!\n")


if __name__ == "__main__":
    main()
