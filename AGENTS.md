# Repository Guidelines

## Project Structure & Modules
- `src/`: Core code. Entry point `src/app.py` (Typer CLI). Agents in `src/agents/` (macro, region, optimizer, risk, LLM adapters), utilities in `src/tools/`, scoring in `src/scoring/`, IO in `src/io/`, prompts in `src/prompts/`.
- `tests/`: Pytest unit tests (`tests/unit/test_*.py`).
- `data/`: Input CSVs (e.g., universes). Do not commit secrets.
- `artifacts/`: Generated outputs (JSON, PNG, MD).
- `doc/`: Specs and notes.

## Build, Test, and Dev Commands
- `make setup`: Create venv (Python 3.11 via uv) and install deps.
- `python -m src.app run ...`: Full weekly pipeline. Example: `python -m src.app run --date 2025-08-12 --regions JP,US --output ./artifacts`.
- `python -m src.app candidates ...`: Region candidates only.
- `python -m src.app report ...`: Build report from portfolio JSON.
- `make run-weekly|candidates|report`: Shortcuts for the above.
- `python -m pytest tests/`: Run tests. Add `--cov=src --cov-report=html` for coverage.

## Coding Style & Naming
- Python 3.11, PEP 8, 4-space indent; prefer type hints and docstrings.
- Names: `snake_case` for functions/vars, `PascalCase` for classes, modules as `snake_case.py`.
- Keep public CLI and agents stable; document breaking changes in README and tests.
- No formatter/linter is enforced; keep imports tidy and functions small.

## Testing Guidelines
- Framework: Pytest. Place tests under `tests/unit/` as `test_<module>.py`.
- Cover new logic with unit tests; target critical paths in `src/agents/*`, `src/tools/*`, and CLI in `src/app.py`.
- Use deterministic inputs (CSV/fixtures). Do not rely on live network in tests.
- Run: `python -m pytest tests/` before opening a PR.

## Commit & Pull Requests
- Conventional style is used in history: `feat: ...`, `fix(scope): ...`, `chore(data): ...`. English or Japanese OK.
- Commits: small, scoped, imperative mood. Reference issues when applicable.
- PRs: clear description, motivation, and scope; include commands used, outputs or screenshots (e.g., paths under `artifacts/`), and test results. Link issues and note any config/env needs.

## Security & Configuration
- Secrets via `.env` (e.g., `OPENAI_API_KEY`, `PPLX_API_KEY`). Do not commit `.env`.
- Prefer cached/sample data for tests; be mindful of API rate limits in runtime code.
