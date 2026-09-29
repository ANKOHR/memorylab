# MemoryLab

MemoryLab is a deterministic benchmark harness for six memory policies. It runs the same synthetic recall episodes through each policy and reports task success, token use, retrieval accuracy, and fabricated recall counts.

## Quickstart

Python 3.10 or newer is required. Install the package and its test extra in a CPU-only environment:

```powershell
python -m pip install -e ".[dev]"
memorylab fixtures --out fixtures
memorylab policies
memorylab run --policy full_context --episodes fixtures --token-budget 128
memorylab report --format md --episodes fixtures --token-budget 128 --out findings.md
```

The same commands work as `python -m memorylab ...` without installing the console script. The default fixtures are bundled in Python and use seed `0`. No random number generator is used. Every command is deterministic for the same inputs.

To run the test suite:

```powershell
python -m pytest
```

## Architecture

```text
Synthetic fixture episodes
          |
          v
Event runner: facts arrive, queries pause the episode
          |
          +--> full_context     all fact events, newest context first
          +--> summary          one lossy note per relation
          +--> token_overlap    ranked event text by literal token overlap
          +--> episodic         time-tagged event store
          +--> structured      typed key/value state
          +--> hybrid           typed state plus event retrieval fallback
          |
          v
Per-query answers, evidence IDs, token counts
          |
          v
Success, retrieval accuracy, corruption, and token metrics
          |
          v
Deterministic JSON run output or Markdown/HTML findings report
```

## HONESTY BOUNDARY

The policies are deterministic rules running on synthetic episodes. Token-overlap similarity is literal word overlap, not embeddings. There are no trained models, no real agent memory, no real retrieval systems, and no embeddings in this project. All facts and characters in the fixtures are fictional. The findings apply to these fixtures only. They do not establish which architecture is best in general and must not be generalized to real agents or real workloads.

MemoryLab measures the behavior of the implemented rules; it does not argue about which memory architecture is best. It runs the same tasks through six policies and shows the numbers.

## Policy catalogue

All policy classes implement the same interface: `observe(fact_event)`, `respond(query, token_budget)`, and `inspect()`. A run includes each policy's final inspectable memory contents and the fact IDs exposed for each answer.

| Policy | Memory and query rule |
| --- | --- |
| `full_context` | Retains every fact event. It presents the newest events first until the memory token budget is used, then resolves the selected event history. |
| `summary` | Retains one latest subject-value note per relation. It deliberately drops other subjects for that relation, making its lossy behavior visible in the corruption trap. |
| `token_overlap` | Retains fact events and ranks each query by shared distinct lowercase alphanumeric tokens. Equal scores prefer the later event, then the lexically smaller fact ID. This is not semantic similarity. |
| `episodic` | Retains time-tagged fact events. Events for the queried subject and relation are shown first, in chronological order, followed by other events. |
| `structured` | Retains a typed state entry for each `(subject, relation)` key. `set` writes only when the key is absent, `correct` replaces the value, and `expire` removes the key. |
| `hybrid` | Uses typed state for exact lookups, the matching event timeline for expired keys, and token-overlap ranking as a fallback for unmatched keys. |

The memory token budget applies per query to the memory entries shown to a policy. Entries are prioritized by that policy and greedily included when they fit. Query text is counted in total token use but is outside the memory budget. Memory and query token counts use whitespace-separated tokens so they can be checked by hand.

## Metrics

- **Task success rate:** correct answers, including correct abstentions when no active fact exists, divided by all queries.
- **Tokens used:** the sum of whitespace-separated tokens in each query plus the memory entries shown for that query.
- **Memory tokens used:** the memory-entry tokens shown across all queries. Compare this with `query_count * token_budget` for total available memory tokens.
- **Retrieval accuracy:** answerable queries that return the planted value and its target fact ID, divided by answerable queries. An abstention or an answer from the wrong source is incorrect.
- **Corruption count:** non-empty answers that differ from the active planted value for the queried subject and relation. This includes stale values and a value attached to the wrong subject. Correct abstentions do not add corruption.

Fact events are processed in fixture order. The ground-truth rules are `set` only when the key has no active value, `correct` always replaces its value, and `expire` removes it. Queries inspect only facts that appear earlier in that episode.

## Fixtures and output

`memorylab fixtures --out DIR` writes a canonical `episodes.json` file. Episodes include direct control lookups, a correction and expiration, distractors, and a corruption trap where a relation-only summary may attach Noah's value to Mira. All fixture content is synthetic and explicitly labelled.

`memorylab run --policy NAME` writes canonical JSON with query-level expected answers, selected evidence IDs, token counts, correctness flags, aggregate metrics, protocol details, and final inspectable policy memory. `memorylab report --format md|html` runs all six policies and writes a findings report with its protocol, results table, findings, limits, and honesty statement.

## Limits

The fixture set is small and hand-authored to make every result auditable. The policy implementations are simple deterministic rules. These results do not measure learned compression, embedding retrieval, real tool or agent systems, long-running deployments, or production workloads. The benchmark provides no evidence that any policy will perform similarly outside these fixtures.
