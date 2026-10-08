# Typography Guidelines

Famílias preferidas: IBM Plex Sans para UI e IBM Plex Mono para código/identificadores técnicos, com stack de fallback em `tokens.json`. **Arquivos de fonte não estão incluídos**; carregar fonte licenciada do produto se disponível. Fallback system UI é o modo sem download, evitando bloqueio do primeiro conteúdo.

## Escala base (16 px)
| Estilo | Tamanho | Peso | Line-height sugerida | Uso |
|---|---:|---:|---:|---|
| Display | 48 px | 600 | 1.1–1.2 | Hero editorial, não dashboard comum |
| H1 | 32 px | 700 | 1.2 | Título de página |
| H2 | 24 px | 600 | 1.3 | Seção |
| H3 | 20 px | 600 | 1.3 | Sub-seção/card |
| H4 | 18 px | 600 | 1.35 | Cabeçalho compacto |
| Body | 16 px | 400 | 1.5 | Texto de leitura |
| Small | 15 px | 400 | 1.45 | Metadados legíveis |
| Label | 14 px | 600 | 1.35 | Label com contraste AA |
| Caption | 13 px | 500 | 1.4 | Auxiliar curto, jamais única instrução essencial |
| KPI | 28 px | 700 | 1.2 | Valor numérico tabular + unidade/contexto |

A escala está nos tokens em rem; line-height também. Adotar `font-variant-numeric: tabular-nums` em colunas/KPIs. Evitar uppercase prolongado, texto claro em fundo laranja e pesos light abaixo de 18 px. Validar acentos, `R$`, datas BR, números negativos e truncamento responsivo. Ajustar tamanho com zoom sem cortar conteúdo.
