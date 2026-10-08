# Dark Mode Guidelines

Tema escuro possui semântica própria em `tokens.json`; não aplicar inversão/filters automáticos aos assets. Priorize planos de fundo escuros levemente azulados, superfícies escalonadas e texto claro de alta legibilidade. Sombras têm pouco efeito em dark mode; usar diferença de superfície, contorno e elevação tonal. Verificar foco, disabled, linhas de tabela, charts, overlays e texto secundário. Imagens do logo devem usar variante apropriada; PNGs de marca podem ter fundo sólido e não devem ser tratados como transparentes. Não reduzir contraste para “suavizar” a UI.

Preferência do sistema é default automático enquanto nenhuma escolha manual está em `data-theme`; teste ambas as condições. High contrast é escolha separada e deve preservar informação/status. Atender `prefers-reduced-motion` independentemente do tema.


## Alto contraste claro — UX baseline v2.2

O tema `high-contrast` é uma apresentação **clara**, separada do modo escuro: canvas branco, superfícies neutras, texto navy, bordas evidentes e foco azul. A ação primária passa a ser navy com texto branco; amarelo fluorescente não é usado no tema. Aviso, sucesso, erro e informação continuam semanticamente distintos, com rótulo textual e contraste verificado. O modo escuro permanece um tema navy próprio. Nenhum asset de marca recebe filtro ou inversão automática.
