"""v0.17.0: testes integrados para livros (129), conhecidos no trabalho, ENEM/SISU/PROUNI/FIES/Pós,
concursos com estabilidade, empreendedorismo, bancos/imóveis/investimentos/empréstimos, cidades, notícias e política."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from sim import (carreiras, conhecidos, decisions, economy, educacao_br, engine, factory, firms,
                 foco, livros, mundo, panels, persistence, start, views, work)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _adulto(seed=13, idade=26, riqueza=500000.0):
    g = factory.new_game("v0170", seed)
    c = start.start_adult(g, idade, "F", "Clara", "Souza")
    c.schooling_years, c.in_school = 12, False
    for k in c.cognition:
        c.cognition[k] = c.cognition_potential[k] = 85
    c.personality["conscienciosidade"] = 85
    c.wealth = riqueza
    return g, c


class TestLivrosEConhecidosV0170(unittest.TestCase):
    def test_129_livros_reais_e_interesses(self):
        self.assertGreaterEqual(len(livros.CATALOGO), 100)
        ids = [x[0] for x in livros.CATALOGO]
        self.assertEqual(len(ids), len(set(ids)))
        for _, t, a, ano, gen, niv in livros.CATALOGO:
            self.assertTrue(t and a and gen)
            self.assertIn(gen, livros.GENERO_COGNICAO, gen)
            self.assertIn(niv, (1, 2, 3))
            self.assertTrue(-800 <= ano <= 2026)
        g, p = _adulto()
        livros.ler(g, "riqueza_nacoes")  # 960 págs: avança no mês 1 e conclui no mês 2
        g.month = g.month % 12 + 1
        livros.ler(g, "riqueza_nacoes")
        livros.ler(g, "dom_casmurro")
        self.assertEqual(livros.interesses(g, p.id), {"economia": 1, "romance": 1})

    def test_conhecer_no_trabalho_e_familia(self):
        g, p = _adulto()
        firms.ensure_world(g)
        work.start_job(g, p, "aux_administrativo", g.year * 12 + g.month)
        rng_antes = g.rng.getstate()
        r = conhecidos.conhecer(g, "trabalho")
        self.assertEqual(g.rng.getstate(), rng_antes)
        novo = g.characters[r["id"]]
        self.assertTrue(work.is_employed(novo))
        self.assertEqual(novo.workplace, p.workplace)
        self.assertIn(novo.family_id, g.families)
        for (fid, occ), n in firms.filled(g).items():
            self.assertLessEqual(n, g.firms[fid].slots.get(occ, 0))


class TestEducacaoBrasileira(unittest.TestCase):
    def test_enem_sisu_ic_e_pos_graduacao(self):
        self.assertGreaterEqual(len(educacao_br.UNIVERSIDADES), 15)
        g, p = _adulto(idade=19)
        enem = educacao_br.fazer_enem(g)
        self.assertTrue(350 <= enem["media"] <= 980)
        p.schooling_years, p.in_college, p.graduated = 12, False, False
        g.educacao_br[p.id]["enem"]["media"] = 820.0
        g.educacao_br[p.id]["enem"]["redacao"] = 900
        res = educacao_br.ingressar(g, "UFMG", "direito", "sisu")
        self.assertEqual(res["universidade"], "UFMG")
        self.assertTrue(p.in_college)
        educacao_br.iniciacao_cientifica(g)
        w0 = p.wealth
        economy.apply_month(g)
        self.assertGreater(p.wealth, w0)
        p.in_college, p.graduated = False, True
        educacao_br.iniciar_pos(g, "mestrado")
        self.assertIsNotNone(g.educacao_br[p.id]["pos_atual"])


class TestCarreirasEPolitica(unittest.TestCase):
    def test_concurso_estavel_e_empresa_propria(self):
        g, p = _adulto(idade=28, riqueza=200000.0)
        p.graduated = True
        r = carreiras.prestar_concurso(g, "aux_prefeitura")
        self.assertTrue(r["aprovado"])
        self.assertTrue(g.carreira_extra[p.id]["estavel"])
        old_sep = work.separation_monthly
        work.separation_monthly = lambda c, n: 1.0
        try:
            engine.advance_months(g, 3)
        finally:
            work.separation_monthly = old_sep
        self.assertIsNotNone(p.occupation)

        emp = carreiras.abrir_empresa(g, "comércio", "micro")
        self.assertIn(emp["id"], g.firms)
        self.assertTrue(g.firms[emp["id"]].is_open)
        carreiras.encerrar_empresa(g)
        self.assertFalse(g.firms[emp["id"]].is_open)

    def test_politica_filiacao_campanha_e_eleicao(self):
        g, p = _adulto(idade=35, riqueza=100000.0)
        carreiras.filiar(g, "civico")
        g.politica[p.id]["influencia"] = 90.0
        res = carreiras.concorrer(g, "vereador")
        self.assertTrue(res["eleito"])
        self.assertEqual(g.politica[p.id]["mandato_meses"], 48)
        economy.apply_month(g)
        self.assertEqual(g.politica[p.id]["mandato_meses"], 47)


class TestMundoBancosECidades(unittest.TestCase):
    def test_cidade_imovel_investimento_emprestimo_e_persistencia(self):
        g, p = _adulto(idade=30, riqueza=500000.0)
        mundo.mudar_cidade(g, "sp")
        self.assertEqual(mundo.cidade_of(g, p.id)[0], "sp")
        custo_sp = economy.household_of(g, p)["cost"]
        mundo.comprar_imovel(g, "kitnet", alugar=False)
        custo_com_casa = economy.household_of(g, p)["cost"]
        self.assertLess(custo_com_casa, custo_sp)
        mundo.comprar_veiculo(g, "moto")
        mundo.investir(g, "tesouro", 50000.0)
        mundo.pedir_emprestimo(g, 10000.0)
        economy.apply_month(g)
        self.assertGreater(g.patrimonio[p.id]["inv"]["tesouro"], 50000.0)
        mundo.registrar_noticias_mes(g)
        self.assertTrue(any(n["tipo"] == "simulada" for n in g.noticias))

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "v16.db")
            persistence.save_game(g, path)
            g2 = persistence.load_game(path)
        self.assertEqual(g2.cidades, g.cidades)
        self.assertEqual(g2.patrimonio, g.patrimonio)
        self.assertEqual(g2.noticias, g.noticias)


class TestPaineisEWebV0170(unittest.TestCase):
    def test_todos_paineis_e_cli_funcionam(self):
        g, _ = _adulto(idade=30)
        for nome in panels.PAINEIS:
            json.dumps(panels.painel(g, nome, {}, {"autosave": True}), ensure_ascii=False)
        env = dict(os.environ, PYTHONPATH=os.path.join(os.path.dirname(ROOT), "app", "src", "main", "python"))
        main_py = os.path.join(os.path.dirname(ROOT), "app", "src", "main", "python", "main.py")
        with tempfile.TemporaryDirectory() as saves:
            r = subprocess.run(
                [sys.executable, main_py, "--cli", "--saves-dir", saves],
                input="1\nCLI17\n77\n1\n30\nF\nAna\nReis\n15\n2\n5\n16\nCasmurro\n1\n10\n0\n",
                capture_output=True, text=True, cwd=ROOT, timeout=60, env=env,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Leu 'Dom Casmurro'", r.stdout)


if __name__ == "__main__":
    unittest.main()
