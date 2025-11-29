# Makefile - developer shortcuts
.PHONY: up down build logs shell migrate createsuper collectstatic test

# Build and bring up containers in foreground (use if you want logs)
up:
	docker compose up --build

# Detached
upd:
	docker compose up --build -d

# Stop and remove containers and volumes
down:
	docker compose down -v

# Rebuild web service
build:
	docker compose build web

# Tail logs for web
logs:
	docker compose logs -f web

# Exec a shell into web container
shell:
	docker compose exec web bash

# Run Django migrations
migrate:
	docker compose exec web uv run python backend/manage.py migrate --noinput

# Create Django superuser interactively (or provide env vars)
createsuper:
	docker compose exec web uv run python backend/manage.py createsuperuser

# Collect static files
collectstatic:
	docker compose exec web uv run python backend/manage.py collectstatic --noinput

# Run test suite (if you have tests)
test:
	docker compose exec web uv run python -m pytest -q
