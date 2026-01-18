# GitHub Setup Guide

Checklist voor het opzetten van de notion-sync-lib repository op GitHub.

## Repository Settings

### About Section

**Description:**
```
Sync Notion pages like Git commits. Smart content-based diffing, automatic rate limiting, zero headaches.
```

**Website:**
```
https://github.com/mvletter/notion-sync-lib#readme
```

**Topics (tags):**
```
notion
notion-api
python
sync
diff
content-sync
translation
automation
rate-limiting
notion-client
```

### Repository Settings → General

- ✅ **Issues**: Enabled
- ✅ **Projects**: Disabled (unless you want project management)
- ✅ **Wiki**: Disabled (we have docs/ folder)
- ✅ **Discussions**: Optional (enable if you want Q&A forum)

### Repository Settings → Features

- ✅ **Require linear history**: Enabled (clean git history)
- ✅ **Allow squash merging**: Enabled
- ✅ **Allow merge commits**: Disabled (prefer squash)
- ✅ **Allow rebase merging**: Enabled
- ✅ **Automatically delete head branches**: Enabled

### Branch Protection (for `main` branch)

Settings → Branches → Add branch protection rule:

- **Branch name pattern**: `main`
- ✅ **Require pull request before merging**
  - Required approvals: 1 (of jij alleen, dan 0)
- ✅ **Require status checks to pass before merging**
  - Status checks: (als je CI hebt)
- ✅ **Require linear history**
- ✅ **Include administrators** (niemand kan protection bypassen)

---

## GitHub Actions (Optional CI/CD)

### Test Workflow

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"

    - name: Run unit tests
      run: |
        pytest tests/test_columns.py tests/test_width_ratio.py -v

    - name: Run linter
      run: |
        ruff check src/ tests/

    - name: Run type checker
      run: |
        mypy src/notion_sync
```

**Note:** Integration tests (`test_live_*.py`) require `NOTION_API_TOKEN` and kunnen niet in public CI draaien.

---

## Issue Templates

Create `.github/ISSUE_TEMPLATE/bug_report.md`:

```markdown
---
name: Bug Report
about: Report a bug or issue
title: '[BUG] '
labels: bug
---

## Describe the bug
A clear description of what the bug is.

## To Reproduce
Steps to reproduce the behavior:
1. Use function '...'
2. With parameters '...'
3. See error

## Expected behavior
What you expected to happen.

## Code Example
```python
# Minimal reproducible example
from notion_sync import ...
```

## Environment
- Python version: [e.g. 3.11]
- notion-sync-lib version: [e.g. 0.3.0]
- OS: [e.g. Ubuntu 22.04]

## Additional context
Any other context about the problem.
```

Create `.github/ISSUE_TEMPLATE/feature_request.md`:

```markdown
---
name: Feature Request
about: Suggest a new feature
title: '[FEATURE] '
labels: enhancement
---

## Feature Description
A clear description of the feature you'd like.

## Use Case
Why is this feature useful? What problem does it solve?

## Proposed Solution
How would you implement this? (optional)

## Alternatives Considered
What other solutions have you thought about?

## Additional Context
Any other context, examples, or screenshots.
```

---

## Pull Request Template

Create `.github/pull_request_template.md`:

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Checklist
- [ ] Tests added/updated (if applicable)
- [ ] Documentation updated (if applicable)
- [ ] Code passes linting (`ruff check`)
- [ ] Code passes type checking (`mypy`)
- [ ] All tests pass locally

## Related Issues
Fixes #(issue number)
```

---

## Release Strategy

### Versioning

We use **Semantic Versioning**: `MAJOR.MINOR.PATCH`

- **MAJOR** (1.0.0): Breaking API changes
- **MINOR** (0.4.0): New features, backwards compatible
- **PATCH** (0.3.1): Bug fixes, backwards compatible

### Creating a Release

1. **Update version** in `pyproject.toml`:
   ```toml
   version = "0.4.0"
   ```

2. **Create git tag**:
   ```bash
   git tag -a v0.4.0 -m "Release v0.4.0: Add XYZ feature"
   git push origin v0.4.0
   ```

3. **Create GitHub Release**:
   - Go to: Releases → Draft a new release
   - Choose tag: `v0.4.0`
   - Release title: `v0.4.0 - Feature Description`
   - Description (example):

   ```markdown
   ## What's New

   - ✨ Added `unwrap_column_list` function for flattening columns
   - 🐛 Fixed error handling in column creation
   - 📚 Improved documentation with usage examples

   ## Breaking Changes

   None

   ## Installation

   ```bash
   pip install git+https://github.com/mvletter/notion-sync-lib.git@v0.4.0
   ```

   ## Full Changelog

   https://github.com/mvletter/notion-sync-lib/compare/v1.0.0...v0.4.0
   ```

---

## Social Media / Repo Card

GitHub genereert automatisch een social media preview card. Check deze:
- Settings → Options → Social preview
- Should laten zien: Title + Description + Topics

Als de preview goed is, ziet het er zo uit wanneer mensen de repo delen:
```
notion-sync-lib
Sync Notion pages like Git commits. Smart content-based diffing, automatic rate limiting, zero headaches.
⭐ Python · Notion · Sync · Diff
```

---

## README Badges (Optional Extra's)

Je kunt meer badges toevoegen aan de README:

```markdown
![GitHub stars](https://img.shields.io/github/stars/mvletter/notion-sync-lib?style=social)
![GitHub issues](https://img.shields.io/github/issues/mvletter/notion-sync-lib)
![GitHub pull requests](https://img.shields.io/github/issues-pr/mvletter/notion-sync-lib)
![GitHub last commit](https://img.shields.io/github/last-commit/mvletter/notion-sync-lib)
```

Maar houd het minimaal - te veel badges is afleidend.

---

## Announcement Checklist

Na het pushen naar GitHub:

- [ ] Check README renders correctly op GitHub
- [ ] Check alle docs/ links werken
- [ ] Test installatie: `pip install git+https://github.com/mvletter/notion-sync-lib.git`
- [ ] Create v1.0.0 release met current state
- [ ] Update repo description en topics
- [ ] (Optional) Post op relevant Reddit (r/notion, r/Python)
- [ ] (Optional) Post op Twitter/LinkedIn
- [ ] (Optional) Submit to awesome-notion list

---

## Future: PyPI Publishing

Wanneer je klaar bent voor PyPI (Python Package Index):

1. **Create PyPI account**: https://pypi.org/account/register/

2. **Build package**:
   ```bash
   python -m build
   ```

3. **Upload to TestPyPI** (eerst testen):
   ```bash
   python -m twine upload --repository testpypi dist/*
   ```

4. **Test install from TestPyPI**:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ notion-sync-lib
   ```

5. **Upload to PyPI** (production):
   ```bash
   python -m twine upload dist/*
   ```

6. **Update installation instructions** in README:
   ```bash
   pip install notion-sync-lib
   ```

---

## Maintenance

### Regular Tasks

**Weekly:**
- Check open issues
- Review pull requests

**Monthly:**
- Update dependencies (notion-client, python-dotenv)
- Run full test suite
- Check for security vulnerabilities: `pip-audit`

**Per Release:**
- Update version in pyproject.toml
- Create git tag
- Create GitHub release with changelog
- Test installation

---

## License Check

Zorg dat je een `LICENSE` file hebt in de root:

```
MIT License

Copyright (c) 2025 Mark Vletter

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

[... rest of MIT license ...]
```

---

## Summary Checklist

Voor eerste publieke release:

- [x] README is wervend en duidelijk
- [x] Alle documentatie is compleet (usage-guide, api-reference, development)
- [x] pyproject.toml heeft goede description en keywords
- [ ] LICENSE file bestaat
- [ ] Repository description en topics zijn ingesteld op GitHub
- [ ] Branch protection is ingesteld
- [ ] Issue templates zijn aangemaakt
- [ ] PR template is aangemaakt
- [ ] v1.0.0 release is gemaakt
- [ ] Installatie is getest: `pip install git+https://github.com/...`

**Je bent klaar voor launch! 🚀**
