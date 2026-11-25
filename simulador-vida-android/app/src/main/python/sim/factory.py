"""Criação de personagens e famílias."""
from __future__ import annotations

from . import economy, work
from .models import COGNICAO, MESES, PERSONALIDADE, Character, Family, Game

NOMES_F = ["Maria", "Ana", "Juliana", "Fernanda", "Camila", "Aline", "Patrícia",
           "Luciana", "Beatriz", "Larissa", "Helena", "Sofia"]
NOMES_M = ["José", "João", "Carlos", "Pedro", "Lucas", "Rafael", "Marcos",
           "Gabriel", "Mateus", "Paulo", "Felipe", "Bruno"]
SOBRENOMES = ["Silva", "Santos", "Oliveira", "Souza", "Pereira", "Costa",
              "Rodrigues", "Almeida", "Nascimento", "Lima", "Ribeiro", "Carvalho"]

IDADE_MAX = 110

# Herança: filho = média + H * (média dos pais - média) + ruído. Variância total preservada.
HERDABILIDADE_PERSONALIDADE = 0.4
HERDABILIDADE_COGNICAO = 0.5
RUIDO_HERANCA = 14.0


def cognition_development(age: int) -> float:
    """Fração do potencial cognitivo já desenvolvida na idade `age` (35% ao nascer, 100% aos 18)."""
    return min(1.0, 0.35 + 0.65 * max(0, age) / 18)


def _score(game: Game, mean: float = 50, sd: float = 15) -> int:
    return int(min(99, max(1, round(game.rng.gauss(mean, sd)))))


def _inherit(game: Game, midparent: float, h: float) -> int:
    v = 50 + h * (midparent - 50) + game.rng.gauss(0, RUIDO_HERANCA)
    return int(min(99, max(1, round(v))))


def default_schooling(age: int, personality: dict, cognition: dict) -> tuple[int, bool]:
    """(anos concluídos, cursando) de quem entra na simulação já com `age` anos. Determinístico
    (sem RNG). Crianças de 6–17 anos estão na série da idade; adultos recebem 12, 9 ou 5 anos
    conforme cognição média e conscienciosidade. Valores ILUSTRATIVOS."""
    if age < 6:
        return 0, False
    if age < 18:
        return age - 6, True
    m = sum(cognition.values()) / len(cognition)
    score = 0.5 * m + 0.5 * personality["conscienciosidade"]
    return (12 if score >= 43 else 9 if score >= 36 else 5), False


def new_game(name: str, seed: int, year: int = 2026, month: int = 1) -> Game:
    if not 1 <= month <= 12:
        raise ValueError("mês inválido")
    return Game(name=name, seed=seed, year=year, month=month)


def create_character(game: Game, age: int, sex: str | None = None,
                     first_name: str | None = None, last_name: str | None = None,
                     family_id: int | None = None, mother_id: int | None = None,
                     father_id: int | None = None,
                     birth: tuple[int, int] | None = None,
                     inherit_from: tuple[Character, Character] | None = None) -> Character:
    """Cria um personagem. `birth=(ano, mês)` fixa a data de nascimento (usado nos
    nascimentos durante a simulação; exige idade 0 e não sorteia o mês)."""
    if birth is not None and age != 0:
        raise ValueError("birth só pode ser usado com idade 0")
    if not 0 <= age <= IDADE_MAX:
        raise ValueError(f"idade deve estar entre 0 e {IDADE_MAX}")
    if sex is None:
        sex = game.rng.choice("FM")
    sex = sex.upper()
    if sex not in ("F", "M"):
        raise ValueError("sexo deve ser 'F' ou 'M'")

    if first_name is None:
        first_name = game.rng.choice(NOMES_F if sex == "F" else NOMES_M)
    if last_name is None:
        last_name = game.rng.choice(SOBRENOMES)

    # Data de nascimento coerente com a idade na data atual do jogo.
    if birth is not None:
        birth_year, birth_month = birth
    else:
        birth_month = game.rng.randint(1, 12)
        birth_year = game.year - age - (1 if birth_month > game.month else 0)

    health = min(100.0, max(20.0, 100 - max(0, age - 30) * 0.5 + game.rng.gauss(0, 5)))

    potential = {k: _score(game) for k in COGNICAO}
    personality = {t: _score(game) for t in PERSONALIDADE}
    if inherit_from is not None:  # nascimento: traços vindos dos pais (ver constantes acima)
        pa, pb = inherit_from
        personality = {t: _inherit(game, (pa.personality[t] + pb.personality[t]) / 2,
                                   HERDABILIDADE_PERSONALIDADE) for t in PERSONALIDADE}
        potential = {k: _inherit(game, (pa.cognition_potential[k] + pb.cognition_potential[k]) / 2,
                                 HERDABILIDADE_COGNICAO) for k in COGNICAO}
    dev = cognition_development(age)
    cognition = {k: int(min(99, max(1, round(v * dev)))) for k, v in potential.items()}

    c = Character(
        id=game.next_char_id,
        first_name=first_name,
        last_name=last_name,
        sex=sex,
        birth_year=birth_year,
        birth_month=birth_month,
        health=health,
        mother_id=mother_id,
        father_id=father_id,
        family_id=family_id,
        personality=personality,
        cognition=cognition,
        cognition_potential=dict(potential),
    )
    c.schooling_years, c.in_school = default_schooling(age, personality, cognition)
    game.next_char_id += 1
    game.characters[c.id] = c
    work.default_work(game, c)  # situação de trabalho inicial (sem usar game.rng)
    economy.initial_economy(game, c)  # carreira, renda e patrimônio iniciais (sem game.rng)

    game.add_event(c.id, "nascimento", f"Nasceu em {MESES[birth_month - 1]} de {birth_year}.",
                   year=birth_year, month=birth_month)
    if age > 0:
        game.add_event(c.id, "criacao", f"Entrou na simulação aos {age} anos.")
    return c


def create_family(game: Game, surname: str | None = None, n_children: int = 2) -> dict:
    """Cria mãe, pai e filhos com datas de nascimento coerentes (pais >= 16 anos mais velhos)."""
    if not 0 <= n_children <= 10:
        raise ValueError("número de filhos deve estar entre 0 e 10")
    if surname is None:
        surname = game.rng.choice(SOBRENOMES)

    fam = Family(id=game.next_family_id, name=f"Família {surname}")
    game.next_family_id += 1
    game.families[fam.id] = fam

    mother_age = game.rng.randint(25, 45)
    father_age = game.rng.randint(25, 48)
    mother = create_character(game, mother_age, "F", last_name=surname, family_id=fam.id)
    father = create_character(game, father_age, "M", last_name=surname, family_id=fam.id)
    mother.spouse_id, father.spouse_id = father.id, mother.id

    max_child_age = min(17, mother_age - 16, father_age - 16)
    ages = sorted((game.rng.randint(0, max_child_age) for _ in range(n_children)), reverse=True)
    children = [
        create_character(game, a, last_name=surname, family_id=fam.id,
                         mother_id=mother.id, father_id=father.id)
        for a in ages
    ]

    if game.player_id is None:
        game.player_id = children[0].id if children else mother.id
    return {"family": fam, "mother": mother, "father": father, "children": children}
