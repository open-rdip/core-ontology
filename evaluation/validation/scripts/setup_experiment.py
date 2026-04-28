#!/usr/bin/env python3
"""
Create LLM experiment folder structure for 12 Gold papers.
Just run: python setup_experiment.py
"""

from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
VALIDATION_DIR = SCRIPT_DIR.parent
EXPERIMENT_DIR = VALIDATION_DIR / "llm_experiment"

GOLD_IDS = [
    "study001", "study002", "study003", "study005", "study006", "study008",
    "study009", "study013", "study015", "study017", "study020", "study022"
]

# ═══════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════

PROMPT_C1 = """You are a research metadata extraction system. Extract all research entities and relationships from this paper.

The paper PDF is attached in this conversation.

Extract: software tools (with versions), datasets, methods, people, organizations, evaluation metrics, configuration parameters, computing resources, and research activities with their ordering.

Return ONLY valid JSON:
{
  "entities": {
    "SoftwareApplication": [{"name":"...","version":"..."}],
    "Dataset": [{"name":"...","format":"...","access":"..."}],
    "Method": [{"name":"..."}],
    "Person": [{"name":"...","role":"..."}],
    "Organization": [{"name":"..."}],
    "Parameter": [{"name":"...","value":"..."}],
    "RandomSeed": [{"name":"...","value":"..."}],
    "ComputingEnvironment": [{"os":"...","gpu":"...","cuda":"..."}],
    "EvaluationResult": [{"metric":"...","value":"...","split":"..."}],
    "Activity": [{"name":"...","type":"..."}]
  },
  "relations": [
    {"subject":"...","predicate":"...","object":"..."}
  ]
}"""

PROMPT_C2 = """You are a research metadata extraction system using DCAT and PROV-O vocabularies.

The paper PDF is attached in this conversation.

Extract using these standard classes:
- prov:Activity — research activities (data collection, processing, training, evaluation)
- dcat:Dataset — datasets used or produced
- schema:SoftwareApplication — software tools or libraries
- prov:Agent / foaf:Person — researchers
- schema:Organization — institutions

Extract using these standard relationships:
- prov:used (Activity → Dataset or Software)
- prov:wasGeneratedBy (Dataset → Activity)
- prov:wasAssociatedWith (Activity → Person)
- prov:wasDerivedFrom (Dataset → Dataset)
- prov:wasInformedBy (Activity → Activity)
- dcterms:identifier, schema:version, dcterms:format

Return ONLY valid JSON:
{
  "entities": {
    "SoftwareApplication": [{"name":"...","version":"..."}],
    "Dataset": [{"name":"...","format":"...","access":"..."}],
    "Method": [{"name":"..."}],
    "Person": [{"name":"...","role":"..."}],
    "Organization": [{"name":"..."}],
    "Parameter": [{"name":"...","value":"..."}],
    "RandomSeed": [{"name":"...","value":"..."}],
    "ComputingEnvironment": [{"os":"...","gpu":"...","cuda":"..."}],
    "EvaluationResult": [{"metric":"...","value":"...","split":"..."}],
    "Activity": [{"name":"...","type":"..."}]
  },
  "relations": [
    {"subject":"...","predicate":"used|wasGeneratedBy|wasAssociatedWith|wasDerivedFrom|wasInformedBy","object":"..."}
  ]
}"""

PROMPT_C3 = """You are a research metadata extraction system using the RDIP ontology.

The paper PDF is attached in this conversation.

Extract using RDIP typed classes:
- rdip:DataCollectionActivity — collecting/capturing raw data
- rdip:DataProcessingActivity — cleaning, transforming, anonymizing data
- rdip:DataProductionActivity — producing new datasets (annotation, labeling)
- rdip:DataAnalysisActivity — training models, running experiments, evaluation
- rdip:SoftwareDevelopmentActivity — building research software
- rdip:SoftwareApplication — named software with version
- rdip:SoftwareDependency — required libraries
- rdip:Method — formal methods, algorithms, protocols
- dcat:Dataset — named datasets
- rdip:Parameter — hyperparameters
- rdip:RandomSeed — random seed values
- rdip:ComputingEnvironment — GPU, CUDA, OS specs
- rdip:EvaluationResult — metrics with values and splits
- vivo:Person — researchers with roles

Extract using RDIP relationships:
- rdip:usedSoftware (Activity → Software)
- rdip:usedDataset (Activity → Dataset)
- rdip:generatesDataset (Activity → Dataset)
- rdip:usedMethod (Activity → Method)
- rdip:hasParameter (Activity → Parameter)
- rdip:executedIn (Activity → Environment)
- rdip:generatesResult (Activity → EvaluationResult)
- rdip:derivedFrom (Dataset → Dataset)
- rdip:follows (Activity → Activity)
- rdip:softwareDependency (Software → Dependency)
- rdip:hasActivityRole (Activity → RoleInActivity)

Activity classification:
- "collected data" → DataCollectionActivity
- "cleaned/normalized data" → DataProcessingActivity
- "annotated/labeled data" → DataProductionActivity
- "trained model / evaluated" → DataAnalysisActivity
- "implemented a tool" → SoftwareDevelopmentActivity

Return ONLY valid JSON:
{
  "entities": {
    "SoftwareApplication": [{"name":"...","version":"..."}],
    "Dataset": [{"name":"...","format":"...","access":"..."}],
    "Method": [{"name":"..."}],
    "Person": [{"name":"...","role":"..."}],
    "Organization": [{"name":"..."}],
    "Parameter": [{"name":"...","value":"..."}],
    "RandomSeed": [{"name":"...","value":"..."}],
    "ComputingEnvironment": [{"os":"...","gpu":"...","cuda":"..."}],
    "EvaluationResult": [{"metric":"...","value":"...","split":"..."}],
    "Activity": [{"name":"...","type":"DataCollectionActivity|DataProcessingActivity|DataProductionActivity|DataAnalysisActivity|SoftwareDevelopmentActivity"}]
  },
  "relations": [
    {"subject":"...","predicate":"usedSoftware|usedDataset|generatesDataset|usedMethod|hasParameter|executedIn|generatesResult|derivedFrom|follows|softwareDependency|hasActivityRole","object":"..."}
  ]
}"""

# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

def main():
    created = 0

    for sid in GOLD_IDS:
        study_dir = EXPERIMENT_DIR / sid
        outputs_dir = study_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        # Create prompt files
        for cid, prompt in [("c1", PROMPT_C1), ("c2", PROMPT_C2), ("c3", PROMPT_C3)]:
            prompt_path = study_dir / f"prompt_{cid}.txt"
            if not prompt_path.exists():
                with open(prompt_path, "w") as f:
                    f.write(prompt)
                created += 1

        # Create empty output files
        for cid in ["c1", "c2", "c3"]:
            output_path = outputs_dir / f"{cid}_output.json"
            if not output_path.exists():
                with open(output_path, "w") as f:
                    f.write("{}")
                created += 1

        print(f"  ✓ {sid}/")
        print(f"      prompt_c1.txt  prompt_c2.txt  prompt_c3.txt")
        print(f"      outputs/c1_output.json  c2_output.json  c3_output.json")

    print(f"\nDone: {created} files created")
    print(f"Folders: {len(GOLD_IDS)}")
    print(f"\nWorkflow:")
    print(f"  1. Open Gemini Pro — NEW chat")
    print(f"  2. Attach pdfs/studyXXX.pdf")
    print(f"  3. Paste content of prompt_c1.txt")
    print(f"  4. Copy response → paste into outputs/c1_output.json")
    print(f"  5. Repeat with NEW chat for c2 and c3")


if __name__ == "__main__":
    main()