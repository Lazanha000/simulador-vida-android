"""G2a (v0.15.1): foco do período."""
import os
import tempfile
import unittest

from sim import engine, factory, foco, persistence, start, views


def jogo(idade=20, seed=3):
    g = factory.new_game("t", seed)
    start.start_adult(g, idade, "F", None, None)
    return g


def rodar(g, f, meses=24):
    foco.definir(g, f)
    p = views.player_of(g)
    for _ in range(meses):
        engine.advance_months(g, 1)
        foco.mensal(g, p)
    return p


class TestFoco(unittest.TestCase):
    def test_invalido_e_padrao(self):
        g = jogo()
        self.assertEqual(foco.atual(g), "equilibrado")
        with self.assertRaises(ValueError):
            foco.definir(g, "voar")

    def test_descansar_recupera_saude_e_estudar_cansa(self):
        g = jogo()
        p = views.player_of(g)
        p.health = 50.0
        foco.definir(g, "descansar"); foco.mensal(g, p)
        self.assertAlmostEqual(p.health, 50.4)
        foco.definir(g, "estudar"); foco.mensal(g, p)
        self.assertLess(p.health, 50.4)

    def test_estudar_aumenta_cognicao_sem_passar_do_potencial(self):
        g = jogo(idade=17)
        p = views.player_of(g)
        for k in p.cognition:
            p.cognition_potential[k] = 99; p.cognition[k] = 40
        foco.definir(g, "estudar")
        for i in range(60):
            g.month, g.year = i % 12 + 1, 2026 + i // 12
            foco.mensal(g, p)
        self.assertGreater(sum(p.cognition.values()), 40 * len(p.cognition))
        self.assertTrue(all(p.cognition[k] <= p.cognition_potential[k] for k in p.cognition))

    def test_trabalhar_so_ajuda_empregado(self):
        g = jogo()
        p = views.player_of(g)
        p.occupation, p.income, p.retired, p.wealth = None, 3000.0, False, 0.0
        foco.definir(g, "trabalhar"); foco.mensal(g, p)
        self.assertEqual(p.wealth, 0.0)
        p.occupation = "x"; foco.mensal(g, p)
        self.assertAlmostEqual(p.wealth, 90.0)

    def test_estudar_melhora_desempenho_escolar(self):
        g = jogo(idade=10)
        p = views.player_of(g)
        import random
        g.rng = random.Random(1); a = engine.school_performance(g, p, 10)
        foco.definir(g, "estudar")
        g.rng = random.Random(1); b = engine.school_performance(g, p, 10)
        self.assertEqual(b, min(100, a + 6))

    def test_save_load_e_save_sem_foco(self):
        g = jogo(); foco.definir(g, "socializar")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.db")
            persistence.save_game(g, path)
            self.assertEqual(foco.atual(persistence.load_game(path)), "socializar")

    def test_foco_padrao_nao_altera_o_mundo(self):
        a, b = jogo(seed=5), jogo(seed=5)
        foco.definir(b, "equilibrado")
        engine.advance_months(a, 36); engine.advance_months(b, 36)
        self.assertEqual([e.text for e in a.biography], [e.text for e in b.biography])


if __name__ == "__main__":
    unittest.main()


class TestAreaEstudo(unittest.TestCase):
    """G2b (v0.15.2): área de estudo."""

    def test_padrao_e_invalida(self):
        g = jogo()
        self.assertEqual(foco.area_atual(g), "geral")
        with self.assertRaises(ValueError):
            foco.definir(g, "estudar", "magia")

    def test_area_sobe_so_a_habilidade_da_area(self):
        g = jogo(idade=17)
        p = views.player_of(g)
        for k in p.cognition_potential:
            p.cognition_potential[k] = 99
        antes = dict(p.cognition)
        foco.definir(g, "estudar", "matematica")
        for _ in range(60):
            foco.mensal(g, p)
            g.month = g.month % 12 + 1
        d = {k: p.cognition[k] - antes[k] for k in antes}
        self.assertGreater(d["raciocinio_logico"], 0)
        for k in ("memoria", "aprendizagem", "compreensao_verbal"):
            self.assertEqual(d[k], 0)

    def test_area_sobrevive_ao_save(self):
        g = jogo()
        foco.definir(g, "estudar", "humanas")
        with tempfile.TemporaryDirectory() as t:
            f = os.path.join(t, "a.db")
            persistence.save_game(g, f)
            g2 = persistence.load_game(f)
        self.assertEqual(foco.area_atual(g2), "humanas")


class TestConhecer(unittest.TestCase):
    """G3a (v0.15.3): conhecer alguém."""

    def test_cria_amigo_com_regras_de_idade_e_nao_muda_o_mundo(self):
        from sim import conhecidos
        for idade, menor in ((15, True), (30, False)):
            g = jogo(idade=idade)
            p = views.player_of(g)
            estado = g.rng.getstate()
            n = len(g.characters)
            r = conhecidos.conhecer(g)
            self.assertEqual(len(g.characters), n + 1)
            self.assertEqual(g.rng.getstate(), estado)
            self.assertTrue(g.are_friends(p.id, r["id"]))
            self.assertEqual(r["idade"] < 18, menor)

    def test_limites(self):
        from sim import conhecidos
        g = jogo(idade=4)
        with self.assertRaises(ValueError):
            conhecidos.conhecer(g)
        g = jogo(idade=30)
        conhecidos.conhecer(g)
        with self.assertRaises(ValueError):      # 1 por mês
            conhecidos.conhecer(g)
        for _ in range(7):                       # até 8 amigos, um por mês
            engine.advance_months(g, 1)
            conhecidos.conhecer(g)
        engine.advance_months(g, 1)
        with self.assertRaises(ValueError):      # círculo cheio (se ninguém esfriou)
            for _ in range(3):
                conhecidos.conhecer(g)
                engine.advance_months(g, 1)


class TestConvivio(unittest.TestCase):
    """G3b (v0.15.4): conversar com amigo."""

    def test_conversar_regras_e_save(self):
        from sim import conhecidos, convivio
        g = jogo(idade=30)
        r = conhecidos.conhecer(g)
        p = views.player_of(g)
        self.assertEqual([a["id"] for a in convivio.amigos(g)], [r["id"]])
        convivio.conversar(g, r["id"])
        self.assertTrue(convivio.recente(g, p.id, r["id"]))
        with self.assertRaises(ValueError):
            convivio.conversar(g, r["id"])      # 1 por mês
        with self.assertRaises(ValueError):
            convivio.conversar(g, 99999)        # não é amigo
        with tempfile.TemporaryDirectory() as t:
            f = os.path.join(t, "c.db")
            persistence.save_game(g, f)
            g2 = persistence.load_game(f)
        self.assertTrue(convivio.recente(g2, p.id, r["id"]))

    def test_efeito_expira_em_12_meses(self):
        from sim import conhecidos, convivio
        g = jogo(idade=30)
        r = conhecidos.conhecer(g)
        p = views.player_of(g)
        convivio.conversar(g, r["id"])
        engine.advance_months(g, 12)
        self.assertFalse(convivio.recente(g, p.id, r["id"]))


class TestConvite(unittest.TestCase):
    """G3c (v0.15.6): convidar amigo para sair."""

    def test_convidar_custo_limite_e_save(self):
        from sim import conhecidos, convivio
        g = jogo(idade=30)
        r = conhecidos.conhecer(g)
        p = views.player_of(g)
        p.wealth = 1000.0
        convivio.convidar(g, r["id"])
        self.assertAlmostEqual(p.wealth, 1000.0 - 0.03 * g.macro["min_wage"], 2)
        self.assertEqual(convivio.fator(g, p.id, r["id"]), 0.3)
        with self.assertRaises(ValueError):
            convivio.convidar(g, r["id"])       # 1 por mês
        with self.assertRaises(ValueError):
            convivio.conversar(g, r["id"])      # mesmo limite
        with tempfile.TemporaryDirectory() as t:
            f = os.path.join(t, "v.db")
            persistence.save_game(g, f)
            g2 = persistence.load_game(f)
        self.assertEqual(convivio.fator(g2, p.id, r["id"]), 0.3)

    def test_sem_dinheiro_e_menor_nao_paga(self):
        from sim import conhecidos, convivio
        g = jogo(idade=30)
        r = conhecidos.conhecer(g)
        views.player_of(g).wealth = 0.0
        with self.assertRaises(ValueError):
            convivio.convidar(g, r["id"])
        g = jogo(idade=14)
        r = conhecidos.conhecer(g)
        views.player_of(g).wealth = 0.0
        self.assertEqual(convivio.convidar(g, r["id"])["custo"], 0.0)


class TestEncontros(unittest.TestCase):
    """G3d (v0.15.7): aplicativo de encontros (só maiores de 18)."""

    def test_menor_nao_tem_acesso(self):
        from sim import encontros
        for idade in (10, 17):
            g = jogo(idade=idade)
            v = encontros.view(g)
            self.assertFalse(v["disponivel"])
            self.assertEqual(v["candidatos"], [])
            with self.assertRaises(ValueError):
                encontros.escolher(g, 0)

    def test_tres_adultos_compativeis_e_escolha_namora(self):
        from sim import encontros, romance
        g = jogo(idade=30)
        p = views.player_of(g)
        if p.partner_id is not None or p.spouse_id is not None:
            p.partner_id = p.spouse_id = None
        c = encontros.candidatos(g)
        self.assertEqual(len(c), 3)
        self.assertEqual(c, encontros.candidatos(g))   # estável no mês
        self.assertTrue(all(x["idade"] >= 18 and abs(x["idade"] - 30) <= 10 and x["sexo"] != p.sex for x in c))
        estado, n = g.rng.getstate(), len(g.characters)
        r = encontros.escolher(g, 1)
        self.assertEqual(g.rng.getstate(), estado)
        self.assertEqual(len(g.characters), n + 1)
        self.assertEqual(r["nome"], c[1]["nome"])
        self.assertEqual(romance.partner_of(g, p).id, r["id"])
        with self.assertRaises(ValueError):
            encontros.escolher(g, 0)


class TestNamoroJogador(unittest.TestCase):
    """G3e (v0.15.8): terminar e pedir em casamento."""

    def _casal(self):
        from sim import encontros
        g = jogo(idade=30)
        p = views.player_of(g)
        p.partner_id = p.spouse_id = None
        encontros.escolher(g, 0)
        return g, p

    def test_terminar(self):
        from sim import encontros, romance
        g, p = self._casal()
        self.assertIsNotNone(romance.partner_of(g, p))
        encontros.terminar(g)
        self.assertIsNone(romance.partner_of(g, p))
        with self.assertRaises(ValueError):
            encontros.terminar(g)

    def test_pedido_exige_6_meses_e_limite_mensal(self):
        from sim import encontros
        g, p = self._casal()
        with self.assertRaises(ValueError):
            encontros.pedir_em_casamento(g)         # recém-namorando
        g.convivio[(-3, p.id)] = 0
        for _ in range(6):
            engine.advance_months(g, 1)
        p = views.player_of(g)
        if p.partner_id is None:
            self.skipTest("o namoro terminou sozinho nesta semente")
        r = encontros.pedir_em_casamento(g)
        if r["aceitou"]:
            self.assertTrue(engine.has_active_spouse(g, p))
        else:
            with self.assertRaises(ValueError):
                encontros.pedir_em_casamento(g)     # 1 por mês


class TestMemoria(unittest.TestCase):
    """G3f (v0.15.9): memória do relacionamento."""

    def test_vira_proximo_com_6_interacoes_e_persiste(self):
        from sim import conhecidos, convivio
        g = jogo(idade=30)
        r = conhecidos.conhecer(g)
        p = views.player_of(g)
        p.wealth = 10000.0
        for i in range(6):
            self.assertFalse(convivio.proximo(g, p.id, r["id"]))
            (convivio.conversar if i % 2 else convivio.convidar)(g, r["id"])
            g.month = g.month % 12 + 1      # só avança o relógio para liberar o limite mensal
        self.assertTrue(convivio.proximo(g, p.id, r["id"]))
        a = convivio.amigos(g)[0]
        self.assertEqual((a["interacoes"], a["proximo"]), (6, True))
        self.assertAlmostEqual(convivio.fator(g, p.id, r["id"]), 0.3 * 0.7, places=6)   # convite recente × próximo
        with tempfile.TemporaryDirectory() as t:
            f = os.path.join(t, "m.db")
            persistence.save_game(g, f)
            g2 = persistence.load_game(f)
        self.assertTrue(convivio.proximo(g2, p.id, r["id"]))

    def test_amizade_sem_interacao_inalterada(self):
        from sim import conhecidos, convivio
        g = jogo(idade=30)
        r = conhecidos.conhecer(g)
        self.assertEqual(convivio.fator(g, views.player_of(g).id, r["id"]), 1.0)


class TestOndeConhecer(unittest.TestCase):
    """G3g (v0.15.10): escolher onde conhecer."""

    def test_escola_gera_colega_de_turma(self):
        from sim import conhecidos
        g = jogo(idade=14)
        p = views.player_of(g)
        self.assertIn("escola", [x["id"] for x in conhecidos.locais(g)])
        r = conhecidos.conhecer(g, "escola")
        o = g.characters[r["id"]]
        now = (g.year, g.month)
        self.assertTrue(engine._classmates(p, o, now))

    def test_faculdade_so_para_quem_cursa(self):
        from sim import conhecidos
        g = jogo(idade=30)
        p = views.player_of(g)
        p.in_college, p.in_school = False, False
        with self.assertRaises(ValueError):
            conhecidos.conhecer(g, "faculdade")
        p.in_college = True
        r = conhecidos.conhecer(g, "faculdade")
        o = g.characters[r["id"]]
        self.assertTrue(o.in_college and o.age_at(g.year, g.month) >= 18)
        self.assertTrue(engine._classmates(p, o, (g.year, g.month)))


class TestLivros(unittest.TestCase):
    """G4a (v0.15.11): catálogo (lote 1) e leitura."""

    def test_catalogo_integro(self):
        from sim import livros
        ids = [x[0] for x in livros.CATALOGO]
        self.assertEqual(len(ids), len(set(ids)))
        for _, titulo, autor, ano, genero, nivel in livros.CATALOGO:
            self.assertTrue(titulo and autor and genero)
            self.assertIn(nivel, (1, 2, 3))
            self.assertTrue(-800 <= ano <= 2026)

    def test_ler_regras_efeito_e_save(self):
        from sim import livros
        g = jogo(idade=30)
        p = views.player_of(g)
        p.cognition["compreensao_verbal"] = 60
        p.cognition_potential["compreensao_verbal"] = 99
        r = livros.ler(g, "dom_casmurro")
        self.assertEqual(r["titulo"], "Dom Casmurro")
        self.assertTrue(r["concluido"])
        # Pode ler outro livro curto dentro da capacidade mensal de páginas
        r2 = livros.ler(g, "hobbit")
        self.assertEqual(r2["titulo"], "O Hobbit")
        with self.assertRaises(ValueError):
            livros.ler(g, "dom_casmurro")           # já lido
        # Esgotando a capacidade do mês, bloqueia até o próximo mês
        lidos_esp = 2  # dom_casmurro + hobbit
        v = livros.view(g)
        while v["paginas_mes_restantes"] > 0:
            cand = next((x for x in v["nao_lidos"] if x["pode"] and x["id"] != "pequeno_principe"), None)
            if cand is None:
                break
            res_l = livros.ler(g, cand["id"])
            if res_l["concluido"]:
                lidos_esp += 1
            v = livros.view(g)
        with self.assertRaises(ValueError):
            livros.ler(g, "pequeno_principe")
        g.month = g.month % 12 + 1
        with self.assertRaises(ValueError):
            livros.ler(g, "nao_existe")
        with tempfile.TemporaryDirectory() as t:
            f = os.path.join(t, "l.db")
            persistence.save_game(g, f)
            g2 = persistence.load_game(f)
        v = livros.view(g2)
        self.assertEqual(v["total_lidos"], lidos_esp)
        self.assertGreaterEqual(v["total_lidos"], 2)
        self.assertTrue(next(i for i in v["itens"] if i["id"] == "dom_casmurro")["lido"])

    def test_crianca_nao_le_nivel_3(self):
        from sim import livros
        g = jogo(idade=8)
        with self.assertRaises(ValueError):
            livros.ler(g, "dom_casmurro")
