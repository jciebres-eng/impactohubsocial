# Design Tokens

## Fonte canônica
`design-tokens/tokens.json` organiza `primitive`, `semantic` e `component`. Adaptadores: `tokens.css`, `tokens.ts`, `tailwind-theme.css`, `react-native.ts`. Gere por `python3 tools/generate_tokens.py`; mudança manual somente no JSON e script versionado.

## Marca aprovada e contraste
Primária UI `#FFD43B`, com `on-brand-primary` navy `#16233B`. Para texto/link amarelo sobre superfície clara, usar `brand-primary-text` (não o amarelo vivo); tema claro usa base neutra `#F6F8F9` e superfícies brancas; modo escuro navy. Os valores refletem a decisão “amarelo primário”, não uma especificação cromática oficial do titular.

## Consumo
### CSS
```css
@import "./design-tokens/tokens.css";
@import "./components/components.css";
.page { color: var(--pi-color-text-primary); background: var(--pi-color-background-default); }
```
Tema via `document.documentElement.dataset.theme = 'dark'`. Default segue `prefers-color-scheme` quando nenhum atributo foi definido; escolha manual deve persistir no app.

### TypeScript
```ts
import { tokens } from './design-tokens/tokens';
const primary = tokens.semantic.color.light['brand-primary'];
```
O JSON canônico é `as const`, não mapear `tokens` cegamente para estilos CSS.

### Tailwind CSS v4
```css
@import "./design-tokens/tokens.css";
@import "./design-tokens/tailwind-theme.css";
```
As variáveis `@theme inline` expõem utilitários sem duplicar os valores. Sem config específica de Tailwind v3; se o consumidor estiver em v3, mapear as variáveis no `theme.extend` do produto e testar nessa versão.

### React Native
`nativeTokens` usa valores sem CSS custom properties: medidas em rem/px são convertidas para números em dp/pt à razão canônica de 16 px por rem, pesos/line-height permanecem numéricos e transparência é normalizada para `rgba(r, g, b, a)`. Sombras CSS não são incluídas no adaptador. Converter elevação por plataforma explicitamente (Android `elevation`; iOS shadow props); não fingir equivalência perfeita.

## Regras
- Componente usa semântica, não primitiva de rampa.
- Conteúdo não colorido usa cores semânticas text/background; estados precisam `on-*` e fundo apropriado.
- Breakpoints são rem para acessibilidade de zoom; media queries CSS recebem valores e unidades.
- Escala de espaço baseada em múltiplos de 4 px; métricas corporais podem usar densidade, mas preservar hierarquia e target.


## Extensão de produto v2.1
A extensão acrescenta ao JSON canônico `primitive.zIndex` (`sticky`, `header`, `toast`) e `component.control.focus-ring-offset`, usados pela navegação e pelos indicadores de foco do protótipo. Eles não criam uma segunda camada de tokens. Reexecute `python3 tools/generate_tokens.py` após alterações; os quatro adaptadores devem continuar sincronizados.


## Revisão de experiência v2.2
O tema `high-contrast` usa canvas claro, texto navy, foco azul e botão primário navy, sem fundo preto/amarelo. O modo escuro continua independente. A escala canônica de leitura é `body: 16 px`, `small: 15 px`, `label: 14 px` e `caption: 13 px`. O master raster opaco permanece preservado nos assets; o protótipo usa wordmark tipográfico em superfície neutra para evitar exibir sua placa de fundo.
