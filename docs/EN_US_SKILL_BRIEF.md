# ACLTD v1.4.3 English Brief

The audited `skill/acltd/SKILL.md` is preserved in its original language to protect audit traceability.

This English brief summarizes the current contract for public readers.

## Definition

ACLTD means Agent Command Long-Term Duration.

It is a continuity protocol for AI agents operating across long missions, interrupted sessions, reboots, provider changes, and incomplete handovers.

## Mission

ACLTD reconstructs the safe operational context from persistent records.

It does not allow the model to invent missing state.

## Core Guarantees

- append-only ledger;
- SHA-256 hash chain;
- mandatory anchor validation;
- atomic checkpoint write;
- pinned facts with auditable sources;
- explicit gap declaration;
- provider-neutral resume;
- human-gated completion and external action authority.

## Homologation Status

Version 1.4.3 is mature enough for optional pilot and incident recovery observation. It is not approved for automatic production installation.
