# RAG Chat 목표 진행 기록

기준일: 2026-07-16 KST

## 목적

DecisionOps Suite의 기술 구성은 충분하지만 첫 방문자가 제품을 즉시 이해하기 어렵다. Control Tower를 chat-first surface로 바꾸고, 기존 evidence와 guardrail을 실제 RAG·citation 경험으로 연결한다.

## Baseline

- 상위 및 Stage 1/2/3 Git worktree: clean, `main...origin/main`
- Control Tower: FastAPI, dashboard, SQLite approval, audit chain/replay, hosted fail-closed auth, optional LLM reviewer 존재
- Public Pages: recorded read-only dashboard `GO`
- Hosted write API: target secret 미설정으로 의도적 `NO_GO`
- 공백: chat endpoint/UI, corpus ingestion, vector database, claim-level citation, golden RAG evaluation

## 구현 방법과 파라미터

- Product surface: 기존 Control Tower FastAPI와 self-contained HTML renderer 확장
- Retrieval: authoritative structured facts + lexical field/section search + dense vector search의 hybrid 방식
- Vector DB: Qdrant REST API, local/container 우선
- Test/snapshot adapter: deterministic memory store, runtime mode를 명시적으로 노출
- Default embedding: CPU·offline 재현이 가능한 deterministic provider부터 시작하고 provider contract를 분리
- 안전 상태: `ANSWER`, `REFUSE`, `REVIEW_REQUIRED`, `NEEDS_MORE_EVIDENCE`

## 완료한 구현

- `/api/chat`, `/api/data/analyze`, Chat-first responsive dashboard
- Qdrant REST collection/upsert/query와 deterministic memory adapter
- structured + lexical + vector retrieval, claim/citation validator
- CSV/JSON profile의 session-only evidence 분리와 persistent-store 회귀 테스트
- optional OpenAI Responses API의 strict JSON schema와 provider failure fallback
- prompt injection·실행·승인·배포·민감정보 요청 refusal
- public Pages recorded read-only chat와 secret/write exclusion contract
- 데스크톱 1440px·모바일 390px screenshot 및 overflow/console QA

## 정량 결과

- 36 golden cases: 36/36 pass
- status accuracy·retrieval recall@3·citation validity/completeness: 100%
- citation precision: 92.6%
- unsafe refusal 6/6, abstention 3/3
- Qdrant warm retrieval p95 7.3ms, cold index + query 78.8ms
- browser QA: desktop/mobile horizontal overflow 0, console error 0

동일 v1.1 oracle로 정규화한 baseline end-to-end pass 58.3%에서 router 분리, source filtering, lexical retrieval, source diversity, deterministic safety gate를 적용해 100%로 개선했다. 상세 결과는 `docs/evaluation/rag_evaluation.md`에 기록했다.

## 현재 판단

Chat-first vertical slice의 구현·정량 검증·시각 증거와 release gate를 완료했다. 전체 regression 78건, 실제 Qdrant golden evaluation, Compose app+Qdrant smoke, public snapshot smoke, README/상위 portfolio 동기화가 모두 통과했다. Control Tower PR #6과 suite README PR 3건을 main에 병합했고, main CI·private demo smoke·Pages 배포 및 공개 URL read-only smoke도 성공했다. Hosted write API는 배포 target secret이 없으므로 기존 의도대로 `NO_GO`를 유지한다.
