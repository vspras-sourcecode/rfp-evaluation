"""Orchestrator Agent: controls the workflow and calls the tools in a fixed order.

  load criteria -> create run -> for each supplier: document tool -> evaluation agent -> validation tool
  -> ranking tool (all suppliers) -> persist to SQLite -> return the complete result

The LLM is used only inside the evaluation agent. Every number after validation comes from ranking.py.
"""
import json
from datetime import date, datetime

import db
from llm_agent import DEFAULT_MODEL, evaluate_supplier
from pdf_tool import extract_pdf_text
from ranking import TIE_BREAK_ORDER, rank_suppliers
from validation import validate_llm_result

FORMULAS = {
    "absolute_score": "sum(score / max_score * weight)",
    "benchmark": "highest valid score for the criterion across all suppliers",
    "gap": "score - benchmark",
    "relative_pct": "score / benchmark * 100 (100 when benchmark is 0)",
    "ppi": "sum(relative_pct * weight) / sum(weights)",
}


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def check_inputs(supplier_inputs, criteria):
    """Return a list of human-readable problems. An empty list means the run may start."""
    errors = []
    if not criteria:
        errors.append("There are no active evaluation criteria.")
    else:
        total = sum(c["weight"] for c in criteria)
        if abs(total - 100) > 0.01:
            errors.append(f"Active criteria weights total {total:g}%, but they must total 100%.")
        if any(c["max_score"] <= 0 for c in criteria):
            errors.append("Every active criterion needs a maximum score above 0.")
    if len(supplier_inputs) < 2:
        errors.append("Upload at least two supplier PDFs; peer benchmarking needs a comparison group.")
    seen = set()
    for i, s in enumerate(supplier_inputs, start=1):
        name = (s.get("supplier_name") or "").strip()
        label = name or f"Supplier #{i}"
        if not name:
            errors.append(f"Supplier #{i}: supplier name is required.")
        elif name.casefold() in seen:
            errors.append(f"Duplicate supplier name: {name}.")
        seen.add(name.casefold())
        if _parse_date(s.get("submission_date")) is None:
            errors.append(f"{label}: submission date is missing or invalid.")
        try:
            rating = float(s.get("experience_rating"))
            if not 0 <= rating <= 5:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"{label}: experience rating must be a number from 0 to 5.")
        if s.get("file") is None:
            errors.append(f"{label}: no PDF attached.")
    return errors


def run_evaluation(supplier_inputs, provider="mock", api_key=None, model=None, progress=None):
    """supplier_inputs: list of {supplier_name, submission_date, experience_rating, file, filename}."""
    criteria = db.get_active_criteria()          # always reload the LATEST active criteria
    errors = check_inputs(supplier_inputs, criteria)
    if errors:
        raise ValueError(" | ".join(errors))

    trace, all_warnings = [], []
    note = progress or (lambda fraction, message: None)
    run_id = db.create_run(criteria)
    total = sum(c["weight"] for c in criteria)
    trace.append(f"load_criteria: {len(criteria)} active criteria, weights total {total:g}%")
    trace.append(f"create_run: {run_id}")

    try:
        entries, documents, per_supplier_warnings = [], {}, {}
        n = len(supplier_inputs)
        for i, s in enumerate(supplier_inputs):
            name = s["supplier_name"].strip()
            note(i / (n + 1), f"Reading and evaluating {name} ({i + 1}/{n})")
            doc = extract_pdf_text(s["file"])
            documents[name] = {"filename": s.get("filename", ""), "pages": doc["pages"], "chars": doc["chars"]}
            trace.append(f"document_tool: {name} ({doc['pages']} pages, {doc['chars']} characters)")
            warns = [f"{name}: {w}" for w in doc["warnings"]]

            raw, llm_warns = (None, []) if not doc["ok"] else evaluate_supplier(
                criteria, name, doc["text"], provider, api_key, model)
            warns += [f"{name}: {w}" for w in llm_warns]
            trace.append(f"evaluation_agent[{provider}]: {name} -> "
                         f"{'result received' if raw is not None else 'no result'}")

            result, val_warns = validate_llm_result(raw, criteria, name)
            warns += val_warns
            trace.append(f"validation_tool: {name} ({len(val_warns)} warnings)")

            per_supplier_warnings[name] = warns
            all_warnings += warns
            entries.append({"supplier_name": name,
                            "submission_date": _parse_date(s["submission_date"]).isoformat(),
                            "experience_rating": float(s["experience_rating"]), "result": result})

        note(n / (n + 1), "Calculating benchmarks, PPI and ranks")
        ranked = rank_suppliers(entries)
        trace.append(f"ranking_tool: {len(entries)} suppliers ranked; {len(ranked['benchmarks'])} benchmarks")
        all_warnings += ranked["warnings"]

        for row in ranked["suppliers"]:
            row["warnings"] = per_supplier_warnings.get(row["supplier_name"], [])
            row["document"] = documents.get(row["supplier_name"], {})
            db.save_supplier_result(run_id, row["supplier_name"], row["submission_date"],
                                    row["experience_rating"], row["absolute_score"], row["ppi"],
                                    row["final_rank"], row)
        status = "COMPLETED_WITH_WARNINGS" if all_warnings else "COMPLETED"
        db.set_run_status(run_id, status)
        trace.append(f"persist: {len(ranked['suppliers'])} rows saved; status {status}")
        note(1.0, "Done")
    except Exception:
        db.set_run_status(run_id, "FAILED")
        raise

    created = next((r["created_at"] for r in db.list_runs() if r["rfp_run_id"] == run_id), "")
    return {"rfp_run_id": run_id, "created_at": created, "status": status, "provider": provider,
            "model": (model or DEFAULT_MODEL) if provider == "claude" else "offline-demo-scorer",
            "criteria": criteria, "formulas": FORMULAS, "tie_break_order": TIE_BREAK_ORDER,
            "benchmarks": ranked["benchmarks"], "suppliers": ranked["suppliers"],
            "tie_break_notes": ranked["tie_break_notes"], "warnings": all_warnings, "trace": trace}


def load_run(run_id):
    """Rebuild a saved run from SQLite and re-run the ranking tool to prove it is reproducible."""
    run = next((r for r in db.list_runs() if r["rfp_run_id"] == run_id), None)
    stored = [json.loads(r["result_json"]) for r in db.load_run_results(run_id)]
    if run is None or not stored:
        return None
    entries = [{"supplier_name": s["supplier_name"], "submission_date": s["submission_date"],
                "experience_rating": s["experience_rating"],
                "result": {"criteria": s["criteria"], "risks": s["risks"],
                           "overall_summary": s["overall_summary"]}} for s in stored]
    ranked = rank_suppliers(entries)
    old = {s["supplier_name"]: s for s in stored}
    reproducible = all(old[r["supplier_name"]]["final_rank"] == r["final_rank"]
                       and old[r["supplier_name"]]["ppi"] == r["ppi"] for r in ranked["suppliers"])
    for row in ranked["suppliers"]:
        row["warnings"] = old[row["supplier_name"]].get("warnings", [])
        row["document"] = old[row["supplier_name"]].get("document", {})
    warnings = [w for r in ranked["suppliers"] for w in r["warnings"]] + ranked["warnings"]
    return {"rfp_run_id": run_id, "created_at": run["created_at"], "status": run["status"],
            "provider": "(loaded from database)", "model": "", "criteria": json.loads(run["criteria_snapshot"] or "[]"),
            "formulas": FORMULAS, "tie_break_order": TIE_BREAK_ORDER, "benchmarks": ranked["benchmarks"],
            "suppliers": ranked["suppliers"], "tie_break_notes": ranked["tie_break_notes"],
            "warnings": warnings, "trace": [], "reproducible": reproducible}


def to_json(run_output):
    return json.dumps(run_output, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import io

    db.init_db()
    files = {"Apex Systems": ("Apex_Systems", "2026-03-02", 4.5), "BrightPath Tech": ("BrightPath_Tech", "2026-03-03", 2.5),
             "NexaWorks": ("NexaWorks", "2026-03-01", 4.0), "Orbit Digital": ("Orbit_Digital", "2026-03-04", 4.8)}
    inputs = [{"supplier_name": n, "submission_date": d, "experience_rating": x,
               "file": f"sample_pdfs/{f}.pdf", "filename": f"{f}.pdf"} for n, (f, d, x) in files.items()]

    print("=== SUCCESSFUL RUN ===")
    out = run_evaluation(inputs, provider="mock")
    print("Run:", out["rfp_run_id"], "| status:", out["status"])
    for r in out["suppliers"]:
        print(f"  #{r['final_rank']} {r['supplier_name']:16} absolute={r['absolute_score']:6.2f} PPI={r['ppi']:6.2f}")
    print("Trace:")
    for step in out["trace"]:
        print("  -", step)
    again = load_run(out["rfp_run_id"])
    print("Reloaded from SQLite, reproducible:", again["reproducible"])

    print("\n=== ERROR CASE 1: bad inputs ===")
    bad = [dict(inputs[0], supplier_name=" "), dict(inputs[1], experience_rating=9),
           dict(inputs[1], supplier_name="BrightPath Tech", submission_date="not a date")]
    for e in check_inputs(bad, db.get_active_criteria()):
        print("  -", e)

    print("\n=== ERROR CASE 2: unreadable PDF in the batch ===")
    broken = [dict(inputs[0]), dict(inputs[1], file=io.BytesIO(b"not a pdf"), filename="broken.pdf")]
    out2 = run_evaluation(broken, provider="mock")
    print("Status:", out2["status"])
    for w in out2["warnings"][:4]:
        print("  -", w)
