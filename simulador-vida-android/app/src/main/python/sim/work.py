"""Trabalho (Fase 5, v0.6.0): ocupações genéricas e regras puras de elegibilidade e escolha.

Sem dependência do motor (o motor e a fábrica importam este módulo). Não define empresas,
salários nem instituições reais: só ocupações genéricas ligadas à escolaridade e à aptidão.
Todos os valores são ILUSTRATIVOS, não estatística oficial.
"""
from __future__ import annotations

import random

from .models import MESES, Character

IDADE_TRABALHO_MIN = 16        # idade mínima para procurar emprego
IDADE_APOSENTADORIA_MIN = 60
SAUDE_MIN_TRABALHO = 30        # abaixo disso não é contratado
NIVEIS = {0: "qualquer escolaridade", 1: "fundamental completo", 2: "médio completo", 3: "superior completo"}
FATOR_SOBRE_QUALIFICADO = 0.2
# --- carreira (v0.7.0) ---
LOCAIS_TRABALHO = 25           # locais de trabalho genéricos (nº); quem divide o local é colega de trabalho
RANKS = ("júnior", "pleno", "sênior", "chefia")
MESES_MIN_PROMOCAO = 24        # tempo mínimo em um nível antes de poder ser promovido
PROMOCAO_BASE = 0.012          # chance mensal-base de promoção (×fator de aptidão)
INFORMAL_PROB = {0: 0.45, 1: 0.20, 2: 0.08, 3: 0.03}  # vínculo informal por nível exigido da ocupação
FATOR_SEPARACAO_INFORMAL = 1.5  # peso de ocupações de nível abaixo da formação (não garante o melhor emprego)

# (chave, nome masculino, nome feminino, nível exigido, aptidão mínima, peso)
OCUPACOES = [
    ("servicos_gerais", "Auxiliar de serviços gerais", "Auxiliar de serviços gerais", 0, 0, 3),
    ("trabalhador_rural", "Trabalhador rural", "Trabalhadora rural", 0, 0, 3),
    ("ajudante_obras", "Ajudante de obras", "Ajudante de obras", 0, 0, 2),
    ("auxiliar_limpeza", "Auxiliar de limpeza", "Auxiliar de limpeza", 0, 0, 2),
    ("operador_producao", "Operador de produção", "Operadora de produção", 1, 30, 3),
    ("auxiliar_cozinha", "Auxiliar de cozinha", "Auxiliar de cozinha", 1, 25, 2),
    ("motorista_entregas", "Motorista de entregas", "Motorista de entregas", 1, 35, 2),
    ("vigilante", "Vigilante", "Vigilante", 1, 30, 2),
    ("aux_administrativo", "Auxiliar administrativo", "Auxiliar administrativa", 2, 38, 4),
    ("atendente_comercio", "Atendente de comércio", "Atendente de comércio", 2, 30, 4),
    ("tecnico_medio", "Técnico de nível médio", "Técnica de nível médio", 2, 42, 2),
    ("representante_vendas", "Representante de vendas", "Representante de vendas", 2, 40, 2),
    ("professor", "Professor", "Professora", 3, 45, 1.3),
    ("engenheiro", "Engenheiro", "Engenheira", 3, 55, 0.7),
    ("advogado", "Advogado", "Advogada", 3, 50, 0.7),
    ("enfermeiro", "Enfermeiro", "Enfermeira", 3, 45, 0.7),
    ("contador", "Contador", "Contadora", 3, 48, 0.7),
    ("analista_sistemas", "Analista de sistemas", "Analista de sistemas", 3, 55, 0.7),
    ("medico", "Médico", "Médica", 3, 62, 0.35),
    ("psicologo", "Psicólogo", "Psicóloga", 3, 50, 0.45),
    ("economista", "Economista", "Economista", 3, 55, 0.4),
    ("pesquisador", "Pesquisador", "Pesquisadora", 3, 58, 0.35),
    ("designer", "Designer", "Designer", 3, 45, 0.45),
    ("administrador", "Administrador", "Administradora", 3, 46, 0.65),
    ("arquiteto", "Arquiteto e urbanista", "Arquiteta e urbanista", 3, 52, 0.35),
    ("dentista", "Cirurgião-dentista", "Cirurgiã-dentista", 3, 55, 0.35),
    ("farmaceutico", "Farmacêutico", "Farmacêutica", 3, 50, 0.4),
    ("fisioterapeuta", "Fisioterapeuta", "Fisioterapeuta", 3, 48, 0.4),
    ("nutricionista", "Nutricionista", "Nutricionista", 3, 46, 0.35),
    ("veterinario", "Médico veterinário", "Médica veterinária", 3, 52, 0.3),
    ("agronomo", "Engenheiro agrônomo", "Engenheira agrônoma", 3, 52, 0.35),
    ("biologo", "Biólogo", "Bióloga", 3, 48, 0.3),
    ("quimico", "Químico", "Química", 3, 52, 0.3),
    ("jornalista", "Jornalista", "Jornalista", 3, 48, 0.35),
    ("publicitario", "Publicitário", "Publicitária", 3, 46, 0.35),
    ("analista_ri", "Analista internacional", "Analista internacional", 3, 54, 0.25),
    ("estatistico", "Estatístico e cientista de dados", "Estatística e cientista de dados", 3, 56, 0.35),
    ("assistente_social", "Assistente social", "Assistente social", 3, 45, 0.35),
    ("sociologo", "Sociólogo / Pesquisador social", "Socióloga / Pesquisadora social", 3, 48, 0.25),
    ("matematico", "Matemático aplicado", "Matemática aplicada", 3, 55, 0.3),
]
_POR_CHAVE = {o[0]: o for o in OCUPACOES}


def occupation_name(key: str, sex: str) -> str:
    o = _POR_CHAVE[key]
    return o[2] if sex == "F" else o[1]


def occupation_level(key: str) -> int:
    return _POR_CHAVE[key][3]


def education_level(c: Character) -> int:
    """0 = sem fundamental completo, 1 = fundamental, 2 = médio, 3 = superior completo."""
    if c.graduated:
        return 3
    if c.schooling_years >= 12:
        return 2
    if c.schooling_years >= 9:
        return 1
    return 0


def work_aptitude(c: Character) -> float:
    """Aptidão profissional 0–100: cognição média (8 domínios, 60%) + conscienciosidade (40%)."""
    cog = sum(c.cognition.values()) / len(c.cognition)
    return 0.6 * cog + 0.4 * c.personality["conscienciosidade"]


def aptitude_factor(c: Character) -> float:
    return min(2.0, max(0.1, (work_aptitude(c) - 30) / 30))


def is_student(c: Character) -> bool:
    return c.in_school or c.in_college


def is_employed(c: Character) -> bool:
    return c.alive and c.occupation is not None and not c.retired


def is_seeking(c: Character) -> bool:
    return c.alive and c.occupation is None and c.seeking_since is not None and not c.retired


def can_enter_market(c: Character, age: int) -> bool:
    """Pode procurar emprego: vivo, ≥16 anos, não aposentado e fora da escola/faculdade."""
    return c.alive and age >= IDADE_TRABALHO_MIN and not c.retired and not is_student(c)


def candidate_occupations(c: Character, min_level_exclusive: int = -1) -> list[tuple]:
    """Ocupações para as quais c se qualifica (escolaridade e aptidão), com nível > o dado."""
    lvl, apt = education_level(c), work_aptitude(c)
    return [o for o in OCUPACOES if o[3] <= lvl and apt >= o[4] and o[3] > min_level_exclusive]


def pick_occupation(rng: random.Random, c: Character, min_level_exclusive: int = -1,
                    allowed: set | None = None, preferred: str | None = None) -> str | None:
    """Sorteia uma ocupação. Quem tem formação maior ocupa mais vagas de nível alto, mas não
    é garantido: ocupações de nível inferior à formação têm peso reduzido, não zero.
    `allowed` (v0.8.0): só ocupações com vaga livre em alguma empresa (None = sem restrição).
    `preferred` (v0.20.0): prioriza ocupação alinhada à graduação/curso técnico quando informada."""
    cands = candidate_occupations(c, min_level_exclusive)
    if allowed is not None:
        cands = [o for o in cands if o[0] in allowed]
    if not cands:
        return None
    lvl = education_level(c)
    pesos = [
        o[5] * (1.0 if o[3] == lvl else FATOR_SOBRE_QUALIFICADO) * (6.0 if preferred and o[0] == preferred else 1.0)
        for o in cands
    ]
    return rng.choices(cands, weights=pesos, k=1)[0][0]


def hire_monthly(c: Character, age: int) -> float:
    """Chance mensal de um desempregado ser contratado."""
    if c.health < SAUDE_MIN_TRABALHO:
        return 0.0
    base = 0.12 * (0.5 + 0.5 * aptitude_factor(c))
    if age < 18:
        base *= 0.6
    elif age >= 60:
        base *= 0.4
    elif age >= 50:
        base *= 0.7
    return min(0.5, base)


def separation_monthly(c: Character, now: int) -> float:
    """Chance mensal de perder o emprego: maior no início do vínculo e com saúde baixa,
    menor com conscienciosidade alta e vínculo longo."""
    p = 0.012
    tenure = now - (c.job_start if c.job_start is not None else now)
    if tenure < 12:
        p *= 1.5
    elif tenure >= 60:
        p *= 0.7
    p *= 1.3 - 0.6 * c.personality["conscienciosidade"] / 100
    p *= 1 + max(0.0, 50 - c.health) / 50
    if c.informal:
        p *= FATOR_SEPARACAO_INFORMAL
    return min(0.2, p)


def retirement_monthly(age: int) -> float:
    if age < IDADE_APOSENTADORIA_MIN:
        return 0.0
    if age < 65:
        return 0.008
    if age < 70:
        return 0.03
    if age < 75:
        return 0.06
    return 1.0


def job_change_monthly(c: Character, age: int) -> float:
    """Chance mensal de um empregado com formação acima da exigida da ocupação trocar para outra melhor."""
    if age >= IDADE_APOSENTADORIA_MIN or c.occupation is None:
        return 0.0
    return 0.006 if education_level(c) > occupation_level(c.occupation) else 0.0


def local_rng(game, c: Character, salt: int, now: int | None = None) -> random.Random:
    """Gerador determinístico por (semente, personagem, mês, sal). NÃO usa `game.rng`: a carreira e a\n    economia não alteram o fluxo do RNG principal, então carregar e continuar segue idêntico."""
    n = game.year * 12 + game.month if now is None else now
    return random.Random(f"{game.seed}:{c.id}:{n}:{salt}")


def start_job(game, c: Character, key: str, now: int) -> None:
    """Inicia um vínculo: ocupação, nível inicial, formal/informal e empresa (v0.8.0; antes, local nº)."""
    from . import firms  # import tardio: firms importa este módulo
    rng = local_rng(game, c, 1, now)
    firm = firms.pick_firm(game, key, rng, exclude_id=c.id) if firms.ATIVO else None
    c.occupation, c.job_start, c.seeking_since = key, now, None
    c.unemp_until, c.unemp_amount = None, 0.0   # novo vínculo encerra o seguro-desemprego
    c.rank, c.rank_since = 0, now
    c.informal = rng.random() < firms.informal_probability(occupation_level(key), firm)
    c.workplace = firm.id if firm is not None else rng.randrange(LOCAIS_TRABALHO)


def clear_job(c: Character) -> None:
    """Encerra o vínculo atual (a experiência acumulada fica)."""
    c.occupation, c.job_start = None, None
    c.rank, c.rank_since, c.informal, c.workplace = 0, None, False, None


def promotion_monthly(c: Character, now: int, age: int) -> float:
    """Chance mensal de promoção: só formais, abaixo de 60 anos, com ≥24 meses no nível atual; sobe com\n    a aptidão; a última etapa (chefia) é mais difícil."""
    if not is_employed(c) or c.informal or c.rank >= len(RANKS) - 1 or age >= IDADE_APOSENTADORIA_MIN:
        return 0.0
    if c.rank_since is None or now - c.rank_since < MESES_MIN_PROMOCAO:
        return 0.0
    p = PROMOCAO_BASE * aptitude_factor(c)
    if c.rank == len(RANKS) - 2:
        p *= 0.5
    if c.health < SAUDE_MIN_TRABALHO:
        p *= 0.3
    return min(0.1, p)


def default_work(game, c: Character) -> None:
    """Situação de trabalho inicial de quem entra na simulação (ou de saves antigos). Determinística
    e SEM usar game.rng (usa um gerador local derivado da semente e do id), como `default_schooling`."""
    age = c.age_at(game.year, game.month)
    if not can_enter_market(c, age):
        return
    rng = random.Random(game.seed * 1_000_003 + c.id * 7919 + 17)
    now = game.year * 12 + game.month
    if age >= IDADE_APOSENTADORIA_MIN:
        p_ret = 0.5 if age < 65 else 0.85 if age < 75 else 1.0
        if rng.random() < p_ret:
            c.occupation = pick_occupation(rng, c)
            c.retired, c.jobs_held = True, 1
            return
    tenure = int(rng.random() * 12 * min(age - IDADE_TRABALHO_MIN, 15))
    if c.health >= SAUDE_MIN_TRABALHO and rng.random() < 0.88:
        c.occupation = pick_occupation(rng, c)
        c.job_start, c.jobs_held = now - tenure, 1
    else:
        c.seeking_since = now - int(rng.random() * 12)


def work_label(c: Character, now_year: int, now_month: int) -> str | None:
    """Texto da situação de trabalho para a ficha (None para menores de 16 anos)."""
    age = c.age_at(now_year, now_month) if c.alive else None
    if age is not None and age < IDADE_TRABALHO_MIN:
        return None
    now = now_year * 12 + now_month

    def desde(m: int | None) -> str:
        if m is None:
            return ""
        anos, meses = divmod(max(0, now - m), 12)
        ta = f"{anos} ano" + ("" if anos == 1 else "s")
        tm = f"{meses} " + ("mês" if meses == 1 else "meses")
        return f" (há {ta} e {tm})" if anos and meses else (f" (há {ta})" if anos else f" (há {tm})")
    if c.occupation is not None and c.retired:
        return f"aposentado(a) (última ocupação: {occupation_name(c.occupation, c.sex)})"
    if c.retired:
        return "aposentado(a)"
    if c.occupation is not None:
        return (f"empregado(a): {occupation_name(c.occupation, c.sex)} ({RANKS[c.rank]}, "
                f"{'informal' if c.informal else 'formal'}){desde(c.job_start)}")
    if c.seeking_since is not None:
        return f"desempregado(a), procurando trabalho{desde(c.seeking_since)}"
    return "sem atividade (estudando)" if is_student(c) else "sem atividade"


__all__ = [n for n in dir() if not n.startswith("_") and n != "MESES"]
