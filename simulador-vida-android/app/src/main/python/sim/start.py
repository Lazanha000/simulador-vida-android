"""Modos de início de partida (v0.14.0).

Orquestra `factory` e `engine` para o jogador começar a vida de três jeitos:
  - `start_newborn`: nascer agora numa família (pais, irmãos mais velhos) — o início clássico de simulador de vida;
  - `start_adult`: um personagem avulso de qualquer idade (comportamento da CLI);
  - `start_family`: uma família pronta (comportamento da CLI).
Usa `game.rng` (como o resto da criação); não há regras de simulação novas aqui.
"""
from __future__ import annotations

from . import engine, factory
from .models import Character, Family, Game

MAX_IRMAOS_NASCER = 5


def start_adult(game: Game, age: int, sex: str | None = None, first_name: str | None = None,
                last_name: str | None = None) -> Character:
    c = factory.create_character(game, age, sex, first_name, last_name)
    game.player_id = c.id
    return c


def start_family(game: Game, surname: str | None = None, n_children: int = 2) -> dict:
    return factory.create_family(game, surname, n_children)   # define o jogador se ainda não houver um


def start_newborn(game: Game, surname: str | None = None, siblings: int = 1, sex: str | None = None,
                  first_name: str | None = None) -> dict:
    """O jogador nasce AGORA (mês corrente) numa família nova: mãe em idade fértil (22–40), pai, até 5 irmãos mais
    velhos (idades distintas, mãe com ≥18 anos ao nascimento de cada um) e o recém-nascido, que herda personalidade e
    potencial cognitivo dos pais como qualquer filho nascido na simulação."""
    if not 0 <= siblings <= MAX_IRMAOS_NASCER:
        raise ValueError(f"número de irmãos deve estar entre 0 e {MAX_IRMAOS_NASCER}")
    rng = game.rng
    if surname is None:
        surname = rng.choice(factory.SOBRENOMES)
    fam = Family(id=game.next_family_id, name=f"Família {surname}")
    game.next_family_id += 1
    game.families[fam.id] = fam

    mother_age = rng.randint(22, 40)
    father_age = rng.randint(max(22, mother_age - 4), min(50, mother_age + 8))
    mother = factory.create_character(game, mother_age, "F", last_name=surname, family_id=fam.id)
    father = factory.create_character(game, father_age, "M", last_name=surname, family_id=fam.id)
    mother.spouse_id, father.spouse_id = father.id, mother.id

    vagas = list(range(1, min(17, mother_age - 18) + 1))   # idades possíveis dos irmãos
    n = min(siblings, len(vagas))
    ages = sorted(rng.sample(vagas, n), reverse=True)
    irmaos = [factory.create_character(game, a, last_name=surname, family_id=fam.id,
                                       mother_id=mother.id, father_id=father.id) for a in ages]

    child = factory.create_character(
        game, 0, sex, first_name, father.last_name, family_id=fam.id, mother_id=mother.id, father_id=father.id,
        birth=(game.year, game.month), inherit_from=(mother, father))
    for parent in (mother, father):
        verbo = "Deu à luz" if parent is mother else "Nasceu"
        game.add_event(parent.id, "nascimento_filho", f"{verbo} {child.full_name} ({engine._relation(child, parent)}).")
    game.player_id = child.id
    return {"family": fam, "mother": mother, "father": father, "siblings": irmaos, "child": child}
