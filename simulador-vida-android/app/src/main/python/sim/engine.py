"""Motor de simulação: passagem do tempo, envelhecimento, saúde e morte.

Não conhece interface nem persistência. Toda aleatoriedade usa game.rng,
consumida em ordem determinística (ids crescentes), o que torna a simulação
reprodutível a partir da semente e do estado salvo do gerador.
"""
from __future__ import annotations

import random

from . import cycle, economy, factory, firms, macro, mundo, romance, work
from .models import MESES, BioEvent, Character, Game

ETAPAS = [(0, "bebê"), (3, "infância"), (12, "adolescência"),
          (18, "idade adulta"), (60, "velhice")]


def life_stage(age: int) -> str:
    nome = ETAPAS[0][1]
    for inicio, n in ETAPAS:
        if age >= inicio:
            nome = n
    return nome


def mortality_annual(age: int, health: float) -> float:
    """Probabilidade anual de morte. Valores ILUSTRATIVOS, não são estatística oficial."""
    if age < 1:
        p = 0.013
    elif age < 15:
        p = 0.0004
    elif age < 40:
        p = 0.0012
    elif age < 60:
        p = 0.0045
    elif age < 70:
        p = 0.011
    elif age < 80:
        p = 0.03
    elif age < 90:
        p = 0.085
    else:
        p = 0.20
    # Saúde 100 = risco da tabela; saúde 0 = o dobro.
    p *= 1 + (100 - health) / 100
    return min(p, 0.95)


def mortality_monthly(age: int, health: float) -> float:
    return 1 - (1 - mortality_annual(age, health)) ** (1 / 12)


def _relation(dead: Character, other: Character) -> str | None:
    """Parentesco de 'dead' em relação a 'other' (com possessivo), ou None."""
    if dead.id == other.spouse_id:
        return "sua esposa" if dead.sex == "F" else "seu marido"
    if dead.id == other.mother_id:
        return "sua mãe"
    if dead.id == other.father_id:
        return "seu pai"
    if other.id in (dead.mother_id, dead.father_id):
        return "sua filha" if dead.sex == "F" else "seu filho"
    shared = {dead.mother_id, dead.father_id} & {other.mother_id, other.father_id}
    shared.discard(None)
    if shared:
        return "sua irmã" if dead.sex == "F" else "seu irmão"
    return None


def _update_health(game: Game, c: Character, age: int) -> None:
    if age < 18:
        drift = 0.3
    elif age < 40:
        drift = 0.0
    elif age < 60:
        drift = -0.04
    else:
        drift = -0.08
    c.health = min(100.0, max(0.0, c.health + drift + game.rng.gauss(0, 0.4)))


def treinar_cognicao(c: Character, key: str, delta: int = 1, elevar_potencial: bool = True) -> int:
    """Aumenta uma habilidade cognitiva (1–99) e, quando treinada ativamente, eleva o potencial junto."""
    if key not in c.cognition or delta == 0:
        return 0
    antes = c.cognition[key]
    novo = int(max(1, min(99, antes + delta)))
    c.cognition[key] = novo
    if elevar_potencial and key in c.cognition_potential:
        c.cognition_potential[key] = int(min(99, max(c.cognition_potential[key], novo)))
    return novo - antes


def _develop_cognition(c: Character, age: int) -> None:
    """Até os 18 anos a cognição cresce em direção ao potencial sem apagar ganhos adquiridos."""
    if age > 18 or not c.cognition_potential:
        return
    dev = factory.cognition_development(age)
    c.cognition = {
        k: int(min(99, max(c.cognition.get(k, 1), round(v * dev))))
        for k, v in c.cognition_potential.items()
    }


def _birthday(game: Game, c: Character, age: int) -> None:
    _develop_cognition(c, age)
    if c.id == game.player_id:
        game.add_event(c.id, "aniversario", f"Fez {age} ano." if age == 1 else f"Fez {age} anos.")
    if life_stage(age) != life_stage(age - 1):
        game.add_event(c.id, "etapa_de_vida", f"Entrou na fase: {life_stage(age)}.")


def _die(game: Game, c: Character, age: int, cause: str = "") -> None:
    c.alive = False
    c.pregnant_until, c.pregnancy_father_id = None, None
    c.in_school = False
    c.in_college = False
    c.death_year, c.death_month = game.year, game.month
    game.add_event(c.id, "morte", f"Faleceu aos {age} anos{cause}.")
    if ECONOMIA:
        for heir, valor in economy.inherit(game, c):
            game.add_event(heir.id, "heranca",
                           f"Recebeu herança de {economy.fmt_brl(valor)} de {c.full_name} ({_relation(c, heir) or 'familiar'}).")
    for other in sorted(game.characters.values(), key=lambda x: x.id):
        if other.id == c.id or not other.alive:
            continue
        rel = _relation(c, other)
        if rel:
            game.add_event(other.id, "falecimento_familiar", f"Faleceu {c.full_name} ({rel}).")
        elif game.are_friends(c.id, other.id):
            game.add_event(other.id, "falecimento_amigo",
                           f"Faleceu {c.full_name} ({'sua amiga' if c.sex == 'F' else 'seu amigo'}).")


# --- nascimentos ------------------------------------------------------
# Probabilidade ANUAL de ter um filho, por faixa etária da mãe (casal ativo).
# Valores ILUSTRATIVOS, não são estatística oficial.
FERTILIDADE = [(15, 0.03), (20, 0.10), (25, 0.12), (30, 0.10), (35, 0.05), (40, 0.012)]
IDADE_FERTIL_MAX = 44
MAX_FILHOS = 10
# Risco de a mãe morrer no parto (ILUSTRATIVO); sobe com a idade e com a saúde baixa.
def maternal_death_risk(age: int, health: float) -> float:
    base = 0.0008 if age < 35 else 0.002 if age < 40 else 0.004
    return min(0.05, base * (1 + (100 - health) / 50))
GEMEOS = True            # interruptor: partos duplos (v0.10.0)
GEMEOS_CHANCE = 0.012    # chance de parto duplo (~1,2% dos partos; ILUSTRATIVA)
INTERVALO_MIN_MESES = 15  # meses mínimos entre dois partos da mesma mãe
GESTACAO = True           # interruptor: concepção → 9 meses → parto (v0.12.0); False = parto imediato (v0.11.0)
GESTACAO_MESES = 9
ABORTO_ESPONTANEO = 0.08  # fração das gestações perdidas no 3º mês (ILUSTRATIVA); a concepção compensa a perda
MES_PERDA = 3
# Licença-maternidade (v0.13.0; ILUSTRATIVA): mãe formal empregada tem 4 meses de licença paga pelo Estado e estabilidade
# durante a gestação e a licença; algumas mães deixam o emprego para cuidar do bebê (mais entre as informais).
LICENCA = True
LICENCA_MESES = 4
SAIDA_MAE_FORMAL, SAIDA_MAE_INFORMAL = 0.06, 0.25
AFASTAMENTO_SAIDA_MESES = 12   # quem deixa o emprego não procura trabalho por este prazo


def birth_annual(age: int) -> float:
    """Probabilidade anual de nascimento de um filho para uma mulher de `age` anos em casal."""
    if age > IDADE_FERTIL_MAX:
        return 0.0
    p = 0.0
    for inicio, prob in FERTILIDADE:
        if age >= inicio:
            p = prob
    return p


def birth_monthly(age: int) -> float:
    return 1 - (1 - birth_annual(age)) ** (1 / 12)


def conception_monthly(age: int) -> float:
    """Chance mensal de engravidar (v0.12.0): a taxa de nascimentos da faixa, corrigida pela perda
    gestacional para que o número de nascimentos por mulher se mantenha."""
    p = min(0.95, birth_annual(age) / (1 - ABORTO_ESPONTANEO))
    return 1 - (1 - p) ** (1 / 12)


def _can_conceive(game: Game, mother: Character, father: Character | None, age: int,
                  filhos: list[Character] | None = None) -> bool:
    if mother.sex != "F" or not mother.alive or birth_annual(age) == 0.0:
        return False
    if father is None or not father.alive or father.id != mother.spouse_id:
        return False
    if GESTACAO and mother.pregnant_until is not None:
        return False
    if filhos is None:
        filhos = game.children_of(mother.id)
    if len(filhos) >= MAX_FILHOS:
        return False
    now = game.year * 12 + game.month
    # Com gestação, o intervalo mínimo entre partos vale entre o parto anterior e a nova concepção - 9 meses.
    espera = INTERVALO_MIN_MESES - (GESTACAO_MESES if GESTACAO else 0)
    return all(now - (f.birth_year * 12 + f.birth_month) >= espera for f in filhos)


def _birth(game: Game, mother: Character, father: Character) -> Character:
    child = factory.create_character(
        game, 0, last_name=father.last_name, family_id=mother.family_id,
        mother_id=mother.id, father_id=father.id, birth=(game.year, game.month),
        inherit_from=(mother, father))
    for parent in (mother, father):
        if not parent.alive:   # pai que morreu durante a gestação
            continue
        rel = _relation(child, parent)
        verbo = "Deu à luz" if parent is mother else "Nasceu"
        game.add_event(parent.id, "nascimento_filho", f"{verbo} {child.full_name} ({rel}).")
    return child


def _abs_to_str(n: int) -> str:
    ano, mes = divmod(n - 1, 12)
    return f"{MESES[mes][:3]}/{ano}"


def _conceive(game: Game, mother: Character, father: Character) -> None:
    now = game.year * 12 + game.month
    mother.pregnant_until, mother.pregnancy_father_id = now + GESTACAO_MESES, father.id
    prev = _abs_to_str(mother.pregnant_until)
    game.add_event(mother.id, "gravidez", f"Engravidou de {father.full_name} (parto previsto: {prev}).")
    game.add_event(father.id, "gravidez", f"{mother.full_name} engravidou (parto previsto: {prev}).")


def _pregnancy_step(game: Game, mother: Character, age: int, filhos: list[Character]) -> None:
    """Gestação em curso: possível perda no 3º mês e parto no mês previsto. Os sorteios usam um gerador
    local por (semente, mês, mãe); só a criação do bebê consome `game.rng`."""
    now = game.year * 12 + game.month
    father = game.characters[mother.pregnancy_father_id]
    rng = random.Random(f"{game.seed}:parto:{now}:{mother.id}")
    if now - (mother.pregnant_until - GESTACAO_MESES) == MES_PERDA and rng.random() < ABORTO_ESPONTANEO:
        mother.pregnant_until, mother.pregnancy_father_id = None, None
        for p in (mother, father):
            if p.alive:
                game.add_event(p.id, "gravidez", "A gestação foi interrompida (perda gestacional).")
        return
    if now < mother.pregnant_until:
        return
    mother.pregnant_until, mother.pregnancy_father_id = None, None
    _birth(game, mother, father)
    if GEMEOS and len(filhos) + 2 <= MAX_FILHOS and rng.random() < GEMEOS_CHANCE:
        gemeo = _birth(game, mother, father)
        for parent in (mother, father):
            if parent.alive:
                game.add_event(parent.id, "gemeos", f"Os filhos nasceram gêmeos (parto duplo com {gemeo.full_name}).")
    if rng.random() < maternal_death_risk(age, mother.health):
        _die(game, mother, age, " em decorrência do parto")
    elif LICENCA:
        _maternity(game, mother, now, rng)


def _maternity(game: Game, mother: Character, now: int, rng: random.Random) -> None:
    """Efeito do parto no trabalho da mãe (v0.13.0). Usa o gerador local do parto: não consome `game.rng`."""
    if not work.is_employed(mother) or mother.retired:
        return
    ocupacao = work.occupation_name(mother.occupation, mother.sex)
    if rng.random() < (SAIDA_MAE_INFORMAL if mother.informal else SAIDA_MAE_FORMAL):
        work.clear_job(mother)
        mother.seeking_since = None
        mother.leave_until = now + AFASTAMENTO_SAIDA_MESES
        game.add_event(mother.id, "trabalho", f"Deixou o emprego ({ocupacao}) para cuidar do bebê.")
    elif not mother.informal:
        mother.leave_until = now + LICENCA_MESES - 1
        game.add_event(mother.id, "trabalho", f"Entrou em licença-maternidade de {LICENCA_MESES} meses (salário pago pelo Estado).")


def _births(game: Game) -> None:
    """Nascimentos do mês. Roda depois das mortes, em ordem de id; só consome o RNG
    das mães elegíveis (mulher viva em idade fértil, casal ativo, respeitando
    intervalo mínimo e limite de filhos). Recém-nascidos só entram na simulação no mês seguinte."""
    por_mae: dict[int, list[Character]] = {}  # índice único por mês (evita O(n²))
    for c in game.characters.values():
        if c.mother_id is not None:
            por_mae.setdefault(c.mother_id, []).append(c)
    for cid in sorted(game.characters):
        mother = game.characters[cid]
        if not mother.alive or mother.sex != "F":
            continue
        age = mother.age_at(game.year, game.month)
        if GESTACAO and mother.pregnant_until is not None:
            _pregnancy_step(game, mother, age, por_mae.get(mother.id, []))
            continue
        father = game.characters.get(mother.spouse_id)
        if not _can_conceive(game, mother, father, age, por_mae.get(mother.id, [])):
            continue
        if GESTACAO:
            if game.rng.random() < conception_monthly(age):
                _conceive(game, mother, father)
            continue
        if game.rng.random() < birth_monthly(age):
            _birth(game, mother, father)
            if GEMEOS and len(por_mae.get(mother.id, [])) + 2 <= MAX_FILHOS \
                    and game.rng.random() < GEMEOS_CHANCE:
                gemeo = _birth(game, mother, father)
                for parent in (mother, father):
                    game.add_event(parent.id, "gemeos", f"Os filhos nasceram gêmeos (parto duplo com {gemeo.full_name}).")
            if game.rng.random() < maternal_death_risk(age, mother.health):
                _die(game, mother, age, " em decorrência do parto")


# --- casamentos -------------------------------------------------------
# Probabilidade ANUAL de um solteiro (>= 18 anos) tomar a iniciativa de uma união, por faixa
# etária (como cada união envolve duas pessoas, a taxa efetiva por pessoa é ~2x esta). Valores ILUSTRATIVOS, não são estatística oficial.
CASAMENTO = [(18, 0.04), (25, 0.06), (30, 0.035), (40, 0.015), (60, 0.005)]
IDADE_CASAMENTO_MIN = 18
DIFERENCA_IDADE_MAX = 10  # anos, entre os dois cônjuges


def marriage_annual(age: int) -> float:
    if age < IDADE_CASAMENTO_MIN:
        return 0.0
    p = 0.0
    for inicio, prob in CASAMENTO:
        if age >= inicio:
            p = prob
    return p


def marriage_monthly(age: int) -> float:
    return 1 - (1 - marriage_annual(age)) ** (1 / 12)


def has_active_spouse(game: Game, c: Character) -> bool:
    """Casamento ativo = vínculo mútuo com cônjuge vivo (viúvo(a) conta como solteiro(a))."""
    sp = game.characters.get(c.spouse_id)
    return sp is not None and sp.alive and sp.spouse_id == c.id


def _parents(game: Game | None, c: Character) -> set[int]:
    return {i for i in (c.mother_id, c.father_id) if i is not None}


def _grandparents(game: Game | None, c: Character) -> set[int]:
    if game is None:
        return set()
    out: set[int] = set()
    for pid in _parents(game, c):
        p = game.characters.get(pid)
        if p is not None:
            out |= _parents(game, p)
    return out


def close_kin(a: Character, b: Character, game: Game | None = None) -> bool:
    """Parentesco que impede união. Sem `game`: pais/filhos e irmãos (inclusive meio-irmãos).
    Com `game`: também avós/netos, tios/sobrinhos e primos de 1º grau."""
    pa, pb = _parents(game, a), _parents(game, b)
    if a.id in pb or b.id in pa or pa & pb:
        return True
    if game is None:
        return False
    ga, gb = _grandparents(game, a), _grandparents(game, b)
    return bool(a.id in gb or b.id in ga or pa & gb or ga & pb or ga & gb)


def _can_marry(a: Character, b: Character, now: tuple[int, int], game: Game | None = None) -> bool:
    if a.ex_spouse_id == b.id or b.ex_spouse_id == a.id:  # não volta com o ex logo após o divórcio
        return False
    return (a.sex != b.sex and not close_kin(a, b, game)
            and abs(a.age_at(*now) - b.age_at(*now)) <= DIFERENCA_IDADE_MAX)


def _marry(game: Game, a: Character, b: Character) -> None:
    a.spouse_id, b.spouse_id = b.id, a.id
    game.add_event(a.id, "casamento", f"Casou-se com {b.full_name}.")
    game.add_event(b.id, "casamento", f"Casou-se com {a.full_name}.")


def _marriages(game: Game) -> None:
    """Casamentos do mês. Roda depois dos nascimentos. Cada solteiro vivo com >= 18 anos,
    em ordem de id e ainda sem par neste mês, sorteia 1 vez; se sair, escolhe (sorteio) um
    parceiro entre os solteiros compatíveis. Sem parceiro compatível, nada acontece.
    Os nomes não mudam e `family_id` de cada um é mantido."""
    now = (game.year, game.month)
    solteiros = [c for c in sorted(game.characters.values(), key=lambda x: x.id)
                 if c.alive and c.age_at(*now) >= IDADE_CASAMENTO_MIN
                 and not has_active_spouse(game, c)
                 and not (romance.ATIVO and c.partner_id is not None)]
    casados: set[int] = set()
    for c in solteiros:
        if c.id in casados:
            continue
        if game.rng.random() >= marriage_monthly(c.age_at(*now)):
            continue
        candidatos = [o for o in solteiros if o.id != c.id and o.id not in casados
                      and _can_marry(c, o, now, game)]
        if CIRCULO_SOCIAL:
            circulo = social_circle(game, c)
            no_circulo = [o for o in candidatos if o.id in circulo]
            if no_circulo:
                candidatos = no_circulo
            elif not candidatos or game.rng.random() >= CHANCE_PARCEIRO_FORA_DO_CIRCULO:
                continue
        if not candidatos:
            continue
        par = game.rng.choice(candidatos)
        _marry(game, c, par)
        casados.update((c.id, par.id))


# --- amizades / círculo social -------------------------------------------
# Interruptor: False = comportamento da v0.2.0 (sem amizades; parceiro sorteado de toda a população).
CIRCULO_SOCIAL = True
IDADE_AMIZADE_MIN = 6
MAX_AMIGOS = 8
# Probabilidade ANUAL de tentar fazer um amigo novo (ILUSTRATIVA); sobe com a extroversão.
AMIZADE_BASE = 0.5
# Chance de conhecer alguém de fora do círculo quando o círculo não tem parceiro compatível.
CHANCE_PARCEIRO_FORA_DO_CIRCULO = 0.4


def friendship_monthly(c: Character) -> float:
    p = min(0.95, AMIZADE_BASE * (0.4 + c.personality["extroversao"] / 100 * 1.2))
    return 1 - (1 - p) ** (1 / 12)


def affinity(a: Character, b: Character) -> float:
    """Afinidade 0.1–1.0: personalidades parecidas (abertura, amabilidade, extroversão)."""
    d = sum(abs(a.personality[t] - b.personality[t]) for t in ("abertura", "amabilidade", "extroversao"))
    return max(0.1, 1 - d / 150)


def _max_age_gap(age: int) -> int:
    return 3 if age < 12 else 6 if age < 18 else 12


def _alive_friend_count(game: Game, c: Character) -> int:
    return sum(1 for i in game._friends.get(c.id, ()) if game.characters[i].alive)


def _friendships(game: Game) -> None:
    """Amizades do mês (depois dos nascimentos). Cada vivo com >= 6 anos e com menos de 8
    amigos vivos sorteia 1 vez; se sair, escolhe um candidato (vivo, >= 6 anos, faixa de idade
    próxima (limite pela idade do mais novo dos dois), sem parentesco próximo, ainda não amigo, também com vaga) ponderado pela afinidade."""
    now = (game.year, game.month)
    vivos = [c for c in sorted(game.characters.values(), key=lambda x: x.id)
             if c.alive and c.age_at(*now) >= IDADE_AMIZADE_MIN]
    vagas = {c.id: MAX_AMIGOS - _alive_friend_count(game, c) for c in vivos}
    for c in vivos:
        if vagas[c.id] <= 0:
            continue
        if game.rng.random() >= friendship_monthly(c) * (1.5 if game.foco.get(c.id) == "socializar" else 1.0):
            continue
        age = c.age_at(*now)
        cands = [o for o in vivos if o.id != c.id and not game.are_friends(c.id, o.id)
                 and abs(o.age_at(*now) - age) <= _max_age_gap(min(age, o.age_at(*now)))
                 and vagas[o.id] > 0 and not close_kin(c, o, game)]
        if not cands:
            continue
        pesos = [friend_weight(c, x, now) for x in cands]
        o = game.rng.choices(cands, weights=pesos)[0]
        game.add_friendship(c.id, o.id)
        vagas[c.id] -= 1
        vagas[o.id] -= 1
        game.add_event(c.id, "amizade", f"Fez amizade com {o.full_name}.")
        game.add_event(o.id, "amizade", f"Fez amizade com {c.full_name}.")


# Fim de amizades (v0.10.0): afastamento anual-base por par de amigos vivos (ILUSTRATIVO).
FIM_AMIZADES = True
AFASTAMENTO_ANUAL = 0.05


def drift_monthly(a: Character, b: Character, now: tuple[int, int], since: tuple[int, int]) -> float:
    """Chance mensal de a amizade esfriar: maior com baixa afinidade e diferença de idade grande;
    menor entre colegas de escola/trabalho e em amizades longas (≥ 5 anos)."""
    mult = 1.7 - affinity(a, b)
    ida, idb = a.age_at(*now), b.age_at(*now)
    if abs(ida - idb) > _max_age_gap(min(ida, idb)):
        mult *= 1.5
    if (EDUCACAO and _classmates(a, b, now)) or (TRABALHO and _coworkers(a, b)):
        mult *= 0.4
    if (now[0] * 12 + now[1]) - (since[0] * 12 + since[1]) >= 60:
        mult *= 0.5
    p = min(0.95, AFASTAMENTO_ANUAL * mult)
    return 1 - (1 - p) ** (1 / 12)


def _friendship_drift(game: Game) -> None:
    """Afastamentos do mês: um sorteio por amizade entre dois vivos, em ordem de ids."""
    now = (game.year, game.month)
    for (a, b), since in sorted(game.friendships.items()):
        ca, cb = game.characters[a], game.characters[b]
        if not (ca.alive and cb.alive):
            continue
        from . import convivio
        if game.rng.random() < drift_monthly(ca, cb, now, since) * convivio.fator(game, a, b):
            game.remove_friendship(a, b)
            game.add_event(a, "amizade_fim", f"Afastou-se de {cb.full_name} (a amizade esfriou).")
            game.add_event(b, "amizade_fim", f"Afastou-se de {ca.full_name} (a amizade esfriou).")


def _coworkers(a: Character, b: Character) -> bool:
    """Colegas de trabalho: ambos empregados no mesmo local de trabalho."""
    return (work.is_employed(a) and work.is_employed(b)
            and a.workplace is not None and a.workplace == b.workplace)


def friend_weight(a: Character, b: Character, now: tuple[int, int]) -> float:
    """Peso de b como novo amigo de a: afinidade × colegas de escola × colegas de trabalho."""
    w = affinity(a, b)
    if EDUCACAO and _classmates(a, b, now):
        w *= FATOR_COLEGAS
    if TRABALHO and _coworkers(a, b):
        w *= FATOR_COLEGAS_TRABALHO
    return w


def social_circle(game: Game, c: Character) -> set[int]:
    """Amigos e amigos de amigos (vivos), exceto a própria pessoa."""
    out: set[int] = set()
    for f in game.friend_ids(c.id):
        out.add(f)
        out.update(game.friend_ids(f))
    out.discard(c.id)
    return {i for i in out if game.characters[i].alive}


# --- educação básica -----------------------------------------------------
# Interruptor: False = sem escola (comportamento da v0.3.0).
EDUCACAO = True
IDADE_ESCOLAR_MIN = 6
IDADE_MATRICULA_MAX = 14      # primeira matrícula só até esta idade
IDADE_ESCOLAR_MAX = 20        # quem não terminou o médio até aqui encerra os estudos
CHANCE_MATRICULA = 0.98
NOTA_APROVACAO = 45
FATOR_COLEGAS_TRABALHO = 3.0   # peso extra de colegas de trabalho (mesmo local) nas amizades
FATOR_COLEGAS = 4.0           # peso extra de colegas de escola (idade próxima) nas amizades
MES_MATRICULA, MES_FIM_ANO = 2, 12
_COG_ESCOLA = ("raciocinio_logico", "compreensao_verbal", "aprendizagem", "atencao", "memoria")


def grade_label(years_done: int) -> str:
    """Série cursada por quem já concluiu `years_done` anos."""
    n = years_done + 1
    return f"{n}º ano do fundamental" if n <= 9 else f"{n - 9}º ano do ensino médio"


def education_label(c: Character) -> str:
    y = c.schooling_years
    if c.in_college:
        return f"cursando o {c.higher_years + 1}º ano do ensino superior"
    if c.graduated:
        return "ensino superior completo"
    if c.higher_years > 0:
        return f"ensino superior incompleto ({c.higher_years} anos)"
    if c.in_school:
        return f"cursando o {grade_label(y)}"
    if y == 0:
        return "sem escolaridade formal"
    if y < 9:
        return f"ensino fundamental incompleto ({y} anos)"
    if y == 9:
        return "ensino fundamental completo"
    if y < 12:
        return f"ensino médio incompleto ({y} anos)"
    return "ensino médio completo"


def school_performance(game: Game, c: Character, age: int) -> int:
    """Desempenho 0–100: cognição ajustada pela idade (55%), conscienciosidade (30%),
    saúde (15%) e variação aleatória. Valores ILUSTRATIVOS."""
    dev = factory.cognition_development(age)
    cog = sum(c.cognition[k] for k in _COG_ESCOLA) / len(_COG_ESCOLA) / dev
    perf = (0.55 * min(99, cog) + 0.30 * c.personality["conscienciosidade"]
            + 0.15 * c.health + game.rng.gauss(0, 6))
    if game.foco.get(c.id) == "estudar":
        perf += 6   # foco do período (v0.15.1)
    intel = game.intelecto.get(c.id) if hasattr(game, "intelecto") else None
    if intel:
        be = intel.get("bonus_escola")
        if isinstance(be, (list, tuple)) and len(be) == 2 and be[0] == game.year:
            perf += min(18, max(0, int(be[1])))
    return int(min(100, max(0, round(perf))))


def dropout_probability(years_done: int, perf: int, failed: bool) -> float:
    base = 0.004 if years_done < 9 else 0.03
    p = base * (1 + max(0, 50 - perf) / 20) * (2.5 if failed else 1.0)
    return min(0.6, p)


def _enroll(game: Game, now: tuple[int, int]) -> None:
    for cid in sorted(game.characters):
        c = game.characters[cid]
        if not c.alive or c.in_school or c.dropped_out or c.schooling_years != 0:
            continue
        if not IDADE_ESCOLAR_MIN <= c.age_at(*now) <= IDADE_MATRICULA_MAX:
            continue
        if game.rng.random() < CHANCE_MATRICULA:
            c.in_school = True
            game.add_event(c.id, "escola", "Começou o ensino fundamental.")
        else:
            c.dropped_out = True
            game.add_event(c.id, "escola", "Não foi matriculado(a) na escola.")


def _close_school_year(game: Game, now: tuple[int, int]) -> None:
    for cid in sorted(game.characters):
        c = game.characters[cid]
        if not c.alive or not c.in_school:
            continue
        age = c.age_at(*now)
        perf = school_performance(game, c, age)
        c.school_performance = perf
        serie = grade_label(c.schooling_years)
        passed = perf >= NOTA_APROVACAO
        if passed:
            c.schooling_years += 1
            game.add_event(c.id, "escola", f"Foi aprovado(a) no {serie}.")
            if c.schooling_years == 9:
                game.add_event(c.id, "escola", "Concluiu o ensino fundamental.")
            elif c.schooling_years == 12:
                c.in_school = False
                game.add_event(c.id, "escola", "Concluiu o ensino médio.")
                continue
        else:
            game.add_event(c.id, "escola", f"Reprovou no {serie}.")
        p_aband = dropout_probability(c.schooling_years, perf, not passed)
        if c.returned_to_school:
            p_aband = min(0.6, p_aband * FATOR_ABANDONO_RETORNO)
        if game.rng.random() < p_aband:
            c.in_school, c.dropped_out = False, True
            game.add_event(c.id, "escola", f"Abandonou a escola ({education_label(c)}).")
        elif age >= IDADE_ESCOLAR_MAX and not c.returned_to_school:
            c.in_school = False
            game.add_event(c.id, "escola", f"Encerrou os estudos aos {age} anos ({education_label(c)}).")


# --- ensino superior e retorno aos estudos (v0.5.0) ----------------------
# Interruptor: False = sem ensino superior nem retorno (comportamento da v0.4.0).
# Todas as probabilidades são ILUSTRATIVAS, não estatística oficial.
ENSINO_SUPERIOR = True
ANOS_SUPERIOR = 4
INGRESSO_SUPERIOR = [(20, 0.17), (24, 0.06), (34, 0.02)]  # (idade máx., chance anual-base)
NOTA_APROVACAO_SUPERIOR = 50
ABANDONO_SUPERIOR_BASE = 0.07
RETORNO_ESTUDOS_BASE = 0.025   # chance anual-base de voltar à escola (18–45 anos)
IDADE_RETORNO_MIN, IDADE_RETORNO_MAX = 18, 45
FATOR_ABANDONO_RETORNO = 1.5


def aptitude(c: Character) -> float:
    """Aptidão acadêmica 0–100: cognição média (60%) e conscienciosidade (40%)."""
    cog = sum(c.cognition[k] for k in _COG_ESCOLA) / len(_COG_ESCOLA)
    return 0.6 * cog + 0.4 * c.personality["conscienciosidade"]


def _aptitude_factor(c: Character) -> float:
    return min(2.0, max(0.1, (aptitude(c) - 30) / 30))


def college_entry_chance(c: Character, age: int) -> float:
    for limite, base in INGRESSO_SUPERIOR:
        if age <= limite:
            return min(0.9, base * _aptitude_factor(c))
    return 0.0


def college_dropout_probability(perf: int, failed: bool) -> float:
    p = ABANDONO_SUPERIOR_BASE * (1 + max(0, 55 - perf) / 20) * (2.0 if failed else 1.0)
    return min(0.7, p)


def _enroll_college(game: Game, now: tuple[int, int]) -> None:
    for cid in sorted(game.characters):
        c = game.characters[cid]
        if (not c.alive or c.in_school or c.in_college or c.graduated or c.higher_years
                or c.schooling_years != 12 or c.age_at(*now) < 17):
            continue
        if game.rng.random() < college_entry_chance(c, c.age_at(*now)):
            c.in_college = True
            game.add_event(c.id, "escola", "Ingressou no ensino superior.")


def _return_to_school(game: Game, now: tuple[int, int]) -> None:
    for cid in sorted(game.characters):
        c = game.characters[cid]
        if not c.alive or c.in_school or c.in_college or not 5 <= c.schooling_years < 12:
            continue
        age = c.age_at(*now)
        if not IDADE_RETORNO_MIN <= age <= IDADE_RETORNO_MAX:
            continue
        if game.rng.random() < RETORNO_ESTUDOS_BASE * _aptitude_factor(c):
            c.in_school, c.dropped_out, c.returned_to_school = True, False, True
            game.add_event(c.id, "escola", f"Voltou a estudar ({education_label(c)}).")


def _close_college_year(game: Game, now: tuple[int, int]) -> None:
    for cid in sorted(game.characters):
        c = game.characters[cid]
        if not c.alive or not c.in_college:
            continue
        perf = school_performance(game, c, c.age_at(*now))
        c.school_performance = perf
        ano = c.higher_years + 1
        passed = perf >= NOTA_APROVACAO_SUPERIOR
        duracao_curso = ANOS_SUPERIOR
        ed_br = game.educacao_br.get(c.id) if hasattr(game, "educacao_br") else None
        if ed_br and ed_br.get("curso"):
            from . import educacao_br
            curso_meta = educacao_br.CURSOS_POR_ID.get(ed_br["curso"])
            if curso_meta:
                duracao_curso = curso_meta[2]
        if passed:
            c.higher_years += 1
            game.add_event(c.id, "escola", f"Foi aprovado(a) no {ano}º ano do ensino superior.")
            if c.higher_years >= duracao_curso:
                c.in_college, c.graduated = False, True
                game.add_event(c.id, "escola", "Formou-se no ensino superior.")
                continue
        else:
            game.add_event(c.id, "escola", f"Reprovou no {ano}º ano do ensino superior.")
        if game.rng.random() < college_dropout_probability(perf, not passed):
            c.in_college = False
            game.add_event(c.id, "escola", f"Abandonou o ensino superior ({education_label(c)}).")


def _school(game: Game) -> None:
    """Ano letivo: matrículas em fevereiro e resultado em dezembro (aprovação, reprovação,
    abandono). Roda depois dos nascimentos e antes das amizades."""
    now = (game.year, game.month)
    if game.month == MES_MATRICULA:
        _enroll(game, now)
        if ENSINO_SUPERIOR:
            _enroll_college(game, now)
            _return_to_school(game, now)
    elif game.month == MES_FIM_ANO:
        _close_school_year(game, now)
        if ENSINO_SUPERIOR:
            _close_college_year(game, now)


# --- trabalho (v0.6.0) ---------------------------------------------------
TRABALHO = True
# Interruptor da economia (v0.7.0): salário, renda, patrimônio, promoção, herança. False = v0.6.0.
ECONOMIA = True


def _work(game: Game) -> None:
    """Mercado de trabalho mensal (depois da escola, antes das amizades), em ordem de id:
    aposentadoria, perda de emprego, mudança para ocupação melhor (após formação maior),
    entrada no mercado e contratação. Estudantes não procuram emprego; quem já trabalha
    pode continuar empregado enquanto estuda."""
    now = game.year * 12 + game.month
    idx = cycle.current(game)  # ciclo econômico do ano (v0.9.0): determinístico, sem game.rng
    f_sep, f_hire = cycle.separation_factor(idx), cycle.hire_factor(idx)
    if firms.ATIVO:
        firms.ensure_world(game)
        if game.month == 1:
            firms.yearly(game)  # fecha/funda empresas e repõe vagas (sem game.rng)
    for cid in sorted(game.characters):
        c = game.characters[cid]
        if not c.alive or c.retired:
            continue
        age = c.age_at(game.year, game.month)
        if age < work.IDADE_TRABALHO_MIN:
            continue
        studying = work.is_student(c)
        afastada = LICENCA and economy.on_leave(c, now)
        # Aposentadoria (empregados e desempregados; quem estuda não se aposenta).
        if not studying and game.rng.random() < work.retirement_monthly(age):
            if ECONOMIA:
                c.income = economy.pension(c, economy._firm_of(game, c), macro.min_wage(game))   # antes de zerar o local de trabalho
            c.retired = True
            c.workplace = None
            c.seeking_since = None
            c.unemp_until, c.unemp_amount = None, 0.0
            game.add_event(c.id, "trabalho", "Aposentou-se"
                           + (f" (última ocupação: {work.occupation_name(c.occupation, c.sex)})." if c.occupation else "."))
            continue
        if c.occupation is not None:
            ex = game.carreira_extra.get(c.id, {})
            estavel_pub = bool(ex.get("estavel"))
            fid_prop = ex.get("empresa_id")
            tem_empresa = fid_prop is not None and fid_prop in game.firms and game.firms[fid_prop].is_open
            demitida = game.rng.random() < work.separation_monthly(c, now) * f_sep
            if demitida and ((LICENCA and not c.informal and (afastada or c.pregnant_until is not None)) or estavel_pub or tem_empresa):
                demitida = False   # estabilidade da gestante/licença, servidor concursado ou fundador
            if demitida:
                game.add_event(c.id, "trabalho", f"Perdeu o emprego ({work.occupation_name(c.occupation, c.sex)}).")
                if ECONOMIA:
                    economy.grant_unemployment(game, c, now)   # antes de clear_job (usa ocupação e salário)
                work.clear_job(c)
                c.seeking_since = now
            elif not afastada and not estavel_pub and not tem_empresa and game.rng.random() < work.job_change_monthly(c, age):
                antes = c.occupation
                pref = None
                if hasattr(game, "educacao_br") and c.id in game.educacao_br:
                    from . import educacao_br
                    pref = educacao_br.ocupacao_preferida(game, c.id)
                novo = work.pick_occupation(game.rng, c, min_level_exclusive=work.occupation_level(antes),
                                            allowed=firms.open_occupations(game, c.id) if firms.ATIVO else None,
                                            preferred=pref)
                if novo is not None:
                    work.start_job(game, c, novo, now)
                    c.jobs_held += 1
                    game.add_event(c.id, "trabalho",
                                   f"Mudou de ocupação: {work.occupation_name(antes, c.sex)} → {work.occupation_name(novo, c.sex)}.")
            elif (ECONOMIA and (p_prom := work.promotion_monthly(c, now, age)) > 0
                  and work.local_rng(game, c, 3).random() < p_prom):
                c.rank, c.rank_since = c.rank + 1, now
                game.add_event(c.id, "trabalho",
                               f"Foi promovido(a) a {work.RANKS[c.rank]} ({work.occupation_name(c.occupation, c.sex)}); "
                               f"novo salário: {economy.fmt_brl(economy.monthly_salary(c, economy._firm_of(game, c), macro.min_wage(game)))}.")
            continue
        if afastada or studying:   # mãe que deixou o emprego não procura trabalho durante o afastamento
            continue
        if c.seeking_since is None:
            c.seeking_since = now
            game.add_event(c.id, "trabalho", "Passou a procurar trabalho.")
        if game.rng.random() < work.hire_monthly(c, age) * f_hire:
            pref = None
            if hasattr(game, "educacao_br") and c.id in game.educacao_br:
                from . import educacao_br
                pref = educacao_br.ocupacao_preferida(game, c.id)
            key = work.pick_occupation(game.rng, c, allowed=firms.open_occupations(game) if firms.ATIVO else None, preferred=pref)
            if key is None:
                continue  # sem vaga compatível com a qualificação neste mês
            work.start_job(game, c, key, now)
            c.jobs_held += 1
            primeiro = "Conseguiu o primeiro emprego" if c.jobs_held == 1 else "Conseguiu um emprego"
            game.add_event(c.id, "trabalho", f"{primeiro}: {work.occupation_name(key, c.sex)}.")


def _classmates(a: Character, b: Character, now: tuple[int, int]) -> bool:
    gap = abs(a.age_at(*now) - b.age_at(*now))
    if a.in_school and b.in_school:
        return gap <= 1
    return ENSINO_SUPERIOR and a.in_college and b.in_college and gap <= 4


# --- divórcios --------------------------------------------------------
# Probabilidade ANUAL base de um casal ativo se separar (ILUSTRATIVA). A personalidade
# do casal modula o risco: neuroticismo alto aumenta; amabilidade e conscienciosidade reduzem.
DIVORCIO_BASE = 0.014


def divorce_risk_multiplier(a: Character, b: Character, now: tuple[int, int]) -> float:
    n = (a.personality["neuroticismo"] + b.personality["neuroticismo"]) / 200 - 0.5
    am = (a.personality["amabilidade"] + b.personality["amabilidade"]) / 200 - 0.5
    co = (a.personality["conscienciosidade"] + b.personality["conscienciosidade"]) / 200 - 0.5
    mult = 1 + 1.4 * n - 1.0 * am - 0.6 * co
    if min(a.age_at(*now), b.age_at(*now)) < 30:
        mult *= 1.5
    return min(3.0, max(0.3, mult))


def divorce_monthly(a: Character, b: Character, now: tuple[int, int]) -> float:
    p = min(0.95, DIVORCIO_BASE * divorce_risk_multiplier(a, b, now))
    return 1 - (1 - p) ** (1 / 12)


GUARDA = True             # interruptor: guarda dos filhos menores no divórcio (v0.10.0)
GUARDA_PAI_BASE = 0.12    # chance-base de a guarda ficar com o pai (sobe se ele tem muito mais renda)


def _custody(game: Game, a: Character, b: Character) -> None:
    """Define o responsável dos filhos comuns menores de 18 anos (um sorteio por divórcio, todos juntos)."""
    mae, pai = (a, b) if a.sex == "F" else (b, a)
    kids = [k for k in game.children_of(mae.id) if k.alive and pai.id in (k.mother_id, k.father_id)
            and k.age_at(game.year, game.month) < 18]
    if not kids:
        return
    tot = mae.income + pai.income
    p_pai = min(0.6, GUARDA_PAI_BASE + (0.3 * pai.income / tot if tot > 0 else 0.0))
    vence = pai if game.rng.random() < p_pai else mae
    outro = mae if vence is pai else pai
    for k in kids:
        k.guardian_id = vence.id
        game.add_event(k.id, "guarda", f"Ficou sob a guarda de {vence.full_name} após a separação dos pais.")
    game.add_event(vence.id, "guarda", f"Obteve a guarda dos filhos menores ({len(kids)}).")
    game.add_event(outro.id, "guarda", f"Perdeu a guarda dos filhos menores ({len(kids)}); ficam com {vence.full_name}.")


def _divorce(game: Game, a: Character, b: Character) -> None:
    a.spouse_id = b.spouse_id = None
    a.ex_spouse_id, b.ex_spouse_id = b.id, a.id
    game.add_event(a.id, "divorcio", f"Separou-se de {b.full_name} (divórcio).")
    game.add_event(b.id, "divorcio", f"Separou-se de {a.full_name} (divórcio).")
    for child in game.children_of(a.id):
        if child.id in {k.id for k in game.children_of(b.id)} and child.alive \
                and child.age_at(game.year, game.month) < 18:
            game.add_event(child.id, "divorcio_pais", "Seus pais se separaram.")
    if GUARDA:
        _custody(game, a, b)


def _divorces(game: Game) -> None:
    """Divórcios do mês, depois dos nascimentos e antes dos casamentos. Um sorteio por casal
    ativo (identificado pela esposa de menor id), em ordem de id."""
    now = (game.year, game.month)
    for cid in sorted(game.characters):
        w = game.characters[cid]
        if w.sex != "F" or not has_active_spouse(game, w):
            continue
        h = game.characters[w.spouse_id]
        if h.sex != "M":
            continue
        if game.rng.random() < divorce_monthly(w, h, now):
            _divorce(game, w, h)


def _tick(game: Game) -> None:
    game.month += 1
    if game.month > 12:
        game.month = 1
        game.year += 1
    for cid in sorted(game.characters):
        c = game.characters[cid]
        if not c.alive:
            continue
        age = c.age_at(game.year, game.month)
        if c.birth_month == game.month and age > 0:
            _birthday(game, c, age)
        _update_health(game, c, age)
        if game.rng.random() < mortality_monthly(age, c.health):
            _die(game, c, age)
    _births(game)
    if EDUCACAO:
        _school(game)
    if macro.ATIVO:
        macro.tick(game)   # preços sobem; em janeiro reajusta o salário mínimo e fecha o ano fiscal (v0.13.0)
    if TRABALHO:
        _work(game)
    if ECONOMIA:
        economy.apply_month(game)
    if CIRCULO_SOCIAL:
        if FIM_AMIZADES:
            _friendship_drift(game)
        _friendships(game)
    _divorces(game)
    if romance.ATIVO:
        romance.run(game)
    _marriages(game)
    mundo.registrar_noticias_mes(game)


def advance_months(game: Game, n: int) -> list[BioEvent]:
    """Avança n meses, processando cada mês em ordem. Retorna os eventos gerados."""
    if n < 1:
        raise ValueError("n deve ser >= 1")
    inicio = len(game.biography)
    for _ in range(n):
        _tick(game)
    return game.biography[inicio:]
