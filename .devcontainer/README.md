# VS Code Dev Container Setup

This project includes a VS Code Dev Container configuration for consistent development environment.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop)
- [Visual Studio Code](https://code.visualstudio.com/)
- [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

## Getting Started

1. **Open in Container**
   - Open this project folder in VS Code
   - When prompted, click "Reopen in Container" or use Command Palette (F1) and select "Dev Containers: Reopen in Container"
   - Wait for the container to build and start

2. **What's Included**
   - Python 3.14 with uv package manager
   - PostgreSQL 15 with PostGIS 3.4
   - Django development server auto-starts on port 8000
   - Pre-configured Python extensions (Pylance, Black, Ruff)
   - Django-specific VS Code tasks and debugging configurations

3. **Available Ports**
   - `8000` - Django development server
   - `5432` - PostgreSQL database

## VS Code Tasks

Access via Terminal → Run Task or `Ctrl+Shift+B`:

- **Run Django Server** - Start the development server
- **Make Migrations** - Create new migrations
- **Run Migrations** - Apply migrations to database
- **Create Superuser** - Create Django admin user
- **Collect Static Files** - Collect static assets
- **Django Shell** - Open Django interactive shell
- **Run Tests** - Execute test suite
- **Check Django** - Run Django system checks

## Debugging

Use the Run and Debug panel (Ctrl+Shift+D):

- **Django: Run Server** - Debug the development server
- **Django: Run Tests** - Debug tests
- **Django: Shell** - Debug in Django shell

## Manual Commands

If you need to run commands manually:

```bash
# Django commands
cd backend
uv run python manage.py <command>

# Install new packages
uv add <package-name>
uv sync

# Database access
psql -h db -U gonajuser -d gonaj
```

## Environment Variables

Configured in `.env` file (loaded automatically):
- `POSTGRES_DB` - Database name
- `POSTGRES_USER` - Database user
- `POSTGRES_PASSWORD` - Database password
- `DJANGO_SECRET_KEY` - Django secret key
- `DJANGO_DEBUG` - Debug mode flag

## Troubleshooting

### Container won't start
- Ensure Docker Desktop is running
- Check if ports 8000 and 5432 are available
- Try rebuilding: Command Palette → "Dev Containers: Rebuild Container"

### Python interpreter not found
- The interpreter should be auto-detected at `/app/.venv/bin/python`
- If not, manually select it via Command Palette → "Python: Select Interpreter"

### Database connection issues
- Database starts in the background automatically
- Connection details: `host=db, port=5432, user=gonajuser, password=gonajpass, database=gonaj`

## File Permissions

The dev container runs as root to avoid permission issues with Docker-created files. If you need to change ownership of files on the host:

```bash
sudo chown -R $USER:$USER .
```
