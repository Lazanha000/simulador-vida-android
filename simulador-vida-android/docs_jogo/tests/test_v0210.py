"""Testes da atualização v0.21.0 (acessibilidade, lista de leitura, ações em lote, modo escuro e cursos reais)."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import sim
from sim import (carreiras, economy, educacao_br, factory, firms, intelecto,
                 livros, mundo, panels, persistence, start, ui_web, views,
                 work)

WEB_DIR = Path(__file__).resolve().parents[2] / "app" / "src" / "main" / "assets" / "web"


def _jogo(idade=22, seed=210, riqueza=120000.0, sexo="F"):
    g = factory.new_game("v0210", seed)
    p = start.start_adult(g, idade, sexo, "Clara" if sexo == "F" else "Pedro", "Mendes")
    p.schooling_years = 12
    p.in_school = False
    for k in p.cognition:
        p.cognition[k] = 78
        p.cognition_potential[k] = 78
    p.personality["conscienciosidade"] = 78
    p.wealth = riqueza
    return g, p


class TestVersaoESchemaV0210(unittest.TestCase):
    def test_versao_schema_e_retrocompatibilidade(self):
        self.assertEqual(sim.__version__, "0.21.0")
        self.assertEqual(persistence.SCHEMA_VERSION, 20)
        self.assertIn("20", persistence.SUPPORTED_VERSIONS)
        self.assertIn("19", persistence.SUPPORTED_VERSIONS)

        g, p = _jogo(idade=20, seed=11)
        livros.fila_adicionar(g, "menina_bonita")
        livros.fila_adicionar(g, "flicts")
        livros.fila_auto(g, True)

        with tempfile.TemporaryDirectory() as td:
            arq20 = os.path.join(td, "v20.db")
            persistence.save_game(g, arq20)
            g2 = persistence.load_game(arq20)
            self.assertEqual(livros.fila_of(g2, p.id), ["menina_bonita", "flicts"])
            self.assertTrue(intelecto.dados(g2, p.id)["auto_ler_fila"])

            # Save v19 legado (sem fila_leitura / auto_ler_fila em intelecto)
            arq19 = os.path.join(td, "v19.db")
            persistence.save_game(g, arq19)
            con = sqlite3.connect(arq19)
            with con:
                con.execute("UPDATE meta SET value='19' WHERE key='schema_version'")
            con.close()
            g19 = persistence.load_game(arq19)
            self.assertEqual(livros.fila_of(g19, p.id), ["menina_bonita", "flicts"])


class TestCursosReaisBrasilV0210(unittest.TestCase):
    def test_catalogo_expandido_integrado_trabalho_e_setores(self):
        self.assertGreaterEqual(len(educacao_br.CURSOS), 34)
        ids = [c[0] for c in educacao_br.CURSOS]
        self.assertEqual(len(ids), len(set(ids)))

        esperados = {
            "ciencias_sociais", "filosofia", "matematica", "letras",
            "administracao", "arquitetura", "odontologia", "farmacia",
            "fisioterapia", "nutricao", "biomedicina", "medicina_veterinaria",
            "agronomia", "ciencias_biologicas", "historia", "geografia",
            "fisica", "quimica", "jornalismo", "publicidade",
            "relacoes_internacionais", "estatistica", "servico_social",
            "educacao_fisica",
        }
        self.assertTrue(esperados.issubset(set(ids)))
        self.assertEqual(set(educacao_br.CURSO_TIPO), set(ids))
        self.assertEqual(set(educacao_br.CURSO_AREA), set(ids))

        occs_work = {o[0] for o in work.OCUPACOES}
        occs_setores = {k for s in firms.SETORES.values() for k in s}
        for _, _, _, _, occ, _ in educacao_br.CURSOS:
            self.assertIn(occ, occs_work)
            self.assertIn(occ, economy.SALARIO_BASE)
            self.assertIn(occ, occs_setores)

        # Formatura em novo curso define ocupacao_preferida correspondente
        g, p = _jogo(idade=19, seed=31)
        st = educacao_br.dados(g, p.id)
        p.graduated = True
        st["curso"] = "ciencias_sociais"
        self.assertEqual(educacao_br.ocupacao_preferida(g, p.id), "sociologo")
        st["curso"] = "arquitetura"
        self.assertEqual(educacao_br.ocupacao_preferida(g, p.id), "arquiteto")


class TestListaDeLeituraEAcoesEmLoteV0210(unittest.TestCase):
    def test_fila_leitura_ordenacao_lote_parcial_e_rng(self):
        g, p = _jogo(idade=22, seed=41)
        for k in p.cognition:
            p.cognition[k] = 50
            p.cognition_potential[k] = 50
        p.cognition["atencao"] = 50
        p.cognition["compreensao_verbal"] = 50
        cap = livros.capacidade_mes(g, p)
        self.assertGreater(cap, 120)

        # Adiciona 3 obras na fila e reordena
        livros.fila_adicionar(g, "flicts")         # 48 págs
        livros.fila_adicionar(g, "menina_bonita")  # 32 págs
        livros.fila_adicionar(g, "os_miseraveis" if "os_miseraveis" in {x[0] for x in livros.CATALOGO} else "miseraveis")  # 1512 págs
        self.assertEqual(livros.fila_of(g, p.id), ["flicts", "menina_bonita", "miseraveis"])

        livros.fila_mover(g, "menina_bonita", -1)
        self.assertEqual(livros.fila_of(g, p.id)[0], "menina_bonita")
        livros.fila_mover(g, "menina_bonita", 1)
        self.assertEqual(livros.fila_of(g, p.id)[0], "flicts")

        # Ler lista em 1 clique: conclui os 2 curtos (48 + 32 = 80p) e inicia o longo com o saldo do mês
        rng0 = g.rng.getstate()
        r = livros.ler_fila(g)
        self.assertEqual(g.rng.getstate(), rng0)
        self.assertEqual(r["concluidos"], 2)
        self.assertEqual(r["em_andamento"], 1)
        self.assertIn("flicts", g.livros[p.id])
        self.assertIn("menina_bonita", g.livros[p.id])
        self.assertEqual(livros.fila_of(g, p.id), ["miseraveis"])
        self.assertGreater(intelecto.dados(g, p.id)["progresso_livros"]["miseraveis"], 0)

        livros.fila_remover(g, "miseraveis")
        self.assertEqual(livros.fila_of(g, p.id), [])
        livros.fila_adicionar(g, "dom_casmurro")
        livros.fila_limpar(g)
        self.assertEqual(livros.fila_of(g, p.id), [])

    def test_auto_ler_fila_ao_virar_mes(self):
        g, p = _jogo(idade=21, seed=45)
        livros.fila_adicionar(g, "menina_bonita")
        livros.fila_auto(g, True)
        views.avancar(g, 1)
        self.assertIn("menina_bonita", g.livros.get(p.id, []))
        self.assertEqual(livros.fila_of(g, p.id), [])

    def test_estudar_lote_freela_lote_e_hora_extra(self):
        g, p = _jogo(idade=24, seed=51)
        firms.ensure_world(g)
        work.start_job(g, p, "analista_sistemas", g.year * 12 + g.month)
        p.income = 5000.0
        mundo.comprar_equipamento(g, "notebook")

        rng0 = g.rng.getstate()
        res_est = intelecto.estudar_lote(g, "enem", "ciencias")
        self.assertEqual(res_est["sessoes"], intelecto.LIMITE_ESTUDO_MES)
        self.assertEqual(res_est["restantes"], 0)
        self.assertGreater(intelecto.bonus_enem_atual(g, p.id), 0)

        w0 = p.wealth
        res_fl = carreiras.fazer_freelas_lote(g, "economia")
        self.assertEqual(res_fl["quantidade"], 2)
        self.assertGreater(p.wealth, w0)
        with self.assertRaises(ValueError):
            carreiras.fazer_freelas_lote(g, "economia")

        w1 = p.wealth
        exp0 = p.experience
        r_ex1 = carreiras.trabalho_extra(g)
        self.assertEqual(r_ex1["restantes"], 1)
        carreiras.trabalho_extra(g)
        with self.assertRaises(ValueError):
            carreiras.trabalho_extra(g)
        self.assertGreater(p.wealth, w1)
        self.assertEqual(p.experience, exp0 + 2)
        self.assertTrue(any("Hora extra" in x["desc"] for x in mundo.extrato(g, p.id)))
        self.assertEqual(g.rng.getstate(), rng0)


class TestApiWebEInterfaceV0210(unittest.TestCase):
    def test_novas_rotas_http_paineis_e_assets(self):
        with tempfile.TemporaryDirectory() as td:
            app = ui_web.App(td)
            est = app.api("POST", "novo", {}, {"nome": "HTTP21", "modo": "avulso", "idade": 24, "semente": 21})
            self.assertGreaterEqual(len(est["educacao_br"]["cursos"]), 34)
            self.assertIn("area", est["educacao_br"]["cursos"][0])
            self.assertIn("extras_restantes", est["carreiras"])

            p = views.player_of(app.game)
            p.wealth = 200000.0
            firms.ensure_world(app.game)
            work.start_job(app.game, p, "administrador", app.game.year * 12 + app.game.month)
            app.api("POST", "mundo/comprar_equipamento", {}, {"id": "notebook"})

            rotas = [
                ("intelecto/estudar_lote", {"modo": "enem", "area": "humanas"}),
                ("livros/fila/adicionar", {"id": "menina_bonita"}),
                ("livros/fila/adicionar", {"id": "flicts"}),
                ("livros/fila/mover", {"id": "flicts", "delta": -1}),
                ("livros/fila/remover", {"id": "flicts"}),
                ("livros/fila/auto", {"ativar": True}),
                ("livros/ler_fila", {}),
                ("livros/fila/limpar", {}),
                ("carreiras/freela_lote", {"area": "ciencias"}),
                ("carreiras/trabalho_extra", {}),
            ]
            for rota, body in rotas:
                r = app.api("POST", rota, {}, body)
                self.assertIn("estado", r, rota)

            cfg = app.api("GET", "painel/config", {}, {})
            acoes = [a["acao"] for b in cfg["blocos"] if b["t"] == "acoes" for a in b["itens"]]
            self.assertIn("tema", acoes)

            trab = app.api("GET", "painel/trabalho", {}, {})
            acoes_trab = [a for b in trab["blocos"] if b["t"] == "acoes" for a in b["itens"]]
            self.assertTrue(any(a.get("nome") == "empresas" for a in acoes_trab))

        css = (WEB_DIR / "css" / "app.css").read_text(encoding="utf-8")
        js_app = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
        js_ui = (WEB_DIR / "js" / "ui.js").read_text(encoding="utf-8")
        js_panels = (WEB_DIR / "js" / "panels.js").read_text(encoding="utf-8")
        for marcador in (".app.escuro", ".chip-voltar", ".voltar-seta", ".fila-controles", ".duas-desigual"):
            self.assertIn(marcador, css)
        for marcador in ("btn-ultima-tela", "btn-tema", "abrirUltimaTela", "estudar_lote", "ler_fila", "freela_lote", "trabalho_extra"):
            self.assertIn(marcador, js_app)
        for marcador in ("temaAtual", "aplicarTema", "SVG_SETA_ESQ", "SVG_VOLTAR_HIST"):
            self.assertIn(marcador, js_ui)
        self.assertIn("voltar-seta", js_panels)
        self.assertIn("tema", js_panels)


if __name__ == "__main__":
    unittest.main()
