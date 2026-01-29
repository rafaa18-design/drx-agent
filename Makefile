# =============================================================================
# Asani AI Agent Template - Makefile
# =============================================================================

.PHONY: help install dev test lint format run docker-build docker-up docker-down \
        migrate migrate-up migrate-down migrate-new migrate-history migrate-current \
        agno-migrate clean

# Default target
help:
	@echo "Asani AI Agent Template - Available commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install production dependencies"
	@echo "  make dev            Install all dependencies (including dev)"
	@echo ""
	@echo "Development:"
	@echo "  make run            Run development server"
	@echo "  make test           Run tests"
	@echo "  make lint           Run linters (ruff, isort)"
	@echo "  make format         Format code (blue, isort)"
	@echo ""
	@echo "Database Migrations (Alembic):"
	@echo "  make migrate        Run all pending migrations"
	@echo "  make migrate-up     Alias for migrate"
	@echo "  make migrate-down   Rollback last migration"
	@echo "  make migrate-new    Create new migration (use: make migrate-new msg='description')"
	@echo "  make migrate-history Show migration history"
	@echo "  make migrate-current Show current migration version"
	@echo ""
	@echo "Agno Migrations:"
	@echo "  make agno-migrate   Run Agno schema migrations (sessions, memories, etc.)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   Build Docker image"
	@echo "  make docker-up      Start services with docker-compose"
	@echo "  make docker-down    Stop docker-compose services"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          Remove cache files and build artifacts"

# =============================================================================
# Setup
# =============================================================================

install:
	uv sync --no-dev

dev:
	uv sync

# =============================================================================
# Development
# =============================================================================

run:
	uv run uvicorn app.main:app --reload --port 8000

test:
	uv run pytest -v

lint:
	uv run ruff check app/ tests/
	uv run isort --check-only app/ tests/

format:
	uv run blue app/ tests/
	uv run isort app/ tests/

# =============================================================================
# Database Migrations (Alembic)
# =============================================================================

migrate:
	uv run alembic upgrade head

migrate-up: migrate

migrate-down:
	uv run alembic downgrade -1

migrate-new:
ifndef msg
	$(error msg is required. Usage: make migrate-new msg='your migration description')
endif
	uv run alembic revision -m "$(msg)"

migrate-history:
	uv run alembic history --verbose

migrate-current:
	uv run alembic current

# =============================================================================
# Agno Migrations (for Agno-managed tables: sessions, memories, knowledge, etc.)
# =============================================================================

agno-migrate:
	@uv run python -c "\
import asyncio; \
from agno.db.migrations.manager import MigrationManager; \
from agno.db.postgres import AsyncPostgresDb; \
from app.config import settings; \
async def run(): \
    db = AsyncPostgresDb(db_url=settings.POSTGRES_URL); \
    m = MigrationManager(db); \
    print(f'Migrating to version {m.latest_schema_version}...'); \
    await m.up(); \
    print('Agno migrations completed!'); \
    await db.close(); \
asyncio.run(run())"

# =============================================================================
# Docker
# =============================================================================

docker-build:
	docker build -t asani-agent-template .

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

# =============================================================================
# Cleanup
# =============================================================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf htmlcov/ 2>/dev/null || true
	rm -rf dist/ 2>/dev/null || true
	rm -rf build/ 2>/dev/null || true
	rm -rf *.egg-info/ 2>/dev/null || true
