# Decision Intelligence Copilot 아키텍처

최종 업데이트: 2026-07-22 KST

## 제품 경계

이 제품은 처음 보는 표 데이터를 자연어로 분석하는 경로와, versioned legacy hospital extract를 canonical EMR schema로 이관하는 case study를 한 화면에서 보여준다. 두 경로는 같은 검증·provenance 원칙을 공유하지만 실행 계약은 분리한다.

기본 제품 shell은 `분석 Copilot`, `Migration Lab`, `검증 결과`, `기술 상세` 4개 영역만 노출한다. 기존 운영 현황·후보 분석·검토/승인 화면은 recruiter-facing primary flow에서 제거했으며, 관련 API와 audit module만 backward compatibility와 regression을 위해 유지한다.

- 업로드 분석: 사용자 파일과 질문을 basic `AnalysisPlan`, 통계 `AdvancedAnalysisPlan`, 예측 `PredictionPlan` 중 하나로 변환한다.
- migration case: versioned synthetic source와 mapping을 `MigrationCase -> MigrationReport`로 변환한다.
- Evidence RAG: 문서와 운영 근거를 설명한다. 업로드 데이터의 숫자나 migration 결과를 계산하지 않는다.
- Safety router: planner와 retrieval보다 먼저 실행해 prompt injection, credential, write·deploy 요청을 차단한다.

## 데이터 분석 흐름

```text
CSV / JSON / XLSX / Parquet (request-scoped)
  -> report-title/preamble detection + deterministic header repair
  -> visible structure/rename map
  -> size, row, column, sensitive-header validation
  -> DatasetManifest + typed values
  -> automatic profile + quality/basic statistics + executable recommendations
  -> natural-language planner
  -> validated typed plan
       ├─ AnalysisPlan -> allowlisted SQL -> in-memory DuckDB
       ├─ AdvancedAnalysisPlan -> DuckDB filtered rows -> SciPy + pandas
       └─ PredictionPlan -> DuckDB filtered rows -> CPU sklearn workflow
  -> table/chart + row counts + SQL/model provenance + assumptions/limits
```

`AnalysisPlan`은 select, filter, group, aggregate, sort, limit만 표현한다. 임의 Python·SQL 문자열과 filesystem/network access는 허용하지 않는다. 숫자는 LLM이 만들지 않고 DuckDB가 계산하며, 72개 versioned schema·paraphrase·multi-turn task에서 pandas oracle과 독립 교차검증한다.

## 심화 통계와 예측 흐름

명시적인 histogram·IQR·차이 검정·Spearman·이동평균 질문만 `AdvancedAnalysisPlan`으로 라우팅한다. generic 합계·평균·상관계수 질문은 기존 `AnalysisPlan`에 남아 회귀 범위를 넓히지 않는다. 고급 plan은 operation별 모양을 닫는다. distribution/outlier/group/time은 수치 컬럼 1개, relationship은 2개, group comparison은 `group_by`, time series는 `time_column`이 반드시 필요하다. DuckDB가 parameterized filter와 source-row lineage를 적용한 전체 분모를 materialize하고 SciPy/pandas가 통계량을 계산한다.

| Operation | 계산 | 결과 경계 |
|---|---|---|
| distribution | quantile, sample stddev, skew, excess kurtosis, normality, histogram | 유효 분모·bin count·정규성 주의 |
| outliers | Tukey `1.5×IQR` 기본, source row 추적 | 이상치는 오류가 아니라 검토 후보 |
| group comparison | Welch/Mann-Whitney/ANOVA/Kruskal, CI, Cohen d/eta² | p-value와 효과크기·CI를 함께 표시 |
| relationship | Pearson/Spearman, p-value, slope, intercept, R² | 인과관계 주장 금지 |
| time series | time sort, raw/day/week/month aggregate, rolling/change/trend | 추세는 period 순서 기준 탐색값 |

`PredictionPlan`은 `regression`, `classification`, `forecasting`만 허용한다. regression/classification은 기본 60/20/20 train/validation/test, 시간 컬럼이 있으면 chronological split을 사용한다. forecast는 무작위 split을 금지하고 lag 1/2/7, rolling 3/7, trend/calendar feature와 3-fold rolling-origin validation을 사용한다. 전처리는 split 뒤 train에만 fit한다.

```text
safe rows + features
  -> leakage / unique-ID / constant / sample / class gate
  -> baseline fit on train
  -> bounded candidates fit on train
  -> validation primary metric comparison
       ├─ improvement < 1% -> NO_MODEL_GAIN (test candidate 미평가)
       └─ improvement >= 1% -> refit train+validation -> held-out test 1회
                                -> uncertainty + error audit + learning curve
                                -> permutation importance + bounded Shapley + model card
```

회귀 baseline은 median dummy, 분류는 most-frequent dummy, forecast는 validation에서 고른 last/seasonal naive다. 회귀 후보는 Ridge/RandomForest, 분류는 LogisticRegression/RandomForest, forecast는 Ridge/GradientBoosting으로 제한한다. 모든 estimator는 CPU, fixed seed, bounded tree/iteration 수를 사용한다. SHAP 외부 dependency는 추가하지 않고 raw feature 최대 8개, validation 최대 20행, deterministic permutation 최대 8개인 model-agnostic permutation-Shapley 근사를 명확한 method name으로 반환한다.

최소 표본은 supervised target 100행, class당 20행, forecast 60시점이다. 상수 target·target과 동일한 feature는 hard block한다. 이름과 고유비율이 ID 성격인 feature, 상수 feature는 제외하고 model card에 기록한다. validation에서 baseline을 1% 이상 개선하지 못하면 모델을 선택하지 않는다. 예측 결과는 업로드 데이터 내부의 offline evidence이며 외부 성능·인과효과를 보장하지 않는다.

업로드가 성공하면 browser는 별도 사용자 발화 없이 deterministic overview를 요청한다. 서버는 감지 제목·header·행/열과 결측·중복·summary row를 설명하고, 수치형 컬럼당 `count/min/Q1/mean/median/Q3/max/stddev`를 최대 8개까지 보여준다. exact 합계 성격 행은 원본 profile에는 남기되 overview 통계 분모에서 제외하고 `input/denominator/excluded` 행수를 공개한다. 이 overview 통계는 parser와 같은 request-scoped pandas profile에서 계산하며 `numeric_source_of_truth=pandas-profile`로 표시한다. 순위·그룹 비교·관계·빈도·품질 추천은 현재 schema로 생성하고, 버튼을 누르면 자연어 입력과 동일한 validated planner 및 DuckDB 실행 경로를 사용한다. 자동 overview 자체는 임의 SQL이나 LLM 계산을 실행하지 않는다.

후속 질문은 브라우저가 직전의 검증된 plan을 함께 보내면 limit·상/하위 방향·metric·group·filter를 제한적으로 수정한다. 예를 들어 “상위 2개” → “평균으로 바꿔줘” → “web만 보고 1개”는 기존 target을 유지하면서 metric과 filter만 바꾼다. 반대로 group·metric·target을 스스로 갖춘 “요일별 배출량(g) 평균”은 직전 plan의 operation과 무관하게 새 분석으로 계획한다. 따라서 rank `select` 다음에도 별도 `aggregate`를 바로 실행할 수 있다. `그중`, `바꿔줘`, `web만 보고` 같은 명시적 연결 표현 또는 자체 완결에 필요한 정보가 없는 짧은 수정만 이전 plan을 사용한다. 모호한 컬럼이나 지원하지 않는 분석은 추정 실행 대신 clarification을 반환한다.

browser는 업로드한 원본 payload, profile, 마지막 basic/advanced/prediction plan을 현재 page chat state에 유지한다. 각 질문은 같은 dataset과 해당 previous plan을 보내므로 filter·group·metric·target·rank, histogram bin, rolling window, forecast horizon 수정이 이어진다. 서로 다른 mode의 새 plan이 실행되면 이전 mode plan은 지워 잘못된 교차 수정이 일어나지 않는다. `대화만 초기화`는 transcript와 세 plan을 지우되 dataset을 유지하고, `분석 조건만 초기화`/“원본으로 돌아가”는 deterministic reset response 뒤 plan만 제거한다. 현재 file과 plan 요약은 별도 session panel에 표시한다. 서버에 dataset session을 영속화하거나 원본을 변형하지 않으며 page 종료·명시적 업로드 해제 시 browser memory에서 연결이 끝난다.

새 파일은 candidate로 먼저 `/api/data/analyze` 검증을 통과한 뒤에만 active dataset을 교체한다. empty·oversize·민감 header·손상 파일이 거절되면 file input만 비우고 이전 정상 dataset/profile/plan을 그대로 유지한다. 이 순서는 교체 실패가 기존 분석 세션의 데이터 손실로 번지는 것을 막는다.

Planner는 source column을 먼저 exact match하고, 그다음 제한된 semantic alias(`지역↔region/area`, `매출↔revenue/sales`, `날짜↔date`, `비용↔cost`, `상태↔status`)를 적용한다. alias 후보가 하나일 때만 자동 연결하며 `region`과 `area`가 함께 있는 것처럼 둘 이상이면 실제 후보명을 보여주고 clarification한다. 추이 질문은 temporal group + sum, 범주별 비율은 전체 또는 filter denominator 기준 `COUNT(*)` share, 최빈 질문은 group count 내림차순, 두 수치 컬럼의 관계는 correlation plan으로 변환한다. “분포”와 “중요한 특징”은 raw row select 대신 bounded overview 통계로 연결한다.

dataset이 첨부된 질문은 dataset-analysis namespace 안에서 닫힌다. planner가 실행 가능한 계획을 만들지 못해도 Evidence RAG로 fall-through하지 않으며, 현재 파일의 컬럼과 지원 범위를 근거로 clarification을 반환한다. 따라서 “가장 성과 좋은 지역은?”처럼 성과 metric이 명시되지 않은 질문이 제품 내부 policy 문서 답변으로 바뀌지 않는다. 통화·퍼센트·천단위 기호 때문에 문자열로 추론된 컬럼도 executor 422로 노출하지 않고, 정규화된 수치 컬럼이 필요하다는 조치를 안내한다.

chart renderer는 0을 중앙 기준으로 양수와 음수 막대를 모두 보존하고 음수를 별도 색으로 구분한다. upload validation, automatic overview, 질문, 추천 버튼은 하나의 request lock을 공유해 double-click이나 처리 중 reset/upload로 동일 분석이 중복 실행되지 않게 한다.

날짜-only 값은 calendar midnight를 timezone 없이 보존한다. 명시적 timezone timestamp만 UTC instant로 정규화한다. 따라서 `2026-06-03까지`는 6월 3일 행을 포함하며 host timezone에 따라 결과가 달라지지 않는다.

CSV/XLSX 첫 10행 안에서 희소한 보고서 제목·빈 preamble 뒤에 밀도 높은 문자형 header가 명확할 때 실제 header를 승격하고 완전 빈 행을 제외한다. 빈 이름·공백·`Unnamed`·중복·대소문자 충돌·숫자·과도하게 긴 header는 열 위치와 값을 유지한 채 복구한다. 자동 변경은 dataset profile과 browser 성공 상태에 구조/원본→정규화 mapping으로 노출한다. 민감 header, nested structure, 손상 파일, 크기/shape 한도는 복구 대상으로 간주하지 않고 계속 차단한다.

“이 데이터는 어떤 데이터지?” 같은 profile intent는 `SELECT *`로 실행하지 않는다. 감지한 제목, 실제 header, 행·열, 수치형 컬럼 수, 결측 수를 deterministic profile 답변으로 반환하고 이후 집계 질문을 안내한다.

“할 수 있는 분석은?”, “다른 분석 더 할 수 있는 거는?”, “또 뭐 볼 수 있어?” 같은 capability intent도 document RAG로 보내지 않는다. 현재 `DatasetManifest`에서 실제 컬럼과 지원 operation을 조합한 실행 가능한 질문만 deterministic하게 제안한다. 기본 pool은 순위·그룹 평균·상관·빈도·품질이고, 추가 pool은 중앙값·표준편차·하위 순위·다른 그룹/수치 관계로 구성한다. “심화 분석과 예측”을 명시하면 분포·IQR·Spearman·그룹 차이 검정을 먼저 제안하고, forecast 60시점 또는 supervised 100행 gate를 충족할 때만 예측 질문을 추가한다. 최근 12-turn history의 동일 추천은 걸러낸다. 모든 후보가 소진되면 이전 추천을 반복하는 대신 직접 지정할 컬럼·집계·필터를 안내한다. `합계·총계·소계` 성격의 행을 감지하면 평균·상관·재집계의 이중 집계 위험을 알리고, 해당 행의 제외 filter가 포함된 예시를 만든다.

추천 group은 원본 열 순서만 따르지 않는다. 고유값 비율이 80% 이상인 식별자형 범주를 뒤로 보내 `배출일 32/32`보다 `요일 7/32`처럼 반복 비교가 가능한 열을 우선한다. 사용자가 식별자형 열을 직접 지정하면 요청은 그대로 실행하지만, 모든 group count가 동일하면 비교 정보가 적다는 deterministic 관찰을 답변에 추가하고 균일한 막대차트는 생략한다.

`합계`, `총계`, `소계`, `subtotal`, `total`, `grand total` exact cell은 공통 detector가 column·label과 원본 행수를 보존한다. aggregate와 rank plan은 이 값을 `ne` filter로 기본 제외해 raw 32행과 denominator 31행을 구분한다. filter는 SQL·AnalysisPlan·답변에 공개하며 `합계 행도 포함해서` 또는 `include the total row`라는 명시적 요청은 최초 질문과 후속 질문 모두에서 기본 제외를 해제한다. 일반 행 조회는 원본 확인을 위해 자동 제외하지 않는다.

## Legacy Hospital Migration 흐름

```text
MS-SQL-style extract ─┐
                      ├-> versioned mapping -> canonical guardian -> patient -> encounter
Firebird-style extract┘                         | required / PK / FK validation
                                                -> accepted rows + reject lineage
                                                -> reconciliation + SHA-256 fingerprints
```

fixture는 실제 환자 정보가 없는 synthetic extract다. source row 20개 각각이 accepted 또는 rejected로 귀결되어 `20 = 11 + 9`가 성립한다. required field, invalid date, duplicate PK, missing FK를 의도적으로 포함하며, target PK/FK와 금액 합계는 독립 테스트로 다시 계산한다.

mapping transform은 allowlist(`strip`, `prefix`, `normalize_phone`, `species_map`, `parse_date`, `decimal_2`, `constant`)만 사용한다. source·mapping·result SHA-256과 idempotency key를 보고서에 보존한다. 이 작은 UI/API case 자체는 DB write를 하지 않는다. 실제 Firebird→PostgreSQL synthetic container integration은 [별도 ADR](architecture_decision_rdb_migration.md)과 `scripts/verify_rdb_migration.sh`에서 같은 contract의 adapter·transaction·recovery를 검증한다. 실제 의료 데이터와 production cutover·SLA는 두 경로 모두 범위 밖이다.

## 신뢰 경계

| 경계 | 보장 | 보장하지 않는 것 |
|---|---|---|
| Uploaded dataset | decoded 1MB, 10k rows, 100 cols; recoverable header repair; automatic bounded overview; request/session only | nested values, multi-file join, arbitrary code |
| Analysis planner | typed plan과 allowlisted operation | 모든 자연어 분석 지원 |
| DuckDB executor | parameterized read-only numeric source of truth | LLM 기반 수치 추정 |
| Advanced executor | DuckDB lineage + bounded SciPy/pandas statistics | 자동 인과 추론, 무제한 검정 탐색 |
| Prediction executor | baseline/validation/test, CPU bounds, model card | production 성능, causal impact, persisted model serving |
| Migration engine | deterministic validation, lineage, reconciliation | live DB extraction/target write |
| Evidence RAG | allowlisted source citation과 safety state | dataset·migration 수치 계산 |
| Public Pages | recorded read-only product walkthrough | live upload/free-form API |

## 검증 증거

- Analysis evaluation: `scripts/evaluate_analysis.py`, `tests/fixtures/analysis_golden_tasks.json`
- Data Science evaluation: `scripts/evaluate_data_science.py`, `tests/fixtures/data_science_golden_tasks.json`
- Migration reconciliation: `scripts/run_migration_case.py`, `tests/test_migration_case.py`
- API/UI contracts: `tests/test_app.py`, `tests/test_dashboard_ui_contract.py`, `scripts/verify_dashboard_ui.py`
- Real browser flow: `scripts/capture_demo_screenshots.py`
- Full regression: `scripts/run_all.sh`

내부 golden set과 automated browser test는 재현 가능한 engineering evidence다. 독립 사용자 5명의 usability 검증은 별도 외부 gate로 유지하며 완료 전에는 `portfolio-ready`를 선언하지 않는다.
