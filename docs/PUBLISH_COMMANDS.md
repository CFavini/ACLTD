# Publish Commands

Repository: `https://github.com/CFavini/ACLTD`. Current release: `v2.0.0`.

## Validate before any release

```bash
cd skill/acltd/scripts
python quick_validate.py
```

Every step must print `PASS`. If any file under `skill/acltd/` changed, regenerate
`MANIFEST_SHA256.txt` and `MANIFEST_SHA256.txt.sha256` first.

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

## Repository settings

1. Enable branch protection for `main`.
2. Enable Actions.
3. Enable Dependabot alerts.
4. Enable secret scanning and push protection.
5. Enable private vulnerability reporting.
6. Add repository topics from `docs/PUBLICATION_GUIDE.md`.
7. Enable GitHub Pages through the Pages workflow.

Do not invite external collaborators until `main` is protected.
