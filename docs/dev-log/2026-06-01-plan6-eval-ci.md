# Plan 6 — Evaluation System & Metrics CI (진행 중)

- **기간**: 2026-06-01 ~ (진행 중)
- **상태**: 8 tasks 중 0 완료
- **결과물 (예정)**: GoldenItem 스키마 + 5 seed items (50 full은 추후 작성), 3개 메트릭 calculator (Grading Accuracy ±0.15, Retrieval Recall@5, Latency p50/p95), runner orchestrator, Jinja2 HTML 리포트, typer CLI (mock/run/show-latest), GitHub Actions workflow_dispatch.

---

## 한 줄 요약 (이력서용, 잠정)

> 면접 어필의 핵심 — "동작한다"를 데이터로 입증하는 eval harness. 50문항 × 3답변 골든셋(시드 5개 + 추후 확장)에 대해 Grading Accuracy(±0.15) / Retrieval Recall@5 / Latency p50,p95 3종 메트릭 산정, Architectural-Dark 테마 HTML 리포트 + history.csv 시계열, 매 PR `pytest`로 단위 검증, `workflow_dispatch`로 ANTHROPIC secret 사용한 manual 풀-eval 실행.

---

## 메트릭 (잠정)

| 시점 | 누적 테스트 수 | 비고 |
|---|---|---|
| Task 0 (Plan 5 종료) | 107 | 베이스라인 |

### 누적 commits (Plan 6)

| Task | commit |
|---|---|

---

## 다음 진행 예정

| Task | 내용 |
|---|---|
| 1 | Dataset 스키마 + 5 seed items + loader (jinja2 추가) |
| 2 | Metric calculators (grading_accuracy, retrieval_recall_at_k, LatencyTracker) |
| 3 | Runner orchestrator (mock + real, EvalReport, passes_targets) |
| 4 | HTML report (Jinja2 template + save_report + history.csv) |
| 5 | __init__ 공개 surface 재수출 |
| 6 | typer CLI (mock/run/show-latest) + Makefile 타겟 |
| 7 | GitHub Actions workflow_dispatch (eval.yml) |
| 8 | E2E 풀 eval (사용자 액션 — credit + browser HTML 확인) |
