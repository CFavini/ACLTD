# Security Policy

ACLTD 2.0.0 is the current stable release. Accepted by the maintainer on 2026-11-25 after field tests on the target hardware: network loss, power loss and forced shutdown.
Passing tests never grants any agent production or external-action authority.

## Supported versions

| Version | Status |
| --- | --- |
| 2.0.0 | Stable, supported |
| 1.x | Historical, read-only verification and explicit migration; no keyed authenticity |

## Authentication and confidentiality

Every 2.0 entry and anchor has HMAC-SHA256 using a caller-provided bytes key or
key callback. The checkpoint envelope is also MAC-authenticated. The core never
stores keys in the journal directory or supplies a default secret. Recomputing
unkeyed SHA256 cannot authenticate modified history. A compromised host/key can
still forge history; this package is not an identity or secret management system.

Optional encryption/decryption hooks store payload and checkpoint state in
base64 ASCII; HMAC covers ciphertext. The caller must supply secure authenticated
encryption and manage keys separately. The reversible fake in tests is NOT
SECURE and is never a runtime default. Without hooks, content stays plaintext.
Base64 alone does not encrypt. Cipher metadata (schema/kind/seq/time/size) remains
visible. Pass encrypt on EVERY encrypted write, including checkpoint phase repair.

## Freshness and concurrency

Authenticated files alone cannot detect a complete authentic old backup replay.
Use on_head and a trusted external expected_head for freshness. Callback failure
reports already-persisted local state; stop and reconcile, do not blindly replay.

OS locks protect cooperating readers/writers. Never remove/replace an active lock
file. A privileged writer ignoring locks, unsupported network filesystem locking,
host compromise and secret theft are outside the lock guarantee. First opening
and restore perform full verification; the incremental cache is only an append
optimization, not evidence for accepting recovered state.

## Recovery and prompts

No complete ledger line is rewritten. A torn final line refuses until approved
repair_torn_tail validates the complete prefix/anchor, removes only noncanonical
trailing bytes and appends removed size/hash/approver/reason. A canonical entry
missing only LF is preserved for manual investigation. A crash during repair can
still leave incomplete audit evidence and requires explicit investigation.

Old checkpoints mixed with a newer ledger are refused. Restore accepts the latest
confirmed digest or newest pending intent only. The backup unit is the coherent
ledger, anchor and checkpoint set, plus independently managed external head/key.

Recovered summary, questions and turns never enter the system channel. Reserved
ACLTD markers are refused case-insensitively; pinned facts and gaps are single
line. This reduces structural injection; it cannot prove LLM obedience or the
truth of human-supplied facts. external_action_allowed is always 0. An approver
string is an audit field, not identity verification or acceptance.

## Durability and exclusions

POSIX directory fsync follows every os.replace. Windows stdlib lacks equivalent
directory flush; file fsync and atomic replace do not prove power-loss durability.
Field tests on the target hardware covered network loss, power loss and forced
shutdown. Data levels, tenant/person/path authorization,
real key services, MCP and coordinated operational backups are integration adapter
responsibilities. The core does not authorize cloud providers for sensitive data.

## Report a vulnerability

Report privately with version, OS/Python, reproduction, expected/observed behavior
and impact. Do not include production secrets or customer recovery data. The
maintainer decides disclosure, acceptance and publication after review.
