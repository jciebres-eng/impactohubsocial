# Accessibility Guidelines — alvo WCAG 2.2 AA

Meta do sistema: WCAG 2.2 AA; isto é um conjunto de tokens e regras, não declaração de conformidade de um produto completo.

## Critérios de implementação e QA
- Texto normal: contraste 4.5:1; texto grande: 3:1. Componentes/estados gráficos necessários: 3:1 contra cores adjacentes (WCAG 1.4.11). Validar tema claro, escuro, high contrast e transparência/composição reais.
- Operação total por teclado, foco visível sem cobrir conteúdo; não remover outline sem substituição. Ordem e foco de modal são geridos no componente.
- Nome, papel e valor acessíveis; label persistente, `aria-describedby` para ajuda/erro; aria-live/role conforme urgência, sem anúncios excessivos.
- Status, badge, match e gráfico não podem depender só da cor. Mensagem também diz qual estado e ação.
- Área alvo de 24×24 CSS px ou espaçamento equivalente sob 2.5.8; preferir 44×44 px em controles comuns/mobile.
- Zoom/reflow: testar 200% e viewport equivalente a 320 CSS px; não exigir rolagem em duas dimensões exceto conteúdo que exige layout (ex. grid/tabela), com alternativa acessível.
- Tempo/motion: oferecer reduzir/parar animação não essencial e respeitar `prefers-reduced-motion`.
- Formularios: erro específico perto do campo, identificação textual do campo, resumo de erros para fluxo longo, preservar dados digitados.
- Tabelas: cabeçalhos programáticos; charts com resumo/dados tabulares acessíveis.

## Limites
Testes automatizados de markup/contraste não provam WCAG conformance. Ainda é necessário teste manual com teclado, leitores de tela (VoiceOver/TalkBack/NVDA), zoom/reflow, alto contraste e auditoria de componentes/fluxos reais antes de qualquer declaração pública.


## Legibilidade reforçada — UX baseline v2.2

Para esta interface, o corpo permanece em 16 CSS px; `small` usa 15 px, `label` 14 px e `caption` 13 px. Rótulos compactos de domínio e badges devem permanecer em pelo menos 12–13 px, ter peso suficiente e espaço interno; controles mobile continuam com alvo de pelo menos 44 × 44 px. Indicadores coloridos aumentam de escala e mantêm identificação textual (cor não comunica estado sozinha). Verificar zoom 200%, contraste e reflow antes do release.
