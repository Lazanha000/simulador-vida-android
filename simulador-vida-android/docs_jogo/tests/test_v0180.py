"""v0.18.0: leitura por páginas e abas lidos/não lidos, fim da trava de compreensão verbal,
ações de estudar/redação/ensaios/artigos/filmes, eventos do nascimento à velhice e coerência geográfica."""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from sim import (carreiras, decisions, educacao_br, engine, factory, intelecto,
                 livros, mundo, persistence, start, ui_web, views)


def _jogo(idade=18, seed=21, riqueza=50000.0):
    g = factory.new_game("v0180", seed)
    p = start.start_adult(g, idade, "F", "Luiza", "Mendes")
    p.wealth = riqueza
    return g, p


class TestLeituraEIntelecto(unittest.TestCase):
    def test_compreensao_verbal_nao_trava_no_potencial_de_nascimento(self):
        g, p = _jogo(idade=16, seed=9)
        p.cognition["compreensao_verbal"] = 25
        p.cognition_potential["compreensao_verbal"] = 25
        # Deve conseguir avançar compreensão verbal e potencial lendo livros nível 1/2, escrevendo redação e estudando
        livros.ler(g, "pequeno_principe")
        livros.ler(g, "alienista")
        intelecto.escrever_ensaio(g, "desigualdade", "redacao")
        intelecto.ler_artigo(g, "linguagem")
        intelecto.estudar(g, "enem")
        self.assertGreater(p.cognition["compreensao_verbal"], 28)
        self.assertEqual(p.cognition_potential["compreensao_verbal"], p.cognition["compreensao_verbal"])

        # Avançar até além do mínimo de nível 3 (VERBAL_MIN[3] = 38) e desbloquear Dom Casmurro
        for m in range(1, 10):
            g.month = (g.month % 12) + 1
            if g.month == 1:
                g.year += 1
            if p.cognition["compreensao_verbal"] >= livros.VERBAL_MIN[3]:
                break
            intelecto.escrever_ensaio(g, "democracia", "redacao")
            intelecto.ler_artigo(g, "linguagem")
        self.assertGreaterEqual(p.cognition["compreensao_verbal"], livros.VERBAL_MIN[3])
        r = livros.ler(g, "dom_casmurro")
        self.assertTrue(r["concluido"])

    def test_aniversario_nao_apaga_ganhos_intelectuais_em_menores(self):
        g = factory.new_game("kid", 14)
        p = start.start_adult(g, 8, "M", "Pedro", "Costa")
        antes = p.cognition["compreensao_verbal"]
        p.cognition["compreensao_verbal"] = antes + 12
        p.cognition_potential["compreensao_verbal"] = max(p.cognition_potential["compreensao_verbal"], antes + 12)
        engine.advance_months(g, 12)  # faz aniversário de 9 anos
        self.assertGreaterEqual(p.cognition["compreensao_verbal"], antes + 12)

    def test_multiplos_livros_paginas_progresso_abas_e_conhecimentos(self):
        g, p = _jogo(idade=25)
        p.cognition["compreensao_verbal"] = 70
        p.cognition_potential["compreensao_verbal"] = 70
        p.cognition["atencao"] = 70

        r1 = livros.ler(g, "pequeno_principe")   # 96 págs
        r2 = livros.ler(g, "alienista")          # 96 págs
        r3 = livros.ler(g, "metamorfose")        # 104 págs
        self.assertTrue(r1["concluido"] and r2["concluido"] and r3["concluido"])

        v = livros.view(g)
        nao_lidos_ids = {x["id"] for x in v["nao_lidos"]}
        lidos_ids = {x["id"] for x in v["lidos"]}
        self.assertEqual(lidos_ids, {"pequeno_principe", "alienista", "metamorfose"})
        self.assertTrue(nao_lidos_ids.isdisjoint(lidos_ids))
        self.assertGreater(v["conhecimentos"]["linguagem"], 0)
        self.assertNotEqual(r1["conhecimentos"], ["Economia e Finanças"])

        # Livro longo com progresso parcial entre meses e persistência em save
        livros.ler(g, "guerra_e_paz")  # 1536 págs
        v2 = livros.view(g)
        self.assertTrue(any(x["id"] == "guerra_e_paz" and x["em_andamento"] for x in v2["em_andamento"]))
        with tempfile.TemporaryDirectory() as td:
            arq = os.path.join(td, "p.db")
            persistence.save_game(g, arq)
            g2 = persistence.load_game(arq)
        v3 = livros.view(g2)
        self.assertTrue(any(x["id"] == "guerra_e_paz" and x["progresso"] > 0 for x in v3["em_andamento"]))

    def test_estudar_ensaio_artigo_filme_e_rng_intacto(self):
        g, p = _jogo(idade=17)
        p.in_school = True
        rng0 = g.rng.getstate()
        r_est = intelecto.estudar(g, "escola")
        r_en = intelecto.estudar(g, "enem")
        r_red = intelecto.escrever_ensaio(g, "tecnologia", "redacao")
        r_art = intelecto.ler_artigo(g, "ciencias")
        r_flm = intelecto.assistir_filme(g, "interestelar")
        self.assertEqual(g.rng.getstate(), rng0)

        self.assertGreater(r_est["restantes"], 0)
        self.assertIn("nota", r_red)
        self.assertGreater(intelecto.bonus_escola_atual(g, p.id), 0)
        self.assertGreater(intelecto.bonus_enem_atual(g, p.id), 0)
        self.assertGreater(intelecto.dados(g, p.id)["conhecimentos"]["ciencias"], 0)
        self.assertIn("interestelar", intelecto.dados(g, p.id)["filmes"])

        # Estudar melhora diretamente o school_performance
        import random
        g.rng = random.Random(5)
        perf_com_estudo = engine.school_performance(g, p, 17)
        g.intelecto[p.id]["bonus_escola"] = [g.year, 0]
        g.rng = random.Random(5)
        perf_sem_estudo = engine.school_performance(g, p, 17)
        self.assertGreater(perf_com_estudo, perf_sem_estudo)


class TestCoerenciaGeograficaEEventos(unittest.TestCase):
    def test_usp_exige_mudanca_para_sp_ou_confirmacao(self):
        g, p = _jogo(idade=19, riqueza=80000.0)
        p.schooling_years, p.in_school = 12, False
        for k in p.cognition:
            p.cognition[k] = p.cognition_potential[k] = 90
        p.personality["conscienciosidade"] = 90
        educacao_br.fazer_enem(g)
        g.educacao_br[p.id]["enem"]["media"] = 850.0
        g.educacao_br[p.id]["enem"]["redacao"] = 920

        # Mora em BH/MG -> tentar USP sem mudar_cidade deve recusar
        self.assertEqual(mundo.cidade_of(g, p.id)[0], "bh")
        with self.assertRaises(ValueError):
            educacao_br.ingressar(g, "USP", "computacao", "sisu")

        # Confirmando mudar_cidade=True -> muda para São Paulo/SP e ingressa na USP
        res = educacao_br.ingressar(g, "USP", "computacao", "sisu", mudar_cidade=True)
        self.assertEqual(res["universidade"], "USP")
        self.assertEqual(mundo.cidade_of(g, p.id)[0], "sp")
        self.assertTrue(p.in_college)

    def test_eventos_desde_nascimento_ate_velhice(self):
        for idade in (0, 1, 3, 8, 15, 30, 68, 85):
            g, p = _jogo(idade=idade, seed=42)
            el = decisions.elegiveis(g, p)
            self.assertGreaterEqual(len(el), 3, f"poucos eventos na idade {idade}")

    def test_http_novas_rotas_intelecto_e_mudanca(self):
        with tempfile.TemporaryDirectory() as td:
            srv, _ = ui_web.criar_servidor(td, porta=0)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            try:
                def post(rota, body):
                    req = urllib.request.Request(
                        base + rota, method="POST",
                        data=json.dumps(body).encode(),
                        headers={"X-Sim": "1", "Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req) as resp:
                        return resp.status, json.loads(resp.read())

                st, _ = post("/api/novo", {"nome": "T18", "modo": "avulso", "idade": 22, "semente": 31})
                self.assertEqual(st, 200)
                for rota, body in [
                    ("/api/intelecto/estudar", {"modo": "tema", "area": "economia"}),
                    ("/api/intelecto/ensaio", {"tema": "economia", "tipo": "ensaio"}),
                    ("/api/intelecto/artigo", {"assunto": "ciencias"}),
                    ("/api/intelecto/filme", {"id": "ilha_flores"}),
                    ("/api/ler", {"id": "manifesto"}),
                ]:
                    st, res = post(rota, body)
                    self.assertEqual(st, 200, rota)
                    self.assertIn("intelecto", res["estado"])
                for pnome in ("escola", "cognicao"):
                    with urllib.request.urlopen(base + f"/api/painel/{pnome}") as rp:
                        self.assertEqual(rp.status, 200)
                        pdata = json.loads(rp.read())
                        self.assertTrue(pdata.get("blocos"))
            finally:
                srv.shutdown()
                srv.server_close()


    def test_avancar_12_meses_com_decisao_retoma_ano_inteiro(self):
        with tempfile.TemporaryDirectory() as td:
            srv, _ = ui_web.criar_servidor(td, porta=0)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            try:
                def post(rota, body):
                    req = urllib.request.Request(
                        base + rota, method="POST",
                        data=json.dumps(body).encode(),
                        headers={"X-Sim": "1", "Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req) as resp:
                        return resp.status, json.loads(resp.read())
                st, est0 = post("/api/novo", {"nome": "AnoCompleto", "modo": "nascer", "irmaos": 1, "semente": 11})
                self.assertEqual(st, 200)
                ano_ini, mes_ini = est0["partida"]["ano"], est0["partida"]["mes"]
                # Avança 12 meses com decisões ativas: se pausar em decisão, decide e retoma o restante do ano
                st, rel = post("/api/avancar", {"meses": 12})
                self.assertEqual(st, 200)
                if rel["decisao"]:
                    self.assertGreater(rel["restantes"], 0)
                    self.assertEqual(rel["meses"] + rel["restantes"], 12)
                    st2, dec = post("/api/decidir", {"opcao": 0})
                    self.assertEqual(st2, 200)
                    self.assertEqual(dec["restantes_avanco"], rel["restantes"])
                    st3, rel_fim = post("/api/avancar/retomar", {})
                    self.assertEqual(st3, 200)
                    self.assertEqual(rel_fim["meses"], 12)
                    self.assertEqual(rel_fim["restantes"], 0)
                    est_fim = rel_fim["estado"]
                else:
                    self.assertEqual(rel["meses"], 12)
                    est_fim = rel["estado"]
                self.assertEqual(est_fim["partida"]["ano"], ano_ini + 1)
                self.assertEqual(est_fim["partida"]["mes"], mes_ini)
            finally:
                srv.shutdown()
                srv.server_close()


if __name__ == "__main__":
    unittest.main()
