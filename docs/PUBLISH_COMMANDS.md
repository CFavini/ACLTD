# Publish Commands

Run these commands from inside the repository folder.

## If You Are Using This Prepared Checkout

This workspace checkout already has:

- branch: `main`;
- remote: `https://github.com/CFavini/ACLTD.git`;
- tag: `v1.4.4-sanitized`;
- initial commit: `Initial public homologation release for ACLTD v1.4.4`.

Create the empty public GitHub repository, then push:

```bash
gh repo create CFavini/ACLTD \
  --public \
  --description "Deterministic, auditable, fail-closed continuity and recovery for long-running AI agent missions." \
  --homepage "https://cfavini.github.io/ACLTD/"

git push -u origin main
git push origin v1.4.4-sanitized
```

## If You Extracted the ZIP Somewhere Else

## Prepare Local Git

```bash
git init
git branch -M main
git add .
git commit -m "Initial public homologation release for ACLTD v1.4.4"
git tag -a v1.4.4-sanitized -m "ACLTD v1.4.4 homologation candidate"
```

## Create Public GitHub Repository

With GitHub CLI:

```bash
gh repo create CFavini/ACLTD \
  --public \
  --source=. \
  --remote=origin \
  --push \
  --description "Deterministic, auditable, fail-closed continuity and recovery for long-running AI agent missions." \
  --homepage "https://cfavini.github.io/ACLTD/"
```

Or create the repository in the GitHub web UI, then run:

```bash
git remote add origin https://github.com/CFavini/ACLTD.git
git push -u origin main
```

## Push First Release Tag

```bash
git push origin v1.4.4-sanitized
```

## After Push

1. Enable branch protection for `main`.
2. Enable Actions.
3. Enable Dependabot alerts.
4. Enable secret scanning and push protection.
5. Enable private vulnerability reporting.
6. Add repository topics from `docs/PUBLICATION_GUIDE.md`.
7. Enable GitHub Pages from `/docs`.

Do not invite external collaborators until `main` is protected.

## Releases

Releases are built by `.github/workflows/release.yml`. Pushing a `v*` tag runs
`quick_validate.py`, builds `acltd-public-repo-kit-<tag>.zip`,
`acltd_skill_<tag>.zip` and `SHA256SUMS.txt`, and attaches them to the GitHub
release (creating it if needed).

```bash
git tag -a vX.Y.Z -m "ACLTD vX.Y.Z"
git push origin vX.Y.Z
```

To rebuild the assets of an existing release, run the **Release** workflow from
the Actions tab with the tag name as input.
