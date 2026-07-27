## Summary

What changed?

## Reason

Why is this change needed?

## Risk Surface

- [ ] Ledger format
- [ ] Checkpoint format
- [ ] Anchor behavior
- [ ] Provider envelopes
- [ ] MCP interface
- [ ] Human authorization
- [ ] Fail-closed behavior
- [ ] Documentation only

## Validation

Commands run:

```bash
cd skill/acltd/scripts
python quick_validate.py
```

Results:

## Safety Checklist

- [ ] No direct production write behavior was introduced.
- [ ] No external action can run without explicit human authorization.
- [ ] Missing state is declared as a gap.
- [ ] Corrupted or ambiguous state still fails closed.
- [ ] Runtime recovery data is not committed.
