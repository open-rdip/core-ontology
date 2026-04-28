#!/usr/bin/env python3
"""
Convert verified gold_standard.json → valid RDIP triples.ttl
Just run: python json_to_turtle.py

Reads:  gold/studyXXX/gold_standard.json
Writes: gold/studyXXX/triples.ttl (per paper)
        combined_gold.ttl (merged graph)
"""

import json
import re
from pathlib import Path

# ═══════════════════════════════════════════════════════
# PATHS (auto-detected)
# ═══════════════════════════════════════════════════════
SCRIPT_DIR = Path(__file__).parent.resolve()
VALIDATION_DIR = SCRIPT_DIR.parent
GOLD_DIR = VALIDATION_DIR / "gold"
OUTPUT_FILE = VALIDATION_DIR / "combined_gold.ttl"


def sanitize_id(name: str) -> str:
    s = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    s = re.sub(r'_+', '_', s).strip('_')
    return s[:60]


def escape_string(s) -> str:
    if s is None:
        return ""
    s = str(s)
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def is_valid(val):
    """Check if a value is non-empty and not null."""
    return val is not None and str(val).strip() not in ("", "null", "None", "exact version not specified")


def convert_one(data: dict) -> tuple:
    sid = data.get("study_id", "unknown")
    prefix = sanitize_id(sid)
    lines = []

    lines.append(f"# RDIP Triples — {sid}")
    lines.append(f"# Generated from verified gold_standard.json\n")
    lines.append("@prefix rdip:   <https://w3id.org/rdip/> .")
    lines.append("@prefix ex:     <https://w3id.org/rdip/eval/> .")
    lines.append("@prefix vivo:   <http://vivoweb.org/ontology/core#> .")
    lines.append("@prefix bibo:   <http://purl.org/ontology/bibo/> .")
    lines.append("@prefix dcat:   <http://www.w3.org/ns/dcat#> .")
    lines.append("@prefix prov:   <http://www.w3.org/ns/prov#> .")
    lines.append("@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .")
    lines.append("@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .")
    lines.append("")

    entities = data.get("entities", {})
    relations = data.get("relations", [])
    project = data.get("project", {})

    # --- Project ---
    proj_id = f"ex:{prefix}_Project"
    lines.append(f"# ═══ PROJECT ═══")
    lines.append(f"{proj_id} a rdip:ResearchProject ;")
    if is_valid(project.get("title")):
        lines.append(f'    rdip:title "{escape_string(project["title"])}" ;')
    if is_valid(project.get("funding")):
        lines.append(f'    rdip:fundingReference "{escape_string(project["funding"])}" ;')
    lines.append(f"    .")
    lines.append("")

    # --- Organizations ---
    orgs = entities.get("Organization", [])
    org_map = {}
    for j, org in enumerate(orgs):
        oid = f"ex:{prefix}_Org{j+1}"
        name = org.get("name", "")
        org_map[name] = oid
        lines.append(f'{oid} a vivo:Organization ;')
        lines.append(f'    rdfs:label "{escape_string(name)}" .')
    if orgs:
        lines.append(f'{proj_id} rdip:hasLeadOrganization ex:{prefix}_Org1 .')
        lines.append("")

    # --- People ---
    people = entities.get("Person", [])
    person_map = {}
    for j, person in enumerate(people):
        pid = f"ex:{prefix}_Person{j+1}"
        name = person.get("name", "")
        person_map[name] = pid
        lines.append(f'{pid} a vivo:Person ;')
        lines.append(f'    rdfs:label "{escape_string(name)}" .')
        lines.append(f'{proj_id} rdip:hasParticipant {pid} .')
    if people:
        lines.append("")

    # --- Software ---
    software = entities.get("SoftwareApplication", [])
    sw_map = {}
    for j, sw in enumerate(software):
        swid = f"ex:{prefix}_Sw{j+1}"
        name = sw.get("name", "")
        sw_map[name] = swid
        lines.append(f'{swid} a rdip:SoftwareApplication ;')
        lines.append(f'    rdip:title "{escape_string(name)}" ;')
        if is_valid(sw.get("version")):
            lines.append(f'    rdip:version "{escape_string(sw["version"])}" ;')
        lines.append(f'    .')
    if software:
        lines.append("")

    # --- Datasets ---
    datasets = entities.get("Dataset", [])
    ds_map = {}
    for j, ds in enumerate(datasets):
        dsid = f"ex:{prefix}_Dataset{j+1}"
        name = ds.get("name", "")
        ds_map[name] = dsid
        lines.append(f'{dsid} a dcat:Dataset ;')
        lines.append(f'    rdip:title "{escape_string(name)}" ;')
        if is_valid(ds.get("format")):
            lines.append(f'    rdip:dataFormat "{escape_string(ds["format"])}" ;')
        if is_valid(ds.get("access")):
            lines.append(f'    rdip:accessLevel "{escape_string(ds["access"])}" ;')
        lines.append(f'    .')
        if is_valid(ds.get("derived_from")) and ds["derived_from"] in ds_map:
            lines.append(f'{dsid} rdip:derivedFrom {ds_map[ds["derived_from"]]} .')
    if datasets:
        lines.append("")

    # --- Methods ---
    methods = entities.get("Method", [])
    method_map = {}
    for j, m in enumerate(methods):
        mid = f"ex:{prefix}_Method{j+1}"
        name = m.get("name", "")
        method_map[name] = mid
        lines.append(f'{mid} a rdip:Method ;')
        lines.append(f'    rdip:title "{escape_string(name)}" ;')
        if is_valid(m.get("description")):
            lines.append(f'    rdip:description "{escape_string(m["description"])}" ;')
        lines.append(f'    .')
    if methods:
        lines.append("")

    # --- Parameters ---
    params = entities.get("Parameter", [])
    param_map = {}
    for j, p in enumerate(params):
        pid = f"ex:{prefix}_Param{j+1}"
        name = p.get("name", "")
        param_map[name] = pid
        lines.append(f'{pid} a rdip:Parameter ;')
        lines.append(f'    rdip:parameterName "{escape_string(name)}" ;')
        if is_valid(p.get("value")):
            lines.append(f'    rdip:parameterValue "{escape_string(str(p["value"]))}" ;')
        if is_valid(p.get("type")):
            lines.append(f'    rdip:parameterDataType "{escape_string(p["type"])}" ;')
        lines.append(f'    .')

    # --- Random Seeds ---
    seeds = entities.get("RandomSeed", [])
    for j, s in enumerate(seeds):
        seedid = f"ex:{prefix}_Seed{j+1}"
        param_map[s.get("name", "random_seed")] = seedid
        lines.append(f'{seedid} a rdip:RandomSeed ;')
        lines.append(f'    rdip:parameterName "random_seed" ;')
        if is_valid(s.get("value")):
            lines.append(f'    rdip:parameterValue "{escape_string(str(s["value"]))}" ;')
        lines.append(f'    rdip:parameterDataType "xsd:integer" .')
    if params or seeds:
        lines.append("")

    # --- Computing Environment ---
    envs = entities.get("ComputingEnvironment", [])
    env_map = {}
    for j, env in enumerate(envs):
        eid = f"ex:{prefix}_Env{j+1}"
        env_key = env.get("os") or env.get("gpu") or f"env{j+1}"
        env_map[env_key] = eid
        lines.append(f'{eid} a rdip:ComputingEnvironment ;')
        if is_valid(env.get("os")):
            lines.append(f'    rdip:osVersion "{escape_string(env["os"])}" ;')
        if is_valid(env.get("gpu")):
            lines.append(f'    rdip:gpuModel "{escape_string(env["gpu"])}" ;')
        if is_valid(env.get("cuda")):
            lines.append(f'    rdip:cudaVersion "{escape_string(env["cuda"])}" ;')
        if is_valid(env.get("ram")):
            lines.append(f'    rdip:hardwareSpec "{escape_string(str(env["ram"]))}" ;')
        lines.append(f'    .')
    if envs:
        lines.append("")

    # --- Evaluation Results ---
    results = entities.get("EvaluationResult", [])
    result_map = {}
    for j, r in enumerate(results):
        rid = f"ex:{prefix}_Result{j+1}"
        metric = r.get("metric", "")
        key = metric if metric not in result_map else f"{metric}_{j+1}"
        result_map[key] = rid
        result_map[metric] = rid
        lines.append(f'{rid} a rdip:EvaluationResult ;')
        lines.append(f'    rdip:metricName "{escape_string(metric)}" ;')
        if is_valid(r.get("value")):
            lines.append(f'    rdip:metricValue "{escape_string(str(r["value"]))}" ;')
        if is_valid(r.get("split")):
            lines.append(f'    rdip:splitLabel "{escape_string(r["split"])}" ;')
        if is_valid(r.get("dataset")):
            lines.append(f'    rdip:evaluationDataset "{escape_string(r["dataset"])}" ;')
        lines.append(f'    rdip:metricDataType "xsd:float" .')
    if results:
        lines.append("")

    # --- Activities ---
    activities = entities.get("Activity", [])
    act_map = {}
    for j, act in enumerate(activities):
        aid = f"ex:{prefix}_Act{j+1}"
        name = act.get("name", "")
        act_map[name] = aid
        act_type = act.get("type", "ResearchActivity")
        if not act_type.startswith("rdip:"):
            act_type = f"rdip:{act_type}"
        lines.append(f'{aid} a {act_type} ;')
        lines.append(f'    rdip:title "{escape_string(name)}" ;')
        lines.append(f'    rdip:isPartOfProject {proj_id} ;')
        lines.append(f'    .')
        lines.append(f'{proj_id} rdip:hasActivity {aid} .')
    if activities:
        lines.append("")

    # --- Relations ---
    lines.append("# ═══ RELATIONS ═══")

    all_entities = {}
    all_entities.update(sw_map)
    all_entities.update(ds_map)
    all_entities.update(method_map)
    all_entities.update(param_map)
    all_entities.update(result_map)
    all_entities.update(act_map)
    all_entities.update(env_map)
    all_entities.update(person_map)
    all_entities.update(org_map)

    resolved, unresolved = 0, 0
    valid_predicates = {
        "usedSoftware", "usedDataset", "generatesDataset", "usedMethod",
        "hasParameter", "executedIn", "generatesResult", "derivedFrom",
        "follows", "softwareDependency", "hasActivityRole"
    }

    for rel in relations:
        subj_name = rel.get("subject", "")
        pred = rel.get("predicate", "")
        obj_name = rel.get("object", "")

        subj = all_entities.get(subj_name)
        obj = all_entities.get(obj_name)

        if not subj or not obj:
            lines.append(f'# UNRESOLVED: "{subj_name}" —{pred}→ "{obj_name}"')
            unresolved += 1
            continue

        if pred in valid_predicates:
            lines.append(f'{subj} rdip:{pred} {obj} .')
            resolved += 1
        else:
            lines.append(f'# UNKNOWN PREDICATE: {subj} {pred} {obj}')
            unresolved += 1

    lines.append("")
    lines.append(f"# ═══ END ({resolved} resolved, {unresolved} unresolved) ═══")

    return lines, resolved, unresolved


def main():
    print(f"Gold dir: {GOLD_DIR}")
    print(f"Output:   {OUTPUT_FILE}\n")

    if not GOLD_DIR.exists():
        print(f"ERROR: {GOLD_DIR} not found")
        print(f"Create it and copy verified gold_standard.json files:")
        print(f"  mkdir -p gold/study001 && cp silver/study001/gold_standard.json gold/study001/")
        return

    combined = []
    total_resolved, total_unresolved = 0, 0
    total_triples = 0

    for paper_dir in sorted(GOLD_DIR.iterdir()):
        if not paper_dir.is_dir():
            continue
        json_path = paper_dir / "gold_standard.json"
        if not json_path.exists():
            print(f"  ⚠ {paper_dir.name}: no gold_standard.json — skip")
            continue

        with open(json_path) as f:
            data = json.load(f)

        if data == {}:
            print(f"  ⚠ {paper_dir.name}: empty JSON — skip")
            continue

        status = data.get("_status", "")
        if status == "DRAFT":
            print(f"  ⚠ {paper_dir.name}: still DRAFT — skip")
            continue

        lines, resolved, unresolved = convert_one(data)
        ttl = "\n".join(lines)

        # Save individual TTL
        ttl_path = paper_dir / "triples.ttl"
        with open(ttl_path, 'w') as f:
            f.write(ttl)

        triple_count = sum(1 for l in lines
                          if l.strip().endswith(' .')
                          and not l.strip().startswith('#')
                          and not l.strip().startswith('@'))
        total_triples += triple_count
        total_resolved += resolved
        total_unresolved += unresolved

        print(f"  ✓ {paper_dir.name}: {triple_count} triples, {resolved} resolved, {unresolved} unresolved")

        combined.append(ttl)

    if combined:
        with open(OUTPUT_FILE, 'w') as f:
            f.write("\n\n".join(combined))
        print(f"\n{'='*50}")
        print(f"  Combined: {OUTPUT_FILE}")
        print(f"  Papers:   {len(combined)}")
        print(f"  Triples:  {total_triples}")
        print(f"  Relations resolved:   {total_resolved}")
        print(f"  Relations unresolved: {total_unresolved}")
        print(f"{'='*50}")

        # ═══════════════════════════════════════════════
        # RDFLIB STATISTICS (per-class breakdown)
        # ═══════════════════════════════════════════════
        try:
            from rdflib import Graph, Namespace, RDF

            RDIP = Namespace("https://w3id.org/rdip/")
            DCAT = Namespace("http://www.w3.org/ns/dcat#")
            VIVO = Namespace("http://vivoweb.org/ontology/core#")

            act_types = [
                "DataCollectionActivity", "DataProcessingActivity",
                "DataProductionActivity", "DataAnalysisActivity",
                "SoftwareDevelopmentActivity", "PublicationActivity",
                "DataPublishingActivity", "DataPreservationActivity"
            ]

            print(f"\n{'='*75}")
            print(f"  RDIP CLASS STATISTICS (via rdflib)")
            print(f"{'='*75}\n")

            all_stats = []
            for paper_dir in sorted(GOLD_DIR.iterdir()):
                ttl_path = paper_dir / "triples.ttl"
                if not ttl_path.exists() or not paper_dir.is_dir():
                    continue
                g = Graph()
                g.parse(str(ttl_path), format="turtle")
                if len(g) < 5:
                    continue

                s = {"id": paper_dir.name, "triples": len(g)}
                s["Projects"] = len(set(g.subjects(RDF.type, RDIP.ResearchProject)))
                s["Software"] = len(set(g.subjects(RDF.type, RDIP.SoftwareApplication)))
                s["Dependencies"] = len(set(g.subjects(RDF.type, RDIP.SoftwareDependency)))
                s["Datasets"] = len(set(g.subjects(RDF.type, DCAT.Dataset)))
                s["Methods"] = len(set(g.subjects(RDF.type, RDIP.Method)))
                s["Parameters"] = len(set(g.subjects(RDF.type, RDIP.Parameter)))
                s["Seeds"] = len(set(g.subjects(RDF.type, RDIP.RandomSeed)))
                s["Environments"] = len(set(g.subjects(RDF.type, RDIP.ComputingEnvironment)))
                s["EvalResults"] = len(set(g.subjects(RDF.type, RDIP.EvaluationResult)))
                s["People"] = len(set(g.subjects(RDF.type, VIVO.Person)))
                s["Organizations"] = len(set(g.subjects(RDF.type, VIVO.Organization)))
                s["Activities"] = len(set(
                    subj for at in act_types
                    for subj in g.subjects(RDF.type, RDIP[at])
                ))
                all_stats.append(s)

            if all_stats:
                cols = ["Projects", "Activities", "Software", "Datasets", "Methods",
                        "Parameters", "Seeds", "Environments", "EvalResults", "People"]
                hdr = f"  {'Paper':<12} {'Trip':>5} " + " ".join(f"{c[:4]:>4}" for c in cols)
                print(hdr)
                print(f"  {'-'*len(hdr)}")
                for s in all_stats:
                    print(f"  {s['id']:<12} {s['triples']:>5} " +
                          " ".join(f"{s[c]:>4}" for c in cols))

                # Totals
                print(f"  {'-'*len(hdr)}")
                totals = {c: sum(s[c] for s in all_stats) for c in ["triples"] + cols}
                print(f"  {'TOTAL':<12} {totals['triples']:>5} " +
                      " ".join(f"{totals[c]:>4}" for c in cols))

        except ImportError:
            print("\n  (pip install rdflib for class-level statistics)")

    else:
        print("\nNo papers found in gold/. Copy verified papers there first.")


if __name__ == "__main__":
    main()