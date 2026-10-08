# Dependências de terceiros e licenças — v0.18.1

Classificação: **PRÓPRIO** (código/ativos do projeto) · **OSS** (open source incorporado/instalado) · **SERVIÇO** (externo, opcional) · **ASSET** (fonte/ícone/imagem de terceiros).
Licenças dos pacotes Python foram lidas dos metadados instalados neste ambiente em 2026-10-05; as demais, dos termos públicos conhecidos — **confirmar no CI com gerador de SBOM** (ver fim).

## Backend (execução) — `backend/requirements.txt`
| Pacote | Versão | Licença | Classe | Uso |
|---|---|---|---|---|
| starlette | 1.6.0 | BSD-3-Clause | OSS | framework ASGI |
| uvicorn | 0.53.0 | BSD-3-Clause | OSS | servidor ASGI |
| pydantic | 2.13.5 | MIT | OSS | validação |
| PyJWT | 2.15.0 | MIT | OSS | validação de id_token OIDC |
| cryptography | 50.0.1 | Apache-2.0 OR BSD-3-Clause | OSS | Fernet (MFA), RSA/JWKS |
| python-multipart | 0.0.32 | Apache-2.0 | OSS | upload |
| pypdf | 6.19.0 | BSD-3-Clause | OSS | inspeção de PDF enviado |
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

### Estado de verificação (v0.18.1)

| Pacote declarado | Instalado neste ambiente? | Versão conferida | Situação |
|---|---|---|---|
| react, react-dom, scheduler | sim | 19.2.8 | **VERIFIED** (lido de `node_modules/*/package.json`) |
| esbuild | sim | 0.28.2 | **VERIFIED** |
| typescript | sim | 6.0.3 | **VERIFIED** |
| @types/react, @types/react-dom | no CI | 19.3.0 | **VERIFIED (v0.24.1)** — fixado na versão do lockfile; instalado por `npm ci` e usado no typecheck oficial no GitHub Actions |
| @capacitor/cli, /core, /android, /ios | no CI | 7.6.9 | **VERIFIED (v0.24.1)** — fixado na versão do lockfile, instalado por `npm ci` no CI; o empacotamento mobile em si continua não executado |
| @capacitor/preferences | no CI | 7.0.4 | **VERIFIED (v0.24.1)** — idem |

Até a v0.24.0 estes sete estavam em **faixa aberta** e nunca tinham sido instalados, e foram
mantidos assim de propósito: fixar uma versão que ninguém baixou seria inventar a verificação. O
`web/package-lock.json` (versionado na v0.24.0, instalado limpo por `npm ci` no CI) passou a dizer a
versão exata de cada um, e é dela que vem o número fixado — não de escolha.

## Fontes e ativos
| Ativo | Licença | Observação |
|---|---|---|
| Inter (subset WOFF) | SIL OFL 1.1 | `inter-Regular/SemiBold.woff` |
| Logo, ícones de interface, favicons, ícones PWA/Android/iOS (v0.24.0) | **NÃO COMPROVADA** | vêm do pacote `IMPACTO_DESIGN_SYSTEM_FULL_CORRETO_v2.3` (`web/brand/`); o próprio pacote declara que a licença da marca não foi comprovada e que o logo master é raster. Ver `web/brand/ASSET_LICENSE_REGISTER.md`. **Titularidade, vetor oficial e busca de anterioridade no INPI pendentes** |
| Splash do app nativo | derivado | canvas navy com o ícone oficial de 1024 px, sem ampliação (`mobile/resources/`) |
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
