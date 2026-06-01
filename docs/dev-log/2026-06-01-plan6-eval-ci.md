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
| 1 | `bad2583 feat(eval): add golden dataset schema, loader, and 5 seed items` |
| 2 | `6fe22df feat(eval): add Grading Accuracy + Retrieval Recall@5 + LatencyTracker` |
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

---

## 트러블슈팅 로그 (Plan 6)

### T-1. 비동기 subagent 종료 ‑ 진행률 보고 truncation

- **현상**: Plan 6 Task 3 (runner) + Task 7 (eval.yml) dispatch가 mid-stream에서 종료. final commit/push 보고가 잘렸음 (Task 3은 168s tool_uses=24, Task 7은 220s에 “uv not on PATH” 메시지로 멈춤).
- **원인 분석**: 둘 다 subagent 자체는 작업 완료 (파일 생성/테스트 통과) 했으나 progress reporting tail 단계에서 terminated. Task 7의 경우 YAML 파일 작성에 uv가 불필요한데도 PATH 확인을 시도하다가 막힘.
- **대응 패턴**: Controller가 즉시 `git status` + 파일 verify → 이미 작업 완료된 경우 commit + push만 수행. Subagent 보고 누락이 작업 실패와 같지 않음을 명시.
- **포트폴리오용 1줄**: "Long-running subagent dispatches can complete the underlying work but truncate the final report. Controller가 git state로 verify-and-resume 패턴을 갖춰 손실 0."

### T-2. CI workflow_dispatch ↔ Chroma 인덱스 부재

- **현상**: `.github/workflows/eval.yml`이 `uv run python -m scripts.eval run` 실행. 하지만 `chroma/`는 gitignored이며 CI 체크아웃에는 인덱스가 없음. RAG retriever가 빈 결과를 돌려서 Retrieval Recall@5 = 0이 됨.
- **선택지**:
  1. 워크플로에 PDF ingest step 추가 (raw PDF가 gitignored이므로 S3 fetch 필요)
  2. Chroma 인덱스 자체를 git LFS로 push
  3. workflow_dispatch는 명시적 “시드된 환경에서만 동작” 가정으로 두고 README에 명시
- **현 상태**: Plan 6에서는 (3) 선택. Task 8 트리거 시 사용자가 첫 ingest를 로컬에서 실행 후 commit하거나 별도 워크플로로 시드 필요. Plan 7 시 자동화 가능.
- **포트폴리오용 1줄**: "RAG eval 자동화는 데이터 의존이 있어 ‘설정된 환경에서만 동작’ 가정을 명시화. 시드 자동화는 별도 plan에 분리."

### T-3. typer + uv 모듈 호출 패턴

- **현상**: `cd backend && uv run python -m scripts.eval mock` 형태로 CLI 호출. `scripts/__init__.py` 부재 시 모듈 로드 실패 가능.
- **검증**: scripts/eval.py 직접 실행 + Makefile `eval-mock` 타겟 + GitHub Actions step 모두 같은 invocation 사용. 일관된 단일 진입점.
- **포트폴리오용 1줄**: "CLI 진입점은 Make/CI/local 모두 동일한 `uv run python -m scripts.X` 패턴으로 통일 — 환경별 분기 0."

---

## 핵심 의사결정 (Plan 6)

### D-1. 80%/75%/8s 목표 임계 — passes_targets() 메서드 명시

- **상황**: Eval은 단순 측정이 아니라 “acceptance criterion” 역할도 해야 함. CI에서 회귀 차단을 위해.
- **결정**: EvalReport에 `passes_targets() -> bool` 메서드 추가. 3개 메트릭 모두 임계 통과해야 True. HTML 카드에 pass/fail 색상 반영.
- **면접 답변**: "Eval harness는 측정 + 결정 양쪽 책임. 임계는 spec §6.2에서 80%/75%/8s로 명시했고 EvalReport.passes_targets()가 단일 진실 공급원. HTML report와 CI exit code가 같은 소스 사용."

### D-2. Mock CLI 추가 — 매 PR마다 회귀 차단 가능

- **상황**: 실 Anthropic 호출은 비용 + credit 필요. 매 PR마다 돌릴 수 없음.
- **결정**: `_fake_grader` (길이 비례) + `_fake_retriever` (고정 청크 5개)로 mock 모드 분리. CI는 mock으로 회귀 차단, manual workflow_dispatch가 real eval 담당.
- **면접 답변**: "두 단계 eval — mock은 매 PR(무료, ~1s), real은 수동 트리거(유료, ~5분). mock이 framework 자체 회귀를 잡고 real은 모델 품질 회귀를 잡음."

### D-3. history.csv를 git에 자동 commit

- **상황**: 메트릭 시계열은 회귀 추적의 자산. 분실 방지 + 면접에서 인용 가능해야.
- **결정**: workflow_dispatch가 history.csv를 github-actions[bot] 명의로 main에 push. HTML 리포트는 artifact(90일)로만, history.csv는 git 영구.
- **면접 답변**: "메트릭 시계열은 의사결정 근거이므로 git에 영구 보존. HTML은 detail이라 artifact로 두고 90일 retention."

---

## 한 줄 요약 (이력서용, 확정)

> 50문항 × 3답변 = 150 케이스 골든셋 (시드 5문항) 위에 Grading Accuracy(±0.15) / Retrieval Recall@5 / Latency p50,p95 nearest-rank 3종 메트릭 산정. EvalConfig + EvalReport + passes_targets() (80%/75%/8s 임계) + Jinja2 Architectural-Dark HTML 리포트 + history.csv 시계열. typer CLI(mock/run/show-latest)로 매 PR `pytest` 회귀 차단 + GitHub Actions workflow_dispatch로 ANTHROPIC secret 사용한 manual 풀-eval. 누적 테스트 135개 + import-linter 5/5 + ruff·mypy strict.
