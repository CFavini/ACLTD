# Architecture

ACLTD 2.0.0 is the current stable release. Its authenticated files reconstruct mission
state; neither a model nor a successful technical check supplies human approval.

## Components and trust

| Component | Responsibility |
| --- | --- |
| Ledger | Canonical append-only history with chained HMAC-SHA256 and SHA256 hashes |
| Anchor | MAC-authenticated seq/hash/byte offsets, atomically replaced after append |
| Checkpoint | MAC-authenticated state/ciphertext, reconciled against latest intent/commit |
| Lock | One persistent OS lock per ledger, held for complete storage transactions |
| Resume | Explicit trusted system and recovered user channels; all six envelopes equivalent |
| Legacy verifier | Read-only unkeyed integrity, explicit new-journal migration only |

Mandatory full verification runs on mission opening and every restore. Normal
own appends use authenticated anchor/head/tail and a process-local metadata
cache; external changes invalidate the cache. A lock serializes both writers and
readers. Advisory locks require cooperating processes and a filesystem supporting
these primitives; the core does not defend against a privileged process ignoring
locks, replacing active lock identities, or compromising the host/key provider.

## Contract for integration adapters

This is a contract only. No integration adapter, MCP, service, tenant or data-level
policy is implemented by ACLTD 2.0.

| Caller parameter/result | Contract |
| --- | --- |
| key | Nonempty bytes or a function returning bytes; mandatory; never persisted by core |
| on_head(seq, head_hash) | Called after durable local append + anchor, under lock; persist an external trusted head |
| expected_head | Exact (seq, head_hash) tuple/list or {seq, head_hash}; verify and restore refuse mismatch |
| approver | Mandatory nonempty single-line text for resume, migration and tail repair; supplied by caller authorization policy |
| encrypt(bytes)->bytes | Optional encryption hook for every payload and checkpoint state; output base64 ASCII |
| decrypt(bytes)->bytes | Required when consuming encrypted state/phase payloads |
| lock_timeout | Nonnegative finite seconds; defaults to 10 |
| LedgerBusy | Distinct retryable occupied exception from append, verify and restore; not evidence of corruption |

The adapter must authorize the responsible human; approver text alone is an
audit claim, not proof of identity. Each integrating environment supplies its own
responsible approver. Real secrets, tenant and person authority, paths, levels and
provider selection, MCP and coherent backups belong to the adapter and are outside
this implementation.

on_head failure occurs AFTER local persistence and raises an explicit error.
An unavailable external store does not undo the committed line. The caller must
stop, reconcile verified local/external heads, and obtain the proper recovery
decision rather than blindly retrying the same operation. Callback work is
synchronous and bounded by the caller; lock_timeout governs acquisition only.
An external database update and local append are not one distributed transaction.

Without expected_head, a complete authentic older ledger/anchor/checkpoint set
can be restored locally. With a trusted newer external head it is refused.
Neither external heads nor callbacks are automatically stored in the journal.

## Resume boundary

build_resume_text(state, token_budget, approver) returns a ResumeText and metadata.
Keep its explicit system/data attributes when calling to_provider_messages;
serialized plain strings are refused. System contains protocol/mission/pinned
facts/gaps. A separate user message labels summary/questions/turns as recovered
data, not instructions, inside delimiters and JSON quoting. Reserved ACLTD markers
are refused in all input strings; mission/facts/sources/gaps are single-line.
Human source validation remains necessary even for a valid MAC.

## Files, durability and migration

Checkpoint intent, replacement and commit run under one ledger lock. Only the
latest confirmed digest or newest pending intent may restore. Repair of a missing
commit is explicit in the result; repair=False reports it pending. A torn ledger
requires the separate approved repair_torn_tail call; complete lines never change.

Every atomic replacement fsyncs its parent directory on POSIX, plus an initial
ledger creation sync. Windows uses file fsync and os.replace; Python stdlib does
not expose an equivalent directory durability flush. Field tests on the target
hardware are summarized in docs/VALIDATION.md.

Legacy verify_legacy does not require a key and never writes. migrate_from_legacy
creates a distinct journal recording the old head/count and explicit approver;
it neither rewrites old files nor proves old history authentic. Legacy checkpoint
state must be reviewed and explicitly written under the new contract. There is
no implicit migration, adopt_anchor, automatic rollout or production promotion.
