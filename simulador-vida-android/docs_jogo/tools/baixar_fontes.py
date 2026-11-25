#!/usr/bin/env python3
"""Baixa UnifrakturMaguntia e IM Fell English (Google Fonts, OFL) para web/fonts e gera fonts.css. Precisa de internet.
ATENÇÃO: escrito sem acesso à rede no desenvolvimento — não foi executado. Se falhar, o jogo continua funcionando com fontes do sistema."""
import os, re, urllib.request
DEST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "fonts")
URL = "https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1&family=UnifrakturMaguntia&display=swap"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
def get(u): return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read()
css = get(URL).decode()
for i, u in enumerate(sorted(set(re.findall(r"url\((https://[^)]+\.woff2)\)", css)))):
    nome = f"fonte{i}.woff2"
    open(os.path.join(DEST, nome), "wb").write(get(u))
    css = css.replace(u, nome)
open(os.path.join(DEST, "fonts.css"), "w", encoding="utf-8").write(css)
print("Fontes salvas em", DEST)
