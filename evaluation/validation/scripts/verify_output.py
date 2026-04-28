#!/usr/bin/env python3
"""
Verify all gold_standard.json files against repo_list.csv.
Just run: python verify_outputs.py
"""

import csv
import json
import os
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
VALIDATION_DIR = SCRIPT_DIR.parent
CSV_PATH = VALIDATION_DIR / "repo_list.csv"
SILVER_DIR = VALIDATION_DIR / "silver"


def count_uncertains(data, path=""):
    """Recursively count [UNCERTAIN] in all string values."""
    count = 0
    locations = []
    if isinstance(data, dict):
        for k, v in data.items():
            c, l = count_uncertains(v, f"{path}.{k}")
            count += c
            locations.extend(l)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            c, l = count_uncertains(v, f"{path}[{i}]")
            count += c
            locations.extend(l)
    elif isinstance(data, str):
        matches = len(re.findall(r'\[UNCERTAIN\]', data, re.IGNORECASE))
        if matches > 0:
            count += matches
            locations.append(f"{path}: {data[:80]}")
    return count, locations


def normalize_title(title):
    """Normalize title for fuzzy comparison."""
    return re.sub(r'[^a-z0-9]', '', title.lower().strip())


def main():
    # Load CSV
    csv_papers = {}
    with open(CSV_PATH, newline="") as f:
        for row in csv.DictReader(f):
            sid = row.get("study_id", "").strip()
            if sid:
                csv_papers[sid] = row.get("paper_title", "").strip()

    print(f"CSV: {len(csv_papers)} papers")
    print(f"Silver: {SILVER_DIR}\n")

    # Track issues
    ok, warnings, errors = 0, 0, 0
    missing = []
    empty = []
    id_mismatch = []
    title_mismatch = []
    uncertain_papers = []
    entity_counts = []

    for sid in sorted(csv_papers.keys()):
        gs_path = SILVER_DIR / sid / "gold_standard.json"

        # Check file exists
        if not gs_path.exists():
            missing.append(sid)
            errors += 1
            continue

        # Load JSON
        try:
            with open(gs_path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"  ✗ {sid}: INVALID JSON — {e}")
            errors += 1
            continue

        # Check if empty
        if data == {} or data == {"study_id": sid}:
            empty.append(sid)
            continue

        issues = []

        # Check study_id
        json_sid = data.get("study_id", "").strip()
        if json_sid and json_sid != sid:
            id_mismatch.append((sid, json_sid))
            issues.append(f"study_id mismatch: folder={sid}, json={json_sid}")

        # Check title
        csv_title = csv_papers[sid]
        json_title = data.get("project", {}).get("title", "").strip()
        if json_title:
            csv_norm = normalize_title(csv_title)
            json_norm = normalize_title(json_title)
            # Check if one contains the other (titles may be truncated or extended)
            if csv_norm and json_norm:
                if csv_norm not in json_norm and json_norm not in csv_norm:
                    # Compute simple overlap ratio
                    csv_words = set(csv_title.lower().split())
                    json_words = set(json_title.lower().split())
                    overlap = len(csv_words & json_words)
                    total = max(len(csv_words), len(json_words))
                    ratio = overlap / total if total > 0 else 0
                    if ratio < 0.5:
                        title_mismatch.append((sid, csv_title[:60], json_title[:60]))
                        issues.append("title mismatch")

        # Count uncertains
        unc_count, unc_locations = count_uncertains(data)
        if unc_count > 0:
            uncertain_papers.append((sid, unc_count, unc_locations))

        # Count entities
        entities = data.get("entities", {})
        n_sw = len(entities.get("SoftwareApplication", []))
        n_ds = len(entities.get("Dataset", []))
        n_met = len(entities.get("Method", []))
        n_par = len(entities.get("Parameter", []))
        n_seed = len(entities.get("RandomSeed", []))
        n_env = len(entities.get("ComputingEnvironment", []))
        n_res = len(entities.get("EvaluationResult", []))
        n_act = len(entities.get("Activity", []))
        n_ppl = len(entities.get("Person", []))
        n_org = len(entities.get("Organization", []))
        n_rel = len(data.get("relations", []))
        total_ent = n_sw + n_ds + n_met + n_par + n_seed + n_env + n_res + n_act + n_ppl + n_org

        entity_counts.append({
            "study_id": sid,
            "software": n_sw, "datasets": n_ds, "methods": n_met,
            "params": n_par, "seeds": n_seed, "env": n_env,
            "results": n_res, "activities": n_act, "people": n_ppl,
            "orgs": n_org, "relations": n_rel, "total": total_ent,
            "uncertains": unc_count,
        })

        if issues:
            warnings += 1
        else:
            ok += 1

    # ═══════════════════════════════════════════════════
    # REPORT
    # ═══════════════════════════════════════════════════

    print("=" * 70)
    print("  VERIFICATION REPORT")
    print("=" * 70)

    # Summary
    print(f"\n  Total in CSV:     {len(csv_papers)}")
    print(f"  Verified OK:      {ok}")
    print(f"  Warnings:         {warnings}")
    print(f"  Errors:           {errors}")
    print(f"  Empty (not done): {len(empty)}")
    print(f"  Missing files:    {len(missing)}")

    # Missing
    if missing:
        print(f"\n  MISSING gold_standard.json:")
        for sid in missing:
            print(f"    ✗ {sid}")

    # Empty
    if empty:
        print(f"\n  EMPTY (still {{}}): {len(empty)} papers")
        for sid in empty:
            print(f"    ○ {sid}")

    # ID mismatches
    if id_mismatch:
        print(f"\n  STUDY_ID MISMATCHES:")
        for folder, json_id in id_mismatch:
            print(f"    ✗ folder={folder}  json={json_id}")

    # Title mismatches
    if title_mismatch:
        print(f"\n  TITLE MISMATCHES:")
        for sid, csv_t, json_t in title_mismatch:
            print(f"    ⚠ {sid}")
            print(f"      CSV:  {csv_t}")
            print(f"      JSON: {json_t}")

    # Uncertains
    if uncertain_papers:
        uncertain_papers.sort(key=lambda x: -x[1])
        print(f"\n  [UNCERTAIN] COUNTS:")
        print(f"  {'Study':<12} {'Count':>5}  Top locations")
        print(f"  {'-'*60}")
        for sid, count, locs in uncertain_papers:
            top = locs[0] if locs else ""
            # Clean up the location string
            top_clean = top.split(": ")[-1][:50] if top else ""
            print(f"  {sid:<12} {count:>5}  {top_clean}")
        total_unc = sum(c for _, c, _ in uncertain_papers)
        print(f"  {'-'*60}")
        print(f"  {'TOTAL':<12} {total_unc:>5}  across {len(uncertain_papers)} papers")

    # Entity statistics
    if entity_counts:
        print(f"\n  ENTITY STATISTICS:")
        print(f"  {'Study':<12} {'SW':>3} {'DS':>3} {'Met':>3} {'Par':>3} {'Sd':>3} {'Env':>3} {'Res':>3} {'Act':>3} {'Ppl':>3} {'Org':>3} {'Rel':>3} {'Tot':>4} {'Unc':>3}")
        print(f"  {'-'*72}")
        for e in entity_counts:
            print(f"  {e['study_id']:<12} {e['software']:>3} {e['datasets']:>3} {e['methods']:>3} "
                  f"{e['params']:>3} {e['seeds']:>3} {e['env']:>3} {e['results']:>3} "
                  f"{e['activities']:>3} {e['people']:>3} {e['orgs']:>3} {e['relations']:>3} "
                  f"{e['total']:>4} {e['uncertains']:>3}")

        # Averages
        n = len(entity_counts)
        print(f"  {'-'*72}")
        print(f"  {'AVERAGE':<12} "
              f"{sum(e['software'] for e in entity_counts)/n:>3.0f} "
              f"{sum(e['datasets'] for e in entity_counts)/n:>3.0f} "
              f"{sum(e['methods'] for e in entity_counts)/n:>3.0f} "
              f"{sum(e['params'] for e in entity_counts)/n:>3.0f} "
              f"{sum(e['seeds'] for e in entity_counts)/n:>3.0f} "
              f"{sum(e['env'] for e in entity_counts)/n:>3.0f} "
              f"{sum(e['results'] for e in entity_counts)/n:>3.0f} "
              f"{sum(e['activities'] for e in entity_counts)/n:>3.0f} "
              f"{sum(e['people'] for e in entity_counts)/n:>3.0f} "
              f"{sum(e['orgs'] for e in entity_counts)/n:>3.0f} "
              f"{sum(e['relations'] for e in entity_counts)/n:>3.0f} "
              f"{sum(e['total'] for e in entity_counts)/n:>4.0f} "
              f"{sum(e['uncertains'] for e in entity_counts)/n:>3.0f}")
        print(f"  {'TOTAL':<12} "
              f"{sum(e['software'] for e in entity_counts):>3} "
              f"{sum(e['datasets'] for e in entity_counts):>3} "
              f"{sum(e['methods'] for e in entity_counts):>3} "
              f"{sum(e['params'] for e in entity_counts):>3} "
              f"{sum(e['seeds'] for e in entity_counts):>3} "
              f"{sum(e['env'] for e in entity_counts):>3} "
              f"{sum(e['results'] for e in entity_counts):>3} "
              f"{sum(e['activities'] for e in entity_counts):>3} "
              f"{sum(e['people'] for e in entity_counts):>3} "
              f"{sum(e['orgs'] for e in entity_counts):>3} "
              f"{sum(e['relations'] for e in entity_counts):>3} "
              f"{sum(e['total'] for e in entity_counts):>4} "
              f"{sum(e['uncertains'] for e in entity_counts):>3}")

    # Papers with zero entities (suspicious)
    zero_ent = [e for e in entity_counts if e['total'] == 0]
    if zero_ent:
        print(f"\n  ⚠ SUSPICIOUS — 0 entities extracted:")
        for e in zero_ent:
            print(f"    {e['study_id']}")

    print(f"\n{'='*70}")


if __name__ == "__main__":
    main()