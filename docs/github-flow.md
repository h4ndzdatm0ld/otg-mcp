# GitHub Flow Branching Strategy

## Overview

OTG-MCP follows the GitHub Flow branching strategy - a lightweight, branch-based workflow that supports teams and projects where deployments are made regularly.

## Our Branching Strategy

We maintain a simple branching model:

1. **Main branch (`main`)**: 
   - Always deployable
   - Protected branch that requires pull request reviews
   - CI/CD automatically runs tests on all changes
   - Source of all deployments

2. **Feature branches**:
   - Created from `main`
   - Named descriptively (e.g., `feature/add-traffic-metrics`, `fix/connection-timeout`)
   - Used for new features, fixes, or any changes
   - Merged back to `main` via pull requests
   - Deleted after merge

## Workflow

```mermaid
graph TD
    A[main branch] -->|Create feature branch| B[feature/xyz]
    B -->|Make changes| C[Commit changes]
    C -->|Push and create PR| D[Pull Request]
    D -->|Review, CI/Tests| E{Approved?}
    E -->|Yes| F[Merge to main]
    F -->|Delete branch| A
    E -->|No| C
```

### Development Process

1. **Create a feature branch from `main`**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and commit**
   ```bash
   # Make changes
   git add .
   git commit -m "Descriptive commit message"
   ```

3. **Push changes and create a Pull Request**
   ```bash
   git push -u origin feature/your-feature-name
   # Create PR via GitHub interface
   ```

4. **Review Process**
   - CI automatically runs tests
   - Code review by teammates
   - Address feedback and make changes if needed

5. **Merge and Clean Up**
   - Merge the approved PR to `main`
   - Delete the feature branch
   - CI/CD deploys the changes automatically

## Release Process

We use GitHub Releases to create official releases, which trigger our CI workflow to publish packages to PyPI.

### Creating a Release

1. **Ensure `main` branch is ready for release**
   - All tests should be passing
   - Documentation should be up-to-date
   - Version number should be updated in relevant files (e.g., `pyproject.toml`)

2. **Create and push a tag**
   ```bash
   # Create a tag using semantic versioning (vX.Y.Z)
   git checkout main
   git pull origin main
   git tag -a v1.2.3 -m "Release v1.2.3"
   git push origin v1.2.3
   ```

3. **Create a GitHub Release**
   - Go to the GitHub repository
   - Navigate to "Releases" > "Create a new release"
   - Select the tag you just created
   - Add a title (e.g., "Release v1.2.3")
   - Write detailed release notes:
     - Major features and improvements
     - Bug fixes
     - Breaking changes (if any)
     - Migration instructions (if needed)
   - Click "Publish release"

4. **Automated Publication**
   - Our CI workflow automatically detects the new release
   - It builds the package for different platforms
   - It publishes the package to PyPI using trusted publishing
   - The workflow runs the `publish` job specifically when a release is published

### Release versioning

We follow semantic versioning (SemVer) for release tags:

- **Major version** (X.y.z): Incremented for incompatible API changes
- **Minor version** (x.Y.z): Incremented for added functionality in a backward-compatible manner
- **Patch version** (x.y.Z): Incremented for backward-compatible bug fixes

```mermaid
graph TD
    A[main branch] -->|Tag v1.0.0| B[Release v1.0.0]
    A -->|Continue development| C[Feature updates]
    C -->|Tag v1.1.0| D[Release v1.1.0]
    C -->|Bug fix| E[Patch]
    E -->|Tag v1.1.1| F[Release v1.1.1]
    C -->|Breaking change| G[Major update]
    G -->|Tag v2.0.0| H[Release v2.0.0]
```

### Pre-releases (optional)

For significant changes, consider using pre-release tags:

- Alpha releases: `v1.2.3-alpha.1`
- Beta releases: `v1.2.3-beta.1`
- Release candidates: `v1.2.3-rc.1`

```bash
git tag -a v1.2.3-rc.1 -m "Release candidate 1 for v1.2.3"
git push origin v1.2.3-rc.1
```

## Benefits of GitHub Flow

- **Simplicity**: Easy to understand and follow
- **Continuous Delivery**: Main branch is always deployable
- **Fast Feedback**: Quick review cycles and automated testing
- **Reduced Overhead**: No need to manage multiple long-lived branches
- **Focus on Features**: Each branch represents a discrete piece of work

## Additional Best Practices

- Keep feature branches short-lived (days, not weeks)
- Commit frequently with clear messages
- Pull from `main` regularly to reduce merge conflicts
- Write tests for new features before merging
- Document significant changes

GitHub Flow is particularly well-suited for our project as we focus on continuous integration, regular deployments, and maintaining a single production version.
