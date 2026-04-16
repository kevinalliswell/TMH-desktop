# Contributing

## Branch Strategy

- `main`: production-ready code and release tags.
- `develop`: integration branch for ongoing work.
- `feature/*`: new features, branched from `develop`.
- `bugfix/*`: routine fixes, branched from `develop`.
- `hotfix/*`: urgent fixes, branched from `main`.
- `release/*`: release stabilization branches when a version needs hardening before tagging.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt ./packages/tmh_comm
pytest
```

On Windows, activate the virtual environment with `.venv\Scripts\activate`.

## Commit Convention

Use Conventional Commit prefixes where practical:

- `feat`: user-facing feature
- `fix`: bug fix
- `docs`: documentation only
- `refactor`: internal refactor without behavior change
- `test`: test-only change
- `chore`: tooling, CI, or maintenance

Examples:

- `feat(ui): add experiment summary export`
- `fix(device): prevent MFC reconnect loop on timeout`
- `chore(ci): add tag-driven release workflow`

## Pull Requests

1. Branch from the correct base branch.
2. Keep PRs focused and easy to review.
3. Run `pytest` before opening a PR.
4. Update docs when user-facing behavior, build flow, or release process changes.
5. Squash-merge by default to keep `main` and `develop` readable.

## Versioning And Tags

- The canonical app version lives in `configs/software.info`.
- Git tags must use the form `v<version>`, for example `v1.1.251121`.
- Update `CHANGELOG.md` before creating a release tag.
- Only tag commits that are already on `main`.
- Use `python scripts/release_manager.py verify` to check version consistency locally.

## Release Flow

1. Merge validated changes into `develop`.
2. Create `release/*` if stabilization is needed, otherwise open a PR from `develop` to `main`.
3. Run `python scripts/release_manager.py prepare --version <new-version> --date <yyyy-mm-dd>`.
4. Tag the `main` commit with `v<version>`.
5. Push the tag to trigger the GitHub Release workflow.

## Test Policy

- `pytest` is intentionally scoped to `tests/ci` for a stable automation baseline.
- Hardware, exploratory UI, and legacy scripts remain under `tests/` and should be run explicitly when relevant.
- Any change that touches serial communication, experiment persistence, or release packaging should include at least one automation-safe smoke test when possible.
