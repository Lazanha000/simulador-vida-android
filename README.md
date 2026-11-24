# Simulador de Vida — Android

Empacotamento Android do Simulador de Vida Brasileiro (v0.14.4). O código do jogo (`app/src/main/python/sim`, `main.py`, `app/src/main/assets/web`) é o original, sem alterações.

Como funciona: Chaquopy embarca o Python 3.12; `android_launcher.py` sobe o servidor do jogo em `127.0.0.1:8765` e um WebView mostra a interface. Saves ficam em `filesDir/saves` e também são gravados ao sair do app.

## Baixar o APK
Aba **Releases** → "Simulador de Vida (APK mais recente)" → `simulador-vida.apk`. No celular, permita "instalar apps desconhecidos" e abra o arquivo.

## Build
O GitHub Actions compila a cada push na `main` (workflow `Build APK`). Local: JDK 17, Android SDK, Python 3.12 e Gradle 8.7 → `gradle assembleDebug`.

Para atualizar o jogo: substitua `sim/`, `main.py` e `assets/web/` e ajuste `versionCode`/`versionName` em `app/build.gradle.kts`.
