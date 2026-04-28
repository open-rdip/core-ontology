# RDIP Verification Checklist

## Overview

```
TWO SEPARATE TASKS — do not mix them:

TASK A: Verify gold_standard.json (all 95 silver + 12 gold thorough)
        → produces verified annotations

TASK B: LLM 3-condition experiment (12 Gold papers ONLY)
        → produces c1/c2/c3_output.json for scoring
        → SEPARATE fresh Gemini sessions, NOT reusing Task A outputs
```

---

## TASK A: Verification

### For each paper, open:
- The paper PDF: `pdfs/{study_id}.pdf`
- The JSON: `silver/{study_id}/gold_standard.json`
- The GitHub repo in a browser

### Step 1: Activities (3 min)
- [ ] Are activity TYPES correct? (Collection vs Processing vs Analysis)
- [ ] Is the ORDER correct? (does activity 2 actually follow activity 1?)
- [ ] Any activities MISSING? (common miss: data preprocessing, model evaluation)
- [ ] Any activities HALLUCINATED? (LLM invented a step not in the paper)
- [ ] Fix: change `"type"` to the correct RDIP activity subclass

### Step 2: Software (3 min)
- [ ] Cross-check software names against paper AND repo
- [ ] Are versions correct? (check requirements.txt in repo)
- [ ] Remove environment components wrongly listed as software (cuda, gcc, python)
- [ ] Remove any hallucinated software not in paper or repo

### Step 3: Datasets (3 min)
- [ ] Are dataset NAMES correct? (exact names from the paper)
- [ ] Is USED vs PRODUCED correct?
- [ ] Are derivedFrom links correct?
- [ ] Are access levels right? (open/restricted)

### Step 4: Evaluation Results (2 min)
- [ ] Are metric NAMES correct? (accuracy vs top-1 accuracy, F1 vs F1-macro)
- [ ] Are metric VALUES correct? (compare against paper tables)
- [ ] Are SPLITS correct? (test vs validation vs train)
- [ ] Is the DATASET field the evaluation dataset, NOT the model name?
- [ ] Any metrics MISSING from the paper's results table?

### Step 5: Parameters & Environment (2 min)
- [ ] Are hyperparameter VALUES correct? (check paper experiments section)
- [ ] Are seeds from main code only? (remove test file seeds)
- [ ] Is GPU specific? (e.g., "NVIDIA A100" not "modern GPUs")
- [ ] Is CUDA/OS accurate?

### Step 6: People & Roles (2 min)
- [ ] Are all authors listed?
- [ ] Are affiliations correct?
- [ ] Are roles reasonable? (first author = PI is usually safe)

### Step 7: Relations (2 min)
- [ ] Do relation subjects/objects match actual entity names in the JSON?
- [ ] Are predicate names from the allowed set?
- [ ] Are `follows` relations matching activity order?

### Step 8: Resolve [UNCERTAIN] Tags
- [ ] Search for `[UNCERTAIN]` in the JSON
- [ ] For each one: confirm it (remove tag) OR fix the value OR set to null
- [ ] GOLD papers: ZERO [UNCERTAIN] should remain after verification
- [ ] Silver papers: a few are acceptable if genuinely unresolvable

### Step 9: Add Verification Fields
Add these fields to the JSON root level:

```json
{
  "study_id": "study001",
  "_status": "VERIFIED",
  "_verified_by": "Author Name",
  "_verification_date": "2026-04-21",
  "_verification_notes": "Fixed activity types, removed test seeds, corrected GPU model",
  "project": { ... },
  "entities": { ... },
  "relations": [ ... ]
}
```

For GOLD papers, also add:
```json
  "_verification_depth": "thorough",
```

For Silver papers:
```json
  "_verification_depth": "standard",
```
or
```json
  "_verification_depth": "quick",
```

### Step 10: Save
- [ ] Save the corrected gold_standard.json
- [ ] Verify the JSON is valid (no trailing commas, no syntax errors)

---

## Verification Depth by Tier

| Tier | Papers | Steps | Time/paper | Total |
|------|--------|-------|-----------|-------|
| Gold (b_score ≥ 5, full) | 12 | All steps, resolve ALL [UNCERTAIN] | 25-30 min | 6 hours |
| Full tier (remaining) | 14 | Steps 1-5, 7-8 | 15-20 min | 5 hours |
| Build-only tier | 69 | Steps 1, 2, 4, 8 | 8-10 min | 12 hours |
| **Total** | **95** | | | **~23 hours** |

---

## Gold Paper List (12 papers)

Copy these to `gold/` after verification:

```bash
for id in study001 study002 study003 study005 study006 study008 \
          study009 study013 study015 study017 study020 study022; do
    mkdir -p gold/$id
    cp silver/$id/gold_standard.json gold/$id/
    cp silver/$id/repo_metadata.json gold/$id/
done
```

---

## TASK B: LLM 3-Condition Experiment (12 Gold papers ONLY)

### What this tests
Whether RDIP vocabulary helps an LLM extract more accurate metadata
compared to generic prompts or DCAT+PROV-O prompts.

### Critical rules
1. Run in FRESH Gemini sessions — do NOT reuse Task A outputs
2. Do NOT include repo metadata in ANY condition — only paper text
3. Use the SAME LLM (Gemini Flash 3) for all 3 conditions
4. Attach the PDF for each run

### Prompts

**C1 — Generic (no ontology vocabulary):**
Just asks to extract entities and relationships. No class definitions.
No predicate constraints. The LLM decides its own schema.

**C2 — DCAT + PROV-O (standard vocabularies):**
Provides DCAT and PROV-O class/property names as guidance.
Uses standard relationship names: prov:used, prov:wasGeneratedBy, etc.

**C3 — RDIP (domain-specific vocabulary):**
Provides full RDIP class hierarchy and relationship names.
Includes activity type classification guide.

### Process (per Gold paper)

1. Open Gemini Flash 3 — NEW conversation
2. Attach `pdfs/studyXXX.pdf`
3. Paste PROMPT_C1 → copy response → save as `llm_experiment/results/studyXXX/c1_output.json`

4. Open Gemini Flash 3 — NEW conversation
5. Attach same PDF
6. Paste PROMPT_C2 → copy response → save as `c2_output.json`

7. Open Gemini Flash 3 — NEW conversation
8. Attach same PDF
9. Paste PROMPT_C3 → copy response → save as `c3_output.json`

Total: 12 papers × 3 conditions = 36 Gemini sessions

### Output structure
```
llm_experiment/results/
├── study001/
│   ├── c1_output.json
│   ├── c2_output.json
│   └── c3_output.json
├── study002/
│   ├── c1_output.json
│   ├── c2_output.json
│   └── c3_output.json
└── ... (12 folders)
```

### Scoring
```bash
python scripts/score_llm.py --gold-dir gold --pred-dir llm_experiment/results --output scores.csv
```

---

## TASK C: Knowledge Graph Generation (12 Gold papers)

### After Task A verification is complete for all 12 Gold papers:

```bash
# Step 1: Convert verified JSON → Turtle
python scripts/json_to_turtle.py --input-dir gold --output combined_gold.ttl

# Step 2: Run CQ1-CQ11 against combined_gold.ttl
# Use any SPARQL tool (Apache Jena, rdflib, online SPARQL endpoint)
```

### SHACL Validation (Gold papers only)
Run SHACL shapes against each `gold/studyXXX/triples.ttl` to verify
the triples conform to RDIP's structural constraints. Only needed
for the 12 Gold papers — these are the ones you report in the paper.

---

## TASK D: Coverage Analysis (all 95 papers)

```bash
python scripts/analyze_coverage.py --input-dir silver --csv repo_list.csv --output coverage_summary.md
```

This produces the schema coverage table for the paper — shows which
RDIP classes are represented across the corpus, broken down by tier.

---

## Common LLM Errors to Watch For

1. **Software hallucination**: adds "scikit-learn" because it's common in ML
2. **Version mismatch**: uses version from training data, not from repo
3. **Activity type confusion**: labels training as DataProcessingActivity
4. **Metric inflation**: reports metrics from related work, not the paper's own
5. **Dataset name fabrication**: "training dataset" instead of actual name
6. **Environment as software**: lists cuda, gcc, python as SoftwareApplication
7. **EvaluationResult dataset = model name**: puts "BLOOM-176B" instead of "Wikitext-2"
8. **Test file seeds**: includes seeds from test/ directory, not experiment code