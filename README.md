# StudyMate AI

멀티 에이전트 기반 학습 시스템. **V1 도메인**: 정보처리기사 실기.

> 본 리포지토리는 포트폴리오 프로젝트입니다. 설계 근거는
> `docs/superpowers/specs/2026-05-30-studymate-ai-design.md` 를 참고하세요.

## Quick Start

전제 조건: Python 3.12+, Node 20+, [uv](https://docs.astral.sh/uv/),
[pnpm](https://pnpm.io/), GNU Make (선택).

```bash
cp .env.example .env
make install

# 옵션 A: 한 줄로 둘 다 띄우기 (Make 필요)
make dev

# 옵션 B: Make 없으면 두 터미널에서 직접
#   Terminal 1: cd backend  && uv run uvicorn app.main:app --reload --port 8000
#   Terminal 2: cd frontend && pnpm dev
```

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
backend/   # FastAPI + LangGraph (Plan 3에서 추가) + RAG (Plan 2)
frontend/  # Next.js 14 + Tailwind
docs/      # specs, plans, ADR
```

## 모듈 경계 (백엔드)

`backend/.importlinter` 가 단일 소스. 위반 시 CI 실패.

## Docker?

V1에선 사용하지 않음. Windows에서 Docker Desktop의 RAM/디스크 비용을 피하고
재현성은 `uv.lock` + `pnpm-lock.yaml`로 확보. 선택적 컨테이너화는 Plan 7
참고.

## License

개인 포트폴리오 (라이선스 미정).
