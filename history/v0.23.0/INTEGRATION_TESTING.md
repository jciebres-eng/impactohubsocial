# INTEGRATION_TESTING — o que está provado por teste

Suíte: `backend/tests/test_v0130_integrations.py` (**76 testes**). Suíte completa do projeto: **468 testes, 0 falhas** (evidência: `docs/evidence/test_run_v0.13.0.log`).

Comando (a partir de `backend/`):
```
TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" \
PASSWORD_SCRYPT_N=16384 RATE_LIMIT_MULTIPLIER=1000 LOG_LEVEL=ERROR \
python3 -m unittest tests.test_v0130_integrations -v
```
Cada execução cria um banco vazio e aplica **todas as migrações** (0001→0011): a migração é testada em banco vazio em toda rodada.

## Dublê, não invenção
Nenhum sistema externo é chamado. `FakeTransport` substitui o `HttpClient` e responde por sufixo de URL, podendo simular status, corpo, erro de rede, demora e cabeçalhos recebidos (`last_headers`). **Isto prova o nosso lado do contrato; não prova compatibilidade com Senior, TOTVS, Protheus ou Gov.br.**

## Cobertura por área
| Classe | Testes | Prova |
|---|---|---|
| `ConnectionLifecycle` | 9 | catálogo, criação em `draft`, `config_problems`, ativação só com configuração+credencial, pausa, revogação, unicidade org×provedor×ambiente, ambiente inválido |
| `CredentialSecurity` | 7 | segredo nunca retornado, só dica, substituição apaga a anterior, exclusão, papel `owner` exigido, coluna negada ao papel da aplicação, ausência em log/auditoria |
| `TenantIsolation` | 10 | leitura e escrita cruzadas recusadas em conexão, credencial, mapeamento, job, link, assinatura, entrega, importação, exportação, evento |
| `MappingAndExternalIds` | 9 | 12 transformações, campo obrigatório ausente = erro, enum sem correspondência = erro, link cria/reusa, conflito detectado, ID interno nunca substituído, `deleted_externally` |
| `JobLifecycle` | 8 | idempotência (mesma chave = mesmo job), ciclo `pending→running→succeeded`, erro temporário repete, permanente não repete, cancelamento, espera crescente, disjuntor abre em 5 falhas, **4 trabalhadores em paralelo = 1 execução** |
| `OutboundWebhooks` | 7 | assinatura HMAC verificável, catálogo fechado, HTTPS obrigatório, 4xx vai a dead-letter, 5xx repete até 6, replay só de dead-letter e da própria organização, `Authorization`/`Cookie` descartados |
| `InboundWebhooks` | 6 | assinatura exigida, carimbo fora da janela recusado, `X-Event-Id` obrigatório, duplicado ignorado, **4 entradas em paralelo = 1 processamento**, conexão inativa recusada, conexão inexistente = 404 genérico |
| `FileIntegration` | 8 | CSV e XLSX importados, JSON/XML recusados com 422 explicativo, mesmo arquivo não entra duas vezes, prévia com erro por linha, aprovação só de linhas válidas, exportação gera documento, neutralização de fórmula |
| `HealthAndOperations` | 5 | checagem não destrutiva, saúde atualizada, painel de operação, latência, retenção |
| `IntegrationSecurity` | 5 | SSRF (169.254.169.254) recusado, XXE recusado, bomba XML recusada, injeção em SOAP escapada, mapeamento sem execução de código |
| `AdapterContracts` | 6 | cada adapter valida configuração, declara capacidades, traduz erro em `IntegrationError` com tipo correto; governo **recusa agir** enquanto `technically_ready` |
| `SimulatedProductionFlow` | 2 | jornada completa (conectar → credencial → mapear → ativar → saúde → pull → link → evento → entrega) e queda do sistema externo sem afetar o núcleo |

## O que NÃO está testado (honestidade)
- Compatibilidade real com qualquer ERP, Gov.br, Conecta ou Stripe ao vivo.
- SFTP (não implementado).
- Carga/estresse com volume de produção.
- DNS rebinding.
- Auditoria de dependências (registros npm/PyPI bloqueados no ambiente).
