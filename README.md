# Simulador de Vida — Android (v0.21.0)

Empacotamento Android do Simulador de Vida Brasileiro (**v0.21.0**, `versionCode 2100000`), com código Python em `simulador-vida-android/app/src/main/python/sim`, interface web em `simulador-vida-android/app/src/main/assets/web` e pacote consolidado para download único em `simulador_v0_21_0_android.zip`.

Como funciona: Chaquopy embarca o Python 3.12; `android_launcher.py` sobe o servidor do jogo em `127.0.0.1:8765` e um WebView exibe a interface. Saves ficam em `filesDir/saves` (esquema SQLite v20, compatível com saves v1–v19).

## Pacote único para download e APK
- **Código-fonte completo pronto para build (`v0.21.0`)**: arquivo único `simulador_v0_21_0_android.zip` na raiz do repositório (contém toda a pasta `simulador-vida-android/`).
- **APK Android (`simulador-vida.apk`)**: compilado automaticamente pelo workflow `.github/workflows/build-apk.yml` (**Build APK**) a cada push na branch `main`, tag `v*` ou execução manual (*workflow_dispatch*) e publicado em **Releases → Simulador de Vida - APK mais recente** (e nos artefatos do workflow).

## Build local do APK
Requer JDK 17, Android SDK 34 (`build-tools;34.0.0`), Python 3.12 e Gradle 8.7:
```bash
cd simulador-vida-android
gradle assembleDebug
```
O APK gerado sai em `simulador-vida-android/app/build/outputs/apk/debug/app-debug.apk`.

