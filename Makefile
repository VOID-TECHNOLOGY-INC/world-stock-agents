PY ?= python3

.PHONY: setup
setup:
	@command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
	@. $$HOME/.cargo/env 2>/dev/null || true; uv venv -p 3.11
	@. .venv/bin/activate && uv pip install -r requirements.txt

.PHONY: run-weekly
run-weekly:
	@. .venv/bin/activate && $(PY) -m src.app run --date $${DATE:-2025-08-12} --regions $${REGIONS:-JP,US} --output ./artifacts
	@. .venv/bin/activate && $(PY) -m src.app buy-signal --date $${DATE:-2025-08-12} --regions $${REGIONS:-JP,US} --output ./artifacts --verbose

.PHONY: candidates
candidates:
	@. .venv/bin/activate && $(PY) -m src.app candidates --regions $${REGIONS:-JP,US} --date $${DATE:-2025-08-12} --output ./artifacts

.PHONY: report
report:
	@AS_OF=$${DATE:-2025-08-12}; FILE=./artifacts/portfolio_$${AS_OF//-/}.json; \
	. .venv/bin/activate && $(PY) -m src.app report --input $$FILE --output ./artifacts

.PHONY: buy-signal
buy-signal:
	@. .venv/bin/activate && $(PY) -m src.app buy-signal --date $${DATE:-2025-08-12} --regions $${REGIONS:-JP,US} --output ./artifacts --verbose


