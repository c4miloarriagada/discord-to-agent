### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `.gitignore`, `.env.example`, `Makefile`
- Create: `src/__init__.py`, `src/domain/__init__.py`, `src/application/__init__.py`, `src/infrastructure/__init__.py`, `src/infrastructure/agents/__init__.py`, `src/interface/__init__.py`, `tests/__init__.py`, `tests/application/__init__.py`, `tests/infrastructure/__init__.py`, `tests/interface/__init__.py` (all empty)

**Interfaces:**
- Consumes: nothing.
- Produces: installable environment; `pytest` discovers `tests/` with `pythonpath = .` so `from src.... import ...` works.

- [ ] **Step 1: Write `requirements.txt`**

```
discord.py==2.6.4
pydantic==2.11.5
pydantic-settings==2.9.1
python-dotenv==1.1.0
structlog==25.3.0
pytest==8.4.0
pytest-asyncio==1.0.0
pytest-cov==6.2.1
ruff==0.12.0
```

- [ ] **Step 2: Write `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
pythonpath = .
```

- [ ] **Step 3: Write `.gitignore`**

```
.env
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.coverage
htmlcov/
.ruff_cache/
*.egg-info/
dist/
build/
```

- [ ] **Step 4: Write `.env.example`**

```env
DISCORD_BOT_TOKEN=your_bot_token_here
ALLOWED_CHANNEL_IDS=123456789,987654321
ALLOWED_USER_IDS=
WORKING_DIR=/home/user/projects
AGENT_TYPE=kimi
KIMI_COMMAND=kimi
KIMI_AUTO_APPROVE_FLAG=--yolo
KIMI_SESSIONS_DIR=~/.kimi-code/sessions
KIMI_CONTEXT_WINDOW=1048576
PROMPT_TIMEOUT=300
RATE_LIMIT_SECONDS=10
LOG_LEVEL=INFO
```

- [ ] **Step 5: Write `Makefile`**

```make
.PHONY: install test coverage run lint

install:
	pip install -r requirements.txt

test:
	pytest

coverage:
	pytest --cov=src/application --cov=src/infrastructure --cov-report=term-missing --cov-fail-under=60

run:
	python -m src.interface.bot

lint:
	ruff check src tests
```

- [ ] **Step 6: Create the empty `__init__.py` files listed above**

```bash
mkdir -p src/domain src/application src/infrastructure/agents src/interface tests/application tests/infrastructure tests/interface
touch src/__init__.py src/domain/__init__.py src/application/__init__.py src/infrastructure/__init__.py src/infrastructure/agents/__init__.py src/interface/__init__.py tests/__init__.py tests/application/__init__.py tests/infrastructure/__init__.py tests/interface/__init__.py
```

- [ ] **Step 7: Create a venv, install, and fix any pin that fails**

```bash
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Expected: install succeeds. If a pinned version does not exist, run `.venv/bin/pip index versions <pkg>` (or `pip install <pkg>==` and read the available versions in the error), pick the closest stable version, update `requirements.txt`, and re-run until clean. All later `pytest`/`python` commands in this plan use `.venv/bin/`.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt pytest.ini .gitignore .env.example Makefile src tests
git commit -m "chore: project scaffolding"
```

---

