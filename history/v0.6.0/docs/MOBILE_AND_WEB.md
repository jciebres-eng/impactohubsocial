# Web, PWA e mobile

**Decisão:** web responsiva + PWA primeiro (ADR-002). Nativo só com necessidade demonstrada (push, offline, câmera de campo).

## Web/PWA — checklist
manifest, ícones, service worker com rascunho resiliente, upload móvel, deep links/convites, estados de loading/erro/vazio, SEO nas páginas públicas, navegação por teclado, contraste, labels, leitor de tela, bundle enxuto, imagens otimizadas, funcionamento em conexão fraca.

## Nativo (se e quando)
React Native (reuso TS) ou Flutter — escolher após prova de necessidade. Conta de loja na **organização**, keystore em vault, permissões mínimas, Data Safety / privacy label iguais ao backend e ao inventário de SDKs, exclusão de conta no app e por URL, TestFlight/testes internos.
**Compras/assinaturas dentro de apps nativos podem estar sujeitas às regras de pagamento das lojas — conferir políticas vigentes antes de decidir [VALIDAR].**

## Estados de publicação
Ready for build → Built → Tested → Signed → Submitted → Approved → Published. Nada acima de "documentado" foi atingido.
