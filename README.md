# Gonaj Backend

> **A crowdsourced transit knowledge platform built for correctness, reversibility, and trust.**

Gonaj is a backend system that transforms messy, incomplete human observations about public transport into reliable transit knowledge over time. It's designed for regions where official data is missing, outdated, or inaccessible.

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Django 5.2](https://img.shields.io/badge/django-5.2-green.svg)](https://www.djangoproject.com/)
[![PostGIS](https://img.shields.io/badge/postgis-3.5-blue.svg)](https://postgis.net/)

## 🌟 Key Features

- **Append-Only Architecture**: User contributions are never overwritten or deleted
- **Evidence-Based Truth**: Canonical transit data is derived from observations, not directly edited
- **Time-Aware Confidence**: Information decays over time unless reinforced by new evidence
- **Full Auditability**: Every decision can be traced back to the evidence that supports it
- **Reversible Operations**: All system beliefs can be re-derived from historical data
- **GeoDjango Integration**: Full PostGIS support for spatial queries and operations

## 🏗️ Technology Stack

- **Framework**: Django 5.2 with Django REST Framework
- **Database**: PostgreSQL 17 + PostGIS 3.5
- **Package Manager**: [uv](https://github.com/astral-sh/uv) - Fast Python package installer
- **Authentication**: JWT + Django Allauth (OAuth2 support)
- **Server**: Gunicorn (production), Django dev server (development)
- **Containerization**: Docker + Docker Compose

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Docker** (20.10+) and **Docker Compose** (v2+)
- **Make** (optional, but recommended for shortcuts)
- **Git**

That's it! Docker handles Python, PostgreSQL, and all other dependencies.

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/gonaj/gonaj-backend.git
cd gonaj-backend
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and update the following critical values:

- `DJANGO_SECRET_KEY` - Generate with: `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`
- `JWT_SECRET_KEY` - Generate with: `python -c 'import secrets; print(secrets.token_urlsafe(50))'`
- Other OAuth and email settings as needed

### 3. Set Up User Permissions (Development)

```bash
make setup-user
```

This configures Docker to use your host user ID to avoid permission issues.

### 4. Start the Application

```bash
make up
```

This will:
- Build the Docker images
- Start PostgreSQL with PostGIS
- Run database migrations
- Start the Django development server at `http://localhost:8000`

### 5. Create a Superuser

In a new terminal:

```bash
make createsuper
```

Follow the prompts to create an admin account.

### 6. Access the Application

- **API**: http://localhost:8000/api/
- **Admin Panel**: http://localhost:8000/admin/
- **Database**: localhost:5432 (for tools like pgAdmin or QGIS)

## 🛠️ Development Workflow

### Common Commands

All commands use the `Makefile` for convenience:

```bash
# Start services (foreground with logs)
make up

# Start services (detached/background)
make upd

# Stop and remove all containers + volumes
make down

# View logs
make logs

# Open a shell in the web container
make shell

# Run migrations
make migrate

# Collect static files
make collectstatic

# Run tests
make test

# Rebuild the web service
make build
```

### Running Without Make

If you prefer not to use `make`:

```bash
# Start services
docker compose up --build

# Run migrations
docker compose exec web uv run python backend/manage.py migrate

# Create superuser
docker compose exec web uv run python backend/manage.py createsuperuser

# Open shell
docker compose exec web bash
```

### Manual Development (Without Docker)

If you want to run the backend directly on your host:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Set up PostgreSQL with PostGIS (on your host)
# Configure .env to point to your database

# Run migrations
uv run python backend/manage.py migrate

# Start development server
uv run python backend/manage.py runserver 0.0.0.0:8000
```

## 📁 Project Structure

```
gonaj-backend/
├── backend/              # Django project root
│   ├── accounts/         # User authentication and profiles
│   ├── api/              # API endpoints and serializers
│   ├── backend/          # Django settings and configuration
│   ├── core/             # Core models and shared utilities
│   ├── transit/          # Transit domain models and logic
│   └── manage.py         # Django management script
├── docs/                 # Comprehensive documentation
│   ├── 00_overview/      # Project vision and context
│   ├── 01_architecture/  # System architecture and invariants
│   ├── 02_phase_1/       # Current implementation phase
│   ├── 03_domain/        # Domain models and concepts
│   ├── 04_api/           # API documentation
│   └── 06_contributing/  # Contribution guidelines
├── .devcontainer/        # VS Code dev container configuration
├── docker-compose.yml    # Docker service definitions
├── Dockerfile            # Multi-stage production build
├── Makefile              # Developer shortcuts
├── pyproject.toml        # Python dependencies (uv format)
├── uv.lock               # Locked dependency versions
└── README.md             # This file
```

## 🧪 Testing

```bash
# Run all tests
make test

# Or directly with pytest
docker compose exec web uv run python -m pytest -v

# Run specific test file
docker compose exec web uv run python -m pytest backend/core/tests/test_models.py -v
```

## 📖 Documentation

This repository includes extensive documentation in the `docs/` folder:

- **[docs/README.md](docs/README.md)** - Start here for an overview
- **Architecture** - Core principles and system invariants
- **Phase-1 Documentation** - Current implementation scope and rules
- **API Documentation** - API principles and quick reference
- **Contributing Guide** - How to safely contribute to the project

### Key Architectural Principles

Before contributing, please understand these core invariants:

1. **Contributions are append-only** - User input is never overwritten or deleted
2. **Canonical data is derived** - Truth is computed from evidence, not edited directly
3. **All decisions are reversible** - Every system belief can be re-derived from history
4. **Confidence decays over time** - Information requires reinforcement to remain trusted
5. **Public APIs expose conclusions, not process** - Internal complexity stays internal

Read **[CONTRIBUTING.md](CONTRIBUTING.md)** for detailed guidelines.

## 🤝 Contributing

We welcome thoughtful contributions! However, this project has specific architectural constraints to ensure long-term correctness and auditability.

**Before contributing:**

1. Read [CONTRIBUTING.md](CONTRIBUTING.md) carefully
2. Review the [architectural invariants](docs/01_architecture/)
3. Understand the [Phase-1 scope](docs/02_phase_1/)
4. Open a discussion for significant changes

Contributions that violate core invariants will not be merged, regardless of their utility.

## 🔒 Security

- Never commit secrets or sensitive data to the repository
- Always use environment variables for configuration
- Report security vulnerabilities privately to the maintainers
- The system is designed with security-in-depth principles

## 📜 Philosophy

Gonaj is intentionally conservative and optimizes for:

- **Correctness over convenience**
- **Long-term trust over short-term speed**
- **Auditability over efficiency**
- **Reversibility over finality**

The system is designed to be **safe to be wrong** and to change its mind over time based on new evidence.

## 🗺️ Roadmap

This project follows a phase-based development model:

- **Phase 1** (Current): Core contribution model, basic transit entities, confidence decay
- **Phase 2** (Planned): Advanced evaluation rules, route synthesis, GTFS export
- **Phase 3** (Future): Real-time predictions, mobile apps, OSM integration

See [docs/02_phase_1/](docs/02_phase_1/) for current phase details.

## 📄 License

[License information to be added]

## 🙏 Acknowledgments

Built with:
- [Django](https://www.djangoproject.com/) - Web framework
- [PostGIS](https://postgis.net/) - Spatial database
- [uv](https://github.com/astral-sh/uv) - Fast Python package manager
- [Docker](https://www.docker.com/) - Containerization

---

**Questions?** Check the [documentation](docs/README.md) or open a discussion.

**Found a bug?** Please read [CONTRIBUTING.md](CONTRIBUTING.md) first, then open an issue.

## Licensing

This repository is licensed under GNU AGPL-3.0.
Documentation under /docs is licensed under CC BY 4.0.

See LICENSE and GOVERNANCE.md for details.

