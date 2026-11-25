"""Conversar com um amigo (G3b, v0.15.4).

Escolha e consequência: o jogador escolhe um amigo vivo e conversa (1 vez por mês por amigo). Efeito: a amizade
esfria com metade da chance por 12 meses após a última conversa (engine._friendship_drift); +0,2 de saúde
(ILUSTRATIVO); evento na biografia dos dois. Estado: `game.convivio` {(a,b): último mês (ano*12+mês)}.
Convidar (G3c, v0.15.6): sair com o amigo; conta como a conversa do mês (mesmo limite) e é mais forte: a amizade esfria
com 30% da chance por 12 meses, +0,5 de saúde; custa 3% do salário mínimo (R$ 45 com o mínimo de R$ 1.500; adultos; menores
não pagam) e exige patrimônio suficiente. Estado: `game.convites`, igual ao `convivio`.
Memória do relacionamento (G3f, v0.15.9): cada conversa/convite soma 1 em `game.memoria` {(a,b): interações}.
Com ≥6 interações a amizade vira "próxima": chance de esfriar ×0,7 para sempre (além dos efeitos acima).
Sem conversa o mundo fica idêntico ao de antes (o número de sorteios do `game.rng` não muda).
"""
from __future__ import annotations

from .models import Game

MESES_EFEITO = 12
INTERACOES_PROXIMO = 6


def _chave(a: int, b: int) -> tuple[int, int]:
    return (min(a, b), max(a, b))


def _mes(game: Game) -> int:
    return game.year * 12 + game.month


def recente(game: Game, a: int, b: int) -> bool:
    ultimo = game.convivio.get(_chave(a, b))
    return ultimo is not None and _mes(game) - ultimo < MESES_EFEITO


def fator(game: Game, a: int, b: int) -> float:
    """Multiplicador da chance de a amizade esfriar (1,0 sem interação recente)."""
    k = _chave(a, b)
    ultimo = game.convites.get(k)
    if ultimo is not None and _mes(game) - ultimo < MESES_EFEITO:
        return 0.3 * (0.7 if proximo(game, a, b) else 1.0)
    base = 0.5 if recente(game, a, b) else 1.0
    return base * (0.7 if proximo(game, a, b) else 1.0)


def proximo(game: Game, a: int, b: int) -> bool:
    return game.memoria.get(_chave(a, b), 0) >= INTERACOES_PROXIMO


def custo_convite(game: Game, p) -> float:
    if p.age_at(game.year, game.month) < 18:
        return 0.0
    return round(0.03 * game.macro["min_wage"], 2)


def amigos(game: Game) -> list[dict]:
    p = game.characters.get(game.player_id) if game.player_id is not None else None
    if p is None or not p.alive:
        return []
    now = (game.year, game.month)
    out = []
    for i in sorted(game._friends.get(p.id, ())):
        o = game.characters[i]
        if o.alive:
            out.append({"id": i, "nome": o.full_name, "idade": o.age_at(*now),
                        "conversou": game.convivio.get(_chave(p.id, i)) == _mes(game),
                        "custo": custo_convite(game, p),
                        "interacoes": game.memoria.get(_chave(p.id, i), 0), "proximo": proximo(game, p.id, i)})
    return out


def conversar(game: Game, amigo_id: int) -> dict:
    p = game.characters.get(game.player_id) if game.player_id is not None else None
    if p is None or not p.alive:
        raise ValueError("Nenhum personagem vivo do jogador.")
    o = game.characters.get(amigo_id)
    if o is None or not o.alive or not game.are_friends(p.id, amigo_id):
        raise ValueError("Essa pessoa não é um amigo vivo.")
    k = _chave(p.id, amigo_id)
    if game.convivio.get(k) == _mes(game):
        raise ValueError(f"Você já conversou com {o.first_name} neste mês.")
    game.convivio[k] = _mes(game)
    game.memoria[k] = game.memoria.get(k, 0) + 1
    from . import vinculos
    vinculos.registrar_evento(game, p.id, o.id, "Conversa de amizade", afinidade=5, confianca=3, intimidade=4, hostilidade=-2)
    p.health = min(100.0, p.health + 0.2)
    game.add_event(p.id, "amizade", f"Passou um tempo conversando com {o.full_name}.")
    game.add_event(o.id, "amizade", f"Passou um tempo conversando com {p.full_name}.")
    return {"id": o.id, "nome": o.full_name}


def convidar(game: Game, amigo_id: int) -> dict:
    p = game.characters.get(game.player_id) if game.player_id is not None else None
    if p is None or not p.alive:
        raise ValueError("Nenhum personagem vivo do jogador.")
    o = game.characters.get(amigo_id)
    if o is None or not o.alive or not game.are_friends(p.id, amigo_id):
        raise ValueError("Essa pessoa não é um amigo vivo.")
    k = _chave(p.id, amigo_id)
    if game.convivio.get(k) == _mes(game):
        raise ValueError(f"Você já passou um tempo com {o.first_name} neste mês.")
    custo = custo_convite(game, p)
    if p.wealth < custo:
        raise ValueError("Patrimônio insuficiente para o convite.")
    p.wealth -= custo
    game.convivio[k] = _mes(game)
    game.convites[k] = _mes(game)
    game.memoria[k] = game.memoria.get(k, 0) + 1
    from . import vinculos
    vinculos.registrar_evento(game, p.id, o.id, "Saíram juntos", afinidade=9, confianca=5, intimidade=7, hostilidade=-4)
    p.health = min(100.0, p.health + 0.5)
    game.add_event(p.id, "amizade", f"Saiu com {o.full_name} (convite).")
    game.add_event(o.id, "amizade", f"Saiu com {p.full_name} (convite).")
    return {"id": o.id, "nome": o.full_name, "custo": custo}
