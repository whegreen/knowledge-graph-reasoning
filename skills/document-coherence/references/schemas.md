# Schemas — document-coherence

## Config (JSON)

Top level: `schema: 1`, plus the keys below. No Python code changes are needed to add a document or a fact type.

| Key | Type | Notes |
|---|---|---|
| `docs` | array of `{id, path, version}` | `path` resolves against `--root`; `version` is the authoritative current version |
| `units` | map `word → {factor, label}` | `factor` is months per unit; conversion only when every endpoint divides evenly by 12 |
| `token_aliases` | map string→string | e.g. `{"grade 1":"grade1"}` |
| `skip_patterns` | map name→regex | referenced by `facts[].skip_if` to drop frequency phrases |
| `skip_sections` | regex | sections treated as changelog/history |
| `facts` | array | see below |
| `one_sided` | array of prefixes | one-sided mentions are not drift |
| `aliases` | map fact key→fact key | e.g. `age:k1 → age:kindy1`; values of the aliased key are compared too (`ALIAS/SUB-TAHAP`) |
| `term_topics` | array of topic names | terminology differences here are `ISTILAH BEDA`, not conflicts |
| `shared_topics` | array of topic names | only these `SATU-SISI` findings escalate; the rest go to `notes` |
| `canon_terms` | map topic→{needle→canonical} | first matching needle wins |
| `topics` | array of `{name, pattern}` | powers `--mode topics` |
| `version_labels` | map doc id→array of labels | identifies which document a `vN.N` mention refers to |
| `owners` | map prefix→doc id | authoritative source used by `--mode audit` |

### Fact entry

```json
{
  "id": "age",
  "emit": "age",
  "pattern": "\\b(Primary|Lower)\\b[^.\\n]{0,40}?(\\d+)\\s*(year|month)\\b",
  "flags": "i",
  "skip_if": "freq",
  "compare": "interval"
}
```

`emit` values: `code` (groups 1+2 → `rf:AAA-RF07`), `session`, `age` (group 1 name, 2 number, 3 unit), `keyword`, `label`, `count`, `db`, `term` (surface form + `terms` map). `compare` values: `existence`, `exact`, `interval`, `term_variant`, `version_reference`.

## Index (schema 2)

```json
{
  "schema": 2,
  "sources": [{"id": "handbook", "path": "docs/handbook.md", "version": "1.2"}],
  "sections": [{"doc": "handbook", "line": 1, "level": 1, "title": "Overview", "end": 40}],
  "facts": {"age:lower": [{"doc": "handbook", "line": 12, "section": "Overview",
                            "value": "3-4 year", "mentions": 2}]},
  "stats": {"docs": 2, "lines": 120, "fact_keys": 30, "mentions": 210}
}
```

## Report (`--json`)

```json
{
  "schema": 1,
  "mode": "pair | topics | audit",
  "generated_at": "2026-11-26T00:00:00Z",
  "coverage": "COVERAGE: 15/177 facts carry a comparable value (8.5%)",
  "data": {}
}
```

`data` contains `findings`, plus `refs` (pair), `escalations` + `notes` (topics) or `conflicts` (audit). Escalations have `topic`, `label`, `kind`, `a`, `b` — and no routing information by design. They are sorted by severity and never truncated in JSON. `notes` carry one-sided topics outside `shared_topics` as information, not agent work.
