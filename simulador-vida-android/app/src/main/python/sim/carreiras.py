"""Concursos públicos, empreendedorismo e política (Fases 5 e 8 — v0.17.0)."""
from __future__ import annotations

import random

from . import cycle, educacao_br, firms, intelecto, macro, mundo, work
from .models import Game

CONCURSOS = [
    ("aux_prefeitura", "Auxiliar Administrativo Municipal", "aux_administrativo", 2, 54, 2.4),
    ("tecnico_tribunal", "Técnico Administrativo / Judiciário", "tecnico_medio", 2, 66, 3.8),
    ("professor_publico", "Professor(a) da Rede Pública", "professor", 3, 60, 4.0),
    ("analista_federal", "Analista Público Federal", "analista_sistemas", 3, 74, 6.8),
    ("auditor_fiscal", "Auditor(a) Fiscal", "contador", 3, 84, 11.0),
]
CONCURSOS_POR_ID = {c[0]: c for c in CONCURSOS}

PARTIDOS = [
    ("civico", "Partido Cívico"),
    ("trabalhista", "Movimento Trabalhista"),
    ("liberal", "Aliança Liberal"),
    ("verde", "Frente Verde"),
    ("social", "União Social"),
]
PARTIDOS_POR_ID = dict(PARTIDOS)

CARGOS_POLITICOS = [
    ("vereador", "Vereador(a)", 18, 40, 3.5),
    ("prefeito", "Prefeito(a)", 21, 62, 7.5),
    ("deputado", "Deputado(a)", 21, 68, 9.0),
    ("senador", "Senador(a)", 35, 78, 11.0),
]
CARGOS_POR_ID = {c[0]: c for c in CARGOS_POLITICOS}


def _jogador(game: Game):
    p = game.characters.get(game.player_id) if game.player_id is not None else None
    return p if p is not None and p.alive else None


def _mes(game: Game) -> int:
    return game.year * 12 + game.month


def prestar_concurso(game: Game, concurso_id: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 18:
        raise ValueError("Concursos públicos exigem 18 anos ou mais.")
    if concurso_id not in CONCURSOS_POR_ID:
        raise ValueError("Concurso inválido.")
    _, cargo, occ, niv_min, dif, sal_m = CONCURSOS_POR_ID[concurso_id]
    if work.education_level(p) < niv_min:
        raise ValueError(f"Este concurso exige {work.NIVEIS[niv_min]}.")
    ex = game.carreira_extra.setdefault(p.id, {})
    mes = _mes(game)
    if ex.get("ultimo_concurso") == mes:
        raise ValueError("Você já prestou um concurso neste mês.")
    taxa = round(0.05 * macro.min_wage(game), 2)
    if p.wealth < taxa:
        raise ValueError("Patrimônio insuficiente para a taxa de inscrição.")
    p.wealth = round(p.wealth - taxa, 2)
    ex["ultimo_concurso"] = mes

    r = random.Random(f"concurso:{game.seed}:{mes}:{p.id}:{concurso_id}")
    bonus_pos = len(game.educacao_br.get(p.id, {}).get("pos_concluidas", [])) * 4
    bonus_livros = min(8, len(game.livros.get(p.id, [])) // 2)
    bonus_foco = 6 if game.foco.get(p.id) == "estudar" else 0
    bonus_prep = intelecto.bonus_concurso_atual(game, p.id)
    nota = work.work_aptitude(p) + bonus_pos + bonus_livros + bonus_foco + bonus_prep + r.gauss(0, 8)
    passou = nota >= dif
    if passou:
        p.retired, p.occupation, p.job_start, p.seeking_since = False, occ, mes, None
        p.informal, p.rank, p.rank_since, p.workplace = False, 1, mes, None
        p.jobs_held += 1
        ex["estavel"], ex["cargo_publico"], ex["salario_minimos"] = True, cargo, sal_m
        p.income = round(sal_m * macro.min_wage(game) * educacao_br.bonus_salarial_pos(game, p.id), 2)
        cid_n, cid_uf = mundo.cidade_of(game, p.id)[1:3]
        local_txt = f" em {cid_n}/{cid_uf}" if concurso_id == "aux_prefeitura" else ""
        game.add_event(p.id, "concurso", f"Aprovado(a) no concurso para {cargo}{local_txt} (estabilidade pública).")
    else:
        game.add_event(p.id, "concurso", f"Prestou concurso para {cargo}, mas não atingiu a nota de corte.")
    return {"aprovado": passou, "cargo": cargo, "nota": round(nota, 1), "corte": dif}


def abrir_empresa(game: Game, setor: str, porte: str = "micro") -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 18:
        raise ValueError("É preciso ter 18 anos ou mais para abrir uma empresa.")
    if setor not in firms.SETORES:
        raise ValueError("Setor inválido.")
    if porte not in ("micro", "pequena"):
        raise ValueError("Ao fundar, escolha porte micro ou pequena.")
    ex = game.carreira_extra.setdefault(p.id, {})
    if ex.get("empresa_id") is not None and game.firms.get(ex["empresa_id"]) and game.firms[ex["empresa_id"]].is_open:
        raise ValueError("Você já administra uma empresa aberta.")
    mw = macro.min_wage(game)
    capital = round((8.0 if porte == "micro" else 22.0) * mw, 2)
    if p.wealth < capital:
        raise ValueError(f"Capital inicial insuficiente (exige R$ {capital:,.2f}).")
    p.wealth = round(p.wealth - capital, 2)
    f = firms.found_firm(game, sector=setor, size=porte)
    ex["empresa_id"], ex["estavel"], ex["cargo_publico"] = f.id, False, None
    p.retired, p.occupation, p.workplace = False, next(iter(f.slots)), f.id
    p.job_start = p.rank_since = _mes(game)
    p.seeking_since, p.informal, p.rank = None, False, 3
    p.jobs_held += 1
    game.add_event(p.id, "empresa", f"Fundou a {f.name} ({f.sector}, porte {f.size}).")
    return {"id": f.id, "nome": f.name, "setor": f.sector, "porte": f.size, "capital": capital}


def encerrar_empresa(game: Game) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    ex = game.carreira_extra.get(p.id, {})
    fid = ex.get("empresa_id")
    if fid is None or fid not in game.firms or not game.firms[fid].is_open:
        raise ValueError("Você não possui empresa aberta.")
    f = game.firms[fid]
    firms.close_firm(game, fid, reason="foi encerrada pelo fundador")
    ex["empresa_id"] = None
    game.add_event(p.id, "empresa", f"Encerrou as atividades da {f.name}.")
    return {"nome": f.name}


def politica_of(game: Game, cid: int) -> dict:
    return game.politica.setdefault(cid, {
        "partido": None, "influencia": 0.0, "cargo": None, "mandato_meses": 0, "ultimo_ato": None,
    })


def filiar(game: Game, partido_id: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 16:
        raise ValueError("Filiação partidária disponível a partir dos 16 anos.")
    if partido_id not in PARTIDOS_POR_ID:
        raise ValueError("Partido inválido.")
    pol = politica_of(game, p.id)
    pol["partido"] = partido_id
    pol["influencia"] = max(5.0, pol["influencia"])
    game.add_event(p.id, "politica", f"Filiou-se ao {PARTIDOS_POR_ID[partido_id]}.")
    return {"partido": PARTIDOS_POR_ID[partido_id]}


def fazer_campanha(game: Game) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    pol = politica_of(game, p.id)
    if not pol.get("partido"):
        raise ValueError("Filie-se a um partido antes de fazer campanha.")
    mes = _mes(game)
    if pol.get("ultimo_ato") == mes:
        raise ValueError("Você já fez campanha neste mês.")
    custo = round(0.15 * macro.min_wage(game), 2)
    if p.wealth < custo:
        raise ValueError("Patrimônio insuficiente para atos de campanha.")
    p.wealth = round(p.wealth - custo, 2)
    pol["ultimo_ato"] = mes
    pol["influencia"] = min(100.0, round(pol["influencia"] + 4.0 + 0.05 * p.personality.get("extroversao", 50), 1))
    game.add_event(p.id, "politica", f"Realizou campanha pelo {PARTIDOS_POR_ID[pol['partido']]} (influência {pol['influencia']:.0f}).")
    return {"influencia": pol["influencia"], "custo": custo}


def concorrer(game: Game, cargo_id: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if cargo_id not in CARGOS_POR_ID:
        raise ValueError("Cargo inválido.")
    _, nome_cargo, idade_min, dif, _ = CARGOS_POR_ID[cargo_id]
    if p.age_at(game.year, game.month) < idade_min:
        raise ValueError(f"Para concorrer a {nome_cargo} é preciso ter ao menos {idade_min} anos.")
    pol = politica_of(game, p.id)
    if not pol.get("partido"):
        raise ValueError("Filie-se a um partido antes de concorrer.")
    mes = _mes(game)
    if pol.get("ultimo_ato") == mes:
        raise ValueError("Você já disputou/fez campanha neste mês.")
    pol["ultimo_ato"] = mes
    r = random.Random(f"eleicao:{game.seed}:{mes}:{p.id}:{cargo_id}")
    carisma = 0.5 * p.personality.get("extroversao", 50) + 0.5 * p.personality.get("amabilidade", 50)
    pontos = 0.65 * pol["influencia"] + 0.35 * carisma + r.gauss(0, 9)
    eleito = pontos >= dif
    if eleito:
        pol["cargo"], pol["mandato_meses"] = cargo_id, 48
        pol["influencia"] = min(100.0, round(pol["influencia"] + 12, 1))
        cid_n, cid_uf = mundo.cidade_of(game, p.id)[1:3]
        ambito = f" em {cid_n}/{cid_uf}" if cargo_id in ("vereador", "prefeito") else f" por {cid_uf}"
        game.add_event(p.id, "politica", f"Eleito(a) {nome_cargo}{ambito} pelo {PARTIDOS_POR_ID[pol['partido']]} (mandato de 4 anos).")
    else:
        game.add_event(p.id, "politica", f"Concorreu a {nome_cargo}, mas não foi eleito(a).")
    return {"eleito": eleito, "cargo": nome_cargo, "pontos": round(pontos, 1), "corte": dif}


PORTE_PROXIMO = {"micro": ("pequena", 14.0), "pequena": ("média", 35.0), "média": ("grande", 80.0)}
LUCRO_PORTE = {"micro": 2.2, "pequena": 4.5, "média": 8.5, "grande": 15.0}

MOVIMENTOS = [
    ("sindicato", "Sindicato e Direitos Trabalhistas"),
    ("estudantil", "Movimento Estudantil e Educação Pública"),
    ("ambiental", "Coletivo Socioambiental"),
    ("comunitario", "Associação de Moradores e Saúde"),
]
MOVIMENTOS_POR_ID = dict(MOVIMENTOS)

PAUTAS_LEI = [
    ("educacao", "Ampliação de bolsas e laboratórios escolares", "ciencias", 2),
    ("saude", "Reforço à atenção básica de saúde pública", "psicologia", 1),
    ("economia", "Incentivo a microempresas e crédito produtivo", "economia", 2),
    ("ciencia", "Fundo de pesquisa científica e inovação", "ciencias", 2),
    ("ambiente", "Preservação ambiental e áreas verdes urbanas", "humanas", 2),
]
PAUTAS_POR_ID = {p[0]: p for p in PAUTAS_LEI}


def expandir_empresa(game: Game) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    ex = game.carreira_extra.get(p.id, {})
    fid = ex.get("empresa_id")
    if fid is None or fid not in game.firms or not game.firms[fid].is_open:
        raise ValueError("Você não possui empresa própria aberta.")
    f = game.firms[fid]
    if f.size not in PORTE_PROXIMO:
        raise ValueError(f"A {f.name} já atingiu o maior porte (grande).")
    novo_porte, custo_m = PORTE_PROXIMO[f.size]
    mw = macro.min_wage(game)
    custo = round(custo_m * mw, 2)
    if p.wealth < custo:
        raise ValueError(f"Patrimônio insuficiente para expandir para porte {novo_porte} (exige {custo:,.2f}).")
    p.wealth = round(p.wealth - custo, 2)
    f.size = novo_porte
    mix = firms.SETORES[f.sector]
    r = random.Random(f"expand:{game.seed}:{_mes(game)}:{f.id}:{novo_porte}")
    extras = 6 if novo_porte == "pequena" else 14 if novo_porte == "média" else 28
    for occ in r.choices(list(mix), weights=list(mix.values()), k=extras):
        f.slots[occ] = f.slots.get(occ, 0) + 1
    mundo.registrar_transacao(game, p.id, "saida", custo, f"Expansão da {f.name} ({novo_porte})")
    game.add_event(p.id, "empresa", f"Expandiu a {f.name} para porte {novo_porte} (+{extras} vagas criadas).")
    return {"nome": f.name, "porte": novo_porte, "custo": custo, "vagas_novas": extras}


def iniciar_meio_periodo(game: Game, area: str = "Geral") -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 16:
        raise ValueError("Estágio / meio período disponível a partir dos 16 anos.")
    if p.retired or work.is_employed(p):
        raise ValueError("Disponível apenas para estudantes ou quem não tem vínculo integral.")
    ex = game.carreira_extra.setdefault(p.id, {})
    if ex.get("meio_periodo"):
        raise ValueError("Você já atua em estágio / meio período.")
    sal_m = 0.90 if p.in_college else 0.65
    area_limpa = (str(area or "Geral").strip()[:40]) or "Geral"
    ex["meio_periodo"] = {"area": area_limpa, "salario_minimos": sal_m}
    valor = round(sal_m * macro.min_wage(game), 2)
    game.add_event(p.id, "trabalho", f"Iniciou estágio / meio período em {area_limpa} (bolsa de {sal_m:.2f} mínimo/mês).")
    return {"area": area_limpa, "bolsa": valor, "salario_minimos": sal_m}


def sair_meio_periodo(game: Game) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    ex = game.carreira_extra.get(p.id, {})
    mp = ex.pop("meio_periodo", None)
    if not mp:
        raise ValueError("Você não está em estágio / meio período.")
    game.add_event(p.id, "trabalho", f"Encerrou o estágio / meio período em {mp.get('area', 'Geral')}.")
    return {"area": mp.get("area", "Geral")}


def fazer_freela(game: Game, area_id: str = "economia") -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 16:
        raise ValueError("Trabalho autônomo / freelancer disponível a partir dos 16 anos.")
    if area_id not in intelecto.AREAS_POR_ID:
        raise ValueError("Área inválida.")
    ex = game.carreira_extra.setdefault(p.id, {})
    mes = _mes(game)
    fl = ex.get("freelas_mes")
    if not isinstance(fl, list) or len(fl) != 2 or fl[0] != mes:
        fl = [mes, 0]
        ex["freelas_mes"] = fl
    if fl[1] >= 2:
        raise ValueError("Você já concluiu 2 projetos autônomos neste mês.")
    ist = intelecto.dados(game, p.id)
    pts = ist.get("conhecimentos", {}).get(area_id, 0)
    idiomas_flu = sum(1 for v in ist.get("idiomas", {}).values() if v >= 70)
    tem_pc = mundo.tem_equipamento(game, p.id, "notebook")
    fator_mw = 0.25 + min(0.45, pts * 0.025) + min(0.24, idiomas_flu * 0.12) + (0.20 if tem_pc else 0.0)
    valor = round(fator_mw * macro.min_wage(game), 2)
    p.wealth = round(p.wealth + valor, 2)
    p.experience += 1
    p.health = max(0.0, round(p.health - 0.35, 2))
    intelecto.adicionar_conhecimento(game, p.id, area_id, 1)
    fl[1] += 1
    area_nome = intelecto.AREAS_POR_ID[area_id][1]
    mundo.registrar_transacao(game, p.id, "entrada", valor, f"Projeto autônomo ({area_nome})")
    game.add_event(p.id, "trabalho", f"Concluiu projeto freelancer de {area_nome} e recebeu R$ {valor:,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."))
    return {"area": area_nome, "valor": valor, "restantes": 2 - fl[1]}


def fazer_freelas_lote(game: Game, area_id: str = "economia") -> dict:
    """Executa todos os projetos freelancer restantes do mês em 1 clique."""
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    ex = game.carreira_extra.setdefault(p.id, {})
    mes = _mes(game)
    fl = ex.get("freelas_mes")
    feitos = fl[1] if isinstance(fl, list) and len(fl) == 2 and fl[0] == mes else 0
    disp = max(0, 2 - feitos)
    if disp <= 0:
        raise ValueError("Você já concluiu os 2 projetos autônomos deste mês.")
    total = 0.0
    area_nome = area_id
    for _ in range(disp):
        r = fazer_freela(game, area_id)
        total = round(total + r["valor"], 2)
        area_nome = r["area"]
    return {"area": area_nome, "quantidade": disp, "valor": total, "restantes": 0}


def trabalho_extra(game: Game) -> dict:
    """Realiza hora extra / turno adicional no trabalho (ou estágio) até 2 vezes/mês."""
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < work.IDADE_TRABALHO_MIN:
        raise ValueError(f"Trabalho disponível a partir dos {work.IDADE_TRABALHO_MIN} anos.")
    ex = game.carreira_extra.setdefault(p.id, {})
    if not work.is_employed(p) and not ex.get("meio_periodo") and not ex.get("estavel"):
        raise ValueError("É preciso estar trabalhando ou em estágio para fazer hora extra.")
    mes = _mes(game)
    xm = ex.get("extras_mes")
    if not isinstance(xm, list) or len(xm) != 2 or xm[0] != mes:
        xm = [mes, 0]
        ex["extras_mes"] = xm
    if xm[1] >= 2:
        raise ValueError("Você já realizou 2 turnos extras neste mês.")
    base_renda = p.income if p.income > 0 else macro.min_wage(game)
    bonus = round(max(0.18 * macro.min_wage(game), 0.12 * base_renda), 2)
    p.wealth = round(p.wealth + bonus, 2)
    p.experience += 1
    p.health = max(0.0, round(p.health - 0.3, 2))
    xm[1] += 1
    mundo.registrar_transacao(game, p.id, "entrada", bonus, "Hora extra / turno adicional")
    game.add_event(p.id, "trabalho", f"Realizou hora extra no trabalho e recebeu R$ {bonus:,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."))
    return {"valor": bonus, "restantes": 2 - xm[1]}


def participar_movimento(game: Game, mov_id: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 16:
        raise ValueError("Participação em sindicatos e movimentos a partir dos 16 anos.")
    if mov_id not in MOVIMENTOS_POR_ID:
        raise ValueError("Movimento inválido.")
    pol = politica_of(game, p.id)
    mes = _mes(game)
    if pol.get("ultimo_mov") == mes:
        raise ValueError("Você já participou de uma assembleia ou ação cívica neste mês.")
    pol["ultimo_mov"] = mes
    pol["influencia"] = min(100.0, round(pol.get("influencia", 0.0) + 3.5, 1))
    pol["movimentos_feitos"] = int(pol.get("movimentos_feitos", 0)) + 1
    if pol["movimentos_feitos"] % 2 == 0:
        p.personality["extroversao"] = min(99, p.personality.get("extroversao", 50) + 1)
        p.personality["amabilidade"] = min(99, p.personality.get("amabilidade", 50) + 1)
    nome = MOVIMENTOS_POR_ID[mov_id]
    game.add_event(p.id, "politica", f"Participou de ação no(a) {nome} (influência {pol['influencia']:.0f}).")
    return {"movimento": nome, "influencia": pol["influencia"]}


def propor_projeto(game: Game, pauta_id: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    pol = politica_of(game, p.id)
    if not pol.get("cargo"):
        raise ValueError("É preciso exercer um mandato eletivo para propor projetos de lei.")
    if pauta_id not in PAUTAS_POR_ID:
        raise ValueError("Pauta legislativa inválida.")
    mes = _mes(game)
    ult = int(pol.get("ultimo_projeto") or 0)
    if mes - ult < 3:
        raise ValueError(f"Aguarde mais {3 - (mes - ult)} mês(es) para apresentar novo projeto.")
    pol["ultimo_projeto"] = mes
    _, titulo, area_id, pts = PAUTAS_POR_ID[pauta_id]
    pol["influencia"] = min(100.0, round(pol.get("influencia", 0.0) + 6.0, 1))
    intelecto.adicionar_conhecimento(game, p.id, area_id, pts)
    if pauta_id == "saude":
        p.health = min(100.0, round(p.health + 1.0, 2))
    cargo_n = CARGOS_POR_ID[pol["cargo"]][1]
    game.noticias.append({
        "ano": game.year, "mes": game.month, "tipo": "simulada",
        "titulo": f"Projeto aprovado: {titulo}",
        "texto": f"Proposta apresentada pelo mandato de {p.full_name} ({cargo_n}) avança no legislativo.",
    })
    if len(game.noticias) > 120:
        del game.noticias[:-120]
    game.add_event(p.id, "politica", f"Apresentou e aprovou projeto de lei: {titulo}.")
    return {"titulo": titulo, "influencia": pol["influencia"]}


def apply_month(game: Game) -> None:
    mw = macro.min_wage(game)
    idx = cycle.current(game)
    for cid, ex in list(game.carreira_extra.items()):
        c = game.characters.get(cid)
        if c is None or not c.alive:
            continue
        if ex.get("meio_periodo"):
            if c.retired or work.is_employed(c):
                ex.pop("meio_periodo", None)
            else:
                bolsa = round(float(ex["meio_periodo"].get("salario_minimos", 0.65)) * mw, 2)
                c.wealth = round(c.wealth + bolsa, 2)
                c.experience += 1
                c.income = round(max(c.income, bolsa), 2)
        if ex.get("estavel") and ex.get("salario_minimos"):
            c.income = round(
                ex["salario_minimos"] * mw * educacao_br.bonus_salarial_pos(game, cid) * intelecto.bonus_salarial_idiomas(game, cid),
                2,
            )
        fid = ex.get("empresa_id")
        if fid is not None and fid in game.firms and game.firms[fid].is_open:
            f = game.firms[fid]
            mult = LUCRO_PORTE.get(f.size, 2.2)
            base_lucro = mult * mw * (1 + 0.5 * idx)
            c.wealth = round(c.wealth + max(0.0, base_lucro), 2)
            c.income = round(max(c.income, base_lucro), 2)
    for cid, pol in list(game.politica.items()):
        c = game.characters.get(cid)
        if c is None or not c.alive or not pol.get("cargo"):
            continue
        c.wealth = round(c.wealth + CARGOS_POR_ID[pol["cargo"]][4] * mw, 2)
        pol["mandato_meses"] -= 1
        if pol["mandato_meses"] <= 0:
            nome_cargo = CARGOS_POR_ID[pol["cargo"]][1]
            pol["cargo"] = None
            game.add_event(cid, "politica", f"Encerrou o mandato de {nome_cargo}.")
