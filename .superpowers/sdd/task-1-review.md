b016b85 chore: project scaffolding

 .env.example                          | 12 ++++++++++++
 .gitignore                            | 12 ++++++++++++
 Makefile                              | 16 ++++++++++++++++
 pytest.ini                            |  4 ++++
 requirements.txt                      |  9 +++++++++
 src/__init__.py                       |  0
 src/application/__init__.py           |  0
 src/domain/__init__.py                |  0
 src/infrastructure/__init__.py        |  0
 src/infrastructure/agents/__init__.py |  0
 src/interface/__init__.py             |  0
 tests/__init__.py                     |  0
 tests/application/__init__.py         |  0
 tests/infrastructure/__init__.py      |  0
 tests/interface/__init__.py           |  0
 15 files changed, 53 insertions(+)

diff --git a/.env.example b/.env.example
new file mode 100644
index 0000000..413d6b8
--- /dev/null
+++ b/.env.example
@@ -0,0 +1,12 @@
+DISCORD_BOT_TOKEN=your_bot_token_here
+ALLOWED_CHANNEL_IDS=123456789,987654321
+ALLOWED_USER_IDS=
+WORKING_DIR=/home/user/projects
+AGENT_TYPE=kimi
+KIMI_COMMAND=kimi
+KIMI_AUTO_APPROVE_FLAG=--yolo
+KIMI_SESSIONS_DIR=~/.kimi-code/sessions
+KIMI_CONTEXT_WINDOW=1048576
+PROMPT_TIMEOUT=300
+RATE_LIMIT_SECONDS=10
+LOG_LEVEL=INFO
diff --git a/.gitignore b/.gitignore
new file mode 100644
index 0000000..ee414c5
--- /dev/null
+++ b/.gitignore
@@ -0,0 +1,12 @@
+.env
+__pycache__/
+*.py[cod]
+.venv/
+venv/
+.pytest_cache/
+.coverage
+htmlcov/
+.ruff_cache/
+*.egg-info/
+dist/
+build/
diff --git a/Makefile b/Makefile
new file mode 100644
index 0000000..894f78d
--- /dev/null
+++ b/Makefile
@@ -0,0 +1,16 @@
+.PHONY: install test coverage run lint
+
+install:
+	pip install -r requirements.txt
+
+test:
+	pytest
+
+coverage:
+	pytest --cov=src/application --cov=src/infrastructure --cov-report=term-missing --cov-fail-under=60
+
+run:
+	python -m src.interface.bot
+
+lint:
+	ruff check src tests
diff --git a/pytest.ini b/pytest.ini
new file mode 100644
index 0000000..8f32afa
--- /dev/null
+++ b/pytest.ini
@@ -0,0 +1,4 @@
+[pytest]
+asyncio_mode = auto
+testpaths = tests
+pythonpath = .
diff --git a/requirements.txt b/requirements.txt
new file mode 100644
index 0000000..f58ca64
--- /dev/null
+++ b/requirements.txt
@@ -0,0 +1,9 @@
+discord.py==2.6.4
+pydantic==2.11.5
+pydantic-settings==2.9.1
+python-dotenv==1.1.0
+structlog==25.3.0
+pytest==8.4.0
+pytest-asyncio==1.0.0
+pytest-cov==6.2.1
+ruff==0.12.0
diff --git a/src/__init__.py b/src/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/src/application/__init__.py b/src/application/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/src/domain/__init__.py b/src/domain/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/src/infrastructure/__init__.py b/src/infrastructure/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/src/infrastructure/agents/__init__.py b/src/infrastructure/agents/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/src/interface/__init__.py b/src/interface/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/tests/__init__.py b/tests/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/tests/application/__init__.py b/tests/application/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/tests/infrastructure/__init__.py b/tests/infrastructure/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/tests/interface/__init__.py b/tests/interface/__init__.py
new file mode 100644
index 0000000..e69de29
