# Brand Guidelines — Plataforma de Impacto

## Identidade aprovada
A referência vigente é o logo raster enviado pelo responsável do projeto, preservado sem alteração em `brand/logos/impacto-reference.png` (303×240 px). O símbolo sozinho está em `brand/marks/impacto-isotipo-master.png` (ampliação assistida por IA, revisada visualmente; não é vetor oficial). A família anterior “Convergência” foi movida integralmente para `brand/archive/convergencia-pre-refresh/` e não deve ser usada como padrão.

## Paleta da interface (direção aprovada)
- **Primária amarela:** `#FFD43B`; cor de preenchimento para ação principal/realce, nunca usar texto branco sobre amarelo.
- **Navy:** `#16233B`; texto/ícone sobre amarelo, cor secundária de marca e superfícies estruturais escuras.
- **Verde da referência:** `#A7D93D`; acento/realce, com texto navy.
- **Azul da referência:** `#18B6E6`; acento informativo, com texto navy. O logo fornecido permanece intocado e conserva as cores que aparecem na imagem.
- A tonalidade amarela acima foi escolhida para operacionalizar “amarelo primário”; pode ser ajustada em `tokens.json` sem mudar o logo. O amarelo é usado em CTAs e destaques, não como cor de fundo da interface. Contraste de texto navy/amarelo primário: ~11:1; texto escuro seguro sobre fundo branco usa `brand-primary-text`.
- Fundos claros voltam à base neutra `#F6F8F9` com superfícies brancas e cinza-claro; amarelo fica em CTAs/realces. O modo escuro permanece navy. Status (sucesso/atenção/erro/info) preserva semântica própria, nunca comunica apenas por matiz.

## Uso do logo
- Usar o PNG mestre fornecido sem recolorir, recortar, distorcer, reconstruir texto, aplicar filtros nem mudar proporções. Ele tem fundo navy opaco: posicioná-lo sobre fundo navy correspondente ou manter a placa escura como parte intencional do lockup.
- Evitar ampliar o lockup raster para além dos 303 px nativos; o pacote inclui uma versão assistida por IA do símbolo para derivados quadrados, não uma master vetorial autenticada.
- Para impressão, tamanhos acima do mestre ou ajustes da identidade, solicitar ao titular o vetor original (SVG/PDF/AI) em alta resolução, a paleta HEX oficial e prova de licença/cessão. A ampliação automatizada não substitui a aprovação de marca.
- Ícone de app/favicon usa o símbolo isolado, sem a palavra “IMPACTO”; manter fundo navy e as cores originais do símbolo.

## Ícones de produto
Os 75 ícones SVG da interface continuam sendo ícones de traço `currentColor`, em grid 24×24. Padrão: navy em superfícies claras/amarelas, claro em superfícies navy/escuro. Não colorir o catálogo inteiro de amarelo nem depender somente da cor para estados; adotar rótulo/texto e pairing acessível. SVG externo via `<img>` pode não herdar `currentColor`; prefira inline/component.

## Escalas e áreas
O símbolo foi testado em 16/32/48/180 px e em renderizações de preview para 512/1024; o PNG de app é 1024×1024. As miniaturas 512/1024 no painel de QA são deliberadamente reduzidas para caber na folha; os arquivos nativos mantêm as dimensões declaradas. Em tamanhos pequenos, usar o símbolo, não o lockup com texto.

## Procedência e limites
O logo raster atual veio do usuário; o pacote original também tinha arte de uma identidade anterior, agora arquivada. A titularidade/licença comercial ainda não foi comprovada. Ícones e PNGs foram gerados/derivados para este pacote; revisar originalidade/trademark e obter aceite do titular antes de distribuição comercial. Esta nota não é parecer jurídico.


## Aplicação no protótipo — v2.2

No protótipo, a marca aparece como wordmark tipográfico IMPACTO ampliado sobre a superfície neutra da navegação, com um traço discreto em cores da paleta. O raster opaco é omitido em todos os temas do protótipo; assim não há placa preta nem faixa escura atrás do logo. Mobile e alto contraste seguem a mesma direção text-first. Os masters originais permanecem intactos no pacote e disponíveis para uso quando houver uma variante transparente/vetorial aprovada.


## Aplicação SaaS e variantes transparentes — v2.3

A pedido do responsável, os masters raster opacos continuam preservados e o pacote inclui PNGs RGBA derivados com transparência real. Os arquivos full-canvas de 303×240 px preservam a origem; as variantes tight-cropped de 157×151 px removem apenas as margens transparentes e são usadas na interface, até 135×130 CSS px no sidebar e 74 CSS px no header móvel — sem ampliar além do raster. A variante clara converte os traços/letras brancos para navy `#16233B`; a variante `dark-surface` preserva o branco para a própria superfície navy. Nenhuma placa escura está embutida nas imagens.

O sidebar segue a referência SaaS indicada: navegação navy, canvas claro, cards/KPIs e área analítica. A logomarca é a imagem transparente aplicada à superfície do sidebar — essa superfície não foi adicionada à imagem. O tema escuro usa a variante adequada à superfície; o alto contraste mantém canvas claro, sem preto/amarelo fluorescente.

Os PWA usam PNGs transparentes de 192×192 e 512×512 (`any`) e 512×512 (`maskable`, com margem segura). Favicons de 16/32/48 px, ICO e Apple Touch Icon de 180 px também estão incluídos. Os ícones PWA e favicons opacos originais permanecem preservados. Ver `brand/TRANSPARENT_ASSETS.md` e `tools/prepare_transparent_brand_assets.py`.

Limitação de origem: o lockup veio como raster de 303×240 px, não como SVG/PDF/AI oficial; por isso o PNG transparente não é anunciado como vetor e não é ampliado por interpolação.