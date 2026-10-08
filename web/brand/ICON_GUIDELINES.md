# Icon Guidelines

## Sistema
Ícones UI são SVG 24×24, traço nominal 1.75, caps/joins arredondados, sem preenchimento de fundo e `currentColor`. Tamanhos de uso: 12, 16, 20, 24, 32, 40 e 48 px. O alinhamento é centralizado no viewBox; tamanhos pequenos podem exigir ajuste óptico, não distorção de viewBox. Padrão em UI clara/amarela: navy; em superfícies navy: foreground claro. Amarelo é preenchimento/realce, não cor de texto pequeno sobre branco.

## Consumo acessível
Ícone decorativo junto a texto: `aria-hidden="true"` e sem nome duplicado. Ícone que por si só é o controle precisa nome no botão (`aria-label` ou texto visualmente oculto), e o SVG fica oculto do AT. Em `<img src="icon.svg">`, defina `alt=""` para decorativo ou alt breve se informativo; `currentColor` não herda de forma confiável em SVG externo — prefira inline SVG/React component ou mascaramento CSS quando necessário.

## Catálogo
Veja `icons/icon-catalog.json` (nome, rótulo, caminho). Categorias incluem navegação, impacto, ESG original, Match Engine, projetos, compliance, fiscal, perfis institucionais, administração e padrões de arquivo. Ícones representam metáforas, não status/certificação. Para tipos de perfil, preserve o mesmo sistema visual.

## Critérios de desenho
- Grid 24; traço uniforme 1.75; manter pelo menos 1.5 unidades de respiro interno quando possível.
- Evitar detalhe crítico em 12/16; se item for essencial nessa escala, criar variante de optical-size e registrar.
- Usar nomes kebab-case sem rótulos confusos; a semântica acessível pertence ao contexto funcional, não ao nome do arquivo.
- Ícones continuam distinguíveis por silhueta e texto, e não apenas por cor.
