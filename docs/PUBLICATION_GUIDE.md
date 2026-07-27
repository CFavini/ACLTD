# Publication and SEO Guide

This guide prepares ACLTD for public GitHub release and Google discoverability.

## Repository Name

Recommended:

```text
acltd
```

Alternative:

```text
agent-command-long-term-duration
```

## GitHub Description

Use this exact repository description:

```text
Deterministic, auditable, fail-closed continuity and recovery for long-running AI agent missions.
```

## Website / Homepage

After GitHub Pages is enabled, use:

```text
https://Cfavini.github.io/acltd/
```

## Topics

Add these GitHub topics:

```text
ai-agents
agent-memory
agent-continuity
mcp
model-context-protocol
long-running-agents
checkpointing
recovery
fail-closed
auditability
jsonl
hash-chain
hermes-agent
nous-research
```

## Branch Protection

Protect `main` before inviting contributors.

Recommended rules:

- Require pull request before merge.
- Require at least one approving review.
- Require status checks to pass.
- Require conversation resolution.
- Dismiss stale approvals after new commits.
- Restrict direct pushes.
- Prevent force pushes.
- Prevent branch deletion.
- Require CODEOWNERS review for sensitive paths.

## Public Release Checklist

1. Create a public GitHub repository.
2. Upload this repository kit.
3. Confirm badges, CODEOWNERS, and links point to `Cfavini/acltd`.
4. Enable GitHub Actions.
5. Protect `main`.
6. Enable Dependabot alerts.
7. Enable secret scanning and push protection.
8. Enable private vulnerability reporting.
9. Add topics.
10. Create the first release: `v1.4.3-homologation`.

See [Publish Commands](PUBLISH_COMMANDS.md) for a ready command sequence.

## Google SEO

Google uses page titles, visible headings, links, metadata, and structured data to understand pages. Keep titles concise, descriptive, and aligned with the visible `H1`.

Recommended GitHub Pages title:

```text
ACLTD - Fail-Closed Continuity for Long-Running AI Agents
```

Recommended meta description:

```text
ACLTD is deterministic, auditable recovery infrastructure for long-running AI agent missions, with append-only ledgers, checkpoints, hash chains, and human-gated restore.
```

Recommended first heading:

```text
ACLTD: Agent Command Long-Term Duration
```

Recommended opening sentence:

```text
ACLTD is a fail-closed continuity and recovery layer for long-running AI agents that must survive lost sessions, process failures, provider swaps, and incomplete handovers.
```

## Indexing Notes

- Public repositories can be indexed by Google, but indexing is not immediate.
- A GitHub Pages site usually gives better SEO control than a README alone.
- Keep the README and Pages title consistent.
- Avoid keyword stuffing.
- Link to the repository from Aitherion, Vantion, or relevant public project pages when appropriate.
- Publish release notes with the same core language.
