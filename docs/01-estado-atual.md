# 01 — Estado atual da Plataforma Impacto

**Data:** 09/10/2026 · **Branch analisada:** `main`, commit `906d383` · **Versão declarada:** 0.30.0 no arquivo `VERSION`
(o último commit se chama "v0.30.1" — ver `02-auditoria.md`, M5)

## Em uma frase

A Plataforma Impacto conecta quem financia projetos sociais (empresas, institutos, governo, pessoas) a quem executa
(ONGs/OSCs, prestadores, promotores de ideias), e acompanha cada projeto do começo ao fim — candidatura, contrato,
marcos, evidências, indicadores, prestação de contas — com registro que não pode ser apagado nem alterado em silêncio.

## O que a plataforma faz hoje (funcionando e testado)

- **Contas e organizações:** cadastro, login com verificação em duas etapas (obrigatória para administradores),
  organizações com papéis, convites. Cada organização só enxerga os próprios dados (isolamento feito no próprio banco).
- **Perfis:** OSC/executora, empresa/financiador, governo, apoiador (pessoa física), prestador de serviço, promotor de
  ideias, e as equipes internas (administração, revisão, suporte, financeiro, auditoria).
- **Projetos e oportunidades:** criação de projeto, chamadas/editais, candidaturas, e um "match" que sugere projetos
  para financiadores e oportunidades para OSCs — **pagamento não melhora posição** (regra testada).
- **Diagnóstico de prontidão:** mostra o que falta para um projeto estar pronto para receber recurso.
- **Contratos e marcos:** acordo assinado entre as partes, marcos com prazos, entrega e aceite (quem entrega não pode
  aceitar a própria entrega).
- **Evidências e indicadores:** cada evidência tem origem, versão, histórico e pode ser contestada; indicadores com
  método registrado; **dossiê do projeto** para quem financia.
- **Documentos:** envio de arquivos com verificação antivírus; arquivo não verificado não é baixado em produção.
- **Base de conhecimento e ajuda:** artigos com fontes, glossário, assistente que cita a fonte ou diz que não sabe.
- **Inteligência artificial:** operações catalogadas, com cota e custo controlados; nenhum provedor externo de IA
  ligado (funciona com o motor local).
- **Painéis ("torres de controle")** por perfil e área administrativa.
- **Trilhas de auditoria** com encadeamento por hash (detectam alteração no histórico).

## O que existe mas está incompleto ou desligado (de propósito)

| Parte | Estado | Por quê |
|---|---|---|
| Cobrança (taxa de 3,5 % sobre operações financiadas) | **desligada** — 0 regras ativas; receita real R$ 0,00 | depende de parecer jurídico/contábil |
| Pagamentos (PIX/cartão) | **não ligado** — nenhum provedor contratado | decisão e contrato pendentes |
| Nota fiscal | **não ligado** | provedor fiscal pendente |
| Assinatura digital qualificada (ICP-Brasil) / gov.br | **não ligado** | integrações externas não contratadas |
| Termos de Uso e Política de Privacidade | **minutas**; o cadastro em produção responde 503 até a aprovação com revisor nomeado | revisão jurídica pendente |
| Aplicativo celular | estrutura pronta (Capacitor), não publicado nas lojas | — |
| Domínio próprio | em configuração (sua pendência 1) | — |

## Tecnologias

| Camada | O que é usado |
|---|---|
| Servidor (backend) | Python 3.12, Starlette + Uvicorn; driver próprio de PostgreSQL sobre a biblioteca oficial `libpq` |
| Banco de dados | PostgreSQL (Supabase, versão 17 na produção; 16 nos testes) com isolamento por organização (RLS) em todas as tabelas |
| Site (frontend) | React 19 + TypeScript, compilado com esbuild |
| Celular | Capacitor 7 (Android/iOS) |
| Contêiner | Uma imagem Docker (site + API); mesmo arquivo serve ao worker |
| Antivírus | ClamAV |
| Testes | `unittest` do Python com banco PostgreSQL real; navegador Chromium (Playwright) para telas e jornadas |
| CI | GitHub Actions: auditoria de segredos e vulnerabilidades, build da imagem, suíte completa, "pilha do zero" |

## Onde está rodando (segundo o `CLAUDE.md`)

| Peça | Onde |
|---|---|
| Site/API | Railway, ambiente **production**, serviço `impactohubsocial` — **publicação manual** |
| Worker (rotinas) | Railway, serviço `pleasing-trust` |
| Antivírus | Railway, serviço `clamav` |
| Demo | Railway, ambiente **demo**, serviço `ideal-delight`, banco próprio com dados fictícios — **publica sozinho a cada commit na `main`** |
| Banco | Supabase Pro (us-west-2), pelo pooler de sessão |
| Arquivos | Cloudflare R2, bucket `impacto-arquivos` |
| Backup | GitHub Actions `backup-supabase`, diário, cifrado, bucket R2 `impacto-backups` |
| Monitor | GitHub Actions `monitor`, a cada 10 minutos |
| E-mail | Brevo (SMTP) |
| DNS | Cloudflare, `impactohubsocial.com.br` |

O que eu **comprovei** de fora hoje: o banco (diagnóstico somente-leitura, execução `37992280274`), o backup
(execução `37988830616`, sucesso) e o CI. O painel do Railway, o R2 e a Cloudflare eu não acesso.

## Estrutura de pastas (as que importam)

```text
backend/
  impacto/        código do servidor (rotas da API, regras, motores, rotinas do worker)
  migrations/     71 alterações do banco, em ordem (só para frente)
  tests/          131 arquivos de teste
  start_container.sh   script de início do site (migra o banco e troca para o usuário limitado)
web/src/          telas do site (React)
mobile/           aplicativo celular (Capacitor)
config/           regras de negócio em arquivos (planos, preços-hipótese, retenção de dados, glossário…)
docs/             documentação técnica e operacional (estes arquivos 01–04 inclusive)
scripts/          ferramentas: varredura de segredos, empacotamento, diagnóstico do Supabase, backup…
infra/            arquivos de uma instalação antiga em servidor próprio (Compose/nginx) — NÃO é o caminho em uso
knowledge-base/   base de conhecimento (fontes, controles, pesquisas)
history/          cópias dos documentos de cada versão anterior
.github/workflows/  CI, backup, monitor, diagnóstico do Supabase
```

Tamanho aproximado: ~52.600 linhas de Python no servidor, ~17.800 linhas no site, 940 operações na API, 227 telas.

## Resultado dos testes (executados nesta auditoria)

Comando (na pasta `backend/`, com PostgreSQL 16 local):
`python3 -m unittest discover -s tests -t .`

```text
Ran 2408 tests in 1907.146s
FAILED (failures=3, skipped=27)
```

- **2.378 passaram**, **3 falharam**, **0 erros**, **27 pulados** (dependem de credenciais externas ou de um servidor de
  armazenamento de teste que só existe no CI).
- As 3 falhas são **as mesmas do CI da `main`** (execução `37988354371`, mesmos 2.408 testes) — não são defeito do
  site em funcionamento, e sim verificações que ficaram desatualizadas depois das mudanças de 09/10:
  1. `test_every_table_but_the_declared_exception_has_rls_enabled` — a migração 0071 protegeu a tabela que o teste
     listava como exceção (mudança boa; o teste precisa ser atualizado);
  2. `test_regenerating_each_matrix_reproduces_what_is_committed` — a matriz `INTEGRATION_HOMOLOGATION_MATRIX.csv` não
     foi regenerada depois do teste novo da v0.30.1;
  3. `test_every_tracked_file_is_either_in_the_manifest_or_excluded_with_a_reason` — arquivos novos fora do manifesto da
     versão (esta branch acrescenta mais quatro documentos, que entram no próximo manifesto).
- Correção das três: incremento 3 do `04-roadmap.md`.

Outras verificações feitas hoje: varredura de segredos (`scripts/secrets_scan.py`, 1.003 arquivos: nenhum segredo);
auditoria de vulnerabilidades de dependências (`pip-audit` + `npm audit`, job `auditoria` do CI: verde); construção da
imagem Docker e "pilha do zero" no CI: verdes.
