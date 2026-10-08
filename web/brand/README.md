# Identidade oficial — fonte dentro do produto

Origem: pacote `IMPACTO_DESIGN_SYSTEM_FULL_CORRETO_v2.3` (release `1.2.0-manus.2`, revisões v2.2 e
v2.3), recebido em 2026-10-07. Esta pasta é a **fonte** da identidade no produto; o que a interface
mostra deriva daqui, nunca de cópia solta em `public/`.

## O que está aqui

| Caminho | O que é | Quem consome |
|---|---|---|
| `tokens.json` | Fonte única: cores primitivas e semânticas (claro, escuro, alto contraste), tipo, espaço, raio, sombra, movimento, componentes | `generate_tokens.py` |
| `tokens.css` | **GERADO** de `tokens.json` — não editar à mão | `src/styles.css` (`@import`) |
| `generate_tokens.py` | Gerador, só biblioteca padrão. Adaptado do original: gera só o CSS (não há consumidor Tailwind/RN aqui) e corrige o `color-scheme` do alto contraste (ver docstring) | teste `test_v0240_brand_gate.py` exige `tokens.css` == saída |
| `components.css` | Base de componentes `.pi-*` (botão, campo, cartão, badge, tabela, alerta, KPI). Importado depois dos tokens; o produto usa as próprias classes, mas sobre os mesmos tokens | `src/styles.css` |
| `icon-catalog.json`, `icons/**` | 75 ícones de traço, 24×24, `currentColor` | `src/ui/icon.tsx` (inline) |
| `impacto-reference-303x240.png` | O lockup como foi recebido (raster, fundo navy opaco). Preservado; não é exibido | registro |
| `mobile/android`, `mobile/ios` | mipmaps, adaptive icon e `AppIcon.appiconset` oficiais, com os READMEs de origem | `mobile/setup.sh` (Capacitor) e projeto Xcode |
| `*_GUIDELINES.md`, `TRANSPARENT_ASSETS.md`, `ASSET_LICENSE_REGISTER.md`, `DESIGN_TOKENS.md` | Os guias de origem, inalterados | quem for desenhar |

O que é **servido** mora em `public/`: `public/brand/` (lockups transparentes e favicons),
`public/icons/` (PWA 192/512/maskable e Apple Touch), `public/favicon.ico`, `public/offline.html`.
Os recursos do app nativo estão em `../mobile/resources/` (ícone 1024, foreground, splash).

## Como a identidade entra na interface

`src/styles.css` não foi reescrito regra a regra: os nomes que ele sempre usou (`--tinta`, `--ipe`,
`--papel`, `--mata`, `--barro`…) viraram **aliases** dos `--pi-*`. Assim todas as regras de
componente vestem a identidade de uma vez, nos três temas, e uma mudança em `tokens.json` chega a
toda a interface por `python3 web/brand/generate_tokens.py` + build. O cabeçalho de `styles.css`
documenta cada alias e as três regras da marca que ele cumpre (amarelo é ação, nunca fundo; nunca
texto branco sobre amarelo; barra lateral navy em qualquer tema).

A marca é imagem (`src/ui/brand.tsx`), escolhida pela superfície: traços brancos sobre navy, traços
navy sobre claro, e `auto` lê o tema. Tamanhos ficam dentro do que o guia permite para um raster de
157×151 px. Nenhum traço da marca é desenhado em CSS.

## O que a fonte declara sobre si mesma — e vale aqui sem suavizar

- **Licença da marca não comprovada.** `ASSET_LICENSE_REGISTER.md` diz; ninguém neste repositório
  pode comprová-la. Antes de distribuição comercial: titularidade e vetor oficial com o responsável.
- **Logo master é raster** (303×240). O símbolo de 1024 px é ampliação assistida, revisada
  visualmente — não é vetor oficial. Por isso a splash do app nativo é um canvas navy com o ícone de
  1024 no tamanho nativo, e não o lockup ampliado.
- **Fontes não embarcadas.** Família preferida: IBM Plex Sans / IBM Plex Mono. O stack oficial lista
  Inter em segundo, e Inter é o que o produto embarca (OFL). Logo, o que renderiza hoje é Inter;
  IBM Plex Sans entra quando for embarcada (OFL também — depende só de rede para baixar).
- **Não inclui** biblioteca React, charting, projeto Android/Xcode, splash ou traduções. Nada disso
  foi inventado aqui.

## Regenerar

```bash
python3 web/brand/generate_tokens.py     # tokens.json → tokens.css
cd web && node build.mjs                 # bundle com a identidade
```
