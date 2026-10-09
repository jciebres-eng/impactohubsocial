# Montagem de documentos — `document-assembly@1.0.0`

Código: `backend/impacto/core/assembly.py` · rotas: `backend/impacto/api/assembly_routes.py` · dados:
`document_templates`, `document_template_fields`, `document_assemblies`.

## 1. O problema que isto resolve

Uma OSC não precisa de um editor de texto. Precisa saber **o que o documento tem que dizer**, de onde vem cada
pedaço, o que ainda falta e se o que falta impede entregar. A plataforma trata o documento como uma montagem com
regra, não como um arquivo em branco.

```
MODELO ──► MONTAGEM ──► COMPLETUDE ──► BLOQUEIO explicado ──► GERAÇÃO ──► REVISÃO (4 olhos) ──► ASSINATURA
```

## 2. Modelo

`document_templates`: `code` + `version` (UNIQUE), `kind` (16 tipos), `data_sources`, `output_formats`, `status`
(`draft` / `published` / `archived`), `owner_org_id` (NULO = modelo da plataforma) e **`source_note`**.

**Modelo publicado é imutável.** Duas camadas:
- `trg_guard` em `document_templates` protege `status`, `published_by`, `published_at`, `code`, `version`;
- `template_field_guard()` recusa INSERT/UPDATE/DELETE de campo quando o modelo está publicado, com a mensagem
  *"Modelo publicado é imutável: crie uma nova versão do modelo"*.

Corrigir um modelo publicado exige **nova versão**. Mesmo princípio das regras fiscais e dos cursos: um documento
gerado em março precisa continuar explicável em dezembro.

### `source_note` é obrigatório na prática

Todo modelo diz **de onde a estrutura dele vem**. Os três da plataforma:

| Código | Título | Fonte declarada |
|---|---|---|
| `projeto_tecnico_base` | Projeto técnico — estrutura base | Estrutura própria da Plataforma Impacto. **Não é formulário oficial de nenhum financiador**: confira as exigências do edital. |
| `plano_trabalho_mrosc` | Plano de trabalho — conteúdo do art. 22 da Lei 13.019/2014 | Itens organizados a partir do art. 22 da Lei 13.019/2014 (MROSC). A redação final e os anexos seguem o edital e o órgão parceiro. A plataforma **não reproduz formulário oficial de órgão público**. |
| `plano_monitoramento_base` | Plano de monitoramento e avaliação | Estrutura própria. A separação produto/resultado/impacto segue a lógica de cadeia de valor usada em avaliação de projetos sociais; **meta atingida não é impacto comprovado**. |

26, 12 e 11 campos respectivamente. Uma organização pode criar modelos próprios (`POST /v1/document-templates`,
papel `admin`), que nascem em rascunho e só servem depois de publicados — e publicar modelo sem campo nenhum é
recusado (409 `template_empty`).

## 3. Campo

`document_template_fields`: `section`, `position`, `key`, `label`, `help`, `field_type` (13 tipos), `options`,
`required`, `derived_from`, `requires_evidence`.

### `derived_from` é uma lista FECHADA

Campo com `derived_from` **não é digitado**: o valor vem do domínio. Os 14 caminhos permitidos estão em
`assembly.DERIVABLE` (título, problema, objetivos, metodologia, território, orçamento, início, fim, público do
projeto; razão social, CNPJ, município/UF da organização; necessidade e objetivo do diagnóstico).

Caminho fora da lista é recusado com 422 `derived_unknown` e a lista do que existe. A razão é direta: se
`derived_from` fosse expressão livre, um modelo seria uma consulta arbitrária ao banco — e modelos podem ser
criados por qualquer organização. Testado em `test_derived_field_path_is_a_closed_list` com
`derived_from: "users.password_hash"`.

Na interface, campo derivado aparece em **leitura**, dizendo de onde vem. A pessoa corrige no projeto, não redigita
no documento.

### `requires_evidence`

Evidência é exigida quando o campo é **obrigatório** ou quando **foi preenchido**: quem afirma, prova. Campo
opcional em branco não gera pendência de evidência — defeito corrigido nesta versão (antes, um campo opcional com
`requires_evidence` bloqueava a geração para sempre).

A evidência é um documento do cofre **da mesma organização**, conferido na gravação (404 se for de outra) e
reconferido na avaliação: documento apagado ou recusado no antivírus aparece como `evidence_invalid`.

## 4. Montagem e completude

`document_assemblies` guarda `values` (o que a equipe digitou), `evidence` (`{campo: document_id}`), e o que **o
servidor calcula**: `completeness`, `missing`, `status`, `blocked_reason`. Essas quatro são colunas guardadas: o
cliente não dita a sua própria completude.

`evaluate()` devolve, sem gravar:

```json
{"completeness": 81.82, "filled": 18, "total": 22,
 "missing": [{"kind": "field|evidence|evidence_invalid", "key": "...", "label": "...", "section": "...",
              "derived_from": "project.objectives"}],
 "derived": {"org.legal_name": "...", "project.title": "..."},
 "blockers": ["3 item(ns) obrigatório(s) faltando."],
 "can_generate": false}
```

### Situações

`drafting` → `ready` → `generated` → `in_review` → `approved` / `rejected` → `signed` → `archived`, com `blocked`
quando há impedimento. A montagem **nasce** em `drafting` (gatilho `assembly_initial_state`): não existe montagem
que nasça aprovada.

## 5. A recusa é o ponto

`POST /v1/document-assemblies/{id}/generate` com pendência:

```json
HTTP 409
{"code": "assembly_blocked",
 "title": "Não é possível gerar este documento: 3 item(ns) obrigatório(s) faltando.",
 "details": {"missing": [...], "completeness": 72.5}}
```

Bloqueios possíveis: modelo não publicado · projeto em situação terminal (`archived`, `cancelled`, `rejected`) ·
item obrigatório faltando · evidência inválida anexada.

Na interface, o botão "Gerar documento" fica **desabilitado com a lista do que falta à vista** — invariante de
design conferida por teste de navegador
(`test_e2e_v0150_web.test_blocked_assembly_shows_what_is_missing_instead_of_generating`).

Gerar documento incompleto seria pior do que não gerar: produz um arquivo com aparência de pronto que será recusado
na ponta, depois do prazo.

## 6. Geração

Formatos: PDF, DOCX, ODT — escritos pela própria plataforma (`services/formats.py`, ver `DOCUMENT_FORMATS.md`), sem
dependência externa. O arquivo vai para o **cofre** (`documents`) com `origin = 'generated'`, hash SHA-256,
`storage_key` própria e rodapé com modelo, versão, identificador da montagem e completude no momento da geração.

A identidade do arquivo é imutável: `document_identity_guard()` recusa alteração de `sha256`, `size_bytes`,
`storage_key` ou `mime_type` em `documents` para **qualquer** papel da aplicação, privilegiado incluído. Nova versão
de documento é **linha nova**.

A geração entra na trilha do projeto como `document_generated`, com o hash e a completude.

## 7. Revisão com quatro olhos

`POST /v1/document-assemblies/{id}/review`:

- quem **montou** não pode aprovar: 409 `four_eyes`, *"Peça a revisão a outra pessoa."*;
- a regra também está no banco: `CHECK (approved_by IS NULL OR approved_by <> created_by)`;
- recusa exige observação, e devolve a montagem para edição (`rejected` → ao salvar, volta a `drafting`);
- aprovação entra na trilha como `document_approved`.

É separação de funções, não burocracia: o mesmo princípio já vale para validação de indicador
(`indicator_values`: quem valida não é quem informou) e para regra fiscal (duas aprovações).

## 8. Rotas

| Método | Caminho | O que faz |
|---|---|---|
| GET | `/v1/document-templates` | modelos (da plataforma + da organização) |
| GET | `/v1/document-templates/{id}` | modelo com seções e campos |
| POST | `/v1/document-templates` | cria modelo próprio (rascunho) |
| POST | `/v1/document-templates/{id}/fields` | acrescenta campo (recusado se publicado) |
| POST | `/v1/document-templates/{id}/publish` | publica (a partir daqui, imutável) |
| GET | `/v1/document-assembly-reference` | caminhos deriváveis, formatos, situações, o que bloqueia |
| GET/POST | `/v1/document-assemblies` | lista / abre montagem |
| GET | `/v1/document-assemblies/{id}` | montagem + modelo + avaliação |
| PUT | `/v1/document-assemblies/{id}` | preenche (servidor recalcula completude) |
| POST | `/v1/document-assemblies/{id}/generate` | gera (RECUSA se incompleto) |
| POST | `/v1/document-assemblies/{id}/review` | revisa (quatro olhos) |

## 9. O que NÃO existe aqui

- **Não há editor colaborativo em tempo real.** A montagem é formulário com regra; edição simultânea não é tratada
  (último a salvar vence, dentro da mesma organização).
- **Não há importação de modelo de terceiro.** A plataforma não distribui formulário oficial de órgão público ou
  financiador. Estrutura de conteúdo, sim; o formulário é do órgão.
- **Não há assinatura automática ao gerar.** Gerar e assinar são passos distintos, com a assinatura seguindo
  `DIGITAL_SIGNATURE.md` e `SIGNATURE_VALIDATION_MATRIX.md`.
