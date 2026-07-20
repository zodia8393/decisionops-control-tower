# RAG golden-set evaluation

- generated: `2026-07-20T01:44:27.019246Z`
- cases: **36**
- vector store: `qdrant`
- embedding: `hashing-char-ngram-v1`
- generation: deterministic fallback only (`LLM called = false`)
- golden set: `v1.1` (`sha256:7adab2f5a77e…`)

## Scorecard

| Metric | Result |
|---|---:|
| End-to-end pass rate | 100.0% |
| Status accuracy | 100.0% |
| Retrieval recall@k | 100.0% |
| Citation precision | 92.6% |
| Citation validity | 100.0% |
| Claim citation completeness | 100.0% |
| Unsafe refusal accuracy | 100.0% |
| Abstention accuracy | 100.0% |
| Mean retrieval latency | 6.255 ms |
| p95 retrieval latency | 7.252 ms |
| Cold-start index + retrieval | 78.816 ms |

## Improvement from baseline

| Metric | Baseline | Current | Delta |
|---|---:|---:|---:|
| End-to-end pass rate | 58.3% | 100.0% | +41.7 pp |
| Status accuracy | 58.3% | 100.0% | +41.7 pp |
| Retrieval recall@k | 92.6% | 100.0% | +7.4 pp |
| Citation precision | 71.6% | 92.6% | +21.0 pp |
| Citation validity | 100.0% | 100.0% | +0.0 pp |
| Claim citation completeness | 100.0% | 100.0% | +0.0 pp |
| Unsafe refusal accuracy | 83.3% | 100.0% | +16.7 pp |
| Abstention accuracy | 100.0% | 100.0% | +0.0 pp |

## Category results

| Category | Cases | Pass rate |
|---|---:|---:|
| abstention | 3 | 100.0% |
| candidate | 5 | 100.0% |
| dataset | 3 | 100.0% |
| deployment | 5 | 100.0% |
| documentation | 5 | 100.0% |
| freshness | 5 | 100.0% |
| policy | 4 | 100.0% |
| refusal | 6 | 100.0% |

## Failed cases

All golden cases passed.

## Interpretation

이 평가는 실제 운영 산출물과 versioned documentation을 대상으로 수행한다. LLM 문장 품질과 외부 provider availability는 분리하고, application-owned status·retrieval·citation·safety contract를 재현 가능하게 측정한다. Citation precision은 golden question에 지정한 source family와 provenance의 일치율이며, claim의 semantic entailment를 판정하는 별도 judge 점수는 아니다.
