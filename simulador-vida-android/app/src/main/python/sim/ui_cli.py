"""Interface de texto (CLI). Só apresentação e entrada; regras ficam em engine/factory."""
from __future__ import annotations

import argparse
import os
import random
import re
import sys

from . import carreiras, conhecidos, convivio, economy, educacao_br, encontros, engine, factory, firms, foco, intelecto, livros, macro, mundo, persistence, romance, work
from .models import COGNICAO, MESES, PERSONALIDADE, Game

ROTULOS = {
    "abertura": "Abertura", "conscienciosidade": "Conscienciosidade",
    "extroversao": "Extroversão", "amabilidade": "Amabilidade",
    "neuroticismo": "Neuroticismo", "memoria": "Memória", "atencao": "Atenção",
    "raciocinio_logico": "Raciocínio lógico", "abstracao": "Abstração",
    "criatividade": "Criatividade", "compreensao_verbal": "Compreensão verbal",
    "resolucao_problemas": "Resolução de problemas", "aprendizagem": "Aprendizagem",
}


class Session:
    def __init__(self, game: Game, path: str):
        self.game = game
        self.path = path
        self.dirty = True


def ask(prompt: str) -> str:
    return input(prompt).strip()


def ask_int(prompt: str, lo: int, hi: int, default: int | None = None) -> int:
    while True:
        raw = ask(prompt)
        if raw == "" and default is not None:
            return default
        try:
            v = int(raw)
        except ValueError:
            print(f"Digite um número entre {lo} e {hi}.")
            continue
        if lo <= v <= hi:
            return v
        print(f"Digite um número entre {lo} e {hi}.")


def slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_")
    return s or "partida"


def fmt_event(game: Game, e) -> str:
    c = game.characters.get(e.char_id)
    nome = c.first_name if c else "?"
    return f"[{MESES[e.month - 1][:3]}/{e.year}] {nome}: {e.text}"


def estado_civil(game: Game, c) -> str:
    sexo_f = c.sex == "F"
    if engine.has_active_spouse(game, c):
        return "casada" if sexo_f else "casado"
    if c.spouse_id in game.characters:  # vínculo histórico com cônjuge falecido
        return "viúva" if sexo_f else "viúvo"
    if c.ex_spouse_id in game.characters:
        return "divorciada" if sexo_f else "divorciado"
    return "solteira" if sexo_f else "solteiro"


def show_family_tree(game: Game, c) -> None:
    """Avós, pais, irmãos, cônjuge, filhos e netos (somente leitura)."""
    def nome(x) -> str:
        ref = (game.year, game.month) if x.alive else (x.death_year, x.death_month)
        return f"{x.full_name} ({x.age_at(*ref)}{'' if x.alive else ', falecido(a)'})"

    print(f"\n=== Família de {c.full_name} ===")
    for pai in game.parents_of(c):
        avos = game.parents_of(pai)
        print(f"{'Mãe' if pai.id == c.mother_id else 'Pai'}: {nome(pai)}")
        for a in avos:
            print(f"   {'Avó' if a.id == pai.mother_id else 'Avô'}: {nome(a)}")
    irmaos = sorted({x.id: x for p in game.parents_of(c) for x in game.children_of(p.id) if x.id != c.id}.values(),
                    key=lambda x: x.id)
    if irmaos:
        print("Irmãos: " + ", ".join(nome(x) for x in irmaos))
    conj = game.characters.get(c.spouse_id)
    if conj:
        print(f"Cônjuge: {nome(conj)}")
    filhos = game.children_of(c.id)
    for f in filhos:
        print(f"Filho(a): {nome(f)}")
        for n in game.children_of(f.id):
            print(f"   Neto(a): {nome(n)}")
    if not (game.parents_of(c) or irmaos or conj or filhos):
        print("Sem parentes registrados.")


def show_character(game: Game, c) -> None:
    age = c.age_at(*((c.death_year, c.death_month) if not c.alive else (game.year, game.month)))
    estado = "vivo(a)" if c.alive else f"falecido(a) em {MESES[c.death_month - 1]} de {c.death_year}"
    print(f"\n=== {c.full_name} (id {c.id}) ===")
    print(f"Sexo: {c.sex} | Idade: {age} ({engine.life_stage(age)}) | {estado}")
    print(f"Nascimento: {MESES[c.birth_month - 1]} de {c.birth_year} | Saúde: {c.health:.0f}/100")
    fam = game.families.get(c.family_id)
    if fam:
        print(f"Família: {fam.name}")
    print(f"Escolaridade: {engine.education_label(c)}"
          + (f" | Desempenho no último ano: {c.school_performance}" if (c.in_school or c.in_college) and c.school_performance is not None else ""))
    trabalho = work.work_label(c, game.year, game.month)
    if trabalho:
        print(f"Trabalho: {trabalho}")
        if c.alive and (c.income > 0 or c.wealth != 0):
            print(f"Renda: {economy.fmt_brl(c.income)}/mês | Patrimônio: {economy.fmt_brl(c.wealth)}"
                  + (f" | {_empresa(game, c)}" if c.workplace is not None and not c.retired else ""))
        if c.alive and economy.receiving_unemployment(c, game.year * 12 + game.month):
            ano, mes = divmod(c.unemp_until, 12)   # mês absoluto = ano*12 + mês (1–12)
            if mes == 0:
                ano, mes = ano - 1, 12
            print(f"Seguro-desemprego: {economy.fmt_brl(c.unemp_amount)}/mês (última parcela em {mes:02d}/{ano})")
    print(f"Estado civil: {estado_civil(game, c)}")
    conj = game.characters.get(c.spouse_id)
    if conj:
        print(f"Cônjuge: {conj.full_name}" + ("" if conj.alive else " (falecido(a))"))
    if c.alive and c.pregnant_until is not None:
        print(f"Gestação: parto previsto em {engine._abs_to_str(c.pregnant_until)}")
    if c.leave_until is not None and economy.on_leave(c, game.year * 12 + game.month):
        print(f"Afastada do trabalho até {engine._abs_to_str(c.leave_until)} (licença-maternidade/cuidado do bebê)")
    par = romance.partner_of(game, c)
    if par is not None:
        print(f"Namoro: {par.full_name} (há {romance._meses(game, c)} meses)")
    ex = game.characters.get(c.ex_spouse_id)
    if ex and c.ex_spouse_id != c.spouse_id:
        print(f"Ex-cônjuge: {ex.full_name}" + ("" if ex.alive else " (falecido(a))"))
    amigos = [game.characters[i] for i in game.friend_ids(c.id)]
    if amigos:
        print("Amigos: " + ", ".join(a.first_name + ("" if a.alive else " (falecido(a))") for a in amigos))
    resp = game.characters.get(c.guardian_id) if c.guardian_id is not None else None
    if resp is not None and resp.alive and c.age_at(game.year, game.month) < 18:
        print(f"Guarda: {resp.full_name}")
    pais = [game.characters[i].full_name for i in (c.mother_id, c.father_id) if i in game.characters]
    if pais:
        print("Pais: " + ", ".join(pais))
    filhos = game.children_of(c.id)
    if filhos:
        print("Filhos: " + ", ".join(f.first_name for f in filhos))
    print("Personalidade: " + ", ".join(f"{ROTULOS[k]} {c.personality[k]}" for k in PERSONALIDADE))
    crianca = age < 18
    print("Cognição" + (" (em desenvolvimento)" if crianca else "") + ": "
          + ", ".join(f"{ROTULOS[k]} {c.cognition[k]}" + (f"/{c.cognition_potential[k]}" if crianca and c.cognition_potential else "")
                      for k in COGNICAO))


def _empresa(game: Game, c) -> str:
    f = game.firms.get(c.workplace)
    if f is None:  # modo legado (firms.ATIVO = False): local numérico
        return f"Local de trabalho nº {c.workplace}"
    return f"{f.name} ({f.sector}, {f.size})"


def show_firms(game: Game, limite: int = 15) -> None:
    """Empresas e vagas: totais, vacância e as maiores empresas abertas com seus empregados."""
    v = firms.vacancy_stats(game)
    print(f"\n=== Empresas e vagas — {game.date_str()} ===")
    print(f"Empresas abertas: {v['abertas']} | fechadas: {v['fechadas']}")
    print(f"Vagas: {v['vagas']} (ocupadas {v['ocupadas']}, livres {v['livres']}; vacância {v['vacancia']:.0%})")
    fill = firms.filled(game)
    por_empresa: dict[int, int] = {}
    for (fid, _), n in fill.items():
        por_empresa[fid] = por_empresa.get(fid, 0) + n
    abertas = sorted((f for f in game.firms.values() if f.is_open), key=lambda f: (-sum(f.slots.values()), f.id))
    for f in abertas[:limite]:
        print(f"  {f.name} — {f.sector}, {f.size}: {por_empresa.get(f.id, 0)}/{sum(f.slots.values())} vagas ocupadas")
    if len(abertas) > limite:
        print(f"  ... e mais {len(abertas) - limite} empresa(s).")
    print("(Empresas genéricas e valores ilustrativos; nenhuma empresa real.)")


def show_finances(game: Game, c) -> None:
    """Finanças do domicílio do personagem: quem sustenta quem, renda, custo de vida e saldo mensal."""
    h = economy.household_of(game, c)
    print(f"\n=== Finanças de {c.full_name} ===")
    if h is None:
        print("Sem domicílio (personagem falecido).")
        return
    print(f"Patrimônio pessoal: {economy.fmt_brl(c.wealth)} | Renda pessoal: {economy.fmt_brl(c.income)}/mês")
    print("Domicílio:")
    for a in h["adults"]:
        print(f"  - {a.full_name}: renda {economy.fmt_brl(a.income)}/mês | patrimônio {economy.fmt_brl(a.wealth)}")
    for k in h["kids"]:
        print(f"  - {k.full_name} (dependente)" + (f": renda {economy.fmt_brl(k.income)}/mês" if k.income else ""))
    if h["auxilio"]:
        print(f"Auxílio social (baixa renda por pessoa): {economy.fmt_brl(h['auxilio'])}/mês")
    if h["pensao_recebida"]:
        print(f"Pensão alimentícia recebida: {economy.fmt_brl(h['pensao_recebida'])}/mês")
    if h["pensao_paga"]:
        print(f"Pensão alimentícia paga: {economy.fmt_brl(h['pensao_paga'])}/mês")
    if h["imposto"]:
        print(f"Impostos e previdência (vínculos formais): {economy.fmt_brl(h['imposto'])}/mês")
    saldo = h["income"] - h["imposto"] - h["cost"]
    print(f"Renda total: {economy.fmt_brl(h['income'])}/mês | Custo de vida: {economy.fmt_brl(h['cost'])}/mês | "
          f"Saldo (após impostos): {economy.fmt_brl(saldo)}/mês")
    print("(Valores ilustrativos, em reais correntes; salário mínimo vigente: "
          + economy.fmt_brl(macro.min_wage(game)) + ".)")


def show_economy(game: Game) -> None:
    s = economy.summary(game)
    print(f"\n=== Panorama econômico — {game.date_str()} ===")
    print(f"Clima econômico: {s['clima']} (índice {s['indice_ciclo']:+.2f})")
    print(f"Inflação do ano: {s['inflacao_anual']:.1%} (ano anterior: {s['inflacao_ano_anterior']:.1%}) | "
          f"Índice de preços: {s['indice_precos']:.3f} | Salário mínimo: {economy.fmt_brl(s['salario_minimo'])} "
          f"({economy.fmt_brl(s['salario_minimo_real'])} em valores do início)")
    print(f"Estado — ano anterior: receita {economy.fmt_brl(s['receita_estado_ano_anterior'])}, despesa "
          f"{economy.fmt_brl(s['despesa_estado_ano_anterior'])} | ano corrente: receita {economy.fmt_brl(s['receita_estado'])}, "
          f"despesa {economy.fmt_brl(s['despesa_estado'])} | caixa acumulado: {economy.fmt_brl(s['tesouro'])}")
    print(f"População viva: {s['populacao']} (adultos: {s['adultos']})")
    print(f"Renda média: {economy.fmt_brl(s['renda_media'])} | mediana: {economy.fmt_brl(s['renda_mediana'])} | Gini da renda: {s['gini_renda']:.2f}")
    print(f"Patrimônio total: {economy.fmt_brl(s['patrimonio_total'])} | mediano: {economy.fmt_brl(s['patrimonio_mediano'])}")
    print(f"Empregados: {s['empregados']} (informais: {s['informais']}) | Procurando trabalho: {s['procurando']} "
          f"| Com seguro-desemprego: {s['segurados']}")
    print(f"Empresas abertas: {s['empresas_abertas']} (fechadas: {s['empresas_fechadas']}) | "
          f"Vagas livres: {s['vagas_livres']}/{s['vagas']} ({s['vacancia']:.0%})")
    for lvl, v in s["renda_por_escolaridade"].items():
        print(f"  Renda média — {work.NIVEIS[lvl]}: {economy.fmt_brl(v)}")


def list_characters(game: Game) -> None:
    print(f"\nPersonagens ({game.date_str()}):")
    for c in sorted(game.characters.values(), key=lambda x: x.id):
        ref = (game.year, game.month) if c.alive else (c.death_year, c.death_month)
        marca = "*" if c.id == game.player_id else " "
        st = "vivo" if c.alive else "falecido"
        print(f" {marca} {c.id:>3}  {c.full_name:<28} {c.age_at(*ref):>3} anos  {st}")
    print(" (* = personagem do jogador)")


def do_advance(s: Session, n: int) -> None:
    eventos = engine.advance_months(s.game, n)
    s.dirty = True
    print(f"\n=== Relatório — agora é {s.game.date_str()} ===")
    if not eventos:
        print("Nada relevante aconteceu.")
    # Amizades de outros personagens são muitas: no relatório só aparecem as do jogador.
    eventos = [e for e in eventos if e.category not in ("amizade", "escola", "trabalho", "heranca") or e.char_id == s.game.player_id]
    for e in eventos:
        print(" - " + fmt_event(s.game, e))
    p = s.game.characters.get(s.game.player_id)
    if p is not None and not p.alive:
        print("\nSeu personagem faleceu. Use 'Trocar personagem' para continuar com outro.")


def do_biography(s: Session) -> None:
    g = s.game
    p = g.characters.get(g.player_id)
    if p is None:
        print("Nenhum personagem do jogador definido.")
        return
    cat = ask("Categoria (Enter = todas; ex.: aniversario, morte, nascimento, nascimento_filho, casamento, divorcio, amizade, escola, trabalho, heranca): ") or None
    de = ask("Ano inicial (Enter = sem filtro): ")
    ate = ask("Ano final (Enter = sem filtro): ")
    try:
        fy = int(de) if de else None
        ty = int(ate) if ate else None
    except ValueError:
        print("Ano inválido.")
        return
    evs = g.events_for(p.id, cat, fy, ty)
    print(f"\n=== Biografia de {p.full_name} ===")
    if not evs:
        print("Nenhum registro para esse filtro.")
    for e in evs:
        print(f"[{MESES[e.month - 1][:3]}/{e.year}] ({e.category}) {e.text}")


def create_character_flow(s: Session) -> None:
    g = s.game
    idade = ask_int(f"Idade (0-{factory.IDADE_MAX}): ", 0, factory.IDADE_MAX)
    sexo = ask("Sexo F/M (Enter = aleatório): ").upper() or None
    if sexo not in (None, "F", "M"):
        print("Sexo inválido.")
        return
    nome = ask("Nome (Enter = aleatório): ") or None
    sobrenome = ask("Sobrenome (Enter = aleatório): ") or None
    c = factory.create_character(g, idade, sexo, nome, sobrenome)
    if g.player_id is None:
        g.player_id = c.id
    s.dirty = True
    print(f"Criado: {c.full_name} (id {c.id}).")


def create_family_flow(s: Session) -> None:
    g = s.game
    sobrenome = ask("Sobrenome da família (Enter = aleatório): ") or None
    n = ask_int("Número de filhos (0-10, Enter = 2): ", 0, 10, default=2)
    r = factory.create_family(g, sobrenome, n)
    s.dirty = True
    print(f"Criada a {r['family'].name}: {r['mother'].full_name}, {r['father'].full_name} "
          f"e {len(r['children'])} filho(s).")


def switch_character(s: Session) -> None:
    g = s.game
    list_characters(g)
    cid = ask_int("Id do novo personagem do jogador: ", 1, max(g.characters) if g.characters else 1)
    if cid not in g.characters:
        print("Id inexistente.")
        return
    g.player_id = cid
    s.dirty = True
    print(f"Agora você joga com {g.characters[cid].full_name}.")


def save(s: Session) -> None:
    persistence.save_game(s.game, s.path)
    s.dirty = False
    print(f"Partida salva em {s.path}")


MENU = """
--- {data} | Jogador: {jogador} ---
 1) Ver personagem atual      6) Avançar 1 mês
 2) Listar personagens        7) Avançar 6 meses
 3) Trocar personagem         8) Avançar 1 ano
 4) Criar personagem          9) Biografia
 5) Criar família            10) Salvar
11) Família do personagem    12) Finanças
13) Panorama econômico      14) Empresas e vagas
15) Foco do período         16) Livros (129 obras)
17) Amigos e encontros      18) ENEM, faculdade e pós
19) Concursos e política    20) Cidade, imóveis e banco
21) Notícias                22) Estudar, redação e cultura
 0) Sair"""


def flow_foco(s: Session) -> None:
    g = s.game
    v = foco.view(g)
    print(f"Foco atual: {v['atual']} (área: {v['area']})")
    for i, op in enumerate(v["opcoes"], 1):
        print(f" {i}) {op['rotulo']}")
    idx = ask_int("Escolha (0 cancela): ", 0, len(v["opcoes"]), 0)
    if idx == 0:
        return
    escolhido = v["opcoes"][idx - 1]["id"]
    area = None
    if escolhido == "estudar":
        for j, ar in enumerate(v["areas"], 1):
            print(f" {j}) {ar['rotulo']}")
        aidx = ask_int("Área de estudo: ", 1, len(v["areas"]), 1)
        area = v["areas"][aidx - 1]["id"]
    try:
        foco.definir(g, escolhido, area)
        s.dirty = True
        print(f"Foco alterado para {escolhido}.")
    except ValueError as exc:
        print(exc)


def flow_livros(s: Session) -> None:
    g = s.game
    termo = ask("Buscar livro (Enter = listar não lidos, 'lidos' = ver lidos): ")
    if termo.lower() == "lidos":
        v = livros.view(g)
        if not v["lidos"]:
            print("Nenhum livro concluído ainda.")
            return
        for i, item in enumerate(v["lidos"], 1):
            print(f" {i}) {item['titulo']} — {item['autor']} ({item['paginas']} págs, {', '.join(item['conhecimento_rotulos'])})")
        return
    v = livros.view(g, busca=termo)
    print(f"Capacidade de leitura este mês: {v['paginas_mes_restantes']}/{v['paginas_mes_total']} págs | Lidos: {v['total_lidos']}/{v['total_catalogo']}")
    if not v["disponivel"]:
        print(v["motivo"])
        return
    disponiveis = [x for x in v["nao_lidos"] if x["pode"]]
    if not disponiveis:
        print("Nenhum livro disponível para leitura com esse filtro.")
        return
    for i, item in enumerate(disponiveis[:20], 1):
        prog_txt = f"{item['progresso']}/{item['paginas']} págs" if item["progresso"] > 0 else f"{item['paginas']} págs"
        print(f" {i}) {item['titulo']} — {item['autor']} ({prog_txt}, {', '.join(item['conhecimento_rotulos'])})")
    idx = ask_int("Ler qual (0 cancela)? ", 0, min(20, len(disponiveis)), 0)
    if idx == 0:
        return
    try:
        r = livros.ler(g, disponiveis[idx - 1]["id"])
        s.dirty = True
        if r["concluido"]:
            print(f"Leu '{r['titulo']}' ({r['genero']}, {r['total_paginas']} págs).")
        else:
            print(f"Leu {r['paginas_lidas_agora']} págs de '{r['titulo']}' ({r['progresso']}/{r['total_paginas']}).")
    except ValueError as exc:
        print(exc)


def flow_social(s: Session) -> None:
    g = s.game
    print("1) Conhecer alguém  2) Amigos  3) Encontros")
    op = ask("> ")
    try:
        if op == "1":
            locs = conhecidos.locais(g)
            for i, l in enumerate(locs, 1):
                print(f" {i}) {l['rotulo']}")
            idx = ask_int("Onde? ", 1, len(locs), 1)
            r = conhecidos.conhecer(g, locs[idx - 1]["id"])
            s.dirty = True
            print(f"Conheceu {r['nome']}, {r['idade']} anos.")
        elif op == "2":
            ams = convivio.amigos(g)
            for i, a in enumerate(ams, 1):
                print(f" {i}) {a['nome']} ({a['idade']}a)")
            if not ams:
                print("Sem amigos.")
                return
            idx = ask_int("Amigo (0 sai): ", 0, len(ams), 0)
            if idx:
                r = convivio.conversar(g, ams[idx - 1]["id"])
                s.dirty = True
                print(f"Conversou com {r['nome']}.")
        elif op == "3":
            ev = encontros.view(g)
            if ev.get("namoro"):
                n = ev["namoro"]
                print(f"Namora {n['nome']} ({n['meses']}m). 1) Pedir em casamento  2) Terminar")
                sub = ask("> ")
                if sub == "1":
                    r = encontros.pedir_em_casamento(g)
                    s.dirty = True
                    print("Aceitou!" if r["aceitou"] else "Ainda não.")
                elif sub == "2":
                    r = encontros.terminar(g)
                    s.dirty = True
                    print(f"Terminou com {r['nome']}.")
            elif ev.get("disponivel"):
                for i, c in enumerate(ev["candidatos"], 1):
                    print(f" {i}) {c['nome']}, {c['idade']} anos")
                idx = ask_int("Escolher (0 sai): ", 0, len(ev["candidatos"]), 0)
                if idx:
                    r = encontros.escolher(g, ev["candidatos"][idx - 1]["slot"])
                    s.dirty = True
                    print(f"Começou a namorar {r['nome']}.")
            else:
                print(ev.get("motivo", "Indisponível."))
    except ValueError as exc:
        print(exc)


def flow_educacao_br(s: Session) -> None:
    g = s.game
    print("1) Fazer ENEM  2) Ingressar em universidade  3) Iniciação Científica  4) Pós-graduação")
    op = ask("> ")
    try:
        if op == "1":
            r = educacao_br.fazer_enem(g)
            s.dirty = True
            print(f"ENEM: média {r['media']} (Redação {r['redacao']}).")
        elif op == "2":
            for i, u in enumerate(educacao_br.UNIVERSIDADES, 1):
                print(f" {i}) {u[0]} - {u[1]} ({u[4]}, corte {u[5]})")
            ui = ask_int("Universidade: ", 1, len(educacao_br.UNIVERSIDADES))
            for i, c in enumerate(educacao_br.CURSOS, 1):
                print(f" {i}) {c[1]}")
            ci = ask_int("Curso: ", 1, len(educacao_br.CURSOS))
            mod = ask("Modalidade (sisu/prouni/fies/vestibular): ") or "sisu"
            uni_escolhida = educacao_br.UNIVERSIDADES[ui - 1]
            cid_atual = mundo.cidade_of(g, g.player_id)[0]
            mudar = False
            if uni_escolhida[3] != "BR" and cid_atual != uni_escolhida[2]:
                mudar = ask(f"A {uni_escolhida[0]} fica em {uni_escolhida[3]}. Mudar-se para lá ao ingressar? (s/n): ").lower() == "s"
            r = educacao_br.ingressar(g, uni_escolhida[0], educacao_br.CURSOS[ci - 1][0], mod, mudar_cidade=mudar)
            s.dirty = True
            print(f"Ingressou em {r['curso']} na {r['universidade']} ({r['modalidade']}).")
        elif op == "3":
            r = educacao_br.iniciacao_cientifica(g)
            s.dirty = True
            print(f"IC iniciada por {r['meses']} meses.")
        elif op == "4":
            niv = ask("Nível (especializacao/mestrado/doutorado): ")
            r = educacao_br.iniciar_pos(g, niv)
            s.dirty = True
            print(f"Iniciou {r['nivel']}.")
    except ValueError as exc:
        print(exc)


def flow_carreiras(s: Session) -> None:
    g = s.game
    print("1) Prestar concurso  2) Abrir empresa  3) Encerrar empresa  4) Filiar partido  5) Campanha  6) Concorrer")
    op = ask("> ")
    try:
        if op == "1":
            for i, c in enumerate(carreiras.CONCURSOS, 1):
                print(f" {i}) {c[1]} (corte {c[4]})")
            idx = ask_int("Concurso: ", 1, len(carreiras.CONCURSOS))
            r = carreiras.prestar_concurso(g, carreiras.CONCURSOS[idx - 1][0])
            s.dirty = True
            print("Aprovado!" if r["aprovado"] else f"Reprovado ({r['nota']} < {r['corte']}).")
        elif op == "2":
            setores = sorted(firms.SETORES)
            for i, st in enumerate(setores, 1):
                print(f" {i}) {st}")
            si = ask_int("Setor: ", 1, len(setores))
            porte = ask("Porte (micro/pequena): ") or "micro"
            r = carreiras.abrir_empresa(g, setores[si - 1], porte)
            s.dirty = True
            print(f"Abriu {r['nome']}.")
        elif op == "3":
            r = carreiras.encerrar_empresa(g)
            s.dirty = True
            print(f"Encerrou {r['nome']}.")
        elif op == "4":
            for i, pt in enumerate(carreiras.PARTIDOS, 1):
                print(f" {i}) {pt[1]}")
            pi = ask_int("Partido: ", 1, len(carreiras.PARTIDOS))
            r = carreiras.filiar(g, carreiras.PARTIDOS[pi - 1][0])
            s.dirty = True
            print(f"Filiado ao {r['partido']}.")
        elif op == "5":
            r = carreiras.fazer_campanha(g)
            s.dirty = True
            print(f"Influência: {r['influencia']}.")
        elif op == "6":
            for i, cg in enumerate(carreiras.CARGOS_POLITICOS, 1):
                print(f" {i}) {cg[1]} (≥{cg[2]} anos)")
            ci = ask_int("Cargo: ", 1, len(carreiras.CARGOS_POLITICOS))
            r = carreiras.concorrer(g, carreiras.CARGOS_POLITICOS[ci - 1][0])
            s.dirty = True
            print("Eleito!" if r["eleito"] else "Não eleito.")
    except ValueError as exc:
        print(exc)


def flow_mundo(s: Session) -> None:
    g = s.game
    print("1) Mudar de cidade  2) Comprar imóvel  3) Comprar veículo  4) Investir  5) Resgatar  6) Empréstimo  7) Quitar")
    op = ask("> ")
    try:
        if op == "1":
            for i, c in enumerate(mundo.CIDADES, 1):
                print(f" {i}) {c[1]}/{c[2]} (custo {c[3]:.2f}x)")
            ci = ask_int("Cidade: ", 1, len(mundo.CIDADES))
            r = mundo.mudar_cidade(g, mundo.CIDADES[ci - 1][0])
            s.dirty = True
            print(f"Mudou-se para {r['cidade']}.")
        elif op == "2":
            for i, im in enumerate(mundo.IMOVEIS, 1):
                print(f" {i}) {im[1]}")
            ii = ask_int("Imóvel: ", 1, len(mundo.IMOVEIS))
            alugar = ask("Alugar para renda? (s/n): ").lower() == "s"
            r = mundo.comprar_imovel(g, mundo.IMOVEIS[ii - 1][0], alugar)
            s.dirty = True
            print(f"Comprou {r['nome']}.")
        elif op == "3":
            for i, v in enumerate(mundo.VEICULOS, 1):
                print(f" {i}) {v[1]}")
            vi = ask_int("Veículo: ", 1, len(mundo.VEICULOS))
            r = mundo.comprar_veiculo(g, mundo.VEICULOS[vi - 1][0])
            s.dirty = True
            print(f"Comprou {r['nome']}.")
        elif op == "4":
            mod = ask("Modalidade (poupanca/tesouro/acoes): ")
            val = float(ask("Valor: "))
            r = mundo.investir(g, mod, val)
            s.dirty = True
            print(f"Saldo em {r['tipo']}: {economy.fmt_brl(r['saldo'])}.")
        elif op == "5":
            mod = ask("Modalidade (poupanca/tesouro/acoes): ")
            val = float(ask("Valor: "))
            r = mundo.resgatar(g, mod, val)
            s.dirty = True
            print(f"Saldo em {r['tipo']}: {economy.fmt_brl(r['saldo'])}.")
        elif op == "6":
            val = float(ask("Valor do empréstimo: "))
            r = mundo.pedir_emprestimo(g, val)
            s.dirty = True
            print(f"Dívida: {economy.fmt_brl(r['divida'])}.")
        elif op == "7":
            val = float(ask("Valor para quitar: "))
            r = mundo.quitar_emprestimo(g, val)
            s.dirty = True
            print(f"Dívida restante: {economy.fmt_brl(r['divida'])}.")
    except ValueError as exc:
        print(exc)




def flow_intelecto(s: Session) -> None:
    g = s.game
    iv = intelecto.view(g)
    if not iv["disponivel"]:
        print("Nenhum personagem vivo do jogador.")
        return
    print(f"1) Estudar ({iv['estudo_restante']}/{iv['estudo_max']})  "
          f"2) Redação/Ensaio ({iv['ensaio_restante']}/{iv['ensaio_max']})  "
          f"3) Ler artigo ({iv['artigo_restante']}/{iv['artigo_max']})  "
          f"4) Assistir filme/doc ({iv['filme_restante']}/{iv['filme_max']})")
    op = ask("> ")
    try:
        if op == "1":
            for i, m in enumerate(iv["modos_estudo"], 1):
                print(f" {i}) {m['rotulo']} ({m['desc']})")
            mi = ask_int("Modo: ", 1, len(iv["modos_estudo"]))
            modo = iv["modos_estudo"][mi - 1]["id"]
            area = None
            if modo == "tema":
                for i, a in enumerate(iv["areas_conhecimento"], 1):
                    print(f" {i}) {a['rotulo']}")
                ai = ask_int("Área: ", 1, len(iv["areas_conhecimento"]))
                area = iv["areas_conhecimento"][ai - 1]["id"]
            r = intelecto.estudar(g, modo, area)
            s.dirty = True
            print(r["mensagem"])
        elif op == "2":
            tipo = "ensaio" if ask("Tipo (1=Redação, 2=Ensaio crítico): ") == "2" else "redacao"
            for i, t in enumerate(iv["temas_ensaio"], 1):
                print(f" {i}) {t['titulo']} [{t['area_nome']}]")
            ti = ask_int("Tema: ", 1, len(iv["temas_ensaio"]))
            r = intelecto.escrever_ensaio(g, iv["temas_ensaio"][ti - 1]["id"], tipo)
            s.dirty = True
            print(f"Concluído ({r['nota']}): {r['tema']}.")
        elif op == "3":
            for i, a in enumerate(iv["areas_conhecimento"], 1):
                print(f" {i}) {a['rotulo']}")
            ai = ask_int("Assunto: ", 1, len(iv["areas_conhecimento"]))
            r = intelecto.ler_artigo(g, iv["areas_conhecimento"][ai - 1]["id"])
            s.dirty = True
            print(f"Leu '{r['titulo']}' ({r['assunto']}).")
        elif op == "4":
            for i, f in enumerate(iv["filmes"], 1):
                print(f" {i}) {f['titulo']} ({f['genero']}, ≥{f['idade_min']}a)")
            fi = ask_int("Filme: ", 1, len(iv["filmes"]))
            r = intelecto.assistir_filme(g, iv["filmes"][fi - 1]["id"])
            s.dirty = True
            print(f"Assistiu a '{r['titulo']}'.")
    except ValueError as exc:
        print(exc)

def game_loop(s: Session) -> None:
    while True:
        g = s.game
        p = g.characters.get(g.player_id)
        print(MENU.format(data=g.date_str(), jogador=p.full_name if p else "(nenhum)"))
        op = ask("> ")
        if op == "1":
            if p:
                show_character(g, p)
            else:
                print("Nenhum personagem do jogador. Crie um personagem ou uma família.")
        elif op == "2":
            list_characters(g)
        elif op == "3":
            switch_character(s)
        elif op == "4":
            create_character_flow(s)
        elif op == "5":
            create_family_flow(s)
        elif op in ("6", "7", "8"):
            if not g.characters:
                print("Crie um personagem ou uma família antes de avançar o tempo.")
            else:
                do_advance(s, {"6": 1, "7": 6, "8": 12}[op])
        elif op == "9":
            do_biography(s)
        elif op == "10":
            save(s)
        elif op == "11":
            if p:
                show_family_tree(g, p)
            else:
                print("Nenhum personagem do jogador.")
        elif op == "12":
            if p:
                show_finances(g, p)
            else:
                print("Nenhum personagem do jogador.")
        elif op == "13":
            show_economy(g)
        elif op == "14":
            show_firms(g)
        elif op == "15":
            flow_foco(s)
        elif op == "16":
            flow_livros(s)
        elif op == "17":
            flow_social(s)
        elif op == "18":
            flow_educacao_br(s)
        elif op == "19":
            flow_carreiras(s)
        elif op == "20":
            flow_mundo(s)
        elif op == "21":
            nots = mundo.noticias_recentes(g, 10)
            if not nots:
                print("Nenhuma notícia registrada ainda.")
            for n in nots:
                print(f"[{n['mes']:02d}/{n['ano']}] {n['titulo']}: {n['texto']}")
        elif op == "22":
            flow_intelecto(s)
        elif op == "0":
            if s.dirty and ask("Há alterações não salvas. Salvar antes de sair? (s/n): ").lower() == "s":
                save(s)
            return
        else:
            print("Opção inválida.")


def new_game_flow(saves_dir: str) -> Session | None:
    nome = ask("Nome da partida: ") or "partida"
    path = os.path.join(saves_dir, slug(nome) + ".db")
    if os.path.exists(path) and ask("Já existe um save com esse nome. Sobrescrever? (s/n): ").lower() != "s":
        return None
    seed_raw = ask("Semente (Enter = aleatória): ")
    seed = int(seed_raw) if seed_raw.lstrip("-").isdigit() else random.randrange(1, 2**31)
    s = Session(factory.new_game(nome, seed), path)
    print(f"Partida '{nome}' criada ({s.game.date_str()}, semente {seed}).")
    print("Como começar? 1) Um personagem  2) Uma família")
    if ask("> ") == "2":
        create_family_flow(s)
    else:
        create_character_flow(s)
    return s


def load_flow(saves_dir: str) -> Session | None:
    saves = sorted(f for f in os.listdir(saves_dir) if f.endswith(".db")) if os.path.isdir(saves_dir) else []
    if not saves:
        print("Nenhum save encontrado.")
        return None
    for i, f in enumerate(saves, 1):
        print(f" {i}) {f}")
    idx = ask_int("Número do save (0 = cancelar): ", 0, len(saves))
    if idx == 0:
        return None
    path = os.path.join(saves_dir, saves[idx - 1])
    try:
        game = persistence.load_game(path)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Não foi possível carregar: {exc}")
        return None
    s = Session(game, path)
    s.dirty = False
    print(f"Partida '{game.name}' carregada ({game.date_str()}).")
    return s


def main(argv: list[str] | None = None) -> int:
    default_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "saves")
    ap = argparse.ArgumentParser(description="Simulador de Vida Brasileiro")
    ap.add_argument("--saves-dir", default=default_dir, help="pasta dos saves")
    args = ap.parse_args(argv)
    try:
        while True:
            print("\n=== SIMULADOR DE VIDA BRASILEIRO ===\n 1) Novo jogo\n 2) Carregar jogo\n 0) Sair")
            op = ask("> ")
            if op == "0":
                return 0
            s = new_game_flow(args.saves_dir) if op == "1" else load_flow(args.saves_dir) if op == "2" else None
            if op not in ("1", "2"):
                print("Opção inválida.")
            if s is not None:
                game_loop(s)
                return 0
    except EOFError:
        print("\nEntrada encerrada.")
        return 0
    except KeyboardInterrupt:
        print("\nInterrompido.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
