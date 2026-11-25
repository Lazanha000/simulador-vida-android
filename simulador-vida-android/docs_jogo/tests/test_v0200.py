"""Testes abrangentes da atualização v0.20.0."""
import json
import os
import sqlite3
import tempfile
import unittest

import sim
from sim import (carreiras, decisions, economy, educacao_br, encontros, engine,
                 factory, firms, intelecto, livros, macro, mundo, panels,
                 persistence, psicologia, start, ui_web, views, vinculos, work)


def _jogo(idade=22, seed=42, riqueza=200000.0, sexo="F"):
    g = factory.new_game("v0200", seed)
    p = start.start_adult(g, idade, sexo, "Marina" if sexo == "F" else "Lucas", "Almeida")
    p.schooling_years = 12
    p.in_school = False
    for k in p.cognition:
        p.cognition[k] = 75
        p.cognition_potential[k] = 75
    p.personality["conscienciosidade"] = 75
    p.wealth = riqueza
    return g, p


class TestVersaoESchemaV0200(unittest.TestCase):
    def test_versao_e_schema(self):
        self.assertEqual(sim.__version__, "0.20.0")
        self.assertEqual(persistence.SCHEMA_VERSION, 19)
        self.assertIn("19", persistence.SUPPORTED_VERSIONS)
        self.assertIn("18", persistence.SUPPORTED_VERSIONS)


class TestPsicologiaHabitosMetasQIV0200(unittest.TestCase):
    def test_qi_opcional_valores_e_medos(self):
        g, p = _jogo(idade=20, seed=10)
        st = psicologia.dados(g, p.id)
        self.assertFalse(st["mostrar_qi"])
        self.assertTrue(2 <= len(st["valores"]) <= 3)
        self.assertEqual(len(st["medos"]), 2)
        self.assertTrue(all(v in psicologia.VALORES_POOL for v in st["valores"]))
        self.assertTrue(all(m in psicologia.MEDOS_POOL for m in st["medos"]))

        qi_medio = psicologia.qi_estimado(p)
        self.assertTrue(60 <= qi_medio <= 155)
        for k in p.cognition:
            p.cognition[k] = 95
        self.assertGreater(psicologia.qi_estimado(p), qi_medio)

        res = psicologia.toggle_qi(g)
        self.assertTrue(res["mostrar_qi"])
        self.assertTrue(psicologia.dados(g, p.id)["mostrar_qi"])
        res2 = psicologia.toggle_qi(g, False)
        self.assertFalse(res2["mostrar_qi"])

    def test_habitos_mensais_sem_consumir_rng(self):
        g, p = _jogo(idade=25, seed=17)
        p.health = 70.0
        p.personality["neuroticismo"] = 70
        p.personality["amabilidade"] = 60
        p.personality["extroversao"] = 60
        carreiras.filiar(g, "civico")

        for hid in ("exercicio", "leitura_diaria", "meditacao", "voluntariado"):
            r = psicologia.alternar_habito(g, hid)
            self.assertTrue(r["ativo"])

        # Ajusta mês para múltiplo de 12 para disparar os efeitos periódicos de meditação (%4) e voluntariado (%6)
        g.year, g.month = 2028, 12
        rng0 = g.rng.getstate()
        inf0 = g.politica[p.id]["influencia"]
        h0 = p.health
        n0 = p.personality["neuroticismo"]
        am0 = p.personality["amabilidade"]
        psicologia.apply_month(g)
        self.assertEqual(g.rng.getstate(), rng0)
        self.assertGreater(p.health, h0)
        self.assertLess(p.personality["neuroticismo"], n0)
        self.assertGreater(p.personality["amabilidade"], am0)
        self.assertGreater(g.politica[p.id]["influencia"], inf0)

        # Leitura diária amplia capacidade mensal de leitura em +120 páginas e reduz esquecimento
        g_sem, p_sem = _jogo(idade=25, seed=17)
        self.assertEqual(livros.capacidade_mes(g, p) - livros.capacidade_mes(g_sem, p_sem), 120)

    def test_metas_de_vida_limite_e_conclusao(self):
        g, p = _jogo(idade=24, seed=23, riqueza=1000.0)
        st = psicologia.dados(g, p.id)
        for m in list(st["metas_ativas"]):
            psicologia.definir_meta(g, m, adicionar=False)
        self.assertEqual(st["metas_ativas"], [])

        psicologia.definir_meta(g, "leitor_10", True)
        psicologia.definir_meta(g, "reserva_50k", True)
        psicologia.definir_meta(g, "poliglota", True)
        with self.assertRaises(ValueError):
            psicologia.definir_meta(g, "casa_propria", True)

        p.health = 80.0
        c0 = p.personality["conscienciosidade"]
        p.wealth = 60000.0
        concl = psicologia.verificar_metas(g, p)
        self.assertIn("reserva_50k", concl)
        self.assertIn("reserva_50k", st["metas_concluidas"])
        self.assertNotIn("reserva_50k", st["metas_ativas"])
        self.assertGreater(p.health, 80.0)
        self.assertEqual(p.personality["conscienciosidade"], min(99, c0 + 1))


class TestVinculosEEncontrosV0200(unittest.TestCase):
    def test_vinculos_multidimensionais_confronto_reconciliacao_e_rng(self):
        g = factory.new_game("vinc", 31)
        fam = start.start_newborn(g, "Costa", 1, "F", "Clara")
        p = fam["child"]
        # Envelhece artificialmente para interações adultas sem alterar parentesco
        p.birth_year -= 20
        mae = fam["mother"]
        amigo = factory.create_character(g, 22, "M", "Rafael", "Dias")
        g.add_friendship(p.id, amigo.id)

        rng0 = g.rng.getstate()
        st_mae = vinculos.estado(g, p.id, mae.id)
        self.assertGreaterEqual(st_mae["confianca"], 70)

        r_conv = vinculos.interagir(g, mae.id, "conversar")
        self.assertIn("afinidade", r_conv["estado"])
        with self.assertRaises(ValueError):
            vinculos.interagir(g, mae.id, "apoiar")  # limite de 1 interação/mês

        # Confrontar amigo repetidamente gera rivalidade (>=50) e remove amizade; 3º confronto -> inimigo (>=80)
        vinculos.interagir(g, amigo.id, "confrontar")
        g.month += 1
        vinculos.interagir(g, amigo.id, "confrontar")
        st_am = vinculos.estado(g, p.id, amigo.id)
        self.assertGreaterEqual(st_am["hostilidade"], 50)
        self.assertFalse(g.are_friends(p.id, amigo.id))
        g.month += 1
        vinculos.interagir(g, amigo.id, "confrontar")
        self.assertGreaterEqual(vinculos.estado(g, p.id, amigo.id)["hostilidade"], 80)
        prox = {x["id"]: x for x in vinculos.pessoas_proximas(g)}
        self.assertTrue(prox[amigo.id]["inimigo"])
        self.assertIn("Inimig", prox[amigo.id]["relacao"])

        # Reconciliar reduz hostilidade e histórico respeita teto de 8 itens
        for _ in range(7):
            g.month = (g.month % 12) + 1
            if g.month == 1:
                g.year += 1
            vinculos.registrar_evento(g, p.id, amigo.id, "Nota", afinidade=1)
        self.assertLessEqual(len(vinculos.estado(g, p.id, amigo.id)["historico"]), 8)

        g.month = (g.month % 12) + 1
        if g.month == 1:
            g.year += 1
        h_antes = vinculos.estado(g, p.id, amigo.id)["hostilidade"]
        vinculos.interagir(g, amigo.id, "reconciliar")
        self.assertLess(vinculos.estado(g, p.id, amigo.id)["hostilidade"], h_antes)
        self.assertEqual(g.rng.getstate(), rng0)

    def test_encontros_preferencia_afetiva_e_rng_intacto(self):
        g, p = _jogo(idade=25, seed=55, sexo="F")
        rng0 = g.rng.getstate()

        cands_op = encontros.candidatos(g)
        self.assertTrue(all(c["sexo"] == "M" for c in cands_op))

        encontros.definir_preferencia(g, "mesmo")
        cands_ms = encontros.candidatos(g)
        self.assertTrue(all(c["sexo"] == "F" for c in cands_ms))

        encontros.definir_preferencia(g, "todos")
        cands_td = encontros.candidatos(g)
        self.assertEqual({c["sexo"] for c in cands_td}, {"F", "M"})

        with self.assertRaises(ValueError):
            encontros.definir_preferencia(g, "invalida")
        self.assertEqual(g.rng.getstate(), rng0)


class TestIntelectoELivrosV0200(unittest.TestCase):
    def test_enciclopedia_idiomas_revisao_grupo_pesquisa_e_esquecimento(self):
        self.assertEqual(len(intelecto.ENCICLOPEDIA), 16)
        self.assertEqual(len(intelecto.SUBDISCIPLINAS_POR_ID), 48)
        self.assertEqual(len(intelecto.IDIOMAS), 6)

        g, p = _jogo(idade=24, seed=66, riqueza=50000.0)
        amigo = factory.create_character(g, 24, "M", "Bruno", "Lima")
        g.add_friendship(p.id, amigo.id)
        mundo.comprar_equipamento(g, "notebook")

        rng0 = g.rng.getstate()
        r_grp = intelecto.grupo_estudo(g, "economia")
        self.assertEqual(r_grp["area"], "Economia e Finanças")
        self.assertGreater(intelecto.dados(g, p.id)["conhecimentos"]["economia"], 0)
        self.assertGreater(len(vinculos.estado(g, p.id, amigo.id)["historico"]), 0)

        # Decaimento de retenção e revisão espaçada
        intelecto.apply_month(g)
        ret_apos = intelecto.dados(g, p.id)["retencao"]["economia"]
        self.assertLess(ret_apos, 100.0)
        self.assertGreaterEqual(ret_apos, 35.0)

        r_rev = intelecto.revisar(g, "economia")
        self.assertLess(r_rev["retencao_antes"], 100.0)
        self.assertEqual(intelecto.dados(g, p.id)["retencao"]["economia"], 100.0)

        # Idiomas + bônus salarial
        for _ in range(10):
            g.month = (g.month % 12) + 1
            if g.month == 1:
                g.year += 1
            res_id = intelecto.estudar_idioma(g, "ingles")
            if res_id["progresso"] >= 70.0:
                break
        self.assertGreaterEqual(intelecto.dados(g, p.id)["idiomas"]["ingles"], 70.0)
        self.assertEqual(intelecto.bonus_salarial_idiomas(g, p.id), 1.05)

        firms.ensure_world(g)
        work.start_job(g, p, "analista_sistemas", g.year * 12 + g.month)
        sal_base = economy.monthly_salary(p, economy._firm_of(g, p), macro.min_wage(g))
        economy.apply_month(g)
        self.assertGreater(p.income, sal_base)

        # Pesquisa e publicação
        r_pesq = intelecto.pesquisar_e_publicar(g, "dados_ia")
        self.assertEqual(r_pesq["total_pesquisas"], 1)
        self.assertGreater(intelecto.dados(g, p.id)["subdisciplinas"]["dados_ia"], 0)
        self.assertEqual(g.rng.getstate(), rng0)

    def test_205_livros_novos_generos_e_capacidade_biblioteca(self):
        self.assertEqual(len(livros.CATALOGO), 205)
        ids = [x[0] for x in livros.CATALOGO]
        self.assertEqual(len(ids), len(set(ids)))
        generos = {x[4] for x in livros.CATALOGO}
        for gen in ("matemática", "química", "engenharia", "tecnologia"):
            self.assertIn(gen, generos)
        for lid, tit, aut, ano, gen, niv in livros.CATALOGO:
            self.assertTrue(tit and aut)
            self.assertIn(gen, livros.GENERO_COGNICAO, lid)
            self.assertIn(gen, livros.GENERO_AREAS, lid)
            self.assertIn(niv, (1, 2, 3))
            self.assertGreater(livros.paginas_livro(lid), 0)

        g, p = _jogo(idade=25, seed=71, riqueza=50000.0)
        cap0 = livros.capacidade_mes(g, p)
        mundo.comprar_equipamento(g, "biblioteca")
        psicologia.alternar_habito(g, "leitura_diaria")
        self.assertEqual(livros.capacidade_mes(g, p), cap0 + 150 + 120)


class TestEducacaoTrabalhoECarreirasV0200(unittest.TestCase):
    def test_novas_ocupacoes_cursos_tecnicos_e_ocupacao_preferida(self):
        novas = {"psicologo", "economista", "pesquisador", "designer"}
        self.assertTrue(novas.issubset({o[0] for o in work.OCUPACOES}))
        self.assertTrue(novas.issubset(set(economy.SALARIO_BASE)))
        setor_occs = {k for s in firms.SETORES.values() for k in s}
        self.assertTrue(novas.issubset(setor_occs))

        self.assertEqual(len(educacao_br.CURSOS), 10)
        self.assertEqual(set(educacao_br.CURSO_TIPO), {c[0] for c in educacao_br.CURSOS})
        self.assertEqual(educacao_br.CURSO_TIPO["design"], "Tecnólogo")
        self.assertEqual(len(educacao_br.CURSOS_TECNICOS), 5)

        g, p = _jogo(idade=18, seed=81, riqueza=50000.0)
        r_tec = educacao_br.iniciar_tecnico(g, "tec_info", publica=True)
        self.assertTrue(r_tec["publica"])
        for _ in range(18):
            economy.apply_month(g)
        st_ed = educacao_br.dados(g, p.id)
        self.assertIsNone(st_ed["tecnico_atual"])
        self.assertIn("tec_info", st_ed["tecnicos_concluidos"])
        self.assertEqual(educacao_br.ocupacao_preferida(g, p.id), "tecnico_medio")
        self.assertAlmostEqual(educacao_br.bonus_salarial_pos(g, p.id), 1.04)

    def test_carreiras_meio_periodo_freela_expandir_movimento_e_lei(self):
        g, p = _jogo(idade=21, seed=91, riqueza=500000.0)
        work.clear_job(p)
        p.in_college = True

        # Meio período / estágio
        r_mp = carreiras.iniciar_meio_periodo(g, "Tecnologia")
        self.assertEqual(r_mp["salario_minimos"], 0.90)
        w0 = p.wealth
        economy.apply_month(g)
        self.assertGreater(p.wealth, w0)
        carreiras.sair_meio_periodo(g)
        self.assertIsNone(g.carreira_extra[p.id].get("meio_periodo"))

        # Freelancer (máx 2/mês) + notebook + extrato
        mundo.comprar_equipamento(g, "notebook")
        r_f1 = carreiras.fazer_freela(g, "ciencias")
        self.assertGreater(r_f1["valor"], 0)
        self.assertEqual(r_f1["restantes"], 1)
        carreiras.fazer_freela(g, "economia")
        with self.assertRaises(ValueError):
            carreiras.fazer_freela(g, "economia")
        self.assertTrue(any("freelancer" in x["desc"].lower() or "autônomo" in x["desc"].lower() for x in mundo.extrato(g, p.id)))

        # Empresa: abrir e expandir
        p.in_college = False
        emp = carreiras.abrir_empresa(g, "serviços", "micro")
        f = g.firms[emp["id"]]
        vagas0 = sum(f.slots.values())
        r_exp = carreiras.expandir_empresa(g)
        self.assertEqual(r_exp["porte"], "pequena")
        self.assertEqual(sum(f.slots.values()), vagas0 + 6)

        # Movimento social e projeto de lei (exige mandato)
        with self.assertRaises(ValueError):
            carreiras.propor_projeto(g, "educacao")
        r_mov = carreiras.participar_movimento(g, "estudantil")
        self.assertGreater(r_mov["influencia"], 0)
        carreiras.filiar(g, "verde")
        g.politica[p.id]["influencia"] = 95.0
        el = carreiras.concorrer(g, "vereador")
        self.assertTrue(el["eleito"])
        r_lei = carreiras.propor_projeto(g, "educacao")
        self.assertIn("bolsas", r_lei["titulo"].lower())
        self.assertTrue(any(n["tipo"] == "simulada" and "Projeto aprovado" in n["titulo"] for n in g.noticias))


class TestMundoEquipamentosPlanoSaudeCensoV0200(unittest.TestCase):
    def test_equipamentos_plano_saude_extrato_e_censo_2030(self):
        g, p = _jogo(idade=30, seed=101, riqueza=100000.0)
        mundo.comprar_equipamento(g, "kit_esportivo")
        self.assertTrue(mundo.tem_equipamento(g, p.id, "kit_esportivo"))
        ps = mundo.alternar_plano_saude(g, True)
        self.assertTrue(ps["ativo"])

        p.health = 70.0
        w0 = p.wealth
        mundo.apply_month(g)
        psicologia.apply_month(g)
        self.assertGreater(p.health, 70.5)
        self.assertLess(p.wealth, w0)  # mensalidade do plano cobrada

        rv = mundo.vender_equipamento(g, "kit_esportivo")
        self.assertGreater(rv["valor"], 0)
        self.assertFalse(mundo.tem_equipamento(g, p.id, "kit_esportivo"))
        self.assertTrue(len(mundo.extrato(g, p.id)) >= 2)

        # Censo demográfico decenal em 08/2030
        g.year, g.month = 2030, 8
        mundo.registrar_noticias_mes(g)
        self.assertTrue(any(n["ano"] == 2030 and n["mes"] == 8 and n["tipo"] == "real" and "Censo" in n["titulo"] for n in g.noticias))


class TestDecisoesPersistenciaEPaineisV0200(unittest.TestCase):
    def test_12_novos_eventos_decisao(self):
        novos_ids = [
            "curso_tecnico_oficina", "ic_congresso", "freela_prazo", "colega_rival_trabalho",
            "socio_empresa", "crise_fluxo_caixa", "jantar_familia_tenso", "conflito_vizinho",
            "plano_saude_escolha", "orcamento_investir", "convite_voluntariado", "rotina_digital",
        ]
        g, p = _jogo(idade=28, seed=111, riqueza=80000.0)
        for eid in novos_ids:
            self.assertIn(eid, decisions.EVENTOS_POR_ID)
            ev = decisions.EVENTOS_POR_ID[eid]
            self.assertEqual(len(ev["ops"]), 3)
            g.decisions["pending"] = {"id": eid, "ano": g.year, "mes": g.month, "pid": p.id}
            res = decisions.decidir(g, 0)
            self.assertEqual(res["escolhida"], 0)

    def test_persistencia_v19_e_retrocompatibilidade_v18(self):
        g, p = _jogo(idade=25, seed=121, riqueza=80000.0)
        psicologia.alternar_habito(g, "exercicio")
        psicologia.toggle_qi(g, True)
        encontros.definir_preferencia(g, "todos")
        mundo.comprar_equipamento(g, "notebook")
        mundo.alternar_plano_saude(g, True)
        intelecto.estudar_idioma(g, "espanhol")
        intelecto.pesquisar_e_publicar(g, "algoritmos" if "algoritmos" in intelecto.SUBDISCIPLINAS_POR_ID else "programacao")
        educacao_br.iniciar_tecnico(g, "tec_adm", publica=False)
        work.clear_job(p)
        carreiras.iniciar_meio_periodo(g, "Finanças")
        carreiras.fazer_freela(g, "economia")

        amigo = factory.create_character(g, 25, "M", "Caio", "Nunes")
        g.add_friendship(p.id, amigo.id)
        vinculos.interagir(g, amigo.id, "apoiar")

        with tempfile.TemporaryDirectory() as td:
            arq = os.path.join(td, "v19.db")
            persistence.save_game(g, arq)
            g2 = persistence.load_game(arq)

            self.assertEqual(g2.psicologia, g.psicologia)
            self.assertEqual(g2.vinculos, g.vinculos)
            self.assertEqual(g2.financas_log, g.financas_log)
            self.assertEqual(g2.educacao_br, g.educacao_br)
            self.assertEqual(g2.intelecto, g.intelecto)
            self.assertEqual(g2.patrimonio, g.patrimonio)

            # Simula save v18 removendo chaves exclusivas da v19 e ajustando schema_version='18'
            arq18 = os.path.join(td, "v18.db")
            persistence.save_game(g, arq18)
            con = sqlite3.connect(arq18)
            with con:
                con.execute("UPDATE meta SET value='18' WHERE key='schema_version'")
                con.execute("DELETE FROM meta WHERE key IN ('psicologia', 'vinculos', 'financas_log')")
            con.close()
            g18 = persistence.load_game(arq18)
            self.assertEqual(g18.psicologia, {})
            self.assertEqual(g18.vinculos, {})
            self.assertEqual(g18.financas_log, {})

    def test_api_http_rotas_e_paineis_v0200(self):
        with tempfile.TemporaryDirectory() as td:
            app = ui_web.App(td)
            est = app.api("POST", "novo", {}, {"nome": "HTTP20", "modo": "avulso", "idade": 24, "semente": 7})
            self.assertIn("psicologia", est)
            self.assertIn("vinculos", est)
            p = views.player_of(app.game)
            work.clear_job(p)
            p.wealth = 500000.0
            p.schooling_years = 12
            p.in_school = False
            for k in p.cognition:
                p.cognition[k] = p.cognition_potential[k] = 80
            amigo = factory.create_character(app.game, 24, "M", "Igor", "Melo")
            app.game.add_friendship(p.id, amigo.id)

            chamadas = [
                ("psicologia/habito", {"id": "exercicio"}),
                ("psicologia/qi", {"mostrar": True}),
                ("psicologia/meta", {"id": "leitor_25", "adicionar": True}),
                ("vinculos/interagir", {"id": amigo.id, "acao": "conversar"}),
                ("encontros/preferencia", {"pref": "todos"}),
                ("mundo/comprar_equipamento", {"id": "notebook"}),
                ("mundo/plano_saude", {"ativar": True}),
                ("intelecto/estudar", {"modo": "tema", "area": "economia"}),
                ("intelecto/revisar", {"area": "economia"}),
                ("intelecto/grupo", {"area": "ciencias"}),
                ("intelecto/idioma", {"idioma": "ingles"}),
                ("intelecto/pesquisar", {"sub": "programacao"}),
                ("educacao/tecnico", {"id": "tec_info", "publica": True}),
                ("carreiras/meio_periodo", {"area": "Dados"}),
                ("carreiras/freela", {"area": "economia"}),
                ("carreiras/sair_meio_periodo", {}),
                ("carreiras/abrir_empresa", {"setor": "comércio", "porte": "micro"}),
                ("carreiras/expandir_empresa", {}),
                ("politica/movimento", {"id": "ambiental"}),
                ("mundo/vender_equipamento", {"id": "notebook"}),
            ]
            for rota, body in chamadas:
                res = app.api("POST", rota, {}, body)
                self.assertIn("estado", res, rota)

            # Mandato + projeto de lei
            app.api("POST", "politica/filiar", {}, {"partido": "verde"})
            app.game.politica[p.id]["influencia"] = 95.0
            app.api("POST", "politica/concorrer", {}, {"cargo": "vereador"})
            res_lei = app.api("POST", "politica/projeto", {}, {"pauta": "educacao"})
            self.assertIn("titulo", res_lei["resultado"])

            # Painéis com jogador e sem jogador
            for nome in panels.PAINEIS:
                pd = app.api("GET", f"painel/{nome}", {}, {})
                json.dumps(pd, ensure_ascii=False)
            cfg = app.api("GET", "painel/config", {}, {})
            acoes_cfg = [a["acao"] for b in cfg["blocos"] if b["t"] == "acoes" for a in b["itens"]]
            self.assertIn("qi", acoes_cfg)
            self.assertIn("pref_afetiva", acoes_cfg)

            app.game.player_id = None
            cfg_sem = app.api("GET", "painel/config", {}, {})
            acoes_sem = [a["acao"] for b in cfg_sem["blocos"] if b["t"] == "acoes" for a in b["itens"]]
            self.assertNotIn("qi", acoes_sem)
            self.assertNotIn("pref_afetiva", acoes_sem)


if __name__ == "__main__":
    unittest.main()
