# -*- coding: ascii -*-
"""ACLTD Checkpoint v1.4.3 - snapshot atomico com commit em duas fases.

Correcoes v1.1 (achados adversariais A3/A4):
- A3: validacao de estado. pinned_fact sem 'source' ou sem 'text' nao
  vazios e recusado (fail-closed). Fonte deve ser auditavel.
- A4: protocolo em duas fases no ledger:
    1) intent  (hash do novo estado)  -> registrado ANTES do arquivo
    2) escrita atomica do checkpoint.json (tmp + replace)
    3) commit  (mesmo hash)           -> registrado DEPOIS do arquivo
  Queda entre quaisquer fases e recuperavel:
    - arquivo bate com ultimo COMMIT................. restauracao normal
    - arquivo bate com ultimo INTENT sem commit...... valido (o hash foi
      registrado no ledger tamper-evident antes da queda); restauracao
      repara anexando o commit + nota de reparo
    - arquivo bate com commit ANTERIOR e ha intent
      posterior sem arquivo........................... queda antes do
      replace; restaura o estado anterior valido e declara gap
    - qualquer outro caso............................ recusa (rollback)
Correcoes v1.2:
- validate_state cobre shape completo do estado, turnos, listas e provider.
- restore_checkpoint revalida o estado restaurado antes de aceitar o hash.
Correcoes v1.3 (achado P4 + fuzzing):
- roles de last_turns restritos a {user, assistant}: role "system" ou
  "tool" em transcript checkpointado e canal de prompt injection e passa
  a ser RECUSADO. LIMITE DECLARADO: injecao via CONTEUDO textual de um
  turno e inerente a qualquer transcript; mitigada pela moldura do resume
  (secao rotulada, fatos fixos prevalecem) e pela confirmacao obrigatoria.
- restore endurecido como funcao total: qualquer entrada malformada
  retorna dict fail-closed, nunca excecao crua.
Correcoes v1.4.1 (achado G4):
- schema do envelope validado contra whitelist; schema desconhecido =
  recusa fail-closed no restore.
Correcoes v1.4.2:
- escrita de texto fixa newline LF para portabilidade Windows/NTFS.
Correcoes v1.4.3:
- provedores tencent/nous aceitos explicitamente para o runtime atual do
  Arconte quando usados como envelope OpenAI-like.
Correcoes v1.4 (achados F3/F5 + JSON estrito):
- escrita com allow_nan=False: estado com NaN/Infinity ou tipos nao
  serializaveis vira CheckpointError, nunca grava JSON fora do padrao.
- leitura do envelope com strict_loads (chaves duplicadas e constantes
  proibidas recusadas).
"""
import json
import hashlib
import os
import sys
import time

from acltd_ledger import (append_entry, verify_chain, last_entries_of_kind,
                          default_anchor_path, LedgerError, strict_loads)


class CheckpointError(Exception):
    """Falha fail-closed do checkpoint."""


def _sha256_text(text):
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _state_body(state):
    """Corpo canonico do estado. NaN/Infinity ou tipos nao serializaveis
    viram CheckpointError fail-closed."""
    try:
        return json.dumps(state, sort_keys=True, ensure_ascii=True,
                          indent=1, allow_nan=False)
    except (TypeError, ValueError) as e:
        raise CheckpointError("estado nao serializavel: " + str(e))


KNOWN_CKPT_SCHEMAS = ("acltd-ckpt-1.0", "acltd-ckpt-1.1", "acltd-ckpt-1.2",
                      "acltd-ckpt-1.3", "acltd-ckpt-1.4")

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
    if problems:
        raise CheckpointError("estado invalido: " + "; ".join(problems))


def write_checkpoint(state_dir, state, ledger_path, agent="unknown",
                     anchor_path=None):
    """Grava checkpoint com validacao + duas fases (intent/commit)."""
    validate_state(state)
    if anchor_path is None:
        anchor_path = default_anchor_path(ledger_path)
    os.makedirs(state_dir, exist_ok=True)
    body = _state_body(state)
    digest = _sha256_text(body)
    # fase 1: intent no ledger (tamper-evident) ANTES do arquivo
    append_entry(ledger_path, "checkpoint_intent",
                 {"state_sha256": digest}, agent=agent, anchor_path=anchor_path)
    # fase 2: escrita atomica do arquivo
    envelope = {
        "schema": "acltd-ckpt-1.4",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "state_sha256": digest,
        "state": state,
    }
    final_path = os.path.join(state_dir, "checkpoint.json")
    tmp_path = final_path + ".tmp"
    with open(tmp_path, "w", encoding="ascii", newline="\n") as f:
        f.write(json.dumps(envelope, sort_keys=True, ensure_ascii=True,
                           indent=1, allow_nan=False))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, final_path)
    # fase 3: commit no ledger
    append_entry(ledger_path, "checkpoint_commit",
                 {"state_sha256": digest}, agent=agent, anchor_path=anchor_path)
    return {"ok": True, "state_sha256": digest, "path": final_path}


def restore_checkpoint(state_dir, ledger_path, anchor_path=None, repair=True):
    """Restaura com verificacao de cadeia + ancora + reconciliacao de fases."""
    if anchor_path is None:
        anchor_path = default_anchor_path(ledger_path)
    final_path = os.path.join(state_dir, "checkpoint.json")
    if not os.path.exists(final_path):
        return {"ok": False, "error": "checkpoint inexistente", "fail_closed": True}
    try:
        with open(final_path, "rb") as f:
            envelope = strict_loads(f.read().decode("ascii"))
    except (IOError, OSError, ValueError) as e:
        return {"ok": False, "error": "checkpoint invalido: " + str(e),
                "fail_closed": True}
    if not isinstance(envelope, dict) or "state" not in envelope:
        return {"ok": False, "error": "checkpoint invalido: envelope",
                "fail_closed": True}
    if envelope.get("schema") not in KNOWN_CKPT_SCHEMAS:
        return {"ok": False, "error": "checkpoint com schema desconhecido: "
                                      + str(envelope.get("schema")),
                "fail_closed": True}
    try:
        validate_state(envelope["state"])
    except CheckpointError as e:
        return {"ok": False, "error": str(e), "fail_closed": True}
    try:
        body = _state_body(envelope["state"])
    except CheckpointError as e:
        return {"ok": False, "error": str(e), "fail_closed": True}
    file_hash = _sha256_text(body)
    if file_hash != envelope.get("state_sha256"):
        return {"ok": False, "error": "checkpoint corrompido (hash interno)",
                "fail_closed": True}
    ok, det = verify_chain(ledger_path, anchor_path)
    if not ok:
        return {"ok": False, "error": "ledger invalido: " + str(det),
                "fail_closed": True}
    try:
        intents = last_entries_of_kind(ledger_path, "checkpoint_intent")
        commits = last_entries_of_kind(ledger_path, "checkpoint_commit")
        # compat v1.0: entradas antigas kind=checkpoint contam como commit
        commits += last_entries_of_kind(ledger_path, "checkpoint")
    except LedgerError as e:
        return {"ok": False, "error": "ledger invalido: " + str(e),
                "fail_closed": True}
    for group in (intents, commits):
        for e in group:
            pl = e.get("payload")
            if not (isinstance(pl, dict) and
                    isinstance(pl.get("state_sha256"), str)):
                return {"ok": False,
                        "error": "entrada de checkpoint malformada no ledger",
                        "fail_closed": True}
    commits.sort(key=lambda e: e["seq"])
    last_intent = intents[-1]["payload"]["state_sha256"] if intents else None
    last_intent_seq = intents[-1]["seq"] if intents else -1
    last_commit = commits[-1]["payload"]["state_sha256"] if commits else None
    last_commit_seq = commits[-1]["seq"] if commits else -1
    committed_hashes = [c["payload"]["state_sha256"] for c in commits]

    note = None
    if last_commit is not None and file_hash == last_commit:
        # caso normal; mas se ha intent MAIS NOVO sem arquivo correspondente,
        # um checkpoint pretendido foi perdido antes da escrita -> declarar gap
        if (last_intent is not None and last_intent_seq > last_commit_seq
                and last_intent != last_commit):
            note = ("recuperado: queda antes da escrita do novo checkpoint; "
                    "restaurado ultimo estado commitado; gap declarado "
                    "(intent seq %d perdido)" % last_intent_seq)
    elif last_intent is not None and file_hash == last_intent:
        # queda entre fase 2 e 3: arquivo valido, commit ausente -> reparo
        note = "recuperado: queda entre checkpoint e commit; commit reparado"
        if repair:
            try:
                append_entry(ledger_path, "checkpoint_commit",
                             {"state_sha256": file_hash, "repair": 1},
                             agent="acltd_restore", anchor_path=anchor_path)
            except LedgerError as e:
                return {"ok": False, "error": "reparo falhou: " + str(e),
                        "fail_closed": True}
    elif (last_intent is not None and last_commit is not None
          and file_hash == last_commit and last_intent != last_commit):
        note = "recuperado: intent sem arquivo; estado anterior valido"
    elif (last_intent is not None and file_hash in committed_hashes
          and last_intent not in committed_hashes):
        # queda entre fase 1 e 2: arquivo ainda e um commit anterior valido
        note = ("recuperado: queda antes da escrita do novo checkpoint; "
                "restaurado ultimo estado commitado; gap declarado")
    else:
        return {"ok": False,
                "error": "checkpoint nao corresponde a intent/commit do ledger "
                         "(possivel rollback)",
                "fail_closed": True}
    out = {"ok": True, "state": envelope["state"], "state_sha256": file_hash}
    if note:
        out["recovery_note"] = note
    return out


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "restore":
        ap = sys.argv[4] if len(sys.argv) > 4 else None
        out = restore_checkpoint(sys.argv[2], sys.argv[3], ap)
        print(json.dumps({"ok": out.get("ok", False), "source": "acltd_checkpoint",
                          "external_action_allowed": False,
                          "requires_favini": False, "data": out}))
        sys.exit(0 if out.get("ok") else 1)
    print("uso: python acltd_checkpoint.py restore <state_dir> <ledger> [ancora]")
    sys.exit(2)
