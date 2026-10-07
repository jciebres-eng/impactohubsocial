# INTEGRATION_SECURITY — revisão de segurança da camada de integração

Método: revisão de código + testes de ataque reais em `backend/tests/test_v0130_integrations.py` (classe `IntegrationSecurity` e outras). **Não é pentest.** Legenda: **PROVADO** (teste) · **POR INSPEÇÃO** · **PENDENTE**.

| Vetor | Controle | Estado |
|---|---|---|
| **SSRF (gravação)** | ao salvar conexão/assinatura: só HTTPS; IP literal privado/loopback/link-local/reservado/multicast recusado. Webhook do cliente **nunca** aceita loopback; conexão aceita só fora de ambiente endurecido (dublê local) | **PROVADO** |
| **SSRF (chamada)** | guarda autoritativa no `HttpClient`: resolve o nome e recusa rede interna/metadados (169.254.169.254); **não segue redirecionamento**; destino recusado é erro **permanente** (não fica repetindo) | **PROVADO** |
| **DNS rebinding** | risco residual conhecido (resolução e conexão são passos separados) | **PENDENTE** — mitigar no egress da infraestrutura |
| **XXE / entidade externa** | `defusedxml` com `forbid_dtd/entities/external`; limite de 8 MB e profundidade 40 | **PROVADO** (XXE e bomba recusados) |
| **Injeção de XML em SOAP** | valores escapados no envelope; nome de operação validado (`isalnum`) | **PROVADO** |
| **Spoofing de webhook** | HMAC-SHA256 com segredo por conexão/assinatura; comparação em tempo constante | **PROVADO** |
| **Replay** | carimbo de tempo na assinatura com tolerância de 300 s **+** dedupe por `(conexão, id do evento)` no banco | **PROVADO** (inclusive 4 entregas em paralelo → 1 processamento) |
| **Vazamento de credencial** | segredo cifrado (Fernet com rotação); **sem SELECT** na coluna para o papel da aplicação (nem em contexto de sistema) — leitura só por `integration_secret()`; API devolve apenas a dica; redação de segredos no log; auditoria sem o valor | **PROVADO** |
| **IDOR / escape de tenant** | RLS em todas as 13 tabelas; leitura e escrita cruzadas recusadas em conexões, credenciais, mapeamentos, jobs, links, eventos, assinaturas, entregas, importações e exportações | **PROVADO** |
| **Escalonamento de privilégio** | papéis: leitura (`viewer`), configuração (`manager`), credencial e aprovação de importação (`owner`), catálogo e painel (administração com MFA); progresso de job/entrega é escrita privilegiada (ninguém "declara entregue") | **PROVADO** |
| **Injeção de SQL** | tudo parametrizado; conteúdo externo é armazenado literalmente | **PROVADO** |
| **Execução de código via mapeamento** | transformações são um conjunto FECHADO; sem `eval`/`exec` | **PROVADO** |
| **Arquivo malicioso** | cofre existente (tamanho, extensão, assinatura binária, conteúdo ativo, zip bomb, antivírus); allowlist **não** foi enfraquecida; XLSX limita conteúdo descomprimido (60 MB) e células (400 mil) | **PROVADO** |
| **Injeção de fórmula (CSV/XLSX)** | exportação prefixa `'` em células que começam com `= + - @ TAB CR` | **PROVADO** |
| **Path traversal** | nenhum caminho vem do cliente: arquivos são lidos pelo `storage_key` do documento | **POR INSPEÇÃO** |
| **Injeção em log** | logs estruturados em JSON com redação de chaves sensíveis | **POR INSPEÇÃO** |
| **Abuso de taxa** | limites por IP em entrada (600/min), saúde (60/h), jobs (120/h), importação (60/h), exportação (30/h), teste de assinatura (30/h) | **PROVADO** (declarado no spec) |
| **Desserialização insegura** | só JSON/CSV/XML por parsers seguros; nenhum `pickle` | **POR INSPEÇÃO** |
| **Cabeçalho malicioso em webhook** | `Authorization`/`Cookie` fornecidos pelo cliente são descartados na entrega | **PROVADO** |
| **Negação de serviço por sistema externo** | teto de tempo, tentativas limitadas, disjuntor por conexão, trabalho fora da requisição | **PROVADO** (núcleo segue respondendo) |

## LGPD (técnico; não é parecer jurídico)
- **Finalidade e minimização**: o payload do evento leva identificadores e campos do domínio, montados pelo servidor; datasets de BI têm colunas fixas e públicas do domínio (sem segredo, sem conteúdo de mensagem de suporte).
- **Acesso**: tudo por organização (RLS) e por papel; credencial nunca é legível.
- **Auditoria**: `audit_events` registra quem, qual organização, qual conexão, operação, objeto, resultado, correlação — sem senha, token ou segredo.
- **Retenção**: entregas concluídas apagadas após 180 dias; dead-letter preservado para investigação; jobs e eventos não têm expurgo automático ainda — **LEGAL VALIDATION REQUIRED** para definir prazos.
- **Compartilhamento com terceiro**: enviar evento a um parceiro é compartilhamento de dado pessoal. A plataforma registra o consentimento/finalidade? **PENDENTE DE DPO**: hoje a assinatura é criada pela organização, que responde pela base legal. Recomendação registrada em `INTEGRATION_OPERATIONS.md`.
- **Exclusão/anonimização**: a importação nunca cria pessoa; apagar correspondência não apaga dado do núcleo. Exclusão de conta segue o fluxo de privacidade existente.
