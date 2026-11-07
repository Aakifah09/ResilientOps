"""SQLite persistence and business rules for ResilientOps.

All data is fictional and generated for demonstration purposes only.
"""
from __future__ import annotations

import os
import sqlite3
import zlib
from contextlib import contextmanager
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("RESILIENTOPS_DB", os.path.join(BASE_DIR, "data", "resilientops.db"))

# --------------------------------------------------------------------------
# Reference data / business rules
# --------------------------------------------------------------------------
SEVERITIES = ["Critical", "High", "Medium", "Low"]
STATUSES = ["Open", "Investigating", "Mitigating", "Resolved", "Closed"]
OPEN_STATUSES = ["Open", "Investigating", "Mitigating"]
CLOSED_STATUSES = ["Resolved", "Closed"]

# Resolution SLA target (hours) per severity
SLA_HOURS = {"Critical": 4, "High": 8, "Medium": 24, "Low": 72}
# Fraction of the incident duration counted as full service downtime
DOWNTIME_FACTOR = {"Critical": 0.9, "High": 0.4, "Medium": 0.12, "Low": 0.02}

RECOVERY_STAGES = {
    "Detected": 5,
    "Triaged": 20,
    "Contained": 45,
    "Recovering": 70,
    "Restored": 90,
    "Post-Incident Review": 100,
}

ROOT_CAUSES = [
    "Software Defect",
    "Configuration Change",
    "Capacity / Performance",
    "Infrastructure Failure",
    "Third-Party Provider",
    "Network",
    "Security Event",
    "Certificate Expiry",
    "Human Error",
    "Under Investigation",
]

TEAMS = [
    "Payments Platform",
    "API Gateway Team",
    "Database Engineering",
    "Identity & Access",
    "Network Operations",
    "Cloud Infrastructure",
    "Security Operations",
    "Service Desk",
]

# name -> (category, tier, availability target %)
SERVICES = {
    "Card Payment Gateway": ("Payment Processing", "Tier 1", 99.95),
    "Payment Settlement Engine": ("Payment Processing", "Tier 1", 99.90),
    "Merchant Payouts Service": ("Payment Processing", "Tier 2", 99.90),
    "Public REST API": ("API", "Tier 1", 99.90),
    "Partner Webhooks API": ("API", "Tier 2", 99.50),
    "Core Customer Database": ("Database", "Tier 1", 99.99),
    "Transactions Ledger DB": ("Database", "Tier 1", 99.99),
    "Single Sign-On (SSO)": ("Authentication", "Tier 1", 99.95),
    "MFA Service": ("Authentication", "Tier 1", 99.90),
    "OAuth Token Service": ("Authentication", "Tier 2", 99.90),
}

DT_FMT = "%Y-%m-%d %H:%M"


def now() -> datetime:
    return datetime.now().replace(second=0, microsecond=0)


# --------------------------------------------------------------------------
# Connection / schema
# --------------------------------------------------------------------------
@contextmanager
def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS services (
    name TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    tier TEXT NOT NULL,
    target_availability REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    service TEXT NOT NULL REFERENCES services(name),
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    reported_at TEXT NOT NULL,
    resolved_at TEXT,
    root_cause TEXT NOT NULL,
    assigned_team TEXT NOT NULL,
    description TEXT,
    customer_impact TEXT,
    recovery_stage TEXT NOT NULL DEFAULT 'Detected',
    recovery_progress INTEGER NOT NULL DEFAULT 5,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS incident_updates (
    update_id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    logged_at TEXT NOT NULL,
    stage TEXT NOT NULL,
    progress INTEGER NOT NULL,
    note TEXT
);
CREATE TABLE IF NOT EXISTS uptime_samples (
    service TEXT NOT NULL REFERENCES services(name),
    day TEXT NOT NULL,
    baseline_uptime REAL NOT NULL,
    PRIMARY KEY (service, day)
);
"""


def init_db(force_reset: bool = False) -> None:
    """Create tables and load seed data on first run (or when reset)."""
    from seed_data import seed_incidents  # local import avoids a cycle

    if force_reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT OR IGNORE INTO services VALUES (?,?,?,?)",
            [(n, c, t, a) for n, (c, t, a) in SERVICES.items()],
        )
        has_data = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    if not has_data:
        seed_incidents()
    ensure_uptime_coverage()


# --------------------------------------------------------------------------
# Incident CRUD
# --------------------------------------------------------------------------
def next_incident_id() -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM incidents"
        ).fetchone()
    return f"INC-{(row[0] or 1000) + 1}"


def _normalise_resolution(data: dict, existing_resolved_at: str | None = None) -> dict:
    """Keep resolved_at / recovery fields consistent with status."""
    if data["status"] in CLOSED_STATUSES:
        data["resolved_at"] = data.get("resolved_at") or existing_resolved_at or now().strftime(DT_FMT)
        if data.get("recovery_progress", 0) < 90:
            data["recovery_stage"], data["recovery_progress"] = "Restored", 90
        if data["status"] == "Closed":
            data["recovery_stage"], data["recovery_progress"] = "Post-Incident Review", 100
    else:
        data["resolved_at"] = None
        if data.get("recovery_progress", 0) >= 90:
            data["recovery_stage"], data["recovery_progress"] = "Recovering", 70
    return data


def create_incident(data: dict) -> str:
    inc_id = next_incident_id()
    ts = now().strftime(DT_FMT)
    data = _normalise_resolution(dict(data))
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO incidents (id, title, service, severity, status, reported_at,
               resolved_at, root_cause, assigned_team, description, customer_impact,
               recovery_stage, recovery_progress, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                inc_id, data["title"], data["service"], data["severity"], data["status"],
                data["reported_at"], data["resolved_at"], data["root_cause"],
                data["assigned_team"], data.get("description", ""), data.get("customer_impact", ""),
                data["recovery_stage"], int(data["recovery_progress"]), ts, ts,
            ),
        )
        conn.execute(
            "INSERT INTO incident_updates (incident_id, logged_at, stage, progress, note) VALUES (?,?,?,?,?)",
            (inc_id, data["reported_at"], data["recovery_stage"], int(data["recovery_progress"]),
             "Incident logged in ResilientOps."),
        )
    return inc_id


def update_incident(inc_id: str, data: dict, note: str | None = None) -> None:
    existing = get_incident(inc_id)
    if existing is None:
        raise ValueError(f"Incident {inc_id} not found")
    data = dict(data)
    keep = existing["resolved_at"] if existing["status"] in CLOSED_STATUSES else None
    data = _normalise_resolution(data, keep)
    with get_conn() as conn:
        conn.execute(
            """UPDATE incidents SET title=?, service=?, severity=?, status=?, reported_at=?,
               resolved_at=?, root_cause=?, assigned_team=?, description=?, customer_impact=?,
               recovery_stage=?, recovery_progress=?, updated_at=? WHERE id=?""",
            (
                data["title"], data["service"], data["severity"], data["status"],
                data["reported_at"], data["resolved_at"], data["root_cause"],
                data["assigned_team"], data.get("description", ""), data.get("customer_impact", ""),
                data["recovery_stage"], int(data["recovery_progress"]),
                now().strftime(DT_FMT), inc_id,
            ),
        )
        changes = [
            f"{k.replace('_', ' ')}: {existing[k]} → {data[k]}"
            for k in ("severity", "status", "assigned_team", "recovery_stage")
            if str(existing[k]) != str(data[k])
        ]
        if changes or note:
            text = "; ".join(filter(None, [note, ", ".join(changes)]))
            conn.execute(
                "INSERT INTO incident_updates (incident_id, logged_at, stage, progress, note) VALUES (?,?,?,?,?)",
                (inc_id, now().strftime(DT_FMT), data["recovery_stage"],
                 int(data["recovery_progress"]), text),
            )


def add_recovery_update(inc_id: str, stage: str, progress: int, note: str) -> None:
    inc = get_incident(inc_id)
    data = dict(inc)
    data["recovery_stage"], data["recovery_progress"] = stage, int(progress)
    if progress >= 90 and inc["status"] in OPEN_STATUSES:
        data["status"] = "Resolved"
    with get_conn() as conn:
        conn.execute(
            "UPDATE incidents SET recovery_stage=?, recovery_progress=?, status=?, resolved_at=?, updated_at=? WHERE id=?",
            (
                stage, int(progress), data["status"],
                inc["resolved_at"] or (now().strftime(DT_FMT) if data["status"] in CLOSED_STATUSES else None),
                now().strftime(DT_FMT), inc_id,
            ),
        )
        conn.execute(
            "INSERT INTO incident_updates (incident_id, logged_at, stage, progress, note) VALUES (?,?,?,?,?)",
            (inc_id, now().strftime(DT_FMT), stage, int(progress), note or ""),
        )


def delete_incident(inc_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM incidents WHERE id=?", (inc_id,))


def get_incident(inc_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM incidents WHERE id=?", (inc_id,)).fetchone()
    return dict(row) if row else None


def get_updates(inc_id: str) -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(
            "SELECT logged_at, stage, progress, note FROM incident_updates WHERE incident_id=? ORDER BY logged_at, update_id",
            conn, params=(inc_id,),
        )


def get_services() -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query("SELECT * FROM services ORDER BY category, name", conn)


# --------------------------------------------------------------------------
# Analytics
# --------------------------------------------------------------------------
def load_incidents() -> pd.DataFrame:
    """Return all incidents enriched with SLA and service attributes."""
    with get_conn() as conn:
        df = pd.read_sql_query(
            """SELECT i.*, s.category, s.tier FROM incidents i
               LEFT JOIN services s ON s.name = i.service ORDER BY i.reported_at DESC""",
            conn,
        )
    if df.empty:
        return df
    current = pd.Timestamp(now())
    df["reported_at"] = pd.to_datetime(df["reported_at"])
    df["resolved_at"] = pd.to_datetime(df["resolved_at"])
    df["is_open"] = df["status"].isin(OPEN_STATUSES)
    df["sla_target_hrs"] = df["severity"].map(SLA_HOURS)
    df["sla_due"] = df["reported_at"] + pd.to_timedelta(df["sla_target_hrs"], unit="h")
    end = df["resolved_at"].fillna(current)
    df["elapsed_hrs"] = ((end - df["reported_at"]).dt.total_seconds() / 3600).round(1)
    df["sla_used_pct"] = (df["elapsed_hrs"] / df["sla_target_hrs"] * 100).round(0)

    def sla_status(r):
        if not r["is_open"]:
            return "Met" if r["elapsed_hrs"] <= r["sla_target_hrs"] else "Breached"
        if r["elapsed_hrs"] > r["sla_target_hrs"]:
            return "Overdue"
        return "At Risk" if r["sla_used_pct"] >= 75 else "Within SLA"

    df["sla_status"] = df.apply(sla_status, axis=1)
    df["is_overdue"] = df["sla_status"] == "Overdue"
    df["hours_overdue"] = np.where(df["is_overdue"], (df["elapsed_hrs"] - df["sla_target_hrs"]).round(1), 0.0)
    df["resolution_hrs"] = np.where(df["is_open"], np.nan, df["elapsed_hrs"])
    return df


def ensure_uptime_coverage(days_back: int = 120) -> None:
    """Generate sample baseline uptime (minor blips) for any missing days up to today."""
    start = date.today() - timedelta(days=days_back)
    all_days = pd.date_range(start, date.today(), freq="D").strftime("%Y-%m-%d").tolist()
    with get_conn() as conn:
        existing = {(r[0], r[1]) for r in conn.execute("SELECT service, day FROM uptime_samples")}
        rows = []
        for svc in SERVICES:
            for d in all_days:
                if (svc, d) in existing:
                    continue
                # deterministic per service/day so data is reproducible
                rng = np.random.default_rng(zlib.crc32(f"{svc}|{d}".encode()))
                blip_minutes = rng.choice([0, 0, 0, 0, 0, 0.5, 1, 2, 3, 5])
                rows.append((svc, d, round(100 - blip_minutes / 1440 * 100, 4)))
        conn.executemany("INSERT INTO uptime_samples VALUES (?,?,?)", rows)


def load_availability() -> pd.DataFrame:
    """Daily availability per service = baseline sample minus incident downtime."""
    with get_conn() as conn:
        up = pd.read_sql_query("SELECT * FROM uptime_samples", conn)
    up["day"] = pd.to_datetime(up["day"])
    up["downtime_min"] = (100 - up["baseline_uptime"]) / 100 * 1440

    inc = load_incidents()
    if not inc.empty:
        current = pd.Timestamp(now())
        for _, r in inc.iterrows():
            start, end = r["reported_at"], (r["resolved_at"] if pd.notna(r["resolved_at"]) else current)
            factor = DOWNTIME_FACTOR.get(r["severity"], 0)
            # Spread the downtime over each calendar day the incident spans
            for day in pd.date_range(start.normalize(), end.normalize(), freq="D"):
                seg_start = max(start, day)
                seg_end = min(end, day + pd.Timedelta(days=1))
                minutes = max((seg_end - seg_start).total_seconds() / 60, 0) * factor
                mask = (up["service"] == r["service"]) & (up["day"] == day)
                up.loc[mask, "downtime_min"] += minutes
    up["downtime_min"] = up["downtime_min"].clip(upper=1440)
    up["availability"] = (100 - up["downtime_min"] / 1440 * 100).round(3)
    svc = get_services()
    up = up.merge(svc, left_on="service", right_on="name", how="left").drop(columns="name")
    return up


def classify_severity(customer_facing: bool, scope: str, financial: str, workaround: bool,
                      data_risk: bool) -> tuple[str, int, list[str]]:
    """Simple rules-based severity classification. Returns (severity, score, reasons)."""
    score, reasons = 0, []
    scope_pts = {"Single user / internal": 0, "Single team or region": 1,
                 "Multiple regions / partners": 2, "All customers": 3}
    fin_pts = {"None": 0, "Low (< £10k)": 1, "Medium (£10k–£250k)": 2, "High (> £250k)": 3}
    score += scope_pts[scope]
    reasons.append(f"Scope '{scope}' (+{scope_pts[scope]})")
    score += fin_pts[financial]
    reasons.append(f"Financial impact '{financial}' (+{fin_pts[financial]})")
    if customer_facing:
        score += 2
        reasons.append("Customer-facing service (+2)")
    if not workaround:
        score += 1
        reasons.append("No workaround available (+1)")
    if data_risk:
        score += 3
        reasons.append("Data integrity / security risk (+3)")
    if score >= 8:
        sev = "Critical"
    elif score >= 5:
        sev = "High"
    elif score >= 3:
        sev = "Medium"
    else:
        sev = "Low"
    return sev, score, reasons
