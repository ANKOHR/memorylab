# MemoryLab findings

> MemoryLab uses deterministic rules on synthetic episodes. Token-overlap similarity is not embeddings. No trained models, real agent memory, or real retrieval systems are involved. Findings apply to these fixtures only.

## Protocol

- Fixture label: Synthetic fictional benchmark data. No real people or agents.
- Fixture seed: 0; no random number generator is used.
- Episodes: 4; policies: 6.
- Memory token budget: 128 whitespace-separated tokens per query. Query text is counted in total token use but is outside that memory budget.
- Events are processed in listed order. `set` changes an absent key, `correct` replaces its value, and `expire` removes it.
- Token-overlap ranking counts shared distinct lowercase alphanumeric tokens. Ties prefer the later event, then the lexically smaller fact ID.

## Results

| Policy | Task success | Retrieval accuracy | Memory tokens used / budget | Total tokens used | Corruptions |
| --- | ---: | ---: | ---: | ---: | ---: |
| full_context | 100.00% (7/7) | 100.00% (6/6) | 107 / 896 | 127 | 0 |
| summary | 71.43% (5/7) | 50.00% (3/6) | 30 / 896 | 50 | 2 |
| token_overlap | 100.00% (7/7) | 100.00% (6/6) | 107 / 896 | 127 | 0 |
| episodic | 100.00% (7/7) | 100.00% (6/6) | 107 / 896 | 127 | 0 |
| structured | 100.00% (7/7) | 100.00% (6/6) | 54 / 896 | 74 | 0 |
| hybrid | 100.00% (7/7) | 100.00% (6/6) | 39 / 896 | 59 | 0 |

## Findings

- Highest task success on this fixture set: full_context, token_overlap, episodic, structured, hybrid at 100.00%.
- Lowest memory-token total: summary at 30 tokens.
- The summary policy answered Mira's assigned-to query with 'South'; the planted answer is 'North'. This fixture records 1 corruption for that policy.
- These observations describe only the listed synthetic episodes and configured budget.

## Metric definitions

- **task_success_rate:** Correct answers, including correct abstentions, divided by all queries.
- **tokens_used:** Whitespace tokens in each query plus the memory entries shown for that query.
- **memory_tokens_used:** Whitespace tokens in shown memory entries; this is compared with the per-query memory budget.
- **retrieval_accuracy:** Queries with a planted target fact answered with that value and source fact ID, divided by answerable queries.
- **corruption_count:** Non-empty answers that differ from the active planted value for the queried subject and relation.

## Limits

The fixture set is small, scripted, synthetic, and designed for hand checking. It does not sample real users, real agents, production memory stores, or real retrieval workloads. The policies are simplified deterministic rules, not trained models. Token overlap is literal token matching, not embeddings. The results do not establish which architecture is best in general and do not generalize to real agents or real workloads.

## Honesty statement

MemoryLab uses deterministic rules on synthetic episodes. Token-overlap similarity is not embeddings. No trained models, real agent memory, or real retrieval systems are involved. Findings apply to these fixtures only.
