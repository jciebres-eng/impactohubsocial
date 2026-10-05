# Relatório final de endurecimento pré-design — v0.15.0

**Escopo deste ciclo:** fechar o núcleo do produto antes de a designer entrar, para que ela não desenhe sobre uma
base que ainda muda de estrutura. Nada de design foi feito aqui, de propósito.

## 1. Veredito

**🟢 GREEN com dois amarelos declarados e três vermelhos que não são de engenharia interna.**

| Camada | Veredito |
|---|---|
| Banco, integridade e caminho de atualização | 🟢 |
| Núcleo do produto (6 motores) | 🟢 |
| API (625 operações) | 🟢 |
| Segurança da aplicação | 🟢 |
| Frontend funcional | 🟢 |
| Chaves e cifragem | 🟡 KMS/HSM não existe, e está declarado |
| Desempenho | 🟡 feed do financiador a 1,6 s, limite declarado na resposta |
| Assinatura qualificada e integrações reais | 🟡 `unavailable` / `contract_tested`, recusa explícita |
| Validação de segurança por terceiro | 🔴 nunca houve |
| Camada de design | 🔴 é a próxima etapa |
| Aplicativo nativo | 🔴 não iniciado |

**RED de engenharia interna: 0.**

## 2. Números

| Medida | v0.14.0 | v0.15.0 |
|---|---|---|
| Testes (banco criado do zero em cada execução) | 564 | **671** (0 falhas, 7 pulados) |
| Operações de API | 574 | **625** |
| Tabelas | 191 | **205** |
| Políticas de RLS | — | **408** em 203 tabelas |
| Índices | 460 | **552** |
| Migrações | 12 | **15** |
| Linhas de Python (aplicação) | — | 28.169 em 154 arquivos |
| Linhas de teste | — | 11.851 |
| Linhas de SQL de migração | — | 6.633 |
| Linhas de TypeScript | — | 10.058 |
| Documentos na raiz | 61 | **75** |

Pulados: 7 — a suíte de volume (passo próprio, `PERF=1`) e casos que dependem de recurso ausente no ambiente.

## 3. O que foi auditado ANTES de alterar

O ciclo começou pela auditoria, registrada em `PRE_DESIGN_AUDIT.md`. Três resultados dela merecem destaque:

**(a) Onde o código já era melhor do que o pedido supunha.** O match já tinha elegibilidade antes de pontuação,
pontuação separada de confiança, campos de explicação e versionamento; `ledger_entries` já era append-only
encadeada por hash; indicadores já tinham separação de funções por `CHECK`; o cifrador de campo já era
`MultiFernet` (portanto já suportava rotação). Nada disso foi reescrito.

**(b) Uma duplicação introduzida por nós na v0.14.0.** `sdg_goals` duplicava `ods_goals`, que existe desde a
migração 0001 e é referenciada por `indicator_catalog` e `ods_targets`. Duas fontes de verdade para os ODS. Foi
consolidada: `ods_goals` ganhou as colunas que faltavam, `sdg_goals` foi **removida**, três referências no código
foram corrigidas e o teste de atualização confere que não sobrou referência pendurada.

**(c) 18 lacunas confirmadas (L1–L18)**, que viraram o trabalho deste ciclo.

## 4. O que foi construído

### Vocabulário comum (`core/evidence.py`)
`Evidence` com 9 fontes, `verified` **derivado da fonte** (não dá para marcar declaração como verificada),
frescura com meia-vida por tipo de dado, decaimento que reduz **confiança e não pontuação**, e faixa de confiança
com `insufficient_data` como valor próprio.

### Ciclo de vida (`core/lifecycle.py`)
Máquina de 17 situações e 58 transições **como dado**, com gatilho no banco que recusa o que não está no grafo —
inclusive no contexto privilegiado. Transições append-only com ator e motivo. Linha de tempo reusando a trilha
encadeada. Retratos comparáveis com hash de estado. 8 regras de risco com severidade por matriz publicada.

### Diagnóstico (`core/diagnostic.py`)
20 lacunas em 8 dimensões ponderadas, saída separada em FATO / INFERÊNCIA / RECOMENDAÇÃO / DESCONHECIDO, versões
imutáveis com `what_changed` calculado pelo servidor, lacuna virando ação e ação fechando quando a lacuna fecha.

### Montagem de documento (`core/assembly.py`)
Modelo publicado imutável, campo derivado por **lista fechada** de caminhos de domínio, completude e bloqueio
calculados pelo servidor, recusa explicada ao gerar incompleto, geração para PDF/DOCX/ODT com hash no cofre,
revisão com quatro olhos. Três modelos da plataforma, publicados, cada um com a fonte declarada.

### Chaves (`core/keys.py`)
Inventário por impressão digital de 16 hex (a chave nunca é gravada), estados `active`/`decrypt_only`/`retired`,
recifragem em lote idempotente e auditada, KMS/HSM declarado ausente na API e na interface.

### Match (`match-engine@1.2.0`)
Evidência nos sinais, confiança ajustada por frescura, faixa de confiança, quatro versões viajando com o resultado,
retorno humano registrado **sem treino automático** e base de calibração sem dado pessoal.

### API
51 rotas novas. Frontend funcional com 13 telas novas, sem nenhuma decisão de design.

## 5. Os 23 defeitos encontrados e corrigidos neste ciclo

Encontrados **por teste**, não por leitura. Os que mais importam:

| # | Defeito | Por que importava |
|---|---|---|
| 1 | Lacuna de documento usava a chave `doc.estatuto`, mas o tipo real é `estatuto_social` | a lacuna **nunca fechava**, por mais documento que a organização enviasse |
| 2 | `generated_at` entrava no hash da versão de diagnóstico | "congelar versão" criava versão nova a cada segundo; "o que mudou" era pergunta sobre o relógio |
| 3 | Retorno de match escrevia na trilha do **projeto** | expunha a decisão do financiador no histórico lido pela organização |
| 4 | Orçamento `0` e público `0` contavam como "informado" | `0` não é `None`, mas é ausência de informação |
| 5 | Evidência exigida bloqueava campo **opcional** em branco | bloqueava a geração para sempre, sem a pessoa entender |
| 6 | `build_state` lia `projects.funded_cents`, que não existe | retrato quebrava com erro 500 |
| 7 | Promoção de ideia violava `projects.territory NOT NULL` | ideia sem território não virava projeto |
| 8 | `EnvKeyProvider` não via a chave realmente em uso | inventário mostrava "nenhuma chave" com dado cifrado existindo |
| 9 | Identidade do arquivo (`sha256`, tamanho, tipo, chave) era alterável no contexto privilegiado | hash de documento assinado precisa ser imutável |
| 10 | Campo opcional em branco enviava `""` e o servidor recusava por padrão de formato | a pessoa via "String should match pattern" por ter deixado um campo vazio |
| 11 | Fila administrativa de documentos não era filtrável | a fila cresce e o item procurado sai da página |
| 12 | `archived → monitoring` não exigia motivo | reabrir projeto arquivado é exceção e precisa ser explicada |
| 13 | 92 chaves estrangeiras de caminho de acesso sem índice | varredura de tabela inteira no filtro de inquilino e no `ON DELETE CASCADE` |
| 14 | Feed do financiador a 3.126 ms, com ~10 idas ao banco por candidato | inutilizável em volume |

Os outros nove são do mesmo tipo: erro que só aparece quando alguém executa de verdade.

## 6. Testes acrescentados

| Suíte | Testes | O que prova |
|---|---|---|
| `test_v0150_core.py` | 39 | comportamento de cada capacidade nova, pela API real |
| `test_v0150_invariants.py` | 21 | determinismo, plano não influencia, bloqueio ≠ elegível, declaração ≠ verificada, frescura reduz confiança, hash imutável, idempotência |
| `test_v0150_security.py` | 16 | **varredura automática de todas as rotas de escrita** + matriz A → recurso de B + RLS em SQL direto + fuga por `SECURITY DEFINER` |
| `test_v0150_upgrade.py` | 10 | atualização v0.12.1 → v0.15.0 com dado dentro, e esquema **idêntico** ao criado do zero |
| `test_e2e_v0150_journeys.py` | 8 | as 8 jornadas de ponta a ponta |
| `test_e2e_v0150_web.py` | 6 | navegador real: página limpa, ideia→projeto, bloqueio visível, recusa visível, desconhecido separado, indisponibilidade declarada |
| `test_v0150_performance.py` | 7 | volume de alvo, orçamento de tempo, detector de N+1, `EXPLAIN` sem varredura sequencial |

A varredura de rotas de escrita merece nota: ela percorre o **registro de rotas** e chama cada rota de escrita com
um identificador inexistente. Rota nova que esqueça de conferir a dona do recurso falha no teste **sem que ninguém
precise escrever um teste para ela**.

## 7. O que NÃO foi feito, e por quê

| Item | Motivo |
|---|---|
| Camada de design | é a etapa seguinte; o escopo dizia explicitamente para não fazer |
| Menus horizontais retráteis e grande área de trabalho | pedido do proprietário, mas é reestruturação de navegação = design (registrado em `DESIGN_HANDOFF.md` §12.5) |
| KMS/HSM | depende de infraestrutura contratada; o contrato de provedor está escrito, a implementação não |
| ICP-Brasil, Gov.br, ACT, biometria, SMS | dependem de contratação/credenciamento; recusa explícita no lugar |
| Integração contra sistema real | depende de acesso a instância de cliente ou órgão |
| Teste de intrusão independente | depende de contratação |
| Carregadores em lote para o feed | é a próxima otimização; exige cuidado com `SECURITY DEFINER` e não entra sem matriz de isolamento dedicada |
| Aplicativo nativo | não iniciado; PWA funciona |

## 8. Compatibilidade

Nada que existia quebrou. Verificado por: a suíte inteira anterior continua verde; as transições que o produto já
fazia estão no grafo; o caminho de atualização com dado dentro passa; o esquema atualizado é idêntico ao criado do
zero; e os contratos de API existentes não mudaram — as 51 rotas são **adições**, e as duas renomeações
(`/v1/taxonomy` → `/v1/impact-taxonomy`, `/v1/directory/professionals` mantida e enriquecida) foram feitas na
v0.14.0, não aqui.

## 9. Documentos desta versão

**Novos (16):** `CORE_PRODUCT_ARCHITECTURE.md` · `MATCH_ENGINE_FINAL.md` · `DIAGNOSTIC_ENGINE.md` ·
`PROJECT_LIFECYCLE.md` · `DOCUMENT_ASSEMBLY.md` · `LONGITUDINAL_TRACKING.md` · `KEY_ROTATION.md` ·
`SIGNATURE_VALIDATION_MATRIX.md` · `EXTERNAL_DEPENDENCIES.md` · `HOMOLOGATION_MATRIX.md` ·
`DATA_RETENTION_MATRIX.md` · `DATABASE_INTEGRITY_REPORT.md` · `SECURITY_FINAL_CHECKLIST.md` ·
`PERFORMANCE_REPORT.md` · `RELEASE_READINESS.md` · este relatório.

**Atualizados:** `DESIGN_HANDOFF.md` (seção 13: fluxos A–I e os 20 invariantes de design) · `CHANGELOG.md` ·
`VERSIONING.md` · `DECISIONS.md` · `README.md` · `API_DOCUMENTATION.md` · `DATABASE_SCHEMA.md` ·
`TEST_REPORT.md` · `SECURITY_AUDIT.md` · `LGPD_AUDIT.md` · `PRODUCTION_READINESS.md` ·
`CLAUDE_HANDOFF_FINAL.md`.

**Snapshot da versão anterior:** `history/v0.14.0/` (21 arquivos, incluindo o log de teste do v0.14.0).

**Evidência:** `docs/evidence/test_run_v0.15.0.log` · `ruff_v0.15.0.log` · `perf_v0.15.0.log` ·
`db_integrity_v0.15.0.txt`.

## 10. Frase final

Esta versão fechou o núcleo do produto e, mais importante, **passou a impedir estruturalmente as mentiras que um
produto desse tipo costuma contar**: declaração marcada como verificada, bloqueio compensado por pontuação,
histórico reescrito, assinatura qualificada sem certificado, documento gerado com lacuna, integração dita pronta
sem nunca ter falado com o sistema do cliente. Cada uma dessas tem agora um gatilho, um `CHECK` ou um teste que a
recusa — não uma recomendação na documentação.

O que falta está listado, com nome e motivo, em `RELEASE_READINESS.md` §5.
