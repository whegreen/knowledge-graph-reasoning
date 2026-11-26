---
name: document-coherence
description: Pre-ingest consistency gate for sets of documents that must agree. Deterministically index facts (ages, codes, versions, named approaches) across documents, compare two documents, produce a topic-level resume, and emit only the items that need human or agent review. Use when asked to check document coherence, cross-document drift, stale version references, or conflicting terminology — before those facts are ingested into a knowledge graph.
---

# Document Coherence

**Version:** 1.0
**License:** Apache-2.0
**Companion to:** `knowledge-graph-reasoning`

## Purpose

`knowledge-graph-reasoning` validates a new fact **against an existing graph**. It has no notion of a *set of source documents that are supposed to say the same thing*. This skill covers that gap: it checks facts **between documents before they reach the graph**.

One question, answered deterministically:

> A paragraph changed in one document. Do the other documents that state the same fact still agree?

It is a **gate**, not a graph reasoner. It never writes nodes, never calls a model, and never resolves a disagreement by itself.

## When to use

| Use it | Do not use it |
|---|---|
| A fact appears in several documents with one authoritative owner | Validating a fact against graph nodes → use `knowledge-graph-reasoning` |
| Two documents need a coverage/terminology comparison | Judging the truth of a claim — it compares statements, not reality |
| Detecting stale cross-document version references | Extracting entities and edges — use the main skill |
| CI gate on textual drift (exit 1 on hard conflicts) | Silent auto-merge of conflicting values |

## Flow

```
config → index facts (doc + line + normalized value) → compare → report → escalations / notes → human
```

`--json` is the handoff contract: its `escalations` are **data** (quotes and a `kind`), never an instruction to call a specific agent. A host may route those escalations to domain agents; this skill does not. `notes` carries one-sided topics that are expected differences in document scope — they are reported but not escalated.

## Commands

```sh
cd skills/document-coherence/scripts

python3 coherence.py --config ../references/coherence.config.example.json \
  --root ../../.. --mode index
python3 coherence.py --config ../references/coherence.config.example.json \
  --root ../../.. --mode pair --docs handbook curriculum
python3 coherence.py --config ../references/coherence.config.example.json \
  --root ../../.. --mode topics --docs handbook curriculum --json
python3 coherence.py --config ../references/coherence.config.example.json \
  --root ../../.. --mode audit --strict
python3 source_coherence/selftest.py     # portable eval, no repo needed
```

`--root` is the base for every `docs[].path`. `--strict` exits 1 only on a hard `BEDA`/`KONFLIK` or a stale version reference. `--json` emits `{"schema":1,"mode":...,"coverage":...,"data":{...}}`.

## Configuration

Everything project-specific lives in JSON; the Python engine contains no document names. See `references/schemas.md` and `references/coherence.config.example.json`.

| Key | Purpose |
|---|---|
| `docs` | `id`, `path`, `version` for each source document |
| `facts[].emit` | One of `code`, `session`, `age`, `keyword`, `label`, `count`, `db`, `term` |
| `facts[].compare` | `existence`, `exact`, `interval`, `term_variant`, `version_reference` |
| `units`, `token_aliases` | Unit normalization (`36 month` → `3 year`) and token canonicalization |
| `aliases`, `one_sided`, `skip_patterns`, `skip_sections` | False-positive control |
| `topics`, `term_topics`, `canon_terms` | Topic resume and term-variant detection |
| `shared_topics` | Topics expected in both documents; a `SATU-SISI` finding is escalated only for these, otherwise it is a `note` |
| `version_labels` | Which document a version mention refers to |
| `owners` | Authoritative source per fact prefix; conflicts are judged against it |

Interval comparison returns `SAMA`, `SUB-TAHAP`, `OVERLAP`, or `BEDA`. `SUB-TAHAP` means one side split the same range into sub-ranges — **not** a conflict. Aliases are not a free pass: when the aliased key carries a value, that value is compared too (`ALIAS/SUB-TAHAP`, `ALIAS/BEDA`). One-sided prefixes (ids, protocol codes, DB names) are intentionally not reported as drift.

## Output contract

```json
{
  "schema": 1,
  "mode": "topics",
  "coverage": "COVERAGE: 15/177 facts carry a comparable value (8.5%)",
  "data": {
    "findings": [{"topic": "framework", "label": "ISTILAH BEDA", "lines_a": [36], "lines_b": [9]}],
    "escalations": [{"topic": "framework", "label": "ISTILAH BEDA", "kind": "topic",
                     "a": "handbook:36 \"...\"", "b": "curriculum:9 \"...\""}],
    "notes": [{"topic": "inclusion", "label": "SATU-SISI", "kind": "topic",
               "a": "handbook:118 \"...\"", "b": "-"}]
  }
}
```

`escalations` are complete and sorted by severity (`REFERENSI BASI`, `KONFLIK`, `ISTILAH BEDA`, `SATU-SISI`) — they are never truncated in JSON. `coverage` is mandatory: a verdict is only as strong as the fraction of facts with comparable values. Never present `KOHEREN` as "everything was checked".

## Rules

1. Deterministic first. Tokens are spent only on items emitted under `escalations`; `notes` are informational and do not call an agent.
2. Contradictions are **never** silently resolved. Preserve both quotes and ask the owner.
3. `ISTILAH BEDA` is a terminology finding, not proof of contradictory meaning.
4. Fix the **consumer**, not the owner, unless the owner is confirmed wrong.
5. Recency does not win ties. The configured `owners` decide which value is authoritative.
6. This skill emits data; the host decides whether to route escalations to an agent.
7. A one-sided topic is a difference in document scope, not drift, unless it is listed in `shared_topics`.

## Limits

Pattern-based extraction does not understand meaning. It detects *that* two documents disagree about a stated value, topic, or term; it cannot decide which interpretation is correct. `SUB-TAHAP` and one-sided facts are deliberately excluded from "incoherent topics". Adding a new fact type requires a config entry and an index regeneration.

## Evals

`evals/evals.json` has five prompts covering interval sub-ranges, alias detection, term variants, stale version references, and one-sided topics. The deterministic engine also ships `source_coherence/selftest.py`, which needs no repository, model, or network.
