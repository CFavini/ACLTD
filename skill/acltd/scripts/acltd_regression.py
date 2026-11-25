# -*- coding: ascii -*-
"""T47+ regressions, same scenarios runnable against 1.4.4 and 2.0.

Usage: python acltd_regression.py --scripts PATH [--output JSON]
Compatibility helpers only supply new parameters when supported; they do not
simulate missing protections. Missing features are explicit test failures.
"""
import argparse
import hashlib
import importlib
import inspect
import json
import multiprocessing
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from unittest import mock

KEY = b"ACLTD-public-test-fixture-key-2.0"
APPROVER = "RT fixture"
SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def modules():
    return tuple(importlib.import_module(n) for n in
                 ("acltd_ledger", "acltd_checkpoint", "acltd_context_pack"))


def call(fn, *args, **kwargs):
    if "key" in inspect.signature(fn).parameters:
        kwargs.setdefault("key", KEY)
    return fn(*args, **kwargs)


def resume(state, approver=APPROVER):
    _, _, P = modules()
    if "approver" in inspect.signature(P.build_resume_text).parameters:
        return P.build_resume_text(state, 4000, approver)
    return P.build_resume_text(state, 4000)


def state(summary="estado A"):
    return {"mission_id": "M-fixture", "provider": {"name": "ollama"},
            "pinned_facts": [{"text": "item 42 reprovado", "source": "ledger:seq0"}],
            "rolling_summary": summary, "last_turns": [{"role": "user", "text": "trecho externo"}],
            "open_questions": ["questao externa"], "gaps": ["evidencia ausente"]}


def fake_encrypt(raw):
    # NAO E SEGURO - so teste (NOT SECURE, test only).
    return bytes(b ^ 0xA5 for b in raw[::-1])


def fake_decrypt(raw):
    # NAO E SEGURO - so teste (NOT SECURE, test only).
    return bytes(b ^ 0xA5 for b in raw)[::-1]


def t47_v1(d):
    L, C, P = modules()
    lp = str(d / "l.jsonl")
    heads = []
    extra = {"on_head": lambda seq, h: heads.append((seq, h))} if "on_head" in inspect.signature(L.append_entry).parameters else {}
    for i in range(3):
        call(L.append_entry, lp, "decision", {"item": 42, "status": "reprovado", "i": i}, **extra)
    good = Path(lp).read_bytes()
    ap = L.default_anchor_path(lp)
    old_anchor = Path(ap).read_bytes()
    entries = L._read_entries(lp)
    entries[1]["payload"]["status"] = "aprovado"
    prev = L.GENESIS_HASH
    for obj in entries:
        obj.pop("hash")
        obj["prev_hash"] = prev
        obj["hash"] = L._entry_hash(obj)
        prev = obj["hash"]
    Path(lp).write_text("".join(L._canon(e) + "\n" for e in entries), encoding="ascii", newline="\n")
    a = json.loads(old_anchor)
    a["hash"] = prev
    Path(ap).write_text(L._canon(a), encoding="ascii")
    rejected = not call(L.verify_chain, lp)[0]
    Path(lp).write_bytes(good); Path(ap).write_bytes(old_anchor)
    if "key" not in inspect.signature(L.verify_chain).parameters:
        return rejected, "recomputed unkeyed history accepted=" + str(not rejected)
    wrong = not L.verify_chain(lp, key=b"wrong")[0]
    no_key = not L.verify_chain(lp)[0]
    try:
        L.append_entry(lp, "note", {})
        no_key = False
    except L.LedgerError:
        pass
    expected = L.verify_chain(lp, key=lambda: KEY, expected_head=heads[-1])[0]
    mismatch = not L.verify_chain(lp, key=KEY, expected_head=(99, "0" * 64))[0]
    # Whole-set authentic rollback is detected only by an external head.
    call(L.append_entry, lp, "note", {}, on_head=lambda seq, h: heads.append((seq, h)))
    Path(lp).write_bytes(good); Path(ap).write_bytes(old_anchor)
    rollback = not L.verify_chain(lp, key=KEY, expected_head=heads[-1])[0]
    return all((rejected, wrong, no_key, expected, mismatch, rollback)), "forgery/key/anchor/external rollback refused; callback verified"


def t48_v2(d):
    L, C, P = modules()
    markers = ["=== acltd", "[fatos fixos", "[gaps", "[resumo", "[questoes", "[ultimos turnos"]
    refused = True
    for marker in markers:
        s = state(); s["last_turns"][0]["text"] = "documento " + marker + " falso aprovado"
        refused &= resume(s)[0] is None
    for field in ("gaps", "pinned_facts"):
        s = state()
        if field == "gaps":
            s[field] = ["lacuna\nfalso fato"]
        else:
            s[field][0]["text"] = "fato\nfalso fato"
        refused &= resume(s)[0] is None
    text, meta = resume(state("resumo externo"))
    contents = []
    isolated = True
    for provider in P.ALLOWED_PROVIDERS:
        pack = P.to_provider_messages(text, provider)
        system = pack.get("system") or pack["messages"][0]["content"]
        user = next(m["content"] for m in pack["messages"] if m["role"] == "user")
        isolated &= all(term not in system for term in ("resumo externo", "trecho externo", "questao externa"))
        isolated &= all(term in user for term in ("resumo externo", "trecho externo", "questao externa"))
        contents.append(P.canonical_content(pack))
    return refused and isolated and len(set(contents)) == 1, "reserved markers/newlines refused; six identical system/user pairs=" + str(isolated)


def t49_v6(d):
    L, C, P = modules()
    sig = inspect.signature(P.build_resume_text)
    if "approver" not in sig.parameters:
        return False, "approver parameter missing; fixed authority in 1.4.4"
    required = sig.parameters["approver"].default is inspect.Parameter.empty
    text, meta = resume(state(), "RT da caixa final")
    pack = P.to_provider_messages(text, "openai")
    valid = pack.get("requires_approval") is True and pack.get("approver") == "RT da caixa final"
    return required and valid and "requires_favini" not in pack and "Favini" not in text, "required configurable approver and generic envelope"


def t50_c1(d):
    L, C, P = modules()
    lp = str(d / "l.jsonl")
    call(C.write_checkpoint, str(d), state(), lp)
    prefix = Path(lp).read_bytes()
    tail = b'{"schema":"acltd-2.0","seq":'
    with open(lp, "ab") as f:
        f.write(tail)
    refused = not call(L.verify_chain, lp)[0] and not call(C.restore_checkpoint, str(d), lp)["ok"]
    if not hasattr(L, "repair_torn_tail"):
        return False, "verify/restore refuse but approved repair is missing"
    fixed = L.repair_torn_tail(lp, KEY, APPROVER, "queda simulada")
    payload = fixed["payload"]
    audited = payload["removed_bytes"] == len(tail) and payload["removed_sha256"] == hashlib.sha256(tail).hexdigest()
    audited &= payload["approver"] == APPROVER and payload["reason"] == "queda simulada"
    safe = Path(lp).read_bytes().startswith(prefix) and call(L.verify_chain, lp)[0]
    safe &= call(C.restore_checkpoint, str(d), lp)["ok"]
    # A complete canonical entry missing only LF MUST NOT be removed.
    raw = Path(lp).read_bytes()[:-1]; Path(lp).write_bytes(raw)
    try:
        L.repair_torn_tail(lp, KEY, APPROVER, "must refuse")
        safe = False
    except L.LedgerError:
        safe &= Path(lp).read_bytes() == raw
    return refused and audited and safe, "partial bytes audited; full prefix unchanged; canonical final entry preserved"


def t51_c2(d):
    L, C, P = modules()
    lp = str(d / "l.jsonl"); cp = d / "checkpoint.json"
    call(C.write_checkpoint, str(d), state("A: 1-100"), lp)
    old = cp.read_bytes()
    call(C.write_checkpoint, str(d), state("B: 1-200"), lp)
    digest = C._sha256_text(C._state_body(state("C: pending")))
    call(L.append_entry, lp, "checkpoint_intent", {"state_sha256": digest})
    normal = call(C.restore_checkpoint, str(d), lp)
    cp.write_bytes(old)
    attack = call(C.restore_checkpoint, str(d), lp)
    return normal["ok"] and normal["state"]["rolling_summary"].startswith("B") and not attack["ok"], "normal latest=B; mixed old A refused=" + str(not attack["ok"])


def writer(args):
    scripts, lp, tag, n = args
    sys.path.insert(0, scripts)
    L = importlib.import_module("acltd_ledger")
    errors = []
    for i in range(n):
        try:
            call(L.append_entry, lp, "note", {"w": tag, "i": i})
        except Exception as e:
            errors.append(type(e).__name__)
    return errors


def t52_c3(d):
    L, C, P = modules()
    lp = str(d / "l.jsonl")
    call(L.append_entry, lp, "note", {})
    if not hasattr(L, "LedgerBusy"):
        return False, "no OS lock or LedgerBusy in 1.4.4 (original race recorded separately)"
    # Real OS process owns lock while parent tests timeout classification.
    code = "import sys,time;sys.path.insert(0,sys.argv[1]);from acltd_ledger import ledger_lock;" \
           "ctx=ledger_lock(sys.argv[2]);ctx.__enter__();print('locked',flush=True);sys.stdin.readline();ctx.__exit__(None,None,None)"
    proc = subprocess.Popen([sys.executable, "-c", code, SCRIPTS, lp], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    busy = False
    try:
        assert proc.stdout.readline().strip() == "locked"
        try:
            call(L.append_entry, lp, "note", {}, lock_timeout=0.03)
        except L.LedgerBusy:
            busy = True
        try:
            call(L.verify_chain, lp, lock_timeout=0.03)
            busy = False
        except L.LedgerBusy:
            pass
    finally:
        proc.communicate("done\n", timeout=10)
    with multiprocessing.get_context("spawn").Pool(2) as pool:
        errors = pool.map(writer, [(SCRIPTS, lp, "iris", 40), (SCRIPTS, lp, "atlas", 40)])
    ok, det = call(L.verify_chain, lp)
    return busy and ok and det["entries"] == 81 and errors == [[], []], "2 writers x40; entries=%s errors=%s; timeout=LedgerBusy" % (det.get("entries"), errors)


def t53_c4(d):
    L, C, P = modules()
    lp = str(d / "l.jsonl")
    windows = {10: [], 1500: []}; exact = {}
    started = time.perf_counter()
    for i in range(1, 1501):
        t = time.perf_counter()
        call(L.append_entry, lp, "decision", {"item": i, "parecer": "aprovado"})
        elapsed = (time.perf_counter() - t) * 1000
        if 1 <= i <= 20:
            windows[10].append(elapsed)
        if i >= 1481:
            windows[1500].append(elapsed)
        if i in (10, 300, 900, 1500):
            exact[i] = round(elapsed, 3)
    med = {i: statistics.median(v) for i, v in windows.items()}
    ratio = med[1500] / med[10]
    # Structural check avoids a lucky timing result masking O(n) rereads.
    with mock.patch.object(L, "_read_entries", side_effect=AssertionError("full reread")):
        try:
            call(L.append_entry, lp, "note", {})
            incremental = True
        except AssertionError:
            incremental = False
    data = {"exact_ms": exact, "window_median_ms": med, "ratio": ratio,
            "total_seconds": round(time.perf_counter() - started, 3), "incremental": incremental}
    return incremental and ratio <= 2 and exact[1500] <= 2 * exact[10], json.dumps(data, sort_keys=True)


def t54_c5(d):
    L, C, P = modules()
    if not hasattr(L, "fsync_directory"):
        return False, "directory fsync missing after replace"
    events = []
    original = L.os.replace
    def replace(src, dst):
        original(src, dst)
        events.append(("replace", os.fspath(dst)))
    def sync(path):
        events.append(("sync", os.fspath(path)))
    with mock.patch.object(L.os, "replace", side_effect=replace), mock.patch.object(L, "fsync_directory", side_effect=sync):
        call(C.write_checkpoint, str(d), state(), str(d / "l.jsonl"))
    replaces = [i for i, event in enumerate(events) if event[0] == "replace"]
    paired = len(replaces) == 3 and all(i+1 < len(events) and events[i+1] == ("sync", events[i][1]) for i in replaces)
    # Exercise actual POSIX branch with fd calls mocked, including close.
    fake_os = mock.Mock(name="posix_os", spec=["name", "open", "close", "fsync", "path", "O_RDONLY", "O_DIRECTORY"])
    fake_os.name = "posix"; fake_os.path = os.path
    fake_os.O_RDONLY = 0; fake_os.O_DIRECTORY = 0x10000
    fake_os.open.return_value = 99
    with mock.patch.object(L, "os", fake_os):
        L.fsync_directory(str(d / "checkpoint.json"))
    posix = fake_os.open.call_count == 1 and fake_os.fsync.call_args == mock.call(99) and fake_os.close.call_args == mock.call(99)
    return paired and posix, "3 replacements each followed by directory sync; simulated POSIX open/fsync/close"


def t55_v5(d):
    L, C, P = modules()
    if "encrypt" not in inspect.signature(L.append_entry).parameters:
        return False, "encryption hooks missing; plaintext exposed"
    lp = str(d / "l.jsonl"); secret = "PARECER CONFIDENCIAL NIVEL 3"
    call(C.write_checkpoint, str(d), state(secret), lp, encrypt=fake_encrypt)
    call(L.append_entry, lp, "fact", {"text": secret}, encrypt=fake_encrypt)
    hidden = secret.encode() not in Path(lp).read_bytes() and secret.encode() not in (d / "checkpoint.json").read_bytes()
    out = call(C.restore_checkpoint, str(d), lp, decrypt=fake_decrypt)
    absent = not call(C.restore_checkpoint, str(d), lp)["ok"]
    # Tamper ciphertext and recompute SHA, but not keyed MAC.
    entries = L._read_entries(lp)
    e = entries[-1]; e["payload"] = e["payload"][::-1]; e.pop("hash"); e["hash"] = L._entry_hash(e)
    entries[-1] = e
    Path(lp).write_text("".join(L._canon(x)+"\n" for x in entries),encoding="ascii",newline="\n")
    tamper = not call(L.verify_chain, lp)[0]
    return hidden and out["ok"] and out["state"]["rolling_summary"] == secret and absent and tamper, "ciphertext-only payload/state; roundtrip; missing decrypt/tamper refused (fake hook NOT SECURE)"


def t56_migration(d):
    L, C, P = modules()
    if not hasattr(L, "migrate_from_legacy"):
        return False, "explicit migration API missing"
    lp = str(d / "old.jsonl"); new = str(d / "new.jsonl")
    obj = {"schema": "acltd-1.4", "seq": 0, "kind": "note", "ts": "fixture", "agent": "test",
           "payload": {"old": True}, "external_action_allowed": 0, "prev_hash": L.GENESIS_HASH}
    obj["hash"] = L._entry_hash(obj)
    Path(lp).write_text(L._canon(obj)+"\n",encoding="ascii",newline="\n")
    Path(lp+".anchor").write_text(json.dumps({"schema":"acltd-anchor-1.4","seq":0,"hash":obj["hash"]}),encoding="ascii")
    before = Path(lp).read_bytes()
    old_ok = L.verify_legacy(lp)[0] and not call(L.verify_chain, lp)[0]
    migrated = L.migrate_from_legacy(lp, new, KEY, APPROVER)
    safe = migrated["kind"] == "migration" and migrated["payload"]["legacy_head"] == obj["hash"] and Path(lp).read_bytes() == before
    try:
        L.migrate_from_legacy(lp, new, KEY, APPROVER)
        safe = False
    except L.LedgerError:
        pass
    return old_ok and safe and call(L.verify_chain, new)[0], "legacy read-only; new journal records old head/approver; no historical authentication claimed"


def t57_fail_closed_edges(d):
    L, C, P = modules()
    if not hasattr(L, "repair_torn_tail"):
        return False, "2.0 repair/authentication API missing"
    lp = str(d / "l.jsonl")
    call(L.append_entry, lp, "note", {})
    good = Path(lp).read_bytes()
    # Wrong key and failed encryption must leave damaged bytes untouched.
    damaged = good + b'{"half":'
    Path(lp).write_bytes(damaged)
    checks = []
    for key, encrypt in ((b"wrong", None), (KEY, lambda raw: "not bytes")):
        try:
            L.repair_torn_tail(lp, key, APPROVER, "test", encrypt=encrypt)
            checks.append(False)
        except L.LedgerError:
            checks.append(Path(lp).read_bytes() == damaged)
    # A corrupted complete line may never be cut or hidden by repair.
    corrupted = damaged.replace(b'"kind":"note"', b'"kind":"evil"')
    Path(lp).write_bytes(corrupted)
    try:
        L.repair_torn_tail(lp, KEY, APPROVER, "test")
        checks.append(False)
    except L.LedgerError:
        checks.append(Path(lp).read_bytes() == corrupted)
    Path(lp).write_bytes(good)
    def failed_head(seq, digest):
        raise RuntimeError("external store unavailable")
    try:
        call(L.append_entry, lp, "note", {}, on_head=failed_head)
        checks.append(False)
    except L.LedgerError as e:
        checks.append("persistido" in str(e) and call(L.verify_chain, lp)[1]["entries"] == 2)
    for bad_key in (None, b"", lambda: "not bytes", lambda: 1/0):
        try:
            L.append_entry(lp, "note", {}, key=bad_key)
            checks.append(False)
        except L.LedgerError:
            checks.append(True)
    try:
        call(L.append_entry, None, "note", {})
        checks.append(False)
    except L.LedgerError:
        checks.append(True)
    return all(checks), "wrong key/hook/prefix refuse without truncation; callback failure reports persisted append; invalid inputs typed"


def t58_encrypted_phase_recovery(d):
    L, C, P = modules()
    if "encrypt" not in inspect.signature(C.write_checkpoint).parameters:
        return False, "cipher hooks missing"
    lp = str(d / "l.jsonl")
    original = C.append_entry
    def interrupted(path, kind, *args, **kwargs):
        if kind == "checkpoint_commit":
            raise L.LedgerError("simulated crash after replace before commit")
        return original(path, kind, *args, **kwargs)
    with mock.patch.object(C, "append_entry", side_effect=interrupted):
        try:
            call(C.write_checkpoint, str(d), state("secret checkpoint"), lp, encrypt=fake_encrypt)
        except C.CheckpointError:
            pass
    before = Path(lp).read_bytes()
    refused = not call(C.restore_checkpoint, str(d), lp, decrypt=fake_decrypt)["ok"]
    refused &= Path(lp).read_bytes() == before
    read_only = call(C.restore_checkpoint, str(d), lp, decrypt=fake_decrypt, repair=False)
    unchanged = Path(lp).read_bytes() == before and "pendente" in read_only.get("recovery_note", "")
    out = call(C.restore_checkpoint, str(d), lp, decrypt=fake_decrypt, encrypt=fake_encrypt)
    entries = L._read_entries(lp)
    encrypted = all(e["encrypted"] for e in entries)
    again = call(C.restore_checkpoint, str(d), lp, decrypt=fake_decrypt)
    return refused and unchanged and out["ok"] and encrypted and again["ok"] and "recovery_note" not in again, "interrupted encrypted transaction repaired without plaintext downgrade; read-only restore leaves pending"


CASES = [("T47_V1_HMAC", "V1", t47_v1), ("T48_V2_prompt_channels", "V2", t48_v2),
         ("T49_V6_approver", "V6", t49_v6), ("T50_C1_torn_tail", "C1", t50_c1),
         ("T51_C2_latest_checkpoint", "C2", t51_c2), ("T52_C3_writer_lock", "C3", t52_c3),
         ("T53_C4_incremental", "C4", t53_c4), ("T54_C5_directory_fsync", "C5", t54_c5),
         ("T55_V5_cipher_hooks", "V5", t55_v5), ("T56_legacy_migration", "migration", t56_migration),
         ("T57_fail_closed_edges", "edge", t57_fail_closed_edges),
         ("T58_encrypted_phase_recovery", "cipher_recovery", t58_encrypted_phase_recovery)]


def run_regressions(selected=None):
    results = []
    with tempfile.TemporaryDirectory(prefix="acltd_regression_") as root:
        for name, finding, fn in CASES:
            if selected is not None and finding not in selected:
                continue
            d = Path(root) / name; d.mkdir()
            try:
                ok, detail = fn(d)
            except Exception as e:
                ok, detail = False, "unexpected test exception: " + repr(e)
            results.append({"test": name, "finding": finding, "ok": bool(ok), "detail": detail})
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scripts", default=SCRIPTS)
    parser.add_argument("--output")
    args = parser.parse_args()
    SCRIPTS = os.path.abspath(args.scripts)
    sys.path.insert(0, SCRIPTS)
    out = {"version_under_test": modules()[0].ACLTD_VERSION, "results": run_regressions()}
    out["ok"] = all(r["ok"] for r in out["results"])
    data = json.dumps(out, indent=1, ensure_ascii=True) + "\n"
    if args.output:
        Path(args.output).write_text(data, encoding="ascii", newline="\n")
    print(data)
    sys.exit(0 if out["ok"] else 1)
