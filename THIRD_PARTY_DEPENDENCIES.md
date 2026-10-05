# Dependências de terceiros e licenças — v0.7.0

Classificação: **PRÓPRIO** (código/ativos do projeto) · **OSS** (open source incorporado/instalado) · **SERVIÇO** (externo, opcional) · **ASSET** (fonte/ícone/imagem de terceiros).
Licenças dos pacotes Python foram lidas dos metadados instalados neste ambiente em 2026-10-05; as demais, dos termos públicos conhecidos — **confirmar no CI com gerador de SBOM** (ver fim).

## Backend (execução) — `backend/requirements.txt`
| Pacote | Versão | Licença | Classe | Uso |
|---|---|---|---|---|
| starlette | 1.6.0 | BSD-3-Clause | OSS | framework ASGI |
| uvicorn | 0.53.0 | BSD-3-Clause | OSS | servidor ASGI |
| pydantic | 2.13.5 | MIT | OSS | validação |
| PyJWT | 2.14.0 | MIT | OSS | validação de id_token OIDC |
| cryptography | 50.0.1 | Apache-2.0 OR BSD-3-Clause | OSS | Fernet (MFA), RSA/JWKS |
| python-multipart | 0.0.32 | Apache-2.0 | OSS | upload |
| pypdf | 5.9.0 | BSD-3-Clause | OSS | inspeção de PDF enviado |
| reportlab | 5.0.1 | BSD (ReportLab) | OSS | PDF de rascunhos |
| defusedxml | 0.7.1 | PSF | OSS | XML seguro (importação de feeds) |
| anyio | 4.15.1 | MIT | OSS | async |
| libpq5 (sistema) | 16.x | PostgreSQL License | OSS | cliente do driver `db/pq.py` |
Transitivas (pydantic-core, annotated-types, typing-extensions, h11, click, cffi, pycparser…): licenças permissivas (MIT/BSD/PSF/Apache) conhecidas — **não inventariadas uma a uma aqui**.
Opcionais: pytesseract 0.3.13 (Apache-2.0), Pillow 12.3.0 (MIT-CMU), Tesseract OCR (Apache-2.0).
Desenvolvimento/teste: Playwright 1.56.0 (Apache-2.0; Chromium: BSD e componentes diversos), pip-audit (Apache-2.0), ruff (MIT).

## Frontend — `web/package.json`
| Pacote | Versão | Licença | Uso |
|---|---|---|---|
| react, react-dom | 19.2.8 | MIT | UI |
| esbuild | 0.28.2 | MIT | build |
| typescript | 6.0.3 | Apache-2.0 | tipagem |
| @types/react, @types/react-dom | ^19.2 | MIT | tipos (CI) |
| @capacitor/* | ^7.0 | MIT | empacotamento Android/iOS (não instalado neste ambiente) |
Nenhuma biblioteca de roteamento, estado, UI kit, ícones ou gráficos de terceiros no bundle.

## Fontes e ativos
| Ativo | Licença | Observação |
|---|---|---|
| Lora (variável) | SIL OFL 1.1 | `web/public/fonts/lora-variable.ttf`; texto da licença em `OFL-1.1.txt` |
| Inter (subset WOFF) | SIL OFL 1.1 | `inter-Regular/SemiBold.woff` |
| Ícones, favicon, splash, ícone do app | **PRÓPRIO** | gerados programaticamente para este projeto (geometria simples); **marca/logo definitiva e busca de anterioridade no INPI pendentes** |
| Imagens/fotografias | nenhuma | |
| Mapas / SDKs de mapa | nenhum | |
| Datasets / modelos de IA | nenhum embarcado | modelos de terceiros só via API, se o proprietário ativar |

## Serviços externos (opcionais, desligados por padrão)
Stripe (pagamentos) · SMTP transacional · S3-compatível · ClamAV (clamd, GPL-2.0 — **rodado como serviço separado, não incorporado**) · IdP OIDC · API de consulta de CNPJ (a escolher; termos próprios) · Portal da Transparência (API, chave própria) · Anthropic / API compatível OpenAI (termos de uso e política de dados do provedor).
Nenhum foi contratado ou testado com credencial real.

## Conteúdo de terceiros
`history/v0.6.0/sources/Estrategia_Plataforma_Impacto_Social.pdf` (relatório-fonte atribuído a Manus AI) — **direitos de uso a confirmar** (ver `IP_REGISTER.md`). Textos legais citados (leis) são públicos.

## Itens a executar no CI (não executados aqui)
`pip-audit -r backend/requirements.txt` · `npm audit --omit=dev` · SBOM (CycloneDX: `cyclonedx-py`, `@cyclonedx/cyclonedx-npm`) · `pip-licenses`/`license-checker`. **Não houve varredura de vulnerabilidades neste ambiente (rede bloqueada).**
