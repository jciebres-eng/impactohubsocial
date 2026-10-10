# Relatório de acessibilidade — v0.18.1

> Conferido **no navegador** (Chromium via Playwright) contra a SPA compilada, com o estilo
> COMPUTADO — não com os tokens do CSS, que é onde esse tipo de verificação costuma passar quando
> não deveria. Arquivo de teste: `backend/tests/test_e2e_v0181_accessibility.py`.

## 1. O que foi verificado, e com que resultado

| # | Verificação | Critério | Situação |
|---|---|---|---|
| 1 | Todo controle de formulário tem nome acessível | WCAG 1.3.1 / 4.1.2 | 🟢 `label`, `aria-label` ou `aria-labelledby` em 100% dos controles visíveis |
| 2 | Erro de formulário é anunciado | WCAG 4.1.3 | 🟢 contêiner com `role=alert` / `aria-live` recebe a mensagem |
| 3 | Atalho "pular para o conteúdo" é a **primeira** parada do Tab | WCAG 2.4.1 | 🟢 e o destino `#conteudo` existe |
| 4 | Navegação só por teclado, sem armadilha de foco | WCAG 2.1.1 / 2.1.2 | 🟢 12 Tabs seguidos terminam sempre em elemento focável |
| 5 | Foco visível (não removido por CSS) | WCAG 2.4.7 | 🟢 `outline` ou `box-shadow` presentes no elemento ativo |
| 6 | Marcos de página e um único `h1` | WCAG 1.3.1 | 🟢 `main`, `nav`, `h1` único, `lang="pt-BR"`, `title` presente |
| 7 | Alternativa textual em imagem e em botão só-ícone | WCAG 1.1.1 | 🟢 nenhum `img` sem `alt`; nenhum controle sem texto nem `aria-label` |
| 8 | Contraste calculado, tema claro | WCAG 1.4.3 (AA) | 🟢 toda amostra ≥ 4,5:1 (ou ≥ 3:1 quando texto grande) |
| 9 | Contraste calculado, tema escuro | WCAG 1.4.3 (AA) | 🟢 idem, com o fundo que o navegador realmente aplicou |
| 10 | Sem rolagem horizontal em 390px | WCAG 1.4.10 | 🟢 |
| 11 | Alvo de toque ≥ 24×24 | WCAG 2.5.8 (AA, 2.2) | 🟢 |
| 12 | Preferência por menos movimento respeitada | WCAG 2.3.3 | 🟢 `prefers-reduced-motion` zera transições |

## 2. O que NÃO foi verificado, e por quê

| Item | Situação | Motivo |
|---|---|---|
| **`axe-core`** | **NOT VERIFIED** | o registry npm responde `403 Forbidden` neste ambiente; sem instalar a biblioteca nem injetá-la de CDN, chamar o que está acima de "auditoria axe" seria mentira. O conjunto implementado cobre um subconjunto do que o axe checa, calculado à mão. |
| **Leitor de tela real** (NVDA, VoiceOver, Orca) | **NOT VERIFIED** | exige sistema operacional com o leitor instalado e operação manual. O que foi verificado é a estrutura que o leitor consome (nome acessível, marcos, `aria-live`), não a experiência auditiva. |
| **Segundo navegador** (Firefox/WebKit) | **NOT VERIFIED** | só Chromium está instalado aqui. |
| **Zoom de texto a 200%** | **NOT VERIFIED** | não exercitado; o layout usa unidades relativas, mas isso não é prova. |
| **Daltonismo / simulação de visão** | **NOT VERIFIED** | nenhuma informação depende **só** de cor na interface atual (as situações têm rótulo textual), mas não houve verificação dedicada. |
| **Navegação por voz** | **NOT VERIFIED** | — |

## 3. Como completar antes da publicação

```bash
# com acesso a registry:
cd web && npm i -D @axe-core/playwright
# e no teste, injetar o axe na página autenticada e falhar em qualquer violação "serious"/"critical"
```

Enquanto isso não for feito, a conformidade declarada desta versão é **o subconjunto da tabela 1**,
e nada além disso. É uma base real — nenhum dos doze itens é promessa — mas não substitui a
auditoria completa nem o teste com pessoas usuárias de tecnologia assistiva, que é o que de fato
decide se a interface é usável.
