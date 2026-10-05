# Acessibilidade — estado real

**Não houve auditoria automatizada (axe/Lighthouse) nem teste com leitor de tela neste release.** O que foi feito por construção:
- HTML semântico (`main`, `nav`, `h1–h3`, `table` com `th`, `ol` na trilha), `label` associado a todo campo, `aria-label` em botões de ícone, `aria-busy` em ações, `role="tab"` nos painéis.
- Foco visível, navegação por teclado, link “Pular para o conteúdo”, `prefers-reduced-motion` respeitado, tema claro/escuro.
- Cor nunca é o único sinal (selos têm texto: “Prioritária”, “Bloqueada”); contraste da paleta pensado para AA (**não medido por ferramenta**).
- Gráficos: barras de fluxo do recurso exibem **valores em texto** (alternativa textual nativa); não há gráficos 3D.
- Mensagens de erro em português claro (`field-error` junto ao campo; **associação via `aria-describedby` não verificada**).
**Pendente:** axe no E2E, teste com NVDA/VoiceOver/TalkBack, auditoria WCAG 2.2 AA, legendas/alt em mídias de evidência (upload de imagem exige descrição? — **não implementado**).

## Atualização v0.9.0
Páginas da Biblioteca passam em verificações próprias no Chromium (um `h1`, `main`, controles com rótulo, botões com nome, `lang`). Componente `Group` (fieldset/legend) evita nomes acessíveis poluídos por grupos de chips. Mapa por UF é grade com texto; todas as informações têm equivalente textual. **Não** houve auditoria com axe/leitor de tela nem teste de contraste automatizado.
