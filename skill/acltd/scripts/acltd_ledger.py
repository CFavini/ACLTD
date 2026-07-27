# -*- coding: ascii -*-
"""ACLTD Ledger v1.4.4 - append-only JSONL com cadeia SHA-256 e ancora monotonica.

Correcoes v1.1 (achados adversariais A1/A2):
- A1: append verifica a cadeia INTEIRA antes de anexar (fail-closed).
- A2: ancora monotonica (seq, hash) em arquivo separado, atualizada
  atomicamente a cada append. Truncamento/rollback do ledger abaixo da
  ancora e detectado. LIMITE DECLARADO: rollback coordenado de ledger +
  checkpoint + ancora permanece indetectavel localmente; a ancora deve
  residir em volume distinto e o head_hash deve ser registrado
  externamente (relatorio a Favini) em marcos importantes.
Correcoes v1.2:
- ancora corrompida falha fechado sem excecao crua.
- seq deve ser inteiro monotonicamente crescente (0..n); ledger
  hash-coerente mas estruturalmente impossivel e recusado.
Correcoes v1.3 (achados P1 + fuzzing):
- ANCORA OBRIGATORIA: ledger nao vazio sem ancora e recusado (delecao da
  ancora deixa de burlar a deteccao de rollback). Ledgers legados exigem
  adocao explicita via adopt_anchor (ordem de Favini), nunca implicita.
- leitura endurecida: bytes nao-ASCII ou I/O invalido no ledger viram
  LedgerError fail-closed, nunca excecao crua.
Correcoes v1.4.1 (achados G1-G5, fechamento byte-exato):
- ARQUIVO byte-exato: nada de strip; linha em branco, espaco no inicio ou
  no fim, ou ausencia de newline final = recusa. O arquivo inteiro deve
  ser exatamente a concatenacao de linhas canonicas + newline.
- Whitelist de schema em entradas do ledger e na ancora; schema
  desconhecido = recusa fail-closed.
Correcoes v1.4.2:
- Ancora pode ficar no maximo 1 seq atras da cabeca. Atraso maior nao e
  estado produzido por queda legitima entre append e escrita da ancora.
- Escrita de texto fixa newline LF para portabilidade Windows/NTFS.
- kind e payload seguem contrato: kind em whitelist; payload deve ser objeto.
Correcoes v1.4.3:
- Smoke test portavel em Windows/Git Bash e provedores tencent/nous
  explicitamente reconhecidos pelo pacote de contexto.
Correcoes v1.4.4:
- Saneamento de metadados publicos do pacote, sem mudanca de schema.
Correcoes v1.4 (achados F1-F5, correcao DE CLASSE):
- DISCIPLINA DE LINHA CANONICA: cada linha do ledger deve ser IDENTICA,
  byte a byte, a canonizacao do objeto que ela declara. Isso fecha de uma
  vez a classe inteira raw-vs-parseado: chaves duplicadas, formatacao
  alternativa, conteudo bruto oculto e qualquer normalizacao do parser.
- JSON ESTRITO em toda leitura: chaves duplicadas recusadas
  (object_pairs_hook), constantes NaN/Infinity recusadas (parse_constant).
- JSON ESTRITO em toda escrita: allow_nan=False; payload nao serializavel
  ou com valores nao finitos vira LedgerError, nunca TypeError cru.

Invariantes: external_action_allowed=0; append-only; ASCII-safe (PS 5.1).
"""
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


def _write_anchor(anchor_path, seq, head_hash):
    tmp = anchor_path + ".tmp"
    with open(tmp, "w", encoding="ascii", newline="\n") as f:
        json.dump({"schema": "acltd-anchor-1.4", "seq": seq, "hash": head_hash},
                  f, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, anchor_path)


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


def verify_chain(ledger_path, anchor_path=None, require_anchor=True):
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


def append_entry(ledger_path, kind, payload, agent="unknown", anchor_path=None):
    """Anexa entrada. Fail-closed: recusa se a cadeia ou a ancora estiverem
    invalidas (LedgerError). Atualiza a ancora atomicamente apos o append."""
    if anchor_path is None:
        anchor_path = default_anchor_path(ledger_path)
    if kind not in KNOWN_KINDS:
        raise LedgerError("append recusado: kind desconhecido: " + str(kind))
    if not isinstance(payload, dict):
        raise LedgerError("append recusado: payload deve ser objeto")
    ok, det = verify_chain(ledger_path, anchor_path)
    if not ok:
        raise LedgerError("append recusado, ledger invalido: " + str(det))
    entries = _read_entries(ledger_path)
    if entries:
        prev_hash = entries[-1]["hash"]
        seq = entries[-1]["seq"] + 1
    else:
        prev_hash = GENESIS_HASH
        seq = 0
    entry = {
        "schema": SCHEMA_VERSION,
        "seq": seq,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "agent": agent,
        "kind": kind,
        "payload": payload,
        "external_action_allowed": 0,
        "prev_hash": prev_hash,
    }
    entry["hash"] = _entry_hash(entry)
    with open(ledger_path, "a", encoding="ascii", newline="\n") as f:
        f.write(_canon(entry) + "\n")
        f.flush()
        os.fsync(f.fileno())
    _write_anchor(anchor_path, seq, entry["hash"])
    return entry


def adopt_anchor(ledger_path, anchor_path=None):
    """Adocao EXPLICITA de ancora para ledger legado (pre-v1.1) sem ancora.
    So deve ser executada sob ordem de Favini, apos auditoria da cadeia.
    Fail-closed: recusa se a cadeia for invalida ou se ja houver ancora
    divergente. Idempotente se a ancora atual ja apontar para a cabeca."""
    if anchor_path is None:
        anchor_path = default_anchor_path(ledger_path)
    ok, det = verify_chain(ledger_path, anchor_path, require_anchor=False)
    if not ok:
        raise LedgerError("adocao recusada, cadeia invalida: " + str(det))
    entries = _read_entries(ledger_path)
    if not entries:
        raise LedgerError("adocao recusada: ledger vazio, nada a ancorar")
    head = entries[-1]
    existing = _read_anchor(anchor_path)
    if existing is not None:
        if existing.get("seq") == head["seq"] and existing.get("hash") == head["hash"]:
            return {"ok": True, "adopted": False, "seq": head["seq"],
                    "note": "ancora ja presente e coerente"}
        raise LedgerError("adocao recusada: ancora existente divergente")
    _write_anchor(anchor_path, head["seq"], head["hash"])
    return {"ok": True, "adopted": True, "seq": head["seq"], "hash": head["hash"]}


def last_entries_of_kind(ledger_path, kind):
    """Retorna todas as entradas do tipo, em ordem."""
    return [e for e in _read_entries(ledger_path) if e.get("kind") == kind]


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "verify":
        ap = sys.argv[3] if len(sys.argv) > 3 else None
        ok, det = verify_chain(sys.argv[2], ap)
        print(json.dumps({"ok": ok, "source": "acltd_ledger",
                          "external_action_allowed": False,
                          "requires_favini": False, "data": det}))
        sys.exit(0 if ok else 1)
    if len(sys.argv) >= 3 and sys.argv[1] == "adopt":
        ap = sys.argv[3] if len(sys.argv) > 3 else None
        try:
            out = adopt_anchor(sys.argv[2], ap)
            print(json.dumps({"ok": True, "source": "acltd_ledger",
                              "external_action_allowed": False,
                              "requires_favini": True, "data": out}))
            sys.exit(0)
        except LedgerError as e:
            print(json.dumps({"ok": False, "source": "acltd_ledger",
                              "external_action_allowed": False,
                              "requires_favini": True, "data": {"error": str(e)}}))
            sys.exit(1)
    print("uso: python acltd_ledger.py verify|adopt <ledger.jsonl> [ancora]")
    sys.exit(2)
