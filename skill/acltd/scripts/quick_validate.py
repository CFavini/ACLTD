# -*- coding: ascii -*-
"""ACLTD Quick Validate - validacao rapida do pacote extraido.
Roda: manifesto (se sha256sum disponivel), py_compile, ASCII-check e
self-test completo. Exit 0 apenas se TUDO passar. Portavel Win/Linux."""
import hashlib
import json
import os
import py_compile
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
steps = []


def step(name, ok, detail=""):
    steps.append({"step": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + ("  | " + detail if detail else ""))


def check_manifest():
    mpath = os.path.join(ROOT, "MANIFEST_SHA256.txt")
    if not os.path.exists(mpath):
        step("manifesto", False, "MANIFEST_SHA256.txt ausente")
        return
    bad = []
    n = 0
    for line in open(mpath, "r", encoding="ascii"):
        line = line.strip()
        if not line:
            continue
        expected, rel = line.split(None, 1)
        rel = rel.strip()
        fp = os.path.join(ROOT, rel.lstrip("./"))
        try:
            h = hashlib.sha256(open(fp, "rb").read()).hexdigest()
        except (IOError, OSError):
            bad.append(rel + " (ilegivel)")
            continue
        n += 1
        if h != expected:
            bad.append(rel)
    step("manifesto", len(bad) == 0, "%d arquivos, divergentes: %s" % (n, bad))


def check_compile_and_ascii():
    bad_c, bad_a = [], []
    for fn in sorted(os.listdir(HERE)):
        if not fn.endswith(".py"):
            continue
        fp = os.path.join(HERE, fn)
        try:
            py_compile.compile(fp, doraise=True)
        except py_compile.PyCompileError:
            bad_c.append(fn)
        try:
            open(fp, "rb").read().decode("ascii")
        except UnicodeDecodeError:
            bad_a.append(fn)
    step("py_compile", len(bad_c) == 0, str(bad_c))
    step("ascii_ps51", len(bad_a) == 0, str(bad_a))


def run_selftest():
    p = subprocess.run([sys.executable, os.path.join(HERE, "acltd_selftest.py")],
                       capture_output=True, text=True)
    tail = (p.stdout or "").strip().splitlines()
    res = ""
    for ln in tail:
        if ln.startswith("RESULTADO"):
            res = ln
    step("selftest", p.returncode == 0, res)


if __name__ == "__main__":
    check_manifest()
    check_compile_and_ascii()
    run_selftest()
    ok = all(s["ok"] for s in steps)
    print(json.dumps({"ok": ok, "source": "acltd_quick_validate",
                      "external_action_allowed": False,
                      "requires_favini": True,
                      "data": {"steps": steps}}))
    sys.exit(0 if ok else 1)
