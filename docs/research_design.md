# 연구 설계

## Research Questions

1. Forecast/readiness artifacts와 agentic review artifacts를 하나의 release control state로 묶을 수 있는가?
2. Human review queue가 실제 product workflow의 중심 객체가 될 수 있는가?
3. Demo-ready와 public-deploy-ready를 분리하면 과장된 포트폴리오 배포 주장을 줄일 수 있는가?
4. 무검토 공개 기준선과 guarded policy를 비교하면 미검증 impact claim을 정량적으로 차단할 수 있는가?

## Evidence Plan

- 복합 데이터 결합: Stage 1 bike-share readiness/priority와 Stage 2 eval/prepublish/review queue를 결합한다.
- Leakage-safe validation: 새 모델 학습은 없고, upstream holdout metric을 release gate로 사용한다.
- Baseline: Stage 2 baseline agent metric을 비교 기준으로 유지한다.
- Main model/system: guarded decision agent와 Control Tower release rules.
- Ablation: API/write persistence 없는 read-only seed와 FastAPI/SQLite approval slice를 비교한다.
- Controlled comparison: `unsafe_auto_publish` 기준선과 `guarded_all_review`, `source_order_capacity`, `impact_guarded_capacity`를 같은 impact card 단위로 비교한다.
- Uncertainty/robustness: bike-share readiness `NO_GO`, missing artifact, empty queue, holdout 실패를 blocker로 둔다.
- Failure audit: `control_state.json`의 blocker list와 review queue 상태를 감사 표면으로 사용한다.
- Decision impact: public deploy 여부, reviewer approval backlog, public-claim blocked units, capacity-ranked action plan을 한 화면에서 판단한다.

## 한계와 윤리

- Raw CCTV, 내부 로그, token, `.env` 값은 사용하지 않는다.
- NY 511 sample은 공개 historical data이며 live dispatch authority가 아니다.
- 자동 출동과 자동 공개는 제공하지 않는다. Approval write action은 local SQLite audit trail에만 제한한다.
- Seoul validation이 `READY`여도 public deploy readiness가 `GO`가 아니면 impact 성과 claim은 계속 차단한다.
