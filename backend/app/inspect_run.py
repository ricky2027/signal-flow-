"""Read-only run forensics; excludes login sessions, tokens and credentials.

uv run python -m app.inspect_run [--run-id UUID]
Accepts a full run UUID or unique prefix of at least eight hex characters.
Defaults to the latest run. Never claims or executes a queued job.
"""

import argparse
import json
import re
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.db import engine
from app.models import Run, Artifact, Event, Job, SourceRecord, ClaimRecord, SignalRecord
from app.store import detail
from app.policy import evidence_gate, rank
from app.schemas import ReviewedEvidence as Evidence, Candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.run_id and not re.fullmatch(r"[0-9a-fA-F-]{8,36}", args.run_id):
        print(json.dumps({"error": "invalid_run_id"}))
        return 1
    try:
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                connection.execute(text("SET TRANSACTION READ ONLY"))
            with Session(bind=connection) as db:
                query = select(Run)
                if args.run_id:
                    query = query.where(Run.id.startswith(args.run_id.lower()))
                matches = db.scalars(query.order_by(Run.created_at.desc()).limit(2 if args.run_id else 1)).all()
                if len(matches) > 1:
                    print(json.dumps({"error": "ambiguous_run_id", "matching_ids": [r.id for r in matches]}))
                    return 1
                run = matches[0] if matches else None
                if not run:
                    print(json.dumps({"error": "run_not_found"}))
                    return 1
                result = {
                    "run": detail(db, run),
                    "artifacts": [
                        {"kind": a.kind, "created_at": a.created_at, "data": a.data}
                        for a in db.scalars(select(Artifact).where(Artifact.run_id == run.id).order_by(Artifact.created_at, Artifact.id))
                    ],
                    "events": [
                        {"sequence": e.sequence, "type": e.type, "stage": e.stage, "occurred_at": e.occurred_at, "payload": e.payload}
                        for e in db.scalars(select(Event).where(Event.run_id == run.id).order_by(Event.sequence))
                    ],
                    "jobs": [
                        {"kind": j.kind, "status": j.status, "lease_expires_at": j.lease_expires_at}
                        for j in db.scalars(select(Job).where(Job.run_id == run.id))
                    ],
                    "relational_records": {
                        name: [row.data for row in db.scalars(select(model).where(model.run_id == run.id))]
                        for name, model in (("sources", SourceRecord), ("claims", ClaimRecord), ("signals", SignalRecord))
                    },
                }
                evidence = next((a["data"] for a in reversed(result["artifacts"]) if a["kind"] == "evidence"), None)
                if evidence:
                    parsed = Evidence.model_validate(evidence)
                    gate_outcome, reasons = evidence_gate(parsed)
                    candidates = [Candidate.model_validate({k: value for k, value in signal.items() if k in Candidate.model_fields}) for signal in result["run"]["signals"]]
                    as_of = (run.started_at or run.created_at).date()
                    scores, outcome = rank(parsed, candidates, as_of)
                    result["deterministic_policy_replay"] = {
                        "as_of": str(as_of), "gate_outcome": gate_outcome,
                        "gate_reasons": reasons, "scored_existing_candidates": scores,
                        "outcome": outcome,
                        "note": "Replays saved facts/candidates only; does not generate missing evidence or signals.",
                    }
                print(json.dumps(result, indent=2, default=str))
                return 0
    except Exception as exc:
        message = str(exc).lower()
        reason = (
            "dns_resolution_failed" if any(t in message for t in ("translate host", "resolve host", "nodename nor servname", "name resolution"))
            else "connection_permission_denied" if "operation not permitted" in message or "permission denied" in message
            else "connection_timeout" if "timeout" in message or "timed out" in message
            else "database_connection_or_schema_error"
        )
        print(json.dumps({"error": "inspection_unavailable", "exception_type": type(exc).__name__, "reason": reason}))
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
