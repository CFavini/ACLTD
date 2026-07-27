# MCP Alignment

ACLTD is designed to align with MCP without treating MCP as the source of truth.

MCP is an interface boundary. ACLTD's truth is the verified recovery record.

## Future MCP Surface

| MCP Surface | ACLTD Use |
| --- | --- |
| Resources | Read-only mission status, pinned facts, gaps, checkpoint metadata, validation summaries |
| Prompts | Safe resume prompt templates and incident review templates |
| Tools | Explicitly human-gated validation, checkpoint, restore, and report generation |

## Non-Negotiable MCP Rules

- No tool may install ACLTD automatically.
- No tool may promote homologation state into production.
- No tool may execute rollback without explicit human authorization.
- No tool may transform ambiguous state into claimed fact.
- No tool may bypass ledger, anchor, or checkpoint verification.
- No tool may write outside its approved scope.

## Suggested MCP Tool Names

These names are proposals only:

- `acltd_validate_state`
- `acltd_build_resume`
- `acltd_write_checkpoint`
- `acltd_restore_checkpoint`
- `acltd_incident_report`

Every mutating tool should declare its scope, required files, expected writes, and human approval requirement before execution.
