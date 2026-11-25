# Validation Summary - ACLTD 2.0.0

Status: **stable**. Accepted by the maintainer on 2026-11-25 after field tests on
the target hardware: network loss, power loss and forced shutdown.

Technical validation is distinct from human approval of any recovered state.
No result below grants an agent production or external-action authority.

## Findings addressed by 2.0

| Finding | Implementation | Test |
| --- | --- | --- |
| V1 forged history | Schema `acltd-2.0`; mandatory HMAC-SHA256 on entries, anchor and checkpoint; caller key or key callback; `on_head` / `expected_head` | T47 |
| V2 prompt-channel mixing | System holds protocol, mission, facts and gaps; summary, questions and turns go to a delimited, JSON-quoted user data block; reserved markers refused case-insensitively | T48 |
| V6 fixed approver | `build_resume_text(state, token_budget, approver)` with no default; envelopes carry `requires_approval=true` and `approver` | T49 |
| C1 torn tail dead end | Explicit `repair_torn_tail` with approver and reason; validates prefix and anchor first; removes only the noncanonical tail and audits size, SHA256, approver and reason | T50, T57 |
| C2 stale checkpoint | Restore accepts only the latest confirmed checkpoint or the newest pending intent | T51 |
| C3 writer races | `<ledger>.lock` with `msvcrt.locking` / `fcntl.flock`, across threads and processes, covering the whole checkpoint transaction; `LedgerBusy` timeout | T52 |
| C4 linear append cost | Full verification on open, restore and unexpected external change; normal append authenticates anchor and reads only head and tail | T53 |
| C5 directory durability | POSIX directory `fsync` after every `os.replace` and on initial creation; Windows limit documented | T54 |
| V5 plaintext storage | Optional `encrypt` / `decrypt` hooks; base64 ciphertext; MAC over ciphertext; no external packages | T55, T58 |
| C6 mixed backups | Coherent older set restores; mixed journal/checkpoint pieces from different instants are refused | acceptance |
| V3 / V4 | Out of core scope: data levels, tenant, person and path authority belong to integration adapters | - |

## Automated results

| Suite | Result | Evidence |
| --- | --- | --- |
| Self-test | 61/61 PASS (49 original results plus T47-T58) | `tests/evidence/selftest-2.0.txt`, `skill/acltd/references/selftest_results.json` |
| Quick validate | manifest, sidecar, compile, ASCII and self-test PASS | `tests/evidence/quick-2.0.txt` |
| Cross-version regressions | 2.0.0: 12/12 protections; 1.4.4: 0/12 (expected) | `tests/evidence/regressions-2.0.*`, `tests/evidence/regressions-1.4.4.*` |
| Acceptance attacks | V1, V2, V5, V6, C1-C6 PROTECTED; V3/V4 out of core scope | `tests/acceptance/resultado-2.0.json` |
| Extended hostile campaign | 13,000 corruptions refused, 0 accepted, 0 raw exceptions | `tests/evidence/campaign-2.0.txt`, `skill/acltd/references/campaign_results.json` |

Extended campaign detail:

| Campaign | Volume | Result |
| --- | ---: | --- |
| C1 ledger byte mutations | 5000 | 0 accepted, 0 raw exceptions |
| C2 checkpoint mutations | 5000 | 0 accepted, 0 raw exceptions |
| C3 anchor garbage | 2000 | 0 accepted, 0 raw exceptions |
| C4 combined corruption | 1000 | 0 accepted, 0 raw exceptions |
| C5 checkpoint phase matrix | 30 | 30 recovered |
| C6 reboot cycles | 100 | 0 failures |
| C7 append stress | 1000 | 1000 valid entries |

## Append cost (C4)

1,500 decisions per run, keeping file `fsync` and atomic anchor replacement.
Target: point ratio and median ratio of at most 2.

| Run | n10 ms | n1500 ms | n1500/n10 | End/start medians |
| --- | ---: | ---: | ---: | ---: |
| 1.4.4 regressions | 14.102 | 64.971 | 4.607 | 4.751 |
| 2.0.0 regressions | 24.080 | 19.747 | 0.820 | 0.923 |
| 2.0.0 acceptance | 18.236 | 17.769 | 0.974 | 1.044 |

These are observations on one Windows host, subject to cache, antivirus and I/O
load; they are not a latency promise on other targets. Under concurrency, two
processes wrote 40 entries each with no refusal or corruption (81 entries with
the initial record), and a held lock surfaced as `LedgerBusy`.

## Compatibility with 1.x journals

2.0 is a deliberate contract change. `append_entry` and `verify_chain` require a
key and refuse legacy schemas; `restore_checkpoint` accepts only 2.0 checkpoints.
`verify_legacy` is read-only and checks unkeyed 1.x integrity, which does not
prove authorship. `migrate_from_legacy(old, new, key, approver)` requires explicit
approval and a new path, leaves the legacy journal intact and opens the 2.0
journal with a `migration` record (legacy head, count, approver and
`legacy_authenticated=false`). Legacy checkpoint state must be reviewed and
written again as a 2.0 checkpoint by the caller.

## Reproduce

From the repository root, with an exclusive temporary directory for attacks:

```bash
python skill/acltd/scripts/acltd_regression.py --output tests/evidence/regressions-2.0.json
python skill/acltd/scripts/acltd_selftest.py --update-reference
python -I tests/acceptance/acceptance_attacks.py skill/acltd/scripts <exclusive-temp-dir>
python skill/acltd/scripts/acltd_campaign.py --update-reference
# After refreshing references, regenerate MANIFEST_SHA256.txt and its .sha256 sidecar.
python skill/acltd/scripts/quick_validate.py
```

## Limits

- Windows stdlib has no directory flush equivalent to POSIX directory `fsync`.
- Advisory locks require cooperating processes and a filesystem that supports them.
- Without a trusted external `expected_head`, a complete authentic older set can
  still be restored locally.
- Integration adapters own real keys, identity, data levels, MCP and coordinated
  backups; none of them is part of this core.
