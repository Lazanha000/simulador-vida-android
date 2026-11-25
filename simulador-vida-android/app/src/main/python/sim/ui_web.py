"""Interface gráfica (v0.14.0): servidor web local, só biblioteca padrão.

`python3 main.py` sobe um servidor em 127.0.0.1 e abre o navegador; a interface (web/) usa o kit de arte "Manuscrito
iluminado". Esta camada só traduz HTTP <-> funções de `views`/`panels`/`factory`/`engine`/`persistence`: não há regra
de simulação aqui. Uma partida ativa por processo (jogo local); todas as chamadas à API são serializadas por um lock.

Segurança de um servidor local: escuta só em 127.0.0.1 (a menos que `--host` diga outra coisa); rejeita `Host` que não
seja local (contra DNS rebinding) e exige o cabeçalho `X-Sim: 1` nos POST (um site qualquer não consegue enviá-lo sem
preflight CORS, que o servidor não responde).
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import random
import re
import socket
import sqlite3
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import __version__, avatar_art, carreiras, livros, conhecidos, convivio, educacao_br, encontros, decisions, factory, foco, intelecto, mundo, panels, persistence, psicologia, start, views, vinculos
from .models import MESES, Game

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_w = os.path.join(RAIZ, "web")
WEB = _w if os.path.isdir(_w) else os.path.join(os.path.dirname(RAIZ), "assets", "web")
MAX_CORPO = 1_000_000
HOSTS_LOCAIS = {"127.0.0.1", "localhost", "[::1]", "::1"}


class ErroApi(Exception):
    def __init__(self, msg: str, status: int = 400, extra: dict | None = None):
        super().__init__(msg)
        self.msg, self.status, self.extra = msg, status, extra or {}


def slug(nome: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", nome.strip()).strip("_")
    return s or "partida"


class App:
    """Estado do processo: pasta de saves e a partida ativa (jogo, arquivo, alterações não salvas, autosave)."""

    def __init__(self, saves_dir: str):
        self.saves_dir = os.path.abspath(saves_dir)
        self.game: Game | None = None
        self.path: str | None = None
        self.dirty = False
        self.autosave = True
        self.lock = threading.RLock()

    # --- utilidades ------------------------------------------------------------------------------
    def meta(self) -> dict:
        return {"arquivo": os.path.basename(self.path) if self.path else None, "sujo": self.dirty, "autosave": self.autosave}

    def _need_game(self) -> Game:
        if self.game is None:
            raise ErroApi("Nenhuma partida aberta.", 409)
        return self.game

    def _ultimo_path(self) -> str:
        return os.path.join(self.saves_dir, ".ultimo")

    def _gravar_ultimo(self) -> None:
        if self.path:
            try:
                os.makedirs(self.saves_dir, exist_ok=True)
                with open(self._ultimo_path(), "w", encoding="utf-8") as f:
                    f.write(os.path.basename(self.path))
            except OSError:
                pass

    def _salvar(self) -> str:
        game = self._need_game()
        if not self.path:
            self.path = os.path.join(self.saves_dir, slug(game.name) + ".db")
        persistence.save_game(game, self.path)
        self.dirty = False
        self._gravar_ultimo()
        return os.path.basename(self.path)

    def _resolver_save(self, nome: str) -> str:
        if not nome or os.path.basename(nome) != nome or not nome.endswith(".db") or nome.startswith("."):
            raise ErroApi("Nome de arquivo inválido.")
        path = os.path.join(self.saves_dir, nome)
        if not os.path.isfile(path):
            raise ErroApi("Save não encontrado.", 404)
        return path

    # --- saves -----------------------------------------------------------------------------------
    def listar_saves(self) -> list[dict]:
        out = []
        if os.path.isdir(self.saves_dir):
            for nome in os.listdir(self.saves_dir):
                if nome.endswith(".db") and not nome.startswith("."):
                    out.append(self._info_save(nome))
        out.sort(key=lambda x: x["mtime"], reverse=True)
        return out

    def _info_save(self, nome: str) -> dict:
        path = os.path.join(self.saves_dir, nome)
        info = {"arquivo": nome, "mtime": os.path.getmtime(path), "nome": nome[:-3], "data": None, "jogador": None, "legivel": False}
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
                if meta.get("schema_version") in persistence.SUPPORTED_VERSIONS:
                    info.update(nome=meta["name"], data=f"{MESES[int(meta['month']) - 1]} de {meta['year']}", legivel=True)
                    pid = meta.get("player_id")
                    if pid not in (None, ""):
                        r = con.execute("SELECT first_name, last_name, birth_year, birth_month, alive, death_year, death_month "
                                        "FROM characters WHERE id = ?", (int(pid),)).fetchone()
                        if r:
                            ref = (int(meta["year"]), int(meta["month"])) if r[4] else (r[5], r[6])
                            idade = ((ref[0] * 12 + ref[1]) - (r[2] * 12 + r[3])) // 12
                            info["jogador"] = f"{r[0]} {r[1]}, {idade} anos" + ("" if r[4] else " (falecido)")
            finally:
                con.close()
        except (sqlite3.Error, ValueError, KeyError):
            pass
        return info

    def ultimo(self) -> dict | None:
        try:
            with open(self._ultimo_path(), encoding="utf-8") as f:
                nome = f.read().strip()
            self._resolver_save(nome)
        except (OSError, ErroApi):
            return None
        info = self._info_save(nome)
        return info if info["legivel"] else None

    # --- ações -----------------------------------------------------------------------------------
    def novo_jogo(self, b: dict) -> dict:
        nome = str(b.get("nome") or "Minha vida").strip()[:60] or "Minha vida"
        path = os.path.join(self.saves_dir, slug(nome) + ".db")
        if os.path.exists(path) and not b.get("sobrescrever"):
            raise ErroApi("Já existe um save com esse nome.", 409, {"existe": True})
        try:
            seed = int(b["semente"]) if str(b.get("semente", "")).strip() else random.randrange(1, 2**31)
        except ValueError:
            raise ErroApi("Semente inválida.")
        game = factory.new_game(nome, seed)
        modo = b.get("modo", "nascer")
        sexo = (b.get("sexo") or "").upper() or None
        if sexo not in (None, "F", "M"):
            raise ErroApi("Sexo inválido.")
        sobrenome = (str(b.get("sobrenome") or "").strip() or None)
        try:
            if modo == "nascer":
                start.start_newborn(game, sobrenome, int(b.get("irmaos", 1)), sexo, str(b.get("nome_personagem") or "").strip() or None)
            elif modo == "avulso":
                start.start_adult(game, int(b.get("idade", 0)), sexo, str(b.get("nome_personagem") or "").strip() or None, sobrenome)
            elif modo == "familia":
                start.start_family(game, sobrenome, int(b.get("filhos", 2)))
            else:
                raise ErroApi("Modo de início inválido.")
        except (ValueError, TypeError) as exc:
            raise ErroApi(str(exc))
        self.game, self.path, self.dirty = game, path, True
        self._salvar()
        return self.estado()

    def carregar(self, nome: str) -> dict:
        path = self._resolver_save(nome)
        try:
            game = persistence.load_game(path)
        except (ValueError, FileNotFoundError, sqlite3.Error) as exc:
            raise ErroApi(f"Não foi possível carregar: {exc}")
        self.game, self.path, self.dirty = game, path, False
        self._gravar_ultimo()
        return self.estado()

    def avancar(self, meses: int) -> dict:
        game = self._need_game()
        if meses not in (1, 6, 12):
            raise ErroApi("Escolha 1, 6 ou 12 meses.")
        if not game.characters:
            raise ErroApi("Crie um personagem antes de avançar o tempo.")
        if game.decisions["pending"]:
            raise ErroApi("Há uma decisão pendente: escolha antes de avançar.", 409)
        rel = views.avancar(game, meses)
        self.dirty = True
        rel["salvo"] = False
        if self.autosave:
            self._salvar()
            rel["salvo"] = True
        rel["estado"] = self.estado()
        return rel

    def retomar_avanco(self) -> dict:
        game = self._need_game()
        if not game.characters:
            raise ErroApi("Crie um personagem antes de avançar o tempo.")
        if game.decisions["pending"]:
            raise ErroApi("Há uma decisão pendente: escolha antes de avançar.", 409)
        try:
            rel = views.retomar_avanco(game)
        except ValueError as exc:
            raise ErroApi(str(exc), 409)
        self.dirty = True
        rel["salvo"] = False
        if self.autosave:
            self._salvar()
            rel["salvo"] = True
        rel["estado"] = self.estado()
        return rel

    def decidir(self, b: dict) -> dict:
        game = self._need_game()
        op = b.get("opcao")
        try:
            r = decisions.decidir(game, None if op in (None, "auto") else int(op))
        except (ValueError, TypeError) as exc:
            raise ErroApi(str(exc), 409)
        self.dirty = True
        if self.autosave:
            self._salvar()
        r["estado"] = self.estado()
        return r

    def estado(self) -> dict:
        return views.estado(self.game, self.meta())

    def fechar(self) -> dict:
        if self.game is not None and self.dirty and self.autosave:
            self._salvar()
        self.game, self.path, self.dirty = None, None, False
        return {"tem_jogo": False}

    def trocar_jogador(self, cid: int) -> dict:
        game = self._need_game()
        c = game.characters.get(cid)
        if c is None:
            raise ErroApi("Id inexistente.", 404)
        if game.decisions["pending"]:
            raise ErroApi("Há uma decisão pendente: escolha antes de trocar de personagem.", 409)
        game.player_id = cid
        self.dirty = True
        if self.autosave:
            self._salvar()
        return self.estado()

    def criar_personagem(self, b: dict) -> dict:
        game = self._need_game()
        sexo = (b.get("sexo") or "").upper() or None
        if sexo not in (None, "F", "M"):
            raise ErroApi("Sexo inválido.")
        try:
            c = factory.create_character(game, int(b.get("idade", 0)), sexo, str(b.get("nome") or "").strip() or None,
                                         str(b.get("sobrenome") or "").strip() or None)
        except (ValueError, TypeError) as exc:
            raise ErroApi(str(exc))
        if game.player_id is None:
            game.player_id = c.id
        self.dirty = True
        return {"criado": views.pessoa(game, c), "estado": self.estado()}

    def criar_familia(self, b: dict) -> dict:
        game = self._need_game()
        try:
            r = factory.create_family(game, str(b.get("sobrenome") or "").strip() or None, int(b.get("filhos", 2)))
        except (ValueError, TypeError) as exc:
            raise ErroApi(str(exc))
        if game.player_id is None:
            game.player_id = r["children"][0].id if r["children"] else r["mother"].id
        self.dirty = True
        return {"criada": r["family"].name, "membros": 2 + len(r["children"]), "estado": self.estado()}

    # --- roteamento da API --------------------------------------------------------------------------
    def api(self, metodo: str, rota: str, q: dict, corpo: dict) -> dict:
        with self.lock:
            if metodo == "GET":
                if rota == "estado":
                    return self.estado()
                if rota == "saves":
                    return {"saves": self.listar_saves(), "ultimo": self.ultimo(), "versao": __version__}
                if rota == "diario":
                    game = self._need_game()
                    p = views.player_of(game)
                    if p is None:
                        raise ErroApi("Nenhum personagem do jogador.", 409)
                    antes = int(q["antes"]) if q.get("antes", "").lstrip("-").isdigit() else None
                    lim = max(10, min(500, int(q["limite"]))) if q.get("limite", "").isdigit() else 120
                    return views.feed(game, p, lim, antes)
                if rota.startswith("painel/"):
                    game = self._need_game()
                    try:
                        return panels.painel(game, rota[len("painel/"):], q, self.meta())
                    except KeyError:
                        raise ErroApi("Painel inexistente.", 404)
                    except (ValueError, TypeError) as exc:
                        raise ErroApi(str(exc))
                if rota == "herdeiros":
                    game = self._need_game()
                    p = views.player_of(game)
                    return {"itens": views.herdeiros_possiveis(game, p) if p else []}
            elif metodo == "POST":
                if rota == "novo":
                    return self.novo_jogo(corpo)
                if rota == "carregar":
                    return self.carregar(str(corpo.get("arquivo", "")))
                if rota == "salvar":
                    return {"arquivo": self._salvar(), "estado": self.estado()}
                if rota == "fechar":
                    return self.fechar()
                if rota == "avancar":
                    return self.avancar(int(corpo.get("meses", 0)))
                if rota == "avancar/retomar":
                    return self.retomar_avanco()
                if rota == "foco":
                    game = self._need_game()
                    try:
                        foco.definir(game, str(corpo.get("foco", "")), corpo.get("area"))
                    except ValueError as exc:
                        raise ErroApi(str(exc))
                    self.dirty = True
                    if self.autosave:
                        self._salvar()
                    return self.estado()
                if rota == "conhecer":
                    game = self._need_game()
                    try:
                        novo = conhecidos.conhecer(game, str(corpo.get("local", "vizinhanca")))
                    except ValueError as exc:
                        raise ErroApi(str(exc), 409)
                    self.dirty = True
                    if self.autosave:
                        self._salvar()
                    return {"novo": novo, "estado": self.estado()}
                if rota == "conversar":
                    game = self._need_game()
                    try:
                        r = convivio.conversar(game, int(corpo.get("id", 0)))
                    except (ValueError, TypeError) as exc:
                        raise ErroApi(str(exc), 409)
                    self.dirty = True
                    if self.autosave:
                        self._salvar()
                    return {"conversa": r, "estado": self.estado()}
                if rota == "convidar":
                    game = self._need_game()
                    try:
                        r = convivio.convidar(game, int(corpo.get("id", 0)))
                    except (ValueError, TypeError) as exc:
                        raise ErroApi(str(exc), 409)
                    self.dirty = True
                    if self.autosave:
                        self._salvar()
                    return {"convite": r, "estado": self.estado()}
                if rota == "encontro":
                    game = self._need_game()
                    try:
                        r = encontros.escolher(game, int(corpo.get("slot", -1)))
                    except (ValueError, TypeError) as exc:
                        raise ErroApi(str(exc), 409)
                    self.dirty = True
                    if self.autosave:
                        self._salvar()
                    return {"par": r, "estado": self.estado()}
                if rota in ("namoro/terminar", "namoro/pedir"):
                    game = self._need_game()
                    try:
                        fn = encontros.terminar if rota.endswith("terminar") else encontros.pedir_em_casamento
                        r = fn(game)
                    except ValueError as exc:
                        raise ErroApi(str(exc), 409)
                    self.dirty = True
                    if self.autosave:
                        self._salvar()
                    return {"resultado": r, "estado": self.estado()}
                if rota == "ler":
                    game = self._need_game()
                    try:
                        pags = int(corpo["paginas"]) if corpo.get("paginas") not in (None, "") else None
                        r = livros.ler(game, str(corpo.get("id", "")), pags)
                    except (ValueError, TypeError) as exc:
                        raise ErroApi(str(exc), 409)
                    self.dirty = True
                    if self.autosave:
                        self._salvar()
                    return {"leitura": r, "estado": self.estado()}
                if rota in (
                    "psicologia/habito", "psicologia/meta", "psicologia/qi",
                    "vinculos/interagir", "encontros/preferencia",
                    "intelecto/estudar", "intelecto/estudar_lote", "intelecto/ensaio", "intelecto/artigo", "intelecto/filme",
                    "intelecto/revisar", "intelecto/grupo", "intelecto/idioma", "intelecto/pesquisar",
                    "livros/fila/adicionar", "livros/fila/remover", "livros/fila/mover", "livros/fila/limpar", "livros/fila/auto", "livros/ler_fila",
                    "educacao/enem", "educacao/ingressar", "educacao/ic", "educacao/pos", "educacao/tecnico",
                    "carreiras/concurso", "carreiras/abrir_empresa", "carreiras/encerrar_empresa",
                    "carreiras/expandir_empresa", "carreiras/meio_periodo", "carreiras/sair_meio_periodo", "carreiras/freela",
                    "carreiras/freela_lote", "carreiras/trabalho_extra",
                    "politica/filiar", "politica/campanha", "politica/concorrer",
                    "politica/movimento", "politica/projeto",
                    "mundo/mudar_cidade", "mundo/comprar_imovel", "mundo/vender_imovel",
                    "mundo/comprar_veiculo", "mundo/vender_veiculo",
                    "mundo/comprar_equipamento", "mundo/vender_equipamento", "mundo/plano_saude",
                    "mundo/investir", "mundo/resgatar", "mundo/emprestimo", "mundo/quitar",
                ):
                    game = self._need_game()
                    try:
                        if rota == "psicologia/habito":
                            r = psicologia.alternar_habito(game, str(corpo.get("id", "")))
                        elif rota == "psicologia/meta":
                            r = psicologia.definir_meta(game, str(corpo.get("id", "")), bool(corpo.get("adicionar", True)))
                        elif rota == "psicologia/qi":
                            r = psicologia.toggle_qi(game, corpo.get("mostrar") if "mostrar" in corpo else None)
                        elif rota == "vinculos/interagir":
                            r = vinculos.interagir(game, int(corpo.get("id", 0)), str(corpo.get("acao", "")))
                        elif rota == "encontros/preferencia":
                            r = encontros.definir_preferencia(game, str(corpo.get("pref", "oposto")))
                        elif rota == "intelecto/estudar":
                            r = intelecto.estudar(game, str(corpo.get("modo", "escola")), corpo.get("area") or None)
                        elif rota == "intelecto/estudar_lote":
                            sessoes = int(corpo["sessoes"]) if corpo.get("sessoes") not in (None, "") else None
                            r = intelecto.estudar_lote(game, str(corpo.get("modo", "escola")), corpo.get("area") or None, sessoes)
                        elif rota == "intelecto/ensaio":
                            r = intelecto.escrever_ensaio(game, str(corpo.get("tema", "")), str(corpo.get("tipo", "redacao")))
                        elif rota == "intelecto/artigo":
                            r = intelecto.ler_artigo(game, str(corpo.get("assunto", "")))
                        elif rota == "intelecto/filme":
                            r = intelecto.assistir_filme(game, str(corpo.get("id", "")))
                        elif rota == "intelecto/revisar":
                            r = intelecto.revisar(game, str(corpo.get("area", "")))
                        elif rota == "intelecto/grupo":
                            r = intelecto.grupo_estudo(game, str(corpo.get("area", "")))
                        elif rota == "intelecto/idioma":
                            r = intelecto.estudar_idioma(game, str(corpo.get("idioma", "")))
                        elif rota == "intelecto/pesquisar":
                            r = intelecto.pesquisar_e_publicar(game, str(corpo.get("sub", "")))
                        elif rota == "livros/fila/adicionar":
                            r = livros.fila_adicionar(game, str(corpo.get("id", "")))
                        elif rota == "livros/fila/remover":
                            r = livros.fila_remover(game, str(corpo.get("id", "")))
                        elif rota == "livros/fila/mover":
                            r = livros.fila_mover(game, str(corpo.get("id", "")), corpo.get("delta", 1))
                        elif rota == "livros/fila/limpar":
                            r = livros.fila_limpar(game)
                        elif rota == "livros/fila/auto":
                            r = livros.fila_auto(game, corpo.get("ativar") if "ativar" in corpo else None)
                        elif rota == "livros/ler_fila":
                            r = livros.ler_fila(game)
                        elif rota == "educacao/enem":
                            r = educacao_br.fazer_enem(game)
                        elif rota == "educacao/ingressar":
                            r = educacao_br.ingressar(game, str(corpo.get("uni", "")), str(corpo.get("curso", "")), str(corpo.get("modalidade", "sisu")), bool(corpo.get("mudar_cidade", False)))
                        elif rota == "educacao/ic":
                            r = educacao_br.iniciacao_cientifica(game)
                        elif rota == "educacao/pos":
                            r = educacao_br.iniciar_pos(game, str(corpo.get("nivel", "")))
                        elif rota == "educacao/tecnico":
                            r = educacao_br.iniciar_tecnico(game, str(corpo.get("id", "")), bool(corpo.get("publica", True)))
                        elif rota == "carreiras/concurso":
                            r = carreiras.prestar_concurso(game, str(corpo.get("id", "")))
                        elif rota == "carreiras/abrir_empresa":
                            r = carreiras.abrir_empresa(game, str(corpo.get("setor", "")), str(corpo.get("porte", "micro")))
                        elif rota == "carreiras/encerrar_empresa":
                            r = carreiras.encerrar_empresa(game)
                        elif rota == "carreiras/expandir_empresa":
                            r = carreiras.expandir_empresa(game)
                        elif rota == "carreiras/meio_periodo":
                            r = carreiras.iniciar_meio_periodo(game, str(corpo.get("area", "Geral")))
                        elif rota == "carreiras/sair_meio_periodo":
                            r = carreiras.sair_meio_periodo(game)
                        elif rota == "carreiras/freela":
                            r = carreiras.fazer_freela(game, str(corpo.get("area", "economia")))
                        elif rota == "carreiras/freela_lote":
                            r = carreiras.fazer_freelas_lote(game, str(corpo.get("area", "economia")))
                        elif rota == "carreiras/trabalho_extra":
                            r = carreiras.trabalho_extra(game)
                        elif rota == "politica/filiar":
                            r = carreiras.filiar(game, str(corpo.get("partido", "")))
                        elif rota == "politica/campanha":
                            r = carreiras.fazer_campanha(game)
                        elif rota == "politica/concorrer":
                            r = carreiras.concorrer(game, str(corpo.get("cargo", "")))
                        elif rota == "politica/movimento":
                            r = carreiras.participar_movimento(game, str(corpo.get("id", "")))
                        elif rota == "politica/projeto":
                            r = carreiras.propor_projeto(game, str(corpo.get("pauta", "")))
                        elif rota == "mundo/mudar_cidade":
                            r = mundo.mudar_cidade(game, str(corpo.get("cidade", "")))
                        elif rota == "mundo/comprar_imovel":
                            r = mundo.comprar_imovel(game, str(corpo.get("tipo", "")), bool(corpo.get("alugar", False)))
                        elif rota == "mundo/vender_imovel":
                            r = mundo.vender_imovel(game, int(corpo.get("idx", -1)))
                        elif rota == "mundo/comprar_veiculo":
                            r = mundo.comprar_veiculo(game, str(corpo.get("tipo", "")))
                        elif rota == "mundo/vender_veiculo":
                            r = mundo.vender_veiculo(game)
                        elif rota == "mundo/comprar_equipamento":
                            r = mundo.comprar_equipamento(game, str(corpo.get("id", "")))
                        elif rota == "mundo/vender_equipamento":
                            r = mundo.vender_equipamento(game, str(corpo.get("id", "")))
                        elif rota == "mundo/plano_saude":
                            r = mundo.alternar_plano_saude(game, corpo.get("ativar") if "ativar" in corpo else None)
                        elif rota == "mundo/investir":
                            r = mundo.investir(game, str(corpo.get("tipo", "")), float(corpo.get("valor", 0)))
                        elif rota == "mundo/resgatar":
                            r = mundo.resgatar(game, str(corpo.get("tipo", "")), float(corpo.get("valor", 0)))
                        elif rota == "mundo/emprestimo":
                            r = mundo.pedir_emprestimo(game, float(corpo.get("valor", 0)))
                        elif rota == "mundo/quitar":
                            r = mundo.quitar_emprestimo(game, float(corpo.get("valor", 0)))
                    except (ValueError, TypeError) as exc:
                        raise ErroApi(str(exc), 409)
                    self.dirty = True
                    if self.autosave:
                        self._salvar()
                    return {"resultado": r, "estado": self.estado()}
                if rota == "decidir":
                    return self.decidir(corpo)
                if rota == "jogador":
                    return self.trocar_jogador(int(corpo.get("id", 0)))
                if rota == "criar/personagem":
                    return self.criar_personagem(corpo)
                if rota == "criar/familia":
                    return self.criar_familia(corpo)
                if rota == "ajustes":
                    if "autosave" in corpo:
                        self.autosave = bool(corpo["autosave"])
                    return self.estado()
            raise ErroApi("Rota inexistente.", 404)


TIPOS = {".svg": "image/svg+xml", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".html": "text/html; charset=utf-8", ".webmanifest": "application/manifest+json", ".woff2": "font/woff2",
         ".json": "application/json"}
RE_AVATAR = re.compile(r"^/avatar/(bebe|crianca|adolescente|jovem|adulto|idoso)_([fm])_([0-4])_([0-4])(_d)?\.svg$")


def _nome_host(h: str) -> str:
    h = h.strip()
    if h.startswith("["):
        return h.split("]")[0] + "]"
    return h.rsplit(":", 1)[0] if ":" in h else h


def make_handler(app: App, host_livre: bool):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = f"SimuladorVida/{__version__}"

        def log_message(self, fmt, *args):  # silencioso
            pass

        # -- helpers
        def _host_ok(self) -> bool:
            return host_livre or _nome_host(self.headers.get("Host") or "") in HOSTS_LOCAIS

        def _enviar(self, status: int, corpo: bytes, tipo: str, cache: str = "no-cache") -> None:
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(corpo)

        def _json(self, status: int, obj: dict) -> None:
            self._enviar(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _estatico(self, caminho: str) -> None:
            rel = unquote(caminho).lstrip("/") or "index.html"
            full = os.path.realpath(os.path.join(WEB, rel))
            if os.path.commonpath([full, os.path.realpath(WEB)]) != os.path.realpath(WEB) or not os.path.isfile(full):
                return self._json(404, {"erro": "Não encontrado."})
            ext = os.path.splitext(full)[1].lower()
            tipo = TIPOS.get(ext) or mimetypes.guess_type(full)[0] or "application/octet-stream"
            cache = "public, max-age=86400" if rel.startswith(("arte/", "fonts/")) else "no-cache"
            with open(full, "rb") as f:
                self._enviar(200, f.read(), tipo, cache)

        def _tratar(self, metodo: str) -> None:
            if not self._host_ok():
                return self._json(403, {"erro": "Host não permitido."})
            url = urlparse(self.path)
            caminho = url.path
            try:
                if caminho.startswith("/api/"):
                    corpo: dict = {}
                    if metodo == "POST":
                        if self.headers.get("X-Sim") != "1":
                            return self._json(403, {"erro": "Cabeçalho X-Sim ausente."})
                        n = int(self.headers.get("Content-Length") or 0)
                        if n > MAX_CORPO:
                            return self._json(413, {"erro": "Corpo grande demais."})
                        raw = self.rfile.read(n) if n else b""
                        corpo = json.loads(raw.decode("utf-8")) if raw else {}
                        if not isinstance(corpo, dict):
                            raise ErroApi("JSON inválido.")
                    q = {k: v[0] for k, v in parse_qs(url.query).items()}
                    return self._json(200, app.api(metodo, caminho[len("/api/"):], q, corpo))
                if metodo == "GET" or metodo == "HEAD":
                    m = RE_AVATAR.match(caminho)
                    if m:
                        est, sx, pele, cab, morto = m.groups()
                        svg = avatar_art.svg(est, sx, int(pele), int(cab), bool(morto))
                        return self._enviar(200, svg.encode("utf-8"), "image/svg+xml", "public, max-age=86400")
                    return self._estatico(caminho)
                self._json(405, {"erro": "Método não permitido."})
            except ErroApi as e:
                self._json(e.status, {"erro": e.msg, **e.extra})
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._json(400, {"erro": "JSON inválido."})
            except (ValueError, TypeError, KeyError) as e:
                self._json(400, {"erro": f"Requisição inválida: {e}"})
            except Exception as e:   # erro inesperado: nunca derruba o servidor
                self._json(500, {"erro": f"Erro interno: {type(e).__name__}: {e}"})

        def do_GET(self):
            self._tratar("GET")

        def do_HEAD(self):
            self._tratar("HEAD")

        def do_POST(self):
            self._tratar("POST")

    return Handler


class Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):   # navegador fechou/recarregou: não é erro do jogo
        if not isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            super().handle_error(request, client_address)


def criar_servidor(saves_dir: str, host: str = "127.0.0.1", porta: int = 8765, host_livre: bool = False):
    """Cria (sem iniciar) o servidor. Se a porta estiver ocupada, tenta as 20 seguintes; `porta=0` = qualquer livre."""
    app = App(saves_dir)
    ultimo_erro = None
    for p in ([0] if porta == 0 else range(porta, porta + 20)):
        try:
            return Servidor((host, p), make_handler(app, host_livre)), app
        except OSError as exc:
            ultimo_erro = exc
    raise OSError(f"Nenhuma porta livre a partir de {porta}: {ultimo_erro}")


def _ip_lan() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Simulador de Vida Brasileiro — interface gráfica (navegador)")
    ap.add_argument("--saves-dir", default=os.path.join(RAIZ, "saves"), help="pasta dos saves")
    ap.add_argument("--host", default="127.0.0.1", help="endereço de escuta (0.0.0.0 = jogar pelo celular na mesma rede)")
    ap.add_argument("--port", type=int, default=8765, help="porta (0 = qualquer livre)")
    ap.add_argument("--no-browser", action="store_true", help="não abrir o navegador")
    args = ap.parse_args(argv)
    host_livre = args.host not in ("127.0.0.1", "localhost", "::1")
    srv, app = criar_servidor(args.saves_dir, args.host, args.port, host_livre)
    porta = srv.server_address[1]
    url = f"http://127.0.0.1:{porta}/"
    print(f"Simulador de Vida Brasileiro v{__version__}\nAbra {url}  (Ctrl+C para encerrar)\nSaves em: {app.saves_dir}")
    if host_livre:
        ip = _ip_lan()
        print("ATENÇÃO: o servidor está acessível na sua rede" + (f"; no celular abra http://{ip}:{porta}/" if ip else "") +
              ". Qualquer pessoa na rede consegue jogar e ver esta partida.")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando…")
    finally:
        with app.lock:
            if app.game is not None and app.dirty and app.autosave:
                app._salvar()
                print("Partida salva.")
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
