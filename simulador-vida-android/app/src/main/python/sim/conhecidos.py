"""Conhecer alguém (G3a/G3g, v0.15.3–0.17.0): o jogador gera uma pessoa nova e já fica amigo dela.

Locais: vizinhança, escola, faculdade e trabalho (v0.17.0: colega na mesma empresa sem estourar vagas).
Todo conhecido ganha uma `Family` (`Família <sobrenome>`), mantendo `game.rng` intacto.
"""
from __future__ import annotations

import random

from . import economy, engine, factory, firms, macro, work
from .models import Family, Game


def locais(game: Game) -> list[dict]:
    p = game.characters.get(game.player_id) if game.player_id is not None else None
    out = [{"id": "vizinhanca", "rotulo": "Na vizinhança"}]
    if p is not None and p.alive:
        if p.in_school:
            out.append({"id": "escola", "rotulo": "Na escola"})
        if getattr(p, "in_college", False):
            out.append({"id": "faculdade", "rotulo": "Na faculdade"})
        if work.is_employed(p):
            out.append({"id": "trabalho", "rotulo": "No trabalho"})
    return out


def _atribuir_trabalho(game: Game, p, novo, mes: int, r: random.Random) -> None:
    firm = game.firms.get(p.workplace) if (firms.ATIVO and p.workplace is not None) else None
    if firm is not None and firm.is_open:
        fill = firms.filled(game, exclude_id=novo.id)
        livres = [k for k, cap in sorted(firm.slots.items()) if cap - fill.get((firm.id, k), 0) > 0]
        if livres:
            occ = r.choice(livres)
        else:
            occ = p.occupation or r.choice(sorted(firm.slots) or sorted(firms.SETORES[firm.sector]))
            firm.slots[occ] = firm.slots.get(occ, 0) + 1
    else:
        occ = p.occupation or "servicos_gerais"
    req_lvl = work.occupation_level(occ)
    novo.in_school = False
    novo.in_college = False
    novo.retired = False
    novo.seeking_since = None
    if req_lvl >= 1:
        novo.schooling_years = max(novo.schooling_years, 9)
    if req_lvl >= 2:
        novo.schooling_years = max(novo.schooling_years, 12)
    if req_lvl >= 3:
        novo.schooling_years = max(novo.schooling_years, 12)
        novo.graduated = True
        novo.higher_years = max(novo.higher_years, engine.ANOS_SUPERIOR)
    novo.occupation = occ
    novo.workplace = firm.id if firm is not None else p.workplace
    novo.job_start = mes
    novo.rank = 0
    novo.rank_since = mes
    novo.jobs_held = max(1, novo.jobs_held)
    novo.informal = r.random() < firms.informal_probability(req_lvl, firm)
    novo.income = economy.monthly_salary(novo, firm, macro.min_wage(game))


def conhecer(game: Game, local: str = "vizinhanca") -> dict:
    p = game.characters.get(game.player_id) if game.player_id is not None else None
    if p is None or not p.alive:
        raise ValueError("Nenhum personagem vivo do jogador.")
    now = (game.year, game.month)
    idade = p.age_at(*now)
    if idade < engine.IDADE_AMIZADE_MIN:
        raise ValueError(f"Só a partir dos {engine.IDADE_AMIZADE_MIN} anos é possível conhecer pessoas.")
    if engine._alive_friend_count(game, p) >= engine.MAX_AMIGOS:
        raise ValueError(f"Você já tem {engine.MAX_AMIGOS} amigos; o círculo está cheio.")
    mes = game.year * 12 + game.month
    chave = (-1, p.id)
    if game.convivio.get(chave) == mes:
        raise ValueError("Você já conheceu alguém neste mês; tente de novo no próximo.")
    if local not in {x["id"] for x in locais(game)}:
        raise ValueError("Você não pode conhecer alguém nesse lugar agora.")
    r = random.Random(f"conhecer:{game.seed}:{mes}:{p.id}:{game.next_char_id}")
    gap = 1 if local == "escola" else 4 if local == "faculdade" else engine._max_age_gap(idade)
    lo, hi = idade - gap, idade + gap
    min_menor = work.IDADE_TRABALHO_MIN if local == "trabalho" else engine.IDADE_AMIZADE_MIN
    max_adulto = 74 if local == "trabalho" else 90
    lo, hi = (max(lo, min_menor), min(hi, 17)) if idade < 18 else (max(lo, 18), min(hi, max_adulto))
    if lo > hi:
        lo = hi = max(min_menor, min(idade, 17)) if idade < 18 else min(max_adulto, max(18, idade))
    idade_novo = r.randint(lo, hi)
    estado = game.rng.getstate()
    try:
        novo = factory.create_character(game, idade_novo, r.choice("FM"))
    finally:
        game.rng.setstate(estado)
    if novo.family_id is None:
        fam = Family(id=game.next_family_id, name=f"Família {novo.last_name}")
        game.next_family_id += 1
        game.families[fam.id] = fam
        novo.family_id = fam.id
    if local == "escola":
        novo.in_school = True
        novo.schooling_years = max(novo.schooling_years, p.schooling_years) if idade_novo >= 18 else novo.schooling_years
    elif local == "faculdade":
        novo.in_college, novo.in_school = True, False
        novo.schooling_years, novo.higher_years = max(12, novo.schooling_years), p.higher_years
    elif local == "trabalho":
        _atribuir_trabalho(game, p, novo, mes, r)
    game.add_friendship(p.id, novo.id)
    game.convivio[chave] = mes
    onde = {"escola": " na escola", "faculdade": " na faculdade", "trabalho": " no trabalho"}.get(local, "")
    game.add_event(p.id, "amizade", f"Conheceu {novo.full_name}{onde} e fez amizade.")
    game.add_event(novo.id, "amizade", f"Conheceu {p.full_name}{onde} e fez amizade.")
    return {"id": novo.id, "nome": novo.full_name, "idade": idade_novo, "local": local}
