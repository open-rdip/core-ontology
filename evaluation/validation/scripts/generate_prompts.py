#!/usr/bin/env python3
"""
Generate a tailored prompt.txt for each study folder in silver/.
Just run: python generate_prompts.py
"""

import csv
import json
import os
from pathlib import Path

# ═══════════════════════════════════════════════════════
# PATHS (auto-detected from script location)
# ═══════════════════════════════════════════════════════
SCRIPT_DIR = Path(__file__).parent.resolve()
VALIDATION_DIR = SCRIPT_DIR.parent             # evaluation/validation/
CSV_PATH = VALIDATION_DIR / "repo_list.csv"
SILVER_DIR = VALIDATION_DIR / "silver"

# ═══════════════════════════════════════════════════════
# PROMPT TEMPLATE
# ═══════════════════════════════════════════════════════
PROMPT_TEMPLATE = """You are an expert research metadata annotator using the RDIP ontology.
Extract structured metadata from this research paper and its repository.

══════════════════════════════════════
PAPER METADATA
══════════════════════════════════════
Study ID: {study_id}
Title: {title}
arXiv: {arxiv_id}
Repository: {repo_url}

══════════════════════════════════════
REPOSITORY METADATA (auto-extracted)
══════════════════════════════════════
{repo_metadata}

══════════════════════════════════════
PAPER TEXT
══════════════════════════════════════
[The paper PDF is attached separately in this conversation]

══════════════════════════════════════
EXTRACTION TASK
══════════════════════════════════════

Extract ALL of the following from the attached paper and the repository metadata above.
Be CONSERVATIVE — only extract what is explicitly stated.
Mark uncertain items with [UNCERTAIN].

Return ONLY valid JSON in this EXACT format (no markdown fences, no explanation before or after):

{{
  "study_id": "{study_id}",
  "project": {{
    "title": "...",
    "lead_organization": "first author's affiliation",
    "funding": "from acknowledgments section, or null"
  }},
  "entities": {{
    "SoftwareApplication": [
      {{"name": "...", "version": "exact version from repo or paper"}}
    ],
    "Dataset": [
      {{"name": "...", "format": "CSV|JSON|images|etc", "access": "open|restricted", "role": "used|produced", "derived_from": "parent dataset name or null"}}
    ],
    "Method": [
      {{"name": "...", "description": "one sentence"}}
    ],
    "Person": [
      {{"name": "...", "affiliation": "...", "role": "Principal Investigator|Software Engineer|Data Collector|..."}}
    ],
    "Organization": [
      {{"name": "..."}}
    ],
    "Parameter": [
      {{"name": "learning_rate|batch_size|num_epochs|etc", "value": "...", "type": "xsd:float|xsd:integer|xsd:string"}}
    ],
    "RandomSeed": [
      {{"name": "random_seed", "value": "...", "source": "paper|repo"}}
    ],
    "ComputingEnvironment": [
      {{"os": "...", "gpu": "...", "cuda": "...", "ram": "..."}}
    ],
    "EvaluationResult": [
      {{"metric": "accuracy|F1|mAP|AUC|etc", "value": "...", "split": "test|val|train", "dataset": "dataset name"}}
    ],
    "Activity": [
      {{"name": "descriptive name", "type": "DataCollectionActivity|DataProcessingActivity|DataProductionActivity|DataAnalysisActivity|SoftwareDevelopmentActivity", "order": 1, "software_used": ["..."], "dataset_used": ["..."], "dataset_produced": ["..."]}}
    ]
  }},
  "relations": [
    {{"subject": "entity name", "predicate": "usedSoftware|usedDataset|generatesDataset|usedMethod|hasParameter|executedIn|generatesResult|derivedFrom|follows|softwareDependency|hasActivityRole", "object": "entity name"}}
  ]
}}

IMPORTANT RULES:
1. Software versions: prefer exact versions from repo (requirements.txt) over paper text.
2. Include random seeds found in repo metadata above.
3. Activities must have an ORDER field (1, 2, 3...) showing execution sequence.
4. For each activity, list which software, datasets, and methods it uses/produces.
5. Relations must use the EXACT predicate names listed above.
6. Evaluation metrics: include the EXACT numeric value and which split (test/val/train).
7. If something is not mentioned, omit it — do NOT fabricate.
"""


def format_repo_metadata(repo_data):
    parts = []

    deps = repo_data.get("software_dependencies", repo_data.get("deps", []))
    if deps:
        parts.append("Software dependencies (from requirements.txt):")
        for d in deps[:40]:
            v = f"=={d['version']}" if d.get("version") else ""
            parts.append(f"  - {d['name']}{v}")

    conda = repo_data.get("conda", {})
    conda_deps = conda.get("deps", [])
    if conda_deps:
        parts.append("\nConda dependencies (from environment.yml):")
        for d in conda_deps[:30]:
            v = f"={d['version']}" if d.get("version") else ""
            parts.append(f"  - {d['name']}{v}")

    env = repo_data.get("environment", repo_data.get("env", {}))
    if env.get("base_image"):
        parts.append(f"\nDocker base image: {env['base_image']}")
        if env.get("cuda_version"):
            parts.append(f"CUDA version (from Docker): {env['cuda_version']}")
        if env.get("os"):
            parts.append(f"OS (from Docker): {env['os']}")
        if env.get("python_version"):
            parts.append(f"Python version (from Docker): {env['python_version']}")

    seeds = repo_data.get("seeds", [])
    if seeds:
        main_seeds = [s for s in seeds if "test" not in s.get("file", "").lower()]
        test_seeds = [s for s in seeds if "test" in s.get("file", "").lower()]
        if main_seeds:
            parts.append("\nRandom seeds found in main code:")
            for s in main_seeds[:5]:
                parts.append(f"  - seed={s['value']} (in {s.get('file', '')})")
        if test_seeds:
            parts.append("\nRandom seeds found in test files (may not be experiment seeds):")
            for s in test_seeds[:3]:
                parts.append(f"  - seed={s['value']} (in {s.get('file', '')})")

    lic = repo_data.get("license", "")
    if lic:
        parts.append(f"\nRepository license: {lic}")

    if not parts:
        return "No repository metadata could be extracted."

    return "\n".join(parts)


def main():
    print(f"CSV:    {CSV_PATH}")
    print(f"Silver: {SILVER_DIR}\n")

    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found"); return
    if not SILVER_DIR.exists():
        print(f"ERROR: {SILVER_DIR} not found"); return

    papers = {}
    with open(CSV_PATH, newline="") as f:
        for row in csv.DictReader(f):
            sid = row.get("study_id", "").strip()
            if sid:
                papers[sid] = row

    generated, skipped, no_repo = 0, 0, 0

    for sid in sorted(papers.keys()):
        row = papers[sid]
        study_dir = SILVER_DIR / sid
        study_dir.mkdir(parents=True, exist_ok=True)

        prompt_path = study_dir / "prompt.txt"
        if prompt_path.exists():
            skipped += 1
            continue

        repo_meta_path = study_dir / "repo_metadata.json"
        if repo_meta_path.exists():
            with open(repo_meta_path) as f:
                repo_data = json.load(f)
            repo_meta_str = format_repo_metadata(repo_data)
        else:
            repo_meta_str = "No repository metadata available. Extract software info from the paper text only."
            no_repo += 1

        prompt = PROMPT_TEMPLATE.format(
            study_id=sid,
            title=row.get("paper_title", ""),
            arxiv_id=row.get("arxiv_id", ""),
            repo_url=row.get("repo_url", ""),
            repo_metadata=repo_meta_str,
        )

        with open(prompt_path, "w") as f:
            f.write(prompt)

        generated += 1
        print(f"  ✓ {sid}: prompt.txt")

    print(f"\nDone: {generated} generated, {skipped} skipped, {no_repo} without repo metadata")


if __name__ == "__main__":
    main()