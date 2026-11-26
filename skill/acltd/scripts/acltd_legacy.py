# -*- coding: ascii -*-
"""Read-only 1.x verification; no authentication guarantee for legacy data."""
import json
import hashlib
import os
import sys
import time

GENESIS_HASH = "0" * 64
KNOWN_ENTRY_SCHEMAS = ("acltd-1.0", "acltd-1.1", "acltd-1.2",
                       "acltd-1.3", "acltd-1.4")
KNOWN_ANCHOR_SCHEMAS = ("acltd-anchor-1.1", "acltd-anchor-1.3",
                        "acltd-anchor-1.4")
SCHEMA_VERSION = "acltd-1.4"
ACLTD_VERSION = "1.4.4"
MAX_ANCHOR_LAG = 1
KNOWN_KINDS = ("turn", "fact", "decision", "gap", "note",
               "checkpoint_intent", "checkpoint_commit", "checkpoint")


class LedgerError(Exception):
    """Falha fail-closed do ledger."""


def _canon(obj):
    """Serializacao canonica estrita. NaN/Infinity e tipos nao
    serializaveis viram LedgerError fail-closed."""
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as e:
        raise LedgerError("objeto nao canonizavel: " + str(e))


def _reject_dup_pairs(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise ValueError("chave JSON duplicada: " + str(k))
        seen[k] = v
    return seen


def _reject_constant(name):
    raise ValueError("constante JSON proibida: " + str(name))


def strict_loads(text):
    """json.loads estrito: recusa chaves duplicadas e NaN/Infinity."""
    return json.loads(text, object_pairs_hook=_reject_dup_pairs,
                      parse_constant=_reject_constant)


def _entry_hash(entry_without_hash):
    return hashlib.sha256(_canon(entry_without_hash).encode("ascii")).hexdigest()


def _validate_entry_contract(obj, line_index=None):
    prefix = "entrada" if line_index is None else "linha %d" % line_index
    kind = obj.get("kind")
    if kind not in KNOWN_KINDS:
        raise LedgerError(prefix + " com kind desconhecido: " + str(kind))
    if not isinstance(obj.get("payload"), dict):
        raise LedgerError(prefix + " com payload nao-objeto")


def default_anchor_path(ledger_path):
    return ledger_path + ".anchor"


def _read_entries(ledger_path):
    entries = []
    if not os.path.exists(ledger_path):
        return entries
    try:
        with open(ledger_path, "rb") as f:
            raw = f.read()
    except (IOError, OSError) as e:
        raise LedgerError("leitura do ledger falhou: " + str(e))
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as e:
        raise LedgerError("ledger contem bytes nao-ASCII: " + str(e))
    if text == "":
        return entries
    if not text.endswith("\n"):
        raise LedgerError("ledger sem newline final (formato nao canonico)")
    for i, line in enumerate(text[:-1].split("\n")):
        if line == "":
            raise LedgerError("linha %d em branco (formato nao canonico)" % i)
        if line != line.strip():
            raise LedgerError("linha %d com espacos nas bordas "
                              "(formato nao canonico)" % i)
        try:
            obj = strict_loads(line)
        except ValueError as e:
            raise LedgerError("json invalido na linha %d: %s" % (i, e))
        if not isinstance(obj, dict):
            raise LedgerError("linha %d nao e objeto" % i)
        if line != _canon(obj):
            raise LedgerError("linha %d nao canonica (raw difere do "
                              "canonizado; possivel adulteracao textual)" % i)
        if obj.get("schema") not in KNOWN_ENTRY_SCHEMAS:
            raise LedgerError("linha %d com schema desconhecido: %s"
                              % (i, obj.get("schema")))
        _validate_entry_contract(obj, i)
        entries.append(obj)
    return entries


def _read_anchor(anchor_path):
    if not os.path.exists(anchor_path):
        return None
    try:
        with open(anchor_path, "rb") as f:
            raw = f.read()
        anchor = strict_loads(raw.decode("ascii"))
    except (IOError, OSError, ValueError) as e:
        raise LedgerError("ancora invalida: " + str(e))
    if not isinstance(anchor, dict):
        raise LedgerError("ancora invalida: nao e objeto")
    return anchor


def verify_legacy(ledger_path, anchor_path=None, require_anchor=True):
    """Verifica cadeia e coerencia com a ancora. Retorna (ok, detalhes).
    require_anchor=True (padrao): ledger NAO VAZIO sem ancora e recusado
    (P1: delecao da ancora nao burla a deteccao de rollback). Ledgers
    legados exigem adocao explicita via adopt_anchor."""
    if anchor_path is None:
        anchor_path = default_anchor_path(ledger_path)
    try:
        entries = _read_entries(ledger_path)
    except LedgerError as e:
        return False, {"error": str(e)}
    prev_hash = GENESIS_HASH
    hash_by_seq = {}
    for expected_seq, obj in enumerate(entries):
        if not isinstance(obj, dict):
            return False, {"error": "entrada nao e objeto", "seq": expected_seq}
        work = dict(obj)
        claimed = work.pop("hash", None)
        if claimed is None:
            return False, {"error": "entrada sem hash", "seq": work.get("seq")}
        seq = work.get("seq")
        if type(seq) is not int or seq != expected_seq:
            return False, {"error": "seq nao monotonico",
                           "seq": seq, "expected_seq": expected_seq}
        if work.get("prev_hash") != prev_hash:
            return False, {"error": "quebra de cadeia (prev_hash)", "seq": work.get("seq")}
        if _entry_hash(work) != claimed:
            return False, {"error": "hash adulterado", "seq": work.get("seq")}
        if work.get("external_action_allowed") != 0:
            return False, {"error": "invariante fail-closed violada", "seq": work.get("seq")}
        hash_by_seq[work.get("seq")] = claimed
        prev_hash = claimed
    try:
        anchor = _read_anchor(anchor_path)
    except LedgerError as e:
        return False, {"error": str(e)}
    if anchor is None and entries and require_anchor:
        return False, {"error": "ledger nao vazio sem ancora "
                                "(delecao da ancora ou ledger legado sem adocao)",
                       "entries": len(entries)}
    if anchor is not None:
        aseq = anchor.get("seq")
        ahash = anchor.get("hash")
        if anchor.get("schema") not in KNOWN_ANCHOR_SCHEMAS:
            return False, {"error": "ancora com schema desconhecido: "
                                    + str(anchor.get("schema"))}
        if type(aseq) is not int or not (isinstance(ahash, str) and ahash):
            return False, {"error": "ancora invalida: campos seq/hash"}
        if aseq not in hash_by_seq:
            return False, {"error": "ledger truncado abaixo da ancora (rollback)",
                           "anchor_seq": aseq, "entries": len(entries)}
        if hash_by_seq[aseq] != ahash:
            return False, {"error": "ledger divergente da ancora (rollback ou tamper)",
                           "anchor_seq": aseq}
        head_seq = len(entries) - 1
        if head_seq - aseq > MAX_ANCHOR_LAG:
            return False, {"error": "ancora atrasada demais",
                           "anchor_seq": aseq, "head_seq": head_seq,
                           "max_lag": MAX_ANCHOR_LAG}
    return True, {"entries": len(entries), "head_hash": prev_hash,
                  "anchored": anchor is not None}
