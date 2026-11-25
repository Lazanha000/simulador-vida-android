"""Ciclo econômico (v0.9.0): um índice anual que sobe e desce e modula o mercado de trabalho.

O índice de cada ano é um processo autorregressivo (AR(1)) gerado SÓ a partir da semente da partida e do
ano: determinístico, sem `game.rng` (carregar e continuar é idêntico) e sem nada para salvar. Vale -1
(recessão profunda) a +1 (expansão forte), média ≈ 0. Valores e sensibilidades ILUSTRATIVOS; nenhum dado real.

Efeitos (aplicados pelo motor e por `firms`): contratação, demissões, fechamento de empresas e vacância-alvo.
"""
from __future__ import annotations

import random

ATIVO = True               # interruptor: False = v0.8.0 (mercado sem ciclo)
ANO_BASE = 1990            # a cadeia começa em 0 neste ano
PERSISTENCIA = 0.55        # quanto do índice do ano anterior se mantém (ciclos duram alguns anos)
RUIDO = 0.5                # desvio do choque anual
LIMITE = 1.0               # índice truncado em [-LIMITE, +LIMITE]
LIMIAR_RECESSAO = -0.45
LIMIAR_EXPANSAO = 0.45

SENS_CONTRATACAO = 0.45    # contratação × (1 + 0,45·índice)  → 0,55 … 1,45
SENS_DEMISSAO = 0.50       # demissão    × (1 − 0,50·índice)  → 0,50 … 1,50
SENS_FECHAMENTO = 0.80     # fechamento  × (1 − 0,80·índice)  → 0,20 … 1,80
SENS_VACANCIA = 0.50       # vacância-alvo × (1 + 0,50·índice) → 0,50 … 1,50

_cache: dict[tuple[int, int], float] = {}


def index(seed: int, year: int) -> float:
    """Índice do ano (determinístico por semente e ano; anos até `ANO_BASE` valem 0)."""
    if year <= ANO_BASE:
        return 0.0
    v, y0 = 0.0, ANO_BASE
    for y in range(year, ANO_BASE, -1):  # acha o ano mais recente já calculado
        if (seed, y) in _cache:
            v, y0 = _cache[(seed, y)], y
            break
    for y in range(y0 + 1, year + 1):
        ruido = random.Random(f"{seed}:cycle:{y}").gauss(0.0, RUIDO)
        v = max(-LIMITE, min(LIMITE, PERSISTENCIA * v + ruido))
        _cache[(seed, y)] = v
    return _cache[(seed, year)]


def current(game) -> float:
    """Índice do ano corrente da partida (0 com o ciclo desligado)."""
    return index(game.seed, game.year) if ATIVO else 0.0


def label(idx: float) -> str:
    if idx <= LIMIAR_RECESSAO:
        return "recessão"
    if idx >= LIMIAR_EXPANSAO:
        return "expansão"
    return "estabilidade"


def hire_factor(idx: float) -> float:
    return 1 + SENS_CONTRATACAO * idx


def separation_factor(idx: float) -> float:
    return 1 - SENS_DEMISSAO * idx


def closure_factor(idx: float) -> float:
    return 1 - SENS_FECHAMENTO * idx


def vacancy_factor(idx: float) -> float:
    return 1 + SENS_VACANCIA * idx
