# -*- coding: utf-8 -*-
"""Rodada 2 da simulacao de ataques ao ACLTD (03/11/2026).

Cada teste reproduz um achado da rodada 1. "VULNERAVEL" = o ACLTD v1.4.4
faz o que nao deveria; "PROTEGIDO" = recusa corretamente.
Adapted for 2.0 API; original SHA-256: e5648dcb22583d9e86c0f0e657d7e691653986bddf348fa2144620fea1db6928.
Uso: python -I acceptance_attacks.py <pasta scripts do ACLTD> <pasta de trabalho>
"""
import json
import multiprocessing
import os
import shutil
import sys
import time

SCRIPTS = os.path.abspath(sys.argv[1])
WORK = os.path.abspath(sys.argv[2])
sys.path.insert(0, SCRIPTS)

import acltd_ledger as L  # noqa: E402
import acltd_checkpoint as C  # noqa: E402
import acltd_context_pack as P  # noqa: E402

RESULTS = []


def rec(cid, vulneravel, detalhe):
    RESULTS.append({"achado": cid,
                    "resultado": "VULNERAVEL" if vulneravel else "PROTEGIDO",
                    "detalhe": detalhe})


def fresh(name):
    d = os.path.join(WORK, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    return d


def state(summary="estado A", **extra):
    s = {"mission_id": "M-ATLAS-PARECER-001",
         "pinned_facts": [{"text": "Pacote P-7 com 300 itens", "source": "ledger:seq0"}],
         "rolling_summary": summary,
         "last_turns": [{"role": "user", "text": "Avalie os itens"},
                        {"role": "assistant", "text": "Item 41 aprovado"}],
         "open_questions": [], "gaps": [],
         "provider": {"name": "ollama"}}
    s.update(extra)
    return s


# 2.0 adaptation: same findings are exercised by cross-version regressions.
# The original C6 three-piece backup scenario below is kept intact.
from acltd_regression import run_regressions, KEY


def run_attacks():
    for r in run_regressions({"V1", "V2", "V5", "V6", "C1", "C2", "C3", "C4", "C5"}):
        RESULTS.append({"achado": r["finding"],
                        "resultado": "PROTEGIDO" if r["ok"] else "FALHOU",
                        "detalhe": r["detail"]})
    for finding in ("V3", "V4"):
        RESULTS.append({"achado": finding, "resultado": "FORA_DO_ESCOPO_ADAPTADOR",
                        "detalhe": "Core does not authorize provider/data level or tenant/path identity; integration adapter."})


# C6 - backup de pecas de instantes diferentes
def c6():
    d = fresh("c6"); lp = os.path.join(d, "l.jsonl"); ap = L.default_anchor_path(lp)
    cp = os.path.join(d, "checkpoint.json")
    C.write_checkpoint(d, state("estado A"), lp, key=KEY)
    snap = {p: open(p, "rb").read() for p in (lp, ap, cp)}
    C.write_checkpoint(d, state("estado B"), lp, key=KEY)
    novo = {p: open(p, "rb").read() for p in (lp, ap, cp)}

    def montar(src):
        for p, b in src.items():
            open(p, "wb").write(b)
        return C.restore_checkpoint(d, lp, key=KEY)
    r_tudo_antigo = montar(snap)
    r_misto1 = montar({lp: novo[lp], ap: novo[ap], cp: snap[cp]})
    r_misto2 = montar({lp: snap[lp], ap: snap[ap], cp: novo[cp]})
    rec("C6", (r_misto1.get("ok") or r_misto2.get("ok")) or not r_tudo_antigo.get("ok"),
        "conjunto antigo inteiro: ok=%s; diario novo + checkpoint antigo: ok=%s; "
        "diario antigo + checkpoint novo: ok=%s (recusa segura, mas a missao para)"
        % (r_tudo_antigo.get("ok"), r_misto1.get("ok"), r_misto2.get("ok")))


if __name__ == "__main__":
    os.makedirs(WORK, exist_ok=True)
    for fn in (run_attacks, c6):
        try:
            fn()
        except Exception as e:
            RESULTS.append({"achado": fn.__name__.upper(), "resultado": "ERRO_NO_TESTE",
                            "detalhe": repr(e)})
    output = json.dumps(RESULTS, indent=1, ensure_ascii=True) + "\n"
    with open(os.path.join(os.path.dirname(__file__), "resultado-2.0.json"), "w", encoding="ascii", newline="\n") as f:
        f.write(output)
    print(output)
    expected = {"V1", "V2", "V5", "V6", "C1", "C2", "C3", "C4", "C5", "C6"}
    ok = {r["achado"] for r in RESULTS if r["resultado"] == "PROTEGIDO"} == expected
    ok = ok and all(any(r["achado"] == k and r["resultado"] == "FORA_DO_ESCOPO_ADAPTADOR" for r in RESULTS) for k in ("V3", "V4"))
    sys.exit(0 if ok else 1)
