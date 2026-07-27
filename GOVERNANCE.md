# Governance

ACLTD uses a maintainer-led open-source governance model.

The project is open to contributions, but the recovery contract is intentionally conservative. Maintainers are responsible for protecting the core invariants, release quality, and security posture.

## Roles

| Role | Responsibility |
| --- | --- |
| Project Lead | Final decision authority for roadmap, releases, and recovery contract changes |
| Maintainer | Reviews pull requests, manages releases, protects branch quality |
| Contributor | Proposes changes through issues, branches, forks, and pull requests |
| Security Reporter | Reports vulnerabilities privately through the security process |

## Decision Process

Routine fixes may be accepted through pull request review.

Substantial changes require a design issue before implementation, including:

- ledger schema changes;
- checkpoint schema changes;
- MCP tool exposure;
- provider envelope behavior;
- recovery policy changes;
- authorization model changes;
- changes that affect fail-closed behavior.

Maintainers may decline changes that are technically valid but conflict with ACLTD's purpose as recovery-first infrastructure.

## Branch Policy

`main` is the canonical public branch and must be protected.

Recommended branch rules:

- no direct pushes to `main`;
- pull request required before merge;
- at least one maintainer approval;
- passing CI required;
- conversation resolution required;
- stale approvals dismissed after new commits;
- force-push disabled for protected branches;
- deletion disabled for protected branches.

## Release Policy

Releases must include:

- version tag;
- changelog entry;
- validation summary;
- known limitations;
- migration notes, if any;
- rollback risk assessment;
- maintainer approval.

## Scope Control

ACLTD should remain a continuity and recovery layer.

Advanced routing, multi-agent orchestration, model selection, cognitive planning, and expert routing may live above ACLTD, but should not weaken the recovery contract.
