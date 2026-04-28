"""
Verify LLM experiment outputs (c1, c2, c3) for all 12 Gold papers.
Just run: python verify_experiment.py
"""

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
VALIDATION_DIR = SCRIPT_DIR.parent
EXPERIMENT_DIR = VALIDATION_DIR / "llm_experiment"
GOLD_DIR = VALIDATION_DIR / "gold"

GOLD_IDS = [
    "study001", "study002", "study003", "study005", "study006", "study008",
    "study009", "study013", "study015", "study017", "study020", "study022"
]
CONDITIONS = ["c1", "c2", "c3"]
COND_NAMES = {"c1": "Generic", "c2": "DCAT+PROV", "c3": "RDIP"}
ENTITY_TYPES = [
    "SoftwareApplication", "Dataset", "Method", "Person", "Organization",
    "Parameter", "RandomSeed", "ComputingEnvironment", "EvaluationResult", "Activity"
]


def count_entities(data):
    counts = {}
    for et in ENTITY_TYPES:
        counts[et] = len(data.get("entities", {}).get(et, []))
    counts["relations"] = len(data.get("relations", []))
    counts["total"] = sum(v for k, v in counts.items() if k != "relations")
    return counts


def main():
    print(f"Experiment dir: {EXPERIMENT_DIR}\n")

    ok, errors, empty = 0, 0, 0
    all_counts = {c: [] for c in CONDITIONS}

    for sid in GOLD_IDS:
        study_dir = EXPERIMENT_DIR / sid / "outputs"
        if not study_dir.exists():
            study_dir = EXPERIMENT_DIR / sid  # fallback if no outputs/ subfolder

        for cid in CONDITIONS:
            out_path = study_dir / f"{cid}_output.json"

            if not out_path.exists():
                print(f"  ✗ {sid}/{cid}: FILE MISSING")
                errors += 1
                continue

            try:
                with open(out_path) as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"  ✗ {sid}/{cid}: INVALID JSON — {e}")
                errors += 1
                continue

            if data == {}:
                print(f"  ○ {sid}/{cid}: EMPTY (not done yet)")
                empty += 1
                continue

            if "entities" not in data:
                print(f"  ⚠ {sid}/{cid}: no 'entities' key — wrong format?")
                errors += 1
                continue

            counts = count_entities(data)
            all_counts[cid].append({"study_id": sid, **counts})
            ok += 1

    # ═══════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════
    total_expected = len(GOLD_IDS) * len(CONDITIONS)
    print(f"\n{'='*70}")
    print(f"  EXPERIMENT VERIFICATION")
    print(f"{'='*70}")
    print(f"  Expected: {total_expected} files (12 papers × 3 conditions)")
    print(f"  Valid:    {ok}")
    print(f"  Empty:    {empty}")
    print(f"  Errors:   {errors}")

    # ═══════════════════════════════════════════════════
    # PER-CONDITION ENTITY COUNTS
    # ═══════════════════════════════════════════════════
    for cid in CONDITIONS:
        entries = all_counts[cid]
        if not entries:
            continue
        print(f"\n  {cid.upper()} — {COND_NAMES[cid]}:")
        print(f"  {'Study':<12} {'SW':>3} {'DS':>3} {'Met':>3} {'Par':>3} {'Sd':>3} {'Env':>3} {'Res':>3} {'Act':>3} {'Ppl':>3} {'Org':>3} {'Rel':>3} {'Tot':>4}")
        print(f"  {'-'*62}")
        for e in entries:
            print(f"  {e['study_id']:<12} "
                  f"{e['SoftwareApplication']:>3} {e['Dataset']:>3} {e['Method']:>3} "
                  f"{e['Parameter']:>3} {e['RandomSeed']:>3} {e['ComputingEnvironment']:>3} "
                  f"{e['EvaluationResult']:>3} {e['Activity']:>3} {e['Person']:>3} "
                  f"{e['Organization']:>3} {e['relations']:>3} {e['total']:>4}")
        n = len(entries)
        print(f"  {'-'*62}")
        print(f"  {'AVERAGE':<12} "
              + " ".join(f"{sum(e[et] for e in entries)/n:>3.0f}" for et in ENTITY_TYPES)
              + f" {sum(e['relations'] for e in entries)/n:>3.0f}"
              + f" {sum(e['total'] for e in entries)/n:>4.0f}")
        print(f"  {'TOTAL':<12} "
              + " ".join(f"{sum(e[et] for e in entries):>3}" for et in ENTITY_TYPES)
              + f" {sum(e['relations'] for e in entries):>3}"
              + f" {sum(e['total'] for e in entries):>4}")

    # ═══════════════════════════════════════════════════
    # QUICK COMPARISON vs GOLD
    # ═══════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"  GOLD vs CONDITIONS (entity totals per paper)")
    print(f"{'='*70}")
    print(f"  {'Study':<12} {'Gold':>5} {'C1':>5} {'C2':>5} {'C3':>5}")
    print(f"  {'-'*34}")

    gold_totals = []
    for sid in GOLD_IDS:
        gold_path = GOLD_DIR / sid / "gold_standard.json"
        gold_total = 0
        if gold_path.exists():
            with open(gold_path) as f:
                gdata = json.load(f)
            gold_total = sum(len(gdata.get("entities", {}).get(et, [])) for et in ENTITY_TYPES)

        c_totals = {}
        for cid in CONDITIONS:
            entries = [e for e in all_counts[cid] if e["study_id"] == sid]
            c_totals[cid] = entries[0]["total"] if entries else 0

        gold_totals.append(gold_total)
        print(f"  {sid:<12} {gold_total:>5} {c_totals['c1']:>5} {c_totals['c2']:>5} {c_totals['c3']:>5}")

    print(f"  {'-'*34}")
    c1_tot = sum(e["total"] for e in all_counts["c1"])
    c2_tot = sum(e["total"] for e in all_counts["c2"])
    c3_tot = sum(e["total"] for e in all_counts["c3"])
    g_tot = sum(gold_totals)
    print(f"  {'TOTAL':<12} {g_tot:>5} {c1_tot:>5} {c2_tot:>5} {c3_tot:>5}")

    if ok == total_expected:
        print(f"\n  ✓ All {total_expected} files valid. Ready to run score_llm.py")
    else:
        print(f"\n  ⚠ {total_expected - ok} files need attention before scoring")

    print(f"{'='*70}")


if __name__ == "__main__":
    main()
