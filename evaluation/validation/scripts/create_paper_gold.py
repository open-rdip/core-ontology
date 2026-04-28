#!/usr/bin/env python3
"""
Create paper-only gold subsets for fairer LLM experiment scoring.
Removes entities that can ONLY be found in the repo, not the paper.

Specifically removes:
- RandomSeed entries with source="repo" 
- Software versions that say "exact version not specified" (already handled)
- Software entries that are build tools (gcc, pip, conda, sysroot, etc.)

Does NOT modify your original gold files - creates temporary copies for scoring.

Just run: python create_paper_gold.py
"""

import json
import re
from pathlib import Path
from copy import deepcopy

SCRIPT_DIR = Path(__file__).parent.resolve()
VALIDATION_DIR = SCRIPT_DIR.parent
GOLD_DIR = VALIDATION_DIR / "gold"
PAPER_GOLD_DIR = VALIDATION_DIR / "gold_paper_only"

# Build tools and environment components that shouldn't be SoftwareApplication
BUILD_TOOLS = {
    "gcc", "g++", "make", "cmake", "ninja", "pip", "conda", "python",
    "cuda", "cudatoolkit", "pytorch-cuda", "sysroot_linux-64",
    "ca-certificates", "certifi", "openssl", "patchelf", "compilers",
    "libaio", "setuptools", "wheel",
}


def is_build_tool(name):
    return name.lower().strip() in BUILD_TOOLS


def filter_gold(data):
    """Create paper-only version of gold standard."""
    filtered = deepcopy(data)
    entities = filtered.get("entities", {})

    # Remove repo-only seeds
    if "RandomSeed" in entities:
        original_count = len(entities["RandomSeed"])
        entities["RandomSeed"] = [
            s for s in entities["RandomSeed"]
            if s.get("source", "") != "repo"
        ]
        removed = original_count - len(entities["RandomSeed"])
        if removed > 0:
            print(f"    Removed {removed} repo-only seeds")

    # Remove build tools from SoftwareApplication
    if "SoftwareApplication" in entities:
        original_count = len(entities["SoftwareApplication"])
        entities["SoftwareApplication"] = [
            sw for sw in entities["SoftwareApplication"]
            if not is_build_tool(sw.get("name", ""))
        ]
        removed = original_count - len(entities["SoftwareApplication"])
        if removed > 0:
            print(f"    Removed {removed} build tools from Software")

    # Remove relations that reference removed entities
    remaining_names = set()
    for etype, ents in entities.items():
        for e in ents:
            name = e.get("name") or e.get("metric") or e.get("os") or e.get("gpu") or ""
            if name:
                remaining_names.add(name)

    # Also keep activity names
    for act in entities.get("Activity", []):
        if act.get("name"):
            remaining_names.add(act["name"])

    original_rels = len(filtered.get("relations", []))
    filtered["relations"] = [
        r for r in filtered.get("relations", [])
        if r.get("subject", "") in remaining_names and r.get("object", "") in remaining_names
    ]
    removed_rels = original_rels - len(filtered["relations"])
    if removed_rels > 0:
        print(f"    Removed {removed_rels} orphaned relations")

    return filtered


def main():
    print(f"Gold dir:        {GOLD_DIR}")
    print(f"Paper-only dir:  {PAPER_GOLD_DIR}\n")

    PAPER_GOLD_DIR.mkdir(parents=True, exist_ok=True)

    total_orig_entities = 0
    total_filtered_entities = 0

    for study_dir in sorted(GOLD_DIR.iterdir()):
        if not study_dir.is_dir():
            continue
        gold_path = study_dir / "gold_standard.json"
        if not gold_path.exists():
            continue

        with open(gold_path) as f:
            data = json.load(f)

        if data == {} or data.get("_status") == "DRAFT":
            continue

        sid = study_dir.name
        print(f"  {sid}:")

        # Count original entities
        orig_count = sum(len(v) for v in data.get("entities", {}).values())
        total_orig_entities += orig_count

        # Filter
        filtered = filter_gold(data)

        # Count filtered entities
        filt_count = sum(len(v) for v in filtered.get("entities", {}).values())
        total_filtered_entities += filt_count

        # Save
        out_dir = PAPER_GOLD_DIR / sid
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "gold_standard.json", "w") as f:
            json.dump(filtered, f, indent=2, ensure_ascii=False)

        print(f"    Entities: {orig_count} → {filt_count} ({orig_count - filt_count} removed)")

    print(f"\n{'='*50}")
    print(f"  Total entities: {total_orig_entities} → {total_filtered_entities}")
    print(f"  Removed: {total_orig_entities - total_filtered_entities}")
    print(f"  Paper-only gold saved to: {PAPER_GOLD_DIR}")
    print(f"\n  To score against paper-only gold:")
    print(f"  Temporarily rename gold/ → gold_full/ and gold_paper_only/ → gold/")
    print(f"  Then run: python score_llm.py")
    print(f"  Then rename back.")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()