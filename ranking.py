"""Ranking Tool: deterministic arithmetic only. No LLM is involved in any calculation here.

Formulas
  absolute score   = sum( score / max_score * weight )                    (0..100 when weights sum to 100)
  benchmark        = highest VALID score for the criterion across all suppliers
  gap              = score - benchmark                                     (0 for the leader, otherwise negative)
  relative %       = score / benchmark * 100                               (100 if the benchmark is 0)
  PPI              = sum( relative % * weight ) / sum( weights )
Tie-break order: 1) higher PPI  2) earlier submission date  3) higher experience rating  4) name A-Z
"""
from datetime import date

PRECISION = 4
TIE_BREAK_ORDER = ("Higher PPI first, then earlier submission date, then higher historical "
                   "experience rating, then supplier name in ascending order.")


def _as_date(value):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return date.max


def _sort_key(s):
    return (-s["ppi"], _as_date(s["submission_date"]), -float(s["experience_rating"] or 0),
            s["supplier_name"].casefold(), s["supplier_name"])


def _decider(better, worse):
    """Explain which rule separated two suppliers that are tied on PPI."""
    d1, d2 = _as_date(better["submission_date"]), _as_date(worse["submission_date"])
    if d1 != d2:
        return (f"{better['supplier_name']} ranked above {worse['supplier_name']}: tied on PPI "
                f"({better['ppi']:.{PRECISION}f}); earlier submission date ({d1} vs {d2}).")
    e1, e2 = float(better["experience_rating"] or 0), float(worse["experience_rating"] or 0)
    if e1 != e2:
        return (f"{better['supplier_name']} ranked above {worse['supplier_name']}: tied on PPI and "
                f"submission date; higher experience rating ({e1:g} vs {e2:g}).")
    return (f"{better['supplier_name']} ranked above {worse['supplier_name']}: tied on PPI, submission "
            f"date and experience rating; supplier name in ascending order.")


def rank_suppliers(suppliers):
    """suppliers: list of {supplier_name, submission_date, experience_rating, result}
    where result is the validated output of validation.validate_llm_result.
    """
    warnings = []
    if not suppliers:
        return {"benchmarks": [], "suppliers": [], "tie_break_notes": [], "warnings": ["No suppliers to rank."]}

    # Benchmarks: best VALID score per criterion
    benchmarks = []
    for crit in suppliers[0]["result"]["criteria"]:
        cid = crit["criterion_id"]
        valid = [(e["score"], s["supplier_name"]) for s in suppliers
                 for e in s["result"]["criteria"] if e["criterion_id"] == cid and e["valid"]]
        best = max((v[0] for v in valid), default=0.0)
        if not valid:
            warnings.append(f"No valid scores for '{crit['name']}'; every supplier gets 100% relative performance.")
        benchmarks.append({
            "criterion_id": cid, "name": crit["name"], "weight": crit["weight"],
            "max_score": crit["max_score"], "benchmark_score": best,
            "leaders": sorted(n for sc, n in valid if sc == best and best > 0)})
    bench_by_id = {b["criterion_id"]: b["benchmark_score"] for b in benchmarks}

    rows = []
    for s in suppliers:
        absolute = weight_sum = ppi_num = 0.0
        details = []
        for e in s["result"]["criteria"]:
            bench = bench_by_id[e["criterion_id"]]
            points = e["score"] / e["max_score"] * e["weight"] if e["max_score"] > 0 else 0.0
            relative = e["score"] / bench * 100 if bench > 0 else 100.0
            absolute += points
            ppi_num += relative * e["weight"]
            weight_sum += e["weight"]
            details.append({**e, "benchmark": bench, "gap": round(e["score"] - bench, PRECISION),
                            "relative_pct": round(relative, PRECISION),
                            "weighted_points": round(points, PRECISION)})
        rows.append({"supplier_name": s["supplier_name"], "submission_date": str(s["submission_date"]),
                     "experience_rating": s["experience_rating"],
                     "absolute_score": round(absolute, PRECISION),
                     "ppi": round(ppi_num / weight_sum if weight_sum else 0.0, PRECISION),
                     "criteria": details, "risks": s["result"]["risks"],
                     "overall_summary": s["result"]["overall_summary"]})

    rows.sort(key=_sort_key)
    for position, row in enumerate(rows, start=1):
        row["final_rank"] = position

    notes = [_decider(a, b) for a, b in zip(rows, rows[1:]) if a["ppi"] == b["ppi"]]
    if not notes:
        notes = ["No suppliers were tied on PPI, so no tie-break rule was needed."]
    return {"benchmarks": benchmarks, "suppliers": rows, "tie_break_notes": notes, "warnings": warnings}


if __name__ == "__main__":
    import db
    from llm_agent import evaluate_supplier
    from pdf_tool import extract_pdf_text
    from validation import validate_llm_result

    db.init_db()
    active = db.get_active_criteria()
    meta = {"Apex Systems": ("Apex_Systems", "2026-03-02", 4.5),
            "BrightPath Tech": ("BrightPath_Tech", "2026-03-03", 2.5),
            "NexaWorks": ("NexaWorks", "2026-03-01", 4.0),
            "Orbit Digital": ("Orbit_Digital", "2026-03-04", 4.8)}
    entries = []
    for name, (fname, when, exp) in meta.items():
        text = extract_pdf_text(f"sample_pdfs/{fname}.pdf")["text"]
        raw, _ = evaluate_supplier(active, name, text, "mock")
        result, _ = validate_llm_result(raw, active, name)
        entries.append({"supplier_name": name, "submission_date": when, "experience_rating": exp, "result": result})
    out = rank_suppliers(entries)
    print("LEADERBOARD")
    for r in out["suppliers"]:
        print(f"  #{r['final_rank']} {r['supplier_name']:16} absolute={r['absolute_score']:7.2f}  PPI={r['ppi']:7.2f}  "
              f"date={r['submission_date']}  exp={r['experience_rating']}")
    print("BENCHMARKS:", {b["name"]: b["benchmark_score"] for b in out["benchmarks"]})
    print("NOTES:", out["tie_break_notes"])

    print("\nTIE-BREAK DEMO (identical scores)")
    clone = entries[0]["result"]
    tie = [{"supplier_name": n, "submission_date": d, "experience_rating": x, "result": clone}
           for n, d, x in [("Zeta", "2026-03-05", 3), ("Alpha", "2026-03-05", 3),
                           ("Mid", "2026-03-05", 4), ("Early", "2026-03-01", 1)]]
    out2 = rank_suppliers(tie)
    for r in out2["suppliers"]:
        print(f"  #{r['final_rank']} {r['supplier_name']}  PPI={r['ppi']}")
    for n in out2["tie_break_notes"]:
        print("  -", n)
