**Project:** gonaj-backend (Django + PostGIS + uv)  
**Date:** December 2025  
**Package Manager:** uv (modern Python package manager)

---

## MANDATORY: Always Use Latest Stable Versions

When adding ANY new dependency or library to this project, you MUST:

### 1. Search for Latest Stable Version

**DO NOT rely on your training data cutoff date.** Always use web search to find the current latest stable version.

**Required steps:**
1. Search PyPI or official documentation for the package
2. Identify the latest **stable** release (not alpha, beta, or rc)
3. Verify the version is compatible with our Python version (3.14+)
4. Use the EXACT version number in `pyproject.toml`

### 2. How to Find Latest Versions

Use one of these methods:

**Method A: PyPI Official Page**
```
Search: "[package-name] pypi latest version"
URL: https://pypi.org/project/[package-name]/
Look for: Latest release version number
```

**Method B: Command Line (if available)**
```bash
uv pip index versions [package-name]
# Or
pip index versions [package-name]
```

**Method C: Official Documentation**
```
Search: "[package-name] latest stable version [current-year]"
Check: Official GitHub releases or documentation
```

### 3. Version Specification Format

**ALWAYS pin exact versions in `pyproject.toml`:**

✅ **CORRECT:**
```toml
dependencies = [
    "django==5.1.4",                    # Exact version
    "djangorestframework==3.15.2",      # Exact version
    "celery==5.4.0",                    # Exact version
]
```

❌ **INCORRECT:**
```toml
dependencies = [
    "django",                           # No version (unpredictable)
    "djangorestframework>=3.14",        # Range (not reproducible)
    "celery~=5.3",                      # Approximate (can drift)
]
```

### 4. Verification Required

Before adding a dependency, verify:

- [ ] Latest stable version number confirmed via web search
- [ ] Version is compatible with Python 3.14+
- [ ] Version is compatible with other project dependencies
- [ ] Version uses `==` exact pin in `pyproject.toml`
- [ ] Run `uv lock` after changes to update `uv.lock`

---

## Current Project Dependencies (as of Dec 2025)

**Core Framework:**
- Django: Check latest 5.x stable
- Django REST Framework: Check latest 3.x stable

**Database:**
- psycopg2-binary: Check latest 2.x stable
- PostGIS: (Docker image) Check latest compatible with PostgreSQL

**Web Server:**
- gunicorn: Check latest stable

**Python Version:**
- Requires: Python >=3.14

---

## Workflow for Adding New Dependencies

### Step 1: Research Latest Version
```bash
# Example: Adding celery
# 1. Search: "celery pypi latest version december 2025"
# 2. Find: https://pypi.org/project/celery/
# 3. Identify: Latest stable is 5.4.0 (example)
```

### Step 2: Add to pyproject.toml
```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "celery==5.4.0",  # ← Exact version from PyPI
]
```

### Step 3: Update Lock File
```bash
uv lock           # Updates uv.lock with exact resolved versions
uv sync           # Installs dependencies
```

### Step 4: Verify Installation
```bash
uv run python -c "import celery; print(celery.__version__)"
# Should output: 5.4.0
```

### Step 5: Rebuild Docker (if needed)
```bash
make down
make up
```

---

## Special Cases

### Django Extensions
- **Django packages:** Always check compatibility with current Django version
- **Example:** django-cors-headers, django-environ, django-filter
- **Search:** "[package-name] django 5.x compatibility"

### Database Drivers
- **psycopg2-binary vs psycopg:** Use binary for development, psycopg3 for production
- **Current:** psycopg2-binary==2.9.x (check latest patch version)

### GIS/Spatial Libraries
- **GDAL:** Version must match system GDAL in Docker image
- **Check:** Current Debian Bookworm GDAL version
- **Note:** Don't add Python GDAL binding unless necessary

### Development Tools
- **Testing:** pytest, pytest-django (latest stable)
- **Linting:** ruff, black (latest stable)
- **Type checking:** mypy (latest stable)

---

## Version Update Policy

### When to Update Versions

1. **Security patches:** Immediately update and rebuild
2. **Bug fixes:** Update during next development cycle
3. **Minor versions:** Review changelog, update if beneficial
4. **Major versions:** Plan migration, test thoroughly

### How to Update

```bash
# 1. Research new version (web search)
# 2. Update pyproject.toml with exact new version
# 3. Update lock file
uv lock

# 4. Test locally
uv sync
make down
make up

# 5. Run tests (when implemented)
uv run python backend/manage.py test

# 6. Commit changes
git add pyproject.toml uv.lock
git commit -m "Update [package] to [version]"
```

---

## Common Packages Reference

### Web Framework
- **Django:** https://pypi.org/project/Django/
- **DRF:** https://pypi.org/project/djangorestframework/

### Database
- **psycopg2:** https://pypi.org/project/psycopg2-binary/
- **psycopg3:** https://pypi.org/project/psycopg/

### Web Server
- **gunicorn:** https://pypi.org/project/gunicorn/
- **uvicorn:** https://pypi.org/project/uvicorn/ (if needed for async)

### Task Queue
- **celery:** https://pypi.org/project/celery/
- **redis:** https://pypi.org/project/redis/

### Testing
- **pytest:** https://pypi.org/project/pytest/
- **pytest-django:** https://pypi.org/project/pytest-django/

### Code Quality
- **ruff:** https://pypi.org/project/ruff/
- **black:** https://pypi.org/project/black/
- **mypy:** https://pypi.org/project/mypy/

---

## Docker Image Versions

When updating Docker base images, also search for latest:

```yaml
# docker-compose.yml
services:
  db:
    image: postgis/postgis:17-3.5  # Check Docker Hub for latest
```

**Check:** https://hub.docker.com/r/postgis/postgis/tags

---

## Error Handling

### If Version Not Found
```
Error: Package 'django==5.2.10' not found
```

**Resolution:**
1. Search PyPI for actual available versions
2. Find latest stable in the correct major version
3. Update pyproject.toml with correct version
4. Run `uv lock` and `uv sync`

### If Dependency Conflict
```
Error: Incompatible dependencies
```

**Resolution:**
1. Check compatibility matrix on package documentation
2. Adjust version constraints if needed
3. May need to update multiple packages together
4. Test thoroughly after resolution

---

## Examples

### ✅ Good Practice ( only for reference not to copy as it is)
```toml
# User requests: "Add celery for background tasks"

# Agent actions:
# 1. Search: "celery pypi latest stable december 2025"
# 2. Find: Latest is 5.4.0
# 3. Add to pyproject.toml:

dependencies = [
    "django==5.1.4",
    "celery==5.4.0",      # ← Exact latest stable from PyPI
    "redis==5.2.0",       # ← Celery dependency, also pinned
]

# 4. Run: uv lock && uv sync
# 5. Document: Added Celery 5.4.0 for background task processing
```

### ❌ Bad Practice
```toml
# Agent assumes version from training data:

dependencies = [
    "django==5.1.4",
    "celery==5.2.7",      # ← OLD version from training data
]

# Problem: Version 5.4.0 is available but not used
# Result: Missing security patches and features
```

---

## Summary Checklist

When adding ANY dependency, ensure:

- [ ] Web search performed for latest version
- [ ] Exact version number (using `==`) in pyproject.toml
- [ ] `uv lock` executed to update lock file
- [ ] `uv sync` executed to install
- [ ] Docker rebuilt if needed (`make down && make up`)
- [ ] Version number and reasoning documented in commit message

---

## Contact & Updates

- **Maintainer:** Project team
- **Last Updated:** December 2025
- **Review Frequency:** Update this document when package management policies change

---

**REMEMBER:** Reproducibility is critical. Always pin exact versions. Always search for latest stable releases. Never guess or use outdated versions from training data.