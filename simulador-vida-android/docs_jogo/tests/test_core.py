import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import contextlib
import io

from unittest import mock

from sim import cycle, economy, engine, factory, firms, macro, persistence, romance, ui_cli, work

_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = _R if os.path.isfile(os.path.join(_R, "main.py")) else os.path.join(os.path.dirname(_R), "app", "src", "main", "python")

# v0.13.0: os testes anteriores medem as regras antigas; as novidades (inflação, impostos, pensão, licença) ficam
# desligadas por padrão aqui e as classes novas as ligam explicitamente (ver `NovidadesV013`).
macro.ATIVO = False
economy.IMPOSTOS = False
economy.PENSAO = False
engine.LICENCA = False


class SemDivorcio:
    """Mixin: desliga divórcios e círculo social para testar regras que assumem casais estáveis."""
    def setUp(self):
        self._div, self._circ, self._edu = engine.DIVORCIO_BASE, engine.CIRCULO_SOCIAL, engine.EDUCACAO
        self._trab, self._eco = engine.TRABALHO, engine.ECONOMIA
        engine.TRABALHO = False
        engine.ECONOMIA = False
        self.addCleanup(setattr, engine, "TRABALHO", self._trab)
        self.addCleanup(setattr, engine, "ECONOMIA", self._eco)
        engine.DIVORCIO_BASE = 0.0
        self._rom = romance.ATIVO
        romance.ATIVO = False
        self.addCleanup(setattr, romance, "ATIVO", self._rom)
        self._ges = engine.GESTACAO
        engine.GESTACAO = False
        self.addCleanup(setattr, engine, "GESTACAO", self._ges)
        engine.CIRCULO_SOCIAL = False  # comportamento da v0.2.0 (sem amizades)
        engine.EDUCACAO = False
        self.addCleanup(setattr, engine, "EDUCACAO", self._edu)
        self.addCleanup(setattr, engine, "DIVORCIO_BASE", self._div)
        self.addCleanup(setattr, engine, "CIRCULO_SOCIAL", self._circ)


class SemCirculo:
    """Mixin: desliga só o círculo social (acelera testes de calibração que não o usam)."""
    def setUp(self):
        self._circ, self._edu, self._trab = engine.CIRCULO_SOCIAL, engine.EDUCACAO, engine.TRABALHO
        self._eco = engine.ECONOMIA
        engine.ECONOMIA = False
        self.addCleanup(setattr, engine, "ECONOMIA", self._eco)
        self._rom = romance.ATIVO
        romance.ATIVO = False
        self.addCleanup(setattr, romance, "ATIVO", self._rom)
        self._ges = engine.GESTACAO
        engine.GESTACAO = False
        self.addCleanup(setattr, engine, "GESTACAO", self._ges)
        engine.CIRCULO_SOCIAL = False
        engine.EDUCACAO = False
        engine.TRABALHO = False
        self.addCleanup(setattr, engine, "TRABALHO", self._trab)
        self.addCleanup(setattr, engine, "CIRCULO_SOCIAL", self._circ)
        self.addCleanup(setattr, engine, "EDUCACAO", self._edu)


def snapshot(g):
    """Representação comparável do estado completo da partida."""
    return (
        g.year, g.month, g.player_id, g.next_char_id, g.next_family_id,
        sorted((c.id, c.first_name, c.last_name, c.sex, c.birth_year, c.birth_month,
                round(c.health, 9), c.alive, c.death_year, c.death_month,
                c.mother_id, c.father_id, c.family_id, c.spouse_id, c.ex_spouse_id,
                tuple(sorted(c.cognition_potential.items())),
                tuple(sorted(c.personality.items())), tuple(sorted(c.cognition.items())))
               for c in g.characters.values()),
        [(e.seq, e.char_id, e.year, e.month, e.category, e.text) for e in g.biography],
        sorted(g.friendships.items()),
        sorted((c.id, c.schooling_years, c.in_school, c.dropped_out, c.school_performance)
               for c in g.characters.values()),
        sorted((c.id, c.occupation, c.job_start, c.seeking_since, c.retired, c.jobs_held)
               for c in g.characters.values()),
        sorted((c.id, c.rank, c.rank_since, c.informal, c.workplace, c.experience, c.income, c.wealth,
                c.unemp_until, c.unemp_amount)
               for c in g.characters.values()),
        sorted((f.id, f.name, f.sector, f.size, f.founded, f.closed, tuple(sorted(f.slots.items())))
               for f in g.firms.values()),
        g.next_firm_id,
        g.rng.getstate(),
    )


class TestCriacao(unittest.TestCase):
    def test_idade_coerente_em_todos_os_meses(self):
        for mes in range(1, 13):
            g = factory.new_game("t", seed=mes, month=mes)
            for idade in (0, 1, 17, 18, 59, 60, 110):
                for _ in range(20):
                    c = factory.create_character(g, idade)
                    self.assertEqual(c.age_at(g.year, g.month), idade)

    def test_validacao(self):
        g = factory.new_game("t", 1)
        with self.assertRaises(ValueError):
            factory.create_character(g, -1)
        with self.assertRaises(ValueError):
            factory.create_character(g, 111)
        with self.assertRaises(ValueError):
            factory.create_character(g, 30, sex="X")

    def test_familia_coerente(self):
        for seed in range(50):
            g = factory.new_game("t", seed)
            r = factory.create_family(g, "Teixeira", 4)
            m, p, fs = r["mother"], r["father"], r["children"]
            self.assertEqual(len(fs), 4)
            for f in fs:
                self.assertEqual((f.mother_id, f.father_id), (m.id, p.id))
                self.assertEqual(f.last_name, "Teixeira")
                self.assertEqual(f.family_id, r["family"].id)
                self.assertGreaterEqual(m.age_at(g.year, g.month) - f.age_at(g.year, g.month), 16)
                self.assertGreaterEqual(p.age_at(g.year, g.month) - f.age_at(g.year, g.month), 16)
            self.assertEqual(g.player_id, fs[0].id)  # filho mais velho


class TestTempo(unittest.TestCase):
    def test_avanco_e_virada_de_ano(self):
        g = factory.new_game("t", 1, year=2026, month=11)
        factory.create_character(g, 20)
        engine.advance_months(g, 1)
        self.assertEqual((g.year, g.month), (2026, 12))
        engine.advance_months(g, 1)
        self.assertEqual((g.year, g.month), (2027, 1))
        engine.advance_months(g, 6)
        self.assertEqual((g.year, g.month), (2027, 7))
        engine.advance_months(g, 12)
        self.assertEqual((g.year, g.month), (2028, 7))
        with self.assertRaises(ValueError):
            engine.advance_months(g, 0)

    def test_idade_muda_exatamente_no_mes_de_nascimento(self):
        g = factory.new_game("t", 3)
        c = factory.create_character(g, 30)
        c.health = 100
        alvo = c.age_at(g.year, g.month)
        for _ in range(24):
            antes = c.age_at(g.year, g.month)
            engine.advance_months(g, 1)
            depois = c.age_at(g.year, g.month)
            self.assertEqual(depois - antes, 1 if g.month == c.birth_month else 0)
        self.assertEqual(c.age_at(g.year, g.month), alvo + 2)

    def test_aniversario_do_jogador_registrado(self):
        g = factory.new_game("t", 5)
        c = factory.create_character(g, 25)
        g.player_id = c.id
        c.health = 100
        engine.advance_months(g, 12)
        self.assertEqual(len(g.events_for(c.id, "aniversario")), 1)

    def test_determinismo(self):
        def rodar():
            g = factory.new_game("t", 99)
            factory.create_family(g, None, 3)
            engine.advance_months(g, 600)
            return snapshot(g)
        self.assertEqual(rodar(), rodar())


class TestMorte(unittest.TestCase):
    def test_idoso_doente_morre_e_para_de_envelhecer(self):
        g = factory.new_game("t", 7)
        c = factory.create_character(g, 100)
        c.health = 0
        engine.advance_months(g, 240)
        self.assertFalse(c.alive)
        self.assertIsNotNone(c.death_year)
        idade_morte = c.age_at(c.death_year, c.death_month)
        n_eventos = len(g.biography)
        engine.advance_months(g, 120)
        self.assertEqual(len(g.biography), n_eventos)  # morto não gera eventos
        self.assertEqual(c.age_at(c.death_year, c.death_month), idade_morte)
        self.assertEqual(len(g.events_for(c.id, "morte")), 1)

    def test_luto_familiar(self):
        g = factory.new_game("t", 11)
        r = factory.create_family(g, "Souza", 1)
        filho = r["children"][0]
        mae = r["mother"]
        mae.health = 0
        mae.birth_year -= 60  # mãe muito idosa => morte quase certa
        engine.advance_months(g, 240)
        self.assertFalse(mae.alive)
        textos = [e.text for e in g.events_for(filho.id, "falecimento_familiar")]
        self.assertTrue(any("sua mãe" in t and mae.full_name in t for t in textos))

    def test_mortalidade_cresce_com_idade_e_baixa_saude(self):
        self.assertLess(engine.mortality_annual(30, 100), engine.mortality_annual(85, 100))
        self.assertLess(engine.mortality_annual(50, 100), engine.mortality_annual(50, 20))
        self.assertLessEqual(engine.mortality_annual(100, 0), 0.95)


class TestConjuge(SemDivorcio, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "jogo.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_vinculo_mutuo_na_familia(self):
        g = factory.new_game("t", 1)
        r = factory.create_family(g, "Lima", 2)
        self.assertEqual(r["mother"].spouse_id, r["father"].id)
        self.assertEqual(r["father"].spouse_id, r["mother"].id)
        self.assertTrue(all(f.spouse_id is None for f in r["children"]))
        solo = factory.create_character(g, 30)
        self.assertIsNone(solo.spouse_id)

    def test_conjuge_persiste(self):
        g = factory.new_game("t", 2)
        r = factory.create_family(g, "Lima", 1)
        persistence.save_game(g, self.path)
        g2 = persistence.load_game(self.path)
        self.assertEqual(g2.characters[r["mother"].id].spouse_id, r["father"].id)
        self.assertEqual(snapshot(g), snapshot(g2))
        con = sqlite3.connect(self.path)
        versao = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        con.close()
        self.assertEqual(versao, str(persistence.SCHEMA_VERSION))

    def test_luto_de_conjuge(self):
        g = factory.new_game("t", 3)
        r = factory.create_family(g, "Souza", 0)
        pai, mae = r["father"], r["mother"]
        engine._die(g, pai, pai.age_at(g.year, g.month))
        textos = [e.text for e in g.events_for(mae.id, "falecimento_familiar")]
        self.assertEqual(len(textos), 1)
        self.assertIn("seu marido", textos[0])
        self.assertIn(pai.full_name, textos[0])
        self.assertEqual(mae.spouse_id, pai.id)  # vínculo histórico preservado
        # e o inverso: esposa falece, marido enlutado
        g2 = factory.new_game("t", 4)
        r2 = factory.create_family(g2, "Souza", 0)
        engine._die(g2, r2["mother"], 40)
        t2 = [e.text for e in g2.events_for(r2["father"].id, "falecimento_familiar")]
        self.assertIn("sua esposa", t2[0])

    def test_migracao_de_save_v1(self):
        # Constrói um save no formato v1 (sem spouse_id) a partir de um save atual.
        g = factory.new_game("antigo", 7, year=2030, month=3)
        factory.create_family(g, "Lima", 2)
        engine.advance_months(g, 30)
        persistence.save_game(g, self.path)
        con = sqlite3.connect(self.path)
        for col in ("spouse_id", "cognition_potential", "ex_spouse_id"):
            con.execute(f"ALTER TABLE characters DROP COLUMN {col}")
        con.execute("UPDATE meta SET value='1' WHERE key='schema_version'")
        con.commit()
        con.close()
        # Carregar v1 funciona; cônjuge fica vazio; demais dados idênticos.
        g1 = persistence.load_game(self.path)
        self.assertTrue(all(c.spouse_id is None for c in g1.characters.values()))
        self.assertEqual((g1.year, g1.month, len(g1.characters), len(g1.biography)),
                         (g.year, g.month, len(g.characters), len(g.biography)))
        self.assertEqual(g1.rng.getstate(), g.rng.getstate())
        # O arquivo v1 não foi alterado ao carregar.
        con = sqlite3.connect(self.path)
        self.assertEqual(con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0], "1")
        con.close()
        # Jogar e salvar converte para a versão atual, e recarrega normalmente.
        engine.advance_months(g1, 12)
        persistence.save_game(g1, self.path)
        con = sqlite3.connect(self.path)
        self.assertEqual(con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],
                         str(persistence.SCHEMA_VERSION))
        con.close()
        self.assertEqual(snapshot(g1), snapshot(persistence.load_game(self.path)))


class TestNascimentos(SemDivorcio, unittest.TestCase):
    def _casal(self, g, idade_mae=28, idade_pai=30):
        m = factory.create_character(g, idade_mae, "F", last_name="Lima")
        f = factory.create_character(g, idade_pai, "M", last_name="Lima")
        m.spouse_id, f.spouse_id = f.id, m.id
        m.health = f.health = 100
        return m, f

    def test_nascimento_vincula_pais_data_e_eventos(self):
        g = factory.new_game("t", 1)
        fam = factory.create_family(g, "Lima", 0)["family"]
        casais = [self._casal(g, 22) for _ in range(10)]
        for m, f in casais:
            m.family_id = f.family_id = fam.id
        engine.advance_months(g, 12 * 20)
        total = 0
        for m, f in casais:
            filhos = g.children_of(m.id)
            total += len(filhos)
            for c in filhos:
                self.assertEqual((c.mother_id, c.father_id), (m.id, f.id))
                self.assertEqual((c.last_name, c.family_id), ("Lima", fam.id))
                self.assertIsNone(c.spouse_id)
                nasc = g.events_for(c.id, "nascimento")
                self.assertEqual(len(nasc), 1)
                self.assertEqual((nasc[0].year, nasc[0].month), (c.birth_year, c.birth_month))
            self.assertEqual(len(g.events_for(m.id, "nascimento_filho")), len(filhos))
            self.assertEqual(len(g.events_for(f.id, "nascimento_filho")), len(filhos))
            for e in g.events_for(m.id, "nascimento_filho"):
                self.assertIn("Deu à luz", e.text)
                self.assertTrue("seu filho" in e.text or "sua filha" in e.text)
        self.assertGreater(total, 5)

    def test_recem_nascido_nasce_no_mes_corrente_com_idade_zero(self):
        g = factory.new_game("t", 2)
        m, f = self._casal(g, 25)
        for _ in range(240):
            engine.advance_months(g, 1)
            novos = [c for c in g.children_of(m.id) if (c.birth_year, c.birth_month) == (g.year, g.month)]
            for c in novos:
                self.assertEqual(c.age_at(g.year, g.month), 0)
                self.assertEqual(g.events_for(c.id, "aniversario"), [])
            if novos:
                return
        self.fail("nenhum nascimento em 20 anos")

    def test_sem_nascimento_fora_das_condicoes(self):
        g = factory.new_game("t", 3)
        solo = factory.create_character(g, 28, "F")                 # sem cônjuge
        viuva, marido = self._casal(g, 28)
        marido.alive = False                                        # cônjuge morto
        velha, v2 = self._casal(g, 46)                              # fora da idade fértil
        nova, v3 = self._casal(g, 13)                               # abaixo da idade fértil
        homem = factory.create_character(g, 30, "M")
        homem.spouse_id = solo.id                                   # vínculo unilateral
        engine.advance_months(g, 12)                                # nova tem no máx. 14 anos ao final
        for c in (solo, viuva, velha, homem, marido):
            self.assertEqual(g.children_of(c.id), [], c.full_name)
        self.assertEqual(g.children_of(nova.id), [])

    def test_intervalo_minimo_e_limite_de_filhos(self):
        g = factory.new_game("t", 4)
        m, f = self._casal(g, 25)
        engine.advance_months(g, 12 * 20)
        datas = sorted(c.birth_year * 12 + c.birth_month for c in g.children_of(m.id))
        for a, b in zip(datas, datas[1:]):
            self.assertGreaterEqual(b - a, engine.INTERVALO_MIN_MESES)
        self.assertLessEqual(len(datas), engine.MAX_FILHOS)
        # limite: mãe com 10 filhos não concebe
        g2 = factory.new_game("t", 5)
        m2, f2 = self._casal(g2, 25)
        for _ in range(engine.MAX_FILHOS):
            c = factory.create_character(g2, 0, mother_id=m2.id, father_id=f2.id)
            c.birth_year -= 5
        self.assertFalse(engine._can_conceive(g2, m2, f2, 25))

    def test_taxa_de_natalidade_na_faixa(self):
        total = n = 0
        for seed in (1, 2):
            g = factory.new_game("cal", seed)
            maes = []
            for _ in range(200):
                m, _f = self._casal(g, 15, 20)
                maes.append(m)
            engine.advance_months(g, 12 * 30)
            total += sum(len(g.children_of(m.id)) for m in maes)
            n += len(maes)
        media = total / n
        self.assertGreaterEqual(media, 1.5, media)   # medido ~1,87
        self.assertLessEqual(media, 2.3, media)

    def test_persistencia_com_nascimentos(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "n.db")
            g = factory.new_game("t", 6)
            factory.create_family(g, "Dias", 1)
            engine.advance_months(g, 12 * 8)
            persistence.save_game(g, path)
            g2 = persistence.load_game(path)
            self.assertEqual(snapshot(g), snapshot(g2))
            engine.advance_months(g, 12 * 8)
            engine.advance_months(g2, 12 * 8)
            self.assertEqual(snapshot(g), snapshot(g2))


class TestCasamento(SemDivorcio, unittest.TestCase):
    def _pool(self, g, n=100, idade0=20, span=10):
        return [factory.create_character(g, idade0 + i % span, "FM"[i % 2]) for i in range(n)]

    def test_vinculo_mutuo_regras_e_eventos(self):
        g = factory.new_game("t", 1)
        pool = self._pool(g, 120, 20, 30)
        antes = {c.id: (c.last_name, c.family_id) for c in pool}
        engine.advance_months(g, 12 * 10)
        casados = [c for c in pool if c.spouse_id]
        self.assertGreater(len(casados), 20)
        for c in casados:
            sp = g.characters[c.spouse_id]
            self.assertEqual(sp.spouse_id, c.id)
            self.assertNotEqual(c.sex, sp.sex)
            self.assertGreaterEqual(c.age_at(g.year, g.month), 18)
            diff_meses = abs((c.birth_year * 12 + c.birth_month) - (sp.birth_year * 12 + sp.birth_month))
            self.assertLessEqual(diff_meses, (engine.DIFERENCA_IDADE_MAX + 1) * 12)
            self.assertFalse(engine.close_kin(c, sp))
            textos = [e.text for e in g.events_for(c.id, "casamento")]
            self.assertEqual(textos, [f"Casou-se com {sp.full_name}."])
            self.assertEqual((c.last_name, c.family_id), antes[c.id])  # nomes não mudam

    def test_ninguem_casa_fora_das_regras(self):
        g = factory.new_game("t", 2)
        criancas = [factory.create_character(g, 5 + i % 4, "FM"[i % 2]) for i in range(20)]
        mulheres = [factory.create_character(g, 25, "F") for _ in range(20)]      # mesmo sexo
        engine.advance_months(g, 12 * 2)  # crianças ainda < 18
        for c in criancas + mulheres:
            self.assertIsNone(c.spouse_id)
        # diferença de idade > 10: sem a regra, boa parte casaria em 15 anos
        g2 = factory.new_game("t", 3)
        jovens = [factory.create_character(g2, 20, "F") for _ in range(40)]
        velhos = [factory.create_character(g2, 45, "M") for _ in range(40)]
        engine.advance_months(g2, 12 * 15)
        self.assertTrue(all(c.spouse_id is None for c in jovens + velhos))

    def test_parentes_proximos_nao_casam(self):
        g = factory.new_game("t", 4)
        mae = factory.create_character(g, 40, "F")
        pai = factory.create_character(g, 42, "M")
        irmaos = [factory.create_character(g, 20 + i, "FM"[i % 2], mother_id=mae.id, father_id=pai.id)
                  for i in range(8)]
        meio = factory.create_character(g, 22, "M", father_id=pai.id)  # meio-irmão
        for c in irmaos + [meio]:
            c.health = 100
        engine.advance_months(g, 12 * 15)
        for a in irmaos + [meio]:
            for b in irmaos + [meio]:
                if a.id != b.id:
                    self.assertTrue(engine.close_kin(a, b))
                    self.assertNotEqual(a.spouse_id, b.id)
        self.assertTrue(engine.close_kin(mae, irmaos[0]))
        self.assertFalse(engine.close_kin(irmaos[0], factory.create_character(g, 25, "M")))

    def test_viuvo_casa_de_novo_e_unilateral_conta_como_solteiro(self):
        g = factory.new_game("t", 5)
        viuvos = []
        for _ in range(30):
            m = factory.create_character(g, 30, "F")
            f = factory.create_character(g, 31, "M")
            m.spouse_id, f.spouse_id = f.id, m.id
            engine._die(g, f, 31)                       # f morre; m fica viúva
            viuvos.append((m, f))
            self.assertFalse(engine.has_active_spouse(g, m))
        solteiros = [factory.create_character(g, 31, "M") for _ in range(30)]
        engine.advance_months(g, 12 * 10)
        novos = [(m, f) for m, f in viuvos if m.spouse_id != f.id]
        self.assertGreater(len(novos), 5)
        for m, f in novos:
            self.assertFalse(f.alive)                    # falecido permanece como estava
            self.assertEqual(f.spouse_id, m.id)
            self.assertNotEqual(g.characters[m.spouse_id].id, f.id)
        # vínculo unilateral = solteiro
        a = factory.create_character(g, 30, "F")
        b = factory.create_character(g, 30, "M")
        b.spouse_id = a.id
        self.assertFalse(engine.has_active_spouse(g, b))
        self.assertFalse(engine.has_active_spouse(g, a))

    def test_taxa_de_casamento_na_faixa(self):
        total = casados = 0
        for seed in (1, 2, 3):
            g = factory.new_game("cal", seed)
            pool = self._pool(g, 200)
            engine.advance_months(g, 12 * 10)
            total += len(pool)
            casados += sum(1 for c in pool if c.spouse_id)
        frac = casados / total
        self.assertGreaterEqual(frac, 0.45, frac)   # medido ~0,59
        self.assertLessEqual(frac, 0.75, frac)

    def test_casamento_leva_a_filhos(self):
        g = factory.new_game("t", 6)
        pool = self._pool(g, 100, 20, 6)
        ids = {c.id for c in pool}
        engine.advance_months(g, 12 * 20)
        filhos = [c for c in g.characters.values() if c.id not in ids]
        self.assertGreater(len(filhos), 10)
        for c in filhos:
            mae, pai = g.characters[c.mother_id], g.characters[c.father_id]
            self.assertTrue(g.events_for(mae.id, "casamento"))
            self.assertTrue(g.events_for(pai.id, "casamento"))

    def test_persistencia_com_casamentos(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.db")
            g = factory.new_game("t", 7)
            self._pool(g, 60)
            engine.advance_months(g, 12 * 5)
            persistence.save_game(g, path)
            g2 = persistence.load_game(path)
            self.assertEqual(snapshot(g), snapshot(g2))
            engine.advance_months(g, 12 * 5)
            engine.advance_months(g2, 12 * 5)
            self.assertEqual(snapshot(g), snapshot(g2))


class TestCalibracao(SemCirculo, unittest.TestCase):
    def test_expectativa_de_vida_na_faixa(self):
        idades = []
        for seed in (1, 2, 3):
            g = factory.new_game("cal", seed)
            nascidos = [factory.create_character(g, 0) for _ in range(600)]
            engine.advance_months(g, 12 * 115)
            self.assertTrue(all(not c.alive for c in nascidos))
            idades += [c.age_at(c.death_year, c.death_month) for c in nascidos]
        media = sum(idades) / len(idades)
        self.assertGreaterEqual(media, 73, media)
        self.assertLessEqual(media, 77, media)

    def test_saude_na_velhice_nao_colapsa(self):
        g = factory.new_game("cal", 5)
        for _ in range(300):
            factory.create_character(g, 60)
        engine.advance_months(g, 12 * 20)  # todos com ~80 anos
        vivos = [c for c in g.characters.values() if c.alive]
        self.assertGreater(len(vivos), 50)
        media = sum(c.health for c in vivos) / len(vivos)
        self.assertGreater(media, 40, media)


class TestPersistencia(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "s", "jogo.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_ida_e_volta(self):
        g = factory.new_game("Minha vida", 42, year=2030, month=5)
        factory.create_family(g, "Lima", 3)
        factory.create_character(g, 70)
        engine.advance_months(g, 100)
        persistence.save_game(g, self.path)
        g2 = persistence.load_game(self.path)
        self.assertEqual(snapshot(g), snapshot(g2))
        self.assertEqual((g2.name, g2.seed), ("Minha vida", 42))
        self.assertEqual({f.id: f.name for f in g.families.values()},
                         {f.id: f.name for f in g2.families.values()})

    def test_continuar_apos_carregar_equivale_a_nao_parar(self):
        a = factory.new_game("t", 2024)
        factory.create_family(a, None, 3)
        engine.advance_months(a, 120)
        persistence.save_game(a, self.path)
        b = persistence.load_game(self.path)
        engine.advance_months(a, 360)
        engine.advance_months(b, 360)
        self.assertEqual(snapshot(a), snapshot(b))

    def test_sem_jogador(self):
        g = factory.new_game("vazio", 1)
        persistence.save_game(g, self.path)
        self.assertIsNone(persistence.load_game(self.path).player_id)

    def test_regravar_substitui_e_nao_deixa_tmp(self):
        g = factory.new_game("t", 1)
        factory.create_character(g, 10)
        persistence.save_game(g, self.path)
        factory.create_character(g, 20)
        persistence.save_game(g, self.path)
        self.assertEqual(len(persistence.load_game(self.path).characters), 2)
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_erros_de_carga(self):
        with self.assertRaises(FileNotFoundError):
            persistence.load_game(os.path.join(self.tmp.name, "nao_existe.db"))
        g = factory.new_game("t", 1)
        persistence.save_game(g, self.path)
        con = sqlite3.connect(self.path)
        con.execute("UPDATE meta SET value='999' WHERE key='schema_version'")
        con.commit()
        con.close()
        with self.assertRaises(ValueError):
            persistence.load_game(self.path)
        lixo = os.path.join(self.tmp.name, "lixo.db")
        with open(lixo, "w") as f:
            f.write("isto não é sqlite")
        with self.assertRaises(ValueError):
            persistence.load_game(lixo)


class TestBiografia(unittest.TestCase):
    def test_filtros_e_ordem_cronologica(self):
        g = factory.new_game("t", 8)
        c = factory.create_character(g, 40)
        g.player_id = c.id
        c.health = 100
        engine.advance_months(g, 36)
        todos = g.events_for(c.id)
        chaves = [(e.year, e.month, e.seq) for e in todos]
        self.assertEqual(chaves, sorted(chaves))
        self.assertEqual(todos[0].category, "nascimento")  # evento retroativo vem primeiro
        self.assertTrue(all(e.category == "aniversario" for e in g.events_for(c.id, "aniversario")))
        periodo = g.events_for(c.id, from_year=2027, to_year=2027)
        self.assertTrue(periodo and all(e.year == 2027 for e in periodo))


def _corr(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    return cov / (vx * vy) ** 0.5


class TestHerancaECognicao(unittest.TestCase):
    def _bebes(self, n=1500, seed=5):
        g = factory.new_game("t", seed)
        out = []
        for _ in range(n):
            m = factory.create_character(g, 30, "F")
            f = factory.create_character(g, 32, "M")
            out.append((m, f, factory.create_character(
                g, 0, mother_id=m.id, father_id=f.id, birth=(g.year, g.month), inherit_from=(m, f))))
        return out

    def test_correlacao_filho_pais_positiva_e_media_estavel(self):
        bebes = self._bebes()
        for t in ("neuroticismo", "amabilidade", "abertura"):
            r = _corr([(m.personality[t] + f.personality[t]) / 2 for m, f, _ in bebes],
                      [c.personality[t] for _, _, c in bebes])
            self.assertGreater(r, 0.2, t)
            media = sum(c.personality[t] for _, _, c in bebes) / len(bebes)
            self.assertAlmostEqual(media, 50, delta=2.5, msg=t)
        r = _corr([(m.cognition_potential["memoria"] + f.cognition_potential["memoria"]) / 2 for m, f, _ in bebes],
                  [c.cognition_potential["memoria"] for _, _, c in bebes])
        self.assertGreater(r, 0.25)

    def test_variancia_preservada_e_limites(self):
        bebes = self._bebes()
        vals = [c.personality["extroversao"] for _, _, c in bebes]
        mu = sum(vals) / len(vals)
        sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5
        self.assertAlmostEqual(sd, 15, delta=2.5)
        for _, _, c in bebes:
            for v in list(c.personality.values()) + list(c.cognition.values()) + list(c.cognition_potential.values()):
                self.assertTrue(1 <= v <= 99)

    def test_cognicao_cresce_ate_o_potencial_aos_18(self):
        g = factory.new_game("t", 2)
        c = factory.create_character(g, 0)
        c.health = 100
        pot = dict(c.cognition_potential)
        self.assertLess(sum(c.cognition.values()), sum(pot.values()))
        ant = sum(c.cognition.values())
        for _ in range(18):
            engine.advance_months(g, 12)
            if not c.alive:
                self.skipTest("morreu")
            self.assertGreaterEqual(sum(c.cognition.values()), ant - 8)  # arredondamento
            ant = sum(c.cognition.values())
        for k in pot:
            self.assertAlmostEqual(c.cognition[k], pot[k], delta=1)

    def test_adultos_avulsos_tem_cognicao_igual_ao_potencial(self):
        g = factory.new_game("t", 3)
        c = factory.create_character(g, 40)
        self.assertEqual(c.cognition, c.cognition_potential)

    def test_crianca_avulsa_tem_cognicao_menor_que_adulta_na_media(self):
        g = factory.new_game("t", 4)
        kids = [sum(factory.create_character(g, 3).cognition.values()) for _ in range(300)]
        adults = [sum(factory.create_character(g, 30).cognition.values()) for _ in range(300)]
        self.assertLess(sum(kids) / 300, 0.75 * sum(adults) / 300)


class TestDivorcio(unittest.TestCase):
    def _casais(self, g, n, **pers):
        out = []
        for i in range(n):
            m = factory.create_character(g, 35, "F", last_name="Lima")
            f = factory.create_character(g, 37, "M", last_name="Lima")
            m.spouse_id, f.spouse_id = f.id, m.id
            m.health = f.health = 100
            for c in (m, f):
                c.personality.update(pers)
            out.append((m, f))
        return out

    def test_divorcio_desfaz_vinculo_registra_eventos_e_preserva_filhos(self):
        g = factory.new_game("t", 1)
        r = factory.create_family(g, "Lima", 2)
        m, f, kids = r["mother"], r["father"], r["children"]
        engine._divorce(g, m, f)
        self.assertIsNone(m.spouse_id)
        self.assertIsNone(f.spouse_id)
        self.assertEqual((m.ex_spouse_id, f.ex_spouse_id), (f.id, m.id))
        self.assertFalse(engine.has_active_spouse(g, m))
        for p in (m, f):
            self.assertEqual(len(g.events_for(p.id, "divorcio")), 1)
        for k in kids:
            self.assertEqual((k.mother_id, k.father_id), (m.id, f.id))
            if k.age_at(g.year, g.month) < 18:
                self.assertEqual(len(g.events_for(k.id, "divorcio_pais")), 1)
        self.assertEqual((m.last_name, f.last_name), ("Lima", "Lima"))

    def test_nao_ha_nascimento_apos_divorcio(self):
        g = factory.new_game("t", 2)
        casais = self._casais(g, 30)
        for m, f in casais:
            engine._divorce(g, m, f)
        antes = len(g.characters)
        # ninguém tem cônjuge ativo, então nada nasce
        engine._births(g)
        self.assertEqual(len(g.characters), antes)

    def test_ex_nao_casa_de_novo_com_o_ex(self):
        g = factory.new_game("t", 3)
        (m, f), = self._casais(g, 1)
        engine._divorce(g, m, f)
        self.assertFalse(engine._can_marry(m, f, (g.year, g.month), g))
        outro = factory.create_character(g, 37, "M")
        self.assertTrue(engine._can_marry(m, outro, (g.year, g.month), g))

    def test_personalidade_muda_o_risco(self):
        g = factory.new_game("t", 4)
        (m1, f1), (m2, f2) = self._casais(g, 2)
        for c in (m1, f1):
            c.personality.update(neuroticismo=90, amabilidade=10, conscienciosidade=10)
        for c in (m2, f2):
            c.personality.update(neuroticismo=10, amabilidade=90, conscienciosidade=90)
        now = (g.year, g.month)
        self.assertGreater(engine.divorce_risk_multiplier(m1, f1, now),
                           2 * engine.divorce_risk_multiplier(m2, f2, now))

    def test_casais_jovens_tem_risco_maior(self):
        g = factory.new_game("t", 5)
        (m, f), = self._casais(g, 1)
        now = (g.year, g.month)
        velho = engine.divorce_risk_multiplier(m, f, now)
        m.birth_year += 10  # 25 anos
        self.assertGreater(engine.divorce_risk_multiplier(m, f, now), velho)

    def test_taxa_de_divorcio_em_20_anos_na_faixa_e_neuroticos_divorciam_mais(self):
        g = factory.new_game("t", 6)
        neu = self._casais(g, 250, neuroticismo=85, amabilidade=30)
        cal = self._casais(g, 250, neuroticismo=15, amabilidade=70)
        engine.advance_months(g, 12 * 15)
        taxa = lambda cs: sum(1 for m, f in cs if g.events_for(m.id, "divorcio")) / len(cs)
        t_neu, t_cal = taxa(neu), taxa(cal)
        self.assertGreater(t_neu, t_cal)
        self.assertTrue(0.05 <= (t_neu + t_cal) / 2 <= 0.45, (t_neu, t_cal))

    def test_recasamento_de_divorciado_nunca_com_o_ex(self):
        g = factory.new_game("t", 7)
        casais = self._casais(g, 120)
        for m, f in casais:
            engine._divorce(g, m, f)
        for i in range(240):
            factory.create_character(g, 32 + i % 8, "FM"[i % 2])
        engine.advance_months(g, 12 * 6)
        recasados = 0
        for m, f in casais:
            for p, ex in ((m, f), (f, m)):
                if engine.has_active_spouse(g, p):
                    recasados += 1
                    self.assertNotEqual(p.spouse_id, ex.id)
        self.assertGreater(recasados, 10)

    def test_persistencia_com_divorcio(self):
        g = factory.new_game("t", 8)
        self._casais(g, 40)
        engine.advance_months(g, 12 * 10)
        self.assertTrue(any(c.ex_spouse_id for c in g.characters.values()))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.db")
            persistence.save_game(g, path)
            g2 = persistence.load_game(path)
            self.assertEqual(snapshot(g), snapshot(g2))
            engine.advance_months(g, 24)
            engine.advance_months(g2, 24)
            self.assertEqual(snapshot(g), snapshot(g2))


class TestParentescoEstendido(unittest.TestCase):
    def _arvore(self):
        g = factory.new_game("t", 1)
        avo = factory.create_character(g, 80, "M")
        avo2 = factory.create_character(g, 78, "F")
        pai = factory.create_character(g, 50, "M", mother_id=avo2.id, father_id=avo.id)
        tio = factory.create_character(g, 47, "F", mother_id=avo2.id, father_id=avo.id)
        mae = factory.create_character(g, 48, "F")
        filho = factory.create_character(g, 25, "M", mother_id=mae.id, father_id=pai.id)
        prima = factory.create_character(g, 24, "F", father_id=None, mother_id=tio.id)
        estranha = factory.create_character(g, 25, "F")
        return g, avo, pai, tio, filho, prima, estranha

    def test_avo_tio_primo_bloqueados_estranho_livre(self):
        g, avo, pai, tio, filho, prima, estranha = self._arvore()
        self.assertTrue(engine.close_kin(filho, avo, g))      # neto-avô
        self.assertTrue(engine.close_kin(filho, tio, g))      # sobrinho-tia
        self.assertTrue(engine.close_kin(filho, prima, g))    # primos
        self.assertFalse(engine.close_kin(filho, estranha, g))
        # Compatibilidade: sem `game` só pais/filhos/irmãos.
        self.assertFalse(engine.close_kin(filho, prima))
        self.assertTrue(engine.close_kin(pai, tio))

    def test_ninguem_casa_com_primo_na_simulacao(self):
        for seed in range(4):
            g = factory.new_game("t", seed)
            fam = [factory.create_family(g, "Lima", 6) for _ in range(4)]
            engine.advance_months(g, 12 * 25)
            for ev in [e for e in g.biography if e.category == "casamento"]:
                c = g.characters[ev.char_id]
                if c.spouse_id in g.characters:
                    self.assertFalse(engine.close_kin(c, g.characters[c.spouse_id], g))


class TestMortalidadeMaterna(unittest.TestCase):
    def test_risco_cresce_com_idade_e_saude_baixa(self):
        self.assertLess(engine.maternal_death_risk(25, 100), engine.maternal_death_risk(41, 100))
        self.assertLess(engine.maternal_death_risk(25, 100), engine.maternal_death_risk(25, 20))
        self.assertLess(engine.maternal_death_risk(25, 100), 0.002)

    def test_morte_no_parto_registra_causa_e_luto(self):
        g = factory.new_game("t", 1)
        r = factory.create_family(g, "Lima", 1)
        m = r["mother"]
        engine._die(g, m, 30, " em decorrência do parto")
        self.assertIn("parto", g.events_for(m.id, "morte")[0].text)
        self.assertTrue(g.events_for(r["father"].id, "falecimento_familiar"))


class TestMigracaoV2(unittest.TestCase):
    def test_save_v2_legivel_potencial_igual_a_cognicao(self):
        g = factory.new_game("antigo", 9)
        factory.create_family(g, "Lima", 3)
        engine.advance_months(g, 24)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "v2.db")
            persistence.save_game(g, path)
            con = sqlite3.connect(path)
            for col in ("cognition_potential", "ex_spouse_id"):
                con.execute(f"ALTER TABLE characters DROP COLUMN {col}")
            con.execute("DROP TABLE friendships")
            con.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
            con.commit()
            con.close()
            g2 = persistence.load_game(path)
            for c in g2.characters.values():
                self.assertEqual(c.cognition_potential, c.cognition)
                self.assertIsNone(c.ex_spouse_id)
            persistence.save_game(g2, path)
            con = sqlite3.connect(path)
            self.assertEqual(con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],
                             str(persistence.SCHEMA_VERSION))
            con.close()
            persistence.load_game(path)


class TestCirculoSocial(unittest.TestCase):
    def _pop(self, g, n=120, idade=(20, 40)):
        return [factory.create_character(g, idade[0] + i % (idade[1] - idade[0]), "FM"[i % 2]) for i in range(n)]

    def test_amizade_simetrica_com_evento_e_sem_autoamizade(self):
        g = factory.new_game("t", 1)
        self._pop(g)
        engine.advance_months(g, 24)
        self.assertGreater(len(g.friendships), 20)
        for (a, b), (y, m) in g.friendships.items():
            self.assertLess(a, b)
            self.assertTrue(g.are_friends(a, b) and g.are_friends(b, a))
            self.assertIn(b, g.friend_ids(a))
        eva = g.events_for(None, "amizade")
        fim = g.events_for(None, "amizade_fim")
        self.assertEqual(len(eva) - len(fim), 2 * len(g.friendships))  # v0.10.0: amizades também terminam
        with self.assertRaises(ValueError):
            g.add_friendship(3, 3)

    def test_regras_idade_parentesco_limite_e_minimo(self):
        g = factory.new_game("t", 2)
        for _ in range(8):
            factory.create_family(g, None, 4)
        engine.advance_months(g, 12 * 8)
        now = (g.year, g.month)
        for (a, b) in g.friendships:
            ca, cb = g.characters[a], g.characters[b]
            self.assertFalse(engine.close_kin(ca, cb, g))
        for c in g.characters.values():
            vivos = [i for i in g.friend_ids(c.id) if g.characters[i].alive]
            self.assertLessEqual(len(vivos), engine.MAX_AMIGOS)
        for ev in g.events_for(None, "amizade"):  # na data do evento ambos tinham >= 6 anos
            c = g.characters[ev.char_id]
            self.assertGreaterEqual(c.age_at(ev.year, ev.month), engine.IDADE_AMIZADE_MIN)

    def test_diferenca_de_idade_respeitada(self):
        g = factory.new_game("t", 3)
        for i in range(300):
            factory.create_character(g, 6 + i % 60)
        engine.advance_months(g, 12)
        self.assertGreater(len(g.friendships), 30)
        for (a, b), (y, m) in g.friendships.items():
            ca, cb = g.characters[a], g.characters[b]
            ia, ib = ca.age_at(y, m), cb.age_at(y, m)
            limite = 3 if min(ia, ib) < 12 else 6 if min(ia, ib) < 18 else 12
            self.assertLessEqual(abs(ia - ib), limite + 1)  # +1: idade muda entre o evento e a conferência

    def test_afinidade_pesa_na_escolha(self):
        g = factory.new_game("t", 4)
        grupos = {}
        for tipo, val in (("A", 10), ("B", 90)):
            grupos[tipo] = [factory.create_character(g, 25) for _ in range(60)]
            for c in grupos[tipo]:
                c.personality.update(abertura=val, amabilidade=val, extroversao=val)
        engine.advance_months(g, 12 * 3)
        ids = {c.id: t for t, cs in grupos.items() for c in cs}
        mesmo = sum(1 for a, b in g.friendships if ids[a] == ids[b])
        self.assertGreater(mesmo / len(g.friendships), 0.75)

    def test_extrovertidos_fazem_mais_amigos(self):
        g = factory.new_game("t", 5)
        ext = [factory.create_character(g, 25) for _ in range(80)]
        intro = [factory.create_character(g, 25) for _ in range(80)]
        for c in ext:
            c.personality["extroversao"] = 95
        for c in intro:
            c.personality["extroversao"] = 5
        for c in ext + intro:
            c.personality.update(abertura=50, amabilidade=50)
        engine.advance_months(g, 12 * 2)
        n = lambda cs: sum(len(g.friend_ids(c.id)) for c in cs) / len(cs)
        self.assertGreater(n(ext), 1.4 * n(intro))

    def test_luto_de_amigo(self):
        g = factory.new_game("t", 6)
        a, b, c = (factory.create_character(g, 30) for _ in range(3))
        g.add_friendship(a.id, b.id)
        engine._die(g, a, 30)
        self.assertEqual(len(g.events_for(b.id, "falecimento_amigo")), 1)
        self.assertEqual(len(g.events_for(c.id, "falecimento_amigo")), 0)
        self.assertNotIn(a.id, engine.social_circle(g, b))

    def test_circulo_e_amigos_de_amigos(self):
        g = factory.new_game("t", 7)
        a, b, c, d = (factory.create_character(g, 30) for _ in range(4))
        g.add_friendship(a.id, b.id)
        g.add_friendship(b.id, c.id)
        self.assertEqual(engine.social_circle(g, a), {b.id, c.id})
        self.assertNotIn(d.id, engine.social_circle(g, a))

    def test_casamento_vem_do_circulo_na_maioria(self):
        g = factory.new_game("t", 8)
        self._pop(g, 240)
        # rastreia o círculo no momento de cada união
        dentro = fora = 0
        for _ in range(12 * 10):
            antes = {c.id: engine.has_active_spouse(g, c) for c in g.characters.values()}
            circ = {c.id: engine.social_circle(g, c) for c in g.characters.values() if c.alive}
            engine.advance_months(g, 1)
            for c in g.characters.values():
                if c.alive and not antes.get(c.id, True) and engine.has_active_spouse(g, c) and c.id < c.spouse_id:
                    # círculo do início do mês (amizades do próprio mês só ampliam)
                    if c.spouse_id in circ.get(c.id, set()) or g.are_friends(c.id, c.spouse_id):
                        dentro += 1
                    else:
                        fora += 1
        self.assertGreater(dentro + fora, 20)
        self.assertGreater(dentro / (dentro + fora), 0.6)

    def test_casamentos_continuam_numa_taxa_razoavel_com_circulo(self):
        g = factory.new_game("t", 9)
        pop = [factory.create_character(g, 20 + i % 10, "FM"[i % 2]) for i in range(300)]
        engine.advance_months(g, 12 * 10)
        casados = sum(1 for c in pop if g.events_for(c.id, "casamento"))
        self.assertTrue(0.25 <= casados / len(pop) <= 0.80, casados / len(pop))

    def test_interruptor_desliga_amizades(self):
        antigo = engine.CIRCULO_SOCIAL
        engine.CIRCULO_SOCIAL = False
        try:
            g = factory.new_game("t", 10)
            self._pop(g, 60)
            engine.advance_months(g, 36)
            self.assertEqual(len(g.friendships), 0)
            self.assertEqual(g.events_for(None, "amizade"), [])
        finally:
            engine.CIRCULO_SOCIAL = antigo

    def test_persistencia_e_continuacao_identica_com_amizades(self):
        g = factory.new_game("t", 11)
        self._pop(g, 80)
        engine.advance_months(g, 36)
        self.assertGreater(len(g.friendships), 10)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.db")
            persistence.save_game(g, path)
            g2 = persistence.load_game(path)
            self.assertEqual(snapshot(g), snapshot(g2))
            self.assertEqual(g.friend_ids(1), g2.friend_ids(1))
            engine.advance_months(g, 24)
            engine.advance_months(g2, 24)
            self.assertEqual(snapshot(g), snapshot(g2))

    def test_migracao_v3_sem_tabela_de_amizades(self):
        g = factory.new_game("t", 12)
        self._pop(g, 30)
        engine.advance_months(g, 12)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "v3.db")
            persistence.save_game(g, path)
            con = sqlite3.connect(path)
            con.execute("DROP TABLE friendships")
            con.execute("UPDATE meta SET value='3' WHERE key='schema_version'")
            con.commit()
            con.close()
            g2 = persistence.load_game(path)
            self.assertEqual(len(g2.friendships), 0)
            persistence.save_game(g2, path)
            con = sqlite3.connect(path)
            self.assertEqual(con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],
                             str(persistence.SCHEMA_VERSION))
            con.close()


class TestEducacao(unittest.TestCase):
    def _coorte(self, g, n=400, idade=6):
        cs = [factory.create_character(g, idade) for _ in range(n)]
        for c in cs:
            c.health = 100
        return cs

    def test_escolaridade_inicial_por_idade(self):
        g = factory.new_game("t", 1)
        bebe, c6, c10, c17 = (factory.create_character(g, a) for a in (0, 6, 10, 17))
        self.assertEqual((bebe.schooling_years, bebe.in_school), (0, False))
        self.assertEqual((c6.schooling_years, c6.in_school), (0, True))
        self.assertEqual((c10.schooling_years, c10.in_school), (4, True))
        self.assertEqual((c17.schooling_years, c17.in_school), (11, True))
        for _ in range(200):
            a = factory.create_character(g, 40)
            self.assertIn(a.schooling_years, (5, 9, 12))
            self.assertFalse(a.in_school)

    def test_adultos_mais_capazes_tem_mais_escolaridade(self):
        g = factory.new_game("t", 2)
        pop = [factory.create_character(g, 40) for _ in range(500)]
        alto = [c.schooling_years for c in pop if sum(c.cognition.values()) / 8 > 55]
        baixo = [c.schooling_years for c in pop if sum(c.cognition.values()) / 8 < 45]
        self.assertGreater(sum(alto) / len(alto), sum(baixo) / len(baixo) + 1)

    def test_matricula_aos_6_anos_em_fevereiro(self):
        g = factory.new_game("t", 3, month=1)
        n = [factory.create_character(g, 5) for _ in range(300)]
        engine.advance_months(g, 1)  # fevereiro: ninguém com 5 anos entra
        self.assertFalse(any(c.in_school or c.dropped_out for c in n if c.age_at(g.year, g.month) < 6))
        engine.advance_months(g, 12)  # fevereiro seguinte: todos já têm 6 anos
        vivos = [c for c in n if c.alive]
        self.assertTrue(all(c.age_at(g.year, g.month) >= 6 for c in vivos))
        matr = sum(c.in_school for c in vivos) / len(vivos)
        self.assertTrue(0.95 <= matr <= 1.0, matr)
        for c in vivos:
            self.assertTrue(c.in_school or c.dropped_out)
            if c.in_school:  # quem fez 6 anos em fevereiro de 2026 já concluiu 1 ano
                self.assertIn(c.schooling_years, (0, 1))

    def test_nunca_na_escola_antes_dos_6_nem_apos_concluir(self):
        g = factory.new_game("t", 5)
        for _ in range(60):
            factory.create_family(g, None, 4)
        for _ in range(12 * 20):
            engine.advance_months(g, 1)
            for c in g.characters.values():
                if c.in_school:
                    self.assertGreaterEqual(c.age_at(g.year, g.month), engine.IDADE_ESCOLAR_MIN)
                    self.assertTrue(c.alive and c.schooling_years < 12)
                self.assertLessEqual(c.schooling_years, 12)

    def test_taxas_de_conclusao_na_faixa(self):
        g = factory.new_game("t", 6)
        cs = self._coorte(g, 500)
        engine.advance_months(g, 12 * 13)
        vivos = [c for c in cs if c.alive]
        f9 = sum(c.schooling_years >= 9 for c in vivos) / len(vivos)
        f12 = sum(c.schooling_years >= 12 for c in vivos) / len(vivos)
        self.assertTrue(0.8 <= f9 <= 0.98, f9)
        self.assertTrue(0.55 <= f12 <= 0.85, f12)
        ap = len([e for e in g.biography if e.text.startswith("Foi aprovado")])
        rp = len([e for e in g.biography if e.text.startswith("Reprovou")])
        self.assertTrue(0.02 <= rp / (ap + rp) <= 0.15)

    def test_cognicao_e_conscienciosidade_melhoram_o_desempenho(self):
        g = factory.new_game("t", 7)
        a, b = factory.create_character(g, 12), factory.create_character(g, 12)
        for c, v in ((a, 90), (b, 10)):
            c.health = 80
            c.personality["conscienciosidade"] = v
            c.cognition_potential = {k: v for k in c.cognition_potential}
            c.cognition = {k: int(v * factory.cognition_development(12)) for k in c.cognition}
        sa = sum(engine.school_performance(g, a, 12) for _ in range(200)) / 200
        sb = sum(engine.school_performance(g, b, 12) for _ in range(200)) / 200
        self.assertGreater(sa, sb + 30)

    def test_reprovacao_nao_avanca_serie(self):
        g = factory.new_game("t", 8, month=11)
        c = factory.create_character(g, 10)
        c.personality["conscienciosidade"] = 1
        c.cognition = {k: 1 for k in c.cognition}
        c.health = 0
        antes = c.schooling_years
        engine.advance_months(g, 1)  # dezembro
        self.assertEqual(c.schooling_years, antes)
        self.assertTrue(g.events_for(c.id, "escola"))
        self.assertTrue(any(e.text.startswith("Reprovou") for e in g.events_for(c.id, "escola")))

    def test_aprovacao_avanca_e_conclusao_do_medio_encerra(self):
        g = factory.new_game("t", 9, month=11)
        c = factory.create_character(g, 17)
        c.personality["conscienciosidade"] = 99
        c.cognition = {k: 99 for k in c.cognition}
        c.cognition_potential = dict(c.cognition)
        c.health = 100
        c.schooling_years = 11
        engine.advance_months(g, 1)
        self.assertEqual(c.schooling_years, 12)
        self.assertFalse(c.in_school)
        self.assertTrue(any("Concluiu o ensino médio" in e.text for e in g.events_for(c.id, "escola")))

    def test_baixo_desempenho_e_reprovacao_aumentam_abandono(self):
        self.assertGreater(engine.dropout_probability(10, 20, False), 2 * engine.dropout_probability(10, 80, False))
        self.assertGreater(engine.dropout_probability(5, 60, True), 2 * engine.dropout_probability(5, 60, False))
        self.assertGreater(engine.dropout_probability(10, 60, False), engine.dropout_probability(5, 60, False))

    def test_colegas_viram_amigos_mais_do_que_nao_colegas(self):
        ee = ff = 0
        for seed in range(10, 16):  # agrega sementes: um único sorteio é ruidoso
            g = factory.new_game("t", seed)
            esc = [factory.create_character(g, 12) for _ in range(80)]
            fora = [factory.create_character(g, 12) for _ in range(80)]
            for c in fora:
                c.in_school = False
                c.dropped_out = True
            for c in esc + fora:
                c.personality.update(abertura=50, amabilidade=50, extroversao=50)
            with mock.patch.object(engine, "FIM_AMIZADES", False):  # mede só a formação das amizades
                engine.advance_months(g, 6)
            ids_e = {c.id for c in esc}
            ee += sum(1 for a, b in g.friendships if a in ids_e and b in ids_e)
            ff += sum(1 for a, b in g.friendships if a not in ids_e and b not in ids_e)
        self.assertGreater(ee, 1.5 * ff, (ee, ff))  # medido ≈1,8 com fator 4; ≈1,07 sem fator

    def test_rotulos_e_interruptor(self):
        g = factory.new_game("t", 11)
        c = factory.create_character(g, 8)
        self.assertEqual(engine.grade_label(0), "1º ano do fundamental")
        self.assertEqual(engine.grade_label(9), "1º ano do ensino médio")
        self.assertIn("cursando", engine.education_label(c))
        c.in_school, c.schooling_years = False, 12
        self.assertEqual(engine.education_label(c), "ensino médio completo")
        antigo = engine.EDUCACAO
        engine.EDUCACAO = False
        try:
            g2 = factory.new_game("t", 12)
            k = factory.create_character(g2, 6)
            engine.advance_months(g2, 36)
            self.assertEqual(g2.events_for(k.id, "escola"), [])
        finally:
            engine.EDUCACAO = antigo

    def test_persistencia_e_continuacao_identica_com_escola(self):
        g = factory.new_game("t", 13)
        for _ in range(10):
            factory.create_family(g, None, 4)
        engine.advance_months(g, 12 * 4)
        self.assertTrue(any(c.school_performance is not None for c in g.characters.values()))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.db")
            persistence.save_game(g, path)
            g2 = persistence.load_game(path)
            self.assertEqual(snapshot(g), snapshot(g2))
            engine.advance_months(g, 24)
            engine.advance_months(g2, 24)
            self.assertEqual(snapshot(g), snapshot(g2))

    def test_migracao_v4_infere_escolaridade(self):
        g = factory.new_game("t", 14)
        for _ in range(5):
            factory.create_family(g, None, 3)
        engine.advance_months(g, 12)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "v4.db")
            persistence.save_game(g, path)
            con = sqlite3.connect(path)
            for col in ("schooling_years", "in_school", "dropped_out", "school_performance"):
                con.execute(f"ALTER TABLE characters DROP COLUMN {col}")
            con.execute("UPDATE meta SET value='4' WHERE key='schema_version'")
            con.commit()
            con.close()
            g2 = persistence.load_game(path)
            for c in g2.characters.values():
                a = c.age_at(g2.year, g2.month)
                if 6 <= a < 18 and c.alive:
                    self.assertEqual((c.schooling_years, c.in_school), (a - 6, True))
                if a < 6:
                    self.assertFalse(c.in_school)
            persistence.save_game(g2, path)
            con = sqlite3.connect(path)
            self.assertEqual(con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],
                             str(persistence.SCHEMA_VERSION))
            con.close()
            persistence.load_game(path)


class TestEnsinoSuperior(unittest.TestCase):
    def setUp(self):
        self._edu, self._sup = engine.EDUCACAO, engine.ENSINO_SUPERIOR
        self.addCleanup(setattr, engine, "EDUCACAO", self._edu)
        self.addCleanup(setattr, engine, "ENSINO_SUPERIOR", self._sup)
        engine.EDUCACAO = engine.ENSINO_SUPERIOR = True

    def _adulto(self, g, idade=18, anos=12, consc=90, cog=90):
        c = factory.create_character(g, idade)
        c.health, c.schooling_years, c.in_school = 100, anos, False
        c.personality["conscienciosidade"] = consc
        for k in c.cognition:
            c.cognition[k] = c.cognition_potential[k] = cog
        return c

    def test_ingresso_e_formatura(self):
        g = factory.new_game("t", 5)
        cs = [self._adulto(g) for _ in range(200)]
        engine.advance_months(g, 12 * 8)
        v = [c for c in cs if c.alive]
        self.assertTrue(any(c.graduated for c in v))
        for c in v:
            if c.graduated:
                self.assertEqual(c.higher_years, engine.ANOS_SUPERIOR)
                self.assertFalse(c.in_college)
                self.assertEqual(engine.education_label(c), "ensino superior completo")
        evs = [e.text for e in g.biography if e.category == "escola"]
        self.assertTrue(any("Ingressou no ensino superior" in t for t in evs))
        self.assertTrue(any("Formou-se" in t for t in evs))

    def test_aptidao_aumenta_ingresso(self):
        g = factory.new_game("t", 6)
        alto, baixo = self._adulto(g, consc=95, cog=95), self._adulto(g, consc=35, cog=35)
        self.assertGreater(engine.college_entry_chance(alto, 18), 3 * engine.college_entry_chance(baixo, 18))

    def test_ingresso_cai_com_a_idade(self):
        g = factory.new_game("t", 6)
        c = self._adulto(g)
        self.assertGreater(engine.college_entry_chance(c, 18), engine.college_entry_chance(c, 22))
        self.assertGreater(engine.college_entry_chance(c, 22), engine.college_entry_chance(c, 30))
        self.assertEqual(engine.college_entry_chance(c, 40), 0.0)

    def test_sem_medio_nao_ingressa(self):
        g = factory.new_game("t", 7)
        cs = [self._adulto(g, anos=9) for _ in range(100)]
        engine.advance_months(g, 12)
        self.assertFalse(any(c.in_college or c.higher_years for c in cs))

    def test_retorno_aos_estudos(self):
        g = factory.new_game("t", 8)
        cs = [self._adulto(g, idade=30, anos=9) for _ in range(300)]
        engine.advance_months(g, 12 * 6)
        v = [c for c in cs if c.alive]
        voltaram = [c for c in v if c.returned_to_school]
        self.assertTrue(voltaram)
        self.assertTrue(any(c.schooling_years > 9 for c in voltaram))
        self.assertTrue(any("Voltou a estudar" in e.text for e in g.biography))

    def test_morte_encerra_curso(self):
        g = factory.new_game("t", 9)
        c = self._adulto(g)
        c.in_college = True
        engine._die(g, c, 20)
        self.assertFalse(c.in_college)

    def test_interruptor_desligado(self):
        engine.ENSINO_SUPERIOR = False
        g = factory.new_game("t", 10)
        cs = [self._adulto(g) for _ in range(100)] + [self._adulto(g, idade=30, anos=9) for _ in range(100)]
        engine.advance_months(g, 12 * 4)
        self.assertFalse(any(c.in_college or c.higher_years or c.returned_to_school for c in cs))

    def test_save_v6_ida_e_volta(self):
        g = factory.new_game("t", 11)
        a = self._adulto(g)
        a.in_college, a.higher_years, a.returned_to_school = True, 2, True
        b = self._adulto(g)
        b.graduated, b.higher_years = True, 4
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.db")
            persistence.save_game(g, p)
            h = persistence.load_game(p)
        ha, hb = h.characters[a.id], h.characters[b.id]
        self.assertEqual((ha.in_college, ha.higher_years, ha.returned_to_school), (True, 2, True))
        self.assertEqual((hb.graduated, hb.higher_years), (True, 4))

    def test_carregar_e_continuar_igual(self):
        def montar():
            g = factory.new_game("t", 12)
            for _ in range(60):
                self._adulto(g, idade=18, consc=70, cog=70)
            return g
        g1 = montar()
        engine.advance_months(g1, 36)
        g2 = montar()
        engine.advance_months(g2, 18)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.db")
            persistence.save_game(g2, p)
            g2 = persistence.load_game(p)
        engine.advance_months(g2, 18)
        est = lambda g: [(c.id, c.higher_years, c.in_college, c.graduated, c.schooling_years) for c in g.characters.values()]
        self.assertEqual(est(g1), est(g2))


class TestTrabalho(unittest.TestCase):
    """v0.6.0: mercado de trabalho (primeiro emprego, ocupação por formação e aptidão, desemprego,
    mudança de ocupação, aposentadoria). Educação e círculo social desligados, salvo onde indicado."""

    def setUp(self):
        self._o = (engine.TRABALHO, engine.EDUCACAO, engine.CIRCULO_SOCIAL)
        self.addCleanup(lambda: (setattr(engine, "TRABALHO", self._o[0]), setattr(engine, "EDUCACAO", self._o[1]),
                                 setattr(engine, "CIRCULO_SOCIAL", self._o[2])))
        engine.TRABALHO, engine.EDUCACAO, engine.CIRCULO_SOCIAL = True, False, False
        # Estas regras (0.6.0) são medidas sem o ciclo econômico (0.9.0), que é fator de confusão aqui: o ciclo
        # alonga o desemprego e comprime a razão de perdas entre conscienciosidade baixa e alta (ainda >1).
        self._ciclo = cycle.ATIVO
        self.addCleanup(setattr, cycle, "ATIVO", self._ciclo)
        cycle.ATIVO = False

    def _pessoa(self, g, idade=28, anos=12, graduado=False, consc=60, cog=60, saude=100, empregar=None):
        c = factory.create_character(g, idade)
        c.health, c.schooling_years, c.in_school = saude, anos, False
        c.graduated, c.higher_years = graduado, 4 if graduado else 0
        c.personality["conscienciosidade"] = consc
        for k in c.cognition:
            c.cognition[k] = c.cognition_potential[k] = cog
        c.occupation = c.job_start = c.seeking_since = None
        c.retired, c.jobs_held = False, 0
        if empregar:
            c.occupation, c.job_start, c.jobs_held = empregar, g.year * 12 + g.month - 24, 1
        return c

    def test_estudante_nao_procura_emprego(self):
        engine.EDUCACAO = True
        g = factory.new_game("t", 3)
        cs = [factory.create_character(g, 16) for _ in range(30)]
        for c in cs:
            c.occupation = c.job_start = c.seeking_since = None
            c.retired, c.jobs_held = False, 0
        for _ in range(23):
            engine.advance_months(g, 1)
            for c in cs:
                if c.alive and (c.in_school or c.in_college):
                    self.assertIsNone(c.occupation)
                    self.assertIsNone(c.seeking_since)
        # quem terminou o médio e saiu da escola entra no mercado
        self.assertTrue(any(c.alive and not c.in_school and (c.occupation or c.seeking_since) for c in cs))

    def test_primeiro_emprego(self):
        g = factory.new_game("t", 4)
        cs = [self._pessoa(g, 20) for _ in range(80)]
        engine.advance_months(g, 36)
        vivos = [c for c in cs if c.alive]
        empregados = [c for c in vivos if work.is_employed(c)]
        self.assertGreater(len(empregados), 0.7 * len(vivos))
        for c in vivos:
            evs = [e.text for e in g.events_for(c.id, "trabalho")]
            self.assertEqual(sum("primeiro emprego" in t for t in evs), 1 if c.jobs_held else 0)
            if c.jobs_held:  # procurou antes de conseguir
                self.assertIn("Passou a procurar trabalho.", evs[0])
        for c in empregados:
            self.assertIsNone(c.seeking_since)
            self.assertIsNotNone(c.job_start)

    def test_ocupacao_respeita_formacao_e_aptidao(self):
        g = factory.new_game("t", 5)
        cs = []
        for anos, grad in ((5, False), (9, False), (12, False), (12, True)):
            for cog in (30, 60, 90):
                cs += [self._pessoa(g, 30, anos, grad, cog=cog) for _ in range(25)]
        engine.advance_months(g, 36)
        emp = [c for c in cs if work.is_employed(c)]
        self.assertGreater(len(emp), 100)
        for c in emp:
            o = work._POR_CHAVE[c.occupation]
            self.assertLessEqual(o[3], work.education_level(c))
            self.assertGreaterEqual(work.work_aptitude(c), o[4])

    def test_formacao_importa_mas_nao_garante(self):
        g = factory.new_game("t", 6)
        grupos = {}
        for nivel, (anos, grad) in enumerate(((5, False), (9, False), (12, False), (12, True))):
            grupos[nivel] = [self._pessoa(g, 28, anos, grad) for _ in range(300)]
        engine.advance_months(g, 60)
        medias = []
        for nivel, cs in grupos.items():
            niv = [work.occupation_level(c.occupation) for c in cs if work.is_employed(c)]
            medias.append(sum(niv) / len(niv))
        self.assertLess(medias[0], medias[1])
        self.assertLess(medias[1], medias[2])
        self.assertLess(medias[2], medias[3])
        grad = [c for c in grupos[3] if work.is_employed(c)]
        abaixo = sum(work.occupation_level(c.occupation) < 3 for c in grad) / len(grad)
        self.assertTrue(0.10 < abaixo < 0.75, abaixo)  # formação não garante a ocupação de nível superior
        self.assertTrue(any(work.is_seeking(c) for c in grupos[3]))  # nem garante emprego

    def test_taxas_de_emprego_e_desemprego(self):
        emp = desemp = total = 0
        for seed in (1, 2, 3):
            g = factory.new_game("t", seed)
            cs = [factory.create_character(g, 30 + i % 10) for i in range(200)]
            engine.advance_months(g, 12 * 8)
            ad = [c for c in cs if c.alive and 25 <= c.age_at(g.year, g.month) <= 54]
            total += len(ad)
            emp += sum(work.is_employed(c) for c in ad)
            desemp += sum(work.is_seeking(c) for c in ad)
        self.assertTrue(0.65 < emp / total < 0.95, emp / total)       # medido ≈0,85–0,9
        self.assertTrue(0.03 < desemp / (emp + desemp) < 0.20, desemp / (emp + desemp))  # medido ≈0,06–0,17

    def test_aptidao_alta_contrata_mais_rapido(self):
        g = factory.new_game("t", 7)
        alta = [self._pessoa(g, 25, cog=90, consc=90) for _ in range(300)]
        baixa = [self._pessoa(g, 25, cog=30, consc=30) for _ in range(300)]
        engine.advance_months(g, 6)
        a = sum(work.is_employed(c) for c in alta if c.alive) / sum(c.alive for c in alta)
        b = sum(work.is_employed(c) for c in baixa if c.alive) / sum(c.alive for c in baixa)
        self.assertGreater(a, 1.3 * b)

    def test_saude_baixa_nao_e_contratada(self):
        g = factory.new_game("t", 8)
        cs = [self._pessoa(g, 25, saude=10) for _ in range(100)]
        engine.advance_months(g, 6)
        self.assertTrue(all(c.jobs_held == 0 for c in cs))
        self.assertEqual(work.hire_monthly(cs[0], 25), 0.0)

    def test_aposentadoria(self):
        g = factory.new_game("t", 9)
        cs = [self._pessoa(g, 55, empregar="atendente_comercio") for _ in range(150)]
        velhos = [factory.create_character(g, 80) for _ in range(50)]
        self.assertTrue(all(c.retired for c in velhos))  # inicial: ≥75 anos todos aposentados
        aposentados = {}
        for _ in range(25):
            engine.advance_months(g, 12)
            for c in cs:
                if not c.alive:
                    continue
                if c.retired:
                    antes = aposentados.setdefault(c.id, (c.occupation, c.jobs_held))
                    self.assertEqual((c.occupation, c.jobs_held), antes)  # aposentado nunca volta a trabalhar
                    self.assertFalse(work.is_employed(c))
                self.assertTrue(not c.retired or c.age_at(g.year, g.month) >= 60)  # ninguém antes dos 60
        self.assertTrue(aposentados)
        for c in cs:
            if c.alive and c.age_at(g.year, g.month) >= 75:
                self.assertTrue(c.retired)

    def test_separacao_depende_da_conscienciosidade(self):
        g = factory.new_game("t", 10)
        alta = [self._pessoa(g, 30, consc=95, empregar="atendente_comercio") for _ in range(300)]
        baixa = [self._pessoa(g, 30, consc=5, empregar="atendente_comercio") for _ in range(300)]
        agora = g.year * 12 + g.month   # efeito direto, antes de o tempo diferenciar vínculos e saúde
        alta[0].informal = baixa[0].informal = False   # isola o efeito da conscienciosidade
        self.assertGreater(work.separation_monthly(baixa[0], agora) / work.separation_monthly(alta[0], agora), 1.6)
        engine.advance_months(g, 24)
        perdas = lambda cs: sum(1 for c in cs for e in g.events_for(c.id, "trabalho") if e.text.startswith("Perdeu o emprego"))
        # Razão teórica por mês ≈1,74 (testada direto acima); a observada ≈1,2–1,4 (quem perde o emprego sai do risco)
        # oscila com o fluxo do RNG, então só exigimos o sinal estatístico.
        self.assertGreater(perdas(baixa), 1.1 * perdas(alta))
        self.assertGreater(perdas(alta), 0)
        # vínculo recém-iniciado é mais instável que o longo
        c = self._pessoa(g, 30, empregar="atendente_comercio")
        c.job_start = g.year * 12 + g.month - 3
        longo = self._pessoa(g, 30, empregar="atendente_comercio")
        longo.job_start = g.year * 12 + g.month - 100
        self.assertGreater(work.separation_monthly(c, g.year * 12 + g.month),
                           work.separation_monthly(longo, g.year * 12 + g.month))

    def test_mudanca_para_ocupacao_melhor_apos_formar(self):
        g = factory.new_game("t", 11)
        formados = [self._pessoa(g, 30, 12, True, cog=85, consc=85, empregar="servicos_gerais") for _ in range(200)]
        sem = [self._pessoa(g, 30, 5, False, empregar="servicos_gerais") for _ in range(100)]
        engine.advance_months(g, 36)
        trocas = {c.id: [e.text for e in g.events_for(c.id, "trabalho") if e.text.startswith("Mudou de ocupação")]
                  for c in formados}
        mudaram = [c for c in formados if trocas[c.id]]
        self.assertGreater(len(mudaram), 0.10 * len(formados))  # medido ≈17% em 36 meses
        for c in mudaram:  # a troca é sempre para nível maior que o da ocupação anterior (nível 0)
            for t in trocas[c.id]:
                self.assertNotIn("→ Auxiliar de serviços gerais", t)
                self.assertNotIn("→ Trabalhador rural", t)
        txt = [e.text for c in sem for e in g.events_for(c.id, "trabalho")]
        self.assertFalse(any("Mudou de ocupação" in t for t in txt))  # sem formação maior, não há troca

    def test_interruptor_desliga_trabalho(self):
        engine.TRABALHO = False
        g = factory.new_game("t", 12)
        cs = [self._pessoa(g, 30) for _ in range(40)]
        engine.advance_months(g, 24)
        self.assertEqual([e for e in g.biography if e.category == "trabalho"], [])
        self.assertTrue(all(c.occupation is None and c.seeking_since is None for c in cs))

    def test_situacao_inicial_deterministica_sem_rng(self):
        g = factory.new_game("t", 13)
        c = factory.create_character(g, 40)
        estado = lambda: (c.occupation, c.job_start, c.seeking_since, c.retired, c.jobs_held)
        a = estado()
        c.occupation = c.job_start = c.seeking_since = None
        c.retired, c.jobs_held = False, 0
        rng_antes = g.rng.getstate()
        work.default_work(g, c)
        self.assertEqual(g.rng.getstate(), rng_antes)  # não consome game.rng
        self.assertEqual(estado(), a)
        self.assertTrue(c.occupation is not None or c.seeking_since is not None)
        for idade in (0, 10, 15):  # menores de 16 anos não têm situação de trabalho
            m = factory.create_character(g, idade)
            self.assertEqual((m.occupation, m.seeking_since, m.retired), (None, None, False))
            self.assertIsNone(work.work_label(m, g.year, g.month))

    def test_rotulos_da_ficha(self):
        g = factory.new_game("t", 14)
        c = self._pessoa(g, 30, empregar="professor")
        self.assertIn("empregado(a): Professor", work.work_label(c, g.year, g.month))
        c.sex = "F"
        self.assertIn("Professora", work.work_label(c, g.year, g.month))
        c.occupation, c.seeking_since = None, g.year * 12 + g.month - 5
        self.assertIn("desempregado(a)", work.work_label(c, g.year, g.month))
        c.seeking_since, c.occupation, c.retired = None, "professor", True
        self.assertIn("aposentado(a) (última ocupação: Professora)", work.work_label(c, g.year, g.month))

    def test_save_v7_ida_e_volta(self):
        g = factory.new_game("t", 15)
        a = self._pessoa(g, 30, empregar="engenheiro")
        b = self._pessoa(g, 30)
        b.seeking_since = g.year * 12 + g.month - 4
        r = self._pessoa(g, 70)
        r.occupation, r.retired, r.jobs_held = "professor", True, 2
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.db")
            persistence.save_game(g, p)
            h = persistence.load_game(p)
        for c in (a, b, r):
            h_ = h.characters[c.id]
            self.assertEqual((h_.occupation, h_.job_start, h_.seeking_since, h_.retired, h_.jobs_held),
                             (c.occupation, c.job_start, c.seeking_since, c.retired, c.jobs_held))

    def test_migracao_v6_infere_trabalho(self):
        g = factory.new_game("t", 16)
        for i in range(30):
            factory.create_character(g, 20 + 2 * i)
        engine.advance_months(g, 12)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "v6.db")
            persistence.save_game(g, p)
            con = sqlite3.connect(p)
            for col in ("occupation", "job_start", "seeking_since", "retired", "jobs_held"):
                con.execute(f"ALTER TABLE characters DROP COLUMN {col}")
            con.execute("UPDATE meta SET value='6' WHERE key='schema_version'")
            con.commit()
            con.close()
            h = persistence.load_game(p)
            for c in h.characters.values():
                if c.alive and c.age_at(h.year, h.month) >= 16 and not (c.in_school or c.in_college):
                    self.assertTrue(c.occupation or c.seeking_since or c.retired)
            h2 = persistence.load_game(p)
            self.assertEqual([(c.id, c.occupation, c.job_start, c.seeking_since, c.retired) for c in h.characters.values()],
                             [(c.id, c.occupation, c.job_start, c.seeking_since, c.retired) for c in h2.characters.values()])
            persistence.save_game(h, p)
            con = sqlite3.connect(p)
            self.assertEqual(con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],
                             str(persistence.SCHEMA_VERSION))
            con.close()
            persistence.load_game(p)

    def test_carregar_e_continuar_igual(self):
        def montar():
            g = factory.new_game("t", 17)
            for i in range(60):
                factory.create_character(g, 16 + i)
            return g
        g1 = montar()
        engine.advance_months(g1, 36)
        g2 = montar()
        engine.advance_months(g2, 18)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.db")
            persistence.save_game(g2, p)
            g2 = persistence.load_game(p)
        engine.advance_months(g2, 18)
        self.assertEqual(snapshot(g1), snapshot(g2))
        self.assertTrue(any(e.category == "trabalho" for e in g1.biography))


class TestEconomia(unittest.TestCase):
    def setUp(self):
        self._o = (engine.TRABALHO, engine.EDUCACAO, engine.CIRCULO_SOCIAL, engine.ECONOMIA, engine.DIVORCIO_BASE)
        self.addCleanup(lambda: (setattr(engine, "TRABALHO", self._o[0]), setattr(engine, "EDUCACAO", self._o[1]),
                                 setattr(engine, "CIRCULO_SOCIAL", self._o[2]), setattr(engine, "ECONOMIA", self._o[3]),
                                 setattr(engine, "DIVORCIO_BASE", self._o[4])))
        engine.TRABALHO, engine.EDUCACAO, engine.CIRCULO_SOCIAL, engine.ECONOMIA = True, False, False, True

    def _p(self, g, idade=30, occ=None, rank=0, exp=0, informal=False, consc=50, sex=None, **kw):
        c = factory.create_character(g, idade, sex=sex)
        c.occupation, c.job_start, c.seeking_since, c.retired = occ, (g.year * 12 + g.month - 36) if occ else None, None, False
        c.rank, c.rank_since, c.informal, c.workplace, c.experience = rank, g.year * 12 + g.month - 40, informal, 0 if occ else None, exp
        c.income = c.wealth = 0.0
        c.health, c.in_school, c.in_college = 100, False, False
        c.personality["conscienciosidade"] = consc
        for k, v in kw.items():
            setattr(c, k, v)
        return c

    def test_salario_por_ocupacao_nivel_experiencia_formalidade(self):
        g = factory.new_game("t", 1)
        base = self._p(g, occ="servicos_gerais")
        self.assertEqual(economy.monthly_salary(base), economy.SALARIO_MINIMO)
        self.assertEqual(economy.monthly_salary(self._p(g)), 0.0)
        self.assertGreater(economy.monthly_salary(self._p(g, occ="medico")), 10 * economy.monthly_salary(base))
        sal = [economy.monthly_salary(self._p(g, occ="professor", rank=r)) for r in range(4)]
        self.assertEqual(sal, sorted(sal))
        self.assertEqual(len(set(sal)), 4)
        self.assertGreater(economy.monthly_salary(self._p(g, occ="professor", exp=120)),
                           economy.monthly_salary(self._p(g, occ="professor", exp=0)))
        # experiência tem teto
        self.assertEqual(economy.monthly_salary(self._p(g, occ="professor", exp=12 * 100)),
                         economy.monthly_salary(self._p(g, occ="professor", exp=12 * 40)))
        self.assertAlmostEqual(economy.monthly_salary(self._p(g, occ="professor", informal=True)),
                               0.8 * economy.monthly_salary(self._p(g, occ="professor")), places=1)

    def test_beneficio_de_aposentadoria(self):
        g = factory.new_game("t", 1)
        f = self._p(g, 62, occ="engenheiro", rank=2, exp=300)
        self.assertAlmostEqual(economy.pension(f), 0.7 * economy.monthly_salary(f), places=1)
        self.assertLessEqual(economy.pension(self._p(g, 62, occ="medico", rank=3, exp=500)), economy.TETO_BENEFICIO)
        self.assertEqual(economy.pension(self._p(g, 62, occ="engenheiro", informal=True)), economy.SALARIO_MINIMO)
        self.assertEqual(economy.pension(self._p(g, 62)), economy.SALARIO_MINIMO)
        self.assertGreaterEqual(economy.pension(self._p(g, 62, occ="servicos_gerais")), economy.SALARIO_MINIMO)

    def test_aposentadoria_no_motor_define_renda_do_beneficio(self):
        engine.TRABALHO = True
        g = factory.new_game("t", 2)
        cs = [self._p(g, 74, occ="engenheiro", rank=2, exp=300) for _ in range(20)]
        engine.advance_months(g, 18)
        ret = [c for c in cs if c.alive and c.retired]
        self.assertTrue(ret)
        for c in ret:
            self.assertGreaterEqual(c.income, economy.SALARIO_MINIMO)
            self.assertLessEqual(c.income, economy.TETO_BENEFICIO)
            self.assertFalse(work.is_employed(c))

    def test_regras_de_promocao(self):
        g = factory.new_game("t", 1)
        now = g.year * 12 + g.month
        c = self._p(g, 35, occ="aux_administrativo", consc=70)
        for k in c.cognition:
            c.cognition[k] = 70
        self.assertGreater(work.promotion_monthly(c, now, 35), 0)
        c.rank_since = now - 10  # pouco tempo no nível
        self.assertEqual(work.promotion_monthly(c, now, 35), 0.0)
        c.rank_since = now - 40
        c.informal = True
        self.assertEqual(work.promotion_monthly(c, now, 35), 0.0)
        c.informal, c.rank = False, 3
        self.assertEqual(work.promotion_monthly(c, now, 35), 0.0)  # topo
        c.rank = 0
        self.assertEqual(work.promotion_monthly(c, now, 60), 0.0)  # idade
        self.assertEqual(work.promotion_monthly(self._p(g, 35), now, 35), 0.0)  # sem emprego
        a = work.promotion_monthly(c, now, 35)
        for k in c.cognition:
            c.cognition[k] = 30
        c.personality["conscienciosidade"] = 30
        self.assertLess(work.promotion_monthly(c, now, 35), a)  # aptidão menor, chance menor
        c.rank = 2
        c.personality["conscienciosidade"] = 70
        for k in c.cognition:
            c.cognition[k] = 70
        self.assertLess(work.promotion_monthly(c, now, 35), a)  # a última etapa é mais difícil

    def test_promocao_acontece_na_simulacao_e_registra_evento(self):
        g = factory.new_game("t", 5)
        cs = [self._p(g, 30, occ="aux_administrativo", consc=80, exp=60, rank_since=g.year * 12 + g.month - 50) for _ in range(40)]
        for c in cs:
            for k in c.cognition:
                c.cognition[k] = c.cognition_potential[k] = 80
        engine.advance_months(g, 60)
        promovidos = [c for c in cs if c.alive and c.rank > 0]
        self.assertGreater(len(promovidos), 3)
        for c in cs:
            self.assertTrue(0 <= c.rank <= 3)
            n = sum("promovido" in e.text for e in g.events_for(c.id, "trabalho"))
            self.assertGreaterEqual(n, c.rank if c.occupation is not None and c.jobs_held <= 1 else 0)
        self.assertTrue(any("novo salário: R$" in e.text for e in g.biography))

    def test_start_job_deterministico_e_sem_rng(self):
        g = factory.new_game("t", 7)
        c = self._p(g, 30)
        antes = g.rng.getstate()
        work.start_job(g, c, "engenheiro", 24330)
        a = (c.occupation, c.rank, c.informal, c.workplace, c.job_start)
        work.start_job(g, c, "engenheiro", 24330)
        self.assertEqual(a, (c.occupation, c.rank, c.informal, c.workplace, c.job_start))
        self.assertEqual(g.rng.getstate(), antes)
        self.assertIn(c.workplace, g.firms)  # v0.8.0: o local de trabalho é uma empresa real
        self.assertEqual((c.rank, c.rank_since), (0, 24330))

    def test_informalidade_cai_com_o_nivel_da_ocupacao(self):
        g = factory.new_game("t", 7)
        taxa = {}
        for chave in ("servicos_gerais", "medico"):
            n = 0
            for i in range(400):
                c = self._p(g, 30)
                work.start_job(g, c, chave, 24000 + i)
                n += c.informal
            taxa[chave] = n / 400
        self.assertGreater(taxa["servicos_gerais"], 0.3)
        self.assertLess(taxa["medico"], 0.12)

    def test_clear_job_mantem_experiencia(self):
        g = factory.new_game("t", 7)
        c = self._p(g, 30, occ="professor", rank=2, exp=90, informal=True)
        work.clear_job(c)
        self.assertEqual((c.occupation, c.job_start, c.rank, c.rank_since, c.informal, c.workplace),
                         (None, None, 0, None, False, None))
        self.assertEqual(c.experience, 90)

    def test_informal_perde_emprego_mais(self):
        g = factory.new_game("t", 1)
        now = g.year * 12 + g.month
        f, i = self._p(g, occ="servicos_gerais"), self._p(g, occ="servicos_gerais", informal=True)
        self.assertAlmostEqual(work.separation_monthly(i, now), 1.5 * work.separation_monthly(f, now))

    def _casal(self, g, filhos=2):
        r = factory.create_family(g, "Teste", filhos)
        pessoas = [g.characters[i] for i in sorted(g.characters)]
        for c in pessoas:
            c.occupation, c.job_start, c.seeking_since, c.retired = None, None, None, False
            c.income = c.wealth = 0.0
            c.informal, c.rank, c.experience = False, 0, 0
        return pessoas

    def test_domicilio_casal_divide_saldo_e_sustenta_filhos(self):
        g = factory.new_game("t", 3)
        pessoas = self._casal(g, 2)
        adultos = [c for c in pessoas if c.age_at(g.year, g.month) >= 25 and c.spouse_id]
        self.assertEqual(len(adultos), 2)
        for a in adultos:
            a.occupation, a.job_start, a.workplace = "engenheiro", g.year * 12 + g.month - 60, 1
            a.personality["conscienciosidade"] = 50
        antes = g.rng.getstate()
        hs = economy.build_households(g)
        h = next(x for x in hs if adultos[0] in x["adults"])
        self.assertEqual({a.id for a in h["adults"]}, {a.id for a in adultos})
        self.assertEqual(len(h["kids"]), 2)
        esperado = economy.CUSTO_ADULTO + economy.CUSTO_ADULTO_EXTRA + 2 * economy.CUSTO_CRIANCA
        self.assertAlmostEqual(h["cost"], esperado)
        self.assertAlmostEqual(h["cost"], 2.4 * economy.SALARIO_MINIMO)  # 0,9 + 0,6 + 2×0,45 salários mínimos
        self.assertGreater(h["cost"], economy.CUSTO_ADULTO + economy.CUSTO_ADULTO_EXTRA)
        economy.apply_month(g)
        self.assertEqual(g.rng.getstate(), antes)  # economia não usa game.rng
        w = [a.wealth for a in adultos]
        self.assertAlmostEqual(w[0], w[1], places=2)
        self.assertGreater(w[0], 0)
        for k in h["kids"]:
            self.assertEqual(k.wealth, 0.0)

    def test_deficit_reduz_patrimonio_e_divida_tem_limite(self):
        g = factory.new_game("t", 3)
        c = self._p(g, 40)  # sem emprego nem renda, solteiro
        c.spouse_id = c.mother_id = c.father_id = None
        c.wealth = 1000.0
        economy.apply_month(g)
        self.assertLess(c.wealth, 1000.0)
        for _ in range(200):
            economy.apply_month(g)
        self.assertEqual(c.wealth, -economy.DIVIDA_MAX)

    def test_poupanca_sobe_com_conscienciosidade(self):
        g = factory.new_game("t", 3)
        a = self._p(g, 40, occ="engenheiro", consc=10)
        b = self._p(g, 40, occ="engenheiro", consc=90)
        for c in (a, b):
            c.spouse_id = c.mother_id = c.father_id = None
        economy.apply_month(g)
        self.assertLess(a.wealth, b.wealth)
        self.assertGreater(a.wealth, 0)

    def test_jovem_sem_renda_e_dependente_dos_pais(self):
        g = factory.new_game("t", 3)
        pessoas = self._casal(g, 1)
        filho = next(c for c in pessoas if c.mother_id)
        filho.birth_year, filho.birth_month = g.year - 21, g.month
        filho.spouse_id = None
        hs = economy.build_households(g)
        h = next(x for x in hs if filho in x["kids"])
        self.assertEqual(len(h["adults"]), 2)
        filho.occupation, filho.income = "servicos_gerais", economy.SALARIO_MINIMO
        hs = economy.build_households(g)
        self.assertTrue(any(filho in x["adults"] for x in hs))  # com renda, é independente

    def test_orfao_menor_nao_se_endivida(self):
        g = factory.new_game("t", 3)
        pessoas = self._casal(g, 1)
        filho = next(c for c in pessoas if c.mother_id)
        for p in pessoas:
            if p is not filho and p.age_at(g.year, g.month) >= 18:
                p.alive = False
        self.assertLess(filho.age_at(g.year, g.month), 18)
        for _ in range(12):
            economy.apply_month(g)
        self.assertGreaterEqual(filho.wealth, 0.0)

    def test_auxilio_social_para_baixa_renda_com_filhos(self):
        g = factory.new_game("t", 3)
        pessoas = self._casal(g, 2)
        pais = [c for c in pessoas if c.spouse_id]
        for p in pais:
            p.occupation, p.income = "servicos_gerais", 0
        economy.apply_month(g)
        h = economy.household_of(g, pais[0])
        self.assertGreater(h["auxilio"], 0)
        for p in pais:
            p.occupation = "medico"
        economy.apply_month(g)
        self.assertEqual(economy.household_of(g, pais[0])["auxilio"], 0.0)

    def test_heranca_conjuge_e_filhos(self):
        g = factory.new_game("t", 3)
        pessoas = self._casal(g, 2)
        pais = [c for c in pessoas if c.spouse_id]
        filhos = [c for c in pessoas if c.mother_id]
        morto, viuvo = pais
        morto.wealth = 100000.0
        res = economy.inherit(g, morto)
        self.assertEqual(morto.wealth, 0.0)
        self.assertAlmostEqual(viuvo.wealth, 50000.0)
        for f in filhos:
            self.assertAlmostEqual(f.wealth, 25000.0)
        self.assertAlmostEqual(sum(v for _, v in res), 100000.0)

    def test_heranca_so_filhos_so_conjuge_sem_herdeiros_e_divida(self):
        g = factory.new_game("t", 3)
        pessoas = self._casal(g, 2)
        pais = [c for c in pessoas if c.spouse_id]
        filhos = [c for c in pessoas if c.mother_id]
        pais[1].alive = False  # cônjuge morto: só filhos herdam
        pais[0].wealth = 60000.0
        economy.inherit(g, pais[0])
        self.assertAlmostEqual(sum(f.wealth for f in filhos), 60000.0)
        solo = self._p(g, 50)
        solo.spouse_id = None
        solo.wealth = 5000.0
        self.assertEqual(economy.inherit(g, solo), [])  # sem herdeiros: Estado
        dev = self._p(g, 50)
        dev.wealth = -9000.0
        self.assertEqual(economy.inherit(g, dev), [])
        self.assertEqual(dev.wealth, 0.0)

    def test_morte_gera_evento_de_heranca(self):
        g = factory.new_game("t", 3)
        pessoas = self._casal(g, 2)
        pais = [c for c in pessoas if c.spouse_id]
        filhos = [c for c in pessoas if c.mother_id]
        pais[0].wealth = 40000.0
        engine._die(g, pais[0], 60)
        textos = [e.text for e in g.events_for(filhos[0].id, "heranca")]
        self.assertEqual(len(textos), 1)
        self.assertIn("R$ 10.000,00", textos[0])
        engine.ECONOMIA = False
        pais[1].wealth = 1000.0
        engine._die(g, pais[1], 60)
        self.assertEqual(len(g.events_for(filhos[0].id, "heranca")), 1)  # interruptor desligado: sem herança

    def test_colegas_de_trabalho_pesam_nas_amizades(self):
        g = factory.new_game("t", 3)
        a = self._p(g, 30, occ="professor")
        b = self._p(g, 30, occ="engenheiro")
        c = self._p(g, 30, occ="engenheiro")
        a.workplace, b.workplace, c.workplace = 5, 5, 6
        for x in (a, b, c):
            x.personality.update(abertura=50, amabilidade=50, extroversao=50)
        now = (g.year, g.month)
        self.assertTrue(engine._coworkers(a, b))
        self.assertFalse(engine._coworkers(a, c))
        self.assertAlmostEqual(engine.friend_weight(a, b, now), engine.FATOR_COLEGAS_TRABALHO * engine.friend_weight(a, c, now))
        b.retired = True  # aposentado deixa de ser colega
        self.assertFalse(engine._coworkers(a, b))
        engine.TRABALHO = False
        b.retired = False
        self.assertEqual(engine.friend_weight(a, b, now), engine.friend_weight(a, c, now))

    def test_gini_e_formatacao(self):
        self.assertEqual(economy.gini([5, 5, 5, 5]), 0.0)
        self.assertAlmostEqual(economy.gini([0, 0, 0, 10]), 0.75)
        self.assertEqual(economy.gini([]), 0.0)
        self.assertEqual(economy.fmt_brl(1234567.891), "R$ 1.234.567,89")
        self.assertEqual(economy.fmt_brl(-50), "-R$ 50,00")

    def test_situacao_inicial_deterministica_sem_rng(self):
        g1, g2 = factory.new_game("a", 11), factory.new_game("b", 11)
        c1 = factory.create_character(g1, 45)
        c2 = factory.create_character(g2, 45)
        self.assertEqual((c1.income, c1.wealth, c1.rank, c1.informal, c1.experience),
                         (c2.income, c2.wealth, c2.rank, c2.informal, c2.experience))
        self.assertEqual(factory.create_character(g1, 10).wealth, 0.0)
        r = factory.create_character(g1, 80)
        self.assertGreaterEqual(r.income, economy.SALARIO_MINIMO)

    def test_calibracao_geral(self):
        inf = tot = 0   # informalidade pooled: ~30 empregados por semente é pouco (0 informais por acaso em 1 semente)
        for seed in (1, 2):
            g = factory.new_game("c", seed)
            for _ in range(20):
                factory.create_family(g, None, 2)
            engine.advance_months(g, 12 * 10)
            now = (g.year, g.month)
            ad = [c for c in g.characters.values() if c.alive and c.age_at(*now) >= 18]
            emp = [c for c in ad if work.is_employed(c)]
            media = sum(c.income for c in emp) / len(emp) / economy.SALARIO_MINIMO
            self.assertTrue(1.2 < media < 5, media)
            s = economy.summary(g)
            self.assertTrue(0.15 < s["gini_renda"] < 0.65, s["gini_renda"])
            inf, tot = inf + s["informais"], tot + len(emp)
            self.assertLess(sum(c.wealth < 0 for c in ad) / len(ad), 0.3)
            self.assertTrue(all(c.wealth >= -economy.DIVIDA_MAX for c in g.characters.values()))
            self.assertTrue(any(c.rank > 0 for c in emp))
            self.assertTrue(all(0 <= c.rank <= 3 for c in g.characters.values()))
            niveis = s["renda_por_escolaridade"]
            if 3 in niveis and 0 in niveis:
                self.assertGreater(niveis[3], niveis[0])  # formação rende mais
        self.assertTrue(0.03 < inf / tot < 0.4, inf / tot)

    def test_determinismo_e_carregar_continuar(self):
        def novo():
            g = factory.new_game("d", 21)
            for _ in range(6):
                factory.create_family(g, None, 2)
            engine.advance_months(g, 36)
            return g
        a, b = novo(), novo()
        engine.advance_months(a, 60)
        engine.advance_months(b, 60)
        self.assertEqual(snapshot(a), snapshot(b))
        g = novo()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "e.db")
            persistence.save_game(g, path)
            g2 = persistence.load_game(path)
            self.assertEqual(snapshot(g), snapshot(g2))
            engine.advance_months(g, 60)
            engine.advance_months(g2, 60)
            self.assertEqual(snapshot(g), snapshot(g2))
            self.assertEqual(snapshot(g), snapshot(a))

    def test_save_v7_legivel_com_economia_inferida(self):
        g = factory.new_game("v7", 9)
        factory.create_family(g, "Lima", 3)
        engine.advance_months(g, 24)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "v7.db")
            persistence.save_game(g, path)
            con = sqlite3.connect(path)
            for col in ("rank", "rank_since", "informal", "workplace", "experience", "income", "wealth"):
                con.execute(f"ALTER TABLE characters DROP COLUMN {col}")
            con.execute("UPDATE meta SET value='7' WHERE key='schema_version'")
            con.commit()
            con.close()
            g2 = persistence.load_game(path)
            adultos = [c for c in g2.characters.values() if c.alive and c.age_at(g2.year, g2.month) >= 30]
            self.assertTrue(adultos)
            self.assertTrue(all(c.income >= 0 for c in adultos) and any(c.wealth > 0 for c in adultos))
            self.assertTrue(all(c.occupation == g.characters[c.id].occupation for c in g2.characters.values()))
            persistence.save_game(g2, path)
            g3 = persistence.load_game(path)
            self.assertEqual(snapshot(g2), snapshot(g3))
            con = sqlite3.connect(path)
            self.assertEqual(con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0], str(persistence.SCHEMA_VERSION))
            con.close()

    def test_interruptor_economia_desligado(self):
        engine.ECONOMIA = False
        g = factory.new_game("o", 4)
        for _ in range(8):
            factory.create_family(g, None, 2)
        antes = {c.id: (c.wealth, c.income) for c in g.characters.values()}
        engine.advance_months(g, 60)
        for cid, (w, i) in antes.items():
            self.assertEqual((g.characters[cid].wealth, g.characters[cid].income), (w, i))
        self.assertFalse(any(e.category == "heranca" or "promovido" in e.text for e in g.biography))


class TestEmpresas(unittest.TestCase):
    """v0.8.0: empresas genéricas, vagas por ocupação, fechamento e rebalanceamento anual."""

    def _jogo(self, seed=3, familias=6):
        g = factory.new_game("emp", seed)
        for _ in range(familias):
            factory.create_family(g, None, 2)
        return g

    def test_toda_ocupacao_tem_setor(self):
        todas = {o[0] for o in work.OCUPACOES}
        cobertas = set().union(*[set(m) for m in firms.SETORES.values()])
        self.assertEqual(todas, cobertas)

    def test_mundo_inicial_deterministico_e_sem_rng(self):
        a, b = factory.new_game("a", 5), factory.new_game("b", 5)
        antes = a.rng.getstate()
        firms.ensure_world(a)
        firms.ensure_world(b)
        self.assertEqual(len(a.firms), firms.EMPRESAS_INICIAIS)
        self.assertEqual({k: (f.sector, f.size, f.slots) for k, f in a.firms.items()},
                         {k: (f.sector, f.size, f.slots) for k, f in b.firms.items()})
        self.assertEqual(a.rng.getstate(), antes)
        self.assertTrue(all(sum(f.slots.values()) > 0 for f in a.firms.values()))

    def test_empregados_tem_empresa_aberta_e_vagas_nunca_estouram(self):
        g = self._jogo(familias=8)
        engine.advance_months(g, 60)
        emp = [c for c in g.characters.values() if work.is_employed(c)]
        self.assertTrue(emp)
        self.assertTrue(all(g.firms[c.workplace].is_open for c in emp))
        for (fid, occ), n in firms.filled(g).items():
            self.assertLessEqual(n, g.firms[fid].slots.get(occ, 0), (fid, occ))

    def test_sem_vagas_ninguem_e_contratado(self):
        def montar():
            g = factory.new_game("sv", 21)
            for _ in range(6):
                factory.create_character(g, 25)
            now = g.year * 12 + g.month
            for c in g.characters.values():
                work.clear_job(c)
                c.seeking_since, c.retired = now, False
            return g
        controle, sem_vagas = montar(), montar()
        for f in sem_vagas.firms.values():
            f.slots = {}
        self.assertEqual(firms.open_occupations(sem_vagas), set())
        engine.advance_months(controle, 10)   # < 12 meses: sem rebalanceamento anual
        engine.advance_months(sem_vagas, 10)
        self.assertTrue(any(work.is_employed(c) for c in controle.characters.values()))
        self.assertFalse(any(work.is_employed(c) for c in sem_vagas.characters.values()))

    def test_vaga_ocupada_nao_esta_mais_aberta(self):
        g = factory.new_game("vo", 4)
        firms.ensure_world(g)
        for f in g.firms.values():
            f.slots.pop("medico", None)
        alvo = g.firms[0]
        alvo.slots["medico"] = 1
        self.assertIn("medico", firms.open_occupations(g))
        c = factory.create_character(g, 40)
        work.clear_job(c)
        work.start_job(g, c, "medico", g.year * 12 + g.month)
        self.assertEqual(c.workplace, 0)
        self.assertNotIn("medico", firms.open_occupations(g))
        self.assertIn("medico", firms.open_occupations(g, exclude_id=c.id))  # a própria vaga conta para quem a ocupa

    def test_fechar_empresa_demite_todos(self):
        g = self._jogo(familias=8)
        engine.advance_months(g, 6)
        por_empresa = {}
        for (fid, _), n in firms.filled(g).items():
            por_empresa[fid] = por_empresa.get(fid, 0) + n
        self.assertTrue(por_empresa)
        fid = max(por_empresa, key=por_empresa.get)
        ids = sorted(c.id for c in g.characters.values() if work.is_employed(c) and c.workplace == fid)
        demitidos = firms.close_firm(g, fid)
        now = g.year * 12 + g.month
        self.assertEqual(sorted(c.id for c in demitidos), ids)
        self.assertEqual(g.firms[fid].closed, now)
        for c in demitidos:
            self.assertTrue(c.occupation is None and c.workplace is None and c.seeking_since == now)
            self.assertTrue(any("encerrou" in e.text for e in g.events_for(c.id, "trabalho")))
        self.assertEqual(firms.close_firm(g, fid), [])  # idempotente
        self.assertNotIn(fid, [f.id for f, _ in sum((firms.free_by_firm(g, o[0]) for o in work.OCUPACOES), [])])

    def test_rebalanceamento_repoe_vagas_apos_fechamentos(self):
        g = self._jogo(familias=8)
        engine.advance_months(g, 6)
        for f in sorted(g.firms.values(), key=lambda x: x.id)[::2]:
            firms.close_firm(g, f.id)
        firms.yearly(g)
        por_ocup = {}
        for (_, occ), n in firms.filled(g).items():
            por_ocup[occ] = por_ocup.get(occ, 0) + n
        for o in work.OCUPACOES:
            desejado = max(firms.VACANCIA_MIN_ABS, -(-int(firms.VACANCIA_ALVO * por_ocup.get(o[0], 0) * 1000) // 1000))
            livres = sum(n for _, n in firms.free_by_firm(g, o[0]))
            self.assertGreaterEqual(livres, desejado, o[0])
        self.assertGreaterEqual(firms.vacancy_stats(g)["abertas"], firms.EMPRESAS_ABERTAS_MIN)

    def test_excesso_de_vagas_encolhe_e_empresa_vazia_e_dissolvida(self):
        g = self._jogo(familias=2)
        firms.ensure_world(g)
        antes = firms.vacancy_stats(g)
        r = firms.yearly(g)
        depois = firms.vacancy_stats(g)
        self.assertLess(depois["vagas"], antes["vagas"])
        self.assertTrue(r["dissolvidas"])
        self.assertTrue(all(g.firms[i].closed is not None for i in r["dissolvidas"]))
        for (fid, occ), n in firms.filled(g).items():
            self.assertLessEqual(n, g.firms[fid].slots.get(occ, 0))

    def test_informalidade_por_porte(self):
        mic, med, gra = (firms.PORTES[n][3] for n in ("micro", "média", "grande"))
        self.assertTrue(mic > med > gra)
        micro = firms.Firm(0, "x", "comércio", "micro", 0)
        grande = firms.Firm(1, "y", "comércio", "grande", 0)
        self.assertGreater(firms.informal_probability(0, micro), firms.informal_probability(0, grande))
        self.assertLessEqual(firms.informal_probability(0, micro), 0.95)
        self.assertEqual(firms.informal_probability(2, None), work.INFORMAL_PROB[2])

    def test_persistencia_e_continuidade_com_empresas(self):
        g = self._jogo(familias=6)
        engine.advance_months(g, 30)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "e.db")
            persistence.save_game(g, path)
            a = persistence.load_game(path)
            self.assertEqual(snapshot(g), snapshot(a))
            engine.advance_months(g, 30)
            engine.advance_months(a, 30)  # atravessa janeiros: fechamentos/fundações idênticos
            self.assertEqual(snapshot(g), snapshot(a))

    def test_migracao_de_save_v8_cria_empresas(self):
        g = self._jogo(familias=5)
        engine.advance_months(g, 24)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "v8.db")
            persistence.save_game(g, path)
            con = sqlite3.connect(path)
            con.execute("DROP TABLE firms")
            con.execute("DELETE FROM meta WHERE key='next_firm_id'")
            con.execute("UPDATE characters SET workplace = id % 25 WHERE workplace IS NOT NULL")
            con.execute("UPDATE meta SET value='8' WHERE key='schema_version'")
            con.commit()
            con.close()
            g2 = persistence.load_game(path)
            emp = [c for c in g2.characters.values() if work.is_employed(c)]
            self.assertTrue(emp and g2.firms)
            self.assertTrue(all(g2.firms[c.workplace].is_open for c in emp))
            for (fid, occ), n in firms.filled(g2).items():
                self.assertLessEqual(n, g2.firms[fid].slots.get(occ, 0))
            self.assertEqual({c.id: c.occupation for c in g2.characters.values()},
                             {c.id: c.occupation for c in g.characters.values()})
            persistence.save_game(g2, path)
            self.assertEqual(snapshot(g2), snapshot(persistence.load_game(path)))

    def test_interruptor_empresas_desligado(self):
        firms.ATIVO = False
        self.addCleanup(setattr, firms, "ATIVO", True)
        g = self._jogo(familias=4)
        engine.advance_months(g, 36)
        self.assertEqual(g.firms, {})
        self.assertTrue(all(c.workplace is None or 0 <= c.workplace < work.LOCAIS_TRABALHO
                            for c in g.characters.values()))

    def test_cli_mostra_empresas_e_vagas(self):
        g = self._jogo(familias=3)
        engine.advance_months(g, 12)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ui_cli.show_firms(g)
            ui_cli.show_economy(g)
        out = buf.getvalue()
        self.assertIn("Empresas e vagas", out)
        self.assertIn("vagas ocupadas", out)
        self.assertIn("Vagas livres", out)


class TestCicloEconomico(unittest.TestCase):
    """v0.9.0: índice anual determinístico (sem game.rng) que modula o mercado de trabalho."""

    def test_indice_deterministico_e_na_faixa(self):
        for seed in (1, 7, 123):
            serie = [cycle.index(seed, a) for a in range(2020, 2080)]
            self.assertEqual(serie, [cycle.index(seed, a) for a in range(2020, 2080)])
            self.assertTrue(all(-cycle.LIMITE <= v <= cycle.LIMITE for v in serie))
        self.assertNotEqual([cycle.index(1, a) for a in range(2026, 2046)],
                            [cycle.index(2, a) for a in range(2026, 2046)])
        self.assertEqual(cycle.index(5, cycle.ANO_BASE), 0.0)

    def test_media_proxima_de_zero_e_ha_recessoes_e_expansoes(self):
        vals = [cycle.index(seed, a) for seed in range(100) for a in range(2026, 2051)]
        self.assertLess(abs(sum(vals) / len(vals)), 0.08)
        self.assertGreater(sum(1 for v in vals if cycle.label(v) == "recessão"), 100)
        self.assertGreater(sum(1 for v in vals if cycle.label(v) == "expansão"), 100)

    def test_cache_nao_muda_o_resultado(self):
        cycle._cache.clear()
        a = cycle.index(9, 2040)
        cycle._cache.clear()
        cycle.index(9, 2035)           # preenche parte da cadeia, depois pede um ano mais novo
        self.assertEqual(cycle.index(9, 2040), a)

    def test_nao_usa_game_rng(self):
        g = factory.new_game("c", 4)
        antes = g.rng.getstate()
        cycle.current(g)
        self.assertEqual(g.rng.getstate(), antes)

    def test_fatores_e_rotulos_literais(self):
        self.assertEqual((cycle.hire_factor(0), cycle.separation_factor(0),
                          cycle.closure_factor(0), cycle.vacancy_factor(0)), (1, 1, 1, 1))
        self.assertAlmostEqual(cycle.hire_factor(1.0), 1.45)
        self.assertAlmostEqual(cycle.hire_factor(-1.0), 0.55)
        self.assertAlmostEqual(cycle.separation_factor(1.0), 0.5)
        self.assertAlmostEqual(cycle.closure_factor(1.0), 0.2)
        self.assertAlmostEqual(cycle.closure_factor(-1.0), 1.8)
        self.assertAlmostEqual(cycle.vacancy_factor(-1.0), 0.5)
        self.assertEqual((cycle.label(-0.9), cycle.label(0.0), cycle.label(0.9)),
                         ("recessão", "estabilidade", "expansão"))

    def test_interruptor_desliga_o_ciclo(self):
        g = factory.new_game("c", 4)
        g.year = 2031
        self.assertNotEqual(cycle.current(g), 0.0)
        with mock.patch.object(cycle, "ATIVO", False):
            self.assertEqual(cycle.current(g), 0.0)

    def _emprego(self, idx, seed=11):
        g = factory.new_game("ciclo", seed)
        for _ in range(14):
            factory.create_family(g, None, 2)
        with mock.patch.object(cycle, "current", return_value=idx):
            engine.advance_months(g, 36)
        s = economy.summary(g)
        return s["empregados"] / max(1, s["empregados"] + s["procurando"])

    def test_expansao_emprega_mais_que_recessao(self):
        exp, rec = self._emprego(1.0), self._emprego(-1.0)
        self.assertGreater(exp, rec + 0.10, (exp, rec))

    def test_fechamento_de_empresas_segue_o_fator_do_ciclo(self):
        def fechadas(fator):
            g = factory.new_game("f", 3)
            firms.ensure_world(g)
            g.month = 1
            with mock.patch.object(cycle, "closure_factor", return_value=fator):
                return len(firms.yearly(g)["fechadas"])
        self.assertEqual(fechadas(0.0), 0)
        self.assertGreaterEqual(fechadas(1000.0), 10)

    def test_panorama_inclui_clima(self):
        g = factory.new_game("c", 4)
        factory.create_family(g, None, 2)
        s = economy.summary(g)
        self.assertIn(s["clima"], ("recessão", "estabilidade", "expansão"))
        self.assertEqual(s["indice_ciclo"], cycle.current(g))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ui_cli.show_economy(g)
        self.assertIn("Clima econômico: " + s["clima"], buf.getvalue())


class SeguroBase:
    """Auxiliares: adultos com vínculo FORMAL numa empresa de porte conhecido (salário calculável à mão)."""

    def _jogo(self, seed=7, n=2, porte="média", ocup="professor", meses=30):
        g = factory.new_game("seg", seed)
        for _ in range(8):
            factory.create_family(g, None, 2)
        firm = firms.found_firm(g, sector="educação e saúde", size=porte)
        now = g.year * 12 + g.month
        adultos = [c for c in g.characters.values() if 25 <= c.age_at(g.year, g.month) <= 50][:n]
        self.assertEqual(len(adultos), n)
        for c in adultos:
            c.occupation, c.job_start, c.informal = ocup, now - meses, False
            c.rank, c.rank_since, c.experience, c.workplace = 0, now - meses, 0, firm.id
            c.retired, c.seeking_since = False, None
            c.in_school = c.in_college = False
        return g, adultos, firm, now


class TestSeguroDesemprego(SeguroBase, unittest.TestCase):
    """v0.9.1: demissão involuntária de vínculo formal (≥12 meses) gera parcelas de seguro-desemprego."""

    def test_valor_e_parcelas_literais(self):
        g, (c,), firm, now = self._jogo(n=1)  # professor 3,0 mín. × 1500 × 1,06 (média) = 4770 → 60% = 2862
        self.assertEqual(economy.unemployment_benefit(c, now, firm), (2862.0, 5))
        c.job_start = now - 15
        self.assertEqual(economy.unemployment_benefit(c, now, firm), (2862.0, 4))
        c.job_start = now - 24
        self.assertEqual(economy.unemployment_benefit(c, now, firm)[1], 5)
        c.job_start = now - 12
        self.assertEqual(economy.unemployment_benefit(c, now, firm)[1], 4)

    def test_nao_elegiveis(self):
        g, (c,), firm, now = self._jogo(n=1)
        c.job_start = now - 11
        self.assertEqual(economy.unemployment_benefit(c, now, firm), (0.0, 0))
        c.job_start, c.informal = now - 30, True
        self.assertEqual(economy.unemployment_benefit(c, now, firm), (0.0, 0))
        c.informal, c.occupation = False, None
        self.assertEqual(economy.unemployment_benefit(c, now, firm), (0.0, 0))
        c.occupation, c.job_start = "professor", None
        self.assertEqual(economy.unemployment_benefit(c, now, firm), (0.0, 0))
        c.job_start = now - 30
        with mock.patch.object(economy, "SEGURO_ATIVO", False):
            self.assertEqual(economy.unemployment_benefit(c, now, firm), (0.0, 0))

    def test_piso_e_teto(self):
        g, (c,), firm, now = self._jogo(n=1, ocup="servicos_gerais")  # 1500×1,06×0,6 = 954 → piso 1500
        self.assertEqual(economy.unemployment_benefit(c, now, firm)[0], 1500.0)
        c.occupation = "medico"                                         # 12×1500×1,06×0,6 = 11448 → teto 3000
        self.assertEqual(economy.unemployment_benefit(c, now, firm)[0], 3000.0)

    def test_demissao_por_fechamento_concede_aos_formais_e_nao_aos_informais(self):
        g, (formal, informal), firm, now = self._jogo(n=2)
        informal.informal = True
        firms.close_firm(g, firm.id)
        self.assertIsNone(formal.occupation)
        self.assertEqual((formal.unemp_amount, formal.unemp_until), (2862.0, now + 4))
        self.assertEqual((informal.unemp_amount, informal.unemp_until), (0.0, None))
        textos = [e.text for e in g.events_for(formal.id, "trabalho")]
        self.assertTrue(any("seguro-desemprego: R$ 2.862,00/mês por 5 meses" in t for t in textos), textos)
        self.assertFalse(any("seguro" in e.text for e in g.events_for(informal.id, "trabalho")))

    def test_renda_durante_as_parcelas_e_depois(self):
        g, (c,), firm, now = self._jogo(n=1)
        firms.close_firm(g, firm.id)               # 5 parcelas: meses now+1 … now+4 em simulação (+ o mês da demissão)
        with mock.patch.object(work, "hire_monthly", return_value=0.0):
            engine.advance_months(g, 1)
            self.assertEqual(c.income, 2862.0)
            engine.advance_months(g, 3)            # último mês com parcela (now+4)
            self.assertEqual(c.income, 2862.0)
            self.assertEqual(c.unemp_until, now + 4)
            engine.advance_months(g, 1)            # esgotado
            self.assertEqual(c.income, 0.0)
            self.assertEqual((c.unemp_until, c.unemp_amount), (None, 0.0))

    def test_novo_emprego_encerra_o_seguro(self):
        g, (c,), firm, now = self._jogo(n=1)
        firms.close_firm(g, firm.id)
        self.assertGreater(c.unemp_amount, 0)
        work.start_job(g, c, "professor", now + 1)
        self.assertEqual((c.unemp_until, c.unemp_amount), (None, 0.0))

    def test_demissao_mensal_pelo_motor_concede(self):
        g, (c,), firm, now = self._jogo(n=1)
        with mock.patch.object(work, "separation_monthly", return_value=1.0), \
             mock.patch.object(work, "hire_monthly", return_value=0.0), \
             mock.patch.object(work, "job_change_monthly", return_value=0.0), \
             mock.patch.object(work, "retirement_monthly", return_value=0.0):
            engine.advance_months(g, 1)
        self.assertIsNone(c.occupation)
        self.assertEqual(c.unemp_amount, 2862.0)

    def test_sem_economia_nao_concede_na_demissao_mensal(self):
        g, (c,), firm, now = self._jogo(n=1)
        with mock.patch.object(engine, "ECONOMIA", False), \
             mock.patch.object(work, "separation_monthly", return_value=1.0), \
             mock.patch.object(work, "hire_monthly", return_value=0.0), \
             mock.patch.object(work, "job_change_monthly", return_value=0.0), \
             mock.patch.object(work, "retirement_monthly", return_value=0.0):
            engine.advance_months(g, 1)
        self.assertEqual(c.unemp_amount, 0.0)

    def test_panorama_conta_segurados(self):
        g, (a, b), firm, now = self._jogo(n=2)
        firms.close_firm(g, firm.id)
        self.assertEqual(economy.summary(g)["segurados"], 2)

    def test_ficha_mostra_ultima_parcela(self):
        g, (c,), firm, now = self._jogo(n=1)
        g.year, g.month = 2030, 12
        now = g.year * 12 + g.month
        c.job_start = now - 30
        firms.close_firm(g, firm.id)               # 5 parcelas: dez/2030 … abr/2031
        c.income = 2862.0
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ui_cli.show_character(g, c)
        self.assertIn("Seguro-desemprego: R$ 2.862,00/mês (última parcela em 04/2031)", buf.getvalue())

    def test_salvar_e_carregar_preserva_o_beneficio(self):
        g, (c,), firm, now = self._jogo(n=1)
        firms.close_firm(g, firm.id)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.db")
            persistence.save_game(g, path)
            g2 = persistence.load_game(path)
        self.assertEqual((g2.characters[c.id].unemp_amount, g2.characters[c.id].unemp_until), (2862.0, now + 4))
        self.assertEqual(snapshot(g), snapshot(g2))

    def test_save_v9_sem_colunas_novas_continua_legivel(self):
        g, (c,), firm, now = self._jogo(n=1)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.db")
            persistence.save_game(g, path)
            con = sqlite3.connect(path)
            con.execute("ALTER TABLE characters DROP COLUMN unemp_until")
            con.execute("ALTER TABLE characters DROP COLUMN unemp_amount")
            con.execute("UPDATE meta SET value='9' WHERE key='schema_version'")
            con.commit()
            con.close()
            g2 = persistence.load_game(path)
        self.assertEqual((g2.characters[c.id].unemp_until, g2.characters[c.id].unemp_amount), (None, 0.0))
        self.assertEqual(g2.characters[c.id].occupation, "professor")
        # a economia JÁ gravada não pode ser reinferida ao carregar um save v9 (regressão real da 0.9.1)
        for k, a in g.characters.items():
            b = g2.characters[k]
            self.assertEqual((b.income, b.wealth, b.workplace, b.experience, b.rank, b.informal),
                             (a.income, a.wealth, a.workplace, a.experience, a.rank, a.informal), k)

    def test_continuar_apos_carregar_e_identico(self):
        g, adultos, firm, now = self._jogo(n=2)
        firms.close_firm(g, firm.id)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.db")
            persistence.save_game(g, path)
            g2 = persistence.load_game(path)
        engine.advance_months(g, 18)
        engine.advance_months(g2, 18)
        self.assertEqual(snapshot(g), snapshot(g2))


class TestPremioPorte(SeguroBase, unittest.TestCase):
    """v0.9.2: o salário depende do porte da empresa (grande paga mais que micro)."""

    def test_fatores_literais(self):
        g, (c,), firm, now = self._jogo(n=1)   # professor: 3,0 × 1500 = 4500 (sem experiência, júnior)
        casos = {"micro": 4050.0, "pequena": 4365.0, "média": 4770.0, "grande": 5130.0}
        for porte, esperado in casos.items():
            f = firms.found_firm(g, sector="educação e saúde", size=porte)
            self.assertEqual(economy.monthly_salary(c, f), esperado, porte)

    def test_sem_empresa_ou_com_interruptor_desligado_nada_muda(self):
        g, (c,), firm, now = self._jogo(n=1)
        self.assertEqual(economy.monthly_salary(c), 4500.0)
        with mock.patch.object(economy, "PREMIO_PORTE", False):
            self.assertEqual(economy.monthly_salary(c, firm), 4500.0)

    def test_combina_com_informal_e_experiencia(self):
        g, (c,), firm, now = self._jogo(n=1)
        grande = firms.found_firm(g, sector="educação e saúde", size="grande")
        c.informal, c.experience = True, 60    # 4500 × 1,10 (5 anos) × 0,8 × 1,14
        self.assertEqual(economy.monthly_salary(c, grande), round(4500 * 1.10 * 0.8 * 1.14, 2))

    def test_apply_month_usa_a_empresa_do_vinculo(self):
        g, (c,), firm, now = self._jogo(n=1)
        grande = firms.found_firm(g, sector="educação e saúde", size="grande")
        c.workplace = grande.id
        economy.apply_month(g)
        self.assertEqual(c.income, economy.monthly_salary(c, grande))
        self.assertGreater(c.income, 4500.0 * 1.13)

    def test_aposentadoria_considera_o_porte(self):
        g, (c,), firm, now = self._jogo(n=1)
        grande = firms.found_firm(g, sector="educação e saúde", size="grande")
        self.assertEqual(economy.pension(c, grande), round(0.7 * 5130.0, 2))
        self.assertEqual(economy.pension(c), round(0.7 * 4500.0, 2))

    def test_promocao_mostra_salario_com_porte(self):
        g, (c,), firm, now = self._jogo(n=1)
        c.rank_since = now - 40
        with mock.patch.object(work, "promotion_monthly", return_value=1.0), \
             mock.patch.object(work, "separation_monthly", return_value=0.0), \
             mock.patch.object(work, "job_change_monthly", return_value=0.0), \
             mock.patch.object(work, "retirement_monthly", return_value=0.0):
            engine.advance_months(g, 1)
        self.assertEqual(c.rank, 1)
        txt = [e.text for e in g.events_for(c.id, "trabalho") if "promovido" in e.text][-1]
        self.assertIn("novo salário: R$ 5.962,50", txt)   # 4500 × 1,25 (pleno) × 1,06 (média), no mês da promoção


class TestV0100(unittest.TestCase):
    """v0.10.0: fim de amizades, gêmeos e guarda dos filhos no divórcio."""

    def _pop(self, g, n=120, idade=(20, 40)):
        return [factory.create_character(g, idade[0] + i % (idade[1] - idade[0]), "FM"[i % 2]) for i in range(n)]

    # --- fim de amizades
    def test_amizades_terminam_e_contas_batem(self):
        g = factory.new_game("t", 3)
        self._pop(g)
        engine.advance_months(g, 60)
        fim = g.events_for(None, "amizade_fim")
        self.assertGreater(len(fim), 10)
        eva = g.events_for(None, "amizade")
        self.assertEqual(len(eva) - len(fim), 2 * len(g.friendships))
        for e in fim:
            self.assertIn("Afastou-se de", e.text)

    def test_interruptor_fim_amizades(self):
        g = factory.new_game("t", 3)
        self._pop(g)
        with mock.patch.object(engine, "FIM_AMIZADES", False):
            engine.advance_months(g, 36)
        self.assertEqual(g.events_for(None, "amizade_fim"), [])
        self.assertGreater(len(g.friendships), 20)

    def test_remove_friendship_simetrica(self):
        g = factory.new_game("t", 1)
        a, b = factory.create_character(g, 30), factory.create_character(g, 31)
        g.add_friendship(a.id, b.id)
        g.remove_friendship(b.id, a.id)
        self.assertFalse(g.are_friends(a.id, b.id) or g.are_friends(b.id, a.id))
        self.assertEqual(g.friendships, {})
        g.remove_friendship(a.id, b.id)  # idempotente

    def test_chance_de_afastamento_modulada(self):
        g = factory.new_game("t", 1)
        a, b = factory.create_character(g, 30), factory.create_character(g, 31)
        now = (g.year, g.month)
        recente = (g.year, g.month)
        antiga = (g.year - 10, g.month)
        for t in ("abertura", "amabilidade", "extroversao"):
            a.personality[t] = b.personality[t] = 50
        base = engine.drift_monthly(a, b, now, recente)
        self.assertLess(engine.drift_monthly(a, b, now, antiga), 0.6 * base)  # amizade longa esfria menos
        b.personality.update(abertura=0, amabilidade=100, extroversao=0)
        self.assertGreater(engine.drift_monthly(a, b, now, recente), base)  # pouca afinidade esfria mais
        b.personality.update(abertura=50, amabilidade=50, extroversao=50)
        for c in (a, b):
            c.occupation, c.workplace, c.retired = "operador", 7, False
            c.seeking_since = None
        if engine._coworkers(a, b):
            self.assertLess(engine.drift_monthly(a, b, now, recente), base)

    # --- gêmeos
    def _casais(self, g, n, idade=24):
        out = []
        for _ in range(n):
            m = factory.create_character(g, idade, "F", last_name="Lima")
            f = factory.create_character(g, idade + 2, "M", last_name="Lima")
            m.spouse_id, f.spouse_id = f.id, m.id
            m.health = f.health = 100
            out.append((m, f))
        return out

    def _sem_ruido(self):
        for nome in ("DIVORCIO_BASE",):
            self.addCleanup(setattr, engine, nome, getattr(engine, nome))
        engine.DIVORCIO_BASE = 0.0
        for nome in ("CIRCULO_SOCIAL", "EDUCACAO", "TRABALHO", "ECONOMIA"):
            p = mock.patch.object(engine, nome, False)
            p.start()
            self.addCleanup(p.stop)

    def test_gemeos_nascem_no_mesmo_mes_e_respeitam_limite(self):
        self._sem_ruido()
        g = factory.new_game("t", 5)
        casais = self._casais(g, 12)
        with mock.patch.object(engine, "GEMEOS_CHANCE", 1.0):
            engine.advance_months(g, 12 * 20)
        ev = g.events_for(None, "gemeos")
        self.assertGreater(len(ev), 4)
        for m, f in casais:
            filhos = g.children_of(m.id)
            self.assertLessEqual(len(filhos), engine.MAX_FILHOS)
            datas = [(c.birth_year, c.birth_month) for c in filhos]
            for d in set(datas):  # com chance 1, toda data de parto tem 2 filhos
                self.assertEqual(datas.count(d), 2)

    def test_gemeos_interruptor_e_taxa_realista(self):
        self._sem_ruido()
        g = factory.new_game("t", 6)
        self._casais(g, 40)
        with mock.patch.object(engine, "GEMEOS", False):
            engine.advance_months(g, 12 * 10)
        self.assertEqual(g.events_for(None, "gemeos"), [])
        g2 = factory.new_game("t", 6)
        self._casais(g2, 150)
        with mock.patch.object(engine, "GESTACAO", False):   # com gestação, o atraso de 9 meses reduz os partos no horizonte
            engine.advance_months(g2, 12 * 12)
        partos = len(g2.events_for(None, "nascimento_filho")) // 2
        gem = len(g2.events_for(None, "gemeos")) // 2
        self.assertGreater(partos, 150)
        self.assertLess(gem / partos, 0.05)

    # --- guarda
    def _divorciar(self, g, idades_filhos=(8, 12), renda_m=0.0, renda_p=0.0):
        m = factory.create_character(g, 35, "F", last_name="Lima")
        f = factory.create_character(g, 37, "M", last_name="Lima")
        m.spouse_id, f.spouse_id = f.id, m.id
        m.income, f.income = renda_m, renda_p
        kids = [factory.create_character(g, i, mother_id=m.id, father_id=f.id, last_name="Lima") for i in idades_filhos]
        engine._divorce(g, m, f)
        return m, f, kids

    def test_guarda_define_responsavel_e_registra_eventos(self):
        g = factory.new_game("t", 1)
        m, f, (k1, k2) = self._divorciar(g, (8, 25))
        self.assertIn(k1.guardian_id, (m.id, f.id))
        self.assertIsNone(k2.guardian_id)  # maior de idade: sem guarda
        self.assertEqual(len(g.events_for(k1.id, "guarda")), 1)
        self.assertEqual(g.events_for(k2.id, "guarda"), [])
        self.assertEqual(len(g.events_for(m.id, "guarda")), 1)
        self.assertEqual(len(g.events_for(f.id, "guarda")), 1)

    def test_guarda_interruptor_e_sem_filhos(self):
        g = factory.new_game("t", 1)
        with mock.patch.object(engine, "GUARDA", False):
            m, f, (k,) = self._divorciar(g, (8,))
        self.assertIsNone(k.guardian_id)
        m2, f2, _ = self._divorciar(g, ())  # sem filhos: nada a decidir
        self.assertEqual(g.events_for(m2.id, "guarda"), [])

    def test_guarda_maioria_com_a_mae_e_renda_do_pai_pesa(self):
        def fracao_pai(renda_m, renda_p, n=300):
            g = factory.new_game("t", 9)
            com_pai = 0
            for _ in range(n):
                m, f, (k,) = self._divorciar(g, (8,), renda_m, renda_p)
                com_pai += k.guardian_id == f.id
            return com_pai / n
        sem_renda = fracao_pai(0.0, 0.0)
        pai_rico = fracao_pai(1000.0, 9000.0)
        self.assertGreater(sem_renda, 0.04)
        self.assertLess(sem_renda, 0.22)
        self.assertGreater(pai_rico, sem_renda)
        self.assertLessEqual(pai_rico, 0.6 + 0.08)

    def test_domicilio_segue_a_guarda_e_cai_para_o_outro_genitor(self):
        g = factory.new_game("t", 2)
        m, f, (k,) = self._divorciar(g, (8,))
        k.guardian_id = f.id
        h = economy.household_of(g, k)
        self.assertIn(f.id, [a.id for a in h["adults"]])
        f.alive = False  # guardião morre: volta para a mãe
        h = economy.household_of(g, k)
        self.assertIn(m.id, [a.id for a in h["adults"]])

    def test_save_v11_preserva_guarda_e_v10_carrega(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "j.db")
            g = factory.new_game("t", 4)
            m, f, (k,) = self._divorciar(g, (8,))
            gid = k.guardian_id
            persistence.save_game(g, path)
            self.assertEqual(persistence.load_game(path).characters[k.id].guardian_id, gid)
            con = sqlite3.connect(path)
            con.execute("UPDATE meta SET value='10' WHERE key='schema_version'")
            con.commit()
            con.close()
            self.assertIsNotNone(persistence.load_game(path))  # v10 ainda é legível


class TestNamoro(unittest.TestCase):
    """v0.11.0: namoro (casais, términos, pedido de casamento) sem usar game.rng."""

    def _pop(self, g, n=120):
        return [factory.create_character(g, 18 + i % 18, "FM"[i % 2]) for i in range(n)]

    def test_casais_mutuos_e_validos(self):
        g = factory.new_game("t", 5)
        self._pop(g)
        engine.advance_months(g, 48)
        inicios = [e for e in g.events_for(None, "namoro") if e.text.startswith("Começou")]
        self.assertGreater(len(inicios), 20)
        casais = 0
        for c in g.characters.values():
            if c.partner_id is None:
                continue
            p = g.characters[c.partner_id]
            casais += 1
            self.assertEqual(p.partner_id, c.id)
            self.assertEqual(p.partner_since, c.partner_since)
            self.assertNotEqual(c.sex, p.sex)
            self.assertFalse(engine.close_kin(c, p, g))
            self.assertFalse(engine.has_active_spouse(g, c))
            self.assertTrue(c.alive and p.alive)
        self.assertGreater(casais, 0)

    def test_namoro_termina_e_vira_casamento(self):
        g = factory.new_game("t", 5)
        self._pop(g)
        engine.advance_months(g, 72)
        fins = [e for e in g.events_for(None, "namoro_fim") if e.text.startswith("Terminou")]
        pedidos = [e for e in g.events_for(None, "namoro") if "decidiu se casar" in e.text]
        self.assertGreater(len(fins), 5)
        self.assertGreater(len(pedidos), 5)
        for e in pedidos:   # quem decidiu casar tem cônjuge e já não tem parceiro de namoro
            c = g.characters[e.char_id]
            self.assertIsNotNone(c.spouse_id)
            self.assertIsNone(c.partner_id)

    def test_interruptor(self):
        g = factory.new_game("t", 5)
        self._pop(g)
        with mock.patch.object(romance, "ATIVO", False):
            engine.advance_months(g, 36)
        self.assertEqual(g.events_for(None, "namoro"), [])
        self.assertTrue(all(c.partner_id is None for c in g.characters.values()))

    def test_idades_compativeis(self):
        g = factory.new_game("t", 1)
        a, b = factory.create_character(g, 16, "F"), factory.create_character(g, 16, "M")
        c, d = factory.create_character(g, 25, "M"), factory.create_character(g, 15, "M")
        now = (g.year, g.month)
        self.assertTrue(romance.compatible(g, a, b, now))
        self.assertFalse(romance.compatible(g, a, c, now))   # 16 x 25: diferença > 3 com menor de 18
        self.assertFalse(romance._eligible(g, d, now))        # 15 anos: fora da idade mínima

    def test_luto_do_parceiro(self):
        g = factory.new_game("t", 1)
        a, b = factory.create_character(g, 30, "F"), factory.create_character(g, 31, "M")
        romance.start(g, a, b)
        engine._die(g, a, 30)
        romance.run(g)
        self.assertIsNone(b.partner_id)
        self.assertIsNone(a.partner_id)
        self.assertTrue(any("faleceu" in e.text for e in g.events_for(b.id, "namoro_fim")))

    def test_probabilidades(self):
        g = factory.new_game("t", 1)
        a, b = factory.create_character(g, 25, "F"), factory.create_character(g, 27, "M")
        self.assertEqual(romance.marry_monthly(25, 5), 0.0)       # menos de 6 meses
        self.assertEqual(romance.marry_monthly(17, 36), 0.0)      # menor de 18
        self.assertGreater(romance.marry_monthly(25, 12), 0.0)
        self.assertLess(romance.breakup_monthly(a, b, 36), romance.breakup_monthly(a, b, 6))
        a.personality["neuroticismo"] = b.personality["neuroticismo"] = 100
        alto = romance.breakup_monthly(a, b, 6)
        a.personality["neuroticismo"] = b.personality["neuroticismo"] = 0
        self.assertGreater(alto, romance.breakup_monthly(a, b, 6))

    def test_nao_usa_rng_principal(self):
        g = factory.new_game("t", 5)
        self._pop(g, 40)
        antes = g.rng.getstate()
        for _ in range(12):
            romance.run(g)
            g.month += 1
        self.assertEqual(g.rng.getstate(), antes)
        self.assertGreater(len(g.events_for(None, "namoro")), 0)

    def test_salvar_carregar_e_continuar(self):
        g1 = factory.new_game("t", 8)
        self._pop(g1, 80)
        engine.advance_months(g1, 24)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "n.db")
            persistence.save_game(g1, path)
            g2 = persistence.load_game(path)
        par = lambda g: sorted((c.id, c.partner_id, c.partner_since) for c in g.characters.values())
        self.assertEqual(par(g1), par(g2))
        self.assertTrue(any(x[1] is not None for x in par(g1)))
        engine.advance_months(g1, 24)
        engine.advance_months(g2, 24)
        self.assertEqual(snapshot(g1), snapshot(g2))
        self.assertEqual(par(g1), par(g2))

    def test_save_v11_sem_colunas_de_namoro(self):
        g = factory.new_game("t", 8)
        self._pop(g, 30)
        engine.advance_months(g, 12)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "v11.db")
            persistence.save_game(g, path)
            con = sqlite3.connect(path)
            con.execute("ALTER TABLE characters DROP COLUMN partner_id")
            con.execute("ALTER TABLE characters DROP COLUMN partner_since")
            con.execute("UPDATE meta SET value='11' WHERE key='schema_version'")
            con.commit()
            con.close()
            g2 = persistence.load_game(path)
        self.assertEqual(len(g2.characters), len(g.characters))
        self.assertTrue(all(c.partner_id is None for c in g2.characters.values()))

    def test_ficha_mostra_namoro(self):
        g = factory.new_game("t", 1)
        a, b = factory.create_character(g, 30, "F"), factory.create_character(g, 31, "M")
        romance.start(g, a, b)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ui_cli.show_character(g, a)
        self.assertIn(f"Namoro: {b.full_name}", buf.getvalue())


class TestGestacao(unittest.TestCase):
    """v0.12.0: gestação (concepção → 9 meses → parto), perda gestacional, persistência."""

    def setUp(self):
        for nome, val in (("DIVORCIO_BASE", 0.0), ("CIRCULO_SOCIAL", False), ("EDUCACAO", False),
                          ("TRABALHO", False), ("ECONOMIA", False)):
            p = mock.patch.object(engine, nome, val)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(romance, "ATIVO", False)
        p.start()
        self.addCleanup(p.stop)

    def _casais(self, g, n=40, idade=27):
        ms = []
        for _ in range(n):
            w, h = factory.create_character(g, idade, "F"), factory.create_character(g, idade + 3, "M")
            w.spouse_id, h.spouse_id = h.id, w.id
            ms.append(w)
        return ms

    def _abs(self, e):
        return e.year * 12 + e.month

    def test_parto_exatamente_nove_meses_depois(self):
        g = factory.new_game("t", 4)
        self._casais(g, 40)
        engine.advance_months(g, 60)
        conc = {(e.char_id, self._abs(e)) for e in g.events_for(None, "gravidez") if e.text.startswith("Engravidou")}
        self.assertGreater(len(conc), 20)
        partos = {(e.char_id, self._abs(e)) for e in g.events_for(None, "nascimento_filho") if e.text.startswith("Deu à luz")}
        self.assertGreater(len(partos), 15)
        for cid, mes in partos:   # todo parto vem de uma concepção 9 meses antes
            self.assertIn((cid, mes - engine.GESTACAO_MESES), conc)

    def test_nao_engravida_estando_gravida(self):
        g = factory.new_game("t", 4)
        self._casais(g, 40)
        engine.advance_months(g, 72)
        por_mae = {}
        for e in g.events_for(None, "gravidez"):
            if e.text.startswith("Engravidou"):
                por_mae.setdefault(e.char_id, []).append(self._abs(e))
        for cid, meses in por_mae.items():
            for a, b in zip(meses, meses[1:]):
                self.assertGreaterEqual(b - a, engine.GESTACAO_MESES + 6)   # 9 meses + espera mínima (15 - 9)

    def test_perda_gestacional(self):
        g = factory.new_game("t", 4)
        self._casais(g, 40)
        with mock.patch.object(engine, "ABORTO_ESPONTANEO", 0.9999):
            engine.advance_months(g, 36)
        perdas = [e for e in g.events_for(None, "gravidez") if "perda gestacional" in e.text]
        self.assertGreater(len(perdas), 10)
        self.assertEqual(g.events_for(None, "nascimento_filho"), [])
        self.assertTrue(all(c.mother_id is None for c in g.characters.values()))

    def test_interruptor_parto_imediato(self):
        g = factory.new_game("t", 4)
        self._casais(g, 40)
        with mock.patch.object(engine, "GESTACAO", False):
            engine.advance_months(g, 48)
        self.assertEqual(g.events_for(None, "gravidez"), [])
        self.assertGreater(len(g.events_for(None, "nascimento_filho")), 10)
        self.assertTrue(all(c.pregnant_until is None for c in g.characters.values()))

    def test_morte_da_mae_encerra_gestacao(self):
        g = factory.new_game("t", 1)
        w, = self._casais(g, 1)
        h = g.characters[w.spouse_id]
        engine._conceive(g, w, h)
        self.assertIsNotNone(w.pregnant_until)
        engine._die(g, w, 27)
        self.assertIsNone(w.pregnant_until)
        engine.advance_months(g, 15)
        self.assertEqual(g.children_of(w.id), [])

    def test_pai_morre_durante_a_gestacao(self):
        g = factory.new_game("t", 1)
        w, = self._casais(g, 1)
        h = g.characters[w.spouse_id]
        engine._conceive(g, w, h)
        engine._die(g, h, 30)
        with mock.patch.object(engine, "ABORTO_ESPONTANEO", 0.0), mock.patch.object(engine, "maternal_death_risk", lambda a, s: 0.0):
            engine.advance_months(g, 10)
        filhos = g.children_of(w.id)
        self.assertGreaterEqual(len(filhos), 1)
        self.assertEqual(filhos[0].father_id, h.id)
        self.assertEqual(filhos[0].last_name, h.last_name)
        self.assertEqual([e for e in g.events_for(h.id, "nascimento_filho")], [])   # pai falecido não recebe evento

    def test_conceicao_monthly_e_intervalo(self):
        self.assertGreater(engine.conception_monthly(27), engine.birth_monthly(27))
        self.assertEqual(engine.conception_monthly(45), 0.0)
        g = factory.new_game("t", 1)
        w, = self._casais(g, 1)
        h = g.characters[w.spouse_id]
        agora = g.year * 12 + g.month
        for atras, esperado in ((5, False), (6, True)):   # parto anterior há 5 meses: ainda não; 6: pode (15 - 9)
            ano, mes = divmod(agora - atras - 1, 12)
            filho = factory.create_character(g, 0, mother_id=w.id, father_id=h.id, birth=(ano, mes + 1))
            self.assertEqual(engine._can_conceive(g, w, h, 27), esperado)
            del g.characters[filho.id]
        w.pregnant_until = agora + 3
        self.assertFalse(engine._can_conceive(g, w, h, 27))

    def test_salvar_carregar_e_continuar(self):
        g1 = factory.new_game("t", 9)
        self._casais(g1, 30)
        engine.advance_months(g1, 20)
        grav = lambda g: sorted((c.id, c.pregnant_until, c.pregnancy_father_id) for c in g.characters.values())
        self.assertTrue(any(x[1] is not None for x in grav(g1)))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "g.db")
            persistence.save_game(g1, path)
            g2 = persistence.load_game(path)
        self.assertEqual(grav(g1), grav(g2))
        engine.advance_months(g1, 24)
        engine.advance_months(g2, 24)
        self.assertEqual(snapshot(g1), snapshot(g2))

    def test_save_v12_sem_colunas_de_gestacao(self):
        g = factory.new_game("t", 9)
        self._casais(g, 10)
        engine.advance_months(g, 6)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "v12.db")
            persistence.save_game(g, path)
            con = sqlite3.connect(path)
            con.execute("ALTER TABLE characters DROP COLUMN pregnant_until")
            con.execute("ALTER TABLE characters DROP COLUMN pregnancy_father_id")
            con.execute("UPDATE meta SET value='12' WHERE key='schema_version'")
            con.commit()
            con.close()
            g2 = persistence.load_game(path)
        self.assertEqual(len(g2.characters), len(g.characters))
        self.assertTrue(all(c.pregnant_until is None for c in g2.characters.values()))

    def test_ficha_mostra_gestacao(self):
        g = factory.new_game("t", 1)
        w, = self._casais(g, 1)
        engine._conceive(g, w, g.characters[w.spouse_id])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ui_cli.show_character(g, w)
        self.assertIn("Gestação: parto previsto em", buf.getvalue())


class NovidadesV013:
    """Mixin: liga inflação, impostos, pensão e licença (desligados por padrão no restante da suíte)."""
    def setUp(self):
        for mod, nome in ((macro, "ATIVO"), (economy, "IMPOSTOS"), (economy, "PENSAO"), (engine, "LICENCA")):
            p = mock.patch.object(mod, nome, True)
            p.start()
            self.addCleanup(p.stop)
        for nome, val in (("EDUCACAO", False), ("CIRCULO_SOCIAL", False), ("DIVORCIO_BASE", 0.0)):
            p = mock.patch.object(engine, nome, val)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(romance, "ATIVO", False)
        p.start()
        self.addCleanup(p.stop)

    def _adulto(self, g, idade=30, occ=None, informal=False, sex=None, rank=0, **kw):
        c = factory.create_character(g, idade, sex=sex)
        now = g.year * 12 + g.month
        c.occupation, c.job_start, c.seeking_since, c.retired = occ, (now - 36) if occ else None, None, False
        c.rank, c.rank_since, c.informal, c.workplace, c.experience = rank, now - 40, informal, None, 0
        c.income = c.wealth = 0.0
        c.health, c.in_school, c.in_college = 100, False, False
        for k, v in kw.items():
            setattr(c, k, v)
        return c


class TestMacro(NovidadesV013, unittest.TestCase):
    """v0.13.0: inflação, índice de preços, salário mínimo dinâmico."""

    def test_base_coerente_com_economia(self):
        self.assertEqual(macro.SALARIO_MINIMO_BASE, economy.SALARIO_MINIMO)
        g = factory.new_game("t", 1)
        self.assertEqual(macro.min_wage(g), economy.SALARIO_MINIMO)
        self.assertEqual(macro.price_level(g), 1.0)

    def test_inflacao_deterministica_e_na_faixa(self):
        g1, g2, g3 = (factory.new_game("t", s) for s in (7, 7, 8))
        anos = []
        for ano in range(2026, 2076):
            for g in (g1, g2, g3):
                g.year = ano
            r = macro.annual_rate(g1)
            self.assertEqual(r, macro.annual_rate(g2))
            self.assertTrue(macro.INFLACAO_MIN <= r <= macro.INFLACAO_MAX)
            anos.append((r, macro.annual_rate(g3)))
        self.assertTrue(any(a != b for a, b in anos))            # sementes diferentes → trajetórias diferentes
        self.assertGreater(len({a for a, _ in anos}), 10)         # varia de ano para ano
        media = sum(a for a, _ in anos) / len(anos)
        self.assertTrue(0.03 < media < 0.06)

    def test_precos_sobem_e_minimo_reajusta_so_em_janeiro(self):
        g = factory.new_game("t", 3)
        factory.create_character(g, 30)
        mins, precos = [], []
        for _ in range(36):
            engine.advance_months(g, 1)
            mins.append((g.year, g.month, macro.min_wage(g)))
            precos.append(macro.price_level(g))
        self.assertEqual(precos, sorted(precos))
        self.assertGreater(precos[-1], 1.08)
        for (y1, m1, w1), (y2, m2, w2) in zip(mins, mins[1:]):
            if m2 == 1:
                self.assertGreater(w2, w1)
            else:
                self.assertEqual(w2, w1)
        # reajuste de janeiro ≥ inflação acumulada desde o reajuste anterior
        jan = [w for (_, m, w) in mins if m == 1]
        self.assertGreater(jan[-1] / jan[-2], 1 + g.macro["inflation_prev"] - 0.0001)

    def test_salario_e_beneficios_escalam_com_o_minimo(self):
        g = factory.new_game("t", 1)
        c = self._adulto(g, occ="professor", rank=1)
        base = economy.monthly_salary(c)
        self.assertAlmostEqual(economy.monthly_salary(c, mw=3000.0), 2 * base, places=1)
        self.assertEqual(economy.pension(self._adulto(g, 62), mw=3000.0), 3000.0)
        self.assertAlmostEqual(economy.pension(c, mw=3000.0), 2 * economy.pension(c), places=1)
        c.job_start = g.year * 12 + g.month - 30
        v1, n = economy.unemployment_benefit(c, g.year * 12 + g.month)
        v2, _ = economy.unemployment_benefit(c, g.year * 12 + g.month, mw=3000.0)
        self.assertEqual(n, 5)
        self.assertAlmostEqual(v2, 2 * v1, places=1)
        self.assertEqual(economy.current_income(self._adulto(g, 70), 70, mw=3000.0), 3000.0)

    def test_custo_de_vida_segue_o_indice_de_precos(self):
        g = factory.new_game("t", 1)
        c = self._adulto(g, 30)
        h1 = economy.household_of(g, c)
        g.macro["price_level"] = 2.0
        h2 = economy.household_of(g, c)
        self.assertAlmostEqual(h2["cost"], 2 * h1["cost"])
        self.assertAlmostEqual(h1["cost"], economy.CUSTO_ADULTO)

    def test_auxilio_escala_com_o_minimo(self):
        g = factory.new_game("t", 1)
        mae = self._adulto(g, 30, occ="servicos_gerais", sex="F")
        mae.income = economy.SALARIO_MINIMO
        for _ in range(2):
            k = factory.create_character(g, 5)
            k.mother_id = mae.id
        a1 = economy.household_of(g, mae)["auxilio"]
        g.macro["min_wage"] = 3000.0
        mae.income = 3000.0
        a2 = economy.household_of(g, mae)["auxilio"]
        self.assertGreater(a1, 0)
        self.assertAlmostEqual(a2, 2 * a1)

    def test_patrimonio_rende_a_inflacao(self):
        g = factory.new_game("t", 1)
        c = self._adulto(g, 40)
        c.wealth = 100000.0
        c.income = 0.0
        w0 = c.wealth
        with mock.patch.object(economy, "build_households", return_value=[]):
            economy.apply_month(g)
        esperado = w0 * (1 + economy.RENDIMENTO_MENSAL + macro.monthly_rate(g))
        self.assertAlmostEqual(c.wealth, round(esperado, 2), places=1)
        self.assertGreater(macro.monthly_rate(g), 0)

    def test_dez_anos_poder_de_compra_do_minimo_razoavel(self):
        g = factory.new_game("t", 5)
        engine.advance_months(g, 120)
        r = macro.real_min_wage(g) / macro.SALARIO_MINIMO_BASE
        self.assertTrue(0.95 < r < 1.35, r)   # ganho real pequeno, sem explodir nem derreter
        self.assertTrue(1.3 < macro.price_level(g) < 2.2, macro.price_level(g))

    def test_interruptor_desligado_nao_muda_nada(self):
        with mock.patch.object(macro, "ATIVO", False):
            g = factory.new_game("t", 2)
            factory.create_character(g, 30)
            engine.advance_months(g, 30)
            self.assertEqual(macro.price_level(g), 1.0)
            self.assertEqual(macro.min_wage(g), economy.SALARIO_MINIMO)
            self.assertEqual(macro.annual_rate(g), 0.0)


class TestImpostosEEstado(NovidadesV013, unittest.TestCase):
    def test_imposto_progressivo_e_linear_no_minimo(self):
        mw = 1500.0
        self.assertEqual(economy.income_tax(0.0, mw), 0.0)
        self.assertAlmostEqual(economy.income_tax(mw, mw), 0.08 * mw)   # 1 mínimo: só previdência
        aliq = [economy.income_tax(x * mw, mw) / (x * mw) for x in (1, 3, 6, 12, 30)]
        self.assertEqual(aliq, sorted(aliq))
        self.assertLess(aliq[0], aliq[-1])
        self.assertAlmostEqual(economy.income_tax(8 * 3000.0, 3000.0), 2 * economy.income_tax(8 * 1500.0, 1500.0), places=1)
        self.assertLess(aliq[-1], 0.4)

    def test_informal_e_aposentado_nao_pagam(self):
        g = factory.new_game("t", 1)
        formal = self._adulto(g, occ="medico")
        inf = self._adulto(g, occ="medico", informal=True)
        apos = self._adulto(g, 70, occ="medico", retired=True)
        for c in (formal, inf, apos):
            c.income = economy.current_income(c, c.age_at(g.year, g.month), mw=1500.0)
        self.assertGreater(economy.household_of(g, formal)["imposto"], 0)
        self.assertEqual(economy.household_of(g, inf)["imposto"], 0)
        self.assertEqual(economy.household_of(g, apos)["imposto"], 0)

    def test_saldo_do_domicilio_desconta_imposto(self):
        g = factory.new_game("t", 1)
        c = self._adulto(g, occ="engenheiro")
        g.firms.clear()
        engine.advance_months(g, 1)
        w1 = c.wealth
        with mock.patch.object(economy, "IMPOSTOS", False):
            g2 = factory.new_game("t", 1)
            c2 = self._adulto(g2, occ="engenheiro")
            engine.advance_months(g2, 1)
        self.assertLess(w1, c2.wealth)

    def test_orcamento_do_estado_registra_receita_e_despesa(self):
        g = factory.new_game("t", 2)
        self._adulto(g, occ="engenheiro")
        self._adulto(g, 70, occ="professor", retired=True)
        engine.advance_months(g, 3)
        self.assertGreater(g.macro["rec"], 0)
        self.assertGreater(g.macro["desp"], 0)
        self.assertAlmostEqual(g.macro["treasury"], g.macro["rec"] - g.macro["desp"], places=2)
        engine.advance_months(g, 12)   # virou o ano: ano anterior fechado
        self.assertGreater(g.macro["rec_prev"], 0)
        self.assertGreater(g.macro["desp_prev"], 0)
        s = economy.summary(g)
        self.assertEqual(s["salario_minimo"], macro.min_wage(g))
        self.assertEqual(s["tesouro"], g.macro["treasury"])


class TestPensaoAlimenticia(NovidadesV013, unittest.TestCase):
    def _cena(self, n_filhos=1, renda_pai=6000.0):
        g = factory.new_game("t", 1)
        mae = self._adulto(g, 34, sex="F")
        pai = self._adulto(g, 36, sex="M", occ="tecnico_medio")
        pai.income = renda_pai
        mae.income = 1500.0
        filhos = []
        for _ in range(n_filhos):
            k = factory.create_character(g, 8, mother_id=mae.id, father_id=pai.id)
            k.guardian_id = mae.id
            filhos.append(k)
        return g, mae, pai, filhos

    def test_valor_por_numero_de_filhos(self):
        for n, taxa in ((1, 0.15), (2, 0.20), (3, 0.25), (6, 0.30)):
            g, mae, pai, _ = self._cena(n)
            fl = economy.alimony_flows(g)
            self.assertEqual(len(fl), 1)
            self.assertEqual(fl[0][:2], (pai.id, mae.id))
            self.assertAlmostEqual(fl[0][2], 6000.0 * taxa)

    def test_efeito_nos_domicilios(self):
        g, mae, pai, _ = self._cena(1)
        hm, hp = economy.household_of(g, mae), economy.household_of(g, pai)
        self.assertAlmostEqual(hp["pensao_paga"], 900.0)
        self.assertAlmostEqual(hm["pensao_recebida"], 900.0)
        with mock.patch.object(economy, "PENSAO", False):
            hm0, hp0 = economy.household_of(g, mae), economy.household_of(g, pai)
        self.assertAlmostEqual(hm["income"] - hm0["income"], 900.0)
        self.assertAlmostEqual(hp0["income"] - hp["income"], 900.0)
        self.assertEqual(hm0["pensao_recebida"], 0.0)

    def test_casos_sem_pensao(self):
        g, mae, pai, filhos = self._cena(1)
        pai.income = 0.0
        self.assertEqual(economy.alimony_flows(g), [])                  # pagador sem renda
        pai.income = 6000.0
        mae.alive = False
        self.assertEqual(economy.alimony_flows(g), [])                  # guardião morto
        mae.alive = True
        pai.spouse_id, mae.spouse_id = mae.id, pai.id
        self.assertEqual(economy.alimony_flows(g), [])                  # voltaram a viver juntos
        pai.spouse_id = mae.spouse_id = None
        filhos[0].guardian_id = None
        self.assertEqual(economy.alimony_flows(g), [])                  # sem guarda definida
        filhos[0].guardian_id = mae.id
        g.year += 11
        self.assertEqual(economy.alimony_flows(g), [])                  # filho maior de idade

    def test_divorcio_real_gera_pensao(self):
        g = factory.new_game("t", 11)
        r = factory.create_family(g, "Lima", 2)
        mae, pai = r["mother"], r["father"]
        for k in r["children"]:
            k.birth_year = g.year - 6
        pai.occupation, pai.job_start, pai.informal, pai.rank = "tecnico_medio", g.year * 12 + g.month - 24, False, 0
        pai.income = 4000.0
        engine._divorce(g, mae, pai)
        fl = economy.alimony_flows(g)
        guardioes = {k.guardian_id for k in r["children"]}
        self.assertEqual(len(guardioes), 1)
        if guardioes == {mae.id}:
            self.assertTrue(any(p == pai.id and q == mae.id for p, q, _ in fl))


class TestLicencaMaternidade(NovidadesV013, unittest.TestCase):
    def setUp(self):
        super().setUp()
        for nome, val in (("GEMEOS", False), ("GESTACAO", True)):
            p = mock.patch.object(engine, nome, val)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(engine, "TRABALHO", True)
        p.start()
        self.addCleanup(p.stop)

    def _gestante(self, g, informal=False, meses=1, occ="aux_administrativo"):
        pai = self._adulto(g, 30, sex="M")
        mae = self._adulto(g, 27, sex="F", occ=occ, informal=informal, spouse_id=pai.id)
        pai.spouse_id = mae.id
        now = g.year * 12 + g.month
        mae.pregnant_until, mae.pregnancy_father_id = now + meses, pai.id
        return mae, pai

    def test_formal_entra_em_licenca_com_vinculo_e_salario(self):
        achou = 0
        for seed in range(1, 40):
            g = factory.new_game("t", seed)
            mae, _ = self._gestante(g)
            engine.advance_months(g, 1)
            if not mae.alive or any(e.text.startswith("Deixou o emprego") for e in g.events_for(mae.id, "trabalho")):
                continue
            achou += 1
            now = g.year * 12 + g.month
            self.assertEqual(mae.leave_until, now + engine.LICENCA_MESES - 1)
            self.assertTrue(work.is_employed(mae))
            self.assertGreater(mae.income, 0)
            self.assertTrue(any("licença-maternidade" in e.text for e in g.events_for(mae.id, "trabalho")))
            if achou >= 3:
                break
        self.assertGreaterEqual(achou, 3)

    def test_formal_protegida_na_gestacao_e_na_licenca_informal_nao(self):
        with mock.patch.object(work, "separation_monthly", return_value=1.0), \
                mock.patch.object(work, "retirement_monthly", return_value=0.0), \
                mock.patch.object(work, "job_change_monthly", return_value=0.0):
            g = factory.new_game("t", 3)
            formal, _ = self._gestante(g, informal=False, meses=9)
            informal, _ = self._gestante(g, informal=True, meses=9)
            engine.advance_months(g, 2)
            self.assertTrue(work.is_employed(formal))
            self.assertFalse(work.is_employed(informal))
            # em licença (sem gestação): ainda protegida; depois do fim, é demitida
            formal.pregnant_until = formal.pregnancy_father_id = None
            now = g.year * 12 + g.month
            formal.leave_until = now + 2
            engine.advance_months(g, 2)
            self.assertTrue(work.is_employed(formal))
            engine.advance_months(g, 2)
            self.assertFalse(work.is_employed(formal))

    def test_sem_licenca_o_interruptor_restaura_o_comportamento_antigo(self):
        with mock.patch.object(engine, "LICENCA", False), \
                mock.patch.object(work, "separation_monthly", return_value=1.0), \
                mock.patch.object(work, "retirement_monthly", return_value=0.0):
            g = factory.new_game("t", 3)
            formal, _ = self._gestante(g, informal=False, meses=9)
            engine.advance_months(g, 2)
            self.assertFalse(work.is_employed(formal))
            self.assertIsNone(formal.leave_until)

    def test_mae_que_deixa_o_emprego_nao_procura_trabalho_no_afastamento(self):
        g = factory.new_game("t", 4)
        mae = self._adulto(g, 28, sex="F", leave_until=g.year * 12 + g.month + 5)
        with mock.patch.object(work, "hire_monthly", return_value=1.0):
            engine.advance_months(g, 3)
            self.assertIsNone(mae.seeking_since)
            self.assertFalse(work.is_employed(mae))
            engine.advance_months(g, 4)
            self.assertTrue(work.is_employed(mae))   # fim do afastamento: volta ao mercado e é contratada

    def test_taxas_de_saida_informal_maior_que_formal(self):
        res = {}
        for informal in (False, True):
            saiu = total = 0
            for seed in range(1, 121):
                g = factory.new_game("t", seed)
                mae, _ = self._gestante(g, informal=informal)
                engine.advance_months(g, 1)
                if not mae.alive:
                    continue
                total += 1
                saiu += any(e.text.startswith("Deixou o emprego") for e in g.events_for(mae.id, "trabalho"))
            res[informal] = saiu / total
        self.assertTrue(0.0 <= res[False] < 0.2, res)
        self.assertTrue(0.12 < res[True] < 0.40, res)
        self.assertGreater(res[True], res[False])

    def test_licenca_e_macro_persistem_e_continuacao_identica(self):
        import tempfile
        g = factory.new_game("t", 6)
        factory.create_family(g, "Lima", 1)
        for _ in range(30):
            factory.create_character(g, 28)
        engine.advance_months(g, 40)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.db")
            persistence.save_game(g, path)
            g2 = persistence.load_game(path)
        self.assertEqual(g.macro, g2.macro)
        self.assertEqual({i: c.leave_until for i, c in g.characters.items()},
                         {i: c.leave_until for i, c in g2.characters.items()})
        engine.advance_months(g, 36)
        engine.advance_months(g2, 36)
        self.assertEqual(snapshot(g), snapshot(g2))
        self.assertEqual(g.macro, g2.macro)

    def test_save_v13_carrega_sem_macro(self):
        import tempfile
        g = factory.new_game("t", 6)
        factory.create_family(g, "Lima", 1)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.db")
            persistence.save_game(g, path)
            con = sqlite3.connect(path)
            con.execute("DELETE FROM meta WHERE key='macro'")
            con.execute("UPDATE meta SET value='13' WHERE key='schema_version'")
            con.commit()
            con.close()
            g2 = persistence.load_game(path)
        self.assertEqual(g2.macro["price_level"], 1.0)
        self.assertEqual(macro.min_wage(g2), 1500.0)
        engine.advance_months(g2, 14)
        self.assertGreater(macro.price_level(g2), 1.0)


class TestIntegracaoV013(NovidadesV013, unittest.TestCase):
    """Tudo ligado: inflação + impostos + pensão + licença convivendo com trabalho, empresas, namoro e gestação."""

    def setUp(self):
        super().setUp()
        for mod, nome, val in ((engine, "EDUCACAO", True), (engine, "CIRCULO_SOCIAL", True), (engine, "DIVORCIO_BASE", 0.014),
                               (engine, "TRABALHO", True), (engine, "ECONOMIA", True), (engine, "GESTACAO", True),
                               (romance, "ATIVO", True)):
            p = mock.patch.object(mod, nome, val)
            p.start()
            self.addCleanup(p.stop)

    def _mundo(self, seed):
        g = factory.new_game("t", seed)
        for _ in range(12):
            factory.create_family(g, None, 2)
        for _ in range(40):
            factory.create_character(g, g.rng.randint(20, 55))
        return g

    def test_dez_anos_estaveis_e_determinismo(self):
        g1, g2 = self._mundo(21), self._mundo(21)
        engine.advance_months(g1, 120)
        engine.advance_months(g2, 120)
        self.assertEqual(snapshot(g1), snapshot(g2))
        s = economy.summary(g1)
        ativos = [c for c in g1.characters.values() if c.alive and 25 <= c.age_at(g1.year, g1.month) <= 54 and not c.in_school]
        emp = sum(1 for c in ativos if work.is_employed(c))
        self.assertTrue(0.70 < emp / len(ativos) < 0.97, emp / len(ativos))
        self.assertGreater(s["indice_precos"], 1.3)
        self.assertGreater(s["receita_estado_ano_anterior"], 0)
        self.assertGreater(s["despesa_estado_ano_anterior"], 0)
        self.assertTrue(all(c.wealth > -economy.DIVIDA_MAX * s["indice_precos"] - 1 for c in g1.characters.values()))
        self.assertTrue(all(c.income >= 0 for c in g1.characters.values()))

    def test_carregar_e_continuar_igual_a_nao_parar(self):
        import tempfile
        g = self._mundo(22)
        engine.advance_months(g, 50)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.db")
            persistence.save_game(g, path)
            g2 = persistence.load_game(path)
        engine.advance_months(g, 70)
        engine.advance_months(g2, 70)
        self.assertEqual(snapshot(g), snapshot(g2))

    def test_cli_mostra_macro_e_licenca(self):
        g = self._mundo(23)
        engine.advance_months(g, 14)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ui_cli.show_economy(g)
            ui_cli.show_finances(g, next(c for c in g.characters.values() if c.alive and c.age_at(g.year, g.month) >= 25))
        out = buf.getvalue()
        for trecho in ("Inflação do ano", "Salário mínimo", "Estado —", "Saldo (após impostos)", "reais correntes"):
            self.assertIn(trecho, out)


class TestCLI(unittest.TestCase):
    def rodar(self, saves, entrada):
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "main.py"), "--cli", "--saves-dir", saves],
            input=entrada, capture_output=True, text=True, cwd=ROOT, timeout=60,
        )

    def test_jogar_salvar_fechar_reabrir(self):
        with tempfile.TemporaryDirectory() as saves:
            # novo jogo -> família (2 filhos) -> avançar 1 mês, 6 meses, 1 ano -> salvar -> sair
            r1 = self.rodar(saves, "1\nTeste CLI\n123\n2\nSilva\n2\n6\n7\n8\n10\n0\n")
            self.assertEqual(r1.returncode, 0, r1.stderr)
            self.assertIn("Partida salva", r1.stdout)
            self.assertEqual(r1.stdout.count("Relatório"), 3)
            self.assertIn("agosto de 2027", r1.stdout)  # 1+6+12 = 19 meses a partir de jan/2026
            self.assertTrue(os.path.isfile(os.path.join(saves, "Teste_CLI.db")))
            # novo processo: carregar -> listar -> sair
            r2 = self.rodar(saves, "2\n1\n2\n0\n")
            self.assertEqual(r2.returncode, 0, r2.stderr)
            self.assertIn("carregada", r2.stdout)
            self.assertIn("Silva", r2.stdout)
            self.assertIn("agosto de 2027", r2.stdout)

    def test_ficha_mostra_trabalho_do_adulto(self):
        with tempfile.TemporaryDirectory() as saves:
            # novo jogo -> família -> avançar 1 ano -> trocar para o primeiro personagem (mãe) -> ver ficha
            r = self.rodar(saves, "1\nTeste\n77\n2\nSilva\n3\n8\n3\n1\n1\n0\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Trabalho: ", r.stdout)

    def test_financas_e_panorama_na_cli(self):
        with tempfile.TemporaryDirectory() as saves:
            # novo jogo -> família -> avançar 1 ano -> trocar para a mãe -> ficha -> finanças -> panorama
            r = self.rodar(saves, "1\nTeste\n77\n2\nSilva\n3\n8\n3\n1\n1\n12\n13\n0\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Renda: R$", r.stdout)
            self.assertIn("=== Finanças de", r.stdout)
            self.assertIn("Custo de vida", r.stdout)
            self.assertIn("Panorama econômico", r.stdout)
            self.assertIn("Gini", r.stdout)

    def test_eof_nao_quebra(self):
        with tempfile.TemporaryDirectory() as saves:
            r = self.rodar(saves, "")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
