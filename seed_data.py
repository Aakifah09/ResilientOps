"""Fictional seed incidents for the ResilientOps demo.

Dates are generated relative to the moment the database is first created so
that SLA, overdue and trend views always contain meaningful examples.
None of this data relates to any real organisation.
"""
from __future__ import annotations

from datetime import timedelta

from database import DT_FMT, RECOVERY_STAGES, get_conn, now

# (title, service, severity, root_cause, team, status, days_ago, hours_ago_extra,
#  duration_hrs (None = still open), recovery_stage, description, customer_impact)
SEED = [
    ("Card authorisation latency spike", "Card Payment Gateway", "Critical", "Capacity / Performance",
     "Payments Platform", "Closed", 85, 3, 3.5, None,
     "Authorisation response times exceeded 6s during peak trading after a traffic surge.",
     "~18% of card payments timed out at checkout for 3 hours."),
    ("Nightly settlement batch failed", "Payment Settlement Engine", "High", "Software Defect",
     "Payments Platform", "Closed", 80, 1, 6.0, None,
     "Batch job crashed on a malformed currency code introduced in the last release.",
     "Merchant settlements delayed by one business day."),
    ("SSO login failures after IdP certificate expiry", "Single Sign-On (SSO)", "Critical", "Certificate Expiry",
     "Identity & Access", "Closed", 77, 8, 2.5, None,
     "SAML signing certificate expired, rejecting all federated logins.",
     "Staff and partner portals inaccessible."),
    ("Public API 5xx errors after deployment", "Public REST API", "High", "Software Defect",
     "API Gateway Team", "Closed", 74, 5, 1.5, None,
     "A routing change returned HTTP 502 for v2 endpoints. Rolled back.",
     "Partner integrations failed for 90 minutes."),
    ("Primary database failover with replication lag", "Core Customer Database", "High", "Infrastructure Failure",
     "Database Engineering", "Closed", 70, 2, 9.0, None,
     "Storage controller fault forced failover; replica was 14 minutes behind.",
     "Customer profile updates unavailable; read-only mode for 9 hours."),
    ("MFA SMS provider outage", "MFA Service", "High", "Third-Party Provider",
     "Identity & Access", "Closed", 66, 4, 11.0, None,
     "Upstream SMS aggregator suffered a regional outage.",
     "Users relying on SMS one-time codes could not log in; app push unaffected."),
    ("Webhook delivery delays to partners", "Partner Webhooks API", "Medium", "Capacity / Performance",
     "API Gateway Team", "Closed", 62, 6, 20.0, None,
     "Delivery queue backlog grew after a partner endpoint slowed down retries.",
     "Event notifications delayed up to 4 hours."),
    ("Ledger database disk space exhaustion", "Transactions Ledger DB", "Critical", "Capacity / Performance",
     "Database Engineering", "Closed", 58, 0, 5.0, None,
     "Archive job failure left transaction logs growing unchecked until the volume filled.",
     "New transactions could not be posted; payments queued."),
    ("Duplicate merchant payouts triggered", "Merchant Payouts Service", "Critical", "Software Defect",
     "Payments Platform", "Closed", 55, 7, 3.0, None,
     "Retry logic re-sent payout instructions after a timeout.",
     "312 merchants received duplicate payouts; recovery initiated."),
    ("API rate limiter misconfiguration", "Public REST API", "Medium", "Configuration Change",
     "API Gateway Team", "Closed", 50, 3, 6.0, None,
     "Rate limits applied per-region instead of per-client, throttling legitimate traffic.",
     "Some partners received HTTP 429 errors."),
    ("Credential stuffing attack on login", "Single Sign-On (SSO)", "High", "Security Event",
     "Security Operations", "Closed", 46, 9, 7.0, None,
     "Automated login attempts from a botnet; WAF rules and step-up MFA applied.",
     "Login latency increased; 41 accounts locked as a precaution."),
    ("Payment gateway TLS handshake failures with acquirer", "Card Payment Gateway", "High", "Third-Party Provider",
     "Network Operations", "Closed", 42, 2, 10.0, None,
     "Acquirer rotated cipher suites without notice.",
     "Intermittent card declines for one acquiring route."),
    ("Slow queries after index removed", "Core Customer Database", "Medium", "Human Error",
     "Database Engineering", "Closed", 38, 4, 30.0, None,
     "An index was dropped during maintenance on the wrong schema.",
     "Account search pages slow for internal users."),
    ("Token refresh errors in mobile app", "OAuth Token Service", "Medium", "Software Defect",
     "Identity & Access", "Closed", 34, 6, 12.0, None,
     "Clock-skew validation too strict after a library upgrade.",
     "Mobile users logged out unexpectedly."),
    ("Core switch failure in secondary data centre", "Payment Settlement Engine", "High", "Network",
     "Network Operations", "Closed", 30, 1, 4.0, None,
     "Hardware failure on a core switch; traffic re-routed to primary site.",
     "Settlement processing paused for 4 hours."),
    ("API developer portal unavailable", "Public REST API", "Low", "Infrastructure Failure",
     "Cloud Infrastructure", "Closed", 27, 5, 40.0, None,
     "Static hosting bucket permissions changed by automation.",
     "Developers unable to view API documentation."),
    ("Settlement file rejected by clearing partner", "Payment Settlement Engine", "Medium", "Third-Party Provider",
     "Payments Platform", "Closed", 23, 3, 18.0, None,
     "Partner introduced a new mandatory field in the file specification.",
     "Settlement for a single scheme delayed by 18 hours."),
    ("Ledger backup job failures", "Transactions Ledger DB", "Low", "Configuration Change",
     "Database Engineering", "Resolved", 20, 0, 96.0, None,
     "Backup credentials rotated but the job configuration was not updated.",
     "No customer impact; recovery point objective at risk."),
    ("Refund API timeouts", "Card Payment Gateway", "Medium", "Capacity / Performance",
     "Payments Platform", "Resolved", 16, 2, 8.0, None,
     "Refund workers under-provisioned after an autoscaling policy change.",
     "Refunds delayed; ~2% failed and were retried."),
    ("SSO session invalidation bug", "Single Sign-On (SSO)", "Medium", "Software Defect",
     "Identity & Access", "Resolved", 12, 4, 14.0, None,
     "Logout in one application terminated sessions across all applications.",
     "Users repeatedly prompted to log in."),
    ("Ledger replication lag increasing", "Transactions Ledger DB", "High", "Under Investigation",
     "Database Engineering", "Investigating", 2, 3, None, "Triaged",
     "Replica lag growing steadily; reporting queries pointed at primary as mitigation.",
     "Reporting dashboards stale; no transaction loss."),
    ("Webhook signature validation errors", "Partner Webhooks API", "Medium", "Software Defect",
     "API Gateway Team", "Mitigating", 1, 6, None, "Recovering",
     "Signature header encoding changed in last deploy; hotfix in progress.",
     "Some partners rejecting webhook payloads."),
    ("Intermittent card declines on gateway", "Card Payment Gateway", "Critical", "Under Investigation",
     "Payments Platform", "Investigating", 0, 2, None, "Contained",
     "Decline rate up 4x on one processing cluster; cluster drained.",
     "Approximately 3% of card transactions declined."),
    ("MFA push notifications delayed", "MFA Service", "Low", "Third-Party Provider",
     "Identity & Access", "Open", 0, 20, None, "Detected",
     "Push notification provider reporting degraded performance.",
     "Push approvals take up to 60 seconds; SMS fallback available."),
    ("Merchant payout report data stale", "Merchant Payouts Service", "Low", "Software Defect",
     "Payments Platform", "Open", 5, 0, None, "Triaged",
     "Report generation job silently failing since a dependency upgrade.",
     "Merchants see yesterday's payout data in the portal."),
    ("Database connection pool exhaustion", "Core Customer Database", "High", "Capacity / Performance",
     "Database Engineering", "Mitigating", 0, 6, None, "Recovering",
     "Connection leak in a new microservice exhausted the pool.",
     "Intermittent errors on customer profile pages."),
]


def seed_incidents() -> None:
    current = now()
    with get_conn() as conn:
        for n, row in enumerate(SEED):
            (title, service, sev, cause, team, status, days_ago, hrs_extra, dur,
             stage, desc, impact) = row
            reported = current - timedelta(days=days_ago, hours=hrs_extra)
            resolved = reported + timedelta(hours=dur) if dur is not None else None
            if status == "Closed":
                stage = "Post-Incident Review"
            elif status == "Resolved":
                stage = "Restored"
            progress = RECOVERY_STAGES[stage]
            inc_id = f"INC-{1001 + n}"
            conn.execute(
                """INSERT INTO incidents (id, title, service, severity, status, reported_at, resolved_at,
                   root_cause, assigned_team, description, customer_impact, recovery_stage,
                   recovery_progress, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (inc_id, title, service, sev, status, reported.strftime(DT_FMT),
                 resolved.strftime(DT_FMT) if resolved else None, cause, team, desc, impact,
                 stage, progress, reported.strftime(DT_FMT), current.strftime(DT_FMT)),
            )
            # Build a plausible recovery timeline
            stages = list(RECOVERY_STAGES)
            last_idx = stages.index(stage)
            end = resolved or current
            span = (end - reported).total_seconds()
            for i, st_name in enumerate(stages[: last_idx + 1]):
                frac = 0 if last_idx == 0 else i / last_idx
                if st_name == "Post-Incident Review" and resolved:
                    ts = resolved + timedelta(days=2)
                    if ts > current:
                        ts = current
                else:
                    ts = reported + timedelta(seconds=span * frac * (0.9 if resolved is None else 1))
                note = {
                    "Detected": "Alert raised by monitoring; incident opened.",
                    "Triaged": f"Severity confirmed as {sev}; {team} engaged.",
                    "Contained": "Impact contained; workaround or traffic shift in place.",
                    "Recovering": "Fix being deployed; service recovering.",
                    "Restored": "Service restored and verified by monitoring.",
                    "Post-Incident Review": "Post-incident review completed; actions tracked.",
                }[st_name]
                conn.execute(
                    "INSERT INTO incident_updates (incident_id, logged_at, stage, progress, note) VALUES (?,?,?,?,?)",
                    (inc_id, ts.strftime(DT_FMT), st_name, RECOVERY_STAGES[st_name], note),
                )
