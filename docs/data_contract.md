# 데이터 계약

## 목적

`Decision Intelligence Copilot`이 session-only 업로드 데이터와 versioned synthetic migration fixture를 처리하고, 기존 Stage 1/2 산출물을 control state, review queue, policy audit, reviewer evidence로 변환하는 계약을 기록한다.

## 업로드 분석 계약

| 항목 | 계약 |
|---|---|
| 입력 | CSV, JSON, XLSX, Parquet 단일 dataset |
| 한도 | decoded 1MB, 10,000행, 100열 |
| 보존 | request와 browser session 안에서만 사용; SQLite·Qdrant·artifact에 원본 미저장 |
| 자동 복구 | 제목/빈 행 뒤 실제 header 승격, 완전 빈 데이터 행 제외, 빈/공백 header, Excel-style `Unnamed`, 중복·대소문자 충돌, 숫자 header, 120자 초과 이름 |
| 거부 | credential-like header, 중첩 JSON/Parquet, 손상 파일, 한도 초과 |
| 오류 응답 | 표준 API는 HTTP 422와 원인 문자열; browser는 `response_envelope=true`에서 HTTP 200의 `status=rejected`로 같은 원인을 받아 inline 표시 |
| 자동 overview | 업로드 성공 직후 설명, 결측·중복·summary row, 수치형 기초통계, current-schema 추천을 deterministic하게 반환 |
| 계획 | validated `AnalysisPlan`·`AdvancedAnalysisPlan`·`PredictionPlan`; extra field 금지 |
| 계산 | in-memory DuckDB read-only filter/lineage + bounded SciPy·pandas·CPU sklearn |
| 결과 | table/chart, 분모, SQL provenance, 통계 가정 또는 baseline/test/error/explanation/model card |

browser session에서 active dataset은 정상적인 새 파일 교체 또는 사용자의 `업로드 해제` 전까지 유지된다. `대화만 초기화`는 transcript와 previous plan만 초기화하고 dataset은 유지한다. `분석 조건만 초기화`, `원본으로 돌아가`, `새 분석 시작`은 `mode=analysis-session-reset`을 반환해 누적 filter·group·metric·sort·limit를 제거하지만 원본 payload와 profile은 유지한다. active plan의 group·metric·filter·limit는 UI에 사람이 읽을 수 있는 형태로 표시한다.

후속 metric 질문에 새 수치 컬럼이 명시되면 operation뿐 아니라 target도 함께 교체한다. 예를 들어 `region별 revenue 합계` 뒤 `orders 평균으로 바꿔줘`는 region group과 기존 filter는 보존하고 target을 `orders`, operation을 `mean`으로 바꾼다. 특정 컬럼의 `필터 제거`는 그 컬럼 filter만 제거하고, `조건 없이`·`전체로`는 전체 filter를 제거한다. 이 동작은 원본 DataFrame mutation이 아니라 다음 read-only `AnalysisPlan` 생성이다.

이전 plan이 있어도 현재 질문이 group·metric·target 또는 독립적인 row filter/rank를 충분히 명시하면 새 plan으로 시작한다. `합계 행을 제외하고 배출량(g) 기준 상위 5개`의 `select` 결과 뒤 `합계 행을 제외하고 요일별 배출량(g) 평균`을 요청하면 기존 select를 수정하지 않고 새 `aggregate`를 생성한다. `평균으로 바꿔줘`, `그중 상위 1개`, `web만 보고`처럼 연결 표현이 있거나 target/group이 생략된 질문만 previous plan을 수정한다. 완결된 질문을 이전 operation에 강제로 적용하다 실패하는 clarification은 허용하지 않는다.

파일 교체는 validate-before-swap이다. candidate가 검증을 통과하기 전 active dataset을 비우지 않으며 거절 시 기존 dataset/profile/plan을 계속 사용한다. browser가 각 요청에 dataset을 다시 전달하고 서버는 request 종료 후 저장하지 않으므로, sticky session은 server-side raw data persistence를 추가하지 않는다.

Header 복구는 원본 열 순서와 셀 값을 바꾸지 않는 deterministic 전처리다. 빈 이름은 1-based 위치를 사용해 `column_1`처럼 만들고, 중복 또는 대소문자만 다른 이름은 `_2`, `_3` suffix로 구분한다. 공백·control character는 정리하고 `Unnamed: n` placeholder는 실제 위치 기반 이름으로 교체한다. 120자를 넘는 이름은 suffix 공간을 포함해 제한 안으로 자른다. 같은 파일은 항상 같은 이름을 만들며 `column_name_normalization.changes`에 position, original, normalized, reason을 반환해 browser가 변경 내역을 표시한다.

CSV/XLSX의 첫 행이 보고서 제목처럼 희소하고 뒤쪽 행이 충분히 밀도 높은 문자형 header일 때만 첫 10행 안에서 실제 header를 승격한다. 선택한 원본 행 번호, 제외한 preamble/빈 행 수, 감지한 제목은 `table_structure_normalization`에 반환한다. 이 정보는 “이 데이터는 어떤 데이터지?” 같은 질문에서 SQL을 실행하지 않고 제목·컬럼·행수·수치형/결측 수를 설명하는 근거로 사용한다.

업로드 성공 직후 browser는 같은 session dataset으로 자동 overview를 요청한다. `overview.quality`은 전체 결측 셀, 완전히 같은 중복 행, exact summary row 수를 반환한다. `overview.statistics`는 수치형 컬럼별 non-null count, missing, min, Q1, mean, median, Q3, max, sample stddev를 반환하고 UI는 최대 8개 수치형 컬럼을 표시한다. 합계 성격 행은 원본 profile과 input row count에는 남기되 기초통계 분모에서는 기본 제외하며 `input_row_count`, `denominator_row_count`, `excluded_summary_row_count`를 함께 공개한다. 이 값은 request-scoped pandas profile이 계산하며 source를 `pandas-profile`로 명시한다. 자동으로 생성된 추천은 label과 실제 자연어 question을 함께 가지며, 클릭 시 수동 입력과 동일하게 validated `AnalysisPlan`과 DuckDB 결과·chart·SQL provenance를 반환한다. 추천 자체가 분석 성공을 보장한다는 뜻은 아니며 planner의 clarification과 지원 범위 제한은 그대로 적용한다.

“할 수 있는 분석은?”과 “다른/더/또/추가 분석” 표현은 문서 검색 근거 부족으로 기권하지 않고 현재 dataset schema를 근거로 처리한다. 응답은 planner가 지원하는 순위·group aggregate·correlation·count·median·stddev·profile 범위에서만 예시를 만들며 SQL을 즉시 실행하지 않는다. 기본 후보와 추가 후보를 분리하고 `history`의 user turn을 정규화해 같은 추천 문장이 있으면 제외한다. 반환하는 각 후보는 `{label, question}` 형태의 `suggested_questions`이며 클릭 시 같은 `/api/chat` planner/executor 경계를 통과한다. 범주 추천은 고유값 비율 80% 이상인 식별자형 열을 후순위로 두어 반복 비교가 가능한 열을 우선한다. 정확히 `합계`, `총계`, `소계`, `subtotal`, `total`, `grand total`인 셀이 있으면 summary row 수를 공개하고, aggregate·rank plan에는 해당 column/value의 `ne` filter를 기본 적용한다. 원본 profile 행수는 바꾸지 않으며 input row count와 denominator를 분리해 반환한다. 일반 select는 원본 확인을 위해 자동 제외하지 않고, `합계 행도 포함해서`라는 명시적 요청은 기본 filter를 적용하지 않거나 후속 plan에서 제거한다. 사용자가 질문을 실행할 때만 validated plan과 DuckDB 결과를 반환한다.

자연어 column 해석은 exact source name을 우선하고, 제한된 한국어/영문 semantic alias는 source 후보가 정확히 하나일 때만 적용한다. 같은 alias에 `region`과 `area`처럼 여러 source column이 연결되면 임의 선택하지 않고 후보 column을 포함한 clarification을 반환한다. 지원 intent에는 profile·capability·overview, aggregate/rank/filter, temporal trend, categorical share, most-frequent count, two-numeric correlation이 포함된다. `share` metric은 column 없이 `COUNT(*) / SUM(COUNT(*)) OVER ()`로 계산하므로 기존 filter가 있으면 조건 통과 행수가 분모다.

dataset이 연결된 상태에서 planner가 질문을 해석하지 못하면 document RAG로 전환하지 않는다. `mode=analysis-clarification`, `retrieval.vector_store=not_used_for_analysis_clarification`을 반환해 현재 파일 밖 근거가 섞이지 않았음을 공개한다. 통화기호·퍼센트·천단위 구분자를 포함해 string으로 추론된 값에 numeric metric을 요청한 경우도 HTTP 422 대신 같은 clarification 계약으로 정규화 필요성을 설명한다. 현재 버전은 단위 의미가 달라질 수 있는 값을 묵시적으로 숫자로 변환하지 않는다.

시각화는 signed numeric row를 삭제하지 않으며 0축 기준 양·음수 bar를 모두 렌더링한다. browser는 upload validation부터 automatic overview와 사용자/추천 질문까지 단일 in-flight request만 허용하고, 처리 중 submit·upload·reset·추천 control을 잠근다. 이 잠금은 계산 결과 계약을 바꾸지 않는 client-side 중복 방지 장치다.

“모든 데이터”를 무조건 수용하지는 않는다. 행/열/크기 제한, 민감정보로 추정되는 header, 손상된 container, 평면 table로 안전하게 해석할 수 없는 nested value는 계속 fail-closed한다.

## 심화 분석 계약

`AdvancedAnalysisPlan` contract version은 `decisionops-advanced-analysis-plan-v1`이다. 허용 operation은 `distribution`, `outliers`, `group_comparison`, `relationship`, `time_series`뿐이다. 임의 callable, expression, Python/SQL text를 받지 않는다.

- value column은 numeric manifest여야 하며 relationship만 정확히 2개, 나머지는 1개다.
- group comparison은 value와 다른 `group_by` 1개, time series는 value와 다른 `time_column` 1개가 필수다.
- filter는 기존 parameterized `FilterClause`를 재사용하고 DuckDB가 원본 zero-based `__decisionops_source_row__`와 함께 적용한다.
- histogram bin은 5~50, IQR multiplier는 0.5~5.0, rolling window는 2~90, confidence는 0.80~0.99다.
- group은 2~50개다. auto 검정은 정규성 증거에 따라 parametric/nonparametric을 고르며 method·p-value·effect size·CI·가정을 결과에 공개한다.
- distribution은 최소 3개, outlier는 4개, relationship/time series는 3개의 유효 관측이 필요하다. 결측/변환 불가 제외 수를 별도로 경고한다.
- chart payload는 최대 500 point, 상세 row는 최대 200개다. 500개가 넘는 시계열 chart만 균등 downsample하며 계산 통계는 전체 분모를 사용한다.

`AdvancedAnalysisResult`는 input/filtered/valid row count, statistics, rows, structured chart, warnings, assumptions, DuckDB source-row SQL provenance, `numeric_source_of_truth=scipy+pandas`를 반환한다.

## 예측 계약

`PredictionPlan` contract version은 `decisionops-prediction-plan-v1`이다. raw estimator parameter, arbitrary model class, serialized model upload를 받지 않는다.

| Gate | 계약 |
|---|---|
| 표본 | regression/classification target 100행 이상, classification class당 20행 이상, forecast 60시점 이상 |
| target | regression/forecast numeric, 모든 task 2개 이상 값; constant target 차단 |
| leakage | target과 값이 동일한 feature hard block; time/target feature 중복 금지 |
| ID/constant | 이름+고유비율 ID feature 및 상수 feature 자동 제외, model card 기록 |
| split | IID 60/20/20, time은 chronological; forecast random split contract 단계에서 거부 |
| baseline | median dummy, most-frequent dummy, last/seasonal naive 중 task별 지정 |
| promotion | validation primary metric이 baseline보다 최소 1% 개선될 때만 test 평가·model 선택 |
| uncertainty | regression/forecast split-conformal absolute residual, classification predicted-class probability |
| explanation | validation permutation importance; raw feature 최대 8개·20행·8 permutations bounded Shapley |
| runtime | CPU only, fixed seed 기본 42, bounded estimator size, request 종료 후 model/raw row 미저장 |

회귀 primary metric은 MAE이고 RMSE/R²를 함께 제공한다. 분류는 macro-F1이 primary이며 balanced accuracy, binary 가능 시 ROC-AUC, confusion matrix/per-class error를 제공한다. forecast는 MAE primary, RMSE/sMAPE와 3-fold rolling-origin validation, horizon 1~30, lag/rolling/calendar feature를 제공한다. prediction candidate를 test 기준으로 고르지 않는다. `NO_MODEL_GAIN`이면 selected model, candidate test metric, SHAP을 만들지 않는다.

`PredictionResult`는 split evidence, baseline validation/test, candidate validation, selected test metrics, row-level actual/prediction/interval or confidence, learning curve/rolling validation, error analysis, permutation importance, bounded Shapley metadata, model card, chart와 source-row SQL provenance를 반환한다. 이 결과는 동일 upload 내부의 offline evidence이며 production SLA·외부 일반화·인과효과 계약이 아니다.

## Legacy Hospital Migration 계약

`src/decisionops_control_tower/fixtures/legacy_hospital_migration.json`은 실제 환자 정보가 없는 versioned synthetic extract다. MS-SQL-style과 Firebird-style source를 canonical `guardian -> patient -> encounter` 순서로 변환한다.

`migration_rehearsal.py`는 같은 mapping contract로 source 120,000행을 생성해 temporary SQLite staging에 2,500행 단위로 적재한다. data와 checkpoint는 같은 transaction에 commit하며 의도적 중단 후 새 connection에서 재개한다. 완료 후 동일 config replay는 0행을 처리해야 하고, required source column rename은 database 연결·target write 전에 실패해야 한다.

`rdb_migration.py`는 별도 Compose stack에서 Firebird 5 source table 3개와 PostgreSQL 17 canonical target을 실제로 연결한다. default source는 table별 40,000행, 총 120,000행이다. Firebird system catalog column set이 아래 mapping contract와 다르면 PostgreSQL domain write 전에 중단한다. 각 PostgreSQL batch는 target row, accepted/reject lineage, checkpoint를 같은 transaction에 commit하며, injected mid-batch failure 뒤 새 connection에서 checkpoint 다음 row부터 재개한다.

- 모든 source row는 accepted 또는 rejected 한쪽으로만 귀결된다.
- required field, primary key, foreign key를 순서대로 검증한다.
- reject에는 source system/table/row/key, target table, reason code, detail을 남긴다.
- source, mapping, result SHA-256과 idempotency key를 반환한다.
- fixture/API 경로는 허용된 transform만 실행하며 live DB 접속과 target write를 하지 않는다.
- 별도 RDB integration 경로만 synthetic container DB에 write하며 실제 병원 DB·PHI를 사용하지 않는다.
- 현재 fixture의 기대 reconciliation은 source 20행 = accepted 11행 + rejected 9행이다.

## 원천

| 원천 | 역할 | 공개성 |
|---|---|---|
| Bike-share station readiness | public deploy blocker와 snapshot readiness | upstream public/derived artifact |
| Bike-share station priority/inventory | 운영 ML decision surface | upstream public/derived artifact |
| Seoul Ddareungi priority/validation | impact card 후보 action과 validation guardrail | Seoul Open Data derived artifact |
| Agentic DecisionOps eval metrics | guarded/holdout success와 invalid action gate | generated artifact |
| Agentic review queue | reviewer approval workload | generated artifact |
| NY 511 incident surface | incident evidence와 publication guardrail | public open-data sample |

## 라이선스 및 사용 조건

- Bike-share와 Agentic Workbench 산출물은 이전 portfolio project의 derived artifact다.
- NY 511 incident surface는 public open-data sample에서 파생된 decision surface다.
- Control Tower는 원천 raw data를 재배포하지 않고, review/product decision artifact만 생성한다.

## 결합 방식

원천 간 raw row join은 하지 않는다. Stage 1/2 산출물을 run-level control state로 결합하고, Stage 2 review queue row를 Control Tower approval queue row로 projection한다. Seoul Ddareungi priority row는 `impact_cards`로 projection하며, validation summary와 public deploy readiness가 모두 준비되지 않으면 public-claim blocker를 붙인다.

`impact_policy_audit`는 무검토 공개 기준선과 guarded policy를 같은 후보 단위로 비교한다. Public `GO` 이후에도 `model_validated_estimate_claim`, `unsafe_realized_impact_claim`, `guarded_realized_impact_claim`을 함께 생성해 모델 검증 추정치와 현장 실현 효과를 분리한다. `reviewer_action_plan`은 영향 우선 정렬, 누적 후보 단위, confidence threshold, public-claim state/scope를 reviewer가 바로 처리할 action row로 투영한다.

`reviewer_policy_robustness`는 동일 impact card에 `baseline`, unit-estimate jitter, confidence stress, top-candidate dropout을 적용한다. Source order, impact guarded, confidence-weighted guarded policy를 capacity 3/6/8에서 비교해 confidence-adjusted units, oracle regret, invalid evidence, selection Jaccard를 기록한다.

`reviewer_evidence_bundles`는 `impact_card_id`로 impact card와 action plan을 join한다. 각 row는 source 관측 시각, 생성 시각, 3시간 freshness SLA, source age, freshness status, SHA-256 fingerprint를 보존한다. `fresh`가 아니면 `reviewer_decision=needs_more_evidence`와 blocked lock 상태로 강제한다.

`agent_reviewer_brief`와 `agent_candidate_review_notes`는 health/API/artifact에서 읽은 source status, claim-safety rule, evidence refs, 다음 검토 action만 저장한다. Agent artifact는 approval write, field dispatch, public deploy 판단, 신규 효과 추정을 하지 않는다.

`approval_history`는 `approval-history-sha256-v1` canonical payload로 각 결정을 이전 event hash에 연결한다. Integrity verifier는 chain을 검산하고 control별 마지막 결정을 replay해 현재 `control_queue.approval_state`와 owner를 대조한다. Legacy row는 hash column이 비어 있을 때 한 번만 backfill하며, 이후 mismatch는 자동 복구하지 않는다.

## 분석 단위

- Control state: pipeline run 1회당 1개 JSON.
- Review queue: Stage 2 `queue_id` 또는 `task_id` 단위 pending decision.
- Impact cards: Seoul station priority 단위 후보 action, 후보 이동량, evidence, validation blocker.
- Impact policy audit: unsafe publish, guarded all-review, estimate-vs-realized claim scope, source-order capacity, impact-guarded capacity의 public-claim 위반 비교.
- Reviewer policy robustness: 4 scenarios × 3 capacities × 3 policies의 deterministic stress comparison. 실현 효과나 인과 추정치가 아니다.
- Reviewer action plan: 검토 용량이 제한될 때 먼저 볼 후보, 누적 후보 단위, local-only 승인/근거요청 판단.
- Reviewer evidence bundle: impact/action join, source trace, freshness gate, deterministic content fingerprint, claim boundary.
- AI reviewer brief: run 단위 source status, claim-safety lock, top risks, next actions, limitations.
- Candidate review notes: 상위 impact card 후보별 evidence refs, local-only next actions, public-claim blocker.
- Dashboard: run 시점의 blocker, metric, queue snapshot.
- Approval history: reviewer가 API/dashboard에서 남긴 chained local decision audit trail.
- Approval audit integrity: event chain 검산, queue-state replay, 최초 invalid event와 mismatch 수.
- Ops metrics: artifact freshness, queue summary, auth enabled flag, configured role names, runtime uptime.
- Deployment readiness: local private demo, container demo, hosted write API, public read-only snapshot의 분리된 GO/NO_GO 판단.
- Target: `demo_mode_ready`, `public_deploy_decision`, reviewer approval backlog.
- Uploaded analysis: browser session의 단일 dataset과 mode별 마지막 validated basic/advanced/prediction plan.
- Migration case: source row, target entity, reject lineage, table reconciliation 단위.

## 저장 정책

| 구분 | 위치 | Git 포함 여부 |
|---|---|---|
| raw upstream data | upstream project artifact roots | 제외 |
| processed control surface | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/` | 제외 |
| impact cards | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/impact_cards.*` | 제외 |
| impact policy audit | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/impact_policy_audit.*` | 제외 |
| reviewer policy robustness | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/reviewer_policy_robustness.*` | 제외 |
| reviewer action plan | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/reviewer_action_plan.*` | 제외 |
| reviewer evidence bundles | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/reviewer_evidence_bundles.*` | 제외 |
| agent reviewer brief | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/agent_reviewer_brief.json` | 제외 |
| candidate review notes | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/agent_candidate_review_notes.json` | 제외 |
| reports | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/` | 제외 |
| dashboard | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/dashboard/` | 제외 |
| approval SQLite | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/control_tower.sqlite` | 제외 |
| approval audit integrity | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/approval_audit_integrity.json` | 제외 |
| deployment readiness | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/deployment_readiness.*` | 제외 |
| public-safe aggregate snapshot | `tests/fixtures/public_demo_inputs.json` | 포함 |

## 누수 위험

- 이 product slice는 새 모델 학습 split이 아니라 upstream artifact orchestration과 approval workflow다.
- Public read-only 판단은 allowlist aggregate의 upstream readiness와 freshness를 그대로 반영하고 임의로 `GO`로 바꾸지 않는다. Hosted write API는 credential/target gate로 별도 판단한다.
- Impact card는 `estimated_delta_vs_no_action_units`, `model_validated_estimate_units`, `realized_delta_vs_no_action_units`, `impact_evidence_tier`, `realized_impact_status`, `public_claim_scope`를 분리한다. 기존 `verified_delta_vs_no_action_units`는 backward-compatible model-validation alias이며 실현 성과를 뜻하지 않는다.
- Impact card의 후보 단위는 public deploy readiness 전 production 성과가 아니라 reviewer evidence이며, readiness가 `GO`여도 field outcome이 없으면 realized-impact claim을 차단한다.
- Policy audit은 unsafe baseline의 미검증 claim 단위를 명시하고 guarded policy가 이를 0으로 낮추는지 검증한다.
- Evidence bundle은 timezone-aware source timestamp만 허용한다. 3시간 SLA 초과, timestamp 누락/오류/미래 시각은 local approval 후보에서도 제외한다.
- SHA-256 fingerprint는 canonical JSON의 impact card와 action plan content drift를 탐지하지만 서명 기반 origin authentication은 제공하지 않는다.
- Approval audit chain은 decision payload와 queue state의 local tamper evidence를 제공하지만, 서명된 외부 anchor가 없으므로 host 관리자 수준 공격을 방어하는 공증 수단은 아니다.
- Review queue approval write action은 `CONTROL_TOWER_ROLE_TOKENS`가 설정되면 reviewer/admin 역할 credential을 요구하고, local SQLite에만 기록하며 upstream artifact, 외부 시스템, field action을 변경하지 않는다.
- AI Reviewer Agent는 read-only이며 `GO/NO_GO`, public claim safety, 숫자 원천을 deterministic artifact에서 가져오고 새 claim을 만들지 않는다.
- Structured request log는 secret/header value 없이 request metadata만 남긴다.
- Monitoring snapshot은 latest JSON과 append-only JSONL history를 reports 아래에 남긴다.
- Deployment readiness gate는 credential 값 없이 auth configured 여부, role 이름, Docker/buildx 상태, public deploy blocker만 기록한다.
- 내부 데이터, 개인정보, raw CCTV, token, `.env` 값은 Control Tower source와 artifact에 복사하지 않는다.
