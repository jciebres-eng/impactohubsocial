# DOCUMENT_FORMATS — importação e exportação de documentos

## 1. Formatos de saída
| Formato | Como é gerado | Onde |
|---|---|---|
| **PDF** | reportlab (já existia), agora com **QR Code e código de verificação** impressos | rascunhos, exportações |
| **DOCX** | OOXML WordprocessingML escrito à mão | rascunhos, exportações |
| **ODT** | ODF Text escrito à mão | rascunhos, exportações |
| **XLSX** | OOXML SpreadsheetML escrito à mão (tipos texto/número/booleano) | exportações |
| **ODS** | ODF Spreadsheet escrito à mão | exportações |
| **XML** | intercâmbio, com nome de tag saneado | exportações |
| **CSV** | já existia, com neutralização de fórmula | exportações |
| **JSON** | já existia | exportações |

**Por que à mão:** `python-docx`, `openpyxl` e `odfpy` não podem ser instalados neste ambiente (registros npm/PyPI
bloqueados). OOXML e ODF são ZIPs de XML; o mínimo válido está em `backend/impacto/services/formats.py`, sem dependência
nova. O ODF respeita a exigência do formato: `mimetype` é a primeira entrada do ZIP e **sem compressão**.

## 2. Formatos de entrada (extração de texto)
`docx` e `odt` passaram a ser lidos (lê o XML interno, remove marcação e **desfaz as entidades XML** — isto era um
defeito meu, corrigido: `&amp;` voltava literal). Já existiam: `pdf`, `txt`, `csv`, `json`, `xml` e imagens.
O cofre de documentos **não foi enfraquecido**: a allowlist, a verificação de assinatura binária, a recusa de PDF com
conteúdo ativo, o limite de zip bomb e o antivírus continuam valendo para tudo que entra.

## 3. Onde usar
| Rota | Formatos |
|---|---|
| `POST /v1/drafts/{id}/export` | `pdf`, `docx`, `odt` — com `include_verification: true`, imprime o QR e o código |
| `POST /v1/integrations/exports` | `csv`, `json`, `xlsx`, `ods`, `xml`, `docx`, `odt`, `pdf` sobre os 6 datasets do hub |
| `POST /v1/drafts/{id}/export-pdf` | mantida por compatibilidade (v0.7.0) |

Imprimir o QR exige que o registro público exista antes (`409 no_verifiable_record` explica e aponta a rota) — assim o
papel nunca sai com um código que não resolve.

## 4. Segurança
- Todo valor textual é escapado antes de entrar no XML (`&`, `<`, `>`); nome de tag é saneado e nunca vem de texto livre.
- **Neutralização de fórmula** (`'` antes de `= + - @ TAB CR`) agora vale para **xlsx e ods também**, não só CSV — uma
  planilha aberta no Excel executa fórmula igual, independente do formato.
- Limites: 50.000 linhas e 256 colunas por planilha; exportação em docx/odt/pdf lista no máximo 2.000 registros e diz
  isso no próprio documento (para a lista completa, xlsx/csv).

## 5. Edição on-line (Office 365 / LibreOffice / OnlyOffice)
**NÃO IMPLEMENTADA — DEPENDÊNCIA EXTERNA.** Editar documento no navegador em colaboração exige um servidor de documentos
que fale WOPI (Microsoft 365 na Web, Collabora Online, OnlyOffice Docs). Isso é infraestrutura contratada, com host
próprio, certificado e licença — não é algo que se resolve em código de aplicação.
O que a plataforma entrega hoje: exporta nos formatos que **abrem no Office e no LibreOffice instalados na máquina da
pessoa**, e importa de volta extraindo o texto. O contrato WOPI está descrito aqui para quando houver o servidor.

## 6. Limite declarado da validação
Os arquivos são validados por teste que **reabre o ZIP e confere o XML** (estrutura, tipos de conteúdo, tipos de célula,
`mimetype` do ODF). **Não foram abertos no Microsoft Office nem no LibreOffice neste ambiente** — não há essas aplicações
aqui. Antes do piloto, abrir uma amostra de cada formato nos dois aplicativos é um teste manual obrigatório.
