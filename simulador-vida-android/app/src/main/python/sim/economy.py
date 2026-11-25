"""Economia (v0.7.0): salário, renda, patrimônio, domicílios, herança e panorama.
v0.9.0: clima econômico no panorama; v0.9.1: seguro-desemprego; v0.9.2: prêmio salarial por porte da empresa.

Todos os valores são ILUSTRATIVOS, em reais CONSTANTES (sem inflação), não estatística oficial.
Funções puras ou determinísticas: nada aqui usa `game.rng`.
"""
from __future__ import annotations

import random

from . import carreiras, cycle, educacao_br, firms, intelecto, macro, mundo, work
from .models import Character

SALARIO_MINIMO = 1500.0  # R$/mês, ilustrativo (valor-base do início da partida; o vigente é `macro.min_wage(game)`)
# Salário-base por ocupação, em múltiplos do salário mínimo.
SALARIO_BASE = {
    "servicos_gerais": 1.0, "trabalhador_rural": 1.0, "ajudante_obras": 1.1, "auxiliar_limpeza": 1.0,
    "operador_producao": 1.6, "auxiliar_cozinha": 1.2, "motorista_entregas": 1.5, "vigilante": 1.4,
    "aux_administrativo": 1.8, "atendente_comercio": 1.3, "tecnico_medio": 2.4, "representante_vendas": 2.0,
    "professor": 3.0, "engenheiro": 6.0, "advogado": 5.5, "enfermeiro": 3.2, "contador": 4.0,
    "analista_sistemas": 5.0, "medico": 12.0,
    "psicologo": 3.8, "economista": 4.8, "pesquisador": 4.2, "designer": 3.5,
    "administrador": 4.2, "arquiteto": 5.0, "dentista": 5.6, "farmaceutico": 3.9,
    "fisioterapeuta": 3.5, "nutricionista": 3.4, "veterinario": 4.1, "agronomo": 4.9,
    "biologo": 3.6, "quimico": 4.3, "jornalista": 3.7, "publicitario": 3.8,
    "analista_ri": 4.6, "estatistico": 5.4, "assistente_social": 3.1,
    "sociologo": 3.4, "matematico": 4.7,
}
FATOR_NIVEL = (1.0, 1.25, 1.6, 2.2)   # júnior, pleno, sênior, chefia
FATOR_INFORMAL = 0.8
EXPERIENCIA_ANUAL = 0.02              # +2% por ano trabalhado
EXPERIENCIA_MAX = 0.4
TAXA_APOSENTADORIA = 0.7              # benefício formal = 70% do último salário
TETO_BENEFICIO = 10 * SALARIO_MINIMO
AUXILIO_LIMITE_PER_CAPITA = 0.6 * SALARIO_MINIMO  # renda per capita abaixo disso recebe auxílio por dependente
AUXILIO_POR_DEPENDENTE = 0.5 * 0.45 * SALARIO_MINIMO
IDADE_DEPENDENTE_MAX = 25            # jovens adultos sem renda e solteiros seguem sustentados pelos pais vivos
IDADE_ASSISTENCIAL = 65               # sem renda e sem trabalho: benefício assistencial de 1 mínimo

# Prêmio/desconto salarial por porte da empresa (v0.9.2; ILUSTRATIVO): grandes pagam mais que micro.
PREMIO_PORTE = True
FATOR_PORTE = {"micro": 0.90, "pequena": 0.97, "média": 1.06, "grande": 1.14}
# Seguro-desemprego (v0.9.1; ILUSTRATIVO): demissão involuntária de vínculo FORMAL com ≥12 meses.
SEGURO_ATIVO = True
SEGURO_TAXA = 0.6                       # fração do último salário
SEGURO_PISO = 1.0 * SALARIO_MINIMO
SEGURO_TETO = 2.0 * SALARIO_MINIMO
SEGURO_PARCELAS = ((24, 5), (12, 4))    # (meses mínimos de vínculo, nº de parcelas), do maior para o menor

# Impostos (v0.13.0; ILUSTRATIVO): só vínculo FORMAL. Previdência + IR progressivo; faixas em salários mínimos.
IMPOSTOS = True
PREVIDENCIA, PREVIDENCIA_TETO = 0.08, 6.0
IR_FAIXAS = ((2.5, 0.0), (3.5, 0.075), (5.0, 0.15), (7.0, 0.225), (float("inf"), 0.275))
# Pensão alimentícia (v0.13.0): o genitor sem a guarda repassa parte da renda ao responsável pela guarda.
PENSAO = True
PENSAO_BASE, PENSAO_EXTRA, PENSAO_MAX = 0.15, 0.05, 0.30

CUSTO_ADULTO = 0.9 * SALARIO_MINIMO   # custo de vida mensal
CUSTO_ADULTO_EXTRA = 0.6 * SALARIO_MINIMO  # 2º adulto do mesmo domicílio (custos compartilhados)
CUSTO_CRIANCA = 0.45 * SALARIO_MINIMO
POUPANCA_MIN, POUPANCA_MAX = 0.15, 0.40  # fração do saldo positivo poupada (sobe com conscienciosidade)
RENDIMENTO_MENSAL = 0.004
JUROS_DIVIDA_MENSAL = 0.01
DIVIDA_MAX = 24 * SALARIO_MINIMO
SHARE_CONJUGE_HERANCA = 0.5           # com cônjuge e filhos: metade ao cônjuge, metade aos filhos


def fmt_brl(x: float) -> str:
    s = f"{abs(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-R$ " if x < 0 else "R$ ") + s


def experience_factor(c: Character) -> float:
    return 1 + min(EXPERIENCIA_MAX, c.experience / 12 * EXPERIENCIA_ANUAL)


def monthly_salary(c: Character, firm=None, mw: float | None = None) -> float:
    """Salário bruto mensal da ocupação atual (0 sem ocupação): base × nível × experiência × formal/informal
    × porte da empresa (v0.9.2; sem `firm` ou com `PREMIO_PORTE` desligado, fator 1)."""
    if c.occupation is None:
        return 0.0
    v = SALARIO_BASE[c.occupation] * (SALARIO_MINIMO if mw is None else mw) * FATOR_NIVEL[c.rank] * experience_factor(c)
    if c.informal:
        v *= FATOR_INFORMAL
    if PREMIO_PORTE and firm is not None:
        v *= FATOR_PORTE[firm.size]
    return round(v, 2)


def _firm_of(game, c: Character):
    """Empresa do vínculo atual (None se sem empresa ou `firms.ATIVO` desligado)."""
    return game.firms.get(c.workplace) if (firms.ATIVO and c.workplace is not None) else None


def unemployment_benefit(c: Character, now: int, firm=None, mw: float | None = None) -> tuple[float, int]:
    """(valor mensal, nº de parcelas) a que tem direito quem perde AGORA o vínculo atual;
    (0.0, 0) se não elegível (informal, sem vínculo ou com menos de 12 meses)."""
    if not SEGURO_ATIVO or c.occupation is None or c.informal or c.job_start is None:
        return 0.0, 0
    tenure = now - c.job_start
    parcelas = next((n for minimo, n in SEGURO_PARCELAS if tenure >= minimo), 0)
    if parcelas == 0:
        return 0.0, 0
    k = 1.0 if mw is None else mw / SALARIO_MINIMO
    valor = min(SEGURO_TETO * k, max(SEGURO_PISO * k, SEGURO_TAXA * monthly_salary(c, firm, mw)))
    return round(valor, 2), parcelas


def grant_unemployment(game, c: Character, now: int) -> float:
    """Concede o seguro-desemprego. CHAMAR ANTES de `work.clear_job` (usa a ocupação e o salário do vínculo
    que acaba). Registra evento; devolve o valor mensal (0.0 se não elegível). Sem `game.rng`."""
    valor, n = unemployment_benefit(c, now, _firm_of(game, c), macro.min_wage(game))
    if valor <= 0:
        return 0.0
    c.unemp_amount, c.unemp_until = valor, now + n - 1   # n parcelas: do mês atual ao (atual + n − 1)
    game.add_event(c.id, "trabalho", f"Passou a receber seguro-desemprego: {fmt_brl(valor)}/mês por {n} meses.")
    return valor


def receiving_unemployment(c: Character, now: int) -> bool:
    return c.unemp_until is not None and now <= c.unemp_until and not work.is_employed(c) and not c.retired


def pension(c: Character, firm=None, mw: float | None = None) -> float:
    """Benefício de aposentado: formal = 70% do último salário (mín. 1 salário mínimo, teto 10);
    informal ou sem ocupação = 1 salário mínimo."""
    m = SALARIO_MINIMO if mw is None else mw
    if c.occupation is None or c.informal:
        return m
    return round(min(TETO_BENEFICIO * m / SALARIO_MINIMO, max(m, TAXA_APOSENTADORIA * monthly_salary(c, firm, mw))), 2)


def savings_rate(adults: list[Character]) -> float:
    consc = sum(a.personality["conscienciosidade"] for a in adults) / len(adults)
    return POUPANCA_MIN + (POUPANCA_MAX - POUPANCA_MIN) * consc / 100


def current_income(c: Character, age: int, now: int | None = None, firm=None, mw: float | None = None) -> float:
    """Renda do mês: benefício (aposentado), salário (empregado), seguro-desemprego (se em curso, exige `now`)
    ou assistencial (≥65 anos); senão 0."""
    m = SALARIO_MINIMO if mw is None else mw
    if c.retired:
        return c.income if c.income > 0 else m
    if work.is_employed(c):
        return monthly_salary(c, firm, mw)
    if now is not None and receiving_unemployment(c, now):
        return c.unemp_amount
    return m if age >= IDADE_ASSISTENCIAL else 0.0


def income_tax(salary: float, mw: float) -> float:
    """Previdência (8% até 6 mínimos) + IR progressivo sobre o salário bruto mensal; escala com o mínimo."""
    if salary <= 0:
        return 0.0
    s = salary / mw
    prev = PREVIDENCIA * min(s, PREVIDENCIA_TETO)
    base, ir, low = max(0.0, s - prev), 0.0, 0.0
    for lim, rate in IR_FAIXAS:
        if base > low:
            ir += (min(base, lim) - low) * rate
        low = lim
    return round((prev + ir) * mw, 2)


def taxpayer(c: Character) -> bool:
    return work.is_employed(c) and not c.informal and not c.retired


def on_leave(c: Character, now: int) -> bool:
    return c.leave_until is not None and now <= c.leave_until


def alimony_flows(game) -> list[tuple[int, int, float]]:
    """Pensão alimentícia: (pagador, recebedor, valor mensal). O genitor vivo e adulto, com renda, que não é o
    responsável pela guarda (nem cônjuge dele) repassa 15% da renda por 1 filho menor, +5% por filho adicional
    (teto 30%). Sem guarda definida, responsável morto ou pagador sem renda: nada."""
    now = (game.year, game.month)
    n_por_par: dict[tuple[int, int], int] = {}
    for k in game.characters.values():
        if not k.alive or k.guardian_id is None or k.age_at(*now) >= 18:
            continue
        g = game.characters.get(k.guardian_id)
        if g is None or not g.alive:
            continue
        for pid in (k.mother_id, k.father_id):
            p = game.characters.get(pid)
            if p is None or not p.alive or p.id == g.id or p.income <= 0 or p.age_at(*now) < 18:
                continue
            if _active_spouse(game, g) is p:
                continue
            n_por_par[(p.id, g.id)] = n_por_par.get((p.id, g.id), 0) + 1
    return [(pid, gid, round(game.characters[pid].income * min(PENSAO_MAX, PENSAO_BASE + PENSAO_EXTRA * (n - 1)), 2))
            for (pid, gid), n in sorted(n_por_par.items())]


def _active_spouse(game, c: Character) -> Character | None:
    sp = game.characters.get(c.spouse_id)
    return sp if sp is not None and sp.alive and sp.spouse_id == c.id else None


def _payer(game, c: Character) -> Character | None:
    """Quem sustenta um menor: o responsável por guarda (se vivo), senão a mãe viva, senão o pai vivo (None se órfão)."""
    for pid in (c.guardian_id, c.mother_id, c.father_id):
        p = game.characters.get(pid)
        if p is not None and p.alive:
            return p
    return None


def build_households(game) -> list[dict]:
    """Domicílios: adultos (≥18, ou menores sem responsável vivo) + cônjuge ativo + dependentes (<18, ou <25 sem renda e
    sem cônjuge, com responsável vivo, sempre com a mãe se viva — não há guarda). Renda de dependentes que trabalham entra no domicílio."""
    now = (game.year, game.month)
    mw, pl = macro.min_wage(game), macro.price_level(game)   # salário mínimo nominal e índice de preços (v0.13.0)
    k = mw / SALARIO_MINIMO
    alive = [c for _, c in sorted(game.characters.items()) if c.alive]
    age = {c.id: c.age_at(*now) for c in alive}
    kids: dict[int, list[Character]] = {}
    heads = []
    for c in alive:
        jovem_sem_renda = (age[c.id] < IDADE_DEPENDENTE_MAX and c.income == 0 and _active_spouse(game, c) is None)
        payer = _payer(game, c) if (age[c.id] < 18 or jovem_sem_renda) else None
        while payer is not None and age[payer.id] < 18:  # mãe/pai menor também é dependente
            payer = _payer(game, payer)
        if payer is not None:
            kids.setdefault(payer.id, []).append(c)
        else:
            heads.append(c)
    head_ids = {c.id for c in heads}
    done, out = set(), []
    for c in heads:
        if c.id in done:
            continue
        adults = [c]
        sp = _active_spouse(game, c)
        if sp is not None and sp.id not in done and sp.id in head_ids:
            adults.append(sp)
        done.update(a.id for a in adults)
        deps = [k for a in adults for k in kids.get(a.id, [])]
        orphan = age[c.id] < 18
        income = sum(a.income for a in adults) + sum(k.income for k in deps)
        cost = (CUSTO_ADULTO + CUSTO_ADULTO_EXTRA * (len(adults) - 1) + CUSTO_CRIANCA * len(deps)) * pl
        if orphan:
            cost = 0.0  # menor sem responsável vivo: custeado por parentes/Estado (simplificação)
        else:
            cost = round(max(0.0, cost * mundo.fator_custo_domicilio(game, adults) - mundo.desconto_moradia_domicilio(game, adults)), 2)
        auxilio = 0.0
        if deps and income / (len(adults) + len(deps)) < AUXILIO_LIMITE_PER_CAPITA * k:
            auxilio = AUXILIO_POR_DEPENDENTE * k * len(deps)  # auxílio social por dependente (ilustrativo)
        out.append({"adults": adults, "kids": deps, "income": income + auxilio, "auxilio": auxilio,
                    "cost": cost, "orphan": orphan, "imposto": 0.0, "pensao_paga": 0.0, "pensao_recebida": 0.0})
    onde = {m.id: h for h in out for m in h["adults"] + h["kids"]}
    if IMPOSTOS:
        for h in out:
            h["imposto"] = round(sum(income_tax(m.income, mw) for m in h["adults"] + h["kids"] if taxpayer(m)), 2)
    if PENSAO:
        for pid, gid, valor in alimony_flows(game):
            hp, hg = onde.get(pid), onde.get(gid)
            if hp is None or hg is None or hp is hg:
                continue
            hp["income"] -= valor
            hg["income"] += valor
            hp["pensao_paga"] += valor
            hg["pensao_recebida"] += valor
    return out


def household_of(game, c: Character) -> dict | None:
    for h in build_households(game):
        if any(m.id == c.id for m in h["adults"] + h["kids"]):
            return h
    return None


def apply_month(game) -> None:
    """Um mês de economia: renda, experiência, custos, poupança/déficit, rendimentos e dívida."""
    now = (game.year, game.month)
    now_i = game.year * 12 + game.month
    mw = macro.min_wage(game)
    infl = macro.monthly_rate(game)
    for c in game.characters.values():
        if not c.alive:
            continue
        if work.is_employed(c):
            c.experience += 1
        if c.unemp_until is not None and now_i > c.unemp_until:   # parcelas esgotadas
            c.unemp_until, c.unemp_amount = None, 0.0
        c.income = current_income(c, c.age_at(*now), now_i, _firm_of(game, c), mw)
        ex = game.carreira_extra.get(c.id)
        b_idiomas = intelecto.bonus_salarial_idiomas(game, c.id) if game.intelecto else 1.0
        if ex and ex.get("estavel") and ex.get("salario_minimos"):
            c.income = round(ex["salario_minimos"] * mw * educacao_br.bonus_salarial_pos(game, c.id) * b_idiomas, 2)
        elif work.is_employed(c) and (game.educacao_br or b_idiomas > 1.0):
            bonus_pos = educacao_br.bonus_salarial_pos(game, c.id) if game.educacao_br else 1.0
            if bonus_pos > 1.0 or b_idiomas > 1.0:
                c.income = round(c.income * bonus_pos * b_idiomas, 2)
    hs = build_households(game)
    receita = sum(h["imposto"] for h in hs)
    despesa = sum(h["auxilio"] for h in hs)   # o Estado paga auxílio, aposentadorias, seguro, assistência e licenças
    for c in game.characters.values():
        if not c.alive:
            continue
        if c.retired or on_leave(c, now_i) and work.is_employed(c):
            despesa += c.income
        elif not work.is_employed(c) and (receiving_unemployment(c, now_i) or c.age_at(*now) >= IDADE_ASSISTENCIAL):
            despesa += c.income
    macro.record_fiscal(game, receita, despesa) if macro.ATIVO else None
    for h in hs:
        net = h["income"] - h["imposto"] - h["cost"]
        if h["orphan"]:
            net = max(0.0, net)
        share = net / len(h["adults"])
        if net > 0:
            share *= savings_rate(h["adults"])
        for a in h["adults"]:
            a.wealth += share
    for c in game.characters.values():
        if not c.alive:
            continue
        c.wealth *= 1 + (RENDIMENTO_MENSAL if c.wealth > 0 else JUROS_DIVIDA_MENSAL) + infl
        c.wealth = round(max(-DIVIDA_MAX * macro.price_level(game), c.wealth), 2)
    educacao_br.apply_month(game)
    carreiras.apply_month(game)
    mundo.apply_month(game)
    if game.player_id is not None:
        pj = game.characters.get(game.player_id)
        if pj is not None and pj.alive and pj.income > 0:
            mundo.registrar_transacao(game, pj.id, "entrada", pj.income, "Renda mensal / salário")


def heirs_of(game, c: Character) -> list[tuple[Character, float]]:
    """Herdeiros e a fração de cada um: cônjuge ativo e filhos vivos (metade/metade; só um grupo = tudo)."""
    sp = _active_spouse(game, c)
    filhos = [k for k in game.children_of(c.id) if k.alive]
    if sp and filhos:
        return [(sp, SHARE_CONJUGE_HERANCA)] + [(k, (1 - SHARE_CONJUGE_HERANCA) / len(filhos)) for k in filhos]
    if sp:
        return [(sp, 1.0)]
    return [(k, 1 / len(filhos)) for k in filhos]


def inherit(game, c: Character) -> list[tuple[Character, float]]:
    """Distribui o patrimônio de quem morreu (dívidas se extinguem; sem herdeiros, vai ao Estado)."""
    w, c.wealth, c.income = c.wealth, 0.0, 0.0
    if w <= 0:
        return []
    out = []
    for h, f in heirs_of(game, c):
        h.wealth = round(h.wealth + w * f, 2)
        out.append((h, round(w * f, 2)))
    return out


def initial_economy(game, c: Character) -> None:
    """Situação econômica inicial de quem entra na simulação (ou de saves antigos), a partir do trabalho
    já definido. Determinística e SEM `game.rng` (gerador local)."""
    age = c.age_at(game.year, game.month)
    if not c.alive or age < work.IDADE_TRABALHO_MIN:
        return
    now = game.year * 12 + game.month
    rng = work.local_rng(game, c, 2, now)
    lvl = work.education_level(c)
    if c.occupation is not None:
        tenure = max(0, now - (c.job_start if c.job_start is not None else now))
        c.experience = tenure + int(rng.random() * 24)
        firm = None
        if firms.ATIVO and not c.retired:
            firm = firms.pick_firm(game, c.occupation, rng, exclude_id=c.id)
        c.informal = rng.random() < firms.informal_probability(work.occupation_level(c.occupation), firm)
        if c.retired:
            c.workplace = None
        else:
            c.workplace = firm.id if firm is not None else rng.randrange(work.LOCAIS_TRABALHO)
        rank = 0
        for lim in (30, 90, 180):
            if c.experience >= lim and not c.informal and rng.random() < 0.55 * min(1.5, work.aptitude_factor(c)):
                rank += 1
            else:
                break
        c.rank = rank
        c.rank_since = None if c.retired else now - int(rng.random() * 36)
    else:
        c.experience = int(rng.random() * 12 * max(0, age - work.IDADE_TRABALHO_MIN) * 0.5)
    mw = macro.min_wage(game)
    c.income = current_income(c, age, firm=_firm_of(game, c), mw=mw)
    if c.retired:
        c.income = pension(c, mw=mw)
    if age >= 18:
        meses = 12 * min(age - 18, 45)
        base = max(c.income, mw * 0.6)
        c.wealth = round(base * meses * 0.1 * rng.random() * (1.2 if lvl >= 2 else 1.0), 2)


def gini(values: list[float]) -> float:
    v = sorted(x for x in values if x >= 0)
    n, s = len(v), sum(v)
    if n == 0 or s == 0:
        return 0.0
    return sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(v)) / (n * s)


def summary(game) -> dict:
    """Panorama econômico da população viva (adultos ≥18): renda média/mediana, desigualdade, patrimônio, emprego."""
    now = (game.year, game.month)
    adultos = [c for c in game.characters.values() if c.alive and c.age_at(*now) >= 18]
    rendas = [c.income for c in adultos]
    pat = sorted(c.wealth for c in adultos)
    ativos = [c for c in adultos if not c.retired and c.age_at(*now) < work.IDADE_APOSENTADORIA_MIN + 15]
    emp = [c for c in ativos if work.is_employed(c)]
    proc = [c for c in ativos if work.is_seeking(c)]
    por_nivel = {}
    for c in adultos:
        por_nivel.setdefault(work.education_level(c), []).append(c.income)
    vg = firms.vacancy_stats(game)
    now_i = game.year * 12 + game.month
    idx = cycle.current(game)
    return {
        "clima": cycle.label(idx), "indice_ciclo": idx,
        "inflacao_anual": macro.annual_rate(game), "inflacao_ano_anterior": game.macro["inflation_prev"],
        "indice_precos": macro.price_level(game), "salario_minimo": macro.min_wage(game),
        "salario_minimo_real": macro.real_min_wage(game),
        "receita_estado": game.macro["rec"], "despesa_estado": game.macro["desp"],
        "receita_estado_ano_anterior": game.macro["rec_prev"], "despesa_estado_ano_anterior": game.macro["desp_prev"],
        "tesouro": game.macro["treasury"],
        "segurados": sum(1 for c in game.characters.values() if c.alive and receiving_unemployment(c, now_i)),
        "empresas_abertas": vg["abertas"], "empresas_fechadas": vg["fechadas"], "vagas": vg["vagas"],
        "vagas_livres": vg["livres"], "vacancia": vg["vacancia"],
        "populacao": sum(1 for c in game.characters.values() if c.alive), "adultos": len(adultos),
        "renda_media": sum(rendas) / len(rendas) if rendas else 0.0,
        "renda_mediana": sorted(rendas)[len(rendas) // 2] if rendas else 0.0,
        "gini_renda": gini(rendas), "patrimonio_total": sum(pat),
        "patrimonio_mediano": pat[len(pat) // 2] if pat else 0.0,
        "empregados": len(emp), "procurando": len(proc),
        "informais": sum(1 for c in emp if c.informal),
        "renda_por_escolaridade": {k: sum(v) / len(v) for k, v in sorted(por_nivel.items())},
    }
