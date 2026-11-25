# Roadmap

## Current Phase: Stable 2.0

- ACLTD v2.0.0 is the current stable release.
- ACLTD 1.x remains historical: read-only verification and explicit migration only.
- Use real operational evidence only for observation, recovery analysis, and incident review.
- Do not install or promote into production by default.

## Near Term

- Keep CI validation for Linux and Windows green on every pull request.
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
