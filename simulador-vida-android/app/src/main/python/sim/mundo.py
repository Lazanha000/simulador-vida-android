"""Mundo, geografia brasileira, bancos, patrimônio e notícias (Fases 6, 7 e 8 — v0.17.0)."""
from __future__ import annotations

import random

from . import cycle, macro
from .models import Game

CIDADES = [
    ("bh", "Belo Horizonte", "MG", 1.00),
    ("sp", "São Paulo", "SP", 1.25),
    ("rj", "Rio de Janeiro", "RJ", 1.20),
    ("campinas", "Campinas", "SP", 1.08),
    ("bsb", "Brasília", "DF", 1.22),
    ("poa", "Porto Alegre", "RS", 1.02),
    ("curitiba", "Curitiba", "PR", 1.02),
    ("florianopolis", "Florianópolis", "SC", 1.12),
    ("salvador", "Salvador", "BA", 0.92),
    ("recife", "Recife", "PE", 0.94),
    ("fortaleza", "Fortaleza", "CE", 0.88),
    ("goiania", "Goiânia", "GO", 0.92),
    ("natal", "Natal", "RN", 0.86),
    ("manaus", "Manaus", "AM", 0.95),
]
CIDADES_POR_ID = {c[0]: c for c in CIDADES}

IMOVEIS = [
    ("kitnet", "Kitnet urbana", 80.0, 0.12, 0.55, 0.32),
    ("apartamento", "Apartamento padrão", 180.0, 0.22, 1.10, 0.48),
    ("casa", "Casa espaçosa", 320.0, 0.38, 1.80, 0.62),
]
IMOVEIS_POR_ID = {x[0]: x for x in IMOVEIS}

VEICULOS = [
    ("moto", "Motocicleta", 10.0, 0.10),
    ("carro_pop", "Carro popular", 35.0, 0.25),
    ("carro_exec", "Carro médio", 75.0, 0.45),
]
VEICULOS_POR_ID = {x[0]: x for x in VEICULOS}

INVESTIMENTOS = {
    "poupanca": "Poupança",
    "tesouro": "Renda fixa (Tesouro)",
    "acoes": "Ações na bolsa",
}

EQUIPAMENTOS = [
    ("notebook", "Notebook profissional", 2.2, "Potencializa estudos, idiomas, pesquisa e renda freelancer."),
    ("biblioteca", "Biblioteca particular", 1.5, "Amplia a capacidade mensal de leitura (+150 págs/mês)."),
    ("kit_esportivo", "Bicicleta e kit esportivo", 1.2, "Ajuda na saúde mensal (+0,30/mês) e mobilidade."),
    ("instrumento", "Instrumento musical e ateliê", 1.6, "Estimula a criatividade e expressão cultural."),
]
EQUIPAMENTOS_POR_ID = {e[0]: e for e in EQUIPAMENTOS}

PLANO_SAUDE_MENSAL_MINIMOS = 0.28
JUROS_EMPRESTIMO_MENSAL = 0.018
PRAZO_EMPRESTIMO = 24


def _jogador(game: Game):
    p = game.characters.get(game.player_id) if game.player_id is not None else None
    return p if p is not None and p.alive else None


def _estado_pat(game: Game, cid: int) -> dict:
    st = game.patrimonio.setdefault(cid, {
        "imoveis": [],
        "veiculo": None,
        "inv": {"poupanca": 0.0, "tesouro": 0.0, "acoes": 0.0},
        "emprestimo": 0.0,
        "parcelas": 0,
        "equipamentos": [],
        "plano_saude": False,
    })
    st.setdefault("equipamentos", [])
    st.setdefault("plano_saude", False)
    return st


def registrar_transacao(game: Game, cid: int, tipo: str, valor: float, desc: str) -> None:
    reg = {"ano": game.year, "mes": game.month, "tipo": tipo, "valor": round(float(valor), 2), "desc": desc}
    log = game.financas_log.setdefault(cid, [])
    log.append(reg)
    if len(log) > 80:
        del log[:-80]


def extrato(game: Game, cid: int, limite: int = 25) -> list[dict]:
    return list(reversed(game.financas_log.get(cid, [])[-limite:]))


def tem_equipamento(game: Game, cid: int, equip_id: str) -> bool:
    st = game.patrimonio.get(cid)
    return bool(st and equip_id in st.get("equipamentos", []))


def cidade_of(game: Game, cid: int) -> tuple[str, str, str, float]:
    return CIDADES_POR_ID.get(game.cidades.get(cid, "bh"), CIDADES_POR_ID["bh"])


def fator_custo_domicilio(game: Game, adults: list) -> float:
    if not game.cidades or not adults:
        return 1.0
    return sum(cidade_of(game, a.id)[3] for a in adults) / len(adults)


def desconto_moradia_domicilio(game: Game, adults: list) -> float:
    if not game.patrimonio:
        return 0.0
    mw = macro.min_wage(game)
    melhor = 0.0
    for a in adults:
        st = game.patrimonio.get(a.id)
        if not st:
            continue
        for im in st.get("imoveis", []):
            if not im.get("alugado"):
                melhor = max(melhor, IMOVEIS_POR_ID[im["tipo"]][5] * mw)
    return round(melhor, 2)


def custo_mudanca(game: Game, p) -> float:
    idade = p.age_at(game.year, game.month)
    return 0.0 if idade < 18 else round(1.5 * macro.min_wage(game), 2)


def mudar_cidade(game: Game, cidade_id: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if cidade_id not in CIDADES_POR_ID:
        raise ValueError("Cidade inválida.")
    if cidade_of(game, p.id)[0] == cidade_id:
        raise ValueError("Você já mora nessa cidade.")
    _, nome, uf, fator = CIDADES_POR_ID[cidade_id]
    custo = custo_mudanca(game, p)
    if p.wealth < custo:
        raise ValueError("Patrimônio insuficiente para custear a mudança.")
    p.wealth = round(p.wealth - custo, 2)
    game.cidades[p.id] = cidade_id
    pol = game.politica.get(p.id)
    if pol and pol.get("cargo") in ("vereador", "prefeito"):
        cargo_ant = pol["cargo"]
        pol["cargo"], pol["mandato_meses"] = None, 0
        game.add_event(p.id, "politica", f"Renunciou ao mandato municipal de {cargo_ant} ao mudar de cidade.")
    game.add_event(p.id, "mudanca", f"Mudou-se para {nome}/{uf}.")
    return {"cidade": f"{nome}/{uf}", "custo": custo, "fator_custo": fator}


def comprar_imovel(game: Game, tipo: str, alugar: bool = False) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 18:
        raise ValueError("Só maiores de 18 anos podem comprar imóveis.")
    if tipo not in IMOVEIS_POR_ID:
        raise ValueError("Tipo de imóvel inválido.")
    _, nome, preco_m, _, _, _ = IMOVEIS_POR_ID[tipo]
    preco = round(preco_m * macro.min_wage(game) * cidade_of(game, p.id)[3], 2)
    if p.wealth < preco:
        raise ValueError("Patrimônio insuficiente para comprar este imóvel.")
    p.wealth = round(p.wealth - preco, 2)
    st = _estado_pat(game, p.id)
    st["imoveis"].append({"tipo": tipo, "valor": preco, "alugado": bool(alugar)})
    uso = "para alugar" if alugar else "para moradia"
    registrar_transacao(game, p.id, "saida", preco, f"Compra: {nome} ({uso})")
    game.add_event(p.id, "imovel", f"Comprou {nome} ({uso}) por R$ {preco:,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."))
    return {"nome": nome, "preco": preco, "alugado": bool(alugar)}


def vender_imovel(game: Game, idx: int) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    st = _estado_pat(game, p.id)
    if not 0 <= idx < len(st["imoveis"]):
        raise ValueError("Imóvel não encontrado.")
    im = st["imoveis"].pop(idx)
    nome = IMOVEIS_POR_ID[im["tipo"]][1]
    valor = round(im["valor"], 2)
    p.wealth = round(p.wealth + valor, 2)
    registrar_transacao(game, p.id, "entrada", valor, f"Venda: {nome}")
    game.add_event(p.id, "imovel", f"Vendeu {nome} por R$ {valor:,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."))
    return {"nome": nome, "valor": valor}


def comprar_veiculo(game: Game, tipo: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 18:
        raise ValueError("Só maiores de 18 anos podem comprar veículos.")
    if tipo not in VEICULOS_POR_ID:
        raise ValueError("Veículo inválido.")
    st = _estado_pat(game, p.id)
    if st["veiculo"] is not None:
        raise ValueError("Você já possui um veículo; venda o atual antes.")
    _, nome, preco_m, _ = VEICULOS_POR_ID[tipo]
    preco = round(preco_m * macro.min_wage(game), 2)
    if p.wealth < preco:
        raise ValueError("Patrimônio insuficiente para comprar este veículo.")
    p.wealth = round(p.wealth - preco, 2)
    st["veiculo"] = {"tipo": tipo, "valor": preco}
    registrar_transacao(game, p.id, "saida", preco, f"Compra: {nome}")
    game.add_event(p.id, "imovel", f"Comprou {nome} por R$ {preco:,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."))
    return {"nome": nome, "preco": preco}


def vender_veiculo(game: Game) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    st = _estado_pat(game, p.id)
    if st["veiculo"] is None:
        raise ValueError("Você não possui veículo.")
    v = st["veiculo"]
    st["veiculo"] = None
    nome = VEICULOS_POR_ID[v["tipo"]][1]
    valor = round(v["valor"] * 0.85, 2)
    p.wealth = round(p.wealth + valor, 2)
    registrar_transacao(game, p.id, "entrada", valor, f"Venda: {nome}")
    game.add_event(p.id, "imovel", f"Vendeu {nome} por R$ {valor:,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."))
    return {"nome": nome, "valor": valor}


def comprar_equipamento(game: Game, equip_id: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 12:
        raise ValueError("Aquisição de equipamentos pessoais disponível a partir dos 12 anos.")
    if equip_id not in EQUIPAMENTOS_POR_ID:
        raise ValueError("Equipamento inválido.")
    st = _estado_pat(game, p.id)
    if equip_id in st["equipamentos"]:
        raise ValueError("Você já possui este item.")
    _, nome, preco_m, _ = EQUIPAMENTOS_POR_ID[equip_id]
    preco = round(preco_m * macro.min_wage(game), 2)
    if p.wealth < preco:
        raise ValueError("Patrimônio insuficiente para comprar este equipamento.")
    p.wealth = round(p.wealth - preco, 2)
    st["equipamentos"].append(equip_id)
    registrar_transacao(game, p.id, "saida", preco, f"Equipamento: {nome}")
    game.add_event(p.id, "imovel", f"Adquiriu {nome} por R$ {preco:,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."))
    return {"id": equip_id, "nome": nome, "preco": preco}


def vender_equipamento(game: Game, equip_id: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if equip_id not in EQUIPAMENTOS_POR_ID:
        raise ValueError("Equipamento inválido.")
    st = _estado_pat(game, p.id)
    if equip_id not in st["equipamentos"]:
        raise ValueError("Você não possui este equipamento.")
    st["equipamentos"].remove(equip_id)
    _, nome, preco_m, _ = EQUIPAMENTOS_POR_ID[equip_id]
    valor = round(0.65 * preco_m * macro.min_wage(game), 2)
    p.wealth = round(p.wealth + valor, 2)
    registrar_transacao(game, p.id, "entrada", valor, f"Venda: {nome}")
    game.add_event(p.id, "imovel", f"Vendeu {nome} por R$ {valor:,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."))
    return {"id": equip_id, "nome": nome, "valor": valor}


def alternar_plano_saude(game: Game, ativar: bool | None = None) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 18:
        raise ValueError("Plano de saúde próprio disponível a partir dos 18 anos.")
    st = _estado_pat(game, p.id)
    st["plano_saude"] = (not st.get("plano_saude", False)) if ativar is None else bool(ativar)
    mens = round(PLANO_SAUDE_MENSAL_MINIMOS * macro.min_wage(game), 2)
    estado_txt = "contratou" if st["plano_saude"] else "cancelou"
    game.add_event(p.id, "decisao", f"{'Contratou' if st['plano_saude'] else 'Cancelou'} plano de saúde particular ({mens:,.2f}/mês).".replace(",", "X").replace(".", ",").replace("X", "."))
    return {"ativo": st["plano_saude"], "mensalidade": mens, "acao": estado_txt}


def investir(game: Game, tipo: str, valor: float) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 18:
        raise ValueError("Só maiores de 18 anos podem investir.")
    if tipo not in INVESTIMENTOS:
        raise ValueError("Modalidade de investimento inválida.")
    valor = round(float(valor), 2)
    if valor <= 0 or valor > p.wealth:
        raise ValueError("Valor inválido ou maior que o patrimônio disponível.")
    st = _estado_pat(game, p.id)
    p.wealth = round(p.wealth - valor, 2)
    st["inv"][tipo] = round(st["inv"].get(tipo, 0.0) + valor, 2)
    registrar_transacao(game, p.id, "saida", valor, f"Aplicação em {INVESTIMENTOS[tipo]}")
    game.add_event(p.id, "investimento", f"Aplicou R$ {valor:,.2f} em {INVESTIMENTOS[tipo]}.".replace(",", "X").replace(".", ",").replace("X", "."))
    return {"tipo": tipo, "saldo": st["inv"][tipo]}


def resgatar(game: Game, tipo: str, valor: float) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if tipo not in INVESTIMENTOS:
        raise ValueError("Modalidade de investimento inválida.")
    st = _estado_pat(game, p.id)
    atual = st["inv"].get(tipo, 0.0)
    valor = round(float(valor), 2)
    if valor <= 0 or valor > atual:
        raise ValueError("Valor inválido ou maior que o saldo investido.")
    st["inv"][tipo] = round(atual - valor, 2)
    p.wealth = round(p.wealth + valor, 2)
    registrar_transacao(game, p.id, "entrada", valor, f"Resgate de {INVESTIMENTOS[tipo]}")
    game.add_event(p.id, "investimento", f"Resgatou R$ {valor:,.2f} de {INVESTIMENTOS[tipo]}.".replace(",", "X").replace(".", ",").replace("X", "."))
    return {"tipo": tipo, "saldo": st["inv"][tipo]}


def limite_credito(game: Game, p) -> float:
    mw = macro.min_wage(game)
    return round(max(2 * mw, 12 * max(0.0, p.income) + 0.5 * max(0.0, p.wealth)), 2)


def pedir_emprestimo(game: Game, valor: float) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 18:
        raise ValueError("Só maiores de 18 anos podem contratar empréstimo.")
    valor = round(float(valor), 2)
    st = _estado_pat(game, p.id)
    lim = limite_credito(game, p)
    if valor <= 0 or st["emprestimo"] + valor > lim:
        raise ValueError(f"Valor fora do limite de crédito ({lim:,.2f}).")
    p.wealth = round(p.wealth + valor, 2)
    st["emprestimo"] = round(st["emprestimo"] + valor, 2)
    st["parcelas"] = PRAZO_EMPRESTIMO
    registrar_transacao(game, p.id, "entrada", valor, "Crédito de empréstimo bancário")
    game.add_event(p.id, "emprestimo", f"Contratou empréstimo bancário de R$ {valor:,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."))
    return {"divida": st["emprestimo"], "parcelas": st["parcelas"]}


def quitar_emprestimo(game: Game, valor: float) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    st = _estado_pat(game, p.id)
    if st["emprestimo"] <= 0:
        raise ValueError("Você não tem empréstimo ativo.")
    valor = round(min(float(valor), st["emprestimo"]), 2)
    if valor <= 0 or valor > p.wealth:
        raise ValueError("Saldo insuficiente para amortizar esse valor.")
    p.wealth = round(p.wealth - valor, 2)
    st["emprestimo"] = round(st["emprestimo"] - valor, 2)
    if st["emprestimo"] <= 0:
        st["emprestimo"] = 0.0
        st["parcelas"] = 0
    registrar_transacao(game, p.id, "saida", valor, "Amortização de empréstimo")
    game.add_event(p.id, "emprestimo", f"Quitou R$ {valor:,.2f} do empréstimo bancário.".replace(",", "X").replace(".", ",").replace("X", "."))
    return {"divida": st["emprestimo"]}


def apply_month(game: Game) -> None:
    if not game.patrimonio:
        return
    mw = macro.min_wage(game)
    infl = macro.monthly_rate(game)
    idx = cycle.current(game)
    now = game.year * 12 + game.month
    for cid, st in list(game.patrimonio.items()):
        c = game.characters.get(cid)
        if c is None or not c.alive:
            continue
        for im in st.get("imoveis", []):
            info = IMOVEIS_POR_ID[im["tipo"]]
            im["valor"] = round(im["valor"] * (1 + infl), 2)
            c.wealth -= info[3] * mw
            if im.get("alugado"):
                c.wealth += info[4] * mw
        if st.get("veiculo") is not None:
            v = st["veiculo"]
            v["valor"] = round(v["valor"] * 0.996, 2)
            c.wealth -= VEICULOS_POR_ID[v["tipo"]][3] * mw
        if st.get("plano_saude"):
            c.wealth -= PLANO_SAUDE_MENSAL_MINIMOS * mw
        if "kit_esportivo" in st.get("equipamentos", []):
            c.health = min(100.0, round(c.health + 0.30, 2))
        inv = st.get("inv", {})
        inv["poupanca"] = round(inv.get("poupanca", 0.0) * (1 + 0.002 + infl), 2)
        inv["tesouro"] = round(inv.get("tesouro", 0.0) * (1 + 0.0045 + infl), 2)
        r_acoes = random.Random(f"bolsa:{game.seed}:{now}:{cid}").gauss(0.005 + 0.012 * idx, 0.03)
        inv["acoes"] = round(max(0.0, inv.get("acoes", 0.0) * (1 + r_acoes + infl)), 2)
        if st.get("emprestimo", 0.0) > 0:
            st["emprestimo"] = round(st["emprestimo"] * (1 + JUROS_EMPRESTIMO_MENSAL + infl), 2)
            n = max(1, st.get("parcelas", 1))
            parcela = round(st["emprestimo"] / n, 2)
            c.wealth -= parcela
            st["emprestimo"] = round(max(0.0, st["emprestimo"] - parcela), 2)
            st["parcelas"] = max(0, n - 1) if st["emprestimo"] > 0 else 0
        c.wealth = round(c.wealth, 2)


def registrar_noticias_mes(game: Game) -> None:
    y, m = game.year, game.month
    if any(n["ano"] == y and n["mes"] == m for n in game.noticias):
        return
    if m == 10 and y >= 2026:
        if (y - 2026) % 4 == 0:
            game.noticias.append({"ano": y, "mes": m, "tipo": "real",
                                  "titulo": "Eleições gerais no Brasil",
                                  "texto": "Eleitores vão às urnas para Presidência, Governos, Senado e Câmaras."})
        elif (y - 2028) % 4 == 0:
            game.noticias.append({"ano": y, "mes": m, "tipo": "real",
                                  "titulo": "Eleições municipais no Brasil",
                                  "texto": "Municípios elegem prefeitos e vereadores em todo o país."})
    elif m == 8 and y >= 2030 and (y - 2030) % 10 == 0:
        game.noticias.append({"ano": y, "mes": m, "tipo": "real",
                              "titulo": "Censo Demográfico Nacional",
                              "texto": "Recenseamento atualiza perfil etário, escolaridade e urbanização do país."})
    if m == 1:
        idx = cycle.current(game)
        r = random.Random(f"noticia:{game.seed}:{y}")
        if idx <= -0.45:
            tit, txt = "Desaceleração econômica", "Queda de investimentos pressiona o mercado de trabalho no país."
        elif idx >= 0.45:
            tit, txt = "Forte expansão produtiva", "Novas contratações aquecem comércio, indústria e serviços."
        else:
            tit, txt = r.choice([
                ("Avanço tecnológico nos serviços", "Digitalização e inteligência artificial ampliam produtividade em médias e grandes empresas."),
                ("Debate sobre orçamento público", "Congresso discute metas fiscais, universidades e investimentos sociais."),
                ("Agenda cultural movimenta capitais", "Mostras literárias e bienais do livro registram público recorde."),
                ("Expansão do ensino técnico", "Institutos federais ampliam oferta de qualificação profissional nas regiões."),
                ("Transição energética em pauta", "Projetos solares e eólicos ganham espaço na matriz elétrica nacional."),
            ])
        game.noticias.append({"ano": y, "mes": m, "tipo": "simulada", "titulo": tit, "texto": txt})
    if len(game.noticias) > 120:
        del game.noticias[:-120]


def noticias_recentes(game: Game, limite: int = 12) -> list[dict]:
    return list(game.noticias[-limite:])[::-1]
