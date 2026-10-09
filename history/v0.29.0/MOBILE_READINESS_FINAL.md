# Prontidão para mobile (v0.16.0)

Avaliação honesta. **VERDE** = provado por execução ou teste. **AMARELO** = código pronto, falta ação externa ou
validação independente. **VERMELHO** = ausente.

## Quadro

| Item | Estado | Evidência / o que falta |
|---|---|---|
| API consumível por app nativo (Bearer, sem depender de cookie) | **VERDE** | `auth="user"` aceita `Authorization: Bearer`; refresh rotativo; 704 rotas |
| PWA (manifest, service worker, offline) | **VERDE** | `web/public/manifest.webmanifest`, `sw.js` gerado no build com pré-cache, `offline.html`; registro desligado quando roda sob Capacitor |
| Layout responsivo das telas antigas | **VERDE** | 25 combinações de página × viewport verificadas sem rolagem horizontal a 390 px (v0.12.1) |
| Layout responsivo das **27 telas novas** | **AMARELO** | usam as mesmas classes e grades, mas **não** passaram pela verificação automática de viewport desta rodada |
| Contraste AA (claro e escuro) | **VERDE** | verificação automática nos dois temas (v0.12.1) |
| Acessibilidade com `axe` e leitor de tela | **AMARELO** | nunca executado; `axe` não instalável neste ambiente (registro npm bloqueado) |
| Navegação móvel | **AMARELO** | gaveta deslizante funcional; a barra inferior de cinco destinos é entrega de design (`NAVIGATION_MODEL.md` §6) |
| Empacotamento Android/iOS (Capacitor) | **AMARELO** | `mobile/setup.sh` existe; **nunca compilado, nunca assinado, nunca enviado** |
| Notificação push no aparelho | **VERMELHO** | o produto tem notificação **no produto** (14 grupos, fan-out para a equipe), com preferência por grupo e canal. **Push nativo não existe**: não há FCM, não há APNs, não há token de dispositivo |
| Compra dentro do app (Apple/Google) | **VERMELHO / decisão do proprietário** | a cobrança é web (Stripe). As regras de compra das lojas **não foram analisadas** e podem exigir compra in-app para assinatura digital |
| Rótulos de privacidade das lojas | **AMARELO** | exclusão de conta e exportação existem como rota; os formulários "Data safety" e "App Privacy" **não** foram preenchidos |
| Textos legais | **AMARELO** | minutas sem revisão jurídica |

## O que mudou nesta rodada, do ponto de vista mobile

**A favor:**

* O `WorkspaceContext` é **uma** chamada que devolve tudo o que a tela de abertura precisa, ordenado pelo servidor.
  Isso é exatamente o que um app nativo precisa — e é o oposto de dez requisições para montar um painel.
* `capabilities` deixa o cliente esconder o que a pessoa não pode fazer **sem** adivinhar regra de papel.
* Taxonomias vêm do servidor, versionadas. O app não precisa de atualização de loja para receber uma causa nova.
* As preferências de notificação já têm granularidade por grupo **e canal**, então quando o push nativo existir, a
  pessoa já tem onde desligá-lo.

**Contra:**

* São **27 telas novas** sem passagem pela verificação de viewport. O risco concreto são as tabelas largas: caixa de
  propostas, grafo da rede e a matriz de prontidão por finalidade.
* O workspace da OSC custa **341 ms** na escala cheia. Em rede móvel ruim, isso soma à latência de rede num ponto que
  é a primeira tela do produto.
* A navegação plana de 36 itens é pior no telefone do que no desktop.

## O caminho para publicar, em ordem

1. Design: navegação móvel e tratamento visual das 27 telas (`NAVIGATION_MODEL.md`, `DESIGN_HANDOFF_FINAL.md`).
2. Verificação de viewport e `axe` nas telas novas, em CI com registro npm liberado.
3. Decidir compra in-app: é decisão comercial e jurídica do proprietário, não técnica.
4. Push nativo, se for requisito: FCM + APNs, tabela de token de dispositivo, e o canal `push` acrescentado às
   preferências que já existem.
5. Compilar e assinar: keystore Android e conta Apple Developer (exige macOS).
6. Preencher rótulos de privacidade, publicar política em domínio próprio, revisão jurídica.
7. Auditoria de dependências (`npm audit`, `pip-audit`) — **bloqueada neste ambiente**, obrigatória em CI.

## Conclusão honesta

**Pronto para receber design e para publicação web.** **Não pronto para as lojas** — e a lacuna não é de API nem de
banco: é empacotamento assinado, decisão de monetização nas lojas, push nativo e revisão jurídica. Nada disso foi
simulado em lugar nenhum do código.
