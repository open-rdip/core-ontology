# Necessity Proof — 5 SPARQL Comparison Queries

Run each query against BOTH `baseline_dcat_prov.ttl` AND `combined_gold.ttl`.

## Q1: Which software produced which dataset?

**RDIP (works):**
```sparql
SELECT ?dataset ?software ?version WHERE {
  ?dataset a dcat:Dataset ; prov:wasGeneratedBy ?activity .
  ?activity rdip:usedSoftware ?software .
  OPTIONAL { ?software rdip:version ?version . }
}
```
**Baseline (ambiguous):** `prov:used` links activities to BOTH datasets and software — cross-product results, no way to distinguish which tool produced which dataset.

## Q2: Ordered typed activity chain within a project

**RDIP (works):**
```sparql
SELECT ?step ?type ?next WHERE {
  ?step a ?type ; rdip:isPartOfProject ?proj .
  OPTIONAL { ?next rdip:follows ?step . }
  FILTER(?type IN (rdip:DataCollectionActivity, rdip:DataProcessingActivity, rdip:DataAnalysisActivity))
}
```
**Baseline (fails):** All activities are generic `prov:Activity`. No type filtering, no project boundary.

## Q3: Person + role + specific activity

**RDIP (works):**
```sparql
SELECT ?person ?role ?activity WHERE {
  ?activity rdip:hasActivityRole ?r .
  ?r rdip:roleLabel ?role ; rdip:rolePerformedBy ?person .
}
```
**Baseline (partial):** `prov:wasAssociatedWith` gives person-activity pairs but NO role labels.

## Q4: Hyperparameters + computing environment

**RDIP (works):**
```sparql
SELECT ?param ?value ?gpu ?cuda WHERE {
  ?activity rdip:hasParameter ?p . ?p rdip:parameterName ?param ; rdip:parameterValue ?value .
  OPTIONAL { ?activity rdip:executedIn ?env . ?env rdip:gpuModel ?gpu ; rdip:cudaVersion ?cuda . }
}
```
**Baseline (impossible):** No vocabulary for parameters, seeds, GPU, or CUDA in DCAT/PROV-O/Schema.org.

## Q5: Evaluation result → raw data lineage

**RDIP (works):**
```sparql
SELECT ?metric ?value ?split ?rawData WHERE {
  ?result rdip:metricName ?metric ; rdip:metricValue ?value ; rdip:splitLabel ?split .
  ?activity rdip:generatesResult ?result ; rdip:usedDataset ?data .
  ?data rdip:derivedFrom+ ?rawData .
  FILTER NOT EXISTS { ?rawData rdip:derivedFrom ?_ }
}
```
**Baseline (impossible):** No EvaluationResult class, no metric vocabulary, no split labels.

## Summary Table (for the paper)

| # | Query | DCAT+PROV-O | RDIP | Why baseline fails |
|---|-------|:-----------:|:----:|-------------------|
| Q1 | Software → Dataset | ✗ | ✓ | prov:used is untyped |
| Q2 | Typed activity chain | ✗ | ✓ | No activity subclasses |
| Q3 | Person + role | ◐ | ✓ | No role vocabulary |
| Q4 | Params + environment | ✗ | ✓ | No vocabulary exists |
| Q5 | Result → raw data | ✗ | ✓ | No EvaluationResult |
