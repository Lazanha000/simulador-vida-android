"""Macroeconomia (v0.13.0): inflação anual, índice de preços, salário mínimo dinâmico e orçamento do Estado.

Tudo ILUSTRATIVO. Determinístico por (semente, ano): nada aqui usa `game.rng`, então salvar/carregar/continuar
segue idêntico. O estado vive em `game.macro` (dict simples, salvo em `meta`).

Mecanismo: os preços (custo de vida) sobem todo mês; os salários e benefícios são múltiplos do salário mínimo,
que só é reajustado em janeiro (inflação do ano anterior + ganho real ligado ao ciclo). Resultado: o poder de
compra cai ao longo do ano e é recomposto em janeiro; o patrimônio rende a taxa real + inflação.
"""
from __future__ import annotations

import random

from . import cycle

ATIVO = True
SALARIO_MINIMO_BASE = 1500.0
INFLACAO_BASE, INFLACAO_CICLO, INFLACAO_RUIDO = 0.045, 0.02, 0.012   # a.a.: base + ciclo×índice + ruído
INFLACAO_MIN, INFLACAO_MAX = 0.01, 0.12
GANHO_REAL_BASE, GANHO_REAL_CICLO = 0.01, 0.01                        # reajuste real do mínimo (base + ciclo)


def annual_rate(game) -> float:
    """Inflação anual do ano corrente (0 com o módulo desligado). Determinística por (semente, ano)."""
    if not ATIVO:
        return 0.0
    rng = random.Random(f"{game.seed}:inflacao:{game.year}")
    r = INFLACAO_BASE + INFLACAO_CICLO * cycle.index(game.seed, game.year) + rng.gauss(0, INFLACAO_RUIDO)
    return round(min(INFLACAO_MAX, max(INFLACAO_MIN, r)), 4)


def monthly_rate(game) -> float:
    return (1 + annual_rate(game)) ** (1 / 12) - 1 if ATIVO else 0.0


def price_level(game) -> float:
    """Índice de preços acumulado (1,0 no início da partida)."""
    return game.macro["price_level"] if ATIVO else 1.0


def min_wage(game) -> float:
    """Salário mínimo nominal vigente."""
    return game.macro["min_wage"] if ATIVO else SALARIO_MINIMO_BASE


def real_min_wage(game) -> float:
    """Salário mínimo em poder de compra do início da partida."""
    return min_wage(game) / price_level(game)


def tick(game) -> None:
    """Um mês de macroeconomia (chamar ANTES de `economy.apply_month`): em janeiro reajusta o salário mínimo e
    fecha o ano fiscal; todo mês sobe o índice de preços."""
    if not ATIVO:
        return
    m = game.macro
    if game.month == 1:
        infl = m["price_level"] / m["p_ref"] - 1
        m["inflation_prev"] = round(infl, 4)
        ganho = GANHO_REAL_BASE + GANHO_REAL_CICLO * max(0.0, cycle.current(game))
        m["min_wage"] = round(m["min_wage"] * (1 + infl + ganho), 2)
        m["p_ref"] = m["price_level"]
        m["rec_prev"], m["desp_prev"] = m["rec"], m["desp"]
        m["rec"], m["desp"] = 0.0, 0.0
    m["price_level"] *= 1 + monthly_rate(game)


def record_fiscal(game, receita: float, despesa: float) -> None:
    m = game.macro
    m["rec"] += receita
    m["desp"] += despesa
    m["treasury"] += receita - despesa
