---
name: acltd
description: ACLTD (Agent Command Long Term Duration) - protocolo de sessao de longa duracao para agentes Hermes/Aitherion. Use SEMPRE que uma tarefa atravessar multiplos turnos, sessoes, reboots ou trocas de provedor de IA (LM Studio, Ollama, Claude API, OpenAI, Tencent/Nous), ou quando o usuario mencionar continuidade, retomada de contexto, checkpoint, sessao longa, perda de contexto ou resiliencia de agente. Garante persistencia em disco (JSONL + checkpoint atomico), cadeia de hash anti-adulteracao, retomada identica pos-reboot e contexto agnostico de provedor, com fatos ancorados em fonte para suprimir alucinacao.
---

# ACLTD - Agent Command Long Term Duration

Versao auditada: v1.4.3.

Protocolo fail-closed de continuidade de sessao para os agentes do Hermes.
Toda memoria vive em DISCO (nunca apenas em RAM): reboot dissolve estado em
memoria, mas o ACLTD reconstroi a sessao byte a byte a partir do ledger.

## Invariantes (nao negociaveis)

1. external_action_allowed = 0 em toda entrada do ledger.
2. Ledger e append-only com cadeia SHA-256 (prev_hash). Nunca reescrever.
   O append verifica a cadeia INTEIRA e a ancora antes de anexar; ledger
   invalido = LedgerError, nunca continuar sobre base adulterada.
3. Ancora monotonica (<ledger>.anchor): registra (seq, hash) do topo a cada
   append, atomicamente. Pode ficar no maximo 1 seq atras da cabeca apos
   queda entre append e escrita da ancora. Truncamento/rollback abaixo da
   ancora e recusado.
   ANCORA E OBRIGATORIA: ledger nao vazio sem ancora = recusa (delecao da
   ancora nao burla a deteccao). Ledger legado exige adopt_anchor explicito
   sob ordem de Favini.
4. Checkpoint em DUAS FASES: intent no ledger -> escrita atomica do arquivo
   (.tmp + rename) -> commit no ledger. Queda em qualquer janela e
   recuperavel; a restauracao reconcilia intent/commit e declara o reparo.
5. Fatos fixos (pinned_facts) exigem "text" e "source" nao vazios; estado
   com fato sem fonte auditavel e RECUSADO na gravacao e na restauracao.
   Fatos nunca sao cortados na compactacao; orcamento insuficiente = erro.
6. Turnos em last_turns aceitam SOMENTE roles user e assistant; role
   system/tool em transcript e canal de injecao e e recusado.
7. Lacunas vao na secao GAPS do resume (protocolo Arconte Supremo).
8. SQLite do Hermes nao e tocado. ACLTD usa arquivos proprios em
   reports/aitherion/acltd/ (mesmo padrao dos 7 ledgers existentes,
   gitignored junto com eles).
9. Nada e considerado concluido sem aprovacao explicita de Favini
   (requires_favini=true nos envelopes de resultado).

## Fluxo operacional

### A cada turno significativo
1. `append_entry(ledger, "turn", {...})` - registrar decisao/fato novo.
2. Se surgiu fato critico (porta, caminho, decisao de Favini):
   promover a pinned_fact com source = "ledger:seqN".

### A cada N turnos ou antes de operacao arriscada
3. `write_checkpoint(state_dir, state, ledger)` - snapshot atomico.
   Estado minimo: mission_id, pinned_facts, rolling_summary, last_turns,
   open_questions, gaps, provider.

### Ao retomar (pos-reboot ou troca de API)
4. `restore_checkpoint(state_dir, ledger)` - se ok=false, PARAR e reportar.
5. `build_resume_text(state, token_budget)` - texto canonico de retomada.
6. `to_provider_messages(text, provider)` - adaptar ao formato do provedor
  (anthropic / openai / lmstudio / ollama / tencent / nous). O CONTEUDO e
  identico; so o envelope muda.
7. Primeira mensagem pos-retomada: o agente deve CONFIRMAR missao, fatos
   fixos e gaps antes de agir. Se a confirmacao contradisser um pinned_fact,
   tratar como alucinacao e reancorar no ledger.

## Anti-alucinacao (mecanismo)

- O modelo nunca e fonte de estado: o disco e. Todo fato injetado no
  contexto tem origem auditavel (ledger:seqN, protocolo, ou Favini).
- Afirmacoes do agente que nao constam no ledger sao tratadas como
  hipoteses ate registro; agentes nao sao autoritativos por padrao.
- verify_chain roda no restore; qualquer adulteracao interrompe a sessao.

## Scripts (executar de scripts/)

- `acltd_ledger.py` - append_entry, verify_chain. CLI: verify <ledger>
- `acltd_checkpoint.py` - write_checkpoint, restore_checkpoint.
  CLI: restore <state_dir> <ledger>
- `acltd_context_pack.py` - build_resume_text, to_provider_messages.
- `acltd_selftest.py` - bateria completa, inclui fuzzing e
  guarda anti-deriva documental). Rodar apos qualquer alteracao
  e ANTES de qualquer deploy. Exit 0 = aprovado.
- `acltd_campaign.py` - campanha estendida reprodutivel de corrupcao,
  queda, reboot e estresse; atualiza references/campaign_results.json.

Todos os scripts sao ASCII puro (seguros para PowerShell 5.1 / Windows-1252)
e retornam o envelope padrao {ok, source, external_action_allowed,
requires_favini, data}.

## Integracao Hermes (mapa de caminhos sugerido)

- Ledger:      reports/aitherion/acltd/acltd_ledger.jsonl
- Checkpoints: reports/aitherion/acltd/state/checkpoint.json
- Scripts:     app/local_office/acltd/ (entregues via disco para Codex Local)

## Limites conhecidos (declarados)

- A supressao de alucinacao e por ANCORAGEM (fatos com fonte + confirmacao
  obrigatoria), nao por garantia matematica sobre o modelo. Nenhum protocolo
  elimina alucinacao do LLM em si; o ACLTD a detecta e corrige por auditoria.
- Rollback coordenado de ledger + checkpoint + ANCORA simultaneamente e
  indetectavel localmente. Mitigacao: manter a ancora em volume distinto e
  registrar o head_hash externamente (relatorio a Favini) em marcos.
- Custo do append: verificacao integral pre-append e O(n) por entrada
  (~16s acumulados por 1000 entradas em sandbox). Mitigacao futura:
  rotacao de ledger por missao.
- A estimativa de tokens e heuristica (1 token ~ 3.5 chars); calibrar por
  provedor se o orcamento for critico.
- Concorrencia: um escritor por ledger. Multiplos agentes escrevendo no
  mesmo arquivo exigem lock (fora do escopo v1.4).
- Contrato do ledger: `kind` deve estar na whitelist do protocolo e
  `payload` deve ser objeto JSON. Entradas fora desse contrato sao recusadas.
- Provedores `tencent` e `nous` usam envelope OpenAI-like. Se outro gateway
  exigir formato proprio, adicionar provedor novo como patch explicito.
- Durabilidade extrema: `os.replace` fornece troca atomica local quando
  bem-sucedido, mas queda de energia no nivel do filesystem ainda deve ser
  validada no alvo Windows/NTFS antes de producao.

Detalhes completos do protocolo: references/PROTOCOLO_ACLTD.md
