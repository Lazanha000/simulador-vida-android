"""Testes da v0.14.0: avatares, indicadores, modos de início, visões/painéis, servidor HTTP e consistência da arte."""
import json
import os
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from sim import avatar_art, decisions, engine, factory, indicators, panels, persistence, start, ui_web, views
from sim.models import MESES

_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = _R if os.path.isdir(os.path.join(_R, "web")) else os.path.join(os.path.dirname(_R), "app", "src", "main", "assets")
ARTE = os.path.join(RAIZ, "web", "arte")


def _familia(seed=11, anos=0):
    g = factory.new_game("t", seed)
    start.start_newborn(g, "Lima", 2)
    for _ in range(anos):
        engine.advance_months(g, 12)
    return g


class TestAvatares(unittest.TestCase):
    def test_identico_ao_kit(self):
        n = 0
        for e in ("bebe", "crianca", "adolescente", "jovem", "adulto", "idoso"):
            for sx in "fm":
                hair = 1 if sx == "f" else 0
                esperado = open(f"{ARTE}/avatares/avatar_{e}_{sx}.svg", encoding="utf-8").read()
                self.assertEqual(avatar_art.svg(e, sx, 1, hair), esperado)
                for si in range(5):
                    esperado = open(f"{ARTE}/avatares/variantes/avatar_{e}_{sx}_pele{si + 1}.svg", encoding="utf-8").read()
                    self.assertEqual(avatar_art.svg(e, sx, si, hair), esperado)
                    n += 1
        for sx in "fm":
            esperado = open(f"{ARTE}/avatares/avatar_falecido_{sx}.svg", encoding="utf-8").read()
            self.assertEqual(avatar_art.svg("adulto", sx, 1, 1 if sx == "f" else 0, True), esperado)
        self.assertEqual(n, 60)

    def test_etapas_por_idade(self):
        casos = {0: "bebe", 2: "bebe", 3: "crianca", 11: "crianca", 12: "adolescente", 17: "adolescente", 18: "jovem",
                 34: "jovem", 35: "adulto", 59: "adulto", 60: "idoso", 110: "idoso"}
        for idade, et in casos.items():
            self.assertEqual(avatar_art.stage_for_age(idade), et)

    def test_aparencia_deterministica_e_herdada(self):
        g = _familia(anos=0)
        for c in g.characters.values():
            p, h = avatar_art.look(g, c)
            self.assertTrue(0 <= p <= 4 and 0 <= h <= 4)
        g2 = _familia(anos=0)
        self.assertEqual({c.id: avatar_art.look(g, c) for c in g.characters.values()},
                         {c.id: avatar_art.look(g2, c) for c in g2.characters.values()})
        # filhos ficam a no máximo 1 ponto da média dos pais
        for c in g.characters.values():
            pais = g.parents_of(c)
            if pais:
                media = sum(avatar_art.look(g, p)[0] for p in pais) / len(pais)
                self.assertLessEqual(abs(avatar_art.look(g, c)[0] - media), 1.1)

    def test_parametros_invalidos(self):
        with self.assertRaises(ValueError):
            avatar_art.svg("alien", "f", 1, 1)
        with self.assertRaises(ValueError):
            avatar_art.svg("adulto", "x", 1, 1)
        with self.assertRaises(ValueError):
            avatar_art.svg("adulto", "f", 9, 1)


class TestIndicadores(unittest.TestCase):
    def test_limites_e_monotonia(self):
        g = _familia(anos=8)
        for c in g.characters.values():
            if c.alive:
                for k, v in indicators.bars(g, c).items():
                    self.assertTrue(0 <= v <= 100, (k, v))
        p = views.player_of(g)
        base = indicators.wellbeing(g, p)
        p.health = max(0.0, p.health - 40)
        self.assertLess(indicators.wellbeing(g, p), base)   # menos saúde, menos bem-estar

    def test_patrimonio_escala_log(self):
        g = _familia()
        p = views.player_of(g)
        p.wealth = -500
        self.assertEqual(indicators.wealth_score(g, p), 0.0)
        p.wealth = 10 * 1500
        a = indicators.wealth_score(g, p)
        p.wealth = 100 * 1500
        self.assertGreater(indicators.wealth_score(g, p), a)

    def test_pesos_somam_um(self):
        self.assertAlmostEqual(indicators.PESO_SAUDE + indicators.PESO_SOCIAL + indicators.PESO_FINANCAS + indicators.PESO_OCUPACAO, 1.0)


class TestInicio(unittest.TestCase):
    def test_nascer(self):
        g = factory.new_game("n", 5)
        r = start.start_newborn(g, "Souza", 3, "F", "Helena")
        c = r["child"]
        self.assertEqual((c.full_name, c.sex, c.age_at(g.year, g.month)), ("Helena Souza", "F", 0))
        self.assertEqual(g.player_id, c.id)
        self.assertEqual(c.mother_id, r["mother"].id)
        self.assertTrue(18 <= r["mother"].age_at(g.year, g.month) - max(s.age_at(g.year, g.month) for s in r["siblings"]) if r["siblings"] else True)
        self.assertTrue(engine.has_active_spouse(g, r["mother"]))
        self.assertTrue(any(e.category == "nascimento_filho" for e in g.events_for(r["mother"].id)))
        with self.assertRaises(ValueError):
            start.start_newborn(factory.new_game("x", 1), siblings=9)

    def test_nascer_e_viver(self):
        g = factory.new_game("n", 8)
        start.start_newborn(g, None, 1)
        engine.advance_months(g, 12 * 20)
        self.assertGreaterEqual(len(g.characters), 4)

    def test_avulso_e_familia(self):
        g = factory.new_game("a", 3)
        c = start.start_adult(g, 40, "M", "Pedro", "Rocha")
        self.assertEqual((g.player_id, c.age_at(g.year, g.month)), (c.id, 40))
        g2 = factory.new_game("b", 3)
        r = start.start_family(g2, "Dias", 3)
        self.assertEqual(len(r["children"]), 3)
        self.assertEqual(g2.player_id, r["children"][0].id)


class TestVisoes(unittest.TestCase):
    def test_avancar_equivale_ao_motor(self):
        a, b = _familia(3), _familia(3)
        ant = decisions.ATIVO
        decisions.ATIVO = False
        try:
            views.avancar(a, 12)
        finally:
            decisions.ATIVO = ant
        engine.advance_months(b, 12)
        self.assertEqual([(e.year, e.month, e.category, e.text) for e in a.biography],
                         [(e.year, e.month, e.category, e.text) for e in b.biography])
        self.assertEqual({c.id: (c.health, c.wealth) for c in a.characters.values()},
                         {c.id: (c.health, c.wealth) for c in b.characters.values()})
        self.assertEqual(a.rng.getstate(), b.rng.getstate())

    def test_relatorio_e_ano_novo(self):
        ant = decisions.ATIVO
        decisions.ATIVO = False
        try:
            g = _familia(2)
            r = views.avancar(g, 1)            # janeiro -> fevereiro: sem virada
            self.assertIsNone(r["ano_novo"])
            for _ in range(11):
                r = views.avancar(g, 1)
            self.assertIsNotNone(r["ano_novo"])  # o 12º mês chega em janeiro
            self.assertEqual(r["ano_novo"]["ano"], g.year)
            r6 = views.avancar(_familia(2), 6)
            self.assertIsNone(r6["ano_novo"])   # jan -> jul
        finally:
            decisions.ATIVO = ant

    def test_para_na_morte_do_jogador(self):
        g = _familia(4)
        pid = g.player_id
        original = engine.mortality_monthly
        engine.mortality_monthly = lambda age, health: 1.0 if age == g.characters[pid].age_at(g.year, g.month) else 0.0
        try:
            r = views.avancar(g, 12)
        finally:
            engine.mortality_monthly = original
        self.assertTrue(r["jogador_morreu"])
        self.assertLess(r["meses"], 12)
        self.assertFalse(g.characters[pid].alive)
        self.assertTrue(views.estado(g)["luto"])
        self.assertTrue(any(e["cat"] == "morte" for e in r["meus"]))

    def test_herdeiros(self):
        g = _familia(6)
        pais = views.herdeiros_possiveis(g, views.player_of(g))
        self.assertTrue(all(h["vivo"] for h in pais))
        self.assertTrue(any(h["rel"] in ("Mãe", "Pai") for h in pais))

    def test_todas_categorias_tem_rotulo_e_arte(self):
        cats = set()
        for seed in (1, 2, 3):
            g = factory.new_game("c", seed)
            for _ in range(2):
                factory.create_family(g, None, 4)
            engine.advance_months(g, 12 * 30)
            for e in g.biography:
                cats.add(e.category)
                icone, tom = views.classificar(e.category, e.text)
                self.assertIn(tom, ("bom", "ruim", "neutro"))
                self.assertTrue(os.path.isfile(os.path.join(ARTE, icone)), icone)
        self.assertLessEqual(cats, set(views.CATEGORIAS), cats - set(views.CATEGORIAS))
        self.assertGreaterEqual(len(cats), 15)

    def test_feed_paginacao(self):
        g = _familia(anos=10)
        p = views.player_of(g)
        f = views.feed(g, p, limite=10)
        self.assertEqual(len(f["itens"]), 10)
        self.assertTrue(f["mais"])
        ant = views.feed(g, p, limite=10, antes=f["itens"][0]["seq"])
        self.assertLess(ant["itens"][-1]["seq"], f["itens"][0]["seq"])

    def test_todos_os_paineis_serializam(self):
        g = _familia(anos=16)
        for p in g.characters.values():
            if p.alive:
                g.player_id = p.id
                for nome in panels.PAINEIS:
                    json.dumps(panels.painel(g, nome, {}, {"autosave": True}), ensure_ascii=False)
        g.player_id = None
        for nome in panels.SEM_PERSONAGEM:
            panels.painel(g, nome, {}, {})
        with self.assertRaises(ValueError):
            panels.painel(g, "escola", {}, {})

    def test_biografia_filtros(self):
        g = _familia(anos=12)
        r = panels.painel(g, "biografia", {"cat": "aniversario", "de": "2030", "ate": "2032"})
        itens = r["blocos"][1]["itens"]
        self.assertTrue(itens and all(i["cat"] == "aniversario" and 2030 <= i["ano"] <= 2032 for i in itens))
        with self.assertRaises(ValueError):
            panels.painel(g, "biografia", {"cat": "xx"})
        todos = panels.painel(g, "biografia", {"todos": "1"})["blocos"][1]["itens"]
        self.assertTrue(all(i["cat"] not in views._CAT_PRIVADAS or i.get("quem") for i in todos))


class TestArte(unittest.TestCase):
    def test_referencias_existem(self):
        faltando = []
        for sub in ("css/app.css", "js/app.js", "js/panels.js", "js/ui.js", "index.html", "manifest.webmanifest"):
            txt = open(os.path.join(RAIZ, "web", sub), encoding="utf-8").read()
            for ref in re.findall(r"arte/[A-Za-z0-9_/\-.]+\.svg", txt):
                if not os.path.isfile(os.path.join(RAIZ, "web", ref)):
                    faltando.append((sub, ref))
        self.assertEqual(faltando, [])

    def test_icones_do_menu_e_eventos_do_kit_usados(self):
        js = open(os.path.join(RAIZ, "web/js/panels.js"), encoding="utf-8").read()
        for _id in re.findall(r"\['([a-z]+)', '[^']+'\]", js.split("const MENU")[1].split("];")[0]):
            self.assertTrue(os.path.isfile(f"{ARTE}/icones/icone_{_id}.svg"), _id)
        usados = set()
        for cat, textos in {"nascimento": ["x"], "morte": ["x"], "casamento": ["x"], "divorcio": ["x"], "namoro": ["x"],
                            "gravidez": ["x"], "gemeos": ["x"], "escola": ["Começou o ensino fundamental.", "Concluiu o ensino médio."],
                            "trabalho": ["Conseguiu um emprego", "Foi promovido(a)", "Perdeu o emprego", "Aposentou-se"],
                            "amizade": ["x"], "amizade_fim": ["x"], "heranca": ["x"], "guarda": ["x"]}.items():
            for t in textos:
                usados.add(views.classificar(cat, t)[0])
        usados |= {panels.ICONE_EVENTO_CLIMA, panels.ICONE_EVENTO_INFLACAO}
        todos = {f"eventos/{f}" for f in os.listdir(f"{ARTE}/eventos")}
        self.assertEqual(todos - usados, set())   # cada miniatura de evento do kit tem uso no jogo


class TestHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.srv, cls.app = ui_web.criar_servidor(cls.dir, porta=0)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def call(self, metodo, rota, corpo=None, cab=True, host=None):
        req = urllib.request.Request(self.base + rota, method=metodo,
                                     data=json.dumps(corpo).encode() if corpo is not None else None)
        if cab:
            req.add_header("X-Sim", "1")
        if host:
            req.add_header("Host", host)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def js(self, *a, **k):
        st, corpo, _ = self.call(*a, **k)
        return st, json.loads(corpo)

    def test_fluxo_completo(self):
        self.call("POST", "/api/fechar", {})
        self.assertEqual(self.js("GET", "/api/estado")[1], {"tem_jogo": False})
        self.assertEqual(self.js("GET", "/api/painel/escola")[0], 409)
        st, est = self.js("POST", "/api/novo", {"nome": "Fluxo HTTP", "modo": "nascer", "irmaos": 1, "sobrenome": "Reis", "semente": 77})
        self.assertEqual(st, 200)
        self.assertTrue(est["tem_jogo"] and est["jogador"]["nome"].endswith("Reis"))
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "Fluxo_HTTP.db")))
        self.assertEqual(self.js("POST", "/api/novo", {"nome": "Fluxo HTTP"})[0], 409)   # já existe
        ant = decisions.ATIVO
        decisions.ATIVO = False
        try:
            st, rel = self.js("POST", "/api/avancar", {"meses": 12})
        finally:
            decisions.ATIVO = ant
        self.assertEqual((st, rel["meses"], rel["salvo"]), (200, 12, True))
        self.assertEqual(self.js("POST", "/api/avancar", {"meses": 5})[0], 400)
        data = rel["estado"]["partida"]["data"]
        # salvar/carregar preserva o estado
        self.js("POST", "/api/fechar", {})
        st, est2 = self.js("POST", "/api/carregar", {"arquivo": "Fluxo_HTTP.db"})
        self.assertEqual((st, est2["partida"]["data"]), (200, data))
        st, s = self.js("GET", "/api/saves")
        self.assertEqual(s["ultimo"]["arquivo"], "Fluxo_HTTP.db")
        self.assertEqual(s["saves"][0]["jogador"].count("anos"), 1)
        st, diario = self.js("GET", "/api/diario?limite=10")
        self.assertEqual(st, 200)
        self.assertTrue(diario["itens"])
        for nome in panels.PAINEIS:
            self.assertEqual(self.js("GET", f"/api/painel/{nome}")[0], 200, nome)
        self.assertEqual(self.js("GET", "/api/painel/inexistente")[0], 404)
        self.assertEqual(self.js("GET", "/api/painel/ficha?id=99999")[0], 400)

    def test_criar_e_trocar(self):
        self.js("POST", "/api/novo", {"nome": "Criar", "modo": "avulso", "idade": 30, "sobrenome": "Paz", "sobrescrever": True})
        st, r = self.js("POST", "/api/criar/personagem", {"idade": 5, "sexo": "F", "nome": "Lia"})
        self.assertEqual((st, r["criado"]["nome"].startswith("Lia")), (200, True))
        st, r = self.js("POST", "/api/criar/familia", {"filhos": 2, "sobrenome": "Neves"})
        self.assertEqual((st, r["membros"]), (200, 4))
        self.assertEqual(self.js("POST", "/api/criar/personagem", {"idade": 500})[0], 400)
        st, est = self.js("POST", "/api/jogador", {"id": 2})
        self.assertEqual(est["jogador"]["id"], 2)
        self.assertEqual(self.js("POST", "/api/jogador", {"id": 9999})[0], 404)

    def test_seguranca(self):
        self.assertEqual(self.call("POST", "/api/fechar", {}, cab=False)[0], 403)            # sem X-Sim
        self.assertEqual(self.call("GET", "/api/estado", host="evil.example.com")[0], 403)   # DNS rebinding
        for rota in ("/../main.py", "/%2e%2e/main.py", "/..%2fsim/engine.py", "/js/../../main.py"):
            self.assertEqual(self.call("GET", rota)[0], 404, rota)
        self.assertEqual(self.js("POST", "/api/carregar", {"arquivo": "../x.db"})[0], 400)
        self.assertEqual(self.js("POST", "/api/carregar", {"arquivo": "inexistente.db"})[0], 404)

    def test_estaticos_e_avatar(self):
        st, corpo, cab = self.call("GET", "/")
        self.assertEqual(st, 200)
        self.assertIn(b"Simulador de Vida", corpo)
        self.assertEqual(self.call("GET", "/js/app.js")[2]["Content-Type"].split(";")[0], "text/javascript")
        self.assertEqual(self.call("GET", "/arte/ui/selo_1mes.svg")[2]["Content-Type"], "image/svg+xml")
        st, corpo, cab = self.call("GET", "/avatar/adulto_f_2_1.svg")
        self.assertEqual(st, 200)
        self.assertEqual(corpo.decode(), avatar_art.svg("adulto", "f", 2, 1))
        self.assertEqual(self.call("GET", "/avatar/adulto_f_9_1.svg")[0], 404)
        self.assertEqual(self.call("GET", "/avatar/morto_f_1_1.svg")[0], 404)
        self.assertEqual(self.call("GET", "/avatar/idoso_m_1_0_d.svg")[0], 200)

    def test_save_antigo_continua_legivel(self):
        g = _familia(3)
        persistence.save_game(g, os.path.join(self.dir, "Antigo.db"))
        st, s = self.js("GET", "/api/saves")
        self.assertTrue(any(x["arquivo"] == "Antigo.db" and x["legivel"] for x in s["saves"]))
        self.assertIn(MESES[g.month - 1], next(x for x in s["saves"] if x["arquivo"] == "Antigo.db")["data"])


if __name__ == "__main__":
    unittest.main()
