# Changelog

## Unreleased - Repository Maintenance

Repository and CI changes only. The audited `skill/acltd` package is unchanged.

- Added `.gitattributes` forcing LF so the SHA256 manifest validates on Windows checkouts.
- Added a release workflow that validates the package and attaches the repo kit, skill ZIP and `SHA256SUMS.txt` to GitHub releases.
- Fixed the GitHub Pages hero image (served from `docs/assets/`) and the Pages asset copy step.
- Corrected repository, Pages and release tag references to `CFavini/ACLTD` and `v1.4.4-sanitized`.
- Updated GitHub Actions: checkout v7, setup-python v7, configure-pages v6, upload-pages-artifact v5, deploy-pages v5.

## 1.4.4 - Sanitized Homologation Candidate

- Passed technical smoke validation.
- Passed full self-test suite.
- Passed extended corruption, checkpoint, reboot, and append campaign.
- Added explicit Tencent and Nous provider envelope support.
- Preserved fail-closed behavior for malformed ledgers, delayed anchors, rollback, duplicate JSON keys, invalid constants, and non-canonical JSONL.
- Sanitized public package metadata and packaged validation reports.
- Normalized temporary test paths in generated result files.
- Cleaned legacy audit wording from packaged specification history.

## Earlier Versions

Earlier versions are retained as audit history only. They should not be used as current specification.
