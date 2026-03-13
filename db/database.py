"""SQLite database layer for application storage and analytics.

Implements: FR-004 (SQLite database), FR-005 (application storage),
            FR-006 (analytics queries), FR-110 (resume version storage).
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from db.models import Application, FeedEvent

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    job_title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    salary TEXT,
    apply_url TEXT NOT NULL,
    match_score INTEGER NOT NULL,
    resume_path TEXT,
    cover_letter_path TEXT,
    cover_letter_text TEXT,
    description_path TEXT,
    status TEXT NOT NULL DEFAULT 'applied',
    error_message TEXT,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dedup ON applications(external_id, platform);
CREATE INDEX IF NOT EXISTS idx_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applied_at ON applications(applied_at);

CREATE TABLE IF NOT EXISTS feed_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    job_title TEXT,
    company TEXT,
    platform TEXT,
    message TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resume_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    job_title TEXT NOT NULL,
    company TEXT NOT NULL,
    resume_md_path TEXT NOT NULL,
    resume_pdf_path TEXT NOT NULL,
    match_score INTEGER,
    llm_provider TEXT,
    llm_model TEXT,
    is_favorite INTEGER NOT NULL DEFAULT 0,
    reuse_source TEXT,
    source_entry_ids TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rv_app_id ON resume_versions(application_id);
CREATE INDEX IF NOT EXISTS idx_rv_created_at ON resume_versions(created_at);

CREATE TABLE IF NOT EXISTS uploaded_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    raw_text TEXT,
    llm_provider TEXT,
    llm_model TEXT,
    processed_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    text TEXT NOT NULL,
    subsection TEXT,
    role_id INTEGER REFERENCES roles(id),
    job_types TEXT,
    tags TEXT,
    source_doc_id INTEGER REFERENCES uploaded_documents(id),
    embedding BLOB,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_kb_dedup ON knowledge_base(category, text);
CREATE INDEX IF NOT EXISTS idx_kb_category ON knowledge_base(category);
CREATE INDEX IF NOT EXISTS idx_kb_active ON knowledge_base(is_active);

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    location TEXT,
    domain TEXT,
    source_doc_id INTEGER REFERENCES uploaded_documents(id),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(title, company, start_date)
);

CREATE TABLE IF NOT EXISTS resume_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    entry_ids TEXT NOT NULL,
    template TEXT NOT NULL DEFAULT 'classic',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS kb_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL REFERENCES knowledge_base(id),
    application_id INTEGER REFERENCES applications(id),
    tfidf_score REAL,
    outcome TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ulog_entry ON kb_usage_log(entry_id);
CREATE INDEX IF NOT EXISTS idx_ulog_app ON kb_usage_log(application_id);

CREATE TABLE IF NOT EXISTS custom_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    tex_content TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS portal_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    portal_type TEXT NOT NULL,
    username TEXT NOT NULL,
    password_hash TEXT,
    has_keyring_password INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    last_login_at DATETIME,
    login_success_count INTEGER NOT NULL DEFAULT 0,
    login_failure_count INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_pc_domain ON portal_credentials(domain);
"""


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def close(self) -> None:
        """Close database resources. No-op for per-operation connections."""
        pass

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate(conn)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Apply incremental schema migrations for existing databases."""
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(applications)").fetchall()
        }
        if "description_path" not in columns:
            conn.execute("ALTER TABLE applications ADD COLUMN description_path TEXT")

        # M1: Add reuse columns to resume_versions for existing DBs
        rv_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(resume_versions)").fetchall()
        }
        if "reuse_source" not in rv_columns:
            conn.execute("ALTER TABLE resume_versions ADD COLUMN reuse_source TEXT")
        if "source_entry_ids" not in rv_columns:
            conn.execute("ALTER TABLE resume_versions ADD COLUMN source_entry_ids TEXT")

        # M9: Add effectiveness tracking columns to knowledge_base
        kb_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(knowledge_base)").fetchall()
        }
        if "effectiveness_score" not in kb_columns:
            conn.execute(
                "ALTER TABLE knowledge_base ADD COLUMN effectiveness_score REAL DEFAULT 0.0"
            )
        if "usage_count" not in kb_columns:
            conn.execute(
                "ALTER TABLE knowledge_base ADD COLUMN usage_count INTEGER DEFAULT 0"
            )
        if "last_used_at" not in kb_columns:
            conn.execute(
                "ALTER TABLE knowledge_base ADD COLUMN last_used_at DATETIME"
            )
        if "role_id" not in kb_columns:
            conn.execute(
                "ALTER TABLE knowledge_base ADD COLUMN role_id INTEGER REFERENCES roles(id)"
            )

        # Add location to roles for existing DBs
        role_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(roles)").fetchall()
        }
        if "location" not in role_columns:
            conn.execute(
                "ALTER TABLE roles ADD COLUMN location TEXT"
            )

    def save_application(
        self,
        external_id: str,
        platform: str,
        job_title: str,
        company: str,
        location: str | None,
        salary: str | None,
        apply_url: str,
        match_score: int,
        resume_path: str | None,
        cover_letter_path: str | None,
        cover_letter_text: str | None,
        status: str,
        error_message: str | None,
        description_path: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO applications (
                    external_id, platform, job_title, company, location, salary,
                    apply_url, match_score, resume_path, cover_letter_path,
                    cover_letter_text, description_path, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    external_id, platform, job_title, company, location, salary,
                    apply_url, match_score, resume_path, cover_letter_path,
                    cover_letter_text, description_path, status, error_message,
                ),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def update_status(self, application_id: int, status: str, notes: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE applications
                SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, notes, application_id),
            )

    def get_all_applications(
        self,
        status: str | None = None,
        platform: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Application]:
        query = "SELECT * FROM applications WHERE 1=1"
        params: list = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if search:
            query += " AND (job_title LIKE ? OR company LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY applied_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [Application(**dict(row)) for row in rows]

    def get_application(self, application_id: int) -> Application | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM applications WHERE id = ?", (application_id,)
            ).fetchone()
            if row is None:
                return None
            return Application(**dict(row))

    def exists(self, external_id: str, platform: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM applications WHERE external_id = ? AND platform = ?",
                (external_id, platform),
            ).fetchone()
            return row is not None

    def export_csv(self, path: Path) -> None:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM applications ORDER BY applied_at DESC").fetchall()
            if not rows:
                return
            headers = rows[0].keys()
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for row in rows:
                    writer.writerow(tuple(row))

    def save_feed_event(
        self,
        event_type: str,
        job_title: str | None = None,
        company: str | None = None,
        platform: str | None = None,
        message: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO feed_events (event_type, job_title, company, platform, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_type, job_title, company, platform, message),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def get_feed_events_for_job(
        self, job_title: str, company: str, limit: int = 50,
    ) -> list[FeedEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM feed_events WHERE job_title = ? AND company = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (job_title, company, limit),
            ).fetchall()
            return [FeedEvent(**dict(row)) for row in rows]

    def get_feed_events(self, limit: int = 100) -> list[FeedEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM feed_events ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [FeedEvent(**dict(row)) for row in rows]

    # ------------------------------------------------------------------
    # Resume versions (FR-110, FR-111, FR-112, FR-114)
    # ------------------------------------------------------------------

    def save_resume_version(
        self,
        application_id: int,
        job_title: str,
        company: str,
        resume_md_path: str,
        resume_pdf_path: str,
        match_score: int | None,
        llm_provider: str | None,
        llm_model: str | None,
        reuse_source: str | None = None,
        source_entry_ids: str | None = None,
    ) -> int:
        """Insert a resume version record. Returns the new id."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO resume_versions (
                    application_id, job_title, company,
                    resume_md_path, resume_pdf_path,
                    match_score, llm_provider, llm_model,
                    reuse_source, source_entry_ids
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id, job_title, company,
                    resume_md_path, resume_pdf_path,
                    match_score, llm_provider, llm_model,
                    reuse_source, source_entry_ids,
                ),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def get_resume_versions(
        self,
        page: int = 1,
        per_page: int = 50,
        search: str | None = None,
        sort: str = "created_at",
        order: str = "desc",
    ) -> tuple[list[dict], int]:
        """Return paginated resume versions joined with application status."""
        allowed_sort = {"created_at", "company", "job_title", "match_score", "is_favorite"}
        if sort not in allowed_sort:
            sort = "created_at"
        if order not in ("asc", "desc"):
            order = "desc"
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 50

        base = """
            FROM resume_versions rv
            LEFT JOIN applications a ON rv.application_id = a.id
        """
        params: list = []
        if search:
            base += " WHERE (rv.company LIKE ? OR rv.job_title LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        with self._connect() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) {base}", params
            ).fetchone()[0]

            rows = conn.execute(
                f"""
                SELECT rv.*, a.status AS application_status
                {base}
                ORDER BY rv.{sort} {order}
                LIMIT ? OFFSET ?
                """,
                params + [per_page, (page - 1) * per_page],
            ).fetchall()

            items = []
            for row in rows:
                d = dict(row)
                d["resume_pdf_exists"] = Path(
                    d.get("resume_pdf_path", "")
                ).exists()
                items.append(d)

            return items, total

    def get_resume_version(self, version_id: int) -> dict | None:
        """Return a single resume version with application status, or None."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT rv.*, a.status AS application_status
                FROM resume_versions rv
                LEFT JOIN applications a ON rv.application_id = a.id
                WHERE rv.id = ?
                """,
                (version_id,),
            ).fetchone()
            if row is None:
                return None
            d = dict(row)
            d["resume_pdf_exists"] = Path(
                d.get("resume_pdf_path", "")
            ).exists()
            return d

    def toggle_favorite(self, version_id: int) -> bool | None:
        """Toggle is_favorite for a resume version. Returns new value, or None if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT is_favorite FROM resume_versions WHERE id = ?",
                (version_id,),
            ).fetchone()
            if row is None:
                return None
            new_val = 0 if row["is_favorite"] else 1
            conn.execute(
                "UPDATE resume_versions SET is_favorite = ? WHERE id = ?",
                (new_val, version_id),
            )
            return bool(new_val)

    def get_resume_metrics(self) -> dict:
        """Compute aggregate resume effectiveness metrics (FR-114)."""
        interview_statuses = (
            "interview", "interviewing", "interviewed", "offer", "accepted"
        )
        placeholders = ",".join("?" for _ in interview_statuses)

        with self._connect() as conn:
            # Total versions
            total = conn.execute(
                "SELECT COUNT(*) FROM resume_versions"
            ).fetchone()[0]

            # Tailored interview rate
            tailored_row = conn.execute(
                f"""
                SELECT COUNT(*) AS total,
                    SUM(CASE WHEN a.status IN ({placeholders})
                        THEN 1 ELSE 0 END) AS positive
                FROM resume_versions rv
                JOIN applications a ON rv.application_id = a.id
                """,
                interview_statuses,
            ).fetchone()
            tailored_total = tailored_row["total"]
            tailored_positive = tailored_row["positive"] or 0
            tailored_rate = (
                round(tailored_positive * 100.0 / tailored_total, 1)
                if tailored_total > 0 else 0.0
            )

            # Fallback rate (apps with resume_path but no resume_version)
            fallback_row = conn.execute(
                f"""
                SELECT COUNT(*) AS total,
                    SUM(CASE WHEN a.status IN ({placeholders})
                        THEN 1 ELSE 0 END) AS positive
                FROM applications a
                LEFT JOIN resume_versions rv ON a.id = rv.application_id
                WHERE rv.id IS NULL AND a.resume_path IS NOT NULL
                """,
                interview_statuses,
            ).fetchone()
            fallback_total = fallback_row["total"]
            fallback_positive = fallback_row["positive"] or 0
            fallback_rate = (
                round(fallback_positive * 100.0 / fallback_total, 1)
                if fallback_total > 0 else 0.0
            )

            # Avg scores
            score_row = conn.execute(
                f"""
                SELECT
                    AVG(CASE WHEN a.status IN ({placeholders})
                        THEN rv.match_score END) AS avg_interviewed,
                    AVG(CASE WHEN a.status = 'rejected'
                        THEN rv.match_score END) AS avg_rejected
                FROM resume_versions rv
                JOIN applications a ON rv.application_id = a.id
                """,
                interview_statuses,
            ).fetchone()

            # By provider
            provider_rows = conn.execute(
                f"""
                SELECT rv.llm_provider AS provider,
                    COUNT(*) AS count,
                    SUM(CASE WHEN a.status IN ({placeholders})
                        THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS interview_rate
                FROM resume_versions rv
                JOIN applications a ON rv.application_id = a.id
                WHERE rv.llm_provider IS NOT NULL
                GROUP BY rv.llm_provider
                """,
                interview_statuses,
            ).fetchall()

            return {
                "total_versions": total,
                "tailored_interview_rate": tailored_rate,
                "fallback_interview_rate": fallback_rate,
                "avg_score_interviewed": round(
                    score_row["avg_interviewed"] or 0, 1
                ),
                "avg_score_rejected": round(
                    score_row["avg_rejected"] or 0, 1
                ),
                "by_provider": [
                    {
                        "provider": r["provider"],
                        "count": r["count"],
                        "interview_rate": round(r["interview_rate"], 1),
                    }
                    for r in provider_rows
                ],
            }

    # ------------------------------------------------------------------
    # Uploaded documents (TASK-030 M1)
    # ------------------------------------------------------------------

    def save_uploaded_document(
        self,
        filename: str,
        file_type: str,
        file_path: str,
        raw_text: str | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> int:
        """Insert an uploaded document record. Returns the new id."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO uploaded_documents (
                    filename, file_type, file_path, raw_text,
                    llm_provider, llm_model, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, CASE WHEN ? IS NOT NULL THEN CURRENT_TIMESTAMP END)
                """,
                (filename, file_type, file_path, raw_text,
                 llm_provider, llm_model, llm_provider),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def get_uploaded_documents(self) -> list[dict]:
        """Return all uploaded documents ordered by creation date."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM uploaded_documents ORDER BY created_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_uploaded_document(self, doc_id: int) -> dict | None:
        """Return a single uploaded document by id."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM uploaded_documents WHERE id = ?", (doc_id,)
            ).fetchone()
            return dict(row) if row else None

    def delete_uploaded_document(self, doc_id: int) -> None:
        """Delete an uploaded document and its KB entries."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM knowledge_base WHERE source_doc_id = ?", (doc_id,)
            )
            conn.execute(
                "DELETE FROM uploaded_documents WHERE id = ?", (doc_id,)
            )

    # ------------------------------------------------------------------
    # Knowledge base entries (TASK-030 M1)
    # ------------------------------------------------------------------

    def save_kb_entry(
        self,
        category: str,
        text: str,
        subsection: str | None = None,
        role_id: int | None = None,
        job_types: str | None = None,
        tags: str | None = None,
        source_doc_id: int | None = None,
        embedding: bytes | None = None,
    ) -> int | None:
        """Insert a KB entry with dedup. Returns id or None if duplicate."""
        with self._connect() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO knowledge_base (
                        category, text, subsection, role_id,
                        job_types, tags, source_doc_id, embedding
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (category, text, subsection, role_id,
                     job_types, tags, source_doc_id, embedding),
                )
                return cursor.lastrowid  # type: ignore[return-value]
            except sqlite3.IntegrityError:
                return None  # duplicate (category, text)

    def get_kb_entries(
        self,
        category: str | None = None,
        active_only: bool = True,
        search: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict]:
        """Return KB entries with optional filtering, joined with roles."""
        query = """
            SELECT kb.*,
                   r.title AS role_title, r.company AS role_company,
                   r.start_date AS role_start_date, r.end_date AS role_end_date,
                   r.location AS role_location
            FROM knowledge_base kb
            LEFT JOIN roles r ON kb.role_id = r.id
            WHERE 1=1
        """
        params: list = []
        if active_only:
            query += " AND kb.is_active = 1"
        if category:
            query += " AND kb.category = ?"
            params.append(category)
        if search:
            query += " AND (kb.text LIKE ? OR kb.subsection LIKE ? OR kb.tags LIKE ? OR r.company LIKE ? OR r.title LIKE ?)"
            params.extend([f"%{search}%"] * 5)
        query += " ORDER BY kb.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_kb_entry(self, entry_id: int) -> dict | None:
        """Return a single KB entry by id, joined with role."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT kb.*,
                          r.title AS role_title, r.company AS role_company,
                          r.start_date AS role_start_date, r.end_date AS role_end_date,
                          r.location AS role_location
                   FROM knowledge_base kb
                   LEFT JOIN roles r ON kb.role_id = r.id
                   WHERE kb.id = ?""",
                (entry_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_kb_entries_by_ids(self, entry_ids: list[int]) -> list[dict]:
        """Fetch specific KB entries by their IDs, preserving order."""
        if not entry_ids:
            return []
        placeholders = ",".join("?" for _ in entry_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM knowledge_base WHERE id IN ({placeholders})",
                entry_ids,
            ).fetchall()
            entries_map = {row["id"]: dict(row) for row in rows}
            return [entries_map[eid] for eid in entry_ids if eid in entries_map]

    def update_kb_entry(
        self,
        entry_id: int,
        text: str | None = None,
        subsection: str | None = None,
        role_id: int | None = None,
        job_types: str | None = None,
        tags: str | None = None,
    ) -> bool:
        """Update a KB entry. Returns True if found and updated."""
        sets: list[str] = ["updated_at = CURRENT_TIMESTAMP"]
        params: list = []
        if text is not None:
            sets.append("text = ?")
            params.append(text)
        if subsection is not None:
            sets.append("subsection = ?")
            params.append(subsection)
        if role_id is not None:
            sets.append("role_id = ?")
            params.append(role_id)
        if job_types is not None:
            sets.append("job_types = ?")
            params.append(job_types)
        if tags is not None:
            sets.append("tags = ?")
            params.append(tags)

        params.append(entry_id)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE knowledge_base SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            return cursor.rowcount > 0

    def soft_delete_kb_entry(self, entry_id: int) -> bool:
        """Soft-delete a KB entry by setting is_active=0."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE knowledge_base SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (entry_id,),
            )
            return cursor.rowcount > 0

    def get_kb_stats(self) -> dict:
        """Return KB statistics: counts by category and total."""
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM knowledge_base WHERE is_active = 1"
            ).fetchone()[0]
            by_category = conn.execute(
                "SELECT category, COUNT(*) as count FROM knowledge_base WHERE is_active = 1 GROUP BY category"
            ).fetchall()
            return {
                "total": total,
                "by_category": {row["category"]: row["count"] for row in by_category},
            }

    # ------------------------------------------------------------------
    # KB Usage Log + Effectiveness (TASK-030 M9)
    # ------------------------------------------------------------------

    def log_kb_usage(
        self,
        entry_ids: list[int],
        application_id: int | None = None,
        scores: dict[int, float] | None = None,
    ) -> int:
        """Log usage of KB entries for a resume assembly.

        Also increments usage_count and updates last_used_at on each entry.

        Args:
            entry_ids: IDs of KB entries used.
            application_id: Optional application ID this was for.
            scores: Optional mapping of entry_id → tfidf_score.

        Returns:
            Number of log rows inserted.
        """
        if not entry_ids:
            return 0

        score_map = scores or {}
        with self._connect() as conn:
            for eid in entry_ids:
                conn.execute(
                    "INSERT INTO kb_usage_log (entry_id, application_id, tfidf_score) "
                    "VALUES (?, ?, ?)",
                    (eid, application_id, score_map.get(eid)),
                )
                conn.execute(
                    "UPDATE knowledge_base SET usage_count = COALESCE(usage_count, 0) + 1, "
                    "last_used_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (eid,),
                )
        return len(entry_ids)

    def update_kb_outcome(
        self,
        application_id: int,
        outcome: str,
    ) -> int:
        """Update outcome for all usage log entries tied to an application.

        Also recalculates effectiveness_score for affected KB entries using
        a weighted moving average: score = successes / total_uses.

        Args:
            application_id: The application that received feedback.
            outcome: One of "interview", "rejected", "no_response".

        Returns:
            Number of usage log rows updated.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE kb_usage_log SET outcome = ? WHERE application_id = ?",
                (outcome, application_id),
            )
            updated = cursor.rowcount

            if updated > 0 and outcome == "interview":
                # Get affected entry IDs
                rows = conn.execute(
                    "SELECT DISTINCT entry_id FROM kb_usage_log WHERE application_id = ?",
                    (application_id,),
                ).fetchall()

                for row in rows:
                    eid = row["entry_id"]
                    # Recalculate: interviews / total logged uses
                    stats = conn.execute(
                        "SELECT COUNT(*) as total, "
                        "SUM(CASE WHEN outcome = 'interview' THEN 1 ELSE 0 END) as wins "
                        "FROM kb_usage_log WHERE entry_id = ? AND outcome IS NOT NULL",
                        (eid,),
                    ).fetchone()
                    if stats and stats["total"] > 0:
                        score = stats["wins"] / stats["total"]
                        conn.execute(
                            "UPDATE knowledge_base SET effectiveness_score = ? WHERE id = ?",
                            (round(score, 4), eid),
                        )

        return updated

    def get_kb_effectiveness(self, limit: int = 50) -> list[dict]:
        """Return KB entries ranked by effectiveness_score.

        Returns entries that have been used at least once, sorted by
        effectiveness_score descending.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, category, text, subsection, "
                "COALESCE(effectiveness_score, 0.0) as effectiveness_score, "
                "COALESCE(usage_count, 0) as usage_count, last_used_at "
                "FROM knowledge_base "
                "WHERE is_active = 1 AND COALESCE(usage_count, 0) > 0 "
                "ORDER BY effectiveness_score DESC, usage_count DESC "
                "LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_reuse_stats(self) -> dict:
        """Return aggregate KB reuse statistics.

        Returns:
            Dict with keys: total_assemblies, total_entries_used,
            unique_entries_used, interviews_from_kb, avg_effectiveness,
            top_categories.
        """
        with self._connect() as conn:
            # Total usage log entries (each = one entry used in one assembly)
            total_used = conn.execute("SELECT COUNT(*) FROM kb_usage_log").fetchone()[0]

            # Unique entries ever used
            unique_used = conn.execute(
                "SELECT COUNT(DISTINCT entry_id) FROM kb_usage_log"
            ).fetchone()[0]

            # Distinct application_ids = total assemblies
            total_assemblies = conn.execute(
                "SELECT COUNT(DISTINCT application_id) FROM kb_usage_log "
                "WHERE application_id IS NOT NULL"
            ).fetchone()[0]

            # Interview outcomes
            interviews = conn.execute(
                "SELECT COUNT(DISTINCT application_id) FROM kb_usage_log "
                "WHERE outcome = 'interview'"
            ).fetchone()[0]

            # Average effectiveness of used entries
            avg_row = conn.execute(
                "SELECT AVG(COALESCE(effectiveness_score, 0.0)) as avg_eff "
                "FROM knowledge_base "
                "WHERE is_active = 1 AND COALESCE(usage_count, 0) > 0"
            ).fetchone()
            avg_eff = round(avg_row["avg_eff"], 4) if avg_row["avg_eff"] else 0.0

            # Top categories by usage
            cats = conn.execute(
                "SELECT kb.category, COUNT(*) as uses "
                "FROM kb_usage_log ul JOIN knowledge_base kb ON ul.entry_id = kb.id "
                "GROUP BY kb.category ORDER BY uses DESC"
            ).fetchall()

            return {
                "total_assemblies": total_assemblies,
                "total_entries_used": total_used,
                "unique_entries_used": unique_used,
                "interviews_from_kb": interviews,
                "avg_effectiveness": avg_eff,
                "top_categories": {r["category"]: r["uses"] for r in cats},
            }

    # ------------------------------------------------------------------
    # Roles (TASK-030 M1)
    # ------------------------------------------------------------------

    def save_role(
        self,
        title: str,
        company: str,
        start_date: str | None = None,
        end_date: str | None = None,
        location: str | None = None,
        domain: str | None = None,
        source_doc_id: int | None = None,
    ) -> int | None:
        """Insert a role record with dedup. Returns id or None if duplicate."""
        with self._connect() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO roles (title, company, start_date, end_date, location, domain, source_doc_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (title, company, start_date, end_date, location, domain, source_doc_id),
                )
                return cursor.lastrowid  # type: ignore[return-value]
            except sqlite3.IntegrityError:
                # Duplicate — return existing role id
                row = conn.execute(
                    "SELECT id FROM roles WHERE title = ? AND company = ? AND start_date IS ?",
                    (title, company, start_date),
                ).fetchone()
                return row["id"] if row else None

    def get_roles(self) -> list[dict]:
        """Return all roles ordered by start_date descending."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM roles ORDER BY start_date DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_analytics_summary(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]

            by_status_rows = conn.execute(
                "SELECT status, COUNT(*) as count FROM applications GROUP BY status"
            ).fetchall()
            by_status = {row["status"]: row["count"] for row in by_status_rows}

            by_platform_rows = conn.execute(
                "SELECT platform, COUNT(*) as count FROM applications GROUP BY platform"
            ).fetchall()
            by_platform = {row["platform"]: row["count"] for row in by_platform_rows}

            return {
                "total": total,
                "by_status": by_status,
                "by_platform": by_platform,
            }

    def get_daily_analytics(self, days: int = 30) -> list[dict]:
        with self._connect() as conn:
            if days > 0:
                rows = conn.execute(
                    """
                    SELECT DATE(applied_at) as date, COUNT(*) as count
                    FROM applications
                    WHERE applied_at >= DATE('now', ?)
                    GROUP BY DATE(applied_at)
                    ORDER BY date
                    """,
                    (f"-{days} days",),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT DATE(applied_at) as date, COUNT(*) as count
                    FROM applications
                    GROUP BY DATE(applied_at)
                    ORDER BY date
                    """
                ).fetchall()
            return [{"date": row["date"], "count": row["count"]} for row in rows]

    def get_enhanced_analytics(self, days: int = 30) -> dict:
        """Compute all analytics metrics in a single database connection.

        Implements: FR-094 (enhanced analytics endpoint).
        """
        interview_statuses = ("interview", "interviewing", "interviewed")
        offer_statuses = ("offer", "accepted")
        funnel_statuses = ("applied",) + interview_statuses + offer_statuses

        with self._connect() as conn:
            # --- Summary metrics ---
            total = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]

            avg_row = conn.execute(
                "SELECT AVG(match_score) as avg_score FROM applications"
            ).fetchone()
            avg_score = round(avg_row["avg_score"], 1) if avg_row["avg_score"] is not None else None

            this_week = conn.execute(
                "SELECT COUNT(*) FROM applications WHERE applied_at >= date('now', 'weekday 1', '-7 days')"
            ).fetchone()[0]

            applied_count = conn.execute(
                "SELECT COUNT(*) FROM applications WHERE status = 'applied'"
            ).fetchone()[0]

            interview_count = conn.execute(
                "SELECT COUNT(*) FROM applications WHERE status IN (?, ?, ?)",
                interview_statuses,
            ).fetchone()[0]

            interview_rate = round((interview_count / applied_count) * 100, 1) if applied_count > 0 else 0.0

            summary = {
                "total": total,
                "interview_rate": interview_rate,
                "avg_score": avg_score,
                "this_week": this_week,
            }

            # --- Conversion funnel ---
            funnel_row = conn.execute(
                """
                SELECT
                  SUM(CASE WHEN status IN (?,?,?,?,?,?) THEN 1 ELSE 0 END) as funnel_applied,
                  SUM(CASE WHEN status IN (?,?,?,?,?) THEN 1 ELSE 0 END) as funnel_interview,
                  SUM(CASE WHEN status IN (?,?) THEN 1 ELSE 0 END) as funnel_offer
                FROM applications
                """,
                funnel_statuses + interview_statuses + offer_statuses + offer_statuses,
            ).fetchone()

            fa = funnel_row["funnel_applied"] or 0
            fi = funnel_row["funnel_interview"] or 0
            fo = funnel_row["funnel_offer"] or 0

            funnel = {
                "applied": fa,
                "interview": fi,
                "offer": fo,
                "applied_to_interview_rate": round((fi / fa) * 100, 1) if fa > 0 else 0.0,
                "interview_to_offer_rate": round((fo / fi) * 100, 1) if fi > 0 else 0.0,
            }

            # --- Platform performance ---
            platform_rows = conn.execute(
                """
                SELECT
                  platform,
                  COUNT(*) as total,
                  SUM(CASE WHEN status IN (?,?,?) THEN 1 ELSE 0 END) as interviews,
                  ROUND(AVG(match_score), 1) as avg_score,
                  SUM(CASE WHEN status IN (?,?) THEN 1 ELSE 0 END) as offers
                FROM applications
                GROUP BY platform
                ORDER BY total DESC
                """,
                interview_statuses + offer_statuses,
            ).fetchall()

            platforms = []
            for row in platform_rows:
                pt = row["total"]
                pi = row["interviews"]
                platforms.append({
                    "platform": row["platform"],
                    "total": pt,
                    "interviews": pi,
                    "interview_rate": round((pi / pt) * 100, 1) if pt > 0 else 0.0,
                    "avg_score": row["avg_score"] if row["avg_score"] is not None else 0.0,
                    "offers": row["offers"],
                })

            # --- Score distribution ---
            score_rows = conn.execute(
                """
                SELECT
                  CASE
                    WHEN match_score BETWEEN 0  AND 9  THEN 0
                    WHEN match_score BETWEEN 10 AND 19 THEN 1
                    WHEN match_score BETWEEN 20 AND 29 THEN 2
                    WHEN match_score BETWEEN 30 AND 39 THEN 3
                    WHEN match_score BETWEEN 40 AND 49 THEN 4
                    WHEN match_score BETWEEN 50 AND 59 THEN 5
                    WHEN match_score BETWEEN 60 AND 69 THEN 6
                    WHEN match_score BETWEEN 70 AND 79 THEN 7
                    WHEN match_score BETWEEN 80 AND 89 THEN 8
                    ELSE 9
                  END as bucket_idx,
                  COUNT(*) as count,
                  SUM(CASE WHEN status IN (?,?,?) THEN 1 ELSE 0 END) as interview_count
                FROM applications
                GROUP BY bucket_idx
                ORDER BY bucket_idx
                """,
                interview_statuses,
            ).fetchall()

            bucket_labels = [
                "0-9", "10-19", "20-29", "30-39", "40-49",
                "50-59", "60-69", "70-79", "80-89", "90-100",
            ]
            score_map = {row["bucket_idx"]: row for row in score_rows}
            score_distribution = []
            for i, label in enumerate(bucket_labels):
                row = score_map.get(i)
                cnt = row["count"] if row else 0
                ic = row["interview_count"] if row else 0
                score_distribution.append({
                    "bucket": label,
                    "count": cnt,
                    "interview_count": ic,
                    "interview_rate": round((ic / cnt) * 100, 1) if cnt > 0 else 0.0,
                })

            # --- Weekly comparison ---
            current_row = conn.execute(
                """
                SELECT COUNT(*) as applications,
                  SUM(CASE WHEN status IN (?,?,?) THEN 1 ELSE 0 END) as interviews,
                  ROUND(AVG(match_score), 1) as avg_score
                FROM applications
                WHERE applied_at >= date('now', 'weekday 1', '-7 days')
                """,
                interview_statuses,
            ).fetchone()

            previous_row = conn.execute(
                """
                SELECT COUNT(*) as applications,
                  SUM(CASE WHEN status IN (?,?,?) THEN 1 ELSE 0 END) as interviews,
                  ROUND(AVG(match_score), 1) as avg_score
                FROM applications
                WHERE applied_at >= date('now', 'weekday 1', '-14 days')
                  AND applied_at < date('now', 'weekday 1', '-7 days')
                """,
                interview_statuses,
            ).fetchone()

            cur = {
                "applications": current_row["applications"],
                "interviews": current_row["interviews"] or 0,
                "avg_score": current_row["avg_score"],
            }
            prev = {
                "applications": previous_row["applications"],
                "interviews": previous_row["interviews"] or 0,
                "avg_score": previous_row["avg_score"],
            }
            changes_avg = None
            if cur["avg_score"] is not None and prev["avg_score"] is not None:
                changes_avg = round(cur["avg_score"] - prev["avg_score"], 1)

            weekly = {
                "current": cur,
                "previous": prev,
                "changes": {
                    "applications": cur["applications"] - prev["applications"],
                    "interviews": cur["interviews"] - prev["interviews"],
                    "avg_score": changes_avg,
                },
            }

            # --- Top companies ---
            top_rows = conn.execute(
                """
                SELECT company, COUNT(*) as total
                FROM applications
                GROUP BY company
                ORDER BY total DESC, company ASC
                LIMIT 10
                """
            ).fetchall()

            top_company_names = [row["company"] for row in top_rows]
            top_companies = []

            if top_company_names:
                placeholders = ",".join("?" * len(top_company_names))
                status_rows = conn.execute(
                    f"""
                    SELECT company, status, COUNT(*) as count
                    FROM applications
                    WHERE company IN ({placeholders})
                    GROUP BY company, status
                    """,
                    top_company_names,
                ).fetchall()

                status_map: dict[str, dict[str, int]] = {}
                for sr in status_rows:
                    status_map.setdefault(sr["company"], {})[sr["status"]] = sr["count"]

                for row in top_rows:
                    top_companies.append({
                        "company": row["company"],
                        "total": row["total"],
                        "statuses": status_map.get(row["company"], {}),
                    })

            # --- Response times ---
            def _compute_response_times(statuses: tuple[str, ...]) -> dict:
                placeholders = ",".join("?" * len(statuses))
                rt_rows = conn.execute(
                    f"""
                    SELECT JULIANDAY(updated_at) - JULIANDAY(applied_at) as days_to_respond
                    FROM applications
                    WHERE status IN ({placeholders})
                      AND updated_at != applied_at
                    ORDER BY days_to_respond
                    """,
                    statuses,
                ).fetchall()

                if not rt_rows:
                    return {"median_days": None, "avg_days": None}

                days_list = [row["days_to_respond"] for row in rt_rows]
                n = len(days_list)
                median = days_list[n // 2] if n % 2 == 1 else (days_list[n // 2 - 1] + days_list[n // 2]) / 2
                avg = sum(days_list) / n
                return {"median_days": round(median, 1), "avg_days": round(avg, 1)}

            response_times = {
                "to_interview": _compute_response_times(interview_statuses),
                "to_rejected": _compute_response_times(("rejected",)),
            }

            # --- Daily trend ---
            daily = self.get_daily_analytics(days)

        return {
            "summary": summary,
            "funnel": funnel,
            "platforms": platforms,
            "score_distribution": score_distribution,
            "weekly": weekly,
            "top_companies": top_companies,
            "response_times": response_times,
            "daily": daily,
        }

    # ------------------------------------------------------------------
    # Resume Presets (TASK-030 M7)
    # ------------------------------------------------------------------

    def save_preset(
        self,
        name: str,
        entry_ids: str,
        template: str = "classic",
    ) -> int:
        """Create a resume preset. entry_ids is a JSON string like '[1,5,12]'."""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO resume_presets (name, entry_ids, template) VALUES (?, ?, ?)",
                (name, entry_ids, template),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def get_presets(self) -> list[dict]:
        """Return all resume presets ordered by most recent first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM resume_presets ORDER BY updated_at DESC, created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_preset(self, preset_id: int) -> dict | None:
        """Return a single preset by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM resume_presets WHERE id = ?", (preset_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_preset(
        self,
        preset_id: int,
        name: str | None = None,
        entry_ids: str | None = None,
        template: str | None = None,
    ) -> bool:
        """Update a preset. Returns True if found and updated."""
        fields: list[str] = []
        values: list[object] = []
        if name is not None:
            fields.append("name = ?")
            values.append(name)
        if entry_ids is not None:
            fields.append("entry_ids = ?")
            values.append(entry_ids)
        if template is not None:
            fields.append("template = ?")
            values.append(template)
        if not fields:
            return False
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(preset_id)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE resume_presets SET {', '.join(fields)} WHERE id = ?",
                tuple(values),
            )
            return cursor.rowcount > 0

    def delete_preset(self, preset_id: int) -> bool:
        """Delete a preset. Returns True if found and deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM resume_presets WHERE id = ?", (preset_id,)
            )
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Custom LaTeX Templates
    # ------------------------------------------------------------------

    def save_custom_template(
        self,
        name: str,
        tex_content: str,
        description: str = "",
        is_default: bool = False,
    ) -> int:
        """Save a custom LaTeX template. Returns template id."""
        with self._connect() as conn:
            if is_default:
                conn.execute("UPDATE custom_templates SET is_default = 0")
            cursor = conn.execute(
                """INSERT INTO custom_templates (name, description, tex_content, is_default)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                     tex_content = excluded.tex_content,
                     description = excluded.description,
                     is_default = excluded.is_default,
                     updated_at = CURRENT_TIMESTAMP""",
                (name, description, tex_content, int(is_default)),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def get_custom_templates(self) -> list[dict]:
        """Return all custom templates (without full tex_content for listing)."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id, name, description, is_default, created_at, updated_at
                   FROM custom_templates ORDER BY name"""
            ).fetchall()
            return [dict(r) for r in rows]

    def get_custom_template(self, template_id: int) -> dict | None:
        """Return a single custom template with full tex_content."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM custom_templates WHERE id = ?", (template_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_custom_template_by_name(self, name: str) -> dict | None:
        """Return a custom template by name with full tex_content."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM custom_templates WHERE name = ?", (name,)
            ).fetchone()
            return dict(row) if row else None

    def get_default_template(self) -> dict | None:
        """Return the default custom template, if any."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM custom_templates WHERE is_default = 1"
            ).fetchone()
            return dict(row) if row else None

    def set_default_template(self, template_id: int) -> bool:
        """Set a template as default, clearing other defaults."""
        with self._connect() as conn:
            conn.execute("UPDATE custom_templates SET is_default = 0")
            cursor = conn.execute(
                "UPDATE custom_templates SET is_default = 1 WHERE id = ?",
                (template_id,),
            )
            return cursor.rowcount > 0

    def delete_custom_template(self, template_id: int) -> bool:
        """Delete a custom template. Returns True if found and deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM custom_templates WHERE id = ?", (template_id,)
            )
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Portal credential CRUD (FR-086)
    # ------------------------------------------------------------------

    def save_portal_credential(
        self,
        domain: str,
        portal_type: str,
        username: str,
        password: str,
        has_keyring: bool = False,
        notes: str | None = None,
    ) -> int:
        """Insert or update a portal credential. Returns the credential ID."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO portal_credentials
                    (domain, portal_type, username, password_hash,
                     has_keyring_password, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    portal_type = excluded.portal_type,
                    username = excluded.username,
                    password_hash = excluded.password_hash,
                    has_keyring_password = excluded.has_keyring_password,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (domain, portal_type, username, password,
                 1 if has_keyring else 0, notes),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def get_portal_credential_by_domain(self, domain: str) -> dict | None:
        """Get a portal credential by domain. Returns dict or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM portal_credentials WHERE domain = ?",
                (domain,),
            ).fetchone()
            if row is None:
                return None
            d = dict(row)
            d["has_keyring_password"] = bool(d.get("has_keyring_password", 0))
            return d

    def get_all_portal_credentials(self) -> list[dict]:
        """List all portal credentials (passwords masked)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, domain, portal_type, username, has_keyring_password, "
                "notes, last_login_at, login_success_count, login_failure_count, "
                "created_at, updated_at "
                "FROM portal_credentials ORDER BY domain"
            ).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["has_keyring_password"] = bool(d.get("has_keyring_password", 0))
                result.append(d)
            return result

    def delete_portal_credential_by_domain(self, domain: str) -> bool:
        """Delete a portal credential by domain. Returns True if deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM portal_credentials WHERE domain = ?", (domain,),
            )
            return cursor.rowcount > 0

    def record_login_attempt(self, domain: str, success: bool) -> None:
        """Record a login attempt outcome for a portal credential."""
        col = "login_success_count" if success else "login_failure_count"
        with self._connect() as conn:
            conn.execute(
                f"UPDATE portal_credentials SET {col} = {col} + 1, "
                "last_login_at = CURRENT_TIMESTAMP, "
                "updated_at = CURRENT_TIMESTAMP "
                "WHERE domain = ?",
                (domain,),
            )
