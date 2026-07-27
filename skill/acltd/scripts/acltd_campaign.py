# -*- coding: ascii -*-
"""ACLTD Campaign Runner v1.4.4 - campanha estendida reprodutivel.

Executa cenarios hostis deterministas de corrupcao, queda e reboot. Nao
substitui acltd_selftest.py; serve para reproduzir references/campaign_results.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from acltd_ledger import append_entry, verify_chain, default_anchor_path
from acltd_checkpoint import write_checkpoint, restore_checkpoint
from acltd_selftest import sample_state


def _write(path, data):
    mode = "wb" if isinstance(data, bytes) else "w"
    kwargs = {} if "b" in mode else {"encoding": "ascii", "newline": "\n"}
    with open(path, mode, **kwargs) as f:
        f.write(data)


def _mutate_bytes(base, index):
    b = bytearray(base)
    pos = index % len(b)
    b[pos] = b[pos] ^ 1
    return bytes(b)


def _semantic_positions(base):
    return [i for i, ch in enumerate(base) if ch not in b" \n\r\t"]


def c1_ledger_byte_mutations(work, volume=5000):
    d = os.path.join(work, "c1"); os.makedirs(d)
    lp = os.path.join(d, "l.jsonl")
    for i in range(4):
        append_entry(lp, "note", {"i": i})
    base = open(lp, "rb").read()
    positions = _semantic_positions(base)
    raw_ex = accepted = 0
    for i in range(volume):
        pos = positions[i % len(positions)]
        mutated = bytearray(base); mutated[pos] = mutated[pos] ^ 1
        _write(lp, bytes(mutated))
        try:
            ok, det = verify_chain(lp)
            if ok:
                accepted += 1
        except Exception:
            raw_ex += 1
    _write(lp, base)
    return {"volume": volume, "raw_exceptions": raw_ex, "accepted": accepted,
            "ok": raw_ex == 0 and accepted == 0}


def c2_checkpoint_mutations(work, volume=5000):
    d = os.path.join(work, "c2"); os.makedirs(d)
    lp = os.path.join(d, "l.jsonl")
    write_checkpoint(d, sample_state(), lp)
    cp = os.path.join(d, "checkpoint.json")
    base = open(cp, "rb").read()
    start = base.index(b'"state"')
    end = base.index(b'"state_sha256"')
    protected = base[start:end]
    offset = start
    positions = [offset + i for i in _semantic_positions(protected)]
    raw_ex = accepted = 0
    for i in range(volume):
        pos = positions[i % len(positions)]
        mutated = bytearray(base); mutated[pos] = mutated[pos] ^ 1
        _write(cp, bytes(mutated))
        try:
            out = restore_checkpoint(d, lp)
            if out.get("ok"):
                accepted += 1
        except Exception:
            raw_ex += 1
    _write(cp, base)
    return {"volume": volume, "raw_exceptions": raw_ex, "accepted": accepted,
            "ok": raw_ex == 0 and accepted == 0}


def c3_anchor_garbage(work, volume=2000):
    d = os.path.join(work, "c3"); os.makedirs(d)
    lp = os.path.join(d, "l.jsonl")
    append_entry(lp, "note", {"i": 0})
    ap = default_anchor_path(lp)
    good = open(ap, "rb").read()
    raw_ex = accepted = 0
    for i in range(volume):
        garbage = ("{\"seq\":%d,\"hash\":\"%064d\",\"schema\":\"bad\"}" %
                   (i, i)).encode("ascii")
        _write(ap, garbage)
        try:
            ok, det = verify_chain(lp)
            if ok:
                accepted += 1
        except Exception:
            raw_ex += 1
    _write(ap, good)
    return {"volume": volume, "raw_exceptions": raw_ex, "accepted": accepted,
            "ok": raw_ex == 0 and accepted == 0}


def c4_combined_corruption(work, volume=1000):
    d = os.path.join(work, "c4"); os.makedirs(d)
    lp = os.path.join(d, "l.jsonl")
    write_checkpoint(d, sample_state(), lp)
    cp = os.path.join(d, "checkpoint.json")
    ap = default_anchor_path(lp)
    led = open(lp, "rb").read(); ck = open(cp, "rb").read(); an = open(ap, "rb").read()
    raw_ex = accepted = 0
    for i in range(volume):
        _write(lp, _mutate_bytes(led, i))
        _write(cp, _mutate_bytes(ck, i * 3))
        _write(ap, _mutate_bytes(an, i * 5))
        try:
            out = restore_checkpoint(d, lp)
            if out.get("ok"):
                accepted += 1
        except Exception:
            raw_ex += 1
    _write(lp, led); _write(cp, ck); _write(ap, an)
    return {"volume": volume, "raw_exceptions": raw_ex, "accepted": accepted,
            "ok": raw_ex == 0 and accepted == 0}


def c5_checkpoint_phase_matrix(work, volume=30):
    ok_count = raw_ex = 0
    for i in range(volume):
        d = os.path.join(work, "c5_%02d" % i); os.makedirs(d)
        lp = os.path.join(d, "l.jsonl")
        write_checkpoint(d, sample_state(), lp)
        out = restore_checkpoint(d, lp)
        if out.get("ok"):
            ok_count += 1
    return {"volume": volume, "raw_exceptions": raw_ex,
            "recovered": ok_count, "ok": ok_count == volume}


def c6_reboot_cycles(work, volume=100):
    d = os.path.join(work, "c6"); os.makedirs(d)
    lp = os.path.join(d, "l.jsonl")
    write_checkpoint(d, sample_state(), lp)
    failures = 0
    for i in range(volume):
        p = subprocess.run([sys.executable, os.path.join(HERE, "acltd_checkpoint.py"),
                            "restore", d, lp],
                           capture_output=True, text=True)
        if p.returncode != 0:
            failures += 1
    return {"volume": volume, "failures": failures, "ok": failures == 0}


def c7_append_stress(work, volume=1000):
    d = os.path.join(work, "c7"); os.makedirs(d)
    lp = os.path.join(d, "l.jsonl")
    start = time.time()
    for i in range(volume):
        append_entry(lp, "note", {"i": i})
    ok, det = verify_chain(lp)
    elapsed = time.time() - start
    return {"volume": volume, "verify_ok": ok, "entries": det.get("entries"),
            "seconds": round(elapsed, 3),
            "ok": ok and det.get("entries") == volume}


def main():
    update_reference = "--update-reference" in sys.argv[1:]
    work = tempfile.mkdtemp(prefix="acltd_campaign_")
    campaigns = {
        "C1_ledger_byte_mutations": c1_ledger_byte_mutations(work),
        "C2_checkpoint_mutations": c2_checkpoint_mutations(work),
        "C3_anchor_garbage": c3_anchor_garbage(work),
        "C4_combined_corruption": c4_combined_corruption(work),
        "C5_checkpoint_phase_matrix": c5_checkpoint_phase_matrix(work),
        "C6_reboot_cycles": c6_reboot_cycles(work),
        "C7_append_stress": c7_append_stress(work),
    }
    ok = all(c["ok"] for c in campaigns.values())
    out = {"ok": ok, "source": "acltd_campaign",
           "external_action_allowed": False, "requires_favini": True,
           "data": {"work": "temporary_test_workspace",
                    "campaigns": campaigns}}
    if update_reference:
        out_path = os.path.join(ROOT, "references", "campaign_results.json")
    else:
        out_path = os.path.join(work, "campaign_results.json")
    if update_reference:
        out["data"]["results_path"] = "acltd/references/campaign_results.json"
    else:
        out["data"]["results_path"] = "temporary_test_workspace/campaign_results.json"
    _write(out_path, json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
