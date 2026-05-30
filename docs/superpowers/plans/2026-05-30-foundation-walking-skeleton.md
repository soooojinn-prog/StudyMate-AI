# Foundation & Walking Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** StudyMate AI 프로젝트의 walking skeleton — FastAPI 백엔드, Next.js 프론트엔드, Docker Compose 통합, 모듈 경계 자동 강제(import-linter), lint/test CI를 셋업하고 `docker compose up` 한 줄로 양쪽이 통신하는 /health 페이지가 작동하도록 만든다.

**Architecture:** Modular Monolith. 백엔드는 `app/{api,agents,rag,learning,eval,core}` 6개 도메인 모듈로 분할하고 import-linter로 의존성 방향을 CI에서 강제한다. 프론트엔드는 Next.js 14 App Router + Tailwind + shadcn/ui. Docker Compose가 양쪽을 하나의 네트워크에 띄우고 프론트가 백엔드 `/health`를 호출해 자체 페이지에 렌더링한다.

**Tech Stack:** Python 3.12 / uv / FastAPI / Pydantic v2 / structlog / pytest / ruff / mypy strict / import-linter | Node 20 / pnpm / Next.js 14 / Tailwind | Docker Compose | GitHub Actions

**This plan is plan 1 of 7 in the StudyMate AI V1 series.** See `docs/superpowers/specs/2026-05-30-studymate-ai-design.md` §13 마일스톤.

**Deferred from spec §10:** shadcn/ui is part of the V1 stack but is not initialized in Plan 1 because the walking skeleton has no UI components beyond a status card. It will be initialized in Plan 4 (Study UI) where the first interactive components are introduced. The same applies to LangSmith (Plan 3) and Sentry (Plan 7).

---

## File Structure

```
studymate-ai/
├─ backend/
│  ├─ pyproject.toml                    # uv 프로젝트 + 의존성 + ruff/mypy/pytest 설정
│  ├─ .python-version                   # 3.12
│  ├─ .importlinter                     # 모듈 경계 규칙
│  ├─ Dockerfile                        # python:3.12-slim 기반
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main.py                        # FastAPI 진입점 + lifespan
│  │  ├─ api/
│  │  │  ├─ __init__.py
│  │  │  └─ routes/
│  │  │     ├─ __init__.py
│  │  │     └─ health.py                # GET /health
│  │  ├─ agents/__init__.py             # 빈 스켈레톤 (Plan 3에서 채움)
│  │  ├─ rag/__init__.py                # 빈 스켈레톤 (Plan 2)
│  │  ├─ learning/__init__.py           # 빈 스켈레톤 (Plan 5)
│  │  ├─ eval/__init__.py               # 빈 스켈레톤 (Plan 6)
│  │  └─ core/
│  │     ├─ __init__.py
│  │     ├─ settings.py                 # Pydantic settings (env)
│  │     └─ logging.py                  # structlog 셋업
│  └─ tests/
│     ├─ __init__.py
│     ├─ conftest.py                    # TestClient fixture
│     ├─ test_health.py                 # GET /health 통합 테스트
│     └─ test_import_boundaries.py      # import-linter 단언
├─ frontend/
│  ├─ package.json
│  ├─ pnpm-workspace.yaml               # (단일 패키지지만 락 안정성)
│  ├─ next.config.mjs
│  ├─ tsconfig.json
│  ├─ tailwind.config.ts
│  ├─ postcss.config.mjs
│  ├─ Dockerfile                        # node:20-alpine 기반
│  ├─ next-env.d.ts                     # next dev 첫 실행 시 자동 생성
│  ├─ src/
│  │  ├─ app/
│  │  │  ├─ layout.tsx
│  │  │  ├─ globals.css
│  │  │  ├─ page.tsx                    # 인덱스: /health로 안내
│  │  │  └─ health/
│  │  │     └─ page.tsx                 # 백엔드 /health 호출 + 렌더
│  │  └─ lib/
│  │     └─ api.ts                      # backend 클라이언트 (BACKEND_URL env)
├─ docker-compose.yml                   # api + frontend 서비스
├─ .github/
│  └─ workflows/
│     └─ ci.yml                         # lint + test (backend & frontend)
├─ Makefile                             # dev, test, lint, build, up, down
└─ README.md                            # 프로젝트 소개 + 실행 방법
```

### 파일별 책임

- **`backend/pyproject.toml`**: 단일 소스. 의존성, ruff/mypy/pytest 설정 모두 여기에. 별도 `ruff.toml`/`mypy.ini`/`pytest.ini`를 만들지 않는다.
- **`backend/app/main.py`**: FastAPI 인스턴스 생성 + 라우터 등록 + 로깅 lifespan. 비즈니스 로직 없음.
- **`backend/app/core/settings.py`**: 환경 변수만 다룬다. 다른 모듈은 `from app.core.settings import settings`로만 접근.
- **`backend/.importlinter`**: 모듈 경계 규칙 단일 소스. Spec §3.3 표를 그대로 코드화.
- **`frontend/src/lib/api.ts`**: 백엔드 URL/엔드포인트 함수 단일 진출입점. 페이지에서 fetch 직접 호출 금지.
- **`docker-compose.yml`**: 개발용. 프로덕션 배포는 V2 (Plan 7 이후).

---

## Task 1: Backend bootstrap (pyproject + 디렉토리 + 핵심 설정)

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.python-version`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/settings.py`
- Create: `backend/app/core/logging.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/agents/__init__.py`
- Create: `backend/app/rag/__init__.py`
- Create: `backend/app/learning/__init__.py`
- Create: `backend/app/eval/__init__.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Create `backend/.python-version`**

```
3.12
```

- [ ] **Step 2: Create `backend/pyproject.toml`**

```toml
[project]
name = "studymate-backend"
version = "0.1.0"
description = "StudyMate AI backend - multi-agent learning system"
requires-python = ">=3.12,<3.13"
dependencies = [
  "fastapi>=0.115",
  "pydantic>=2.9",
  "pydantic-settings>=2.5",
  "uvicorn[standard]>=0.32",
  "structlog>=24.4",
]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "pytest-cov>=5.0",
  "httpx>=0.27",
  "ruff>=0.7",
  "mypy>=1.13",
  "import-linter>=2.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RET", "PL", "PT"]
ignore = ["PLR0913"]  # too-many-arguments — FastAPI 라우터엔 흔함

[tool.mypy]
python_version = "3.12"
strict = true
disallow_untyped_decorators = false  # FastAPI 데코레이터 호환
warn_return_any = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "-ra --strict-markers --cov=app --cov-report=term-missing"
testpaths = ["tests"]
```

- [ ] **Step 3: Create `backend/app/__init__.py`** — empty file (just exists)

```python
```

- [ ] **Step 4: Create the six domain module `__init__.py` files** — empty files marking namespace packages

Files to create with empty content (just `""` or no content):
- `backend/app/api/__init__.py`
- `backend/app/api/routes/__init__.py`
- `backend/app/agents/__init__.py`
- `backend/app/rag/__init__.py`
- `backend/app/learning/__init__.py`
- `backend/app/eval/__init__.py`
- `backend/app/core/__init__.py`
- `backend/tests/__init__.py`

- [ ] **Step 5: Create `backend/app/core/settings.py`**

```python
"""Application settings loaded from environment variables."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level settings. Only environment access lives here."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "StudyMate AI"
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # CORS for the Next.js dev server
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

- [ ] **Step 6: Create `backend/app/core/logging.py`**

```python
"""structlog configuration. Call configure_logging() once at startup."""
import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog to emit JSON to stdout."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level)
        ),
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 7: Create `backend/app/main.py`**

```python
"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.core.logging import configure_logging
from app.core.settings import settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    return app


app = create_app()
```

- [ ] **Step 8: Install uv (skip if already installed) and sync dependencies**

Run from `backend/`:
```bash
uv sync
```

Expected: `Resolved N packages` and a new `uv.lock` file is created.

- [ ] **Step 9: Verify the app imports without runtime errors**

Run from `backend/`:
```bash
uv run python -c "from app.main import app; print(app.title)"
```

Expected: `StudyMate AI`

- [ ] **Step 10: Commit**

```bash
git add backend/
git commit -m "feat(backend): bootstrap FastAPI app with module skeleton"
```

---

## Task 2: Health endpoint with TDD

**Files:**
- Create: `backend/app/api/routes/health.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write the failing test in `backend/tests/test_health.py`**

```python
"""Tests for the health endpoint."""
from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "app" in body
    assert "version" in body
```

- [ ] **Step 2: Write the TestClient fixture in `backend/tests/conftest.py`**

```python
"""Pytest fixtures shared across the test suite."""
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 3: Run the test and verify it fails**

Run from `backend/`:
```bash
uv run pytest tests/test_health.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.routes.health'` (because `main.py` already imports it but the module doesn't exist yet) or `404` if you previously had a stub. Either confirms the test correctly drives the implementation.

- [ ] **Step 4: Implement `backend/app/api/routes/health.py`**

```python
"""Health check endpoint."""
from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.settings import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str


def _read_version() -> str:
    try:
        return version("studymate-backend")
    except PackageNotFoundError:
        return "0.0.0-dev"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=_read_version(),
    )
```

- [ ] **Step 5: Run the test and verify it passes**

Run from `backend/`:
```bash
uv run pytest tests/test_health.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/health.py backend/tests/conftest.py backend/tests/test_health.py
git commit -m "feat(backend): add /health endpoint with integration test"
```

---

## Task 3: Module boundary enforcement with import-linter

**Files:**
- Create: `backend/.importlinter`
- Create: `backend/tests/test_import_boundaries.py`

- [ ] **Step 1: Create `backend/.importlinter`**

```ini
[importlinter]
root_package = app
include_external_packages = True

[importlinter:contract:1]
name = api may only depend on agents, learning, eval, core
type = forbidden
source_modules =
    app.api
forbidden_modules =
    app.rag

[importlinter:contract:2]
name = agents must not import api
type = forbidden
source_modules =
    app.agents
forbidden_modules =
    app.api

[importlinter:contract:3]
name = rag must not import api, agents, learning, eval
type = forbidden
source_modules =
    app.rag
forbidden_modules =
    app.api
    app.agents
    app.learning
    app.eval

[importlinter:contract:4]
name = learning must not import api, agents, rag, eval
type = forbidden
source_modules =
    app.learning
forbidden_modules =
    app.api
    app.agents
    app.rag
    app.eval

[importlinter:contract:5]
name = core must not import any other app module
type = forbidden
source_modules =
    app.core
forbidden_modules =
    app.api
    app.agents
    app.rag
    app.learning
    app.eval
```

- [ ] **Step 2: Run import-linter to verify all contracts pass (skeleton is clean)**

Run from `backend/`:
```bash
uv run lint-imports --config .importlinter
```

Expected: `Contracts: 5 kept, 0 broken.`

- [ ] **Step 3: Write a guard test in `backend/tests/test_import_boundaries.py`**

```python
"""Verify the import-linter contracts pass. Acts as a CI tripwire if devs forget to run lint-imports."""
import subprocess
from pathlib import Path


def test_import_linter_contracts_hold() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["uv", "run", "lint-imports", "--config", ".importlinter"],
        cwd=backend_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"import-linter contracts broken:\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
```

- [ ] **Step 4: Run the test and verify it passes**

Run from `backend/`:
```bash
uv run pytest tests/test_import_boundaries.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Verify the contract actually catches violations (negative check)**

Add a temporary import in `backend/app/core/settings.py`:
```python
# Temporary intentional violation
import app.api  # noqa
```

Run from `backend/`:
```bash
uv run lint-imports --config .importlinter
```

Expected: `Contracts: 4 kept, 1 broken.` with the `core must not import any other app module` contract failing.

Now **revert** the temporary import:
```python
# Delete the offending line so the file matches Task 1 Step 5
```

Re-run:
```bash
uv run lint-imports --config .importlinter
```

Expected: `Contracts: 5 kept, 0 broken.`

- [ ] **Step 6: Commit**

```bash
git add backend/.importlinter backend/tests/test_import_boundaries.py
git commit -m "feat(backend): enforce module boundaries with import-linter"
```

---

## Task 4: Ruff + Mypy strict pass on the whole tree

**Files:**
- Modify: `backend/pyproject.toml` (already has tool sections from Task 1)
- Possibly Modify: any of the existing files if ruff/mypy reports issues

- [ ] **Step 1: Run ruff on the backend**

Run from `backend/`:
```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: `All checks passed!` for both. If formatting differs, run `uv run ruff format .` then commit.

- [ ] **Step 2: Run mypy on the backend**

Run from `backend/`:
```bash
uv run mypy app tests
```

Expected: `Success: no issues found in N source files`. If you see errors, fix them — common ones:
- Missing return annotations on test functions: tests already opted out via `[[tool.mypy.overrides]]`.
- `Untyped decorator` errors are silenced by `disallow_untyped_decorators = false`.

- [ ] **Step 3: Add a tiny sanity test that verifies ruff/mypy can be invoked**

This is intentionally minimal — the real enforcement is in CI (Task 10). We just want a guard that catches local breakage.

Create `backend/tests/test_lint_tools_runnable.py`:
```python
"""Smoke test: ruff and mypy CLIs are installed and callable."""
import subprocess


def test_ruff_invokable() -> None:
    result = subprocess.run(
        ["uv", "run", "ruff", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "ruff" in result.stdout.lower()


def test_mypy_invokable() -> None:
    result = subprocess.run(
        ["uv", "run", "mypy", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "mypy" in result.stdout.lower()
```

- [ ] **Step 4: Run the whole test suite to make sure nothing regressed**

Run from `backend/`:
```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_lint_tools_runnable.py
git commit -m "test(backend): smoke-test ruff and mypy availability"
```

---

## Task 5: Frontend bootstrap (Next.js 14 + Tailwind + pnpm)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/pnpm-workspace.yaml`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.mjs`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.mjs`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/globals.css`
- Create: `frontend/src/app/page.tsx`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "studymate-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000",
    "lint": "next lint",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "next": "14.2.18",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "@types/node": "20.16.10",
    "@types/react": "18.3.12",
    "@types/react-dom": "18.3.1",
    "autoprefixer": "10.4.20",
    "eslint": "8.57.1",
    "eslint-config-next": "14.2.18",
    "postcss": "8.4.49",
    "tailwindcss": "3.4.14",
    "typescript": "5.6.3"
  },
  "engines": {
    "node": ">=20",
    "pnpm": ">=9"
  }
}
```

- [ ] **Step 2: Create `frontend/pnpm-workspace.yaml`** (empty workspace declaration — keeps pnpm happy in a monorepo-friendly way)

```yaml
packages:
  - .
```

- [ ] **Step 3: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "src/**/*.ts", "src/**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 4: Create `frontend/next.config.mjs`**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",  // optimized Docker build
};

export default nextConfig;
```

- [ ] **Step 5: Create `frontend/tailwind.config.ts`**

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};

export default config;
```

- [ ] **Step 6: Create `frontend/postcss.config.mjs`**

```javascript
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

- [ ] **Step 7: Create `frontend/src/app/globals.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  color-scheme: light dark;
}

body {
  @apply bg-white text-gray-900 antialiased;
}
```

- [ ] **Step 8: Create `frontend/src/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StudyMate AI",
  description: "Multi-agent learning system for 정보처리기사 실기",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 9: Create `frontend/src/app/page.tsx`** (landing — points to /health for the skeleton)

```tsx
import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-3xl font-bold">StudyMate AI</h1>
      <p className="mt-2 text-gray-600">
        멀티 에이전트 기반 학습 시스템 (정보처리기사 실기 V1).
      </p>
      <Link
        href="/health"
        className="mt-6 inline-block rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
      >
        시스템 상태 확인 →
      </Link>
    </main>
  );
}
```

- [ ] **Step 10: Install dependencies**

Run from `frontend/`:
```bash
pnpm install
```

Expected: lockfile created, `node_modules/` populated. No errors.

- [ ] **Step 11: Verify the app builds**

Run from `frontend/`:
```bash
pnpm build
```

Expected: `✓ Compiled successfully` and `.next/standalone` directory created.

- [ ] **Step 12: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): bootstrap Next.js 14 + Tailwind + pnpm"
```

---

## Task 6: Frontend /health page calling backend

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/app/health/page.tsx`

- [ ] **Step 1: Create `frontend/src/lib/api.ts`**

```typescript
/**
 * Backend API client. All HTTP calls to the backend go through this module
 * so that page components never hardcode URLs.
 */
const DEFAULT_BACKEND_URL = "http://localhost:8000";

function backendUrl(): string {
  // BACKEND_URL is set by docker-compose for server components and at build
  // time. Falls back to localhost for local pnpm dev.
  return process.env.BACKEND_URL ?? DEFAULT_BACKEND_URL;
}

export type HealthPayload = {
  status: string;
  app: string;
  version: string;
};

export async function fetchHealth(): Promise<HealthPayload> {
  const res = await fetch(`${backendUrl()}/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Backend /health responded ${res.status}`);
  }
  return (await res.json()) as HealthPayload;
}
```

- [ ] **Step 2: Create `frontend/src/app/health/page.tsx`** (server component — fetches at request time)

```tsx
import { fetchHealth } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HealthPage() {
  let payload: Awaited<ReturnType<typeof fetchHealth>> | null = null;
  let error: string | null = null;

  try {
    payload = await fetchHealth();
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-bold">시스템 상태</h1>

      {error && (
        <div className="mt-4 rounded border border-red-300 bg-red-50 p-4 text-red-800">
          <p className="font-semibold">백엔드 호출 실패</p>
          <pre className="mt-2 whitespace-pre-wrap text-sm">{error}</pre>
        </div>
      )}

      {payload && (
        <dl className="mt-4 grid grid-cols-2 gap-y-2 rounded border border-gray-200 bg-gray-50 p-4">
          <dt className="font-semibold">Status</dt>
          <dd>{payload.status}</dd>
          <dt className="font-semibold">App</dt>
          <dd>{payload.app}</dd>
          <dt className="font-semibold">Version</dt>
          <dd>{payload.version}</dd>
        </dl>
      )}
    </main>
  );
}
```

- [ ] **Step 3: Run typecheck**

Run from `frontend/`:
```bash
pnpm typecheck
```

Expected: no errors.

- [ ] **Step 4: Manually verify locally before Docker (skip if no Python/Node setup yet — Task 9 verifies via Docker)**

Terminal A (from `backend/`):
```bash
uv run uvicorn app.main:app --reload --port 8000
```

Terminal B (from `frontend/`):
```bash
pnpm dev
```

Open `http://localhost:3000/health`. Expected: a card with `Status: ok`, `App: StudyMate AI`, `Version: 0.0.0-dev`.

Stop both processes (Ctrl+C in each terminal).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/app/health/page.tsx
git commit -m "feat(frontend): add /health page calling backend"
```

---

## Task 7: Backend Dockerfile

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`

- [ ] **Step 1: Create `backend/.dockerignore`**

```
__pycache__
*.pyc
*.pyo
.pytest_cache
.ruff_cache
.mypy_cache
.venv
tests
.env
.env.*
```

- [ ] **Step 2: Create `backend/Dockerfile`** (multi-stage, uv-based)

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Install uv (pinned version for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

# Install runtime deps only (no dev group)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY app ./app

# Install the project itself (without re-resolving dependencies)
RUN uv sync --frozen --no-dev

ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Build the backend image**

Run from `backend/`:
```bash
docker build -t studymate-backend:dev .
```

Expected: successful build ending with `naming to ... studymate-backend:dev done`.

- [ ] **Step 4: Smoke-test the image directly**

Run:
```bash
docker run --rm -p 8000:8000 --name studymate-backend-smoke studymate-backend:dev
```

In another terminal:
```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok","app":"StudyMate AI","version":"0.1.0"}` (or `0.0.0-dev` if metadata isn't installed — both acceptable).

Stop the container: `Ctrl+C` in the run terminal.

- [ ] **Step 5: Commit**

```bash
git add backend/Dockerfile backend/.dockerignore
git commit -m "build(backend): add Dockerfile (uv, multi-stage, slim)"
```

---

## Task 8: Frontend Dockerfile

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/.dockerignore`

- [ ] **Step 1: Create `frontend/.dockerignore`**

```
node_modules
.next
.turbo
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.env
.env.*
```

- [ ] **Step 2: Create `frontend/Dockerfile`** (multi-stage, leveraging Next.js standalone output)

```dockerfile
# syntax=docker/dockerfile:1.7
FROM node:20-alpine AS deps
RUN corepack enable && corepack prepare pnpm@9.12.3 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:20-alpine AS builder
RUN corepack enable && corepack prepare pnpm@9.12.3 --activate
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM node:20-alpine AS runner
ENV NODE_ENV=production
WORKDIR /app

# Copy the standalone Next.js server (smaller, no node_modules)
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
```

- [ ] **Step 3: Build the frontend image**

Run from `frontend/`:
```bash
docker build -t studymate-frontend:dev .
```

Expected: successful build.

- [ ] **Step 4: Smoke-test (without backend — should render landing page but /health will error)**

Run:
```bash
docker run --rm -p 3000:3000 --name studymate-frontend-smoke studymate-frontend:dev
```

Open `http://localhost:3000`. Expected: the landing page renders. `/health` will show "백엔드 호출 실패" — that's expected without backend running.

Stop the container: `Ctrl+C`.

- [ ] **Step 5: Commit**

```bash
git add frontend/Dockerfile frontend/.dockerignore
git commit -m "build(frontend): add Dockerfile (Next.js standalone output)"
```

---

## Task 9: Docker Compose integration

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: Create `.env.example`** at the project root

```bash
# Backend
APP_NAME=StudyMate AI
ENVIRONMENT=development
LOG_LEVEL=INFO
# JSON list — used by FastAPI CORS middleware
ALLOWED_ORIGINS=["http://localhost:3000"]

# Frontend
# How the frontend (server-side) reaches the backend inside the compose network
BACKEND_URL=http://api:8000
```

- [ ] **Step 2: Create `docker-compose.yml`** at the project root

```yaml
services:
  api:
    build:
      context: ./backend
    image: studymate-backend:dev
    container_name: studymate-api
    environment:
      APP_NAME: ${APP_NAME:-StudyMate AI}
      ENVIRONMENT: ${ENVIRONMENT:-development}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      ALLOWED_ORIGINS: ${ALLOWED_ORIGINS:-["http://localhost:3000"]}
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 10s
      timeout: 5s
      retries: 5

  frontend:
    build:
      context: ./frontend
    image: studymate-frontend:dev
    container_name: studymate-frontend
    environment:
      BACKEND_URL: ${BACKEND_URL:-http://api:8000}
      NODE_ENV: production
    ports:
      - "3000:3000"
    depends_on:
      api:
        condition: service_healthy
```

- [ ] **Step 3: Copy the example env file**

Run from the project root:
```bash
cp .env.example .env
```

(On Windows PowerShell: `Copy-Item .env.example .env`.)

- [ ] **Step 4: Bring the stack up**

Run from the project root:
```bash
docker compose up --build -d
```

Expected: both services build and start. `docker compose ps` shows both `studymate-api` and `studymate-frontend` as healthy/running.

- [ ] **Step 5: Verify the walking skeleton end-to-end**

```bash
# 1) Backend reachable from host
curl http://localhost:8000/health

# 2) Frontend reachable from host
curl -I http://localhost:3000

# 3) Frontend /health (server-side fetch to api:8000 inside docker network)
curl http://localhost:3000/health | grep -i "StudyMate AI"
```

Open `http://localhost:3000/health` in a browser. Expected: the card shows `Status: ok`, `App: StudyMate AI`, `Version: 0.1.0` (or `0.0.0-dev`). **No error banner.**

- [ ] **Step 6: Tear the stack down**

```bash
docker compose down
```

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "build: docker-compose wiring backend and frontend"
```

---

## Task 10: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend:
    name: Backend (lint + types + tests)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "0.5.4"
          enable-cache: true

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --frozen

      - name: Ruff lint
        run: uv run ruff check .

      - name: Ruff format check
        run: uv run ruff format --check .

      - name: Mypy
        run: uv run mypy app tests

      - name: Import boundaries
        run: uv run lint-imports --config .importlinter

      - name: Pytest
        run: uv run pytest

  frontend:
    name: Frontend (typecheck + build)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 9.12.3

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "pnpm"
          cache-dependency-path: frontend/pnpm-lock.yaml

      - name: Install
        run: pnpm install --frozen-lockfile

      - name: Typecheck
        run: pnpm typecheck

      - name: Lint
        run: pnpm lint

      - name: Build
        run: pnpm build
```

- [ ] **Step 2: Verify the workflow file is syntactically valid**

Locally, just check that the YAML parses:
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

Expected: no output (success).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: lint, typecheck, test on backend and frontend"
```

- [ ] **Step 4 (deferred until repo is pushed): Verify CI runs green on GitHub**

Once the project is pushed to GitHub, open the Actions tab and confirm the `CI` workflow runs on push/PR and both jobs pass. If a job fails, fix locally and amend the relevant task.

---

## Task 11: Makefile + README skeleton

**Files:**
- Create: `Makefile`
- Create: `README.md`

- [ ] **Step 1: Create `Makefile`** at the project root

```makefile
.PHONY: help install dev test lint typecheck build up down logs ci-local

help:
	@echo "StudyMate AI - common commands"
	@echo ""
	@echo "  install     install backend (uv sync) and frontend (pnpm install) deps"
	@echo "  dev         start backend (uvicorn) and frontend (pnpm dev) — see notes"
	@echo "  test        run backend pytest"
	@echo "  lint        run ruff + ruff format check + frontend lint"
	@echo "  typecheck   run mypy + frontend typecheck"
	@echo "  build       docker compose build"
	@echo "  up          docker compose up -d (production-like local)"
	@echo "  down        docker compose down"
	@echo "  logs        docker compose logs -f"
	@echo "  ci-local    run the same checks CI runs"

install:
	cd backend && uv sync
	cd frontend && pnpm install

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd frontend && pnpm lint

typecheck:
	cd backend && uv run mypy app tests
	cd frontend && pnpm typecheck

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

ci-local: lint typecheck test
	cd backend && uv run lint-imports --config .importlinter
	cd frontend && pnpm build
```

- [ ] **Step 2: Create `README.md`** at the project root

````markdown
# StudyMate AI

멀티 에이전트 기반 학습 시스템. **V1 도메인**: 정보처리기사 실기.

> 본 리포지토리는 포트폴리오 프로젝트입니다. 설계 근거는
> `docs/superpowers/specs/2026-05-30-studymate-ai-design.md` 를 참고하세요.

## Quick Start

전제 조건: Docker, Docker Compose v2.

```bash
cp .env.example .env
docker compose up --build -d

# 접속
open http://localhost:3000        # 프론트엔드 (Next.js)
open http://localhost:8000/docs   # 백엔드 OpenAPI
open http://localhost:3000/health # 통합 작동 확인
```

종료:
```bash
docker compose down
```

## 로컬 개발 (Docker 없이)

전제: Python 3.12, Node 20+, uv, pnpm.

```bash
make install
# Terminal A
cd backend && uv run uvicorn app.main:app --reload
# Terminal B
cd frontend && pnpm dev
```

## 자주 쓰는 명령

| 목적 | 명령 |
|---|---|
| 전체 테스트 | `make test` |
| 전체 린트 | `make lint` |
| 타입 체크 | `make typecheck` |
| CI 와 동일한 체크 | `make ci-local` |
| 컨테이너 로그 | `make logs` |

## 디렉토리 구조

설계 문서 §3.2 참고.

```
backend/   # FastAPI + LangGraph (Plan 3에서 추가) + RAG (Plan 2)
frontend/  # Next.js 14 + Tailwind
docs/      # specs, plans, ADR
```

## 모듈 경계 (백엔드)

`backend/.importlinter` 가 단일 소스. 위반 시 CI 실패.

## License

TBD (개인 포트폴리오, 외부 배포 시 라이선스 결정).
````

- [ ] **Step 3: Run `make ci-local` to verify all checks pass locally**

Run from the project root:
```bash
make ci-local
```

Expected: ruff/mypy/import-linter/pytest pass on backend; lint/typecheck/build pass on frontend.

(On Windows without GNU Make, run each subcommand manually as a fallback; or use `wsl make ci-local`.)

- [ ] **Step 4: Commit**

```bash
git add Makefile README.md
git commit -m "docs: add README quick start and Makefile shortcuts"
```

---

## Task 12: Verify the walking skeleton end-to-end one more time + sanity check

This is the gate: the entire plan is "done" only if a fresh `docker compose up` from a clean state produces a working /health page.

- [ ] **Step 1: Clean local state**

```bash
docker compose down -v
docker image rm studymate-backend:dev studymate-frontend:dev 2>/dev/null || true
```

- [ ] **Step 2: Rebuild and bring up**

```bash
docker compose up --build -d
docker compose ps
```

Expected: both services healthy/running.

- [ ] **Step 3: Programmatic smoke check**

```bash
# Backend
curl --fail http://localhost:8000/health
# Frontend page contains status info
curl --fail --silent http://localhost:3000/health | grep -i "Status"
```

Both should return 0. If either fails, debug before declaring done.

- [ ] **Step 4: Browser check**

Open `http://localhost:3000` → click "시스템 상태 확인 →" → confirm card renders `Status: ok`, `App: StudyMate AI`, no error banner.

- [ ] **Step 5: Tear down**

```bash
docker compose down
```

- [ ] **Step 6: Final commit (any leftover lockfile updates)**

```bash
git status
# If uv.lock or pnpm-lock.yaml changed during the verification, stage and commit.
git add backend/uv.lock frontend/pnpm-lock.yaml 2>/dev/null || true
git diff --cached --quiet || git commit -m "chore: lock files after walking-skeleton verification"
```

---

## Acceptance Criteria

Plan 1 is complete when **all** of the following hold:

1. `docker compose up --build` brings both `studymate-api` and `studymate-frontend` up healthy.
2. `http://localhost:3000/health` renders backend status in the browser without errors.
3. `make ci-local` exits 0 on a clean checkout.
4. `backend/.importlinter` enforces all 5 module-boundary contracts and the guard test in `tests/test_import_boundaries.py` passes.
5. `.github/workflows/ci.yml` is committed and ready to run on push (real CI verification deferred until repo is pushed to GitHub).

---

## What's Next

Plan 2: **RAG Pipeline & Indexing**. PDF 수집 스크립트, pdfplumber 추출, cleaner, chunker, BGE-M3 임베딩, topic_tagger (Haiku 호출), ChromaDB persistent client, retriever. 검증: `make seed`로 1년치 기출 인덱싱 + `retriever.retrieve(query)` 가 한국어 쿼리에 대해 적합한 chunk를 반환.
