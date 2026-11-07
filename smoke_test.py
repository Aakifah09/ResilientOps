"""Smoke test for ResilientOps. Uses a temporary database; run: python smoke_test.py"""
import os
import sys
import tempfile

TMP = tempfile.mkdtemp()
os.environ["RESILIENTOPS_DB"] = os.path.join(TMP, "test.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        check.failed = True


check.failed = False

# ---- Data layer ---------------------------------------------------------
db.init_db()
df = db.load_incidents()
check(len(df) >= 20, f"seeded {len(df)} incidents (>= 20)")
check(set(df["category"]) >= {"Payment Processing", "API", "Database", "Authentication"}, "all four categories present")
check(df["is_overdue"].any(), "at least one overdue incident")
check((df["sla_status"] == "Met").any() and (df["sla_status"] == "Breached").any(), "SLA met and breached examples")

new_id = db.create_incident({
    "title": "Test incident for smoke test", "service": "Public REST API", "severity": "High",
    "status": "Open", "root_cause": "Software Defect", "assigned_team": "API Gateway Team",
    "reported_at": db.now().strftime(db.DT_FMT), "recovery_stage": "Detected", "recovery_progress": 5,
})
check(db.get_incident(new_id)["status"] == "Open", f"created {new_id}")
inc = db.get_incident(new_id)
inc["status"] = "Resolved"
db.update_incident(new_id, inc, "Fixed")
inc = db.get_incident(new_id)
check(inc["resolved_at"] is not None and inc["recovery_progress"] >= 90, "resolving sets resolved_at and progress")
check(len(db.get_updates(new_id)) >= 2, "timeline updates recorded")
db.add_recovery_update("INC-1023", "Recovering", 95, "test")
check(db.get_incident("INC-1023")["status"] == "Resolved", "recovery >= 90% resolves incident")
db.delete_incident(new_id)
check(db.get_incident(new_id) is None, "delete works")
check(db.classify_severity(True, "All customers", "High (> £250k)", False, True)[0] == "Critical", "classifier: critical")
check(db.classify_severity(False, "Single user / internal", "None", True, False)[0] == "Low", "classifier: low")
av = db.load_availability()
check(not av.empty and av["availability"].between(0, 100).all(), f"availability rows: {len(av)}")

# ---- UI: render every page headlessly -----------------------------------
app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
at = AppTest.from_file(app_path, default_timeout=60).run()
check(not at.exception, "app loads without exception")
pages = at.sidebar.radio[0].options
for p in pages:
    at.sidebar.radio[0].set_value(p).run()
    errs = [e.value for e in at.exception]
    check(not errs, f"page renders: {p}" + (f" -> {errs}" if errs else ""))

# Create an incident through the UI
at.sidebar.radio[0].set_value(pages[2]).run()
at.text_input[0].input("UI-created payment API outage").run()
btn = [b for b in at.button if "Create incident" in b.label][0]
btn.click().run()
check(not at.exception, "create via UI without exception")
check(any("UI-created payment API outage" == t for t in db.load_incidents()["title"]), "UI-created incident persisted")

print("\nRESULT:", "FAILED" if check.failed else "ALL CHECKS PASSED")
sys.exit(1 if check.failed else 0)
