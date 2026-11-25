# Changelog

## 2.0.0 - Stable (2026-11-25)

- Accepted by the maintainer on 2026-11-25 after field tests on the target hardware: network loss, power loss and forced shutdown.

- V1: schema acltd-2.0, required caller key, HMAC-SHA256 entries/anchor/checkpoint,
  on_head and expected_head; read-only verify_legacy and approved explicit migration.
- V2: separate system protocol/facts/gaps from delimited recovered user data;
  case-insensitive reserved-marker rejection and single-line pinned facts/gaps.
- V6: required approver parameter and generic requires_approval/approver envelopes;
  no approver name is fixed in runtime code.
- C1: explicit approved repair_torn_tail removes only noncanonical incomplete tail
  bytes, preserving complete lines and recording removed size/SHA256 and approval.
- C2: only latest confirmed checkpoint or newest pending intent may restore.
- C3: stdlib Windows/POSIX exclusive ledger lock, whole checkpoint transaction,
  configurable timeout and distinct LedgerBusy.
- C4: authenticated incremental anchor/head/tail append, full verification on
  first opening, metadata change and restore; comparative 1.4.4/2.0 benchmarks.
- C5: POSIX directory fsync after every atomic replace; Windows limit documented.
- V5: optional byte encryption/decryption hooks; base64 payload/state ciphertext,
  MAC over ciphertext; no cryptographic dependencies or real key provisioning.
- C6: coherent-set restore maintained; mixed backup pieces refused.
- V3/V4, real keys, integration adapters, MCP and operational backups remain outside core.
- Retained original tests with explicit 2.0 API/fixture updates; added cross-version
  T47 onward, adapted acceptance attacks, refreshed campaigns and SHA256 manifest.
- Fixed LF packaging via .gitattributes; manifest sidecar is now verified too.
- Repository maintenance: GitHub Actions updated (checkout 7, setup-python 7,
  configure-pages 6, upload-pages-artifact 5, deploy-pages 5), Pages asset path
  fixed and tag-driven release workflow added.
- Validation summary moved to docs/VALIDATION.md.

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
