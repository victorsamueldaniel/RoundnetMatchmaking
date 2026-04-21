# Contributing

## Prerequisites
- Python 3.10+
- pip

## Local Setup
1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies:
   ```bash
   python -m pip install -e ".[dev,ui]"
   ```

## Development Workflow
1. Create a branch from `main`.
2. Make focused changes.
3. Run quality checks locally:
   ```bash
   pytest -q
   black --check .
   flake8 .
   ```
4. Open a pull request with a clear summary and test evidence.

## Pull Request Expectations
- Keep scope focused and reviewable.
- Update documentation when behavior changes.
- Avoid committing generated artifacts (build output, runtime sessions, caches).

## Commit Guidance
- Use imperative commit messages.
- Reference related issue numbers when relevant.
