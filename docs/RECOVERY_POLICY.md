# Recovery Policy

ACLTD v1.4.4 is approved for homologation and optional pilot use. It is not approved for automatic production installation.

## Homologation Position

ACLTD may be kept available as a recovery resource when real incidents occur.

It may use real operational evidence for:

- incident observation;
- recovery analysis;
- continuity reconstruction;
- duplicate-action prevention;
- gap identification;
- post-incident reporting.

It must not use homologation access for:

- production rollback;
- production writes;
- automatic installation;
- automatic promotion;
- automatic patching;
- silent recovery;
- unapproved external actions.

## Why This Policy Exists

The project was created because real continuity incidents happened. Ignoring real operational data would make the tool less useful.

The safe compromise is controlled homologation:

- real evidence may inform recovery;
- production state is not changed;
- every action remains human-gated;
- ambiguous state fails closed.

## Activation Criteria

ACLTD may be proposed when one or more of the following occurs:

- terminal or process shutdown during a long mission;
- lost session;
- provider or model change;
- handover gap;
- suspected duplicated action;
- suspected contradiction of prior decisions;
- corrupted or incomplete recovery state;
- incident similar to the original failure history.

Before any use, the agent must report:

1. the incident or risk detected;
2. why ACLTD applies;
3. the proposed scope;
4. which data would be consulted;
5. which actions will not be taken without approval;
6. the exact human command needed to proceed.

## Final Rule

Real data may support recovery analysis. It must not become permission to alter production.
