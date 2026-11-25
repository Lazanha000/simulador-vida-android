"""Educação brasileira (Fase 3 — v0.17.0): ENEM, SISU, PROUNI, FIES, Universidades reais e Pós-graduação."""
from __future__ import annotations

import random

from . import economy, engine, foco, intelecto, macro, mundo
from .models import Game

UNIVERSIDADES = [
    ("USP", "Universidade de São Paulo", "sp", "SP", "Pública Estadual", 720),
    ("UNICAMP", "Universidade Estadual de Campinas", "campinas", "SP", "Pública Estadual", 710),
    ("UFMG", "Universidade Federal de Minas Gerais", "bh", "MG", "Pública Federal", 700),
    ("UFRJ", "Universidade Federal do Rio de Janeiro", "rj", "RJ", "Pública Federal", 695),
    ("UnB", "Universidade de Brasília", "bsb", "DF", "Pública Federal", 685),
    ("UFRGS", "Universidade Federal do Rio Grande do Sul", "poa", "RS", "Pública Federal", 685),
    ("UFPR", "Universidade Federal do Paraná", "curitiba", "PR", "Pública Federal", 675),
    ("UFSC", "Universidade Federal de Santa Catarina", "florianopolis", "SC", "Pública Federal", 680),
    ("UFPE", "Universidade Federal de Pernambuco", "recife", "PE", "Pública Federal", 670),
    ("UFBA", "Universidade Federal da Bahia", "salvador", "BA", "Pública Federal", 665),
    ("UFC", "Universidade Federal do Ceará", "fortaleza", "CE", "Pública Federal", 670),
    ("UFG", "Universidade Federal de Goiás", "goiania", "GO", "Pública Federal", 655),
    ("UFRN", "Universidade Federal do Rio Grande do Norte", "natal", "RN", "Pública Federal", 650),
    ("UFAM", "Universidade Federal do Amazonas", "manaus", "AM", "Pública Federal", 640),
    ("IF", "Instituto Federal de Educação, Ciência e Tecnologia", "bh", "BR", "Pública Federal", 560),
    ("PRIVADA", "Instituição Privada de Ensino Superior", "sp", "BR", "Privada", 450),
]
UNIS_POR_SIGLA = {u[0]: u for u in UNIVERSIDADES}

CURSOS = [
    ("medicina", "Medicina", 6, 95, "medico", 5.5),
    ("direito", "Direito", 5, 25, "advogado", 1.8),
    ("engenharia", "Engenharia", 5, 30, "engenheiro", 2.0),
    ("computacao", "Sistemas de Informação / Computação", 4, 20, "analista_sistemas", 1.6),
    ("enfermagem", "Enfermagem", 4, -5, "enfermeiro", 1.4),
    ("contabilidade", "Ciências Contábeis", 4, -15, "contador", 1.2),
    ("licenciatura", "Licenciatura / Pedagogia", 4, -30, "professor", 1.0),
    ("psicologia", "Psicologia", 5, 10, "psicologo", 1.5),
    ("economia", "Ciências Econômicas", 4, 15, "economista", 1.5),
    ("design", "Design Gráfico e Digital (Tecnólogo)", 3, -10, "designer", 1.1),
]
CURSOS_POR_ID = {c[0]: c for c in CURSOS}
CURSO_TIPO = {
    "medicina": "Bacharelado",
    "direito": "Bacharelado",
    "engenharia": "Bacharelado",
    "computacao": "Bacharelado",
    "enfermagem": "Bacharelado",
    "contabilidade": "Bacharelado",
    "licenciatura": "Licenciatura",
    "psicologia": "Bacharelado",
    "economia": "Bacharelado",
    "design": "Tecnólogo",
}

CURSOS_TECNICOS = [
    ("tec_info", "Técnico em Informática", 18, "tecnico_medio", 0.30, "ciencias"),
    ("tec_adm", "Técnico em Administração", 18, "aux_administrativo", 0.25, "economia"),
    ("tec_enf", "Técnico em Enfermagem", 18, "tecnico_medio", 0.30, "ciencias"),
    ("tec_eletro", "Técnico em Eletrotécnica", 18, "tecnico_medio", 0.30, "ciencias"),
    ("tec_log", "Técnico em Logística", 18, "tecnico_medio", 0.25, "economia"),
]
CURSOS_TECNICOS_POR_ID = {t[0]: t for t in CURSOS_TECNICOS}

POS_NIVEIS = {
    "especializacao": ("Especialização", 12, 0.0, 1.05),
    "mestrado": ("Mestrado", 24, 1.2, 1.12),
    "doutorado": ("Doutorado", 48, 1.8, 1.22),
}


def _jogador(game: Game):
    p = game.characters.get(game.player_id) if game.player_id is not None else None
    return p if p is not None and p.alive else None


def dados(game: Game, cid: int) -> dict:
    st = game.educacao_br.setdefault(cid, {
        "enem_ano": None, "enem": None, "uni": None, "curso": None,
        "modalidade": None, "fies_divida": 0.0, "pos_atual": None, "pos_concluidas": [], "ic_meses": 0,
        "tecnico_atual": None, "tecnicos_concluidos": [],
    })
    st.setdefault("tecnico_atual", None)
    st.setdefault("tecnicos_concluidos", [])
    return st


def ocupacao_preferida(game: Game, cid: int) -> str | None:
    """Ocupação compatível com a graduação ou formação técnica registrada em educacao_br."""
    st = game.educacao_br.get(cid)
    c = game.characters.get(cid)
    if not st or c is None:
        return None
    if c.graduated and st.get("curso") in CURSOS_POR_ID:
        return CURSOS_POR_ID[st["curso"]][4]
    for tid in reversed(st.get("tecnicos_concluidos", [])):
        if tid in CURSOS_TECNICOS_POR_ID:
            return CURSOS_TECNICOS_POR_ID[tid][3]
    return None


def bonus_salarial_pos(game: Game, cid: int) -> float:
    st = game.educacao_br.get(cid)
    if not st:
        return 1.0
    mult = 1.0
    for n in st.get("pos_concluidas", []):
        mult = max(mult, POS_NIVEIS[n][3])
    if st.get("tecnicos_concluidos") and mult == 1.0:
        mult = 1.04
    return mult


def fazer_enem(game: Game) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 16 or p.schooling_years < 11:
        raise ValueError("O ENEM exige ao menos estar no último ano do ensino médio (≥16 anos).")
    st = dados(game, p.id)
    if st["enem_ano"] == game.year:
        raise ValueError("Você já fez o ENEM neste ano.")
    r = random.Random(f"enem:{game.seed}:{game.year}:{p.id}")
    area_foco = foco.area_atual(game, p.id) if foco.atual(game, p.id) == "estudar" else "geral"
    consc = p.personality.get("conscienciosidade", 50)

    bonus_prep = intelecto.bonus_enem_atual(game, p.id)

    def nota(cog_key: str, area_id: str) -> int:
        base = (
            400 + 3.2 * p.cognition.get(cog_key, 50) + 1.1 * consc
            + (45 if area_foco == area_id else 15 if area_foco != "geral" else 0)
            + 0.7 * bonus_prep
        )
        return int(min(980, max(350, round(base + r.gauss(0, 28)))))

    notas = {
        "linguagens": nota("compreensao_verbal", "linguagens"),
        "humanas": nota("memoria", "humanas"),
        "natureza": nota("aprendizagem", "natureza"),
        "matematica": nota("raciocinio_logico", "matematica"),
        "redacao": min(1000, max(300, int(round((380 + 3.6 * p.cognition.get("compreensao_verbal", 50)
                                                + 1.3 * consc + (50 if area_foco == "linguagens" else 0)
                                                + 0.8 * bonus_prep
                                                + r.gauss(0, 35)) / 20) * 20))),
    }
    media = round(sum(notas.values()) / 5, 1)
    notas["media"] = media
    st["enem_ano"] = game.year
    st["enem"] = notas
    game.add_event(p.id, "universidade", f"Fez o ENEM {game.year} e obteve média {media:.1f} (Redação {notas['redacao']}).")
    return notas


def _renda_per_capita_minimos(game: Game, p) -> float:
    h = economy.household_of(game, p)
    mw = macro.min_wage(game)
    if not h or mw <= 0:
        return 0.0
    return (h["income"] / max(1, len(h["adults"]) + len(h["kids"]))) / mw


def ingressar(game: Game, uni_sigla: str, curso_id: str, modalidade: str = "sisu", mudar_cidade: bool = False) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.schooling_years < 12:
        raise ValueError("Conclua o ensino médio antes de ingressar no ensino superior.")
    if p.in_college or p.graduated:
        raise ValueError("Você já cursa ou concluiu uma graduação.")
    if uni_sigla not in UNIS_POR_SIGLA or curso_id not in CURSOS_POR_ID:
        raise ValueError("Instituição ou curso inválido.")
    uni, curso = UNIS_POR_SIGLA[uni_sigla], CURSOS_POR_ID[curso_id]
    cid_atual, nome_atual, uf_atual, _ = mundo.cidade_of(game, p.id)
    precisa_mudar = uni[3] != "BR" and cid_atual != uni[2]
    if precisa_mudar and not mudar_cidade:
        cid_uni_nome = mundo.CIDADES_POR_ID[uni[2]][1]
        raise ValueError(
            f"A {uni[0]} fica em {cid_uni_nome}/{uni[3]} e você mora em {nome_atual}/{uf_atual}. "
            f"Mude-se para lá ou confirme a mudança ao ingressar."
        )
    if precisa_mudar and p.wealth < mundo.custo_mudanca(game, p):
        raise ValueError("Patrimônio insuficiente para custear a mudança para a cidade da universidade.")
    st = dados(game, p.id)
    corte = uni[5] + curso[3]
    is_publica = uni[4].startswith("Pública")
    mod = modalidade
    if mod == "sisu":
        if not is_publica:
            raise ValueError("O SISU seleciona apenas para instituições públicas.")
        if not st["enem"] or st["enem"]["redacao"] == 0:
            raise ValueError("É preciso ter nota do ENEM para disputar o SISU.")
        if st["enem"]["media"] < corte:
            raise ValueError(f"Nota {st['enem']['media']:.1f} abaixo do corte ({corte}) para {curso[1]} na {uni[0]}.")
    elif mod == "prouni":
        if is_publica:
            raise ValueError("O PROUNI oferece bolsas apenas em instituições privadas.")
        if not st["enem"] or st["enem"]["media"] < 450:
            raise ValueError("O PROUNI exige média mínima de 450 pontos no ENEM.")
        rpc = _renda_per_capita_minimos(game, p)
        if rpc <= 1.5:
            mod = "prouni_100"
        elif rpc <= 3.0:
            mod = "prouni_50"
        else:
            raise ValueError("Renda familiar per capita acima do limite de 3 salários mínimos do PROUNI.")
    elif mod == "fies":
        if is_publica:
            raise ValueError("O FIES financia apenas instituições privadas.")
        if not st["enem"] or st["enem"]["media"] < 450:
            raise ValueError("O FIES exige nota mínima de 450 pontos no ENEM.")
    elif mod == "vestibular":
        r = random.Random(f"vest:{game.seed}:{game.year * 12 + game.month}:{p.id}:{uni_sigla}:{curso_id}")
        if 400 + 4.0 * engine.aptitude(p) + r.gauss(0, 35) < corte:
            raise ValueError(f"Não alcançou a nota necessária no vestibular da {uni[0]}.")
    else:
        raise ValueError("Modalidade inválida (use sisu, prouni, fies ou vestibular).")
    mudou = None
    if precisa_mudar:
        mudou = mundo.mudar_cidade(game, uni[2])["cidade"]
    p.in_college, p.in_school = True, False
    st["uni"], st["curso"], st["modalidade"] = uni[0], curso[0], mod
    game.add_event(p.id, "universidade", f"Ingressou em {curso[1]} na {uni[0]} ({uni[1]}) via {mod.upper().replace('_', ' ')}.")
    return {"universidade": uni[0], "curso": curso[1], "modalidade": mod, "mudou_para": mudou}


def iniciacao_cientifica(game: Game) -> dict:
    p = _jogador(game)
    if p is None or not p.in_college:
        raise ValueError("É preciso estar cursando o ensino superior.")
    st = dados(game, p.id)
    if st.get("ic_meses", 0) > 0:
        raise ValueError("Você já participa de iniciação científica neste período.")
    st["ic_meses"] = 12
    for k in ("aprendizagem", "resolucao_problemas"):
        engine.treinar_cognicao(p, k, 1, elevar_potencial=True)
    game.add_event(p.id, "universidade", "Iniciou bolsa de Iniciação Científica na graduação (12 meses).")
    return {"meses": 12, "bolsa_minimos": 0.45}


def iniciar_pos(game: Game, nivel: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if not p.graduated:
        raise ValueError("A pós-graduação exige ensino superior completo.")
    if nivel not in POS_NIVEIS:
        raise ValueError("Nível de pós-graduação inválido.")
    st = dados(game, p.id)
    if st.get("pos_atual") is not None:
        raise ValueError("Você já está cursando uma pós-graduação.")
    if nivel in st.get("pos_concluidas", []):
        raise ValueError("Você já concluiu essa etapa acadêmica.")
    nome, meses, bolsa_m, _ = POS_NIVEIS[nivel]
    tem_bolsa = bolsa_m > 0 and engine.aptitude(p) >= 60
    st["pos_atual"] = {"nivel": nivel, "meses": meses, "bolsa": bolsa_m if tem_bolsa else 0.0}
    game.add_event(p.id, "universidade", f"Iniciou {nome} ({meses // 12} ano(s))" + (" com bolsa acadêmica." if tem_bolsa else "."))
    return {"nivel": nome, "meses": meses, "bolsa_minimos": bolsa_m if tem_bolsa else 0.0}


def iniciar_tecnico(game: Game, curso_tec_id: str, publica: bool = True) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 15 or p.schooling_years < 9:
        raise ValueError("Cursos técnicos exigem pelo menos 15 anos e ensino fundamental completo.")
    if curso_tec_id not in CURSOS_TECNICOS_POR_ID:
        raise ValueError("Curso técnico inválido.")
    st = dados(game, p.id)
    if st.get("tecnico_atual") is not None:
        raise ValueError("Você já está cursando um curso técnico.")
    if curso_tec_id in st.get("tecnicos_concluidos", []):
        raise ValueError("Você já concluiu este curso técnico.")
    tid, nome, meses, _, mens_m, _ = CURSOS_TECNICOS_POR_ID[curso_tec_id]
    if publica and engine.aptitude(p) < 40 and p.schooling_years < 11:
        raise ValueError("Aptidão insuficiente para vaga gratuita no Instituto Federal; tente rede privada ou estude mais.")
    mensalidade = 0.0 if publica else round(mens_m * macro.min_wage(game), 2)
    st["tecnico_atual"] = {"id": tid, "meses": meses, "publica": bool(publica), "mensalidade_m": 0.0 if publica else mens_m}
    inst = "Instituto Federal (gratuito)" if publica else "Rede Técnica Privada"
    game.add_event(p.id, "escola", f"Matriculou-se no {nome} ({inst}, {meses} meses).")
    return {"id": tid, "nome": nome, "meses": meses, "publica": bool(publica), "mensalidade": mensalidade}


def apply_month(game: Game) -> None:
    if not game.educacao_br:
        return
    mw = macro.min_wage(game)
    for cid, st in list(game.educacao_br.items()):
        c = game.characters.get(cid)
        if c is None or not c.alive:
            continue
        if c.in_college and st.get("curso") in CURSOS_POR_ID:
            mens = CURSOS_POR_ID[st["curso"]][5] * mw
            mod = st.get("modalidade")
            if mod == "prouni_50":
                c.wealth -= 0.5 * mens
            elif mod == "fies":
                st["fies_divida"] = round(st.get("fies_divida", 0.0) + mens, 2)
            elif mod == "vestibular" and st.get("uni") == "PRIVADA":
                c.wealth -= mens
        elif not c.in_college and st.get("fies_divida", 0.0) > 0 and c.income > 0:
            parc = round(min(st["fies_divida"], 0.08 * c.income), 2)
            c.wealth -= parc
            st["fies_divida"] = round(st["fies_divida"] - parc, 2)
        if st.get("ic_meses", 0) > 0 and c.in_college:
            c.wealth += 0.45 * mw
            st["ic_meses"] -= 1
        tec = st.get("tecnico_atual")
        if tec is not None:
            mens_t = float(tec.get("mensalidade_m", 0.0)) * mw
            if mens_t > 0:
                c.wealth -= mens_t
            tec["meses"] -= 1
            if tec["meses"] <= 0:
                tid = tec["id"]
                st["tecnico_atual"] = None
                if tid not in st["tecnicos_concluidos"]:
                    st["tecnicos_concluidos"].append(tid)
                t_info = CURSOS_TECNICOS_POR_ID.get(tid)
                if t_info:
                    for k in ("resolucao_problemas", "aprendizagem"):
                        engine.treinar_cognicao(c, k, 1, elevar_potencial=True)
                    intelecto.adicionar_conhecimento(game, c.id, t_info[5], 3)
                    game.add_event(c.id, "escola", f"Concluiu o curso técnico: {t_info[1]}!")
        pos = st.get("pos_atual")
        if pos is not None:
            if pos.get("bolsa", 0.0) > 0:
                c.wealth += pos["bolsa"] * mw
            pos["meses"] -= 1
            if pos["meses"] <= 0:
                niv = pos["nivel"]
                st["pos_atual"] = None
                if niv not in st["pos_concluidas"]:
                    st["pos_concluidas"].append(niv)
                for k in ("abstracao", "resolucao_problemas"):
                    engine.treinar_cognicao(c, k, 1, elevar_potencial=True)
                game.add_event(c.id, "universidade", f"Concluiu {POS_NIVEIS[niv][0]}!")
        c.wealth = round(c.wealth, 2)
