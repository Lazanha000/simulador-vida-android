"""E2E opcional (Playwright): morte COM herdeiros — lista de herdeiros, continuar como parente, sem erro de JS.
Uso: python3 tests/e2e_morte_herdeiros.py [--saida /tmp/shots]
"""
import argparse, os, sys, tempfile, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright  # noqa: E402
from sim import engine, ui_web  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--saida", default="/tmp/shots"); a = ap.parse_args()
    os.makedirs(a.saida, exist_ok=True)
    srv, app = ui_web.criar_servidor(tempfile.mkdtemp(), porta=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    probs, falhas = [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 430, "height": 820})
        pg.on("pageerror", lambda e: probs.append(f"pageerror: {e}"))
        pg.on("console", lambda m: m.type == "error" and "ERR_NAME_NOT_RESOLVED" not in m.text and probs.append(f"console: {m.text}"))
        pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/"); pg.wait_for_selector(".tit-botoes")
        pg.click("text=Novo jogo"); pg.click(".seg >> nth=0 >> text=Família")
        pg.click(".rodape .btn >> nth=0"); pg.wait_for_selector(".feed")
        g = app.game
        # joga com o adulto mais velho vivo e o envelhece por baixo dos panos até perto do fim
        velho = max((c for c in g.characters.values() if c.alive), key=lambda c: c.age_at(g.year, g.month))
        pg.evaluate("id => fetch('/api/jogador',{method:'POST',headers:{'X-Sim':'1','Content-Type':'application/json'},body:JSON.stringify({id})})", velho.id)
        pg.reload(); pg.wait_for_selector(".feed")
        morreu = False
        for _ in range(60):
            pg.click("#selo"); pg.click(".bandeja button >> nth=2"); pg.wait_for_timeout(1200)
            if pg.query_selector(".faixa-luto"): morreu = True; break
            if pg.query_selector(".fundo"): pg.click(".fundo .btn")
        if not morreu:
            falhas.append("o jogador não morreu em 60 anos")
        else:
            rot = pg.locator(".fundo .acoes button").all_inner_texts()
            herd = pg.locator(".fundo .pes").count()
            pg.screenshot(path=os.path.join(a.saida, "30_morte_com_herdeiros.png"))
            if herd == 0: falhas.append("sem herdeiros listados (família deveria ter)")
            elif [r.strip() for r in rot] != ["Ver biografia", "Fechar"]: falhas.append(f"botões: {rot}")
            else:
                nome_antes = pg.inner_text(".cab .nome")
                pg.click(".fundo .pes >> nth=0"); pg.wait_for_timeout(1200)
                if pg.query_selector(".fundo"): falhas.append("o diálogo In memoriam continuou aberto após escolher o herdeiro")
                nome_depois = pg.inner_text(".cab .nome")
                if nome_antes == nome_depois: falhas.append("o personagem não trocou")
                pg.screenshot(path=os.path.join(a.saida, "31_continuou_como_herdeiro.png"))
        b.close()
    for x in probs + falhas: print("FALHA:", x)
    print("OK" if not (probs or falhas) else "COM FALHAS")
    return 1 if (probs or falhas) else 0


if __name__ == "__main__":
    sys.exit(main())
