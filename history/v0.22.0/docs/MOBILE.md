# Mobile (Android / iOS) — status honesto

| Etapa | Android | iOS |
|---|---|---|
| CODE READY (app web empacotável, ícones, splash, deep links, modo token) | ✅ | ✅ |
| Projeto nativo gerado (`cap add`) | ❌ não gerado neste ambiente | ❌ (exige macOS) |
| BUILD (AAB/IPA) | ❌ não executado (sem Android SDK/Gradle/Maven; sem Xcode) | ❌ |
| TESTED em dispositivo/emulador | ❌ | ❌ |
| SIGNED / SUBMITTED / APPROVED / PUBLISHED | ❌ | ❌ |

**Nenhum app foi compilado, assinado ou publicado.** O que existe é o caminho reproduzível.

## Abordagem
Capacitor 7 envolve o **mesmo build web** (`web/dist`). Escolha pragmática para piloto: uma base de código, mesmo conjunto de testes.
Se o produto exigir recursos nativos pesados (mapas offline, push rico, câmera avançada), reavaliar React Native/Flutter.

- `web/capacitor.config.json`: `appId br.org.impacto.app` (**configurável — troque antes de publicar**), `appName Impacto`.
- Autenticação no app: `X-Auth-Mode: token` → tokens Bearer (sem cookies); `native.ts` guarda em `@capacitor/preferences`.
  **Pendência de segurança:** migrar para armazenamento seguro (Keychain/Keystore, ex. plugin de secure storage) antes de produção.
- API: `IMPACTO_API_BASE=https://SEU-DOMINIO` embutido no build; CORS deve permitir as origens do app (`capacitor://localhost`, `https://localhost`) em `CORS_ORIGINS`.
- Deep links: `mobile/templates/assetlinks.json` (Android App Links) e `apple-app-site-association` (iOS), + `AndroidManifest-intent-filter.xml`. Preencher fingerprint SHA-256 da chave de assinatura e Team ID e hospedar em `/.well-known/` do domínio.
- Ícones/splash: `mobile/resources/` (`@capacitor/assets`).

## Gerar os projetos nativos
```bash
export IMPACTO_API_BASE=https://app.seudominio.org
bash mobile/setup.sh        # npm install, build web, cap add android (e ios no macOS), assets, cap sync
cd web/android && ./gradlew bundleRelease      # JDK 21 + Android SDK 35
npx cap open ios                                # Xcode → Archive (macOS)
```

## Assinatura e lojas (ações do proprietário)
- **Google Play**: conta de desenvolvedor, criar keystore de upload (guardar fora do git), Play App Signing, formulário **Data safety**, política de privacidade pública (usar `docs/legal/PRIVACY_POLICY.md` após validação jurídica), testes fechados exigidos para contas novas.
- **App Store**: Apple Developer Program, certificados/perfis, **App Privacy** (nutrition labels), política de privacidade, conta de teste para revisão, justificativa de login/conta (exclusão de conta já existe: `POST /v1/privacy/delete-account` — exigência da Apple).
- Pagamentos: se a assinatura for vendida **dentro** do app, as lojas podem exigir compra no app; hoje a cobrança é feita na web (Stripe Checkout). Validar política vigente de cada loja antes da submissão.
- Push, mapas e câmera: **não implementados** (sem plugin, sem backend de push).

## PWA (web)
`manifest.webmanifest`, ícones 192/512/maskable, Service Worker com precache do shell e página offline; `/v1` nunca é cacheado. Instalável em Android/iOS via navegador como alternativa imediata às lojas.
