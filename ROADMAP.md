# Roadmap

## Current Phase: Public Homologation

- Publish the repository as a public open-source project.
- Keep ACLTD v1.4.3 as an optional homologation resource.
- Use real operational evidence only for observation, recovery analysis, and incident review.
- Do not install or promote into production by default.

## Near Term

- Add English-facing documentation without changing the audited v1.4.3 package.
- Add CI validation for Linux and Windows.
- Add MCP interface design notes.
- Add incident replay examples using sanitized fixtures.
- Add branch protection and repository ruleset documentation.

## Later

- Define a read-only MCP resource surface.
- Define explicit human-gated MCP tools for validation and restore.
- Evaluate multi-writer locking as a separate proposal.
- Evaluate ledger rotation by mission.

## Out of Scope for ACLTD Core

- Autonomous production rollback.
- Unapproved external actions.
- Model-driven reconstruction of missing state.
- Multi-agent routing.
- Cognitive expert routing.
- Automatic installation into live agent workflows.
