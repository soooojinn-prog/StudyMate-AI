# StudyMate AI

멀티 에이전트 기반 학습 시스템. **V1 도메인**: 정보처리기사 실기.

> 본 리포지토리는 포트폴리오 프로젝트입니다. 설계 근거는
> `docs/superpowers/specs/2026-05-30-studymate-ai-design.md` 를 참고하세요.

## Quick Start

전제 조건: Python 3.12+, Node 20+, [uv](https://docs.astral.sh/uv/),
[pnpm](https://pnpm.io/), GNU Make (선택).

```bash
# 백엔드(.env)와 프론트엔드(frontend/.env.local)는 별도 파일에서 환경 변수를 읽습니다.
cp .env.example .env
cp frontend/.env.example frontend/.env.local
make install

# 옵션 A: 한 줄로 둘 다 띄우기 (Make 필요)
make dev

# 옵션 B: Make 없으면 두 터미널에서 직접
#   Terminal 1: cd backend  && uv run uvicorn app.main:app --reload --port 8000
#   Terminal 2: cd frontend && pnpm dev
```

> Windows에서는 `cmd` 또는 Git Bash에서 Make를 실행하세요. PowerShell에서 Make
> 가 인식되지 않으면 옵션 B를 사용하세요.

접속:
- 프론트엔드: <http://localhost:3000>
- 백엔드 OpenAPI: <http://localhost:8000/docs>
- 통합 작동 확인: <http://localhost:3000/health>

## 자주 쓰는 명령

| 목적 | 명령 |
|---|---|
| 의존성 설치 | `make install` |
| 동시 실행 | `make dev` |
| 백엔드만 | `make dev-backend` |
| 프론트엔드만 | `make dev-frontend` |
| 전체 테스트 | `make test` |
| 전체 린트 | `make lint` |
| 타입 체크 | `make typecheck` |
| CI 와 동일한 체크 | `make ci-local` |

## 디렉토리 구조

```
backend/   # FastAPI + LangGraph (Plan 3) + RAG (Plan 2) + Learning (Plan 5) + Eval (Plan 6)
frontend/  # Next.js 14 + Tailwind + Architectural-Dark 디자인 (Plan 4)
docs/      # specs, plans, ADR, design-explorations, dev-log
```

## 구현 현황 (Plans 1-6 완료, Plan 7 선택)

| Plan | 결과물 | 상태 |
|---|---|---|
| 1. Foundation | 모듈러 모놀리식 + import-linter + ruff/mypy + CI | ✅ |
| 2. RAG | pdfplumber + BGE-M3 + ChromaDB + topic tagger | ✅ (Task 12 E2E 사용자 액션) |
| 3. LangGraph | Coordinator(Haiku) + QuestionGenerator(Sonnet) + Grader(Sonnet) + HITL | ✅ |
| 4. Study UI | FastAPI 세션 API + Next.js /study (Architectural-Dark) | ✅ (Task 10 E2E 사용자 액션) |
| 5. Learning Records | SQLAlchemy + Alembic + 약점 분석 + /dashboard | ✅ (Task 8 E2E 사용자 액션) |
| 6. Eval & CI | 골든셋 + 3 메트릭 + Jinja2 HTML 리포트 + typer CLI + workflow_dispatch | ✅ (Task 8 manual trigger 사용자 액션) |
| 7. Polish + Docker | 선택적 컨테이너화 + 운영 관측성 | 미시작 |

- **누적 테스트**: 135 (백엔드 pytest)
- **import-linter**: 5/5 contracts kept
- **ruff (E,F,I,B,UP,SIM,RET,PL,PT) + mypy strict + import-linter** 통합 품질 게이트
- **Architectural-Dark 디자인** — Fraunces italic + JetBrains Mono + Pretendard, 깊은 navy + cyan + amber 액센트

자세한 내용:
- 면접·이력서 답변 키트: `docs/dev-log/INTERVIEW_POINTS.md`
- Plan별 회고/메트릭/트러블슈팅: `docs/dev-log/`
- 디자인 결정 ADR: `docs/design-explorations/DECISION.md`

## 모듈 경계 (백엔드)

`backend/.importlinter` 가 단일 소스. 위반 시 CI 실패.

## Docker?

V1에선 사용하지 않음. Windows에서 Docker Desktop의 RAM/디스크 비용을 피하고
재현성은 `uv.lock` + `pnpm-lock.yaml`로 확보. 선택적 컨테이너화는 Plan 7
참고.

## License

개인 포트폴리오 (라이선스 미정).
