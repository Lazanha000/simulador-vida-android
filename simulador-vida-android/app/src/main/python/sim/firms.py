"""Empresas e vagas (Fase 5/7, v0.8.0): empresas genéricas com número limitado de vagas por ocupação.

Substitui o "local de trabalho" numérico: `Character.workplace` passa a ser o id de uma `Firm`.
A contratação só ocorre em ocupações com vaga livre; empresas fecham (demitindo todos) e novas
são fundadas no rebalanceamento anual. Valores ILUSTRATIVOS; nenhuma empresa ou instituição real.
Nada aqui usa `game.rng`: usa geradores locais derivados da semente (carregar e continuar é idêntico).
"""
from __future__ import annotations

import math
import random

from . import cycle, work
from .models import Firm, Game

ATIVO = True               # interruptor: False = v0.7.0 (local de trabalho 0–24 sem vagas)
EMPRESAS_INICIAIS = 24     # empresas criadas no primeiro uso do mundo
VACANCIA_ALVO = 0.12       # fração de vagas livres desejada por ocupação no rebalanceamento anual
VACANCIA_MIN_ABS = 1       # mínimo de vagas livres desejado por ocupação
EXCESSO_FATOR = 2.5        # acima de desejado×2,5+1 vagas livres, as empresas reduzem vagas (o mercado escala com a população)
EXCESSO_FOLGA = 1
CHANCE_FUNDAR = 0.35       # ao faltar vaga: chance de fundar empresa nova (senão, uma existente expande)
EMPRESAS_ABERTAS_MIN = 5   # nunca fecha abaixo disso
MAX_ITER_REBALANCE = 400

# porte: (vagas mín., vagas máx., chance anual de fechar, fator de informalidade, peso na fundação)
PORTES = {
    "micro": (3, 6, 0.040, 1.5, 5),
    "pequena": (7, 15, 0.025, 1.1, 4),
    "média": (20, 45, 0.012, 0.8, 2),
    "grande": (60, 120, 0.005, 0.5, 1),
}
# setor -> {ocupação: peso}. Todas as ocupações de `work.OCUPACOES` aparecem em algum setor.
SETORES = {
    "comércio": {"atendente_comercio": 5, "representante_vendas": 3, "aux_administrativo": 2,
                 "servicos_gerais": 1, "motorista_entregas": 2, "contador": 0.4, "designer": 0.3,
                 "administrador": 0.6, "farmaceutico": 0.4, "publicitario": 0.3, "analista_ri": 0.2},
    "indústria": {"operador_producao": 6, "tecnico_medio": 2, "engenheiro": 0.9, "servicos_gerais": 1,
                  "vigilante": 1, "aux_administrativo": 1, "motorista_entregas": 1, "auxiliar_limpeza": 1,
                  "administrador": 0.4, "quimico": 0.4, "farmaceutico": 0.3, "agronomo": 0.25, "estatistico": 0.25},
    "agropecuária": {"trabalhador_rural": 8, "motorista_entregas": 1, "tecnico_medio": 0.5, "servicos_gerais": 1,
                     "agronomo": 0.6, "veterinario": 0.5, "biologo": 0.3, "quimico": 0.25},
    "construção": {"ajudante_obras": 6, "engenheiro": 0.9, "tecnico_medio": 1, "vigilante": 1, "motorista_entregas": 1,
                   "arquiteto": 0.6, "administrador": 0.25},
    "serviços": {"servicos_gerais": 3, "auxiliar_limpeza": 3, "auxiliar_cozinha": 3, "vigilante": 2,
                 "aux_administrativo": 2, "atendente_comercio": 1, "contador": 0.8, "advogado": 0.8,
                 "psicologo": 0.4, "designer": 0.5, "administrador": 0.5, "arquiteto": 0.3,
                 "dentista": 0.35, "fisioterapeuta": 0.35, "nutricionista": 0.3, "veterinario": 0.25,
                 "jornalista": 0.35, "publicitario": 0.4, "assistente_social": 0.3, "sociologo": 0.2},
    "educação e saúde": {"professor": 4.2, "enfermeiro": 2.5, "medico": 0.9, "aux_administrativo": 1,
                         "auxiliar_limpeza": 1, "auxiliar_cozinha": 1, "vigilante": 1,
                         "psicologo": 0.6, "pesquisador": 0.45, "dentista": 0.45, "farmaceutico": 0.4,
                         "fisioterapeuta": 0.45, "nutricionista": 0.4, "biologo": 0.35,
                         "assistente_social": 0.4, "sociologo": 0.25, "matematico": 0.3},
    "tecnologia e finanças": {"analista_sistemas": 3.5, "contador": 1.6, "advogado": 0.9, "aux_administrativo": 2,
                              "representante_vendas": 1, "tecnico_medio": 1, "engenheiro": 0.4,
                              "economista": 0.7, "pesquisador": 0.4, "designer": 0.5, "administrador": 0.6,
                              "jornalista": 0.3, "analista_ri": 0.35, "estatistico": 0.55, "matematico": 0.4},
}


def _rng(game: Game, *parts) -> random.Random:
    return random.Random(f"{game.seed}:firm:" + ":".join(str(p) for p in parts))


def _now(game: Game) -> int:
    return game.year * 12 + game.month


def informal_factor(firm: Firm | None) -> float:
    return PORTES[firm.size][3] if firm is not None else 1.0


def informal_probability(level: int, firm: Firm | None) -> float:
    """Chance de vínculo informal: base por nível da ocupação × fator do porte (micro informal mais, grande menos)."""
    return min(0.95, work.INFORMAL_PROB[level] * informal_factor(firm))


# --- criação ------------------------------------------------------------
def found_firm(game: Game, sector: str | None = None, size: str | None = None,
               must_have: str | None = None) -> Firm:
    """Funda uma empresa (determinístico). `must_have` garante o setor e ≥1 vaga naquela ocupação."""
    fid = game.next_firm_id
    game.next_firm_id += 1
    rng = _rng(game, "found", fid)
    if sector is None:
        setores = [s for s in SETORES if must_have is None or must_have in SETORES[s]]
        pesos = [SETORES[s][must_have] if must_have else 1.0 for s in setores]
        sector = rng.choices(setores, weights=pesos, k=1)[0]
    if size is None:
        nomes = list(PORTES)
        size = rng.choices(nomes, weights=[PORTES[n][4] for n in nomes], k=1)[0]
    lo, hi = PORTES[size][0], PORTES[size][1]
    total = rng.randint(lo, hi)
    mix = SETORES[sector]
    slots: dict[str, int] = {}
    for key in rng.choices(list(mix), weights=list(mix.values()), k=total):
        slots[key] = slots.get(key, 0) + 1
    if must_have is not None and slots.get(must_have, 0) < 1:
        slots[must_have] = 1
    f = Firm(fid, f"Empresa {fid + 1:03d}", sector, size, _now(game), None, slots)
    game.firms[fid] = f
    return f


def ensure_world(game: Game) -> None:
    """Cria o conjunto inicial de empresas no primeiro uso (idempotente)."""
    if game.firms:
        return
    for _ in range(EMPRESAS_INICIAIS):
        found_firm(game)


# --- consultas ----------------------------------------------------------
def filled(game: Game, exclude_id: int | None = None) -> dict[tuple[int, str], int]:
    """Vagas ocupadas: (id da empresa, ocupação) -> nº de empregados (aposentados e mortos não contam)."""
    out: dict[tuple[int, str], int] = {}
    for c in game.characters.values():
        if c.id != exclude_id and work.is_employed(c) and c.workplace is not None:
            k = (c.workplace, c.occupation)
            out[k] = out.get(k, 0) + 1
    return out


def free_by_firm(game: Game, key: str, exclude_id: int | None = None) -> list[tuple[Firm, int]]:
    """Empresas abertas com vaga livre na ocupação `key`, em ordem de id."""
    fill = filled(game, exclude_id)
    out = []
    for fid in sorted(game.firms):
        f = game.firms[fid]
        if f.is_open:
            livres = f.slots.get(key, 0) - fill.get((fid, key), 0)
            if livres > 0:
                out.append((f, livres))
    return out


def open_occupations(game: Game, exclude_id: int | None = None) -> set[str]:
    """Ocupações com pelo menos uma vaga livre em alguma empresa aberta."""
    ensure_world(game)
    fill = filled(game, exclude_id)
    out = set()
    for f in game.firms.values():
        if f.is_open:
            for key, cap in f.slots.items():
                if cap - fill.get((f.id, key), 0) > 0:
                    out.add(key)
    return out


def vacancy_stats(game: Game) -> dict:
    """Panorama de empresas: abertas/fechadas, vagas totais/ocupadas/livres e taxa de vacância."""
    fill = filled(game)
    abertas = [f for f in game.firms.values() if f.is_open]
    total = sum(sum(f.slots.values()) for f in abertas)
    ocup = sum(min(v, game.firms[fid].slots.get(k, 0)) if game.firms.get(fid) and game.firms[fid].is_open else 0
               for (fid, k), v in fill.items())
    return {"abertas": len(abertas), "fechadas": len(game.firms) - len(abertas), "vagas": total,
            "ocupadas": ocup, "livres": total - ocup, "vacancia": (total - ocup) / total if total else 0.0}


# --- alocação de um trabalhador --------------------------------------------
def pick_firm(game: Game, key: str, rng: random.Random, exclude_id: int | None = None) -> Firm:
    """Escolhe a empresa de um novo vínculo na ocupação `key` (sorteio ponderado pelas vagas livres).
    Sem vaga livre (colocação inicial, saves antigos, chamadas diretas): amplia uma empresa existente
    do setor ou, em último caso, funda uma microempresa; a contratação mensal nunca chega aqui."""
    ensure_world(game)
    cands = free_by_firm(game, key, exclude_id)
    if cands:
        return rng.choices([f for f, _ in cands], weights=[n for _, n in cands], k=1)[0]
    com_vaga_no_setor = [f for fid, f in sorted(game.firms.items()) if f.is_open and key in SETORES[f.sector]]
    if com_vaga_no_setor:
        f = rng.choice(com_vaga_no_setor)
        f.slots[key] = f.slots.get(key, 0) + 1
        return f
    f = found_firm(game, size="micro", must_have=key)
    return f


def close_firm(game: Game, firm_id: int, reason: str = "encerrou as atividades") -> list:
    """Fecha a empresa: perde as vagas e demite todos (evento na biografia, passam a procurar trabalho)."""
    f = game.firms[firm_id]
    if not f.is_open:
        return []
    from . import economy  # import tardio: economy importa este módulo
    now = _now(game)
    f.closed = now
    demitidos = []
    for cid in sorted(game.characters):
        c = game.characters[cid]
        if work.is_employed(c) and c.workplace == firm_id:
            game.add_event(c.id, "trabalho",
                           f"Perdeu o emprego ({work.occupation_name(c.occupation, c.sex)}): a {f.name} {reason}.")
            economy.grant_unemployment(game, c, now)   # antes de clear_job (seguro-desemprego, v0.9.1)
            work.clear_job(c)
            c.seeking_since = now
            demitidos.append(c)
    return demitidos


# --- rebalanceamento anual --------------------------------------------------
def yearly(game: Game) -> dict:
    """Rodado em janeiro: (1) algumas empresas fecham (mais as pequenas); (2) o mercado repõe vagas até a
    vacância-alvo por ocupação (expandindo empresas ou fundando novas). Determinístico, sem `game.rng`."""
    ensure_world(game)
    now = _now(game)
    idx = cycle.current(game)  # ciclo econômico (v0.9.0): recessão fecha mais empresas e abre menos vagas
    f_fecha, vac_alvo = cycle.closure_factor(idx), VACANCIA_ALVO * cycle.vacancy_factor(idx)
    fechadas, fundadas, dissolvidas = [], [], []
    abertas = [f for f in sorted(game.firms.values(), key=lambda x: x.id) if f.is_open]
    for f in abertas:
        if sum(1 for x in game.firms.values() if x.is_open) <= EMPRESAS_ABERTAS_MIN:
            break
        if _rng(game, "close", f.id, now).random() < PORTES[f.size][2] * f_fecha:
            close_firm(game, f.id)
            fechadas.append(f.id)
    fill = filled(game)
    por_ocup: dict[str, int] = {}
    for (fid, k), v in fill.items():
        por_ocup[k] = por_ocup.get(k, 0) + v
    for oc in work.OCUPACOES:
        key = oc[0]
        desejado = max(VACANCIA_MIN_ABS, math.ceil(vac_alvo * por_ocup.get(key, 0)))
        limite = math.ceil(desejado * EXCESSO_FATOR) + EXCESSO_FOLGA
        for it in range(MAX_ITER_REBALANCE):  # excesso de vagas: empresas enxugam (nunca abaixo do nº de empregados)
            livres_f = free_by_firm(game, key)
            livres = sum(n for _, n in livres_f)
            if livres <= limite:
                break
            rng = _rng(game, "shrink", key, now, it)
            alvo, n_livres = rng.choices(livres_f, weights=[n for _, n in livres_f], k=1)[0]
            corte = min(n_livres, max(1, math.ceil(0.25 * n_livres)), livres - limite)
            alvo.slots[key] -= corte
            if alvo.slots[key] <= 0:
                del alvo.slots[key]
        for it in range(MAX_ITER_REBALANCE):
            livres = sum(n for _, n in free_by_firm(game, key))
            if livres >= desejado:
                break
            rng = _rng(game, "grow", key, now, it)
            existentes = [f for f in sorted(game.firms.values(), key=lambda x: x.id)
                          if f.is_open and key in SETORES[f.sector]]
            if not existentes or rng.random() < CHANCE_FUNDAR:
                fundadas.append(found_firm(game, must_have=key).id)
            else:
                f = rng.choice(existentes)
                f.slots[key] = f.slots.get(key, 0) + max(1, math.ceil(0.15 * f.slots.get(key, 0)))
    # Empresas sem vagas e sem empregados são dissolvidas (sem demissões).
    empregadas = {fid for (fid, _) in filled(game)}
    for fid in sorted(game.firms):
        f = game.firms[fid]
        if (f.is_open and not any(f.slots.values()) and fid not in empregadas
                and sum(1 for x in game.firms.values() if x.is_open) > EMPRESAS_ABERTAS_MIN):
            f.closed = now
            dissolvidas.append(fid)
    return {"fechadas": fechadas, "fundadas": fundadas, "dissolvidas": dissolvidas}


def reconcile(game: Game, force: bool = False) -> None:
    """Dá empresa real a quem trabalha sem uma (saves antigos, workplace inválido ou empresa fechada).
    `force` reatribui todos os empregados (saves ≤ v8, em que workplace era só um número 0–24)."""
    ensure_world(game)
    for cid in sorted(game.characters):
        c = game.characters[cid]
        if not work.is_employed(c):
            continue
        f = game.firms.get(c.workplace) if c.workplace is not None else None
        if force or f is None or not f.is_open:
            rng = _rng(game, "adopt", c.id)
            nova = pick_firm(game, c.occupation, rng, exclude_id=c.id)
            c.workplace = nova.id


__all__ = [n for n in dir() if not n.startswith("_") and n not in ("math", "random", "Game", "Firm")]
