# -*- coding: ascii -*-
"""ACLTD Context Pack v1.4.3 - reconstrucao de contexto agnostica de provedor.

Objetivo: apos reboot ou troca de API (LM Studio, Ollama, Claude API, OpenAI),
reconstruir um prompt de retomada IDENTICO em conteudo, apenas adaptado ao
formato de mensagens de cada provedor. Tencent/Nous sao tratados como
envelope OpenAI-like quando usados por gateways compativeis.

Regras anti-alucinacao:
- Todo fato injetado vem do checkpoint (fonte auditavel), nunca de memoria do modelo.
- Fatos possuem origem (source) e seq do ledger quando aplicavel.
- Lacunas sao declaradas explicitamente na secao GAPS (protocolo Arconte Supremo).
- Compactacao preserva SEMPRE pinned_facts; corta apenas last_turns antigos.
"""
import json

from acltd_checkpoint import validate_state, CheckpointError
from acltd_ledger import ACLTD_VERSION

ALLOWED_PROVIDERS = ["anthropic", "openai", "lmstudio", "ollama",
                     "tencent", "nous"]


def estimate_tokens(text):
    # heuristica conservadora: 1 token ~ 3.5 chars em pt-BR/ASCII
    return int(len(text) / 3.5) + 1


def build_resume_text(state, token_budget=4000):
    """Monta o texto canonico de retomada dentro do orcamento de tokens.
    FUNCAO TOTAL v1.4: valida o estado ANTES de montar (mesma validacao do
    checkpoint, incluindo roles restritos a user/assistant); qualquer
    estado malformado retorna (None, {"error": ...}), nunca excecao crua."""
    try:
        validate_state(state)
    except CheckpointError as e:
        return None, {"error": str(e)}
    try:
        return _build_resume_text_inner(state, token_budget)
    except Exception as e:
        return None, {"error": "falha interna na montagem: " + repr(e)}


def _build_resume_text_inner(state, token_budget):
    if not isinstance(state, dict):
        return None, {"error": "estado invalido: estado nao e objeto"}
    for key in ("pinned_facts", "last_turns", "open_questions", "gaps"):
        if not isinstance(state.get(key, []), list):
            return None, {"error": "estado invalido: " + key + " deve ser lista"}
    for i, fact in enumerate(state.get("pinned_facts", [])):
        if not isinstance(fact, dict):
            return None, {"error": "estado invalido: pinned_facts[%d]" % i}
        if not isinstance(fact.get("text"), str):
            return None, {"error": "estado invalido: pinned_facts[%d].text" % i}
        if not isinstance(fact.get("source"), str):
            return None, {"error": "estado invalido: pinned_facts[%d].source" % i}
    for i, turn in enumerate(state.get("last_turns", [])):
        if not isinstance(turn, dict):
            return None, {"error": "estado invalido: last_turns[%d]" % i}
        if not isinstance(turn.get("role"), str) or not isinstance(turn.get("text"), str):
            return None, {"error": "estado invalido: last_turns[%d]" % i}
    header = [
        "=== ACLTD RESUME v" + ACLTD_VERSION + " ===",
        "MISSAO: " + state.get("mission_id", "desconhecida"),
        "PROTOCOLO: fail-closed; external_action_allowed=0; nada aprovado sem Favini.",
        "",
        "[FATOS FIXOS - NAO CONTESTAR SEM EVIDENCIA]",
    ]
    for fact in state.get("pinned_facts", []):
        src = fact.get("source", "sem-fonte")
        header.append("- " + fact["text"] + " (fonte: " + src + ")")
    header.append("")
    header.append("[RESUMO ACUMULADO]")
    header.append(state.get("rolling_summary", "(vazio)"))
    header.append("")
    header.append("[QUESTOES ABERTAS]")
    for q in state.get("open_questions", []):
        header.append("- " + q)
    header.append("")
    header.append("[GAPS DECLARADOS]")
    gaps = state.get("gaps", [])
    if not gaps:
        header.append("- nenhum gap declarado")
    for g in gaps:
        header.append("- " + g)
    base_text = "\n".join(header)
    base_cost = estimate_tokens(base_text)
    remaining = token_budget - base_cost
    if remaining < 0:
        # fatos fixos nunca sao cortados; orcamento insuficiente e erro declarado
        return None, {"error": "orcamento insuficiente para fatos fixos",
                      "base_cost": base_cost, "budget": token_budget}
    turns_lines = ["", "[ULTIMOS TURNOS (mais recentes por ultimo)]"]
    kept = []
    for turn in reversed(state.get("last_turns", [])):
        line = turn["role"] + ": " + turn["text"]
        cost = estimate_tokens(line)
        if remaining - cost < 0:
            break
        kept.append(line)
        remaining -= cost
    turns_lines.extend(reversed(kept))
    full = base_text + "\n" + "\n".join(turns_lines)
    return full, {"tokens_est": estimate_tokens(full),
                  "turns_kept": len(kept),
                  "turns_total": len(state.get("last_turns", []))}


def to_provider_messages(resume_text, provider):
    """Adapta o texto canonico ao formato do provedor. Conteudo identico."""
    if provider not in ALLOWED_PROVIDERS:
        return None
    if provider in ("anthropic",):
        return {"system": resume_text,
                "messages": [{"role": "user",
                              "content": "Confirme a retomada listando missao, fatos fixos e gaps."}]}
    if provider in ("openai", "lmstudio", "ollama", "tencent", "nous"):
        return {"messages": [
            {"role": "system", "content": resume_text},
            {"role": "user",
             "content": "Confirme a retomada listando missao, fatos fixos e gaps."}]}
    return None


def canonical_content(pack):
    """Extrai o conteudo do sistema independente do formato, para comparacao."""
    if "system" in pack:
        return pack["system"]
    for m in pack["messages"]:
        if m["role"] == "system":
            return m["content"]
    return None


if __name__ == "__main__":
    print(json.dumps({"ok": True, "source": "acltd_context_pack",
                      "external_action_allowed": False,
                      "requires_favini": False,
                      "data": {"providers": ALLOWED_PROVIDERS}}))
