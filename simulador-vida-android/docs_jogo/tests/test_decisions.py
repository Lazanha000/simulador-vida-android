"""G1 (v0.15.0): eventos com decisão."""
import os
import sqlite3
import tempfile
import unittest

from sim import decisions, factory, persistence, start, views


def jogo(seed=7, idade=14):
    g = factory.new_game("t", seed)
    start.start_adult(g, idade, "F", None, None)
    return g


def ate_decisao(g, limite=400):
    for _ in range(limite):
        r = views.avancar(g, 1)
        if r["decisao"]:
            return r
    raise AssertionError("nenhuma decisão em 400 meses")


class TestDecisoes(unittest.TestCase):
    def test_catalogo_cobre_toda_a_vida_com_3_opcoes(self):
        self.assertGreaterEqual(len(decisions.EVENTOS), 40)
        for e in decisions.EVENTOS:
            self.assertEqual(len(e["ops"]), 3, e["id"])
        # Cobertura do nascimento (0) até a velhice (80+)
        for idade in (0, 2, 8, 15, 30, 75):
            g = jogo(idade=idade)
            p = views.player_of(g)
            self.assertTrue(decisions.elegiveis(g, p), f"sem eventos para idade {idade}")

    def test_avanco_para_na_decisao_e_bloqueia_ate_escolher(self):
        g = jogo()
        r = ate_decisao(g)
        self.assertEqual(r["interrompido"], "decisao")
        self.assertEqual(len(r["decisao"]["opcoes"]), 3)
        with self.assertRaises(ValueError):
            views.avancar(g, 1)
        self.assertFalse(views.estado(g, {})["pode_avancar"])
        decisions.decidir(g, 0)
        self.assertTrue(views.estado(g, {})["pode_avancar"])

    def test_determinismo_e_nao_consome_rng_do_mundo(self):
        a, b = jogo(), jogo()
        ra, rb = ate_decisao(a), ate_decisao(b)
        self.assertEqual(ra["decisao"], rb["decisao"])
        self.assertEqual(a.date_str(), b.date_str())
        self.assertEqual(decisions.decidir(a, None)["escolhida"], decisions.decidir(b, None)["escolhida"])

    def test_cada_opcao_aplica_efeito_e_registra_biografia(self):
        for ev in decisions.EVENTOS:
            for i, (_, _, ef) in enumerate(ev["ops"]):
                g = jogo(idade=30)
                p = views.player_of(g)
                p.wealth = 1000.0
                antes = (p.health, p.wealth, dict(p.cognition), dict(p.personality))
                g.decisions["pending"] = {"id": ev["id"], "ano": g.year, "mes": g.month, "pid": p.id}
                n = len(g.biography)
                decisions.decidir(g, i)
                self.assertIsNone(g.decisions["pending"])
                self.assertEqual(g.biography[n].category, "decisao")
                if "m" in ef:
                    self.assertAlmostEqual(p.wealth - antes[1], ef["m"] * g.macro["min_wage"], places=4)
                if "s" in ef:
                    self.assertAlmostEqual(p.health, max(0, min(100, antes[0] + ef["s"])), places=6)
                for k, d in (ef.get("p") or {}).items():
                    self.assertEqual(p.personality[k], max(1, min(99, antes[3][k] + d)))

    def test_salvar_e_carregar_no_meio_da_decisao(self):
        g = jogo()
        r = ate_decisao(g)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.db")
            persistence.save_game(g, path)
            h = persistence.load_game(path)
        self.assertEqual(views.estado(h, {})["decisao"], r["decisao"])
        self.assertEqual(h.decisions, g.decisions)
        self.assertEqual(decisions.decidir(h, 1)["escolhida"], decisions.decidir(g, 1)["escolhida"])

    def test_save_antigo_v14_carrega_sem_decisao(self):
        g = jogo()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.db")
            persistence.save_game(g, path)
            con = sqlite3.connect(path)
            with con:
                con.execute("DELETE FROM meta WHERE key='decisions'")
                con.execute("UPDATE meta SET value='14' WHERE key='schema_version'")
            con.close()
            h = persistence.load_game(path)
        self.assertIsNone(h.decisions["pending"])

    def test_intervalo_minimo_entre_eventos(self):
        g = jogo()
        ate_decisao(g)
        decisions.decidir(g, 0)
        r = views.avancar(g, 1)
        self.assertIsNone(r["decisao"])


if __name__ == "__main__":
    unittest.main()


class TestConsequenciaAtrasada(unittest.TestCase):
    """v0.15.13: consequências com atraso."""

    def _jogo_com(self, ev_id, opcao):
        g = factory.new_game("t", 5)
        start.start_adult(g, 16, "F", None, None)
        p = views.player_of(g)
        g.decisions["pending"] = {"id": ev_id, "ano": g.year, "mes": g.month, "pid": p.id}
        decisions.decidir(g, opcao)
        return g, p

    def test_agenda_e_aplica_no_mes_certo(self):
        g, p = self._jogo_com("festa_prova", 0)
        self.assertEqual(len(g.decisions["depois"]), 1)
        antes = p.personality["conscienciosidade"]
        self.assertEqual(decisions.atrasadas(g), 0)          # ainda não chegou
        g.month = g.month % 12 + 1
        g.month = g.month % 12 + 1
        self.assertEqual(decisions.atrasadas(g), 1)
        self.assertEqual(p.personality["conscienciosidade"], antes + 1)
        self.assertTrue(g.biography[-1].text.startswith("Consequência:"))
        self.assertEqual(g.decisions["depois"], [])
        self.assertEqual(decisions.atrasadas(g), 0)          # não repete

    def test_opcao_sem_atraso_nao_agenda_e_save_preserva(self):
        g, p = self._jogo_com("festa_prova", 1)
        self.assertEqual(g.decisions["depois"], [])
        g, p = self._jogo_com("prova_dificil", 2)
        with tempfile.TemporaryDirectory() as t:
            f = os.path.join(t, "d.db")
            persistence.save_game(g, f)
            g2 = persistence.load_game(f)
        self.assertEqual(len(g2.decisions["depois"]), 1)
