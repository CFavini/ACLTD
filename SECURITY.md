# Security Policy

ACLTD is recovery infrastructure. Security reports are treated seriously because corrupted recovery state can cause repeated actions, false continuity, or unsafe resumption.

## Supported Versions

| Version | Status |
| --- | --- |
| 1.4.3 | Homologation / optional pilot |
| earlier versions | Historical audit only |

## Report a Vulnerability

Please report vulnerabilities privately before opening a public issue.

Include:

- affected version;
- operating system and shell;
- Python version;
- reproduction steps;
- expected behavior;
- observed behavior;
- whether the issue allows tampering, rollback, duplicate action, invented state, or bypass of human authorization.

## Security Boundaries

ACLTD must not:

- execute external actions without explicit human authorization;
- treat model output as source-of-truth state;
- silently repair corrupted ledgers;
- accept malformed JSONL;
- accept duplicated JSON keys;
- accept NaN or Infinity values;
- accept rollback below the anchor;
- bypass checkpoint validation;
- write to production during homologation.

## Responsible Disclosure

Maintainers will acknowledge valid reports, assess severity, prepare a fix when appropriate, and publish security notes without exposing exploit details before users have a reasonable update path.
