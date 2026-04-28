#!/usr/bin/env python3
"""
Score LLM experiment with detailed analysis.
Reports: strict, relaxed, and predicate-normalized scores.
Also separates paper-extractable vs repo-only entities.
Just run: python score_llm.py
"""

import json
import re
import csv
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).parent.resolve()
VALIDATION_DIR = SCRIPT_DIR.parent
GOLD_DIR = VALIDATION_DIR / "gold"
EXPERIMENT_DIR = VALIDATION_DIR / "llm_experiment"
OUTPUT_CSV = VALIDATION_DIR / "scores.csv"

ETYPES = [
    "SoftwareApplication", "Dataset", "Method", "Person", "Organization",
    "Parameter", "RandomSeed", "ComputingEnvironment", "EvaluationResult", "Activity"
]
CONDITIONS = ["c1", "c2", "c3"]
COND_NAMES = {"c1": "Generic", "c2": "DCAT+PROV", "c3": "RDIP"}

# ═══════════════════════════════════════════════════════
# PREDICATE NORMALIZATION MAP
# Maps PROV-O and generic predicates to RDIP equivalents
# This gives C1 and C2 a FAIR chance at relation matching
# ═══════════════════════════════════════════════════════
PREDICATE_MAP = {
    # PROV-O → RDIP
    "used": "usedSoftware",  # ambiguous, but closest
    "wasGeneratedBy": "generatesDataset",
    "wasAssociatedWith": "hasActivityRole",
    "wasDerivedFrom": "derivedFrom",
    "wasInformedBy": "follows",
    "generated": "generatesDataset",
    "wasAttributedTo": "hasActivityRole",
    # Generic → RDIP
    "uses": "usedSoftware",
    "produces": "generatesDataset",
    "generates": "generatesDataset",
    "followedBy": "follows",
    "dependsOn": "softwareDependency",
    "requires": "softwareDependency",
    "evaluates": "generatesResult",
    "trainedOn": "usedDataset",
    "testedOn": "usedDataset",
    "runsOn": "executedIn",
    "employs": "usedMethod",
    "applies": "usedMethod",
    "hasParameter": "hasParameter",
    "hasResult": "generatesResult",
    # Already RDIP (pass through)
    "usedSoftware": "usedSoftware",
    "usedDataset": "usedDataset",
    "generatesDataset": "generatesDataset",
    "usedMethod": "usedMethod",
    "executedIn": "executedIn",
    "generatesResult": "generatesResult",
    "derivedFrom": "derivedFrom",
    "follows": "follows",
    "softwareDependency": "softwareDependency",
    "hasActivityRole": "hasActivityRole",
}


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower().strip())


def tokenize(s):
    return set(re.findall(r'[a-z0-9]+', s.lower()))


def get_entity_name(e):
    return e.get("name") or e.get("metric") or e.get("os") or e.get("gpu") or ""


def normalize_predicate(pred):
    """Map any predicate to its RDIP equivalent."""
    p = pred.strip()
    # Direct match
    if p in PREDICATE_MAP:
        return PREDICATE_MAP[p]
    # Case-insensitive match
    p_lower = p.lower()
    for k, v in PREDICATE_MAP.items():
        if k.lower() == p_lower:
            return v
    # Substring match
    for k, v in PREDICATE_MAP.items():
        if k.lower() in p_lower or p_lower in k.lower():
            return v
    return p  # return original if no match


# ═══════════════════════════════════════════════════════
# MATCHING FUNCTIONS
# ═══════════════════════════════════════════════════════

def strict_match_entities(gold_ents, pred_ents):
    gset = {norm(get_entity_name(e)) for e in gold_ents}
    pset = {norm(get_entity_name(e)) for e in pred_ents}
    gset.discard(""); pset.discard("")
    tp = len(gset & pset)
    return {"tp": tp, "fp": len(pset) - tp, "fn": len(gset) - tp}


def relaxed_match_entities(gold_ents, pred_ents):
    gold_names = [get_entity_name(e) for e in gold_ents if get_entity_name(e)]
    pred_names = [get_entity_name(e) for e in pred_ents if get_entity_name(e)]
    matched_gold, matched_pred = set(), set()

    # Pass 1: exact normalized
    gold_norms = {norm(g): g for g in gold_names}
    pred_norms = {norm(p): p for p in pred_names}
    for gn, g in gold_norms.items():
        if gn in pred_norms:
            matched_gold.add(g); matched_pred.add(pred_norms[gn])

    # Pass 2: substring
    for g in [x for x in gold_names if x not in matched_gold]:
        gn = norm(g)
        for p in [x for x in pred_names if x not in matched_pred]:
            pn = norm(p)
            if gn and pn and (gn in pn or pn in gn):
                matched_gold.add(g); matched_pred.add(p); break

    # Pass 3: token overlap ≥ 50%
    for g in [x for x in gold_names if x not in matched_gold]:
        gt = tokenize(g)
        if not gt: continue
        best_score, best_p = 0, None
        for p in [x for x in pred_names if x not in matched_pred]:
            pt = tokenize(p)
            if not pt: continue
            score = len(gt & pt) / min(len(gt), len(pt))
            if score > best_score: best_score = score; best_p = p
        if best_score >= 0.5 and best_p:
            matched_gold.add(g); matched_pred.add(best_p)

    tp = len(matched_gold)
    return {"tp": tp, "fp": len(pred_names) - len(matched_pred), "fn": len(gold_names) - len(matched_gold)}


def score_relations_strict(gold_rels, pred_rels):
    def key(r): return (norm(r.get("subject", "")), r.get("predicate", ""), norm(r.get("object", "")))
    gs = {key(r) for r in gold_rels}
    ps = {key(r) for r in pred_rels}
    tp = len(gs & ps)
    return {"tp": tp, "fp": len(ps) - tp, "fn": len(gs) - tp}


def score_relations_relaxed(gold_rels, pred_rels):
    """Relaxed: substring match on subject+object, ignore predicate."""
    matched_g, matched_p = set(), set()
    for gi, gr in enumerate(gold_rels):
        gs, go = norm(gr.get("subject", "")), norm(gr.get("object", ""))
        for pi, pr in enumerate(pred_rels):
            if pi in matched_p: continue
            ps, po = norm(pr.get("subject", "")), norm(pr.get("object", ""))
            subj_match = gs and ps and (gs in ps or ps in gs)
            obj_match = go and po and (go in po or po in go)
            if subj_match and obj_match:
                matched_g.add(gi); matched_p.add(pi); break
    tp = len(matched_g)
    return {"tp": tp, "fp": len(pred_rels) - len(matched_p), "fn": len(gold_rels) - len(matched_g)}


def score_relations_normalized(gold_rels, pred_rels):
    """Predicate-normalized: map all predicates to RDIP equivalents, then relaxed match on subject+object."""
    matched_g, matched_p = set(), set()
    for gi, gr in enumerate(gold_rels):
        gs = norm(gr.get("subject", ""))
        gp = normalize_predicate(gr.get("predicate", ""))
        go = norm(gr.get("object", ""))
        for pi, pr in enumerate(pred_rels):
            if pi in matched_p: continue
            ps = norm(pr.get("subject", ""))
            pp = normalize_predicate(pr.get("predicate", ""))
            po = norm(pr.get("object", ""))
            subj_match = gs and ps and (gs in ps or ps in gs)
            obj_match = go and po and (go in po or po in go)
            pred_match = gp == pp
            if subj_match and obj_match and pred_match:
                matched_g.add(gi); matched_p.add(pi); break
    tp = len(matched_g)
    return {"tp": tp, "fp": len(pred_rels) - len(matched_p), "fn": len(gold_rels) - len(matched_g)}


def prf(s):
    p = s["tp"] / (s["tp"] + s["fp"]) if s["tp"] + s["fp"] > 0 else 0
    r = s["tp"] / (s["tp"] + s["fn"]) if s["tp"] + s["fn"] > 0 else 0
    f = 2 * p * r / (p + r) if p + r > 0 else 0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3), **s}


def find_pred_path(experiment_dir, study_id, cond):
    for p in [
        experiment_dir / study_id / "outputs" / f"{cond}_output.json",
        experiment_dir / study_id / f"{cond}_output.json",
        experiment_dir / "results" / study_id / f"{cond}_output.json",
    ]:
        if p.exists(): return p
    return None


# ═══════════════════════════════════════════════════════
# MAIN SCORING
# ═══════════════════════════════════════════════════════

def main():
    print(f"Gold dir:    {GOLD_DIR}")
    print(f"Experiment:  {EXPERIMENT_DIR}\n")

    # Collect all scores
    results = {mode: {c: defaultdict(lambda: {"tp":0,"fp":0,"fn":0}) for c in CONDITIONS}
               for mode in ["strict", "relaxed"]}
    rel_results = {mode: {c: {"tp":0,"fp":0,"fn":0} for c in CONDITIONS}
                   for mode in ["strict", "relaxed", "normalized"]}
    paper_rows = []

    for study_dir in sorted(GOLD_DIR.iterdir()):
        if not study_dir.is_dir(): continue
        gold_path = study_dir / "gold_standard.json"
        if not gold_path.exists(): continue
        with open(gold_path) as f: gold = json.load(f)
        if gold.get("_status", "") == "DRAFT": continue
        sid = study_dir.name

        for cond in CONDITIONS:
            pred_path = find_pred_path(EXPERIMENT_DIR, sid, cond)
            if not pred_path: continue
            with open(pred_path) as f: pred = json.load(f)
            if pred == {} or "entities" not in pred: continue

            # Entity scoring
            for mode_name, match_fn in [("strict", strict_match_entities), ("relaxed", relaxed_match_entities)]:
                total = {"tp": 0, "fp": 0, "fn": 0}
                for et in ETYPES:
                    ge = gold.get("entities", {}).get(et, [])
                    pe = pred.get("entities", {}).get(et, [])
                    s = match_fn(ge, pe)
                    total["tp"] += s["tp"]; total["fp"] += s["fp"]; total["fn"] += s["fn"]
                    results[mode_name][cond][et]["tp"] += s["tp"]
                    results[mode_name][cond][et]["fp"] += s["fp"]
                    results[mode_name][cond][et]["fn"] += s["fn"]

            # Relation scoring (3 modes)
            gr = gold.get("relations", [])
            pr = pred.get("relations", [])

            s_strict = score_relations_strict(gr, pr)
            s_relaxed = score_relations_relaxed(gr, pr)
            s_normalized = score_relations_normalized(gr, pr)

            for k in ["tp", "fp", "fn"]:
                rel_results["strict"][cond][k] += s_strict[k]
                rel_results["relaxed"][cond][k] += s_relaxed[k]
                rel_results["normalized"][cond][k] += s_normalized[k]

            # Per-paper row
            ep_strict = prf({"tp": sum(strict_match_entities(
                gold.get("entities",{}).get(et,[]),
                pred.get("entities",{}).get(et,[]))["tp"] for et in ETYPES),
                "fp": sum(strict_match_entities(
                gold.get("entities",{}).get(et,[]),
                pred.get("entities",{}).get(et,[]))["fp"] for et in ETYPES),
                "fn": sum(strict_match_entities(
                gold.get("entities",{}).get(et,[]),
                pred.get("entities",{}).get(et,[]))["fn"] for et in ETYPES)})

            print(f"  {sid}/{cond}: E-F1(strict)={ep_strict['f1']:.3f}  R-F1(strict)={prf(s_strict)['f1']:.3f}  R-F1(norm)={prf(s_normalized)['f1']:.3f}")

    # ═══════════════════════════════════════════════════
    # PRINT RESULTS
    # ═══════════════════════════════════════════════════

    for mode in ["strict", "relaxed"]:
        label = mode.upper()
        print(f"\n{'='*70}")
        print(f"  {label} ENTITY MATCHING")
        print(f"{'='*70}")
        print(f"  {'Condition':<14} {'P':>8} {'R':>8} {'F1':>8}")
        print(f"  {'-'*38}")
        for cond in CONDITIONS:
            t = {"tp":0, "fp":0, "fn":0}
            for et in ETYPES:
                t["tp"] += results[mode][cond][et]["tp"]
                t["fp"] += results[mode][cond][et]["fp"]
                t["fn"] += results[mode][cond][et]["fn"]
            ep = prf(t)
            print(f"  {cond} {COND_NAMES[cond]:<10} {ep['precision']:>8.3f} {ep['recall']:>8.3f} {ep['f1']:>8.3f}")

        # Per-entity breakdown
        print(f"\n  Per-Entity-Type F1 ({label}):")
        print(f"  {'Type':<25} {'C1':>6} {'C2':>6} {'C3':>6} {'C3-C1':>6}")
        print(f"  {'-'*49}")
        for et in ETYPES:
            f1s = {c: prf(results[mode][c][et])["f1"] for c in CONDITIONS}
            diff = f1s["c3"] - f1s["c1"]
            sign = "+" if diff >= 0 else ""
            print(f"  {et:<25} {f1s['c1']:>6.3f} {f1s['c2']:>6.3f} {f1s['c3']:>6.3f} {sign}{diff:>5.3f}")

    # ═══════════════════════════════════════════════════
    # RELATION RESULTS (3 modes)
    # ═══════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"  RELATION MATCHING (3 scoring modes)")
    print(f"{'='*70}")
    print(f"  {'Condition':<14} {'Strict':>8} {'Relaxed':>8} {'Normalized':>10}")
    print(f"  {'-'*42}")
    for cond in CONDITIONS:
        sf = prf(rel_results["strict"][cond])["f1"]
        rf = prf(rel_results["relaxed"][cond])["f1"]
        nf = prf(rel_results["normalized"][cond])["f1"]
        print(f"  {cond} {COND_NAMES[cond]:<10} {sf:>8.3f} {rf:>8.3f} {nf:>10.3f}")

    print(f"\n  Scoring modes explained:")
    print(f"  Strict:     exact match on (subject, predicate, object)")
    print(f"  Relaxed:    substring match on subject+object, predicate ignored")
    print(f"  Normalized: predicates mapped to RDIP equivalents, then relaxed subject+object")
    print(f"              (e.g., prov:used → rdip:usedSoftware)")

    # ═══════════════════════════════════════════════════
    # COMBINED TABLE FOR THE PAPER
    # ═══════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"  TABLE FOR THE PAPER")
    print(f"{'='*70}")
    print(f"  {'Condition':<14} {'E-F1':>6} {'E-F1':>6} {'R-F1':>6} {'R-F1':>6} {'R-F1':>6}")
    print(f"  {'':14} {'strict':>6} {'relax':>6} {'strict':>6} {'relax':>6} {'norm':>6}")
    print(f"  {'-'*50}")
    for cond in CONDITIONS:
        # Entity F1s
        es = {"tp":0,"fp":0,"fn":0}
        er = {"tp":0,"fp":0,"fn":0}
        for et in ETYPES:
            es["tp"]+=results["strict"][cond][et]["tp"]; es["fp"]+=results["strict"][cond][et]["fp"]; es["fn"]+=results["strict"][cond][et]["fn"]
            er["tp"]+=results["relaxed"][cond][et]["tp"]; er["fp"]+=results["relaxed"][cond][et]["fp"]; er["fn"]+=results["relaxed"][cond][et]["fn"]
        esf = prf(es)["f1"]
        erf = prf(er)["f1"]
        # Relation F1s
        rsf = prf(rel_results["strict"][cond])["f1"]
        rrf = prf(rel_results["relaxed"][cond])["f1"]
        rnf = prf(rel_results["normalized"][cond])["f1"]
        print(f"  {cond} {COND_NAMES[cond]:<10} {esf:>6.3f} {erf:>6.3f} {rsf:>6.3f} {rrf:>6.3f} {rnf:>6.3f}")

    # ═══════════════════════════════════════════════════
    # DETAILED RELATION ANALYSIS
    # ═══════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"  DETAILED RELATION ANALYSIS")
    print(f"{'='*70}")
    for cond in CONDITIONS:
        for mode, label in [("strict", "Strict"), ("normalized", "Normalized")]:
            s = rel_results[mode][cond]
            p = prf(s)
            print(f"  {cond} {COND_NAMES[cond]:<10} ({label:>10}): TP={s['tp']:>3}  FP={s['fp']:>3}  FN={s['fn']:>3}  P={p['precision']:.3f}  R={p['recall']:.3f}  F1={p['f1']:.3f}")

    print(f"\n{'='*70}")


if __name__ == "__main__":
    main()