"""Validation Tool: check the schema of an LLM result, normalise it, and record warnings.

After this step every active criterion has exactly one entry with a numeric score in
0..max_score. Missing or malformed results become score 0 with valid=False, so they are
never used as a peer benchmark.
"""
import math

MAX_TEXT = 1000


def _to_int(value):
    try:
        if isinstance(value, bool):
            return None
        number = float(value)
        return int(number) if number == int(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _to_score(value):
    """Return a finite float or None."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(str(value).strip()) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _text(value):
    if value is None:
        return ""
    return str(value).strip()[:MAX_TEXT]


def validate_llm_result(raw, criteria, supplier_name):
    """Return (normalised_result, warnings). Never raises."""
    warnings = []

    def warn(message):
        warnings.append(f"{supplier_name}: {message}")

    if not isinstance(raw, dict):
        warn("no usable result from the evaluation model; all criteria scored 0.")
        raw = {}
    items = raw.get("criteria")
    if not isinstance(items, list):
        if raw:
            warn("'criteria' is missing or not a list; all criteria scored 0.")
        items = []

    valid_ids = {c["criterion_id"] for c in criteria}
    found = {}
    for item in items:
        if not isinstance(item, dict):
            warn("ignored a criterion entry that was not an object.")
            continue
        cid = _to_int(item.get("criterion_id"))
        if cid is None:
            warn(f"ignored an entry with invalid criterion_id {item.get('criterion_id')!r}.")
        elif cid not in valid_ids:
            warn(f"ignored result for unknown criterion_id {cid}.")
        elif cid in found:
            warn(f"duplicate result for criterion_id {cid}; kept the first one.")
        else:
            found[cid] = item

    normalised = []
    for c in criteria:
        item = found.get(c["criterion_id"])
        entry = {"criterion_id": c["criterion_id"], "name": c["name"], "weight": c["weight"],
                 "max_score": c["max_score"], "score": 0.0, "valid": False,
                 "justification": "", "evidence": "No evidence found"}
        if item is None:
            warn(f"missing result for '{c['name']}'; scored 0 and excluded from benchmarks.")
        else:
            score = _to_score(item.get("score"))
            if score is None:
                warn(f"score for '{c['name']}' is not a valid number ({item.get('score')!r}); scored 0.")
                entry["justification"] = "Score was missing or malformed in the model output."
            else:
                limit = c["max_score"]
                if score < 0 or score > limit:
                    clipped = min(max(score, 0.0), limit)
                    warn(f"score {score:g} for '{c['name']}' is outside 0..{limit:g}; clipped to {clipped:g}.")
                    score = clipped
                reported_max = _to_score(item.get("max_score"))
                if reported_max is not None and reported_max != limit:
                    warn(f"model reported max_score {reported_max:g} for '{c['name']}'; "
                         f"using the configured {limit:g}.")
                entry.update(score=round(score, 2), valid=True,
                             justification=_text(item.get("justification")),
                             evidence=_text(item.get("evidence")) or "No evidence found")
                if score > 0 and entry["evidence"].lower().startswith("no evidence"):
                    warn(f"'{c['name']}' has a score of {score:g} but no supporting evidence.")
        normalised.append(entry)

    risks = raw.get("risks")
    if isinstance(risks, str):
        risks = [risks]
    elif not isinstance(risks, list):
        risks = []
    reported_name = raw.get("supplier_name")
    if reported_name and str(reported_name).strip().lower() != supplier_name.strip().lower():
        warn(f"model returned supplier_name {reported_name!r}; using the entered name.")

    result = {"supplier_name": supplier_name, "criteria": normalised,
              "risks": [_text(r) for r in risks if _text(r)],
              "overall_summary": _text(raw.get("overall_summary"))}
    return result, warnings


if __name__ == "__main__":
    import db

    db.init_db()
    active = db.get_active_criteria()
    cases = {
        "Perfect result": {"supplier_name": "Demo", "criteria": [
            {"criterion_id": c["criterion_id"], "score": 7, "max_score": 10,
             "justification": "ok", "evidence": "quote"} for c in active]},
        "Messy result": {"supplier_name": "Demo", "criteria": [
            {"criterion_id": 1, "score": 14, "max_score": 10, "justification": "x", "evidence": "y"},
            {"criterion_id": "2", "score": "8", "justification": "x", "evidence": "y"},
            {"criterion_id": 3, "score": "excellent", "justification": "x", "evidence": "y"},
            {"criterion_id": 3, "score": 5, "justification": "duplicate", "evidence": "y"},
            {"criterion_id": 4, "score": -2, "justification": "x", "evidence": "y"},
            {"criterion_id": 99, "score": 5}]},
        "Not JSON at all": None,
    }
    for label, raw in cases.items():
        result, warns = validate_llm_result(raw, active, "Demo")
        print(f"\n=== {label} ===")
        for r in result["criteria"]:
            print(f"  {r['name']:24} score={r['score']:<5} valid={r['valid']}")
        print(f"  warnings ({len(warns)}):")
        for w in warns:
            print("   -", w)
