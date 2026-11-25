"""Aplicativo de encontros (G3d, v0.15.7): só para maiores de 18 anos, solteiros, sem cônjuge nem parceiro.

Regra de idade (mostrada na tela): jogador menor de 18 não tem acesso; todos os candidatos têm 18 anos ou mais.
Escolha e consequência: o jogador vê 3 candidatos (nome, idade, sexo) e escolhe um (ou nenhum); o escolhido nasce
como personagem novo (traços próprios, persistido) e começa a namorar o jogador (`romance.start`). Os 3 candidatos
mudam a cada mês (sorteio local por semente/mês/jogador; nada é gravado até a escolha) e só 1 escolha por mês.
O `game.rng` é restaurado: o mundo simulado não muda por causa desta ação. Só pessoas de sexo diferente e
diferença de idade ≤ 10 anos (as mesmas regras do casamento no jogo atual).

Namoro (G3e, v0.15.8): com par, o jogador pode TERMINAR (-1 de saúde, ilustrativo) ou PEDIR EM CASAMENTO (só com
≥6 meses de namoro e ambos ≥18; 1 pedido por mês). O par aceita com chance 50% + 1,4 pp por mês de namoro (teto 100%
aos 36 meses; sorteio local por semente/mês/casal). Aceito: casam (`engine._marry`); recusado: segue o namoro e entra
na biografia. Eventos para os dois.
"""
from __future__ import annotations

import random

from . import engine, factory, romance
from .models import Game

QTD = 3
DIFERENCA_MAX = 10


def _jogador(game: Game):
    p = game.characters.get(game.player_id) if game.player_id is not None else None
    return p if p is not None and p.alive else None


def _motivo(game: Game, p) -> str | None:
    if p is None:
        return "Nenhum personagem vivo do jogador."
    if p.age_at(game.year, game.month) < 18:
        return "O aplicativo é só para maiores de 18 anos."
    if p.partner_id is not None and romance.partner_of(game, p) is not None:
        return "Você já está namorando."
    if engine.has_active_spouse(game, p):
        return "Você já é casado(a)."
    return None


def _mes(game: Game) -> int:
    return game.year * 12 + game.month


def preferencia_of(game: Game, cid: int) -> str:
    st = game.psicologia.get(cid)
    return st.get("pref_afetiva", "oposto") if st else "oposto"


def definir_preferencia(game: Game, pref: str) -> dict:
    if pref not in ("oposto", "mesmo", "todos"):
        raise ValueError("Preferência inválida (use oposto, mesmo ou todos).")
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    from . import psicologia
    st = psicologia.dados(game, p.id)
    st["pref_afetiva"] = pref
    return {"preferencia": pref}


def candidatos(game: Game) -> list[dict]:
    p = _jogador(game)
    if _motivo(game, p):
        return []
    idade = p.age_at(game.year, game.month)
    pref = preferencia_of(game, p.id)
    oposto = "M" if p.sex == "F" else "F"
    out = []
    for slot in range(QTD):
        r = random.Random(f"encontros:{game.seed}:{_mes(game)}:{p.id}:{slot}")
        if pref == "mesmo":
            sexo = p.sex
        elif pref == "todos":
            sexo = oposto if slot % 2 == 0 else p.sex
        else:
            sexo = oposto
        nomes = factory.NOMES_F if sexo == "F" else factory.NOMES_M
        out.append({"slot": slot, "nome": f"{r.choice(nomes)} {r.choice(factory.SOBRENOMES)}",
                    "idade": r.randint(max(18, idade - DIFERENCA_MAX), min(90, idade + DIFERENCA_MAX)),
                    "sexo": sexo})
    return out


def _par(game: Game, p):
    return romance.partner_of(game, p) if p is not None else None


def _namoro_view(game: Game, p) -> dict | None:
    q = _par(game, p)
    if q is None:
        return None
    now = (game.year, game.month)
    meses = game.year * 12 + game.month - (p.partner_since or 0)
    motivo = None
    if meses < romance.MESES_ANTES_CASAR:
        motivo = f"Só depois de {romance.MESES_ANTES_CASAR} meses de namoro."
    elif min(p.age_at(*now), q.age_at(*now)) < 18:
        motivo = "Só entre maiores de 18 anos."
    elif game.convivio.get((-3, p.id)) == _mes(game):
        motivo = "Você já fez um pedido neste mês."
    return {"id": q.id, "nome": q.full_name, "idade": q.age_at(*now), "meses": meses,
            "pode_pedir": motivo is None, "motivo": motivo}


def terminar(game: Game) -> dict:
    p = _jogador(game)
    q = _par(game, p)
    if q is None:
        raise ValueError("Você não está namorando.")
    game.add_event(p.id, "namoro_fim", f"Terminou o namoro com {q.full_name}.")
    game.add_event(q.id, "namoro_fim", f"{p.full_name} terminou o namoro.")
    romance._clear(p, q)
    p.health = max(0.0, p.health - 1.0)
    return {"nome": q.full_name}


def pedir_em_casamento(game: Game) -> dict:
    p = _jogador(game)
    q = _par(game, p)
    if q is None:
        raise ValueError("Você não está namorando.")
    v = _namoro_view(game, p)
    if not v["pode_pedir"]:
        raise ValueError(v["motivo"])
    game.convivio[(-3, p.id)] = _mes(game)
    chance = min(1.0, 0.5 + 0.014 * v["meses"])
    r = random.Random(f"pedido:{game.seed}:{_mes(game)}:{p.id}:{q.id}")
    if r.random() < chance:
        game.add_event(p.id, "namoro", f"Pediu {q.full_name} em casamento e ela/ele aceitou.")
        game.add_event(q.id, "namoro", f"Aceitou o pedido de casamento de {p.full_name}.")
        romance._clear(p, q)
        engine._marry(game, p, q)
        return {"aceitou": True, "nome": q.full_name}
    game.add_event(p.id, "namoro", f"Pediu {q.full_name} em casamento, mas ela/ele ainda não estava pronto(a).")
    game.add_event(q.id, "namoro", f"{p.full_name} fez um pedido de casamento; não se sentiu pronto(a) ainda.")
    return {"aceitou": False, "nome": q.full_name}


def view(game: Game) -> dict:
    p = _jogador(game)
    motivo = _motivo(game, p)
    if motivo is None and game.convivio.get((-2, p.id)) == _mes(game):
        motivo = "Você já escolheu alguém neste mês."
    pref = preferencia_of(game, p.id) if p is not None else "oposto"
    return {"disponivel": motivo is None, "motivo": motivo, "preferencia": pref,
            "namoro": _namoro_view(game, p),
            "candidatos": candidatos(game) if motivo is None else []}


def escolher(game: Game, slot: int) -> dict:
    p = _jogador(game)
    motivo = _motivo(game, p) or (
        "Você já escolheu alguém neste mês." if game.convivio.get((-2, p.id)) == _mes(game) else None)
    if motivo:
        raise ValueError(motivo)
    c = next((x for x in candidatos(game) if x["slot"] == slot), None)
    if c is None:
        raise ValueError("Candidato inválido.")
    nome, sobrenome = c["nome"].split(" ", 1)
    estado = game.rng.getstate()
    try:
        novo = factory.create_character(game, c["idade"], c["sexo"], first_name=nome, last_name=sobrenome)
    finally:
        game.rng.setstate(estado)
    game.convivio[(-2, p.id)] = _mes(game)
    romance.start(game, p, novo)
    return {"id": novo.id, "nome": novo.full_name, "idade": c["idade"]}
