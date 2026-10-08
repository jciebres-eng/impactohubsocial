#!/usr/bin/env bash
# Gera os projetos nativos Android/iOS (Capacitor) a partir do build web. Requer acesso ao npm,
# JDK 21 e Android SDK 35 (exigências do Capacitor 7) (Android) ou macOS + Xcode (iOS). NÃO foi executado no ambiente de build deste release.
set -euo pipefail
: "${IMPACTO_API_BASE:?defina IMPACTO_API_BASE=https://SEU-DOMINIO (API em produção)}"
cd "$(dirname "$0")/../web"
npm install
IMPACTO_API_BASE="$IMPACTO_API_BASE" node build.mjs
[ -d android ] || npx cap add android
[ "$(uname)" = "Darwin" ] && { [ -d ios ] || npx cap add ios; }
npx --yes @capacitor/assets generate --assetPath ../mobile/resources --iconBackgroundColor '#16233B' --splashBackgroundColor '#16233B' || true
npx cap sync
echo "Android: cd web/android && ./gradlew bundleRelease   (assinatura: ver docs/MOBILE.md)"
echo "iOS:     npx cap open ios   (Xcode → Archive)"
