# -*- coding: ascii -*-
"""ACLTD 2.0 authenticated two-phase checkpoints; standard library only."""
import hashlib
import json
import os
import sys
import time
from acltd_ledger import (append_entry, verify_chain, default_anchor_path,
    ledger_lock, LedgerError, LedgerBusy, strict_loads, _key, _seal,
    _authenticate, atomic_write, encode_data, decode_data, _read_entries)

RESERVED_MARKERS = ("=== ACLTD", "[FATOS FIXOS", "[GAPS", "[RESUMO",
                    "[QUESTOES", "[ULTIMOS TURNOS")
LINE_BREAKS = "\r\n\v\f\x85\u2028\u2029"
KNOWN_CKPT_SCHEMAS = ("acltd-ckpt-2.0",)


class CheckpointError(Exception):
    """Fail-closed checkpoint error."""


def _state_body(state):
    try:
        return json.dumps(state, sort_keys=True, ensure_ascii=True, indent=1, allow_nan=False)
    except (ValueError, TypeError, OverflowError, RecursionError) as e:
        raise CheckpointError("estado nao serializavel: " + str(e)) from None


def _sha256_text(text):
    return hashlib.sha256(text.encode("ascii")).hexdigest()


REQUIRED_KEYS = ["mission_id", "pinned_facts", "rolling_summary",
                 "last_turns", "open_questions", "gaps", "provider"]
ALLOWED_PROVIDERS = ["anthropic", "openai", "lmstudio", "ollama",
                     "tencent", "nous"]


def validate_state(state):
    """Valida o estado. Levanta CheckpointError com a lista de problemas."""
    problems = []
    if not isinstance(state, dict):
        raise CheckpointError("estado invalido: estado nao e objeto")
    for k in REQUIRED_KEYS:
        if k not in state:
            problems.append("chave obrigatoria ausente: " + k)
    if not (isinstance(state.get("mission_id"), str) and
            state.get("mission_id").strip()):
        problems.append("mission_id invalido")
    if not isinstance(state.get("rolling_summary"), str):
        problems.append("rolling_summary deve ser texto")
    pinned_facts = state.get("pinned_facts", [])
    if not isinstance(pinned_facts, list):
        problems.append("pinned_facts deve ser lista")
        pinned_facts = []
    for i, fact in enumerate(pinned_facts):
        if not isinstance(fact, dict):
            problems.append("pinned_fact[%d] nao e objeto" % i)
            continue
        text = fact.get("text")
        source = fact.get("source")
        if not (isinstance(text, str) and text.strip()):
            problems.append("pinned_fact[%d] sem 'text' valido" % i)
        if not (isinstance(source, str) and source.strip()):
            problems.append("pinned_fact[%d] sem 'source' auditavel" % i)
    last_turns = state.get("last_turns", [])
    if not isinstance(last_turns, list):
        problems.append("last_turns deve ser lista")
        last_turns = []
    for i, turn in enumerate(last_turns):
        if not isinstance(turn, dict):
            problems.append("last_turns[%d] nao e objeto" % i)
            continue
        role = turn.get("role")
        text = turn.get("text")
        if role not in ("user", "assistant"):
            problems.append("last_turns[%d] role invalido "
                            "(permitidos: user, assistant)" % i)
        if not isinstance(text, str):
            problems.append("last_turns[%d] text deve ser texto" % i)
    for key in ("open_questions", "gaps"):
        values = state.get(key, [])
        if not isinstance(values, list):
            problems.append(key + " deve ser lista")
            continue
        for i, value in enumerate(values):
            if not isinstance(value, str):
                problems.append("%s[%d] deve ser texto" % (key, i))
    provider = state.get("provider")
    if not isinstance(provider, dict):
        problems.append("provider deve ser objeto")
    else:
        pname = provider.get("name")
        if pname not in ALLOWED_PROVIDERS:
            problems.append("provider.name invalido: " + str(pname))
    def inspect_text(value):
        if isinstance(value, str):
            upper = value.upper()
            if any(marker in upper for marker in RESERVED_MARKERS):
                problems.append("marcador ACLTD reservado no texto")
        elif isinstance(value, dict):
            for k, v in value.items():
                inspect_text(k)
                inspect_text(v)
        elif isinstance(value, list):
            for v in value:
                inspect_text(v)
    try:
        _state_body(state)
        inspect_text(state)
    except (CheckpointError, RecursionError):
        problems.append("estado nao serializavel ou recursivo")
    single_lines = [state.get("mission_id", "")]
    for fact in pinned_facts:
        if isinstance(fact, dict):
            single_lines.extend([fact.get("text", ""), fact.get("source", "")])
    if isinstance(state.get("gaps"), list):
        single_lines.extend(state["gaps"])
    if any(isinstance(v, str) and any(c in v for c in LINE_BREAKS) for v in single_lines):
        problems.append("missao, fatos fixos, fontes e lacunas devem ter uma linha")
    if problems:
        raise CheckpointError("estado invalido: " + "; ".join(problems))


def write_checkpoint(state_dir, state, ledger_path, agent="unknown", anchor_path=None,
                     *, key=None, encrypt=None, on_head=None, lock_timeout=10.0):
    validate_state(state)
    try:
        key = _key(key)
        stored = encode_data(state, encrypt)
        digest = _sha256_text(_state_body(stored))
        with ledger_lock(ledger_path, lock_timeout):
            os.makedirs(state_dir, exist_ok=True)
            ap = anchor_path or default_anchor_path(ledger_path)
            opts = dict(key=key, encrypt=encrypt, on_head=on_head, anchor_path=ap, agent=agent)
            append_entry(ledger_path, "checkpoint_intent", {"state_sha256": digest}, **opts)
            envelope = _seal({"schema": "acltd-ckpt-2.0",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "state_sha256": digest, "state": stored, "encrypted": encrypt is not None}, key)
            final_path = os.path.join(state_dir, "checkpoint.json")
            atomic_write(final_path, _state_body(envelope).encode("ascii"))
            append_entry(ledger_path, "checkpoint_commit", {"state_sha256": digest}, **opts)
            return {"ok": True, "state_sha256": digest, "path": final_path,
                    "external_action_allowed": 0, "requires_approval": True}
    except LedgerBusy:
        raise
    except (LedgerError, OSError, ValueError, TypeError, RecursionError) as e:
        raise CheckpointError(str(e)) from None


def restore_checkpoint(state_dir, ledger_path, anchor_path=None, repair=True, *,
                       key=None, decrypt=None, encrypt=None, on_head=None,
                       expected_head=None, lock_timeout=10.0):
    """Full verification under transaction lock. Busy is a distinct exception."""
    try:
        key = _key(key)
        with ledger_lock(ledger_path, lock_timeout):
            return _restore(state_dir, ledger_path, anchor_path or default_anchor_path(ledger_path),
                            repair, key, decrypt, encrypt, on_head, expected_head)
    except LedgerBusy:
        raise
    except (LedgerError, CheckpointError, OSError, ValueError, TypeError, RecursionError) as e:
        return {"ok": False, "error": str(e), "fail_closed": True,
                "external_action_allowed": 0}


def _restore(state_dir, ledger_path, ap, repair, key, decrypt, encrypt, on_head, expected_head):
    ok, det = verify_chain(ledger_path, ap, key=key, expected_head=expected_head)
    if not ok:
        raise CheckpointError("ledger invalido: " + str(det))
    with open(os.path.join(state_dir, "checkpoint.json"), "rb") as f:
        envelope = strict_loads(f.read().decode("ascii"))
    if not isinstance(envelope, dict) or envelope.get("schema") not in KNOWN_CKPT_SCHEMAS:
        raise CheckpointError("checkpoint com schema desconhecido")
    _authenticate(envelope, key, "checkpoint")
    if type(envelope.get("encrypted")) is not bool:
        raise CheckpointError("checkpoint encrypted invalido")
    stored = envelope.get("state")
    file_hash = _sha256_text(_state_body(stored))
    if file_hash != envelope.get("state_sha256"):
        raise CheckpointError("checkpoint corrompido (hash interno)")
    state = decode_data(stored, envelope["encrypted"], decrypt)
    validate_state(state)
    intents, commits = [], []
    for obj in _read_entries(ledger_path):
        if obj["kind"] in ("checkpoint_intent", "checkpoint_commit"):
            payload = decode_data(obj["payload"], obj["encrypted"], decrypt)
            if not isinstance(payload, dict) or not isinstance(payload.get("state_sha256"), str):
                raise CheckpointError("entrada de checkpoint malformada no ledger")
            (intents if obj["kind"] == "checkpoint_intent" else commits).append(
                (obj["seq"], payload["state_sha256"]))
    last_intent_seq, last_intent = intents[-1] if intents else (-1, None)
    last_commit_seq, last_commit = commits[-1] if commits else (-1, None)
    pending = last_intent_seq > last_commit_seq
    note = None
    if last_commit is not None and file_hash == last_commit:
        if pending and last_intent != last_commit:
            note = "recuperado: queda antes da escrita; restaurado ultimo estado commitado; gap declarado"
    elif pending and file_hash == last_intent:
        note = "recuperado: queda entre checkpoint e commit"
        if repair:
            # Do not silently downgrade encrypted storage when repairing a phase.
            if envelope["encrypted"] and encrypt is None:
                raise CheckpointError("encrypt obrigatorio para reparar checkpoint cifrado")
            append_entry(ledger_path, "checkpoint_commit", {"state_sha256": file_hash, "repair": 1},
                         agent="acltd_restore", anchor_path=ap, key=key,
                         encrypt=encrypt, on_head=on_head)
            note += "; commit reparado"
        else:
            note += "; commit pendente (repair=False)"
    elif any(digest == file_hash for _, digest in commits):
        raise CheckpointError("checkpoint mais antigo que o \u00faltimo confirmado (poss\u00edvel backup misturado)")
    else:
        raise CheckpointError("checkpoint nao corresponde ao ultimo intent/commit (possivel rollback)")
    out = {"ok": True, "state": state, "state_sha256": file_hash,
           "external_action_allowed": 0, "requires_approval": True}
    if note:
        out["recovery_note"] = note
    return out


if __name__ == "__main__":
    print(json.dumps({"ok": False, "external_action_allowed": 0,
                      "error": "use API com chave bytes/funcao; CLI nao recebe segredos"}))
    sys.exit(2)
