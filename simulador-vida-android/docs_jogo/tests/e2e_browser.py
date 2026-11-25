"""Teste ponta a ponta no navegador (opcional; exige `pip install playwright` + `playwright install chromium`).

Sobe o servidor em processo, joga pelo Chromium headless, confere que não houve erro de JavaScript e salva capturas
de tela em --saida. Não faz parte do `unittest discover` (o nome não começa com `test`).
Uso: python3 tests/e2e_browser.py [--saida /tmp/shots] [--headed]
"""
import argparse
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright  # noqa: E402

from sim import engine, ui_web  # noqa: E402

PAINEIS = ["ficha", "escola", "bens", "relacoes", "trabalho", "saude", "bemestar", "cognicao", "social", "familia",
           "arvore", "biografia", "empresas", "panorama", "impostos", "seguro", "personagens", "config"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default="/tmp/shots")
    ap.add_argument("--headed", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.saida, exist_ok=True)
    pasta = tempfile.mkdtemp()
    srv, app = ui_web.criar_servidor(pasta, porta=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    problemas = []
    shot = lambda pg, n: pg.screenshot(path=os.path.join(a.saida, n))  # noqa: E731

    with sync_playwright() as p:
        b = p.chromium.launch(headless=not a.headed)
        pg = b.new_page(viewport={"width": 430, "height": 820})
        pg.on("pageerror", lambda e: problemas.append(f"pageerror: {e}"))
        pg.on("console", lambda m: m.type == "error" and "ERR_NAME_NOT_RESOLVED" not in m.text and problemas.append(f"console: {m.text}"))
        pg.goto(url)
        pg.wait_for_selector(".tit-botoes")

        # --- partida com um adulto de 32 anos ---
        pg.click("text=Novo jogo")
        pg.fill("input[type=text] >> nth=0", "Adulto Teste")
        pg.click(".seg >> nth=0 >> text=Personagem")
        pg.fill("input[type=number] >> nth=0", "32")
        pg.click(".rodape .btn >> nth=0")
        pg.wait_for_selector(".feed")
        for _ in range(3):   # 3 anos
            pg.click("#selo")
            pg.click(".bandeja button >> nth=2")
            pg.wait_for_timeout(1800)
            if pg.query_selector(".fundo"):
                pg.click(".fundo .btn")
        shot(pg, "10_adulto_jogo.png")

        for nome in PAINEIS:
            app_painel = nome
            pg.click(".pill")
            pg.wait_for_selector(".grade")
            pg.evaluate("n => document.querySelector('.sheet')?.remove()", None)   # fecha o menu sem depender do botão
            # abre o painel diretamente pelo mesmo caminho do menu/nav
            if nome in ("ficha",):
                pg.click("#av")
            elif nome in ("escola", "bens", "relacoes", "trabalho"):
                pg.click(f".nb >> nth={['escola','bens','relacoes','trabalho'].index(nome)}")
            else:
                pg.click(".pill")
                pg.wait_for_selector(".grade")
                rotulos = {"saude": "Saúde", "bemestar": None, "cognicao": "Mente", "social": "Social", "familia": "Família",
                           "arvore": "Árvore", "biografia": "Biografia", "empresas": "Empresas", "panorama": "Panorama",
                           "impostos": "Impostos", "seguro": "Proteção", "personagens": None, "config": "Ajustes"}
                r = rotulos[nome]
                if r is None:   # bem-estar abre pela barra; personagens pelo Ajustes
                    pg.click(".grade button >> text=Ajustes") if nome == "personagens" else pg.evaluate("document.querySelector('.grade')?.closest('.sheet')?.remove()")
                    if nome == "personagens":
                        pg.wait_for_selector(".sheet .btn >> text=Personagens")
                        pg.click(".sheet .btn >> text=Personagens")
                    else:
                        pg.click(".bar >> nth=4")
                else:
                    pg.click(f".grade button >> text={r}")
            pg.wait_for_selector(".sheet .corpo .bloco, .sheet .corpo .ger", timeout=8000)
            pg.wait_for_timeout(350)
            shot(pg, f"20_painel_{nome}.png")
            while pg.query_selector(".sheet"):
                pg.evaluate("document.querySelectorAll('.sheet').forEach(s => s.remove())")
            del app_painel

        b.close()
    srv.shutdown()
    print("PROBLEMAS:", problemas or "nenhum")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
