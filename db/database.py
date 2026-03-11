"""SQLite database layer for application storage and analytics.

Implements: FR-004 (SQLite database), FR-005 (application storage),
            FR-006 (analytics queries).
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
