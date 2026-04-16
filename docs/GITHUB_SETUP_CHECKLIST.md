# GitHub Setup Checklist

This repository now includes versioned GitHub automation and collaboration files. The following repository settings still need to be enabled in GitHub UI because they are not fully stored in git.

## Recommended Repository Settings

- Set the default branch to `main`.
- Enable automatic deletion of head branches after merge.
- Prefer squash merge for routine pull requests.
- Keep the repository private unless distribution requirements change.

## Branch Protection

### `main`

- Require a pull request before merging.
- Require at least 1 approval.
- Dismiss stale approvals when new commits are pushed.
- Require status checks before merging.
- Add `ci` as a required status check.
- Block force pushes.
- Block branch deletion.

### `develop`

- Require a pull request before merging.
- Require status checks before merging.
- Add `ci` as a required status check.

## Labels

Recommended working labels:

- `type: bug`
- `type: feature`
- `type: docs`
- `type: ci`
- `type: refactor`
- `dependencies`
- `skip-changelog`

## Release Discipline

- Update `configs/software.info` first.
- Update `CHANGELOG.md`.
- Merge to `main`.
- Create and push `v<version>` tag.
- Let GitHub Actions build and publish the Release.

