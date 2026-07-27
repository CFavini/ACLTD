# Contributing to ACLTD

Thank you for helping improve ACLTD.

This project accepts contributions through the standard GitHub branch and pull request workflow. The `main` branch is protected and must remain stable.

## Contribution Types

We welcome:

- bug fixes;
- failing tests that reproduce continuity or recovery issues;
- documentation improvements;
- portability improvements for Windows, Linux, Git Bash, PowerShell, and CI;
- additional provider envelope tests;
- security hardening;
- MCP interface proposals that preserve human authorization and fail-closed behavior.

We are selective about:

- new runtime features;
- new state formats;
- provider-specific behavior;
- changes that increase operational authority;
- changes that weaken validation in exchange for convenience.

We do not accept:

- direct pushes to `main`;
- changes that bypass human authorization;
- state reconstruction from model guesses;
- silent recovery after corruption;
- network dependencies in core validation;
- production rollback, auto-installation, or auto-promotion behavior.

## Development Flow

1. Open an issue or discussion for significant changes.
2. Create a branch from `main`.
3. Keep the change focused.
4. Add or update tests.
5. Run validation locally.
6. Open a pull request.
7. Wait for CI and maintainer review.

## Local Validation

```bash
cd skill/acltd/scripts
python quick_validate.py
```

For deeper validation:

```bash
python acltd_selftest.py
python acltd_campaign.py
```

## Pull Request Requirements

Every pull request must include:

- what changed;
- why it changed;
- how it was tested;
- whether it affects ledger format, checkpoint format, provider envelopes, or authorization behavior;
- whether it changes any fail-closed condition.

## Design Requirements

ACLTD changes must preserve these invariants:

- disk is the source of truth;
- ledger is append-only;
- restore verifies before resuming;
- missing context is declared as a gap;
- pinned facts require sources;
- external actions require explicit human authorization;
- corrupted or ambiguous state fails closed.

## Maintainer Review

Maintainers may request revisions, split large changes, reject changes outside project scope, or defer proposals until a design issue is settled.

The goal is a stable recovery foundation, not rapid feature accumulation.
