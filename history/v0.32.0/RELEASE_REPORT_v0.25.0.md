# Relatório de release — IMPACTO v0.25.0

**Data:** 08/10/2026 · **Ramo:** `main` · **Tag:** `v0.25.0` · **Pacote:** `IMPACTO_FULL_DEMO_v0.25.0.zip`
(o hash do commit e o SHA-256 do pacote não cabem dentro do próprio commit/pacote; vêm no
`.sha256` ao lado do ZIP e no `git log` da tag).

## 1. Status

```text
RELEASE STATUS: PASS WITH CONDITIONS
```

**PASS** no que é software: banco → API → tela → jornada → resultado está provado por execução, do
banco vazio ao reinício, no ambiente de desenvolvimento e no GitHub. **CONDITIONS**: não há endereço
público (depende de conta de hospedagem do dono do projeto — D-PUB1); leitor de tela real e as 14
integrações de terceiros seguem fora de alcance, como antes.

## 2. Web

```text
URL:                 NÃO HÁ URL PÚBLICA (D-PUB1 — exige conta de hospedagem em nome do dono)
STATUS:              pilha completa provada do zero no CI (job pilha-do-zero), a cada push
ÚLTIMO SMOKE TEST:   job pilha-do-zero da run 37747523510 (commit f17cddc) — sucesso, com a trava do axe
```

Nenhuma URL foi inventada. O que existe e está testado: `infra/compose/demo/compose.yml` sobe a
demonstração em `http://127.0.0.1:8080` em qualquer máquina com Docker; e a mesma imagem já subiu
contra o Supabase real do projeto (run 37727468920, `readyz` 200, v0.24.2).

## 3. Git

```text
BRANCH:  main
COMMIT:  o commit apontado pela tag v0.25.0
TAG:     v0.25.0
STATUS:  limpo no fechamento (conferido antes da tag)
```

## 4. ZIP

```text
ARQUIVO:  IMPACTO_FULL_DEMO_v0.25.0.zip
VERSÃO:   0.25.0
SHA256:   no arquivo IMPACTO_FULL_DEMO_v0.25.0.zip.sha256
ZIP TEST: unzip -t sem erro; conferido byte a byte contra o objeto Git do commit; sem ZIP aninhado
```

## 5. Perfis testados

OSC · Empresa (financiador) · Profissional · Governo · Apoiadora (pessoa física — nova) ·
Administração (com segundo fator e confirmação de identidade reais) · Suporte (equipe) · Visitante
sem login. Contas internas de editora e revisor entram no robô e nas jornadas de preparação, mas
**não** executam jornada editorial própria nesta versão (ver pendências).

Login real no navegador para cada perfil; logout implícito por contexto novo a cada perfil.
Recusa conferida: cada tela restrita é aberta por um perfil que NÃO deve vê-la (92 recusas corretas).

## 6. Jornadas completas testadas (API real, sem escrita direta no banco)

| Jornada | Começa | Termina em resultado verificável |
|---|---|---|
| OSC: projeto → diagnóstico → impacto | projeto novo e publicado | diagnóstico aplicado, versão, prontidão em 8 dimensões, 4 medições em série |
| Financiador | match do edital | candidatura assinada e aprovada, aporte, desembolso, pagamento confirmado, medições VALIDADAS por outra organização |
| Rede | proposta de apoio | proposta aceita, conversa nos dois sentidos, relatório de impacto aceito pelo apoiador |
| Profissional | necessidade publicada | oferta aceita, revisão técnica aprovada com credencial verificada |
| Governo | chamamento público | candidatura avaliada e aprovada pelo governo, necessidade do território com fonte |
| Captação | cota de apoio | cotas apoiadas por empresa e pessoa física, campanha pública aberta sem login |
| Documentos | montagem a partir do projeto | documento gerado, acordo assinado pelas duas partes, registro verificável conferido sem login, compra decidida com 3 orçamentos |
| Marketplace e perfis | anúncio | anúncio e solução publicados, perfis públicos |
| Suporte e Central | chamado | resposta do suporte lida; curso concluído com certificado |
| Banco de Ideias | ideia | ideia amadurecida e transformada em projeto |
| Administração | visão geral | solução classificada, cadeia de auditoria verificada, interruptor lido com confirmação de identidade |
| Pendências | — | proposta aguardando resposta, relatório aguardando análise, afirmações conferidas, experiência e credencial aguardando conferência, denúncia na moderação |

Total: **169 passos em 13 jornadas, 0 falha** (`docs/evidence/jornadas_v0250/relatorio.json`).
Contra a pilha do zero (Supabase-like, Docker), o mesmo roteiro: 0 falha (job `pilha-do-zero`).

## 7. Testes

```text
TOTAL:  2277 (suíte do backend, inclui E2E de navegador)
PASS:   2275 na regressão final completa; as 2 falhas eram de fechamento (mapa tela→API e
        manifesto da versão), corrigidas e reconferidas pelos testes correspondentes
FAIL:   0 após o fechamento — a run do CI do commit da tag é a conferência independente
SKIP:   29 (local; dependem de ambiente — ex.: comparação da árvore npm instalada)
```

Além da suíte: robô das 218 telas e jornadas também rodaram **contra a pilha do zero** no CI, e o
axe-core rodou em cada rota.

**Contagens das provas desta versão** (geradas: `docs/execution/COVERAGE_MATRIX.md`):

| Prova | Resultado |
|---|---|
| Telas do roteador abertas no Chromium com dado real | **218 / 218** |
| Visitas (perfil × tela) | 790: 514 com dado, 130 vazias legítimas, 92 recusas corretas, 54 perfil sem registro próprio |
| Erro de JavaScript / 5xx / chamada recusada escondida / botão sem ação | **0 / 0 / 0 / 0** |
| Telas de menu em 390 px (telefone) sem rolagem lateral | **230 / 230** |
| axe-core 4.10.2, WCAG A/AA, violações crítica/grave | **0** após correção (eram 3 regras) |
| Jornadas pela API | **13**, 169 passos, **0 falha** |
| Dados sobrevivem a reinício da aplicação | **sim** (pilha do zero) |

## 8. Problemas encontrados e corrigidos

| Problema | Onde | Como foi achado |
|---|---|---|
| 500 em `GET /v1/billing` (administração) | backend | robô de telas |
| Tela de equidade quebrava ao abrir | front | robô de telas (erro JS) |
| Responsabilidade chamava API sem parâmetros (422) | front | robô de telas |
| Confirmação de identidade inexistente na interface | front | robô de telas (401 sem saída) |
| 21 telas internas com erro cru para quem não é da equipe | front/roteador | robô de telas |
| 4 telas com 403 escondido (pediam projetos a quem não é OSC) | front | robô (chamada recusada) |
| Comparar soluções sem itens, perfil institucional 403 cru, link de e-mail sem token | front | robô de telas |
| "Tentar novamente" em erro definitivo; concordância "não encontrado" | front/backend | robô de telas |
| 13 seletores sem nome acessível, barra de progresso sem papel, rolagem fora do teclado | front | axe-core no CI |
| Inventário de telas contava errado (119 → 82 só por link; menus pela metade) | gerador | comparação robô × inventário |
| Persona Apoiador inexistente na demonstração | seed | robô (telas inalcançáveis) |
| `docker-compose.yml` de homologação incompatível com o entrypoint | infra | revisão para a pilha do zero |
| Diagnóstico do Supabase não dizia por que não conectava | script | execução real com o dono (v0.24.2) |

## 9. Pendências (não escondidas)

- **Endereço público** da demonstração — D-PUB1: conta de hospedagem do dono.
- **Leitor de tela real** (NVDA/VoiceOver) — fora de alcance de software automatizado.
- **Jornada editorial** (editora → revisor → publicação) não está no roteiro de demonstração desta
  versão; o fluxo é coberto pelos testes de conteúdo da Central (v0.12), não pela demonstração.
- **Apoiadora** executa só 4 passos de API (interesse, perfil, apoio a cota) — jornada fina.
- **14 integrações** (pagamento, fiscal, assinatura qualificada, gov.br, SMS…) seguem bloqueadas por
  credencial de fornecedor, como antes; nada disso foi simulado.
- 234 operações de API sem tela (medido em `screen_backend_map.json`): backend à frente da
  interface, como antes.

## 10. Segurança, acessibilidade, responsividade, Design System

- **Segurança:** recusa por perfil conferida em toda tela restrita; isolamento entre organizações
  (registro de outra organização → 404) permanece provado pelos testes de RLS; nenhum segredo nos
  arquivos (varredura própria + gitleaks no CI); `pip-audit` e `npm audit`: 0 vulnerabilidade.
  **Nenhum sistema ligado à internet é "impossível de invadir", e este não é exceção.**
- **Acessibilidade:** axe-core WCAG A/AA em cada rota, com trava; verificações próprias anteriores
  (nome acessível, teclado, foco, contraste calculado) seguem na suíte.
- **Responsividade:** 390 px sem vazamento lateral em todas as telas de menu dos 6 perfis.
- **Design System:** identidade oficial da v0.24.0 mantida; nenhuma tela nova com estética própria.

## 11. Match, diagnóstico, documentação, longitudinal, BI, governo, marketplace, financeiro

Exercitados pelas jornadas acima, sempre pela API real: match do edital com o projeto (sinais
explicados), diagnóstico aplicado e versionado, montagem de documento com campos derivados do
projeto e evidência anexada, série de 4 medições com 3 validadas por outra organização (reportado ×
validado; sem afirmação de causalidade), chamamento e necessidade territorial com fonte, anúncio no
marketplace, compromisso → desembolso → pagamento confirmado. Gráficos e BI: as telas abrem com
dado real e sem erro (robô); a correção visual de cada gráfico não é afirmada por este relatório.

## 12. Evidências

| O quê | Onde |
|---|---|
| Matriz por rota (790 visitas) | `docs/execution/ROUTE_RUNTIME_MATRIX.csv` |
| Matriz por perfil e jornada | `docs/execution/COVERAGE_MATRIX.md` |
| Jornadas, passo a passo | `docs/evidence/jornadas_v0250/relatorio.json` |
| Telas: resumo | `docs/evidence/telas_v0250/resumo.json` |
| Telefone: resumo e capturas | `docs/evidence/responsivo_v0250/` |
| Pilha do zero | job `pilha-do-zero` no GitHub Actions (artefato `pilha-do-zero`) |
| Regressão completa | `docs/evidence/test_run_v0.25.0.log` |
| Bloqueios | `docs/execution/BLOCKERS.md` (D-PUB1) |

## 13. Conclusão

A versão pode ser **apresentada** como demonstração funcional — localmente ou em qualquer máquina com
Docker, a partir do zero, com os dados das jornadas — e cada afirmação acima tem execução por trás.
Não pode ser apresentada como **endereço compartilhável** até que exista hospedagem (D-PUB1).
