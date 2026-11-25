"""Indicadores derivados (v0.14.0) para as barras de status da interface.

Nada aqui é estado novo: são funções PURAS de dados que o motor já mantém (saúde, cognição, amizades, família, renda,
patrimônio, ocupação). Não usam `game.rng`, não são salvas e não alteram a simulação. Todos devolvem 0–100.
O "bem-estar" (barra de felicidade do kit de arte) é um indicador ILUSTRATIVO que combina quatro dimensões; se um dia
virar atributo do motor (com efeitos), este módulo deixa de ser a fonte.
"""
from __future__ import annotations

import math

from . import economy, engine, macro, romance, work
from .models import Character, Game

# Pesos do bem-estar (somam 1,0).
PESO_SAUDE, PESO_SOCIAL, PESO_FINANCAS, PESO_OCUPACAO = 0.30, 0.25, 0.25, 0.20
AMIGOS_REF = engine.MAX_AMIGOS // 2     # com metade do máximo de amigos a dimensão de amizades já é plena
PATRIMONIO_REF = 240.0                  # patrimônio (em salários mínimos) que enche a barra de patrimônio (escala log)


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def cognition_avg(c: Character) -> float:
    return sum(c.cognition.values()) / len(c.cognition) if c.cognition else 0.0


def friends_alive(game: Game, c: Character) -> int:
    return sum(1 for i in game.friend_ids(c.id) if game.characters[i].alive)


def _relatives_alive(game: Game, c: Character) -> bool:
    outros = [*game.parents_of(c), *game.children_of(c.id)]
    conj = game.characters.get(c.spouse_id)
    if conj is not None:
        outros.append(conj)
    return any(o.alive for o in outros)


def social_score(game: Game, c: Character) -> float:
    """Amizades (50%), vínculo próximo — cônjuge/namoro, ou um responsável vivo para menores (30%) — e família viva (20%)."""
    amigos = min(1.0, friends_alive(game, c) / AMIGOS_REF)
    age = c.age_at(game.year, game.month)
    if age < 18:
        vinculo = 1.0 if any(p.alive for p in game.parents_of(c)) else 0.0
    else:
        vinculo = 1.0 if (engine.has_active_spouse(game, c) or romance.partner_of(game, c) is not None) else 0.0
    familia = 1.0 if _relatives_alive(game, c) else 0.0
    return 100.0 * (0.5 * amigos + 0.3 * vinculo + 0.2 * familia)


def wealth_score(game: Game, c: Character) -> float:
    """Patrimônio em salários mínimos vigentes, em escala logarítmica (dívida = 0)."""
    w = c.wealth / macro.min_wage(game)
    if w <= 0:
        return 0.0
    return _clamp(100.0 * math.log10(1 + w) / math.log10(1 + PATRIMONIO_REF))


def finance_score(game: Game, c: Character, household: dict | None = None) -> float:
    """Folga do domicílio: (renda − impostos) / custo de vida. 1,5× o custo ou mais = 100; dívida pessoal desconta 20%."""
    h = household if household is not None else economy.household_of(game, c)
    if h is None:
        return 0.0
    if h["cost"] <= 0:
        s = 60.0
    else:
        s = _clamp(100.0 * ((h["income"] - h["imposto"]) / h["cost"]) / 1.5)
    return s * 0.8 if c.wealth < 0 else s


def occupation_score(game: Game, c: Character, age: int | None = None) -> float:
    if age is None:
        age = c.age_at(game.year, game.month)
    now = game.year * 12 + game.month
    if age < 6:
        return 90.0
    if work.is_student(c):
        return 80.0
    if c.retired:
        return 85.0
    if work.is_employed(c):
        return 100.0 if not c.informal else 85.0
    if economy.on_leave(c, now):
        return 70.0
    if economy.receiving_unemployment(c, now):
        return 45.0
    if work.is_seeking(c):
        return 30.0
    return 60.0 if age < work.IDADE_TRABALHO_MIN else 50.0


def wellbeing(game: Game, c: Character, household: dict | None = None) -> float:
    """Bem-estar (0–100) = 30% saúde + 25% vida social + 25% folga financeira + 20% ocupação."""
    age = c.age_at(game.year, game.month)
    return _clamp(PESO_SAUDE * c.health + PESO_SOCIAL * social_score(game, c)
                  + PESO_FINANCAS * finance_score(game, c, household) + PESO_OCUPACAO * occupation_score(game, c, age))


def bars(game: Game, c: Character, household: dict | None = None) -> dict[str, float]:
    """As cinco barras do kit: saúde, cognição, social, patrimônio e felicidade (bem-estar)."""
    return {
        "saude": _clamp(c.health),
        "cognicao": _clamp(cognition_avg(c)),
        "social": social_score(game, c),
        "patrimonio": wealth_score(game, c),
        "felicidade": wellbeing(game, c, household),
    }
