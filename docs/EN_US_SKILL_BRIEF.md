# ACLTD v2.0.0 English Brief

The current contract lives in `skill/acltd/SKILL.md`; historical behavior is distinguished from the 2.0 specification.

This English brief summarizes the current contract for public readers.

## Definition

ACLTD means Agent Command Long-Term Duration.

It is a continuity protocol for AI agents operating across long missions, interrupted sessions, reboots, provider changes, and incomplete handovers.

## Mission

ACLTD reconstructs the safe operational context from persistent records.

It does not allow the model to invent missing state.

## Core Guarantees

- append-only ledger;
- chained SHA-256 hashes with keyed HMAC-SHA256 entries, anchors and checkpoints;
- mandatory anchor validation;
- atomic checkpoint write;
- pinned facts with auditable sources;
- explicit gap declaration;
- provider-neutral explicit system/user resume with required caller approver;
- OS ledger locks and incremental append after full opening verification;
- approved torn-tail repair and explicit read-only legacy migration;
- optional byte cipher hooks without external dependencies;
- human-gated completion and external action authority.

## Release Status

Version 2.0.0 is the current stable release. Accepted by the maintainer on 2026-11-25 after field tests on the target hardware: network loss, power loss and forced shutdown. Integration adapters, real keys, identity/data-level policy, MCP and operational backup remain outside the core.
