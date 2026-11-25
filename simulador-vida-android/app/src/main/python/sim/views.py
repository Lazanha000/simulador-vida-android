"""Visões (v0.14.0): transformam o estado do jogo em dados JSON para a interface web.

Só leitura e apresentação — nenhuma regra de simulação mora aqui (o avanço do tempo chama `engine.advance_months`).
Convenções de caminho: ícones e miniaturas são caminhos relativos a /arte/ (ex.: "eventos/evento_morte.svg");
avatares são rotas /avatar/... geradas por `sim.avatar_art`.
"""
from __future__ import annotations

from . import avatar_art, carreiras, livros, conhecidos, convivio, decisions, educacao_br, encontros, economy, engine, foco, indicators, intelecto, macro, mundo, psicologia, vinculos, work
from .models import MESES, Character, Game

ROTULOS = {
    "abertura": "Abertura", "conscienciosidade": "Conscienciosidade", "extroversao": "Extroversão",
    "amabilidade": "Amabilidade", "neuroticismo": "Neuroticismo", "memoria": "Memória", "atencao": "Atenção",
    "raciocinio_logico": "Raciocínio lógico", "abstracao": "Abstração", "criatividade": "Criatividade",
    "compreensao_verbal": "Compreensão verbal", "resolucao_problemas": "Resolução de problemas",
    "aprendizagem": "Aprendizagem",
}

CATEGORIAS = {
    "aniversario": "Aniversários", "etapa_de_vida": "Fases da vida", "nascimento": "Nascimento",
    "criacao": "Entrada na simulação", "nascimento_filho": "Filhos", "gravidez": "Gestações", "gemeos": "Gêmeos",
    "casamento": "Casamentos", "divorcio": "Divórcios", "divorcio_pais": "Separação dos pais", "guarda": "Guarda",
    "namoro": "Namoros", "namoro_fim": "Términos de namoro", "amizade": "Amizades", "amizade_fim": "Amizades desfeitas",
    "escola": "Estudos", "decisao": "Decisões", "trabalho": "Trabalho", "heranca": "Heranças", "morte": "Falecimentos",
    "falecimento_familiar": "Perdas na família", "falecimento_amigo": "Perdas de amigos",
    "universidade": "Universidade e ENEM", "concurso": "Concursos públicos",
    "empresa": "Empresa própria", "politica": "Política",
    "mudanca": "Mudança de cidade", "imovel": "Imóveis e veículos",
    "investimento": "Investimentos", "emprestimo": "Empréstimos",
}

# Categorias do diário do jogador que não valem como notícia do mundo (só aparecem para o próprio jogador).
_CAT_PRIVADAS = ("amizade", "escola", "trabalho", "heranca", "aniversario", "etapa_de_vida")


# --- formatação ---------------------------------------------------------------------------------
def brl(x: float) -> str:
    return economy.fmt_brl(x)


def mes_ano(ano: int, mes: int) -> str:
    return f"{MESES[mes - 1][:3]}/{ano}"


def abs_str(n: int) -> str:
    """Mês absoluto (ano*12+mês, mês 1–12) como 'mmm/aaaa'."""
    ano, mes = divmod(n - 1, 12)
    return mes_ano(ano, mes + 1)


def anos_meses(meses: int) -> str:
    """Duração em texto, com singular/plural corretos ("1 ano e 1 mês", "2 anos", "0 meses")."""
    a, m = divmod(max(0, meses), 12)
    ta = f"{a} ano" + ("" if a == 1 else "s")
    tm = f"{m} " + ("mês" if m == 1 else "meses")
    if a and m:
        return f"{ta} e {tm}"
    return ta if a else tm


def g(c: Character, fem: str, masc: str) -> str:
    return fem if c.sex == "F" else masc


# --- pessoas -------------------------------------------------------------------------------------
def ref_date(game: Game, c: Character) -> tuple[int, int]:
    return (game.year, game.month) if c.alive else (c.death_year, c.death_month)


def age_of(game: Game, c: Character) -> int:
    return c.age_at(*ref_date(game, c))


def civil(game: Game, c: Character) -> str:
    if engine.has_active_spouse(game, c):
        return g(c, "casada", "casado")
    if c.spouse_id in game.characters:   # vínculo histórico com cônjuge falecido
        return g(c, "viúva", "viúvo")
    if c.ex_spouse_id in game.characters:
        return g(c, "divorciada", "divorciado")
    return g(c, "solteira", "solteiro")


def ocupacao_curta(game: Game, c: Character, age: int | None = None) -> str:
    a = age_of(game, c) if age is None else age
    if not c.alive:
        return g(c, "Falecida", "Falecido")
    if a < work.IDADE_TRABALHO_MIN and not work.is_employed(c):
        return "Estudante" if work.is_student(c) else engine.life_stage(a).capitalize()
    if work.is_student(c):
        return "Estudante"
    if c.retired:
        return g(c, "Aposentada", "Aposentado")
    if work.is_employed(c):
        return work.occupation_name(c.occupation, c.sex)
    if work.is_seeking(c):
        return "Procurando trabalho"
    return "Sem atividade"


def resumo(game: Game, c: Character) -> str:
    a = age_of(game, c)
    if not c.alive:
        return f"† aos {a} anos ({c.death_year})"
    return f"{a} anos · {ocupacao_curta(game, c, a)}"


def pessoa(game: Game, c: Character, rel: str | None = None, sub: str | None = None) -> dict:
    a = age_of(game, c)
    return {"id": c.id, "nome": c.full_name, "primeiro": c.first_name, "idade": a, "vivo": c.alive, "sexo": c.sex,
            "avatar": avatar_art.url(game, c, a), "rel": rel, "sub": resumo(game, c) if sub is None else sub,
            "jogador": c.id == game.player_id}


def player_of(game: Game) -> Character | None:
    return game.characters.get(game.player_id) if game.player_id is not None else None


# --- diário (eventos da biografia) ------------------------------------------------------------------
def classificar(cat: str, texto: str) -> tuple[str, str]:
    """(miniatura relativa a /arte/, tom: 'bom' | 'ruim' | 'neutro') de um evento da biografia."""
    ev, ic = (lambda n: f"eventos/evento_{n}.svg"), (lambda n: f"icones/icone_{n}.svg")
    if cat in ("nascimento", "nascimento_filho"):
        return ev("nascimento"), "bom"
    if cat in ("criacao", "aniversario", "etapa_de_vida"):
        return ic("biografia"), "neutro"
    if cat in ("morte", "falecimento_familiar", "falecimento_amigo"):
        return ev("morte"), "ruim"
    if cat == "decisao":
        return ic("biografia"), "neutro"
    if cat == "gravidez":
        return ev("gravidez"), ("ruim" if "interrompida" in texto else "bom")
    if cat == "gemeos":
        return ev("gemeos"), "bom"
    if cat == "casamento":
        return ev("casamento"), "bom"
    if cat in ("divorcio", "divorcio_pais"):
        return ev("divorcio"), "ruim"
    if cat == "guarda":
        return ev("guarda"), "neutro"
    if cat == "namoro":
        return ev("namoro"), "bom"
    if cat == "namoro_fim":
        return ev("amizade_fim"), "ruim"
    if cat == "amizade":
        return ev("amizade"), "bom"
    if cat == "amizade_fim":
        return ev("amizade_fim"), "ruim"
    if cat == "heranca":
        return ev("heranca"), "bom"
    if cat == "escola":
        if texto.startswith(("Concluiu", "Formou")):
            return ev("formatura"), "bom"
        if texto.startswith(("Reprovou", "Abandonou", "Encerrou", "Não foi")):
            return ev("escola_inicio"), "ruim"
        return ev("escola_inicio"), "neutro"
    if cat == "trabalho":
        if texto.startswith("Aposentou"):
            return ev("aposentadoria"), "neutro"
        if texto.startswith(("Perdeu", "Deixou")):
            return ev("demissao"), "ruim"
        if "seguro-desemprego" in texto or "licença-maternidade" in texto:
            return ic("seguro"), "neutro"
        if texto.startswith(("Foi promovido", "Mudou de ocupação")):
            return ev("promocao"), "bom"
        if texto.startswith("Passou a procurar"):
            return ev("emprego"), "neutro"
        return ev("emprego"), "bom"
    if cat == "universidade":
        if texto.startswith(("Concluiu", "Ingressou", "Iniciou")):
            return ev("formatura"), "bom"
        return ev("escola_inicio"), "neutro"
    if cat == "concurso":
        return (ev("emprego"), "bom") if texto.startswith("Aprovado") else (ev("escola_inicio"), "neutro")
    if cat == "empresa":
        return (ev("emprego"), "bom") if texto.startswith(("Fundou", "Expandiu")) else (ev("demissao"), "neutro")
    if cat == "politica":
        return (ev("promocao"), "bom") if texto.startswith(("Eleito", "Filiou", "Realizou")) else (ic("panorama"), "neutro")
    if cat == "mudanca":
        return ic("panorama"), "neutro"
    if cat in ("imovel", "investimento"):
        return ic("bens"), "bom"
    if cat == "emprestimo":
        return (ic("bens"), "neutro") if texto.startswith("Quitou") else (ic("bens"), "ruim")
    return ic("biografia"), "neutro"


def evento_item(game: Game, e, ref: Character | None = None, com_quem: bool = False) -> dict:
    icone, tom = classificar(e.category, e.text)
    quem = game.characters.get(e.char_id)
    base = ref if ref is not None else quem
    item = {"seq": e.seq, "ano": e.year, "mes": e.month, "data": mes_ano(e.year, e.month), "cat": e.category,
            "texto": e.text, "icone": icone, "tom": tom,
            "idade": base.age_at(e.year, e.month) if base is not None else None}
    if com_quem and quem is not None:
        item["quem"] = quem.first_name
    return item


def feed(game: Game, c: Character, limite: int = 120, antes: int | None = None) -> dict:
    """Diário do personagem: os `limite` eventos mais recentes anteriores a `antes` (seq), em ordem cronológica."""
    evs = game.events_for(c.id)
    if antes is not None:
        evs = [e for e in evs if e.seq < antes]
    total = len(evs)
    evs = evs[-limite:]
    return {"itens": [evento_item(game, e, c) for e in evs], "mais": total > len(evs), "restantes": total - len(evs)}


# --- estado ---------------------------------------------------------------------------------------
BARRAS = (("saude", "Saúde", "saude"), ("cognicao", "Mente", "cognicao"), ("social", "Social", "social"),
          ("patrimonio", "Patrimônio", "bens"), ("felicidade", "Bem-estar", "bemestar"))


def dinheiro(game: Game, c: Character) -> dict:
    return {"patrimonio": brl(c.wealth), "renda": brl(c.income), "negativo": c.wealth < 0,
            "linha": brl(c.wealth), "sub": (f"{brl(c.income)}/mês" if c.income > 0 else "sem renda")}


def estado(game: Game | None, meta: dict | None = None) -> dict:
    """Estado geral para a tela principal. `meta`: arquivo, sujo, autosave (vindos da sessão do servidor)."""
    meta = meta or {}
    if game is None:
        return {"tem_jogo": False}
    p = player_of(game)
    out = {
        "tem_jogo": True,
        "partida": {"nome": game.name, "semente": game.seed, "data": game.date_str(), "ano": game.year,
                    "mes": game.month, "arquivo": meta.get("arquivo"), "sujo": bool(meta.get("sujo")),
                    "autosave": bool(meta.get("autosave", True))},
        "n_personagens": len(game.characters),
        "populacao": sum(1 for c in game.characters.values() if c.alive),
        "jogador": None, "luto": False, "pode_avancar": bool(game.characters) and not game.decisions["pending"],
        "decisao": decisions.view(game),
        "avanco_pendente": int((game.decisions.get("turno") or {}).get("restantes", 0)) if not game.decisions["pending"] else 0,
        "foco": foco.view(game), "amigos": convivio.amigos(game), "encontros": encontros.view(game), "locais": conhecidos.locais(game), "livros": livros.view(game), "intelecto": intelecto.view(game),
        "psicologia": psicologia.view(game), "vinculos": vinculos.pessoas_proximas(game),
        "acoes_vinculo": [{"id": k, "rotulo": v} for k, v in vinculos.ACOES_VINCULO.items()],
    }
    if p is not None:
        h = economy.household_of(game, p) if p.alive else None
        b = indicators.bars(game, p, h)
        pe = pessoa(game, p)
        pe["sub"] = f"{ocupacao_curta(game, p)} · {civil(game, p)}" if p.alive else f"{civil(game, p)} · faleceu em {mes_ano(p.death_year, p.death_month)}"
        pe["grande"] = pessoa(game, p)["avatar"]
        out["jogador"] = pe
        out["luto"] = not p.alive
        out["dinheiro"] = dinheiro(game, p)
        out["barras"] = [{"id": i, "rotulo": r, "valor": round(b[i]), "painel": pn} for i, r, pn in BARRAS]
        out["gestante"] = p.alive and p.pregnant_until is not None
        cid_atual = mundo.cidade_of(game, p.id)
        ed = educacao_br.dados(game, p.id)
        ex = game.carreira_extra.get(p.id, {})
        pol = carreiras.politica_of(game, p.id)
        pat = game.patrimonio.get(p.id, {"imoveis": [], "veiculo": None, "inv": {"poupanca": 0.0, "tesouro": 0.0, "acoes": 0.0}, "emprestimo": 0.0, "parcelas": 0, "equipamentos": [], "plano_saude": False})
        mw = macro.min_wage(game)
        emp_id = ex.get("empresa_id")
        emp_obj = game.firms.get(emp_id) if emp_id is not None else None
        fl = ex.get("freelas_mes")
        freelas_feitos = fl[1] if isinstance(fl, list) and len(fl) == 2 and fl[0] == (game.year * 12 + game.month) else 0
        xm = ex.get("extras_mes")
        extras_feitos = xm[1] if isinstance(xm, list) and len(xm) == 2 and xm[0] == (game.year * 12 + game.month) else 0
        prox_porte = carreiras.PORTE_PROXIMO.get(emp_obj.size) if (emp_obj and emp_obj.is_open) else None
        out["educacao_br"] = {
            "enem_ano": ed.get("enem_ano"),
            "enem": ed.get("enem"),
            "uni": ed.get("uni"),
            "curso": ed.get("curso"),
            "modalidade": ed.get("modalidade"),
            "fies_divida": ed.get("fies_divida", 0.0),
            "ic_meses": ed.get("ic_meses", 0),
            "pos_atual": ed.get("pos_atual"),
            "pos_concluidas": list(ed.get("pos_concluidas", [])),
            "tecnico_atual": ed.get("tecnico_atual"),
            "tecnicos_concluidos": list(ed.get("tecnicos_concluidos", [])),
            "custo_mudanca": mundo.custo_mudanca(game, p),
            "universidades": [{"sigla": u[0], "nome": u[1], "cidade_id": u[2], "cidade_nome": mundo.CIDADES_POR_ID.get(u[2], (u[2], u[2]))[1], "uf": u[3], "tipo": u[4], "corte": u[5]} for u in educacao_br.UNIVERSIDADES],
            "cursos": [{"id": cr[0], "nome": cr[1], "anos": cr[2], "ajuste": cr[3], "tipo": educacao_br.CURSO_TIPO.get(cr[0], "Bacharelado"), "area": educacao_br.CURSO_AREA.get(cr[0], "Geral"), "mensalidade": round(cr[5] * mw, 2)} for cr in educacao_br.CURSOS],
            "cursos_tecnicos": [{"id": t[0], "nome": t[1], "meses": t[2], "mensalidade": round(t[4] * mw, 2)} for t in educacao_br.CURSOS_TECNICOS],
            "pos_opcoes": [{"id": k, "nome": v[0], "meses": v[1], "bolsa": round(v[2] * mw, 2), "bonus": int(round((v[3] - 1) * 100))} for k, v in educacao_br.POS_NIVEIS.items()],
        }
        out["carreiras"] = {
            "estavel": bool(ex.get("estavel")),
            "cargo_publico": ex.get("cargo_publico"),
            "meio_periodo": ex.get("meio_periodo"),
            "freelas_restantes": max(0, 2 - freelas_feitos),
            "extras_restantes": max(0, 2 - extras_feitos),
            "empresa": {
                "id": emp_obj.id, "nome": emp_obj.name, "setor": emp_obj.sector, "porte": emp_obj.size,
                "pode_expandir": prox_porte is not None,
                "proximo_porte": prox_porte[0] if prox_porte else None,
                "custo_expansao": round(prox_porte[1] * mw, 2) if prox_porte else None,
            } if emp_obj and emp_obj.is_open else None,
            "concursos": [{"id": c_id, "cargo": cargo, "nivel": work.NIVEIS[niv], "nivel_id": niv, "corte": dif, "salario": round(sal_m * mw, 2)} for c_id, cargo, _, niv, dif, sal_m in carreiras.CONCURSOS],
            "politica": {
                "partido": pol.get("partido"),
                "partido_nome": carreiras.PARTIDOS_POR_ID.get(pol.get("partido")) if pol.get("partido") else None,
                "influencia": pol.get("influencia", 0.0),
                "cargo": pol.get("cargo"),
                "cargo_nome": carreiras.CARGOS_POR_ID[pol["cargo"]][1] if pol.get("cargo") in carreiras.CARGOS_POR_ID else None,
                "mandato_meses": pol.get("mandato_meses", 0),
                "ultimo_projeto": pol.get("ultimo_projeto"),
            },
            "partidos": [{"id": k, "nome": v} for k, v in carreiras.PARTIDOS],
            "cargos": [{"id": k, "nome": nm, "idade_min": idm, "corte": dif, "salario": round(sm * mw, 2)} for k, nm, idm, dif, sm in carreiras.CARGOS_POLITICOS],
            "movimentos": [{"id": k, "nome": v} for k, v in carreiras.MOVIMENTOS],
            "pautas": [{"id": p0[0], "titulo": p0[1]} for p0 in carreiras.PAUTAS_LEI],
            "setores": sorted(carreiras.firms.SETORES),
        }
        out["mundo"] = {
            "cidade": {"id": cid_atual[0], "nome": cid_atual[1], "uf": cid_atual[2], "fator": cid_atual[3]},
            "cidades": [{"id": x[0], "nome": x[1], "uf": x[2], "fator": x[3]} for x in mundo.CIDADES],
            "imoveis": [{"tipo": im["tipo"], "nome": mundo.IMOVEIS_POR_ID[im["tipo"]][1], "valor": im["valor"], "alugado": im.get("alugado", False)} for im in pat.get("imoveis", [])],
            "veiculo": {"tipo": pat["veiculo"]["tipo"], "nome": mundo.VEICULOS_POR_ID[pat["veiculo"]["tipo"]][1], "valor": pat["veiculo"]["valor"]} if pat.get("veiculo") else None,
            "equipamentos": list(pat.get("equipamentos", [])),
            "catalogo_equipamentos": [
                {"id": e[0], "nome": e[1], "preco": round(e[2] * mw, 2), "desc": e[3], "possui": e[0] in pat.get("equipamentos", [])}
                for e in mundo.EQUIPAMENTOS
            ],
            "plano_saude": bool(pat.get("plano_saude", False)),
            "plano_saude_mensalidade": round(mundo.PLANO_SAUDE_MENSAL_MINIMOS * mw, 2),
            "inv": dict(pat.get("inv", {"poupanca": 0.0, "tesouro": 0.0, "acoes": 0.0})),
            "emprestimo": pat.get("emprestimo", 0.0),
            "parcelas": pat.get("parcelas", 0),
            "limite_credito": mundo.limite_credito(game, p),
            "catalogo_imoveis": [{"id": x[0], "nome": x[1], "preco": round(x[2] * mw * cid_atual[3], 2)} for x in mundo.IMOVEIS],
            "catalogo_veiculos": [{"id": x[0], "nome": x[1], "preco": round(x[2] * mw, 2)} for x in mundo.VEICULOS],
            "extrato": mundo.extrato(game, p.id, 20),
            "noticias": mundo.noticias_recentes(game, 10),
        }
    return out


# --- avanço do tempo e relatório ------------------------------------------------------------------
def noticias_ano(game: Game) -> dict:
    """Notícias econômicas do ano corrente (usadas no relatório ao virar o ano)."""
    s = economy.summary(game)
    return {"ano": game.year, "clima": s["clima"], "indice_ciclo": round(s["indice_ciclo"], 2),
            "inflacao_anterior": s["inflacao_ano_anterior"], "salario_minimo": brl(s["salario_minimo"]),
            "inflacao_anterior_fmt": f"{s['inflacao_ano_anterior']:.1%}".replace(".", ","),
            "empregados": s["empregados"], "procurando": s["procurando"]}


def _relatorio_turno(game: Game, p: Character | None, pedidos: int, feitos: int, interrompido: str | None,
                     ano0: int, mes0: int, inicio: int, restantes: int = 0) -> dict:
    novos = game.biography[inicio:]
    meus = [evento_item(game, e, p) for e in novos if p is not None and e.char_id == p.id]
    mundo_ev = {
        "nascimentos": sum(1 for e in novos if e.category == "nascimento"),
        "mortes": sum(1 for e in novos if e.category == "morte"),
        "casamentos": sum(1 for e in novos if e.category == "casamento") // 2,
        "divorcios": sum(1 for e in novos if e.category == "divorcio") // 2,
        "namoros": sum(1 for e in novos if e.category == "namoro" and e.text.startswith("Começou")) // 2,
    }
    cruzou_janeiro = any((mes0 - 1 + i) % 12 == 0 for i in range(1, feitos + 1))
    return {"pedidos": pedidos, "meses": feitos, "restantes": restantes, "interrompido": interrompido,
            "data": game.date_str(), "de": f"{MESES[mes0 - 1]} de {ano0}", "meus": meus, "mundo": mundo_ev,
            "total_eventos": len(novos), "ano_novo": noticias_ano(game) if cruzou_janeiro else None,
            "jogador_morreu": interrompido == "morte", "decisao": decisions.view(game)}


def avancar(game: Game, meses: int, permitir_decisao: bool = True) -> dict:
    """Avança `meses` meses, um de cada vez (idêntico a `advance_months(game, meses)`), e para na morte do jogador.
    Se interrompido por decisão antes de concluir `meses`, guarda o restante em `game.decisions['turno']` para retomar."""
    if meses < 1:
        raise ValueError("meses deve ser >= 1")
    if game.decisions["pending"]:
        raise ValueError("Há uma decisão pendente: escolha antes de avançar.")
    game.decisions.pop("turno", None)
    p = player_of(game)
    vivo_antes = p is not None and p.alive
    ano0, mes0 = game.year, game.month
    inicio = len(game.biography)
    feitos, interrompido = 0, None
    for _ in range(meses):
        engine.advance_months(game, 1)
        feitos += 1
        if vivo_antes and not p.alive:
            interrompido = "morte"
            break
        foco.mensal(game, p)
        intelecto.apply_month(game)
        psicologia.apply_month(game)
        decisions.atrasadas(game)
        if permitir_decisao and decisions.tentar(game, p):
            interrompido = "decisao"
            break
    restantes = max(0, meses - feitos) if interrompido == "decisao" else 0
    if restantes > 0:
        game.decisions["turno"] = {
            "pedidos": meses, "feitos": feitos, "restantes": restantes,
            "ano0": ano0, "mes0": mes0, "inicio": inicio,
        }
    return _relatorio_turno(game, p, meses, feitos, interrompido, ano0, mes0, inicio, restantes)


def retomar_avanco(game: Game) -> dict:
    """Completa os meses restantes de um turno de 6 ou 12 meses pausado por uma decisão."""
    if game.decisions["pending"]:
        raise ValueError("Há uma decisão pendente: escolha antes de continuar.")
    turno = game.decisions.pop("turno", None)
    if not turno or int(turno.get("restantes", 0)) < 1:
        raise ValueError("Não há avanço pendente para retomar.")
    restantes = int(turno["restantes"])
    p = player_of(game)
    vivo_antes = p is not None and p.alive
    feitos_agora, interrompido = 0, None
    for _ in range(restantes):
        engine.advance_months(game, 1)
        feitos_agora += 1
        if vivo_antes and not p.alive:
            interrompido = "morte"
            break
        foco.mensal(game, p)
        intelecto.apply_month(game)
        psicologia.apply_month(game)
        decisions.atrasadas(game)
    total_feitos = int(turno["feitos"]) + feitos_agora
    return _relatorio_turno(
        game, p, int(turno["pedidos"]), total_feitos, interrompido,
        int(turno["ano0"]), int(turno["mes0"]), int(turno["inicio"]), 0,
    )


def herdeiros_possiveis(game: Game, c: Character) -> list[dict]:
    """Parentes vivos com quem o jogador pode continuar após a morte (cônjuge, filhos, irmãos, pais)."""
    vistos, out = set(), []

    def add(x: Character | None, rel: str) -> None:
        if x is not None and x.alive and x.id not in vistos and x.id != c.id:
            vistos.add(x.id)
            out.append(pessoa(game, x, rel=rel))
    conj = game.characters.get(c.spouse_id)
    add(conj, g(conj, "Esposa", "Marido") if conj else "Cônjuge")
    for f in sorted(game.children_of(c.id), key=lambda x: x.id):
        add(f, g(f, "Filha", "Filho"))
    for pai in game.parents_of(c):
        for irm in sorted(game.children_of(pai.id), key=lambda x: x.id):
            add(irm, g(irm, "Irmã", "Irmão"))
    for pai in game.parents_of(c):
        add(pai, g(pai, "Mãe", "Pai"))
    return out
