# Simulador de Vida — Android (v0.20.0)

Empacotamento Android do Simulador de Vida Brasileiro (**v0.20.0**). O código do jogo está em `app/src/main/python/sim`, `app/src/main/python/main.py` e `app/src/main/assets/web`.

Como funciona: Chaquopy embarca o Python 3.12; `android_launcher.py` sobe o servidor do jogo em `127.0.0.1:8765` e um WebView exibe a interface. Saves ficam em `filesDir/saves` (esquema SQLite v19, retrocompatível com saves v1–v18).

## Executar e testar no PC
- Interface web local: `PYTHONPATH=app/src/main/python python3 app/src/main/python/main.py`
- Modo CLI: `PYTHONPATH=app/src/main/python python3 app/src/main/python/main.py --cli`
- Suíte de testes: `PYTHONPATH=app/src/main/python:docs_jogo python3 -m unittest discover -s docs_jogo/tests -t docs_jogo -v`

## Baixar o APK
Aba **Releases** → "Simulador de Vida - APK mais recente" → `simulador-vida.apk`. No celular, permita "instalar apps desconhecidos" e abra o arquivo.

## Build
O GitHub Actions compila a cada push na `main` (workflow `Build APK` em `../.github/workflows/build-apk.yml`). Build local: JDK 17, Android SDK 34, Python 3.12 e Gradle 8.7 → `gradle assembleDebug`.

