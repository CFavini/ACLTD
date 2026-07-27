# PROTOCOLO ACLTD v1.4 - Referencia Completa

Versao do codigo: 1.4.3. Este documento descreve APENAS a especificacao
vigente. Resultados e achados de rodadas anteriores estao no Apendice A,
que e material historico de auditoria e NAO deve ser seguido como
especificacao.

## 1. Modelo de dados

### Entrada do ledger (JSONL canonico, uma por linha)
{"agent":"...","external_action_allowed":0,"hash":"<sha256>",
 "kind":"turn|fact|decision|gap|note|checkpoint_intent|checkpoint_commit",
 "payload":{...},"prev_hash":"<sha256 anterior ou 64 zeros>",
 "schema":"acltd-1.4","seq":N,"ts":"..."}

Disciplina de arquivo BYTE-EXATA:
- cada linha deve ser IDENTICA, byte a byte, a canonizacao do objeto
  (sort_keys, separadores compactos, ensure_ascii, allow_nan=False);
- proibidos: linha em branco, espaco nas bordas, ausencia de newline
  final, chave duplicada, NaN/Infinity, schema fora da whitelist
  (acltd-1.0 a acltd-1.4);
- kind fora da whitelist e payload nao-objeto sao recusados na escrita e
  na verificacao;
- qualquer violacao = LedgerError fail-closed; append sobre ledger
  invalido e recusado.

### Ancora (<ledger>.anchor, atomica, obrigatoria p/ ledger nao vazio)
{"hash":"<sha256 da cabeca>","schema":"acltd-anchor-1.4","seq":N}
- schema fora da whitelist (acltd-anchor-1.1/1.3/1.4) = recusa;
- ledger nao vazio sem ancora = recusa (delecao nao burla rollback);
- ledger legado exige adopt_anchor EXPLICITO sob ordem de Favini;
- propriedade "piso": ancora pode ficar 1 atras da cabeca apos queda
  entre append e escrita da ancora; aceita e reancorada no proximo append;
- atraso maior que 1 seq e recusado como estado nao produzido por queda
  legitima.

### Checkpoint (checkpoint.json, escrita atomica tmp+replace)
{"schema":"acltd-ckpt-1.4","ts":"...","state_sha256":"<sha256>",
 "state":{mission_id, pinned_facts[{text,source}], rolling_summary,
          last_turns[{role,text}], open_questions[], gaps[],
          provider{name,...}}}
- schema fora da whitelist (acltd-ckpt-1.0 a 1.4) = recusa no restore;
- pinned_facts exigem text E source nao vazios (escrita E restauracao);
- roles permitidos em last_turns: SOMENTE user e assistant;
- provider.name restrito a: anthropic, openai, lmstudio, ollama,
  tencent, nous;
- estado com NaN/Infinity ou nao serializavel = CheckpointError.

## 2. Commit em duas fases e recuperacao de quedas

write_checkpoint: (1) intent no ledger -> (2) arquivo atomico ->
(3) commit no ledger. Restauracao reconcilia:
| Situacao                                  | Comportamento                     |
|-------------------------------------------|-----------------------------------|
| arquivo == ultimo commit                  | restauracao normal                |
| arquivo == ultimo intent, sem commit      | valido; commit reparado + nota    |
| intent orfao mais novo que o commit       | restaura commit; gap declarado    |
| arquivo sem intent/commit correspondente  | recusa (forja/rollback)           |
| queda no meio de qualquer escrita atomica | .tmp abandonado; anterior intacto |

## 3. Ciclo de vida e retomada

INICIO -> append(decision, missao) -> turnos -> checkpoint periodico
-> [reboot/troca de API] -> restore (cadeia+ancora+fases+revalidacao)
-> build_resume_text (funcao total; valida estado; cabecalho traz a
versao do codigo) -> to_provider_messages (conteudo identico; envelope
por provedor; tencent/nous usam formato OpenAI-like) -> CONFIRMACAO
obrigatoria do agente antes de agir.

## 4. Compactacao

Ordem de preservacao: pinned_facts > gaps > open_questions >
rolling_summary > last_turns (somente esta e cortavel, do mais antigo).
Orcamento insuficiente para as secoes fixas = erro declarado.

## 5. Anti-alucinacao

- O disco e a fonte de estado, nunca o modelo.
- Fato sem source auditavel nao entra nem sai de checkpoint.
- Afirmacao do agente ausente do ledger = hipotese ate registro.
- Aprovacao de Favini nunca e presumida.

## 6. Limites residuais declarados

- Rollback coordenado reescrevendo ledger + checkpoint + ANCORA em
  conjunto: indetectavel localmente. Mitigacao: ancora em volume
  distinto + registro externo do head_hash com Favini em marcos.
- Injecao via CONTEUDO textual de turnos: inerente a transcripts;
  mitigada pela moldura do resume, fatos fixos e confirmacao.
- Ledger legado: adopt_anchor atesta a cadeia dali em diante, nao o
  passado pre-adocao.
- Um escritor por ledger (lock multi-agente fora do escopo).
- Custo O(n) por append (verificacao integral); mitigacao: rotacao de
  ledger por missao.
- Validacao Windows/NTFS/PowerShell 5.1 pendente no ambiente de Favini.

## Apendice A - Historico de auditoria (obsoleto como especificacao)

Material de rastreabilidade das rodadas de auditoria cruzada
(Claude <-> IA externa <-> Favini). NAO seguir como especificacao.

- R1 (v1.0->v1.1, achados A1-A5 de Favini): append apos tamper; rollback
  coordenado; fato sem fonte; queda entre checkpoint e ledger; caminho
  fixo. Suite da epoca: 10 -> 17 testes.
- R2 (v1.1->v1.2, IA externa, A6-A10): ancora corrompida com excecao
  crua; seq nao monotonico; shape invalido; restore sem revalidacao;
  provider desconhecido. Suite: 22 testes.
- R3 (v1.2->v1.3, Claude, P1/P4 + fuzzing): delecao da ancora; role
  system em transcript; bytes nao-ASCII; adopt_anchor; ancora como piso.
  Suite: 33 testes.
- R4 (v1.3->v1.4, IA externa, F1-F7): classe raw-vs-parseado (chave
  duplicada, linha nao canonica), NaN em ledger/checkpoint, payload nao
  serializavel, resume nao-total, deriva documental. Suite: 41 testes.
- R5 (v1.4->v1.4.1, IA externa, G1-G7): espacos nas bordas, linhas em
  branco, schemas malignos em checkpoint/ancora, cabecalho do resume
  defasado, protocolo com blocos obsoletos, T38 fraco.
- R6 (v1.4.1->v1.4.2, Codex, H1-H4): ancora atrasada demais, escrita LF
  explicita para Windows, kind fora da whitelist e payload nao-objeto.
- R7 (v1.4.2->v1.4.3, Codex, I1-I2): self-test portavel para Windows/Git
  Bash em T16/T20 e provedores tencent/nous aceitos explicitamente.
