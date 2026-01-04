run:
	uv run python -m indexer_engine.app.interface.cli indexer run

migrate:
	uv run alembic revision --autogenerate -m "$(name)" --rev-id $(shell date '+%Y_%m_%d_%H%M%S')

upgrade:
	uv run alembic upgrade head

format:
	uv run ruff check --fix .

lint:
	uv run ruff check .

typecheck:
	uv run mypy .