"""Psicologia, hábitos, valores, objetivos individuais e QI opcional (v0.20.0).

Implementa o §4.1 e §4.3 do Prompt-Mestre:
- Indicador opcional de QI (derivado das 8 capacidades cognitivas, nunca reduzindo inteligência a um único número).
- Valores, medos e preferências individuais coerentes com a personalidade.
- Hábitos mensais ativos (atividade física, leitura diária, meditação/sono, voluntariado) com efeitos reais.
- Objetivos individuais (metas de vida) verificados automaticamente com recompensas reais e registro na biografia.

Nunca consome `game.rng` (usa gerador local determinístico quando precisa sortear).
"""
from __future__ import annotations

import random

from . import engine
from .models import Character, Game

HABITOS = [
    ("exercicio", "Atividade física regular", 6, "Melhora a saúde mensal (+0,45) e desacelera o declínio na velhice."),
    ("leitura_diaria", "Leitura diária", 8, "Amplia a capacidade mensal de leitura (+120 págs) e reduz o esquecimento."),
    ("meditacao", "Higiene do sono e meditação", 10, "Reduz neuroticismo aos poucos e protege a saúde mental."),
    ("voluntariado", "Voluntariado comunitário", 14, "Fortalece amabilidade/extroversão e gera influência cívica."),
]
HABITOS_POR_ID = {h[0]: h for h in HABITOS}

VALORES_POOL = [
    "Conhecimento e verdade",
    "Família e vínculos",
    "Estabilidade e segurança",
    "Autonomia e liberdade",
    "Justiça social e cidadania",
    "Prosperidade e empreendedorismo",
    "Arte e expressão pessoal",
    "Saúde e equilíbrio",
]

MEDOS_POOL = [
    "Solidão e isolamento",
    "Instabilidade financeira",
    "Fracasso profissional",
    "Perda da saúde",
    "Conflitos familiares",
    "Estagnação intelectual",
]

# (id, rótulo, idade_min, descrição)
METAS_CATALOGO = [
    ("ensino_medio", "Concluir o ensino médio", 10, "Completar os 12 anos da educação básica."),
    ("universidade", "Ingressar no ensino superior", 15, "Entrar na faculdade via ENEM/SISU, PROUNI, FIES ou vestibular."),
    ("graduacao", "Concluir a graduação", 17, "Formar-se no ensino superior."),
    ("pos_graduacao", "Concluir pós-graduação", 21, "Finalizar especialização, mestrado ou doutorado."),
    ("leitor_10", "Ler 10 livros completos", 6, "Alcançar 10 obras concluídas na biblioteca."),
    ("leitor_25", "Ler 25 livros completos", 12, "Tornar-se leitor(a) assíduo(a) com 25 livros."),
    ("poliglota", "Dominar um segundo idioma", 12, "Alcançar nível avançado (≥70%) em qualquer idioma."),
    ("primeiro_emprego", "Conseguir o primeiro emprego", 15, "Ingressar no mercado de trabalho."),
    ("chefia", "Alcançar cargo Sênior/Chefia ou empresa própria", 20, "Chegar ao topo da carreira ou fundar negócio."),
    ("concurso", "Passar em concurso público", 18, "Conquistar estabilidade no serviço público."),
    ("reserva_50k", "Formar reserva de R$ 50.000", 18, "Acumular patrimônio líquido de R$ 50 mil."),
    ("casa_propria", "Comprar imóvel próprio", 18, "Adquirir o primeiro imóvel."),
    ("casar", "Construir casamento", 18, "Casar-se durante a vida adulta."),
    ("ter_filho", "Ter filhos", 18, "Formar descendência na família."),
    ("cargo_politico", "Eleger-se a cargo público", 18, "Conquistar mandato eletivo em eleição."),
]
METAS_POR_ID = {m[0]: m for m in METAS_CATALOGO}
MAX_METAS_ATIVAS = 3


def _jogador(game: Game) -> Character | None:
    p = game.characters.get(game.player_id) if game.player_id is not None else None
    return p if p is not None and p.alive else None


def qi_estimado(c: Character) -> int:
    """Indicador opcional de QI (média ~100, desvio ~15), derivado das capacidades cognitivas."""
    pesos = {
        "raciocinio_logico": 1.35,
        "abstracao": 1.25,
        "compreensao_verbal": 1.20,
        "resolucao_problemas": 1.20,
        "memoria": 1.00,
        "aprendizagem": 1.00,
        "atencao": 0.90,
        "criatividade": 0.90,
    }
    soma_p = sum(pesos.values())
    media = sum(c.cognition.get(k, 50) * w for k, w in pesos.items()) / soma_p
    qi = int(round(100 + (media - 50.0) * 1.15))
    return max(60, min(155, qi))


def _metas_iniciais(game: Game, c: Character) -> list[str]:
    age = c.age_at(game.year, game.month)
    metas = []
    if c.schooling_years < 12:
        metas.append("ensino_medio")
    elif not c.graduated and not c.in_college:
        metas.append("universidade")
    elif not c.graduated:
        metas.append("graduacao")
    if len(game.livros.get(c.id, [])) < 10:
        metas.append("leitor_10")
    if age >= 16 and c.jobs_held == 0 and not c.retired:
        metas.append("primeiro_emprego")
    elif age >= 20 and len(metas) < MAX_METAS_ATIVAS and c.wealth < 50000:
        metas.append("reserva_50k")
    if len(metas) < MAX_METAS_ATIVAS and age >= 18 and not engine.has_active_spouse(game, c):
        metas.append("casar")
    if len(metas) < MAX_METAS_ATIVAS:
        metas.append("poliglota")
    return metas[:MAX_METAS_ATIVAS]


def dados(game: Game, cid: int) -> dict:
    if cid in game.psicologia:
        st = game.psicologia[cid]
        st.setdefault("habitos", [])
        st.setdefault("metas_ativas", [])
        st.setdefault("metas_concluidas", [])
        st.setdefault("mostrar_qi", False)
        return st
    c = game.characters.get(cid)
    r = random.Random(f"psi:{game.seed}:{cid}")
    valores = []
    if c is not None:
        if c.personality.get("abertura", 50) >= 60:
            valores.append("Conhecimento e verdade")
        if c.personality.get("amabilidade", 50) >= 60:
            valores.append("Família e vínculos")
        if c.personality.get("conscienciosidade", 50) >= 60:
            valores.append("Estabilidade e segurança")
        if c.personality.get("extroversao", 50) >= 60:
            valores.append("Justiça social e cidadania")
    while len(valores) < 2:
        cand = r.choice(VALORES_POOL)
        if cand not in valores:
            valores.append(cand)
    medos = []
    if c is not None and c.personality.get("neuroticismo", 50) >= 60:
        medos.append("Instabilidade financeira")
    while len(medos) < 2:
        cand = r.choice(MEDOS_POOL)
        if cand not in medos:
            medos.append(cand)
    st = {
        "valores": valores[:3],
        "medos": medos[:2],
        "habitos": [],
        "metas_ativas": _metas_iniciais(game, c) if c is not None else [],
        "metas_concluidas": [],
        "mostrar_qi": False,
        "mes_check": 0,
    }
    game.psicologia[cid] = st
    return st


def alternar_habito(game: Game, habito_id: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if habito_id not in HABITOS_POR_ID:
        raise ValueError("Hábito inválido.")
    _, nome, idade_min, _ = HABITOS_POR_ID[habito_id]
    if p.age_at(game.year, game.month) < idade_min:
        raise ValueError(f"{nome} disponível a partir dos {idade_min} anos.")
    st = dados(game, p.id)
    habs = st["habitos"]
    if habito_id in habs:
        habs.remove(habito_id)
        ativo = False
        game.add_event(p.id, "decisao", f"Deixou o hábito: {nome}.")
    else:
        habs.append(habito_id)
        ativo = True
        game.add_event(p.id, "decisao", f"Adotou o hábito: {nome}.")
    return {"habito": habito_id, "nome": nome, "ativo": ativo, "habitos": list(habs)}


def definir_meta(game: Game, meta_id: str, adicionar: bool = True) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if meta_id not in METAS_POR_ID:
        raise ValueError("Objetivo inválido.")
    st = dados(game, p.id)
    if meta_id in st["metas_concluidas"]:
        raise ValueError("Você já concluiu este objetivo!")
    if adicionar:
        if meta_id in st["metas_ativas"]:
            raise ValueError("Este objetivo já está ativo.")
        if len(st["metas_ativas"]) >= MAX_METAS_ATIVAS:
            raise ValueError(f"Limite de {MAX_METAS_ATIVAS} objetivos ativos simultaneamente. Remova um antes.")
        if p.age_at(game.year, game.month) < METAS_POR_ID[meta_id][2]:
            raise ValueError(f"Objetivo disponível a partir dos {METAS_POR_ID[meta_id][2]} anos.")
        st["metas_ativas"].append(meta_id)
        game.add_event(p.id, "decisao", f"Definiu novo objetivo de vida: {METAS_POR_ID[meta_id][1]}.")
    else:
        if meta_id in st["metas_ativas"]:
            st["metas_ativas"].remove(meta_id)
    return {"metas_ativas": list(st["metas_ativas"]), "metas_concluidas": list(st["metas_concluidas"])}


def toggle_qi(game: Game, mostrar: bool | None = None) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    st = dados(game, p.id)
    st["mostrar_qi"] = (not st["mostrar_qi"]) if mostrar is None else bool(mostrar)
    return {"mostrar_qi": st["mostrar_qi"], "qi": qi_estimado(p)}


def _meta_cumprida(game: Game, c: Character, meta_id: str) -> tuple[bool, int]:
    """Retorna (cumprida, progresso_0_100)."""
    ed = game.educacao_br.get(c.id, {})
    ex = game.carreira_extra.get(c.id, {})
    pol = game.politica.get(c.id, {})
    pat = game.patrimonio.get(c.id, {})
    intel = game.intelecto.get(c.id, {})
    n_livros = len(game.livros.get(c.id, []))
    if meta_id == "ensino_medio":
        return c.schooling_years >= 12, min(100, int(round(c.schooling_years / 12 * 100)))
    if meta_id == "universidade":
        ok = c.in_college or c.graduated
        return ok, 100 if ok else min(90, int(round(c.schooling_years / 12 * 80)))
    if meta_id == "graduacao":
        return c.graduated, 100 if c.graduated else min(95, c.higher_years * 22)
    if meta_id == "pos_graduacao":
        ok = len(ed.get("pos_concluidas", [])) >= 1
        return ok, 100 if ok else (50 if ed.get("pos_atual") else 0)
    if meta_id == "leitor_10":
        return n_livros >= 10, min(100, n_livros * 10)
    if meta_id == "leitor_25":
        return n_livros >= 25, min(100, n_livros * 4)
    if meta_id == "poliglota":
        idiomas = intel.get("idiomas", {})
        mx = max(idiomas.values(), default=0)
        return mx >= 70, min(100, int(round(mx / 70 * 100)))
    if meta_id == "primeiro_emprego":
        ok = c.jobs_held >= 1 or c.occupation is not None
        return ok, 100 if ok else 0
    if meta_id == "chefia":
        ok = c.rank >= 2 or bool(ex.get("empresa_id"))
        return ok, 100 if ok else min(90, c.rank * 40)
    if meta_id == "concurso":
        ok = bool(ex.get("estavel"))
        return ok, 100 if ok else 0
    if meta_id == "reserva_50k":
        total = c.wealth + sum(pat.get("inv", {}).values())
        return total >= 50000.0, max(0, min(100, int(round(total / 50000.0 * 100))))
    if meta_id == "casa_propria":
        n_im = len(pat.get("imoveis", []))
        return n_im >= 1, 100 if n_im >= 1 else 0
    if meta_id == "casar":
        ok = engine.has_active_spouse(game, c)
        return ok, 100 if ok else (50 if c.partner_id else 0)
    if meta_id == "ter_filho":
        n_f = len(game.children_of(c.id))
        return n_f >= 1, 100 if n_f >= 1 else 0
    if meta_id == "cargo_politico":
        ok = bool(pol.get("cargo"))
        return ok, 100 if ok else min(80, int(round(pol.get("influencia", 0))))
    return False, 0


def verificar_metas(game: Game, c: Character) -> list[str]:
    if not c.alive:
        return []
    st = dados(game, c.id)
    concluidas_agora = []
    restantes = []
    for mid in st["metas_ativas"]:
        ok, _ = _meta_cumprida(game, c, mid)
        if ok and mid not in st["metas_concluidas"]:
            st["metas_concluidas"].append(mid)
            concluidas_agora.append(mid)
            c.health = min(100.0, round(c.health + 2.5, 2))
            c.personality["conscienciosidade"] = int(min(99, c.personality.get("conscienciosidade", 50) + 1))
            nome = METAS_POR_ID[mid][1]
            game.add_event(c.id, "decisao", f"Objetivo de vida alcançado: {nome}! (+saúde e realização)")
        else:
            restantes.append(mid)
    st["metas_ativas"] = restantes
    return concluidas_agora


def tem_habito(game: Game, cid: int, habito_id: str) -> bool:
    st = game.psicologia.get(cid)
    return bool(st and habito_id in st.get("habitos", []))


def apply_month(game: Game) -> None:
    """Aplica efeitos mensais de hábitos e plano de saúde sem consumir `game.rng`."""
    p = _jogador(game)
    if p is None:
        return
    st = dados(game, p.id)
    habs = st.get("habitos", [])
    now = game.year * 12 + game.month
    if "exercicio" in habs:
        p.health = min(100.0, round(p.health + 0.45, 2))
    if "meditacao" in habs:
        p.health = min(100.0, round(p.health + 0.25, 2))
        if now % 4 == 0 and p.personality.get("neuroticismo", 50) > 10:
            p.personality["neuroticismo"] = max(1, p.personality["neuroticismo"] - 1)
    if "voluntariado" in habs:
        if now % 6 == 0:
            p.personality["amabilidade"] = min(99, p.personality.get("amabilidade", 50) + 1)
            p.personality["extroversao"] = min(99, p.personality.get("extroversao", 50) + 1)
        if p.id in game.politica:
            game.politica[p.id]["influencia"] = min(100.0, round(game.politica[p.id].get("influencia", 0.0) + 0.5, 1))
    # Plano de saúde (em patrimônio) também protege mensalmente
    pat = game.patrimonio.get(p.id)
    if pat and pat.get("plano_saude"):
        p.health = min(100.0, round(p.health + 0.35, 2))
    verificar_metas(game, p)


def view(game: Game) -> dict:
    p = _jogador(game)
    if p is None:
        return {"disponivel": False, "habitos_catalogo": [], "metas_catalogo": []}
    st = dados(game, p.id)
    verificar_metas(game, p)
    idade = p.age_at(game.year, game.month)
    metas_ativas = []
    for mid in st["metas_ativas"]:
        if mid in METAS_POR_ID:
            ok, prog = _meta_cumprida(game, p, mid)
            metas_ativas.append({"id": mid, "rotulo": METAS_POR_ID[mid][1], "desc": METAS_POR_ID[mid][3], "progresso": prog, "concluida": ok})
    metas_disp = [
        {"id": m[0], "rotulo": m[1], "idade_min": m[2], "desc": m[3], "pode": idade >= m[2]}
        for m in METAS_CATALOGO
        if m[0] not in st["metas_ativas"] and m[0] not in st["metas_concluidas"]
    ]
    return {
        "disponivel": True,
        "mostrar_qi": bool(st.get("mostrar_qi", False)),
        "qi": qi_estimado(p),
        "valores": list(st.get("valores", [])),
        "medos": list(st.get("medos", [])),
        "habitos_ativos": list(st.get("habitos", [])),
        "habitos_catalogo": [
            {"id": h[0], "rotulo": h[1], "idade_min": h[2], "desc": h[3], "ativo": h[0] in st.get("habitos", []), "pode": idade >= h[2]}
            for h in HABITOS
        ],
        "metas_ativas": metas_ativas,
        "metas_concluidas": [{"id": mid, "rotulo": METAS_POR_ID[mid][1]} for mid in st["metas_concluidas"] if mid in METAS_POR_ID],
        "metas_disponiveis": metas_disp,
    }
