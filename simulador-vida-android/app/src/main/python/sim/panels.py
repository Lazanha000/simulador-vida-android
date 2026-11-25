"""Painéis de detalhe (v0.14.0): cada painel devolve {"titulo", "icone", "blocos": [...]} para a interface web.

Tipos de bloco (a interface tem um renderizador genérico para todos):
  linhas   {"titulo", "itens": [{"r": rótulo, "v": valor, "i": ícone?}]}
  barras   {"titulo", "itens": [{"r", "v": 0–100, "cor": saude|cognicao|social|patrimonio|felicidade, "x": texto?}]}
  pessoas  {"titulo", "itens": [pessoa], "vazio": texto}        pessoa = ver views.pessoa
  geracoes {"titulo", "linhas": [{"titulo", "itens": [pessoa]}]}
  eventos  {"titulo", "itens": [evento_item], "vazio"}
  lista    {"titulo", "itens": [{"titulo", "texto", "i"?}], "mais": {...}?}
  texto    {"texto", "cap": bool}      cap = primeira letra como capitular
  retrato  {"pessoa", "legenda"}
  filtros  {...biografia}      busca {...personagens}      acoes {"itens": [{"rotulo", "acao", ...}]}
Só leitura: nenhuma regra de simulação aqui. Números de regras vêm das constantes dos módulos do motor.
"""
from __future__ import annotations

from . import carreiras, economy, educacao_br, encontros, engine, firms, indicators, intelecto, livros, macro, mundo, psicologia, romance, vinculos, work
from .models import COGNICAO, MESES, PERSONALIDADE, Character, Game
from .views import (CATEGORIAS, ROTULOS, _CAT_PRIVADAS, abs_str, age_of, anos_meses, brl, civil, evento_item, g,
                    mes_ano, ocupacao_curta, pessoa, player_of, ref_date)

ICONE_EVENTO_CLIMA = "eventos/evento_ciclo_economico.svg"
ICONE_EVENTO_INFLACAO = "eventos/evento_inflacao.svg"


def _ic(nome: str) -> str:
    return f"icones/icone_{nome}.svg"


# --- construtores de bloco --------------------------------------------------------------------------
def L(titulo, itens) -> dict:
    return {"t": "linhas", "titulo": titulo,
            "itens": [({"r": i[0], "v": i[1]} | ({"i": i[2]} if len(i) > 2 else {})) for i in itens if i[1] not in (None, "")]}


def B(titulo, itens) -> dict:
    return {"t": "barras", "titulo": titulo,
            "itens": [{"r": r, "v": round(max(0.0, min(100.0, v))), "cor": cor, **({"x": x} if x else {})}
                      for r, v, cor, x in itens]}


def P(titulo, pessoas, vazio="Ninguém por aqui.") -> dict:
    return {"t": "pessoas", "titulo": titulo, "itens": pessoas, "vazio": vazio}


def T(texto, cap=False) -> dict:
    return {"t": "texto", "texto": texto, "cap": cap}


def EV(titulo, itens, vazio="Nada registrado ainda.") -> dict:
    return {"t": "eventos", "titulo": titulo, "itens": itens, "vazio": vazio}


def ACOES(itens) -> dict:
    return {"t": "acoes", "itens": itens}


def _painel(titulo: str, icone: str, blocos: list) -> dict:
    return {"titulo": titulo, "icone": icone, "blocos": blocos}


def _alive_friends(game: Game, c: Character) -> list[Character]:
    return [game.characters[i] for i in game.friend_ids(c.id)]


def _num(x: float) -> str:
    """Número com até 1 casa decimal e vírgula (2.5 → '2,5'; 15.0 → '15')."""
    return f"{x:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def _now_i(game: Game) -> int:
    return game.year * 12 + game.month


# --- linhas reutilizadas (ficha e painéis) -----------------------------------------------------------
def _empresa(game: Game, c: Character) -> str | None:
    if c.workplace is None or c.retired:
        return None
    f = game.firms.get(c.workplace)
    return f"Local de trabalho nº {c.workplace}" if f is None else f"{f.name} ({f.sector}, {f.size})"


def _linhas_escola(game: Game, c: Character) -> list:
    rows = [("Escolaridade", engine.education_label(c))]
    if (c.in_school or c.in_college) and c.school_performance is not None:
        rows.append(("Desempenho no último ano", f"{c.school_performance}/100"))
    if c.returned_to_school:
        rows.append(("Retorno aos estudos", "voltou a estudar depois de adulto"))
    if c.dropped_out:
        rows.append(("Situação", "abandonou os estudos"))
    return rows


def _linhas_trabalho(game: Game, c: Character) -> list:
    rows = []
    lab = work.work_label(c, *ref_date(game, c))
    if lab:
        rows.append(("Trabalho", lab[0].upper() + lab[1:]))
    if c.alive and (c.income > 0 or c.wealth != 0):
        rows += [("Renda", f"{brl(c.income)}/mês"), ("Patrimônio", brl(c.wealth))]
    rows.append(("Empresa", _empresa(game, c)))
    if c.alive and economy.receiving_unemployment(c, _now_i(game)):
        rows.append(("Seguro-desemprego", f"{brl(c.unemp_amount)}/mês (última parcela em {abs_str(c.unemp_until)})"))
    return rows


def _linhas_vida_a_dois(game: Game, c: Character) -> list:
    rows = [("Estado civil", civil(game, c))]
    conj = game.characters.get(c.spouse_id)
    if conj:
        rows.append(("Cônjuge", conj.full_name + ("" if conj.alive else " (falecido(a))")))
    if c.alive and c.pregnant_until is not None:
        rows.append(("Gestação", f"parto previsto em {abs_str(c.pregnant_until)}"))
    if c.leave_until is not None and economy.on_leave(c, _now_i(game)):
        rows.append(("Afastamento", f"até {abs_str(c.leave_until)} (licença-maternidade/cuidado do bebê)"))
    par = romance.partner_of(game, c)
    if par is not None:
        rows.append(("Namoro", f"{par.full_name} (há {anos_meses(_now_i(game) - (c.partner_since or 0))})"))
    ex = game.characters.get(c.ex_spouse_id)
    if ex and c.ex_spouse_id != c.spouse_id:
        rows.append(("Ex-cônjuge", ex.full_name + ("" if ex.alive else " (falecido(a))")))
    resp = game.characters.get(c.guardian_id) if c.guardian_id is not None else None
    if resp is not None and resp.alive and age_of(game, c) < 18:
        rows.append(("Guarda", resp.full_name))
    return rows


def _barras_personalidade(c: Character) -> dict:
    return B("Personalidade", [(ROTULOS[k], c.personality[k], "felicidade", None) for k in PERSONALIDADE])


def _barras_cognicao(game: Game, c: Character) -> dict:
    crianca = age_of(game, c) < 18
    return B("Cognição" + (" (em desenvolvimento)" if crianca else ""),
             [(ROTULOS[k], c.cognition[k], "cognicao",
               f"potencial {c.cognition_potential[k]}" if crianca and c.cognition_potential else None) for k in COGNICAO])


# --- parentesco ------------------------------------------------------------------------------------
def parentes(game: Game, c: Character) -> dict:
    pais = game.parents_of(c)
    avos = [(a, g(a, "Avó", "Avô")) for p in pais for a in game.parents_of(p)]
    irmaos = sorted({x.id: x for p in pais for x in game.children_of(p.id) if x.id != c.id}.values(), key=lambda x: x.id)
    filhos = sorted(game.children_of(c.id), key=lambda x: x.id)
    netos = sorted({n.id: n for f in filhos for n in game.children_of(f.id)}.values(), key=lambda x: x.id)
    return {"avos": avos, "pais": [(p, g(p, "Mãe", "Pai")) for p in pais],
            "irmaos": [(x, g(x, "Irmã", "Irmão")) for x in irmaos], "conjuge": game.characters.get(c.spouse_id),
            "filhos": [(f, g(f, "Filha", "Filho")) for f in filhos], "netos": [(n, g(n, "Neta", "Neto")) for n in netos]}


def _pp(game: Game, pares) -> list:
    return [pessoa(game, x, rel=r) for x, r in pares]


# --- painéis -------------------------------------------------------------------------------------
def p_ficha(game: Game, c: Character, q: dict, meta: dict) -> dict:
    a = age_of(game, c)
    pa = parentes(game, c)
    sit = "Vivo(a)" if c.alive else f"Faleceu em {MESES[c.death_month - 1]} de {c.death_year}"
    fam = game.families.get(c.family_id)
    blocos = [
        {"t": "retrato", "pessoa": pessoa(game, c), "legenda": f"{civil(game, c)} · {ocupacao_curta(game, c, a)}"},
        L("Identidade", [("Sexo", "Feminino" if c.sex == "F" else "Masculino"),
                         ("Idade", f"{a} anos ({engine.life_stage(a)})"),
                         ("Nascimento", f"{MESES[c.birth_month - 1]} de {c.birth_year}"), ("Situação", sit),
                         ("Família", fam.name if fam else None), ("Saúde", f"{c.health:.0f}/100")]),
        L("Estudos", _linhas_escola(game, c)),
        L("Trabalho e renda", _linhas_trabalho(game, c)),
        L("Vida a dois", _linhas_vida_a_dois(game, c)),
        P("Pais", _pp(game, pa["pais"]), "Pais não registrados."),
        P("Filhos", _pp(game, pa["filhos"]), "Sem filhos."),
        P("Amigos", [pessoa(game, x) for x in _alive_friends(game, c)], "Sem amigos registrados."),
        _barras_personalidade(c), _barras_cognicao(game, c),
    ]
    if c.alive and c.id != game.player_id:
        blocos.append(ACOES([{"rotulo": f"Jogar com {c.first_name}", "acao": "jogar", "id": c.id}]))
    return _painel(c.full_name, _ic("biografia"), blocos)


def p_escola(game: Game, c: Character, q: dict, meta: dict) -> dict:
    sup = 100.0 if c.graduated else c.higher_years / engine.ANOS_SUPERIOR * 100
    blocos = [
        L("Situação", _linhas_escola(game, c)),
        B("Progresso", [("Ensino básico", c.schooling_years / 12 * 100, "cognicao", f"{c.schooling_years} de 12 anos"),
                        ("Ensino superior", sup, "patrimonio",
                         "formado(a)" if c.graduated else f"{c.higher_years} de {engine.ANOS_SUPERIOR} anos")]),
    ]
    if c.alive and (c.in_school or c.in_college):
        now = (game.year, game.month)
        colegas = [o for o in sorted(game.characters.values(), key=lambda x: x.id)
                   if o.alive and o.id != c.id and engine._classmates(c, o, now)]
        blocos.append(P(f"Colegas de turma ({len(colegas)})", [pessoa(game, o) for o in colegas[:8]], "Sem colegas."))
    esc = [evento_item(game, e, c) for e in game.events_for(c.id, "escola")][::-1][:10]
    blocos.append(EV("Trajetória escolar (mais recentes primeiro)", esc))
    blocos.append(T(
        f"A matrícula acontece aos {engine.IDADE_ESCOLAR_MIN} anos, em fevereiro; o ano letivo fecha em dezembro, com "
        f"aprovação a partir da nota {engine.NOTA_APROVACAO}. O fundamental tem 9 anos e o médio, 3. O ensino superior "
        f"dura {engine.ANOS_SUPERIOR} anos, com ingresso em fevereiro por idade e aptidão. Adultos de "
        f"{engine.IDADE_RETORNO_MIN} a {engine.IDADE_RETORNO_MAX} anos que pararam antes do médio podem voltar a estudar."))
    ed = game.educacao_br.get(c.id)
    if ed:
        erows = []
        if ed.get("enem"):
            erows.append(("Último ENEM", f"{ed['enem']['media']:.1f} (Redação {ed['enem']['redacao']})"))
        if ed.get("uni") and ed.get("curso"):
            uni_n = educacao_br.UNIS_POR_SIGLA.get(ed["uni"], (ed["uni"],))[0]
            curso_n = educacao_br.CURSOS_POR_ID.get(ed["curso"], (None, ed["curso"]))[1]
            erows.append(("Universidade", f"{curso_n} · {uni_n} ({str(ed.get('modalidade', '')).upper().replace('_', ' ')})"))
        if ed.get("fies_divida", 0.0) > 0:
            erows.append(("Dívida FIES", brl(ed["fies_divida"])))
        if ed.get("ic_meses", 0) > 0:
            erows.append(("Iniciação Científica", f"{ed['ic_meses']} mês(es) restante(s)"))
        if ed.get("pos_atual"):
            pa = ed["pos_atual"]
            erows.append(("Pós-graduação atual", f"{educacao_br.POS_NIVEIS[pa['nivel']][0]} ({pa['meses']} meses restantes)"))
        if ed.get("pos_concluidas"):
            erows.append(("Pós concluídas", ", ".join(educacao_br.POS_NIVEIS[n][0] for n in ed["pos_concluidas"])))
        if ed.get("tecnico_atual"):
            ta = ed["tecnico_atual"]
            tn = educacao_br.CURSOS_TECNICOS_POR_ID.get(ta["id"], (None, ta["id"]))[1]
            erows.append(("Curso técnico atual", f"{tn} ({ta['meses']} meses restantes)"))
        if ed.get("tecnicos_concluidos"):
            erows.append(("Técnicos concluídos", ", ".join(educacao_br.CURSOS_TECNICOS_POR_ID[t][1] for t in ed["tecnicos_concluidos"] if t in educacao_br.CURSOS_TECNICOS_POR_ID)))
        if erows:
            blocos.insert(1, L("Formação Superior, Técnica & ENEM", erows))
    iv = intelecto.dados(game, c.id) if c.id in game.intelecto else None
    if iv:
        con_rows = [(intelecto.AREAS_POR_ID[aid][1], f"{pts} pts") for aid, _, _ in intelecto.AREAS_CONHECIMENTO for pts in (iv.get("conhecimentos", {}).get(aid, 0),) if pts > 0]
        if con_rows:
            blocos.insert(2, L("Conhecimentos acumulados", con_rows))
    if c.id == game.player_id and c.alive:
        blocos.append(ACOES([
            {"rotulo": "Estudar e fazer simulado", "acao": "abrir_modal", "modal": "estudar"},
            {"rotulo": f"Biblioteca ({len(livros.CATALOGO)} livros)", "acao": "abrir_modal", "modal": "livros"},
            {"rotulo": "Redação, artigos e filmes", "acao": "abrir_modal", "modal": "formacao"},
            {"rotulo": "ENEM, faculdade, técnico e pós", "acao": "abrir_modal", "modal": "educacao_br"},
        ]))
    return _painel("Escola", _ic("escola"), blocos)


def p_bens(game: Game, c: Character, q: dict, meta: dict) -> dict:
    h = economy.household_of(game, c)
    blocos = [B("Patrimônio", [("Patrimônio pessoal", indicators.wealth_score(game, c), "patrimonio", brl(c.wealth))]),
              L("Você", [("Patrimônio pessoal", brl(c.wealth)), ("Renda pessoal", f"{brl(c.income)}/mês")])]
    if h is None:
        blocos.append(T("Sem domicílio (personagem falecido)."))
    else:
        saldo = h["income"] - h["imposto"] - h["cost"]
        blocos.append(L("Domicílio", [
            ("Renda total", f"{brl(h['income'])}/mês"),
            ("Auxílio social", f"{brl(h['auxilio'])}/mês" if h["auxilio"] else None),
            ("Pensão alimentícia recebida", f"{brl(h['pensao_recebida'])}/mês" if h["pensao_recebida"] else None),
            ("Pensão alimentícia paga", f"{brl(h['pensao_paga'])}/mês" if h["pensao_paga"] else None),
            ("Impostos e previdência", f"{brl(h['imposto'])}/mês" if h["imposto"] else None),
            ("Custo de vida", f"{brl(h['cost'])}/mês"), ("Saldo mensal (após impostos)", brl(saldo))]))
        blocos.append(P("Moram com você", [pessoa(game, m, sub=f"renda {brl(m.income)}/mês" if m.income else "dependente")
                                           for m in h["adults"] + h["kids"] if m.id != c.id], "Você mora sozinho(a)."))
    blocos.append(T(f"Valores ilustrativos, em reais correntes. Salário mínimo vigente: {brl(macro.min_wage(game))}; "
                    f"índice de preços: {macro.price_level(game):.3f} (1,000 no início da partida)."))
    cid_info = mundo.cidade_of(game, c.id)
    pat = game.patrimonio.get(c.id)
    mrows = [("Cidade atual", f"{cid_info[1]}/{cid_info[2]} (custo {cid_info[3]:.2f}×)")]
    if pat:
        inv = pat.get("inv", {})
        total_inv = sum(inv.values())
        if total_inv > 0:
            mrows.append(("Investimentos", f"{brl(total_inv)} (Poup. {brl(inv.get('poupanca', 0))} · Tes. {brl(inv.get('tesouro', 0))} · Ações {brl(inv.get('acoes', 0))})"))
        if pat.get("imoveis"):
            mrows.append(("Imóveis", f"{len(pat['imoveis'])} imóvel(is)"))
        if pat.get("veiculo"):
            v = pat["veiculo"]
            mrows.append(("Veículo", f"{mundo.VEICULOS_POR_ID[v['tipo']][1]} ({brl(v['valor'])})"))
        if pat.get("equipamentos"):
            mrows.append(("Equipamentos", ", ".join(mundo.EQUIPAMENTOS_POR_ID[e][1] for e in pat["equipamentos"] if e in mundo.EQUIPAMENTOS_POR_ID)))
        if pat.get("plano_saude"):
            mrows.append(("Plano de saúde", "ativo (mensal)"))
        if pat.get("emprestimo", 0.0) > 0:
            mrows.append(("Empréstimo ativo", f"{brl(pat['emprestimo'])} ({pat.get('parcelas', 0)} parcelas)"))
    blocos.insert(2, L("Cidade, imóveis e banco", mrows))
    ext = mundo.extrato(game, c.id, 10)
    if ext:
        blocos.append(L("Extrato recente", [
            (f"{x['mes']:02d}/{x['ano']} · {x['desc']}", ("+" if x["tipo"] == "entrada" else "-") + brl(x["valor"]))
            for x in ext
        ]))
    if c.id == game.player_id and c.alive:
        blocos.append(ACOES([{"rotulo": "Cidade, imóveis, itens e banco", "acao": "abrir_modal", "modal": "mundo"}]))
    return _painel("Bens e finanças", _ic("bens"), blocos)


def p_relacoes(game: Game, c: Character, q: dict, meta: dict) -> dict:
    conj, par = game.characters.get(c.spouse_id), romance.partner_of(game, c)
    ex = game.characters.get(c.ex_spouse_id)
    pessoas = []
    if conj:
        pessoas.append(pessoa(game, conj, rel=g(conj, "Esposa", "Marido")))
    if par:
        pessoas.append(pessoa(game, par, rel=g(par, "Namorada", "Namorado")))
    if ex and c.ex_spouse_id != c.spouse_id:
        pessoas.append(pessoa(game, ex, rel=g(ex, "Ex-esposa", "Ex-marido")))
    sit_rows = _linhas_vida_a_dois(game, c)
    if c.id == game.player_id and c.alive:
        pref_map = {"oposto": "Sexo oposto", "mesmo": "Mesmo sexo", "todos": "Todos"}
        sit_rows.append(("Preferência afetiva", pref_map.get(encontros.preferencia_of(game, c.id), "Sexo oposto")))
    blocos = [L("Situação", sit_rows), P("Pessoas", pessoas, "Nenhum vínculo amoroso registrado.")]
    if c.id == game.player_id and c.alive:
        vinc = vinculos.pessoas_proximas(game)
        if vinc:
            blocos.append(L("Vínculos multidimensionais", [
                (f"{v['nome']} ({v['relacao']})",
                 f"Afin. {v['afinidade']} · Conf. {v['confianca']} · Resp. {v['respeito']}"
                 + (f" · Host. {v['hostilidade']}" if v["hostilidade"] >= 30 else ""))
                for v in vinc[:6]
            ]))
        blocos.append(ACOES([
            {"rotulo": "Vínculos, família e rivais", "acao": "abrir_modal", "modal": "vinculos"},
            {"rotulo": "Encontros e namoro", "acao": "abrir_modal", "modal": "encontros"},
        ]))
    blocos.append(T(f"Namoro a partir dos {romance.IDADE_MIN} anos; casamento após {romance.MESES_ANTES_CASAR} meses de namoro e idade ≥{engine.IDADE_CASAMENTO_MIN}. "
                    "Cada vínculo guarda afinidade, confiança, intimidade, respeito, hostilidade e memórias."))
    return _painel("Relações", _ic("relacoes"), blocos)


def p_trabalho(game: Game, c: Character, q: dict, meta: dict) -> dict:
    a, now = age_of(game, c), _now_i(game)
    blocos = []
    if a < work.IDADE_TRABALHO_MIN and not work.is_employed(c):
        blocos.append(T(f"Ainda não pode trabalhar: a idade mínima para procurar emprego é {work.IDADE_TRABALHO_MIN} anos."))
    else:
        firm = economy._firm_of(game, c) if work.is_employed(c) else None
        rows = _linhas_trabalho(game, c)
        if work.is_employed(c):
            rows += [("Nível na carreira", work.RANKS[c.rank]), ("Vínculo", "informal" if c.informal else "formal"),
                     ("Salário bruto", f"{brl(economy.monthly_salary(c, firm, macro.min_wage(game)))}/mês"),
                     ("No emprego há", anos_meses(now - (c.job_start or now))),
                     ("No nível há", anos_meses(now - (c.rank_since or c.job_start or now)))]
        if c.seeking_since is not None and work.is_seeking(c):
            rows.append(("Procurando trabalho há", anos_meses(now - c.seeking_since)))
        if c.leave_until is not None and economy.on_leave(c, now):
            rows.append(("Afastamento até", abs_str(c.leave_until)))
        rows += [("Experiência acumulada", anos_meses(c.experience)), ("Empregos já tidos", str(c.jobs_held))]
        blocos.append(L("Situação", rows))
        blocos.append(B("Aptidão", [("Aptidão profissional", work.work_aptitude(c), "cognicao", "cognição 60% + conscienciosidade 40%")]))
        if work.is_employed(c) and c.workplace is not None:
            colegas = [o for o in sorted(game.characters.values(), key=lambda x: x.id)
                       if o.id != c.id and engine._coworkers(c, o)]
            blocos.append(P(f"Colegas de trabalho ({len(colegas)})", [pessoa(game, o) for o in colegas[:10]], "Sem colegas."))
    tr = [evento_item(game, e, c) for e in game.events_for(c.id, "trabalho")][::-1][:10]
    blocos.append(EV("Carreira (mais recentes primeiro)", tr))
    ex = game.carreira_extra.get(c.id, {})
    pol = game.politica.get(c.id, {})
    extra_rows = []
    if ex.get("estavel"):
        extra_rows.append(("Serviço público", f"{ex.get('cargo_publico') or 'Concursado'} (estável)"))
    if ex.get("meio_periodo"):
        mp = ex["meio_periodo"]
        extra_rows.append(("Estágio / meio período", f"{mp.get('area', 'Geral')} ({mp.get('salario_minimos', 0.65):.2f} mín.)"))
    if ex.get("empresa_id") is not None and ex["empresa_id"] in game.firms and game.firms[ex["empresa_id"]].is_open:
        fprop = game.firms[ex["empresa_id"]]
        extra_rows.append(("Empresa própria", f"{fprop.name} ({fprop.sector}, {fprop.size})"))
    if pol.get("partido"):
        extra_rows.append(("Partido político", carreiras.PARTIDOS_POR_ID.get(pol["partido"], pol["partido"])))
        extra_rows.append(("Influência política", f"{pol.get('influencia', 0):.0f}/100"))
    if pol.get("cargo"):
        extra_rows.append(("Mandato eletivo", f"{carreiras.CARGOS_POR_ID[pol['cargo']][1]} ({pol.get('mandato_meses', 0)} meses)"))
    if extra_rows:
        blocos.insert(1, L("Concursos, estágio, empresa e política", extra_rows))
    if c.id == game.player_id and c.alive:
        blocos.append(ACOES([
            {"rotulo": "Concursos, freelas, empresa e política", "acao": "abrir_modal", "modal": "carreiras"},
            {"rotulo": "Empresas do mercado", "acao": "painel", "nome": "empresas"},
        ]))
    return _painel("Trabalho", _ic("trabalho"), blocos)


def p_saude(game: Game, c: Character, q: dict, meta: dict) -> dict:
    a = age_of(game, c)
    rows = [("Saúde", f"{c.health:.0f}/100"), ("Fase da vida", engine.life_stage(a))]
    if c.alive:
        rows.append(("Risco de morte nos próximos 12 meses", f"{engine.mortality_annual(a, c.health):.1%}".replace(".", ",")))
        if c.pregnant_until is not None:
            rows.append(("Gestação", f"parto previsto em {abs_str(c.pregnant_until)}"))
    blocos = [B("Condição", [("Saúde geral", c.health, "saude", None)]), L("Detalhes", rows),
              T("A saúde oscila com a idade e a mortalidade depende dela. As taxas são ilustrativas (calibradas para uma "
                "expectativa de vida simulada próxima de 75 anos), não estatística oficial.")]
    return _painel("Saúde", _ic("saude"), blocos)


def p_mente(game: Game, c: Character, q: dict, meta: dict) -> dict:
    iv = intelecto.dados(game, c.id) if (c.id in game.intelecto or c.id == game.player_id) else None
    psi = psicologia.dados(game, c.id) if (c.id in game.psicologia or c.id == game.player_id) else None
    con_rows = []
    if iv:
        ret = iv.get("retencao", {})
        con_rows = [
            (intelecto.AREAS_POR_ID[aid][1], f"{pts} pts · retenção {ret.get(aid, 100.0):.0f}%")
            for aid, _, _ in intelecto.AREAS_CONHECIMENTO
            for pts in (iv.get("conhecimentos", {}).get(aid, 0),) if pts > 0
        ]
    blocos = [_barras_personalidade(c), _barras_cognicao(game, c)]
    if psi:
        prows = []
        if psi.get("mostrar_qi"):
            prows.append(("QI estimado (indicador opcional)", str(psicologia.qi_estimado(c))))
        if psi.get("valores"):
            prows.append(("Valores pessoais", ", ".join(psi["valores"])))
        if psi.get("medos"):
            prows.append(("Medos e preocupações", ", ".join(psi["medos"])))
        if psi.get("habitos"):
            prows.append(("Hábitos ativos", ", ".join(psicologia.HABITOS_POR_ID[h][1] for h in psi["habitos"] if h in psicologia.HABITOS_POR_ID)))
        if psi.get("metas_ativas"):
            prows.append(("Metas em andamento", ", ".join(psicologia.METAS_POR_ID[m][1] for m in psi["metas_ativas"] if m in psicologia.METAS_POR_ID)))
        if psi.get("metas_concluidas"):
            prows.append(("Metas realizadas", str(len(psi["metas_concluidas"]))))
        if prows:
            blocos.append(L("Psicologia, hábitos e metas", prows))
    if con_rows:
        blocos.append(L("Áreas de conhecimento e retenção", con_rows))
    if iv and iv.get("idiomas"):
        id_rows = [(intelecto.IDIOMAS_POR_ID[iid][1], f"{pct:.0f}% ({intelecto.nivel_idioma(pct)})")
                   for iid, pct in iv["idiomas"].items() if iid in intelecto.IDIOMAS_POR_ID and pct > 0]
        if id_rows:
            blocos.append(L("Idiomas", id_rows))
    if c.id == game.player_id and c.alive:
        blocos.append(ACOES([
            {"rotulo": "Psicologia, hábitos e metas", "acao": "abrir_modal", "modal": "psicologia"},
            {"rotulo": "Estudar, revisar e idiomas", "acao": "abrir_modal", "modal": "estudar"},
            {"rotulo": f"Biblioteca ({len(livros.CATALOGO)} livros)", "acao": "abrir_modal", "modal": "livros"},
            {"rotulo": "Redação, artigos e filmes", "acao": "abrir_modal", "modal": "formacao"},
        ]))
    blocos.append(T(
        "A cognição cresce até os 18 anos e evolui em qualquer fase com leitura, estudo, revisões espaçadas, idiomas, "
        "pesquisa, redações e filmes — elevando também o potencial quando há esforço ativo."
    ))
    return _painel("Mente", _ic("cognicao"), blocos)


def p_social(game: Game, c: Character, q: dict, meta: dict) -> dict:
    amigos = _alive_friends(game, c)
    itens = []
    for x in amigos:
        ano, mes = game.friendships[(min(c.id, x.id), max(c.id, x.id))]
        itens.append(pessoa(game, x, sub=f"{resumo_curto(game, x)} · amigos desde {mes_ano(ano, mes)}"))
    vivos = sum(1 for x in amigos if x.alive)
    circulo = [("Amigos e amigos de amigos", str(len(engine.social_circle(game, c))))]
    if work.is_employed(c):
        circulo.append(("Colegas de trabalho", str(sum(1 for o in game.characters.values() if o.id != c.id and engine._coworkers(c, o)))))
    blocos = [B("Vida social", [("Amigos vivos", vivos / engine.MAX_AMIGOS * 100, "social", f"{vivos} de {engine.MAX_AMIGOS}"),
                                ("Índice social", indicators.social_score(game, c), "social", None)]),
              P("Amigos", itens, "Sem amigos registrados."), L("Círculo", circulo)]
    if c.id == game.player_id and c.alive:
        vinc = vinculos.pessoas_proximas(game)
        riv = [v for v in vinc if v["hostilidade"] >= 50]
        if riv:
            blocos.append(L("Rivais e inimizades", [(f"{v['nome']} ({v['relacao']})", f"Hostilidade {v['hostilidade']}/100") for v in riv]))
        blocos.append(ACOES([{"rotulo": "Vínculos, família e rivais", "acao": "abrir_modal", "modal": "vinculos"}]))
    if c.alive and age_of(game, c) < engine.IDADE_AMIZADE_MIN:
        blocos.append(T(f"Amizades começam aos {engine.IDADE_AMIZADE_MIN} anos."))
    return _painel("Social", _ic("social"), blocos)


def resumo_curto(game: Game, c: Character) -> str:
    a = age_of(game, c)
    return f"{a} anos" if c.alive else f"† aos {a} anos"


def p_bemestar(game: Game, c: Character, q: dict, meta: dict) -> dict:
    a = age_of(game, c)
    comp = [("Saúde", c.health, "saude", f"peso {indicators.PESO_SAUDE:.0%}"),
            ("Vida social", indicators.social_score(game, c), "social", f"peso {indicators.PESO_SOCIAL:.0%}"),
            ("Folga financeira", indicators.finance_score(game, c), "patrimonio", f"peso {indicators.PESO_FINANCAS:.0%}"),
            ("Ocupação", indicators.occupation_score(game, c, a), "cognicao", f"peso {indicators.PESO_OCUPACAO:.0%}")]
    return _painel("Bem-estar", _ic("saude"), [
        B("Bem-estar geral", [("Bem-estar", indicators.wellbeing(game, c), "felicidade", None)]), B("Componentes", comp),
        T("Indicador derivado e ilustrativo: não é um atributo do motor e não altera a simulação. Combina saúde, amizades e "
          "vínculos, a folga do orçamento do domicílio (renda menos impostos, sobre o custo de vida) e a ocupação (estudando, "
          "empregado, aposentado ou procurando trabalho).")])


def p_familia(game: Game, c: Character, q: dict, meta: dict) -> dict:
    pa = parentes(game, c)
    fam = game.families.get(c.family_id)
    membros = sum(1 for x in game.characters.values() if x.family_id == c.family_id and x.alive) if fam else 0
    blocos = [L("Família", [("Sobrenome", fam.name if fam else None), ("Membros vivos", str(membros) if fam else None)]),
              P("Pais", _pp(game, pa["pais"]), "Pais não registrados."),
              P("Cônjuge", [pessoa(game, pa["conjuge"], rel=g(pa["conjuge"], "Esposa", "Marido"))] if pa["conjuge"] else [], "Sem cônjuge registrado."),
              P("Irmãos", _pp(game, pa["irmaos"]), "Sem irmãos."), P("Filhos", _pp(game, pa["filhos"]), "Sem filhos."),
              P("Avós", _pp(game, pa["avos"]), "Avós não registrados."), P("Netos", _pp(game, pa["netos"]), "Sem netos.")]
    return _painel("Família", _ic("familia"), blocos)


def p_arvore(game: Game, c: Character, q: dict, meta: dict) -> dict:
    pa = parentes(game, c)
    meio = [pessoa(game, c, rel="Você")] + _pp(game, pa["irmaos"]) + (
        [pessoa(game, pa["conjuge"], rel=g(pa["conjuge"], "Esposa", "Marido"))] if pa["conjuge"] else [])
    linhas = [("Avós", _pp(game, pa["avos"])), ("Pais", _pp(game, pa["pais"])), ("Você, irmãos e cônjuge", meio),
              ("Filhos", _pp(game, pa["filhos"])), ("Netos", _pp(game, pa["netos"]))]
    blocos = [{"t": "geracoes", "titulo": "Gerações", "linhas": [{"titulo": t, "itens": i} for t, i in linhas if i]}]
    return _painel("Árvore familiar", _ic("arvore"), blocos)


def p_biografia(game: Game, c: Character | None, q: dict, meta: dict) -> dict:
    cat = q.get("cat") or None
    de = int(q["de"]) if str(q.get("de", "")).lstrip("-").isdigit() else None
    ate = int(q["ate"]) if str(q.get("ate", "")).lstrip("-").isdigit() else None
    todos = str(q.get("todos", "0")) == "1" or c is None   # sem personagem, só o mundo
    if cat is not None and cat not in CATEGORIAS:
        raise ValueError("categoria inválida")
    evs = game.events_for(None if todos else c.id, cat, de, ate)
    if todos:
        evs = [e for e in evs if e.category not in _CAT_PRIVADAS or (c is not None and e.char_id == c.id)]
    total = len(evs)
    LIM = 150
    itens = [evento_item(game, e, game.characters.get(e.char_id) if todos else c, com_quem=todos) for e in evs[-LIM:]][::-1]
    filtros = {"t": "filtros", "cat": cat or "", "de": de, "ate": ate, "todos": todos,
               "categorias": [{"id": "", "rotulo": "Todas"}] + [{"id": k, "rotulo": v} for k, v in CATEGORIAS.items()]}
    nome = "Biografia" if not todos else "Acontecimentos do mundo"
    return _painel(nome, _ic("biografia"), [
        filtros, EV(f"{total} registro(s)" + (f" — mostrando os {LIM} mais recentes" if total > LIM else "")
                    + " (mais recentes primeiro)", itens, "Nenhum registro para esse filtro.")])


def p_empresas(game: Game, c: Character | None, q: dict, meta: dict) -> dict:
    lim = max(5, min(200, int(q.get("lim", 12))))
    v = firms.vacancy_stats(game)
    fill = firms.filled(game)
    por_empresa: dict[int, int] = {}
    for (fid, _), n in fill.items():
        por_empresa[fid] = por_empresa.get(fid, 0) + n
    abertas = sorted((f for f in game.firms.values() if f.is_open), key=lambda f: (-sum(f.slots.values()), f.id))
    minha = c.workplace if (c is not None and work.is_employed(c)) else None
    itens = [{"titulo": f.name + (" — onde você trabalha" if f.id == minha else ""),
              "texto": f"{f.sector}, {f.size}: {por_empresa.get(f.id, 0)}/{sum(f.slots.values())} vagas ocupadas",
              "i": _ic("empresas")} for f in abertas[:lim]]
    lista = {"t": "lista", "titulo": f"Maiores empresas abertas ({min(lim, len(abertas))} de {len(abertas)})", "itens": itens}
    if len(abertas) > lim:
        lista["mais"] = {"rotulo": f"Mostrar mais ({len(abertas) - lim})", "acao": "painel", "nome": "empresas", "q": {"lim": lim + 15}}
    return _painel("Empresas e vagas", _ic("empresas"), [
        L("Mercado", [("Empresas abertas", str(v["abertas"])), ("Empresas fechadas", str(v["fechadas"])),
                      ("Vagas", f"{v['vagas']} (ocupadas {v['ocupadas']}, livres {v['livres']})"),
                      ("Vacância", f"{v['vacancia']:.0%}")]), lista,
        T("Empresas genéricas e valores ilustrativos; nenhuma empresa real.")])


def p_panorama(game: Game, c: Character | None, q: dict, meta: dict) -> dict:
    s = economy.summary(game)
    pct = lambda x: f"{x:.1%}".replace(".", ",")  # noqa: E731
    por_nivel = [(f"Renda média — {work.NIVEIS[k]}", brl(v)) for k, v in s["renda_por_escolaridade"].items()]
    return _painel("Panorama econômico", _ic("panorama"), [
        L("Conjuntura", [("Clima econômico", f"{s['clima']} (índice {s['indice_ciclo']:+.2f})".replace(".", ","), ICONE_EVENTO_CLIMA),
                         ("Inflação do ano", f"{pct(s['inflacao_anual'])} (ano anterior: {pct(s['inflacao_ano_anterior'])})", ICONE_EVENTO_INFLACAO),
                         ("Índice de preços", f"{s['indice_precos']:.3f}"),
                         ("Salário mínimo", f"{brl(s['salario_minimo'])} ({brl(s['salario_minimo_real'])} em valores do início)")]),
        L("População e renda", [("População viva", f"{s['populacao']} (adultos: {s['adultos']})"),
                                ("Renda média", brl(s["renda_media"])), ("Renda mediana", brl(s["renda_mediana"])),
                                ("Gini da renda", f"{s['gini_renda']:.2f}".replace(".", ",")),
                                ("Patrimônio total", brl(s["patrimonio_total"])), ("Patrimônio mediano", brl(s["patrimonio_mediano"]))]),
        L("Emprego", [("Empregados", f"{s['empregados']} (informais: {s['informais']})"),
                      ("Procurando trabalho", str(s["procurando"])), ("Com seguro-desemprego", str(s["segurados"])),
                      ("Empresas abertas", f"{s['empresas_abertas']} (fechadas: {s['empresas_fechadas']})"),
                      ("Vagas livres", f"{s['vagas_livres']}/{s['vagas']} ({s['vacancia']:.0%})")]),
        L("Renda por escolaridade", por_nivel)])


def p_impostos(game: Game, c: Character | None, q: dict, meta: dict) -> dict:
    mw, s = macro.min_wage(game), economy.summary(game)
    blocos = []
    if c is not None:
        if economy.taxpayer(c):
            bruto = economy.monthly_salary(c, economy._firm_of(game, c), mw)
            imp = economy.income_tax(bruto, mw)
            blocos.append(L("Seus impostos", [("Salário bruto", f"{brl(bruto)}/mês"), ("Previdência + imposto de renda", f"{brl(imp)}/mês"),
                                              ("Alíquota efetiva", f"{imp / bruto:.1%}".replace(".", ",")), ("Salário líquido", f"{brl(bruto - imp)}/mês")]))
        else:
            blocos.append(T("Você não paga imposto sobre a renda: só vínculo formal, sem aposentadoria, contribui."))
        h = economy.household_of(game, c)
        if h is not None:
            blocos.append(L("Seu domicílio", [("Impostos e previdência", f"{brl(h['imposto'])}/mês")]))
    m = game.macro
    blocos.append(L("Orçamento do Estado", [
        ("Ano corrente — receita", brl(s["receita_estado"])), ("Ano corrente — despesa", brl(s["despesa_estado"])),
        ("Ano anterior — receita", brl(s["receita_estado_ano_anterior"])), ("Ano anterior — despesa", brl(s["despesa_estado_ano_anterior"])),
        ("Caixa acumulado", brl(m["treasury"]))]))
    faixas = [(f"até {_num(lim)} mín.: {_num(taxa * 100)}%" if lim != float("inf") else f"acima: {_num(taxa * 100)}%")
              for lim, taxa in economy.IR_FAIXAS]
    blocos.append(T(f"Previdência de {economy.PREVIDENCIA:.0%} do salário (até {economy.PREVIDENCIA_TETO:.0f} mínimos) mais imposto de "
                    f"renda progressivo sobre o restante: " + "; ".join(faixas) + ". Só vale para vínculo formal. Receita = impostos; despesa = "
                    "aposentadorias, seguro-desemprego, assistência a idosos, licenças-maternidade e auxílio social."))
    return _painel("Impostos", _ic("impostos"), blocos)


def p_seguro(game: Game, c: Character, q: dict, meta: dict) -> dict:
    a, now = age_of(game, c), _now_i(game)
    rows = []
    if economy.receiving_unemployment(c, now):
        rows.append(("Seguro-desemprego", f"{brl(c.unemp_amount)}/mês (última parcela em {abs_str(c.unemp_until)})"))
    else:
        rows.append(("Seguro-desemprego", "não está recebendo"))
    if c.retired:
        rows.append(("Aposentadoria", f"{brl(c.income)}/mês"))
    elif a >= economy.IDADE_ASSISTENCIAL and not work.is_employed(c):
        rows.append(("Assistência a idosos", f"{brl(macro.min_wage(game))}/mês (1 salário mínimo)"))
    h = economy.household_of(game, c) if c.alive else None
    if h and h["auxilio"]:
        rows.append(("Auxílio social do domicílio", f"{brl(h['auxilio'])}/mês"))
    if c.leave_until is not None and economy.on_leave(c, now):
        rows.append(("Licença-maternidade", f"até {abs_str(c.leave_until)}"))
    parcelas = "; ".join(f"≥ {m} meses de vínculo: {n} parcelas" for m, n in economy.SEGURO_PARCELAS[::-1])
    return _painel("Proteção social", _ic("seguro"), [
        L("Sua situação", rows),
        T(f"Seguro-desemprego: demissão involuntária de vínculo formal; {economy.SEGURO_TAXA:.0%} do último salário, entre "
          f"{economy.SEGURO_PISO / economy.SALARIO_MINIMO:.0f} e {economy.SEGURO_TETO / economy.SALARIO_MINIMO:.0f} salários mínimos ({parcelas}). "
          f"Aposentadoria a partir dos {work.IDADE_APOSENTADORIA_MIN} anos (todos aos 75): formal = {economy.TAXA_APOSENTADORIA:.0%} do último salário; "
          f"informal = 1 mínimo. Licença-maternidade: {engine.LICENCA_MESES} meses com salário integral para mães com vínculo formal, "
          f"paga pelo Estado.")])


def p_personagens(game: Game, c: Character | None, q: dict, meta: dict) -> dict:
    busca = (q.get("busca") or "").strip().lower()
    pag = max(0, int(q.get("pag", 0)))
    PAG = 25
    todos = sorted(game.characters.values(), key=lambda x: (not x.alive, x.id))
    if busca:
        todos = [x for x in todos if busca in x.full_name.lower()]
    parte = todos[pag * PAG:(pag + 1) * PAG]
    lista = {"t": "pessoas", "titulo": f"Personagens ({len(todos)})", "itens": [pessoa(game, x) for x in parte],
             "vazio": "Nenhum personagem encontrado."}
    blocos = [{"t": "busca", "valor": busca, "painel": "personagens"}, lista]
    nav = []
    if pag > 0:
        nav.append({"rotulo": "‹ Anteriores", "acao": "painel", "nome": "personagens", "q": {"pag": pag - 1, "busca": busca}})
    if (pag + 1) * PAG < len(todos):
        nav.append({"rotulo": "Próximos ›", "acao": "painel", "nome": "personagens", "q": {"pag": pag + 1, "busca": busca}})
    if nav:
        blocos.append(ACOES(nav))
    blocos.append(ACOES([{"rotulo": "Criar personagem", "acao": "criar_personagem"},
                         {"rotulo": "Criar família", "acao": "criar_familia"}]))
    return _painel("Personagens", _ic("social"), blocos)


def p_config(game: Game, c: Character | None, q: dict, meta: dict) -> dict:
    auto = bool(meta.get("autosave", True))
    acoes = [
        {"rotulo": f"Autosave: {'ligado' if auto else 'desligado'}", "acao": "autosave", "valor": not auto},
        {"rotulo": "Alternar modo escuro / claro", "acao": "tema"},
        {"rotulo": "Lembrar onde eu estava", "acao": "lembrar"},
        {"rotulo": "Salvar agora", "acao": "salvar"},
        {"rotulo": "Personagens", "acao": "painel", "nome": "personagens"},
        {"rotulo": "Texto maior", "acao": "texto", "delta": 1}, {"rotulo": "Texto menor", "acao": "texto", "delta": -1},
    ]
    if c is not None and c.alive:
        psi = psicologia.dados(game, c.id)
        qi_on = bool(psi.get("mostrar_qi", False))
        pref = encontros.preferencia_of(game, c.id)
        prox_pref = {"oposto": "mesmo", "mesmo": "todos", "todos": "oposto"}[pref]
        pref_rot = {"oposto": "Sexo oposto", "mesmo": "Mesmo sexo", "todos": "Todos"}[pref]
        acoes.insert(2, {"rotulo": f"Exibir QI opcional: {'sim' if qi_on else 'não'}", "acao": "qi", "valor": not qi_on})
        acoes.insert(3, {"rotulo": f"Preferência afetiva: {pref_rot}", "acao": "pref_afetiva", "valor": prox_pref})
    acoes.append({"rotulo": "Voltar ao título", "acao": "titulo"})
    return _painel("Ajustes", _ic("config"), [
        L("Partida", [("Nome", game.name), ("Semente", str(game.seed)), ("Data", game.date_str()),
                      ("Arquivo", meta.get("arquivo") or "ainda não salvo"),
                      ("Alterações não salvas", "sim" if meta.get("sujo") else "não"),
                      ("Personagens", f"{len(game.characters)} ({sum(1 for x in game.characters.values() if x.alive)} vivos)")]),
        ACOES(acoes)])


def p_noticias(game: Game, c: Character | None, q: dict, meta: dict) -> dict:
    nots = mundo.noticias_recentes(game, 20)
    itens = [
        {"titulo": f"[{'REAL' if n.get('tipo') == 'real' else 'SIMULADA'}] {mes_ano(n['ano'], n['mes'])} · {n['titulo']}",
         "texto": n["texto"],
         "i": ICONE_EVENTO_CLIMA if n.get("tipo") == "simulada" else _ic("panorama")}
        for n in nots
    ]
    blocos = [{"t": "lista", "titulo": "Notícias recentes", "itens": itens}] if itens else [
        T("Nenhuma manchete registrada ainda. Avance o tempo para acompanhar o noticiário econômico e eleitoral.")]
    return _painel("Notícias", _ic("panorama"), blocos)


PAINEIS = {
    "ficha": p_ficha, "escola": p_escola, "bens": p_bens, "relacoes": p_relacoes, "trabalho": p_trabalho,
    "saude": p_saude, "bemestar": p_bemestar, "cognicao": p_mente, "social": p_social, "familia": p_familia, "arvore": p_arvore,
    "biografia": p_biografia, "empresas": p_empresas, "panorama": p_panorama, "impostos": p_impostos,
    "seguro": p_seguro, "noticias": p_noticias, "personagens": p_personagens, "config": p_config,
}
# Painéis que não exigem um personagem do jogador vivo ou existente.
SEM_PERSONAGEM = {"biografia", "empresas", "panorama", "impostos", "noticias", "personagens", "config"}


def painel(game: Game, nome: str, q: dict | None = None, meta: dict | None = None) -> dict:
    if nome not in PAINEIS:
        raise KeyError(nome)
    q, meta = q or {}, meta or {}
    if nome == "ficha":
        c = game.characters.get(int(q.get("id", game.player_id or 0)))
        if c is None:
            raise ValueError("personagem inexistente")
    else:
        c = player_of(game)
        if c is None and nome not in SEM_PERSONAGEM:
            raise ValueError("Nenhum personagem do jogador. Crie um personagem ou uma família.")
    return PAINEIS[nome](game, c, q, meta)
