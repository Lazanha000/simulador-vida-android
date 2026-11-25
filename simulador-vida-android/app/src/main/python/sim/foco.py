"""Foco do período (G2, v0.15.1): o jogador escolhe em que o personagem investe o tempo. Vale até mudar.

Escolha e consequência (valores ILUSTRATIVOS; sorteios por gerador local, sem consumir `game.rng`):
- estudar:   +6 no desempenho escolar (engine.school_performance); 20%/mês de +1 em memória, aprendizagem,
             compreensão verbal ou raciocínio lógico (até o potencial); custo: -0,1 de saúde/mês.
- trabalhar: se empregado, "horas extras": +3% da renda/mês no patrimônio; custo: -0,15 de saúde/mês.
- socializar: 1,5× a chance mensal de fazer amizade (engine._friendships); sem custo.
- descansar: +0,4 de saúde/mês (até 100); custo de oportunidade: nenhum dos ganhos acima.
- equilibrado (padrão): nada muda.
- área de estudo (G2b, v0.15.2; só vale com foco estudar): linguagens → compreensão verbal, humanas → memória,
  natureza → aprendizagem, matemática → raciocínio lógico. Com área, o +1 mensal (25%) vai SEMPRE para a
  habilidade da área; "geral" (padrão) mantém o sorteio entre as 4 (20%). Áreas = as 4 do ENEM (proposta
  ainda não confirmada pelo dono; é só a tabela AREAS).
"""
from __future__ import annotations

import random

from . import engine
from .models import Game

FOCOS = {"equilibrado": "Equilibrado", "estudar": "Estudar", "trabalhar": "Trabalhar",
         "socializar": "Socializar", "descansar": "Descansar"}
_COG = ("memoria", "aprendizagem", "compreensao_verbal", "raciocinio_logico")
AREAS = {"geral": ("Geral", None), "linguagens": ("Linguagens", "compreensao_verbal"),
         "humanas": ("Humanas", "memoria"), "natureza": ("Natureza", "aprendizagem"),
         "matematica": ("Matemática", "raciocinio_logico")}


def definir(game: Game, nome: str, area: str | None = None) -> None:
    if nome not in FOCOS:
        raise ValueError("Foco inválido.")
    if area is not None and area not in AREAS:
        raise ValueError("Área de estudo inválida.")
    if game.player_id is None:
        raise ValueError("Nenhum personagem do jogador.")
    game.foco[game.player_id] = nome
    if area is not None:
        game.area[game.player_id] = area


def atual(game: Game, cid: int | None = None) -> str:
    return game.foco.get(game.player_id if cid is None else cid, "equilibrado")


def area_atual(game: Game, cid: int | None = None) -> str:
    return game.area.get(game.player_id if cid is None else cid, "geral")


def view(game: Game) -> dict:
    return {"atual": atual(game), "opcoes": [{"id": k, "rotulo": v} for k, v in FOCOS.items()],
            "area": area_atual(game), "areas": [{"id": k, "rotulo": v[0]} for k, v in AREAS.items()]}


def mensal(game: Game, c) -> None:
    """Efeitos do foco no mês (chamado pelo `views.avancar` para o personagem do jogador vivo)."""
    if c is None or not c.alive:
        return
    f = atual(game, c.id)
    r = random.Random(f"foco:{game.seed}:{game.year * 12 + game.month}:{c.id}")
    if f == "estudar":
        c.health = max(0.0, c.health - 0.1)
        k_area = AREAS[area_atual(game, c.id)][1]
        if r.random() < (0.35 if k_area else 0.28):
            k = k_area or r.choice(_COG)
            if c.cognition.get(k, 99) < 99:
                engine.treinar_cognicao(c, k, 1, elevar_potencial=True)
    elif f == "trabalhar":
        if c.occupation and not c.retired and c.income > 0:
            c.wealth += 0.03 * c.income
            c.health = max(0.0, c.health - 0.15)
    elif f == "descansar":
        c.health = min(100.0, c.health + 0.4)
