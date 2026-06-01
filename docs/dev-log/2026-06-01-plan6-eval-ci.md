# Plan 6 — Evaluation System & Metrics CI (진행 중)

- **기간**: 2026-06-01 ~ (진행 중)
- **상태**: 8 tasks 중 6 완료 (Task 7 진행 중, Task 8은 사용자 액션 대기)
- **결과물 (예정)**: GoldenItem 스키마 + 5 seed items (50 full은 추후 작성), 3개 메트릭 calculator (Grading Accuracy ±0.15, Retrieval Recall@5, Latency p50/p95), runner orchestrator, Jinja2 HTML 리포트, typer CLI (mock/run/show-latest), GitHub Actions workflow_dispatch.

---

## 한 줄 요약 (이력서용, 잠정)

> 면접 어필의 핵심 — "동작한다"를 데이터로 입증하는 eval harness. 50문항 × 3답변 골든셋(시드 5개 + 추후 확장)에 대해 Grading Accuracy(±0.15) / Retrieval Recall@5 / Latency p50,p95 3종 메트릭 산정, Architectural-Dark 테마 HTML 리포트 + history.csv 시계열, 매 PR `pytest`로 단위 검증, `workflow_dispatch`로 ANTHROPIC secret 사용한 manual 풀-eval 실행.

---

## 메트릭 (잠정)

| 시점 | 누적 테스트 수 | 비고 |
|---|---|---|
| Task 0 (Plan 5 종료) | 107 | 베이스라인 |
| Task 1 완료 | 114 | Dataset 스키마 (GoldenItem/SampleAnswer 3-tier excellent/acceptable/wrong) + 5 seed items (정규화/SQL/TCP/OOP/디자인패턴) + load_golden + jinja2 추가 + 7 tests |
| Task 2 완료 | 124 | 3 metric calculators — grading_accuracy(±0.15 tol), retrieval_recall_at_k, LatencyTracker (nearest-rank p50/p95) + 10 tests |
| Task 3 완료 | 131 | Runner orchestrator — EvalConfig(frozen) + EvalReport(passes_targets 80%/75%/8s) + PerCaseResult + run_eval + to_json + 7 fake-callback tests |
| Task 4 완료 | 135 | HTML report (Architectural-Dark Jinja2 template) + render_html + save_report (HTML + history.csv append) + 4 tests |
| Task 5 완료 | 135 | __init__ 공개 surface 재수출 (12 symbols) |
| Task 6 완료 | 135 | typer CLI (mock/run/show-latest) + Makefile eval 타겟 3개 + .gitignore HTML 제외 — mock CLI E2E 검증 완료 |

### 누적 commits (Plan 6)

| Task | commit |
|---|---|
| 1 | (Task 1 commit hash — see git log) |
| 2 | (Task 2 commit hash — see git log) |
| 3 | `2f5a117 feat(eval): add runner orchestrator with grading + retrieval + latency metrics` |
| 4 | `bf48401 feat(eval): add HTML report renderer + history.csv appender` |
| 5 | (inline — merged into next push due to no untracked changes) |
| 6 | `8dce6c7 feat(eval): add typer CLI (mock/run/show-latest) and make eval targets` |

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
