# Decision Intelligence Copilot holdout-schema and conversation challenge

- generated: `2026-07-21T03:09:58.960463Z`
- golden set: `v1.1` (`sha256:344d2013696d…`)
- datasets/cases: **5 / 72**
- oracle: `independent-pandas-dataframe-operations`

## Scorecard

| Metric | Result |
|---|---:|
| End-to-end pass rate | 100.0% |
| Planning accuracy | 100.0% |
| AnalysisPlan schema validity | 100.0% |
| Numeric execution correctness | 100.0% |
| Paraphrase challenge (24 cases) | 100.0% |
| Multi-turn plan revision (8 cases) | 100.0% |

## Failed cases

All holdout-schema cases passed.

## Interpretation

이 평가는 planner에 domain별 컬럼명을 hard-code하지 않은 상태에서 versioned holdout schema, template과 겹치지 않는 paraphrase, 이전 AnalysisPlan을 수정하는 multi-turn case를 함께 사용한다. 수치는 DuckDB 결과를 별도 pandas 연산 oracle과 비교한다. 문항은 프로젝트 내부에서 설계했으므로 실제 외부 사용자 usability를 대신하지 않는다.
