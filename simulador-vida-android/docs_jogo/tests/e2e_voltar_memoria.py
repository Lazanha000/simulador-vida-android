"""E2E da v0.19.0 no navegador: botão Voltar (tela anterior) e memória de "onde eu estava" (opcional; Playwright).

Sobe o servidor em processo, joga pelo Chromium headless e confere, em tela real: Voltar das sub-telas de Ações volta ao
menu Ações; Biblioteca/Filmes/painéis lembram busca, filtros, aba e rolagem; o gancho do botão físico do Android
(`window.__simVoltar`) fecha uma camada por vez; a opção "Lembrar onde eu estava" liga/desliga; a memória sobrevive a
recarregar a página. Não entra no `unittest discover` (nome sem `test`).
Uso: python3 tests/e2e_voltar_memoria.py [--saida /tmp/shots]
"""
import argparse
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright  # noqa: E402

from sim import ui_web  # noqa: E402

falhas: list[str] = []


def confere(cond, msg):
    print(("  ok  " if cond else "FALHA ") + msg)
    if not cond:
        falhas.append(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default="/tmp/shots")
    a = ap.parse_args()
    os.makedirs(a.saida, exist_ok=True)
    srv, _app = ui_web.criar_servidor(tempfile.mkdtemp(), porta=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    erros: list[str] = []

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 400, "height": 760})
        pg.on("pageerror", lambda e: erros.append(f"pageerror: {e}"))
        pg.on("console", lambda m: m.type == "error" and "net::ERR_" not in m.text and erros.append(f"console: {m.text}"))  # fontes do Google (sem rede) não contam

        titulo = lambda: (pg.inner_text(".fundo:last-of-type .dlg h2") if pg.query_selector(".fundo") else None)  # noqa: E731
        rol = lambda: pg.evaluate("document.querySelector('.fundo:last-of-type .dlg').scrollTop")  # noqa: E731
        rolar = lambda y: pg.evaluate(f"document.querySelector('.fundo:last-of-type .dlg').scrollTop = {y}")  # noqa: E731
        voltar_fisico = lambda: pg.evaluate("window.__simVoltar()")  # noqa: E731
        acoes = lambda: (pg.click("#btn-acoes"), pg.wait_for_selector(".fundo"))  # noqa: E731
        sub = lambda t: pg.click(f".fundo .decisao >> text={t}")  # noqa: E731
        voltar = lambda: pg.click(".fundo .acoes.fixa >> text=Voltar")  # noqa: E731

        pg.goto(url)
        pg.wait_for_selector(".tit-botoes")
        print("Nova partida")
        pg.click("text=Novo jogo")
        pg.fill("input[type=text] >> nth=0", "Teste Voltar")
        pg.click(".seg >> nth=0 >> text=Personagem")
        pg.fill("input[type=number] >> nth=0", "25")
        pg.fill("input[placeholder=aleatória]", "777")
        # voltar ao título e retornar: o que foi digitado fica
        pg.click(".rodape .btn.p")   # Voltar
        pg.wait_for_selector(".tit-botoes")
        pg.click("text=Novo jogo")
        confere(pg.input_value("input[type=text] >> nth=0") == "Teste Voltar", "Nova partida lembra o nome digitado")
        confere(pg.query_selector(".seg >> nth=0 >> button.on").inner_text() == "Personagem", "Nova partida lembra o modo")
        confere(pg.input_value("input[placeholder=aleatória]") == "", "Nova partida NÃO lembra a semente")
        confere(pg.input_value("input[type=number] >> nth=0") == "25", "Nova partida lembra a idade")
        pg.click(".rodape .btn >> nth=0")
        pg.wait_for_selector(".feed")
        # botão físico no título/novo
        confere(voltar_fisico() is False, "Voltar físico na tela do jogo sem nada aberto: false (app pode fechar)")

        print("Ações -> Biblioteca: Voltar e memória")
        acoes()
        confere(titulo() == "Ações", "menu Ações abre")
        sub("Biblioteca")
        confere(titulo() == "Biblioteca", "Biblioteca abre")
        pg.fill(".fundo input[type=search]", "a")
        gens = pg.eval_on_selector_all(".fundo select option", "o => o.map(x => x.value)")
        gen = next(g for g in gens if g)
        pg.select_option(".fundo select", gen)
        n_cards_gen = pg.eval_on_selector_all(".livro-card", "e => e.length")
        pg.select_option(".fundo select", "")
        pg.check(".fundo .check-linha input")
        pg.click(".fundo .seg >> text=/Lendo/")
        pg.click(".fundo .seg >> text=/Para ler/")
        pg.select_option(".fundo select", gen)
        rolar(0)
        pg.screenshot(path=os.path.join(a.saida, "20_biblioteca_filtrada.png"))
        pg.select_option(".fundo select", "")
        rolar(400)
        y1 = rol()
        confere(y1 > 100, f"Biblioteca rolou ({y1})")
        voltar()
        confere(titulo() == "Ações", "Voltar da Biblioteca volta ao menu Ações (tela anterior)")
        voltar()
        confere(titulo() is None, "Voltar em Ações fecha tudo")
        acoes(); sub("Biblioteca")
        confere(pg.input_value(".fundo input[type=search]") == "a", "Biblioteca lembra a busca")
        confere(pg.is_checked(".fundo .check-linha input"), "Biblioteca lembra 'só os que posso ler'")
        confere(rol() > 100, f"Biblioteca lembra a rolagem ({rol()})")
        # aba e gênero
        pg.click(".fundo .seg >> text=/Lidos/")
        pg.select_option(".fundo select", gen)
        voltar(); voltar()
        acoes(); sub("Biblioteca")
        confere(pg.query_selector(".fundo .seg button.on").inner_text().startswith("Lidos"), "Biblioteca lembra a aba (Lidos)")
        confere(pg.input_value(".fundo select") == gen, "Biblioteca lembra o gênero")
        voltar(); voltar()

        print("Ações -> Redação, Artigos e Filmes: aba e rolagem por aba")
        pg.set_viewport_size({"width": 400, "height": 480})   # tela baixa: garante que a lista de filmes rola
        def aba(t):   # clica por JS (o Playwright rolaria até o topo antes do clique) e espera o quadro de restauração da rolagem
            pg.evaluate("t => [...document.querySelectorAll('.fundo .seg button')].find(b => b.textContent.includes(t)).click()", t)
            pg.wait_for_timeout(120)
        acoes(); sub("Redação, Artigos e Filmes")
        aba("Filmes")
        rolar(120)
        yf = rol()
        confere(yf > 20, f"Filmes é rolável neste teste ({yf})")
        aba("Artigos")
        confere(rol() < yf, f"Aba Artigos tem a própria rolagem ({rol()})")
        aba("Filmes")
        confere(abs(rol() - yf) <= 2, f"Filmes volta à própria rolagem ao trocar de aba ({rol()} vs {yf})")
        voltar()
        confere(titulo() == "Ações", "Voltar de Filmes volta ao menu Ações")
        voltar()
        acoes(); sub("Redação, Artigos e Filmes")
        confere(pg.query_selector(".fundo .seg button.on").inner_text().startswith("Filmes"), "Formação reabre na aba Filmes")
        confere(abs(rol() - yf) <= 2, f"Formação reabre na rolagem de Filmes ({rol()} vs {yf})")
        pg.screenshot(path=os.path.join(a.saida, "21_filmes_restaurado.png"))
        voltar(); voltar()
        pg.set_viewport_size({"width": 400, "height": 760})

        print("Selects: ENEM/faculdade e Mundo")
        acoes(); sub("ENEM, faculdade e pós")
        pg.select_option(".fundo select >> nth=1", index=2)
        v_curso = pg.input_value(".fundo select >> nth=1")
        voltar(); voltar()
        acoes(); sub("ENEM, faculdade e pós")
        confere(pg.input_value(".fundo select >> nth=1") == v_curso, "Curso escolhido volta como estava")
        voltar(); voltar()

        print("Botão físico do Android (window.__simVoltar)")
        acoes(); sub("Biblioteca")
        confere(voltar_fisico() is True and titulo() == "Ações", "físico: Biblioteca -> Ações")
        confere(voltar_fisico() is True and titulo() is None, "físico: Ações -> fecha")
        pg.click("#btn-menu")
        pg.click(".grade >> text=Biografia")
        pg.wait_for_selector(".sheet >> nth=1")
        confere(voltar_fisico() is True and pg.eval_on_selector_all(".sheet", "e => e.length") == 1, "físico: fecha o painel e fica no menu")
        confere(voltar_fisico() is True and pg.eval_on_selector_all(".sheet", "e => e.length") == 0, "físico: fecha o menu")
        confere(voltar_fisico() is False, "físico: nada aberto = false")

        print("Painéis: Biografia lembra o filtro")
        pg.click("#btn-menu")
        pg.click(".grade >> text=Biografia")
        pg.wait_for_selector(".sheet select")
        pg.select_option(".sheet select", index=2)
        pg.wait_for_timeout(300)
        cat = pg.input_value(".sheet select")
        pg.click(".sheet .seg >> text=Todo o mundo")
        pg.wait_for_timeout(300)
        pg.click(".sheet >> nth=1 >> .rodape .btn")
        pg.click(".sheet >> .rodape .btn")
        pg.click("#btn-menu")
        pg.click(".grade >> text=Biografia")
        pg.wait_for_selector(".sheet select")
        pg.wait_for_timeout(300)
        confere(pg.input_value(".sheet select") == cat, "Biografia reabre com a categoria escolhida")
        confere(pg.query_selector(".sheet .seg button.on").inner_text() == "Todo o mundo", "Biografia reabre em 'Todo o mundo'")
        pg.click(".sheet >> nth=1 >> .rodape .btn")
        pg.click(".sheet >> .rodape .btn")

        print("Ajustes: ligar/desligar a memória")
        pg.click("#btn-menu")
        pg.click(".grade >> text=Ajustes")
        pg.wait_for_selector("text=Lembrar onde eu estava: ligado")
        pg.click("text=Lembrar onde eu estava: ligado")
        pg.wait_for_selector("text=Lembrar onde eu estava: desligado")
        pg.click(".sheet >> nth=1 >> .rodape .btn")
        pg.click(".sheet >> .rodape .btn")
        acoes(); sub("Biblioteca")
        confere(pg.input_value(".fundo input[type=search]") == "", "Com a memória desligada a Biblioteca abre limpa")
        pg.fill(".fundo input[type=search]", "zzz")
        voltar(); voltar()
        acoes(); sub("Biblioteca")
        confere(pg.input_value(".fundo input[type=search]") == "", "Com a memória desligada nada é lembrado")
        voltar(); voltar()
        pg.click("#btn-menu")
        pg.click(".grade >> text=Ajustes")
        pg.click("text=Lembrar onde eu estava: desligado")
        pg.wait_for_selector("text=Lembrar onde eu estava: ligado")
        pg.click(".sheet >> nth=1 >> .rodape .btn")
        pg.click(".sheet >> .rodape .btn")

        print("Persistência ao recarregar a página")
        acoes(); sub("Biblioteca")
        pg.fill(".fundo input[type=search]", "dom")
        voltar(); voltar()
        pg.wait_for_timeout(500)
        pg.reload()   # o servidor segue com a partida aberta: o jogo volta direto para a tela principal
        pg.wait_for_selector(".feed")
        acoes(); sub("Biblioteca")
        confere(pg.input_value(".fundo input[type=search]") == "dom", "Busca da Biblioteca sobrevive a recarregar")
        voltar(); voltar()
        b.close()

    for e in erros:
        print("ERRO JS:", e)
    print(f"\n{len(falhas)} falha(s), {len(erros)} erro(s) de JavaScript")
    return 1 if falhas or erros else 0


if __name__ == "__main__":
    sys.exit(main())
