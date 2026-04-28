#!/usr/bin/env python3
"""
Analyze RDIP schema coverage across all silver annotations.
Usage: python analyze_coverage.py --input-dir silver --csv repo_list.csv --output coverage_summary.md
"""
import json, os, csv, argparse
from collections import defaultdict

CONCEPTS = [
    ("SoftwareApplication", "entities", "Has named software"),
    ("SoftwareVersion", "entities", "Software has version string"),
    ("SoftwareDependency", "entities", "Lists library dependencies"),
    ("Dataset", "entities", "Has named dataset"),
    ("Method", "entities", "Names a method/protocol"),
    ("Parameter", "entities", "Reports hyperparameters"),
    ("RandomSeed", "entities", "Reports random seed"),
    ("ComputingEnvironment", "entities", "Mentions GPU/OS/hardware"),
    ("EvaluationResult", "entities", "Reports evaluation metrics"),
    ("Activity", "entities", "Describes research activities"),
    ("Person", "entities", "Lists researchers"),
    ("Organization", "entities", "Lists institutions"),
]

def check_coverage(data):
    """Check which RDIP concepts are present in a gold_standard.json."""
    cov = {}
    ents = data.get("entities", {})
    for concept, _, _ in CONCEPTS:
        if concept == "SoftwareVersion":
            sw = ents.get("SoftwareApplication", [])
            cov[concept] = any(s.get("version") for s in sw)
        else:
            items = ents.get(concept, [])
            cov[concept] = len(items) > 0
    # Relations
    rels = data.get("relations", [])
    cov["derivedFrom"] = any(r.get("predicate") == "derivedFrom" for r in rels)
    cov["follows"] = any(r.get("predicate") == "follows" for r in rels)
    cov["usedSoftware"] = any(r.get("predicate") == "usedSoftware" for r in rels)
    cov["generatesResult"] = any(r.get("predicate") == "generatesResult" for r in rels)
    return cov

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", required=True, help="silver/ directory")
    p.add_argument("--csv", required=True, help="repo_list.csv for tier info")
    p.add_argument("--output", default="coverage_summary.md")
    args = p.parse_args()

    # Load tier info
    tiers = {}
    with open(args.csv, newline='') as f:
        for row in csv.DictReader(f):
            sid = row.get('study_id','').strip()
            if sid: tiers[sid] = row.get('final_tier','').strip()

    all_cov = []
    for study_dir in sorted(os.listdir(args.input_dir)):
        gs = os.path.join(args.input_dir, study_dir, "gold_standard.json")
        if not os.path.exists(gs): continue
        with open(gs) as f: data = json.load(f)
        if "error" in data: continue
        cov = check_coverage(data)
        cov["study_id"] = study_dir
        cov["tier"] = tiers.get(study_dir, "unknown")
        all_cov.append(cov)

    if not all_cov:
        print("No data found. Run extract_local.py --mode silver first."); return

    # Aggregate
    all_concepts = [c for c,_,_ in CONCEPTS] + ["derivedFrom","follows","usedSoftware","generatesResult"]
    tier_groups = defaultdict(list)
    for c in all_cov: tier_groups[c["tier"]].append(c)

    lines = ["# RDIP Schema Coverage Summary\n"]
    lines.append(f"Total papers analyzed: {len(all_cov)}\n")

    # Overall table
    lines.append("## Coverage by RDIP Concept\n")
    tier_names = sorted(tier_groups.keys())
    hdr = "| Concept | " + " | ".join(f"{t} (n={len(tier_groups[t])})" for t in tier_names) + f" | Overall (n={len(all_cov)}) |"
    lines.append(hdr)
    lines.append("|" + "|".join(["---"]*(len(tier_names)+2)) + "|")

    for concept in all_concepts:
        cells = []
        total_y = 0
        for t in tier_names:
            papers = tier_groups[t]
            y = sum(1 for p in papers if p.get(concept, False))
            total_y += y
            pct = y/len(papers)*100 if papers else 0
            cells.append(f"{y}/{len(papers)} ({pct:.0f}%)")
        overall_pct = total_y/len(all_cov)*100
        cells.append(f"{total_y}/{len(all_cov)} ({overall_pct:.0f}%)")
        lines.append(f"| {concept} | " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("## Key Observations\n")
    lines.append("- High coverage (>80%) in: [fill after running]")
    lines.append("- Low coverage (<40%) in: [fill after running]")
    lines.append("- Low coverage does NOT mean RDIP fails — it means papers underreport this metadata.")
    lines.append("  RDIP provides the schema to capture it when present.\n")

    with open(args.output, 'w') as f: f.write("\n".join(lines))
    print(f"Coverage summary → {args.output}")
    print("\n".join(lines))

if __name__ == "__main__": main()
