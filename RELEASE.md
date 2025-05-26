# OTG-MCP Release Process

This document outlines the process for releasing new versions of the OTG-MCP package.

## Version Management

### Current Versioning Strategy

The project uses [Semantic Versioning](https://semver.org/) with pre-release tags:
- **Format**: `MAJOR.MINOR.PATCH[pre-release]`
- **Pre-release tags**: `a0` (alpha), `b0` (beta), `rc0` (release candidate)

### Version Locations

**Single Source of Truth**: All version information is managed in `pyproject.toml`
```toml
[project]
version = "0.1.3a0"  # Current version
```

> **Note**: The legacy `setup.py` file has been removed to eliminate version conflicts and follow modern Python packaging standards.

## Release Types

### 1. Alpha Release (Pre-release)
Used for early testing and development features.

**Example**: `0.1.2a0` → `0.1.3a0` (patch alpha) or `0.2.0a0` (minor alpha)

### 2. Beta Release (Pre-release)
Used for feature-complete versions that need broader testing.

**Example**: `0.1.3a0` → `0.1.3b0`

### 3. Release Candidate (Pre-release)
Used for versions ready for release, pending final validation.

**Example**: `0.1.3b0` → `0.1.3rc0`

### 4. Stable Release
Production-ready version.

**Example**: `0.1.3rc0` → `0.1.3`

## Version Bumping Process

### Step 1: Update Version in pyproject.toml

Edit the version field in `pyproject.toml`:

```toml
[project]
version = "NEW_VERSION_HERE"
```

### Step 2: Commit and Tag

```bash
# Commit the version change
git add pyproject.toml
git commit -m "Bump version to NEW_VERSION"

# Create and push tag
git tag vNEW_VERSION
git push origin main --tags
```

### Step 3: Automated Publishing

The CI/CD pipeline automatically handles publishing when a release is created:

1. **Tests Run**: All tests must pass on Python 3.11 and 3.12
2. **Package Build**: Automatically builds wheel and source distributions
3. **PyPI Publishing**: Publishes to PyPI using trusted publishing (OIDC)

## Creating a GitHub Release

### Manual Release Creation

1. Go to [GitHub Releases](https://github.com/h4ndzdatm0ld/otg-mcp/releases)
2. Click "Draft a new release"
3. Choose the tag you created (`vNEW_VERSION`)
4. Set release title (e.g., "OTG-MCP v0.1.3a0")
5. Add release notes (see template below)
6. Check "Set as a pre-release" for alpha/beta/rc versions
7. Click "Publish release"

### Release Notes Template

```markdown
## What's Changed

### New Features
- Feature 1 description
- Feature 2 description

### Bug Fixes
- Bug fix 1 description
- Bug fix 2 description

### Improvements
- Improvement 1 description
- Improvement 2 description

### Breaking Changes
- Breaking change description (if any)

### Dependencies
- Updated dependency X to version Y
- Added new dependency Z

**Full Changelog**: https://github.com/h4ndzdatm0ld/otg-mcp/compare/vPREVIOUS_VERSION...vNEW_VERSION
```

## Pre-Release Checklist

Before bumping any version:

- [ ] All tests pass locally (`pytest`)
- [ ] Code quality checks pass (`ruff check`, `mypy`)
- [ ] Documentation is updated
- [ ] CHANGELOG.md is updated (if exists)
- [ ] Version number follows semantic versioning rules
- [ ] Breaking changes are documented

## Post-Release Checklist

After publishing a release:

- [ ] Verify package is available on [PyPI](https://pypi.org/project/otg-mcp/)
- [ ] Test installation from PyPI: `pip install otg-mcp==NEW_VERSION`
- [ ] Update any dependent projects or documentation
- [ ] Announce release in relevant channels

## Common Version Bump Examples

### Patch Alpha Release (Bug fixes, small changes)
```bash
# Current: 0.1.2a0 → New: 0.1.3a0
# Edit pyproject.toml version field
git add pyproject.toml
git commit -m "Bump version to 0.1.3a0"
git tag v0.1.3a0
git push origin main --tags
```

### Minor Alpha Release (New features)
```bash
# Current: 0.1.3a0 → New: 0.2.0a0
# Edit pyproject.toml version field
git add pyproject.toml
git commit -m "Bump version to 0.2.0a0"
git tag v0.2.0a0
git push origin main --tags
```

### Alpha to Beta
```bash
# Current: 0.2.0a0 → New: 0.2.0b0
# Edit pyproject.toml version field
git add pyproject.toml
git commit -m "Bump version to 0.2.0b0"
git tag v0.2.0b0
git push origin main --tags
```

### Beta to Stable
```bash
# Current: 0.2.0b0 → New: 0.2.0
# Edit pyproject.toml version field
git add pyproject.toml
git commit -m "Release version 0.2.0"
git tag v0.2.0
git push origin main --tags
```

## Automated CI/CD Pipeline

The project uses GitHub Actions for automated testing and publishing:

### CI Pipeline (`.github/workflows/ci.yml`)
- **Triggers**: Push, Pull Request, Release
- **Tests**: Python 3.11 and 3.12 on Ubuntu and macOS
- **Quality**: Linting (ruff), Type checking (mypy)
- **Coverage**: Test coverage reporting
- **Build**: Package building and artifact upload

### Publishing Pipeline
- **Trigger**: GitHub Release creation
- **Authentication**: Trusted publishing with OIDC (no API tokens needed)
- **Target**: PyPI (https://pypi.org/project/otg-mcp/)

## Troubleshooting

### Version Conflicts
If you encounter version conflicts, ensure:
- Only `pyproject.toml` contains version information
- No leftover `setup.py` or `__version__.py` files exist
- Version follows semantic versioning format

### Publishing Failures
If PyPI publishing fails:
- Check that the version doesn't already exist on PyPI
- Verify GitHub Actions has proper OIDC configuration
- Ensure all tests pass before release

### Build Failures
If package building fails:
- Verify `pyproject.toml` syntax is correct
- Check that all dependencies are properly specified
- Ensure `src/otg_mcp/` structure is correct

## Additional Resources

- [Semantic Versioning](https://semver.org/)
- [Python Packaging Guide](https://packaging.python.org/)
- [PyPA Build](https://build.pypa.io/)
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github)
