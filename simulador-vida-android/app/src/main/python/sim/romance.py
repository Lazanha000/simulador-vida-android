"""Namoro (v0.11.0): casais antes do casamento.

Solteiros (>= 16 anos, sem cônjuge ativo, sem parceiro) formam casais, que podem terminar ou
virar casamento. Não usa `game.rng`: o sorteio vem de um gerador local por (semente, mês, sal, id),
então o namoro não altera o fluxo do RNG principal e carregar/continuar segue idêntico.
Todas as probabilidades são ILUSTRATIVAS, não estatística oficial.
"""
from __future__ import annotations

import random

from .models import Character, Game

ATIVO = True              # interruptor: False = comportamento da v0.10.0 (sem namoro)
IDADE_MIN = 16
DIFERENCA_MENOR_18 = 3    # anos de diferença máxima se algum dos dois tem < 18 anos
# Probabilidade ANUAL de um solteiro tomar a iniciativa de um namoro, por faixa etária.
NAMORO = [(16, 0.30), (25, 0.22), (35, 0.10), (50, 0.04)]
TERMINO_BASE = 0.35       # probabilidade anual-base de um casal terminar
MESES_ANTES_CASAR = 6     # tempo mínimo de namoro antes do pedido
# Probabilidade ANUAL de o casal (>= 6 meses, ambos >= 18 anos) se casar, pela idade do mais novo.
CASAR = [(18, 0.06), (22, 0.13), (30, 0.13), (40, 0.05), (50, 0.02)]
CHANCE_FORA_DO_CIRCULO = 0.25  # conhecer alguém fora do círculo se ele não tem par compatível


def _anual(tabela, idade: int) -> float:
    p = 0.0
    for inicio, prob in tabela:
        if idade >= inicio:
            p = prob
    return p


def _mensal(p: float) -> float:
    return 1 - (1 - min(0.99, max(0.0, p))) ** (1 / 12)


def _rng(game: Game, sal: str, cid: int) -> random.Random:
    return random.Random(f"{game.seed}:namoro:{game.year * 12 + game.month}:{sal}:{cid}")


def dating_monthly(c: Character, age: int) -> float:
    """Chance mensal de iniciar um namoro: maior com extroversão alta (×0,6–×1,4)."""
    return _mensal(_anual(NAMORO, age) * (0.6 + 0.8 * c.personality["extroversao"] / 100))


def breakup_monthly(a: Character, b: Character, meses: int) -> float:
    """Chance mensal de o casal terminar: sobe com baixa afinidade e neuroticismo, cai com a duração."""
    from . import engine
    mult = (1.7 - engine.affinity(a, b)) * (0.7 + 0.6 * (a.personality["neuroticismo"]
                                                         + b.personality["neuroticismo"]) / 200)
    if meses >= 24:
        mult *= 0.5
    return _mensal(TERMINO_BASE * mult)


def marry_monthly(idade_menor: int, meses: int) -> float:
    if meses < MESES_ANTES_CASAR or idade_menor < 18:
        return 0.0
    return _mensal(_anual(CASAR, idade_menor))


def partner_of(game: Game, c: Character) -> Character | None:
    """Parceiro de namoro vivo (vínculo mútuo), ou None."""
    p = game.characters.get(c.partner_id) if c.partner_id is not None else None
    return p if p is not None and p.alive and p.partner_id == c.id else None


def _eligible(game: Game, c: Character, now: tuple[int, int]) -> bool:
    from . import engine
    return (c.alive and c.partner_id is None and c.age_at(*now) >= IDADE_MIN
            and not engine.has_active_spouse(game, c))


def compatible(game: Game, a: Character, b: Character, now: tuple[int, int]) -> bool:
    from . import engine
    ia, ib = a.age_at(*now), b.age_at(*now)
    if min(ia, ib) < 18 and abs(ia - ib) > DIFERENCA_MENOR_18:
        return False
    return engine._can_marry(a, b, now, game)


def _clear(*chars: Character) -> None:
    for c in chars:
        c.partner_id, c.partner_since = None, None


def _meses(game: Game, c: Character) -> int:
    return game.year * 12 + game.month - (c.partner_since or 0)


def start(game: Game, a: Character, b: Character) -> None:
    a.partner_id, b.partner_id = b.id, a.id
    a.partner_since = b.partner_since = game.year * 12 + game.month
    game.add_event(a.id, "namoro", f"Começou a namorar {b.full_name}.")
    game.add_event(b.id, "namoro", f"Começou a namorar {a.full_name}.")


def run(game: Game) -> None:
    """Namoros do mês (depois dos divórcios, antes dos casamentos): luto/limpeza, términos e pedidos
    de casamento dos casais existentes (menor id primeiro) e novos casais. Em ordem de id."""
    from . import engine
    now = (game.year, game.month)
    chars = sorted(game.characters.values(), key=lambda x: x.id)
    # 1) vínculos desfeitos: parceiro morto (ou casado por outro caminho)
    for c in chars:
        if c.partner_id is None:
            continue
        p = game.characters.get(c.partner_id)
        if not c.alive:
            _clear(c)
        elif p is not None and not p.alive:
            game.add_event(c.id, "namoro_fim", f"{p.full_name} (parceiro(a) de namoro) faleceu.")
            _clear(c)
        elif p is None or p.partner_id != c.id or engine.has_active_spouse(game, c):
            _clear(c)
    # 2) casais existentes: término ou casamento
    for c in chars:
        p = partner_of(game, c)
        if p is None or c.id > p.id:
            continue
        meses = _meses(game, c)
        rng = _rng(game, "casal", c.id)
        if rng.random() < breakup_monthly(c, p, meses):
            game.add_event(c.id, "namoro_fim", f"Terminou o namoro com {p.full_name}.")
            game.add_event(p.id, "namoro_fim", f"Terminou o namoro com {c.full_name}.")
            _clear(c, p)
        elif rng.random() < marry_monthly(min(c.age_at(*now), p.age_at(*now)), meses):
            for x, y in ((c, p), (p, c)):
                game.add_event(x.id, "namoro", f"Depois de {meses} meses de namoro, decidiu se casar com {y.full_name}.")
            _clear(c, p)
            engine._marry(game, c, p)
    # 3) novos casais
    livres = [c for c in chars if _eligible(game, c, now)]
    formados: set[int] = set()
    for c in livres:
        if c.id in formados or c.partner_id is not None:
            continue
        rng = _rng(game, "novo", c.id)
        if rng.random() >= dating_monthly(c, c.age_at(*now)):
            continue
        cands = [o for o in livres if o.id != c.id and o.id not in formados
                 and o.partner_id is None and compatible(game, c, o, now)]
        if engine.CIRCULO_SOCIAL:
            circulo = engine.social_circle(game, c)
            no_circulo = [o for o in cands if o.id in circulo]
            if no_circulo:
                cands = no_circulo
            elif not cands or rng.random() >= CHANCE_FORA_DO_CIRCULO:
                continue
        if not cands:
            continue
        o = rng.choices(cands, weights=[engine.affinity(c, x) for x in cands])[0]
        start(game, c, o)
        formados.update((c.id, o.id))
