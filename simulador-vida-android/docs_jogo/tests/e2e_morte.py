"""Teste ponta a ponta (opcional, Playwright) da tela de morte SEM herdeiros: botões 'Novo personagem' e 'Voltar ao título'.

Uso: python3 tests/e2e_morte.py [--saida /tmp/shots]
"""
import argparse
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright  # noqa: E402

from sim import ui_web  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default="/tmp/shots")
    a = ap.parse_args()
    os.makedirs(a.saida, exist_ok=True)
    def servidor() -> str:   # uma partida por servidor: cada cenário sobe o seu
        srv, _ = ui_web.criar_servidor(tempfile.mkdtemp(), porta=0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{srv.server_address[1]}/"
    problemas, falhas = [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 430, "height": 820})
        pg.on("pageerror", lambda e: problemas.append(f"pageerror: {e}"))
        pg.on("console", lambda m: m.type == "error" and "ERR_NAME_NOT_RESOLVED" not in m.text and problemas.append(f"console: {m.text}"))

        def comecar():
            pg.goto(servidor())
            pg.wait_for_selector(".tit-botoes")
            pg.click("text=Novo jogo")
            pg.click(".seg >> nth=0 >> text=Personagem")
            pg.fill("input[type=number] >> nth=0", "108")
            pg.click(".rodape .btn >> nth=0")
            pg.wait_for_selector(".feed")
            for _ in range(10):
                pg.click("#selo")
                pg.click(".bandeja button >> nth=2")
                pg.wait_for_timeout(1500)
                if pg.query_selector(".faixa-luto"):
                    return True
                if pg.query_selector(".fundo"):
                    pg.click(".fundo .btn")
            return False

        # 1) 'Novo personagem' abre o painel Personagens
        if not comecar():
            falhas.append("o personagem de 108 anos não morreu em 10 anos")
        else:
            rotulos = [t.strip() for t in pg.locator(".fundo .acoes button").all_inner_texts()]
            if rotulos != ["Novo personagem", "Voltar ao título", "Ver biografia", "Fechar"]:
                falhas.append(f"botões inesperados: {rotulos}")
            pg.screenshot(path=os.path.join(a.saida, "20_morte_sem_herdeiros.png"))
            pg.click(".fundo >> text=Novo personagem")
            pg.wait_for_timeout(600)
            if not pg.query_selector("text=Criar personagem"):
                falhas.append("'Novo personagem' não abriu o painel Personagens")
            pg.screenshot(path=os.path.join(a.saida, "21_painel_personagens.png"))
        # 2) 'Voltar ao título' leva ao título
        if not comecar():
            falhas.append("segunda partida: o personagem não morreu")
        else:
            pg.click(".fundo >> text=Voltar ao título")
            try:
                pg.wait_for_selector(".tit-botoes", timeout=5000)
            except Exception:
                falhas.append("'Voltar ao título' não mostrou o título (ou pediu confirmação)")
                pg.screenshot(path=os.path.join(a.saida, "22_voltar_titulo_falhou.png"))
        b.close()
    for x in problemas + falhas:
        print("FALHA:", x)
    print("OK" if not (problemas or falhas) else "COM FALHAS")
    return 1 if (problemas or falhas) else 0


if __name__ == "__main__":
    sys.exit(main())
