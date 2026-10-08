# Assets transparentes da marca IMPACTO — v2.3

## Arquivos entregues

| Uso | Arquivo | Dimensão / formato | Fundo | Observação |
|---|---|---:|---|---|
| Lockup full-canvas para superfícies claras | `brand/logos/impacto-logo-transparent.png` | 303×240 PNG RGBA | Transparente | Canvas completo do raster; branco adaptado para navy `#16233B` |
| Lockup full-canvas para superfícies navy | `brand/logos/impacto-logo-transparent-dark-surface.png` | 303×240 PNG RGBA | Transparente | Canvas completo; cores originais da arte |
| Lockup tight para superfícies claras | `brand/logos/impacto-logo-transparent-tight.png` | 157×151 PNG RGBA | Transparente | Recorte das margens vazias; variante usada no header móvel claro |
| Lockup tight para superfícies navy | `brand/logos/impacto-logo-transparent-dark-surface-tight.png` | 157×151 PNG RGBA | Transparente | Recorte das margens vazias; variante usada no sidebar e header móvel escuro |
| Isotipo para superfícies claras | `brand/marks/impacto-isotipo-transparent.png` | 1254×1254 PNG RGBA | Transparente | Master raster; branco adaptado para navy |
| Isotipo para superfícies navy | `brand/marks/impacto-isotipo-transparent-dark-surface.png` | 1254×1254 PNG RGBA | Transparente | Cores claras originais preservadas |
| Ícone de app | `brand/app-icons/app-icon-1024-transparent.png` | 1024×1024 PNG RGBA | Transparente | Derivado do isotipo, pronto para catálogo/app |
| Ícone PWA | `pwa/icon-192-transparent.png` | 192×192 PNG RGBA | Transparente | Manifesto, `purpose: any` |
| Ícone PWA | `pwa/icon-512-transparent.png` | 512×512 PNG RGBA | Transparente | Manifesto, `purpose: any` |
| Ícone PWA mascarável | `pwa/maskable-512-transparent.png` | 512×512 PNG RGBA | Transparente | Símbolo reduzido para margem segura da máscara |
| Favicons | `brand/favicon/favicon-{16,32,48}-transparent.png` | 16, 32, 48 px PNG RGBA | Transparente | Navegadores e atalhos |
| Favicon multirresolução | `brand/favicon/favicon-transparent.ico` | 16/32/48 ICO | Transparente | Compatibilidade desktop |
| Apple Touch Icon | `brand/favicon/apple-touch-icon-180-transparent.png` | 180×180 PNG RGBA | Transparente | Atalho iOS/Safari |

Os ícones PWA opacos navy e os mestres raster recebidos foram preservados nos nomes originais; o manifesto e o protótipo passam a apontar para os derivados transparentes.

## Uso no produto

- Sidebar navy: use a variante `*-dark-surface.png`, com o arquivo realmente transparente sobre a própria superfície do sidebar — não existe placa escura embutida na imagem.
- Canvas claro: use `impacto-logo-transparent.png`; a troca de branco por navy é uma adaptação derivada para manter leitura sem fundo escuro.
- Em superfícies escuras, não use a variante clara; em superfícies claras, não use as letras brancas da variante escura.
- Os arquivos full-canvas de 303×240 px preservam todo o raster; as variantes tight-cropped (157×151 px) removem somente o espaço transparente ao redor. O sidebar usa a variante tight a até 135×130 CSS px, abaixo do tamanho nativo; o header móvel usa até 74 CSS px. Assim o desenho aparece maior sem interpolação ampliada.
- PNG é o formato transparente efetivamente disponível. O pacote recebido não continha um master vetorial autenticado; não se apresenta raster incorporado em SVG como se fosse vetor.
- A titularidade/licença comercial dos materiais de origem continua pendente de comprovação, conforme o registro original.

## Reprodução

Com Pillow e NumPy instalados, execute na raiz do pacote:

```bash
python3 tools/prepare_transparent_brand_assets.py
```

O script não altera os arquivos mestres; ele remove o matte navy da rasterização e exporta as variantes e dimensões listadas acima. Confira `BRAND_GUIDELINES.md` e `pwa/manifest.webmanifest` para o contrato de aplicação.