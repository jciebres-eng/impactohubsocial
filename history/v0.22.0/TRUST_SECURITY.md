# TRUST_SECURITY — revisão de segurança da camada de confiança (v0.14.0)

Método: revisão de código + testes de ataque reais em `backend/tests/test_v0140_trust.py`. **Não é pentest.**
Legenda: **PROVADO** (teste) · **POR INSPEÇÃO** · **PENDENTE**.

| Vetor | Controle | Estado |
|---|---|---|
| **Autopromoção de identidade** | `identity_verifications.status` é coluna guardada (`guard_columns`): o papel da aplicação recebe 42501 | **PROVADO** (SQL direto no contexto da própria pessoa) |
| **Autopromoção de credencial** | `verification_status` guardada desde a 0002; o avanço para `document_submitted` é passo privilegiado | **PROVADO** |
| **Assinar sem a segunda camada** | código obrigatório, de uso único, com 5 tentativas | **PROVADO** (sem código, código errado, reusado, expirado) |
| **Troca do documento entre conferência e assinatura** | o desafio guarda o hash; o servidor relê e compara | **PROVADO** |
| **Reuso do mesmo código em paralelo** | `used_at` queimado em contexto de sistema | **PROVADO** — 4 requisições simultâneas com o mesmo código ⇒ **1** assinatura |
| **Reescrever a cadeia de custódia** | `trust_events` sem GRANT de UPDATE + gatilho append-only; `seq`/`prev_hash`/`event_hash` calculados por gatilho SECURITY DEFINER | **PROVADO** (recusa para a organização **e** para o contexto de sistema) |
| **Adulterar a cadeia** | detectada por `trust_verify()` | **PROVADO** — o teste desliga o gatilho **como dono do banco** para quebrar, e a verificação aponta o `seq` exato |
| **Adulterar o arquivo guardado** | o hash é recontado na verificação pública e no endpoint de integridade | **PROVADO** — `storage_verified: false` |
| **Falsificar assinatura de outra parte** | `signed_at`/`signature_id` são colunas guardadas; a linha da outra parte é invisível para escrita por RLS | **PROVADO** (os dois caminhos) |
| **Congelar o hash do acordo** | `content_sha256` é coluna guardada | **PROVADO** |
| **Vender mais cotas do que existem** | gatilho `quota_capacity_guard` **SECURITY DEFINER** com trava na cota e checagem explícita de NULL | **PROVADO** — inclusive 4 reservas simultâneas |
| **Confirmar o próprio pagamento** | `quota_pledges.status` e `payment_ref` guardados; confirmação é da administração | **PROVADO** |
| **Publicar honorário sem fonte** | CHECK no banco + validação na rota | **PROVADO** (`422 source_required`) |
| **Vazamento de dado pessoal na página pública** | payload curado na criação; a consulta pública lê só `public_fields` | **PROVADO** — e-mail, identificador e nome do representante ausentes do corpo da resposta e da página renderizada |
| **IDOR entre organizações** | RLS nas 26 tabelas novas | **PROVADO** — registros públicos, custódia, integridade, acordos, cotas, marcadores, identidade |
| **Enumeração de códigos públicos** | código aleatório de 12 caracteres em alfabeto de 33 (~60 bits), limite de 120 consultas/IP/hora | **PROVADO** (limite declarado no spec) |
| **Recursão de política de RLS** | travessia entre acordos e partes por funções SECURITY DEFINER | **PROVADO** (era um defeito real; corrigido) |
| **Injeção em XML/OOXML/ODF gerado** | todo valor passa por `escape`; nome de tag é saneado | **PROVADO** (`&`, `<`, `>` escapados; tags `nome ruim`→`nome_ruim`) |
| **Injeção de fórmula em planilha** | neutralização com `'` aplicada a CSV **e** a xlsx/ods | **PROVADO** |
| **Leitura de docx/odt enviado** | `zipfile` + remoção de marcação, sem parser de XML sobre conteúdo não confiável | **POR INSPEÇÃO** |
| **Segredo em log** | redação por chave; o código do desafio nunca é persistido em claro (só o SHA-256) | **POR INSPEÇÃO** |
| **Força bruta no código de 6 dígitos** | 5 tentativas por desafio + expiração de 10 min + limite por IP | **PROVADO** |
| **DNS rebinding / SSRF** | nenhuma chamada externa nova nesta camada | não se aplica |
| **Assinatura qualificada falsificada** | a plataforma **não emite** assinatura qualificada; o enum nunca é usado | **POR INSPEÇÃO** |
| **Pentest da camada** | — | **PENDENTE** |
| **Auditoria de dependências** | registros npm/PyPI bloqueados neste ambiente | **PENDENTE** (obrigatória em CI) |

## Bug de segurança encontrado e corrigido durante a construção
O gatilho que impede vender mais cotas do que existem **passava em silêncio**. `SELECT ... FOR UPDATE` aplica também a
política de **UPDATE** da tabela travada; quem apoia não é dona da cota, então a linha desaparecia e as variáveis vinham
`NULL`. Em PL/pgSQL, toda comparação com `NULL` não é verdadeira — logo todas as checagens eram puladas e era possível
reservar cota inexistente (o teste chegou a ver `remaining_quotas: -1`). Correção: a função passou a ser SECURITY DEFINER
(também para somar **todas** as reservas, não só as visíveis) e ganhou checagem explícita de `NULL`.
Lição registrada como ADR: **guarda de integridade não pode depender de visibilidade por RLS.**

## Chaves e segredos
O selo do carimbo interno e o HMAC da assinatura usam `SECRET_KEY` do processo. Rotação da chave invalida a conferência
dos selos antigos — **DEPENDÊNCIA DE INFRAESTRUTURA**: guardar a chave em gerenciador de segredos e versioná-la antes do
piloto. O código do desafio nunca é gravado em claro. Nenhuma chave entra no ZIP de release (varredura automática no
`make_release.py`).
