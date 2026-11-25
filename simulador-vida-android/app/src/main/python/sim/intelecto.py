"""Formação intelectual ativa (v0.18.0): estudo dirigido, redações, ensaios, artigos e filmes/documentários.

Todas as atividades usam `engine.treinar_cognicao(..., elevar_potencial=True)` para que o jogador possa
desenvolver compreensão verbal e demais aptidões sem travar no potencial sorteado ao nascer, e nunca
consomem `game.rng` (mantendo o determinismo demográfico/econômico intacto).
"""
from __future__ import annotations

import random

from . import engine
from .models import Game

AREAS_CONHECIMENTO = [
    ("linguagem", "Linguagens e Literatura", "compreensao_verbal"),
    ("humanas", "História e Sociedade", "memoria"),
    ("filosofia", "Filosofia e Pensamento Crítico", "abstracao"),
    ("economia", "Economia e Finanças", "raciocinio_logico"),
    ("direito", "Política e Direito", "resolucao_problemas"),
    ("ciencias", "Ciências e Tecnologia", "aprendizagem"),
    ("psicologia", "Psicologia e Comportamento", "atencao"),
    ("artes", "Artes e Cultura", "criatividade"),
]
AREAS_POR_ID = {x[0]: x for x in AREAS_CONHECIMENTO}

MODOS_ESTUDO = [
    ("escola", "Estudar para escola / faculdade", 6, "Melhora o rendimento escolar/acadêmico do ano e aprendizagem."),
    ("enem", "Fazer simulado ENEM / vestibular", 15, "Prepara diretamente para o ENEM e amplia a compreensão verbal e lógica."),
    ("concurso", "Estudar para concurso público", 18, "Aumenta a nota em concursos públicos e o raciocínio aplicado."),
    ("tema", "Estudo autônomo aprofundado", 8, "Aprofunda uma área de conhecimento específica e sua habilidade cognitiva."),
]
MODOS_POR_ID = {x[0]: x for x in MODOS_ESTUDO}

TEMAS_ENSAIO = [
    ("desigualdade", "Desigualdade social e acesso à educação no Brasil", "humanas", "compreensao_verbal"),
    ("tecnologia", "Inteligência artificial, trabalho e privacidade digital", "ciencias", "abstracao"),
    ("meio_ambiente", "Crise climática, Amazônia e transição energética", "ciencias", "resolucao_problemas"),
    ("saude_publica", "Desafios do SUS e saúde mental na juventude", "psicologia", "aprendizagem"),
    ("democracia", "Participação cidadã, instituições e desinformação", "direito", "compreensao_verbal"),
    ("urbanizacao", "Mobilidade urbana e direito à cidade", "humanas", "resolucao_problemas"),
    ("economia", "Inflação, crédito e desenvolvimento sustentável", "economia", "raciocinio_logico"),
    ("cultura", "Valorização da cultura brasileira e patrimônio histórico", "artes", "criatividade"),
    ("etica_ciencia", "Limites éticos da ciência e biotecnologia", "filosofia", "abstracao"),
    ("trabalho", "Futuro das profissões e equilíbrio entre trabalho e vida", "economia", "aprendizagem"),
]
TEMAS_POR_ID = {x[0]: x for x in TEMAS_ENSAIO}

ARTIGOS_CATALOGO = {
    "linguagem": [
        "A oralidade brasileira na prosa contemporânea",
        "Como a leitura frequente amplia a compreensão textual",
        "Machado de Assis e a ironia na literatura nacional",
        "Argumentação e coesão em textos dissertativos",
    ],
    "humanas": [
        "Urbanização brasileira no século XX: causas e efeitos",
        "Formação regional e diversidade cultural do Brasil",
        "O papel das universidades públicas no desenvolvimento nacional",
        "Movimentos sociais e conquistas de direitos no país",
    ],
    "filosofia": [
        "Ética pública e responsabilidade coletiva",
        "Método científico e pensamento crítico na era da informação",
        "O conceito de justiça de Aristóteles ao século XXI",
        "Como evitar falácias lógicas no debate cotidiano",
    ],
    "economia": [
        "Juros, inflação e poder de compra das famílias",
        "Educação financeira e reserva de emergência na prática",
        "Produtividade, indústria e inovação no Brasil",
        "Renda fixa, bolsa e diversificação de patrimônio",
    ],
    "direito": [
        "Direitos fundamentais na Constituição de 1988",
        "Separação dos Poderes e funcionamento dos municípios",
        "Direito do consumidor e contratos digitais",
        "Políticas públicas de acesso à justiça",
    ],
    "ciencias": [
        "Energia renovável e matriz elétrica brasileira",
        "Neuroplasticidade: como o cérebro aprende em qualquer idade",
        "Fundamentos de algoritmos e computação moderna",
        "Biotecnologia e avanços na medicina preventiva",
    ],
    "psicologia": [
        "Hábitos de foco profundo e atenção sustentada",
        "Gestão emocional diante de provas e pressão profissional",
        "Sono, memória e consolidação do aprendizado",
        "Empatia, escuta ativa e vínculos duradouros",
    ],
    "artes": [
        "O modernismo brasileiro e a reinvenção estética",
        "Cinema nacional contemporâneo em festivais internacionais",
        "Arquitetura modernista e espaços urbanos",
        "Música popular brasileira como crônica social",
    ],
}

FILMES = [
    ("o_menino_e_o_mundo", "O Menino e o Mundo", "Alê Abreu · 2013", "animação", 5, "artes", "criatividade", "abstracao", "abertura"),
    ("viagem_chihiro", "A Viagem de Chihiro", "Hayao Miyazaki · 2001", "animação", 6, "artes", "criatividade", "atencao", "abertura"),
    ("auto_compadecida", "O Auto da Compadecida", "Guel Arraes · 2000", "comédia dramática", 10, "linguagem", "compreensao_verbal", "criatividade", "extroversao"),
    ("central_brasil", "Central do Brasil", "Walter Salles · 1998", "drama", 12, "humanas", "compreensao_verbal", "memoria", "amabilidade"),
    ("ilha_flores", "Ilha das Flores", "Jorge Furtado · 1989", "documentário", 12, "economia", "abstracao", "resolucao_problemas", "abertura"),
    ("tempos_modernos", "Tempos Modernos", "Charlie Chaplin · 1936", "clássico", 10, "humanas", "abstracao", "criatividade", "abertura"),
    ("cosmos_serie", "Cosmos (Documentário Científico)", "Carl Sagan · 1980", "documentário", 10, "ciencias", "aprendizagem", "abstracao", "abertura"),
    ("interestelar", "Interestelar", "Christopher Nolan · 2014", "ficção científica", 12, "ciencias", "raciocinio_logico", "abstracao", "abertura"),
    ("doze_homens", "12 Homens e uma Sentença", "Sidney Lumet · 1957", "drama jurídico", 13, "direito", "resolucao_problemas", "compreensao_verbal", "conscienciosidade"),
    ("que_horas_volta", "Que Horas Ela Volta?", "Anna Muylaert · 2015", "drama social", 13, "humanas", "compreensao_verbal", "abstracao", "amabilidade"),
    ("dilema_redes", "O Dilema das Redes", "Jeff Orlowski · 2020", "documentário", 12, "psicologia", "atencao", "resolucao_problemas", "conscienciosidade"),
    ("cabra_marcado", "Cabra Marcado para Morrer", "Eduardo Coutinho · 1984", "documentário", 14, "humanas", "memoria", "compreensao_verbal", "abertura"),
    ("cidade_de_deus", "Cidade de Deus", "Fernando Meirelles · 2002", "drama", 16, "humanas", "abstracao", "memoria", "abertura"),
    ("parasita", "Parasita", "Bong Joon-ho · 2019", "drama / sátira", 15, "economia", "abstracao", "resolucao_problemas", "abertura"),
    ("bacurau", "Bacurau", "Kleber Mendonça Filho · 2019", "ficção / crítica", 16, "direito", "criatividade", "abstracao", "abertura"),
    ("odisseia_2001", "2001: Uma Odisseia no Espaço", "Stanley Kubrick · 1968", "ficção científica", 14, "filosofia", "abstracao", "criatividade", "abertura"),
]
FILMES_POR_ID = {f[0]: f for f in FILMES}

LIMITE_ESTUDO_MES = 3
LIMITE_ENSAIO_MES = 2
LIMITE_ARTIGO_MES = 3
LIMITE_FILME_MES = 2
LIMITE_IDIOMA_MES = 2
LIMITE_PESQUISA_MES = 1

# 16 Áreas Enciclopédicas do Prompt-Mestre (§4.3) com 3 subdisciplinas cada, mapeadas às 8 raízes.
# (id_disc, nome, area_raiz, subdisciplinas: [(sub_id, nome_sub), ...])
ENCICLOPEDIA = [
    ("filosofia_d", "Filosofia", "filosofia", [("etica", "Ética e Filosofia Moral"), ("epistemologia", "Epistemologia"), ("logica_fil", "Lógica Filosófica")]),
    ("ciencias_sociais", "Ciências Sociais", "humanas", [("sociologia", "Sociologia Brasileira"), ("antropologia", "Antropologia"), ("ciencia_politica", "Ciência Política")]),
    ("historia", "História", "humanas", [("hist_brasil", "História do Brasil"), ("hist_geral", "História Geral"), ("hist_econ", "História Econômica")]),
    ("economia_d", "Economia", "economia", [("macroeconomia", "Macroeconomia"), ("microeconomia", "Microeconomia"), ("financas_pub", "Finanças Públicas")]),
    ("direito_d", "Direito", "direito", [("constitucional", "Direito Constitucional"), ("civil_trab", "Direito Civil e do Trabalho"), ("penal_pub", "Direito Administrativo e Penal")]),
    ("matematica", "Matemática", "economia", [("algebra", "Álgebra e Funções"), ("calculo", "Cálculo Diferencial"), ("estatistica", "Probabilidade e Estatística")]),
    ("fisica", "Física", "ciencias", [("mecanica", "Mecânica Clássica"), ("termo_eletro", "Termodinâmica e Eletromagnetismo"), ("fisica_mod", "Física Moderna")]),
    ("quimica", "Química", "ciencias", [("quim_geral", "Química Geral e Inorgânica"), ("quim_org", "Química Orgânica"), ("fisico_quim", "Físico-Química")]),
    ("biologia", "Biologia", "ciencias", [("genetica", "Genética e Biologia Molecular"), ("ecologia", "Ecologia e Biodiversidade"), ("fisiologia", "Fisiologia Humana")]),
    ("literatura", "Literatura", "linguagem", [("lit_br", "Literatura Brasileira"), ("lit_univ", "Literatura Universal"), ("teoria_lit", "Teoria Literária")]),
    ("linguistica", "Linguística", "linguagem", [("gramatica", "Gramática e Sintaxe"), ("semantica", "Semântica e Pragmática"), ("retorica", "Retórica e Argumentação")]),
    ("psicologia_d", "Psicologia", "psicologia", [("cognitiva", "Psicologia Cognitiva"), ("desenvolvimento", "Psicologia do Desenvolvimento"), ("social_psi", "Psicologia Social")]),
    ("geografia", "Geografia", "humanas", [("geopolitica", "Geopolítica e Território"), ("urbanismo", "Geografia Urbana"), ("geofisica", "Climatologia e Meio Ambiente")]),
    ("artes_d", "Artes", "artes", [("artes_visuais", "Artes Visuais e Arquitetura"), ("musica", "Música e Musicologia"), ("cinema_teatro", "Cinema e Dramaturgia")]),
    ("tecnologia", "Tecnologia", "ciencias", [("programacao", "Algoritmos e Programação"), ("dados_ia", "Ciência de Dados e IA"), ("redes_seg", "Sistemas e Segurança Digital")]),
    ("engenharia", "Engenharia", "economia", [("eng_civil", "Engenharia Civil e Infraestrutura"), ("eng_eletrica", "Engenharia Elétrica e Energia"), ("eng_prod", "Engenharia de Produção")]),
]
SUBDISCIPLINAS_POR_ID = {
    sub_id: (sub_nome, disc_id, disc_nome, raiz)
    for disc_id, disc_nome, raiz, subs in ENCICLOPEDIA
    for sub_id, sub_nome in subs
}

IDIOMAS = [
    ("ingles", "Inglês", "Global / Tecnologia e Negócios"),
    ("espanhol", "Espanhol", "América Latina / Integração Regional"),
    ("frances", "Francês", "Humanidades, Diplomacia e Artes"),
    ("alemao", "Alemão", "Ciência, Filosofia e Engenharia"),
    ("italiano", "Italiano", "Artes, História e Cultura"),
    ("libras", "Libras", "Língua Brasileira de Sinais e Inclusão"),
]
IDIOMAS_POR_ID = {x[0]: x for x in IDIOMAS}


def _jogador(game: Game):
    p = game.characters.get(game.player_id) if game.player_id is not None else None
    return p if p is not None and p.alive else None


def _mes(game: Game) -> int:
    return game.year * 12 + game.month


def dados(game: Game, cid: int) -> dict:
    st = game.intelecto.setdefault(cid, {})
    con = st.setdefault("conhecimentos", {})
    ret = st.setdefault("retencao", {})
    for area_id, _, _ in AREAS_CONHECIMENTO:
        con.setdefault(area_id, 0)
        ret.setdefault(area_id, 100.0 if con.get(area_id, 0) > 0 else 100.0)
    st.setdefault("subdisciplinas", {})
    st.setdefault("idiomas", {})
    st.setdefault("pesquisas", [])
    st.setdefault("progresso_livros", {})
    st.setdefault("paginas_mes", [0, 0])
    st.setdefault("sessoes_mes", [0, 0, 0, 0, 0, 0, 0])
    st.setdefault("ensaios", [])
    st.setdefault("artigos", [])
    st.setdefault("filmes", [])
    st.setdefault("bonus_escola", [0, 0])
    st.setdefault("bonus_enem", [0, 0])
    st.setdefault("bonus_concurso", [0, 0])
    st.setdefault("fila_leitura", [])
    st.setdefault("auto_ler_fila", False)
    return st


def _sessoes_mes(st: dict, mes_abs: int) -> list[int]:
    sm = st.get("sessoes_mes")
    if not isinstance(sm, list) or len(sm) < 5 or sm[0] != mes_abs:
        sm = [mes_abs, 0, 0, 0, 0, 0, 0]
        st["sessoes_mes"] = sm
    while len(sm) < 7:
        sm.append(0)
    return sm


def adicionar_conhecimento(game: Game, cid: int, area_id: str, pontos: int = 1) -> None:
    if area_id not in AREAS_POR_ID or pontos <= 0:
        return
    st = dados(game, cid)
    st["conhecimentos"][area_id] = int(st["conhecimentos"].get(area_id, 0) + pontos)
    st["retencao"][area_id] = 100.0


def _add_bonus_anual(st: dict, chave: str, ano: int, delta: int, teto: int) -> int:
    atual = st.get(chave)
    val = int(atual[1]) if isinstance(atual, (list, tuple)) and len(atual) == 2 and atual[0] == ano else 0
    novo = min(teto, val + delta)
    st[chave] = [ano, novo]
    return novo


def bonus_escola_atual(game: Game, cid: int) -> int:
    st = game.intelecto.get(cid)
    if not st:
        return 0
    b = st.get("bonus_escola")
    return int(b[1]) if isinstance(b, (list, tuple)) and len(b) == 2 and b[0] == game.year else 0


def bonus_enem_atual(game: Game, cid: int) -> int:
    st = game.intelecto.get(cid)
    if not st:
        return 0
    b = st.get("bonus_enem")
    return int(b[1]) if isinstance(b, (list, tuple)) and len(b) == 2 and b[0] == game.year else 0


def bonus_concurso_atual(game: Game, cid: int) -> int:
    st = game.intelecto.get(cid)
    if not st:
        return 0
    b = st.get("bonus_concurso")
    return int(b[1]) if isinstance(b, (list, tuple)) and len(b) == 2 and b[0] == game.year else 0


def estudar(game: Game, modo_id: str = "escola", area_id: str | None = None) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if modo_id not in MODOS_POR_ID:
        raise ValueError("Modo de estudo inválido.")
    _, rotulo, idade_min, _ = MODOS_POR_ID[modo_id]
    idade = p.age_at(game.year, game.month)
    if idade < idade_min:
        raise ValueError(f"{rotulo} disponível a partir dos {idade_min} anos.")
    if area_id is not None and area_id not in AREAS_POR_ID:
        raise ValueError("Área de estudo inválida.")

    st = dados(game, p.id)
    sm = _sessoes_mes(st, _mes(game))
    if sm[1] >= LIMITE_ESTUDO_MES:
        raise ValueError(f"Você já fez {LIMITE_ESTUDO_MES} sessões de estudo neste mês. Avance o mês para continuar.")

    area_escolhida = area_id or "ciencias"
    ganhos = []
    if modo_id == "escola":
        _add_bonus_anual(st, "bonus_escola", game.year, 6, 18)
        cog = AREAS_POR_ID[area_escolhida][2] if area_id else "aprendizagem"
        if engine.treinar_cognicao(p, cog, 1, elevar_potencial=True):
            ganhos.append(cog)
        if p.cognition.get("atencao", 0) < 99 and sm[1] == 0:
            if engine.treinar_cognicao(p, "atencao", 1, elevar_potencial=True):
                ganhos.append("atencao")
        adicionar_conhecimento(game, p.id, area_escolhida if area_id else "humanas", 1)
        msg = f"Estudou para {'a faculdade' if p.in_college else 'a escola'} (reforço escolar +{bonus_escola_atual(game, p.id)} no ano)."
    elif modo_id == "enem":
        _add_bonus_anual(st, "bonus_enem", game.year, 18, 60)
        pares = [("compreensao_verbal", "raciocinio_logico"), ("aprendizagem", "memoria")]
        c1, c2 = pares[sm[1] % 2]
        for k in (c1, c2):
            if engine.treinar_cognicao(p, k, 1, elevar_potencial=True):
                ganhos.append(k)
        adicionar_conhecimento(game, p.id, area_id or "linguagem", 1)
        msg = f"Fez simulado do ENEM / vestibular (preparo anual +{bonus_enem_atual(game, p.id)} pts)."
    elif modo_id == "concurso":
        _add_bonus_anual(st, "bonus_concurso", game.year, 4, 14)
        for k in ("resolucao_problemas", "memoria"):
            if engine.treinar_cognicao(p, k, 1, elevar_potencial=True):
                ganhos.append(k)
        adicionar_conhecimento(game, p.id, "direito", 1)
        adicionar_conhecimento(game, p.id, "economia", 1)
        msg = f"Estudou para concursos públicos (bônus anual +{bonus_concurso_atual(game, p.id)})."
    else:  # tema
        _, area_nome, cog = AREAS_POR_ID[area_escolhida]
        if engine.treinar_cognicao(p, cog, 1, elevar_potencial=True):
            ganhos.append(cog)
        if cog != "compreensao_verbal" and sm[1] == 0:
            if engine.treinar_cognicao(p, "compreensao_verbal", 1, elevar_potencial=True):
                ganhos.append("compreensao_verbal")
        adicionar_conhecimento(game, p.id, area_escolhida, 2)
        msg = f"Realizou estudo aprofundado em {area_nome}."

    pat = game.patrimonio.get(p.id)
    tem_pc = bool(pat and "notebook" in pat.get("equipamentos", []))
    if tem_pc and modo_id in ("enem", "concurso", "tema"):
        adicionar_conhecimento(game, p.id, area_escolhida, 1)
    p.health = max(0.0, round(p.health - 0.15, 2))
    sm[1] += 1
    game.add_event(p.id, "escola", msg)
    return {
        "modo": modo_id,
        "rotulo": rotulo,
        "ganhos": ganhos,
        "restantes": LIMITE_ESTUDO_MES - sm[1],
        "mensagem": msg,
    }


def estudar_lote(game: Game, modo_id: str = "escola", area_id: str | None = None, sessoes: int | None = None) -> dict:
    """Executa várias sessões de estudo em 1 ação (padrão: todas as restantes do mês) sem consumir `game.rng`."""
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    st = dados(game, p.id)
    sm = _sessoes_mes(st, _mes(game))
    disponiveis = LIMITE_ESTUDO_MES - sm[1]
    if disponiveis <= 0:
        raise ValueError(f"Você já fez {LIMITE_ESTUDO_MES} sessões de estudo neste mês. Avance o mês para continuar.")
    alvo = disponiveis if sessoes is None else max(1, min(disponiveis, int(sessoes)))
    ganhos_totais = []
    ultimo = None
    for _ in range(alvo):
        res = estudar(game, modo_id, area_id)
        ultimo = res
        for g in res.get("ganhos", []):
            if g not in ganhos_totais:
                ganhos_totais.append(g)
    rotulo = ultimo["rotulo"] if ultimo else MODOS_POR_ID.get(modo_id, (modo_id, modo_id))[1]
    msg = f"Concluiu {alvo} sessão(ões) de {rotulo}."
    return {
        "modo": modo_id,
        "rotulo": rotulo,
        "sessoes": alvo,
        "ganhos": ganhos_totais,
        "restantes": LIMITE_ESTUDO_MES - _sessoes_mes(st, _mes(game))[1],
        "mensagem": msg,
    }


def escrever_ensaio(game: Game, tema_id: str, tipo: str = "redacao") -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if tipo not in ("redacao", "ensaio"):
        raise ValueError("Tipo inválido (use redacao ou ensaio).")
    if tema_id not in TEMAS_POR_ID:
        raise ValueError("Tema inválido.")
    idade_min = 10 if tipo == "redacao" else 14
    idade = p.age_at(game.year, game.month)
    if idade < idade_min:
        raise ValueError(f"Escrever {'redação' if tipo == 'redacao' else 'ensaio'} exige pelo menos {idade_min} anos.")

    st = dados(game, p.id)
    sm = _sessoes_mes(st, _mes(game))
    if sm[2] >= LIMITE_ENSAIO_MES:
        raise ValueError(f"Você já escreveu {LIMITE_ENSAIO_MES} textos neste mês. Avance o mês para continuar.")

    _, titulo_tema, area_id, cog_extra = TEMAS_POR_ID[tema_id]
    r = random.Random(f"ensaio:{game.seed}:{_mes(game)}:{p.id}:{sm[2]}:{tema_id}:{tipo}")
    verbal = p.cognition.get("compreensao_verbal", 40)
    abstr = p.cognition.get("abstracao", 40)
    consc = p.personality.get("conscienciosidade", 50)
    con_area = st["conhecimentos"].get(area_id, 0)
    base = 380 + 3.4 * verbal + 1.8 * abstr + 0.9 * consc + min(80, con_area * 8) + r.gauss(0, 22)
    nota_1000 = int(min(1000, max(360, round(base / 20) * 20)))
    nota_fmt = f"{nota_1000}/1000" if tipo == "redacao" else f"{min(10.0, round(nota_1000 / 100, 1)):.1f}/10"

    ganhos = []
    if engine.treinar_cognicao(p, "compreensao_verbal", 1, elevar_potencial=True):
        ganhos.append("compreensao_verbal")
    if (tipo == "ensaio" or nota_1000 >= 800) and cog_extra != "compreensao_verbal":
        if engine.treinar_cognicao(p, cog_extra, 1, elevar_potencial=True):
            ganhos.append(cog_extra)
    elif tipo == "ensaio" and engine.treinar_cognicao(p, "abstracao", 1, elevar_potencial=True):
        ganhos.append("abstracao")

    adicionar_conhecimento(game, p.id, area_id, 2)
    adicionar_conhecimento(game, p.id, "linguagem", 1)
    _add_bonus_anual(st, "bonus_enem", game.year, 12, 60)
    _add_bonus_anual(st, "bonus_escola", game.year, 3, 18)

    sm[2] += 1
    reg = {"ano": game.year, "mes": game.month, "tipo": tipo, "tema": tema_id, "titulo": titulo_tema, "nota": nota_fmt}
    st["ensaios"] = (st["ensaios"] + [reg])[-30:]
    nome_tipo = "uma redação" if tipo == "redacao" else "um ensaio crítico"
    game.add_event(p.id, "escola", f"Escreveu {nome_tipo} sobre \"{titulo_tema}\" ({nota_fmt}).")
    return {
        "tipo": tipo,
        "tema": titulo_tema,
        "nota": nota_fmt,
        "ganhos": ganhos,
        "restantes": LIMITE_ENSAIO_MES - sm[2],
    }


def ler_artigo(game: Game, assunto_id: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if assunto_id not in AREAS_POR_ID:
        raise ValueError("Assunto de artigo inválido.")
    if p.age_at(game.year, game.month) < 10:
        raise ValueError("Leitura de artigos disponível a partir dos 10 anos.")

    st = dados(game, p.id)
    sm = _sessoes_mes(st, _mes(game))
    if sm[3] >= LIMITE_ARTIGO_MES:
        raise ValueError(f"Você já leu {LIMITE_ARTIGO_MES} artigos neste mês. Avance o mês para ler mais.")

    _, assunto_nome, cog = AREAS_POR_ID[assunto_id]
    lista_titulos = ARTIGOS_CATALOGO[assunto_id]
    lidos_assunto = sum(1 for a in st["artigos"] if a.get("assunto") == assunto_id)
    titulo = lista_titulos[(lidos_assunto + sm[3]) % len(lista_titulos)]

    ganhos = []
    if engine.treinar_cognicao(p, cog, 1, elevar_potencial=True):
        ganhos.append(cog)
    if cog != "compreensao_verbal" and sm[3] == 0:
        if engine.treinar_cognicao(p, "compreensao_verbal", 1, elevar_potencial=True):
            ganhos.append("compreensao_verbal")
    adicionar_conhecimento(game, p.id, assunto_id, 2)

    sm[3] += 1
    st["artigos"] = (st["artigos"] + [{"ano": game.year, "mes": game.month, "assunto": assunto_id, "titulo": titulo}])[-30:]
    game.add_event(p.id, "escola", f"Leu artigo de {assunto_nome}: \"{titulo}\".")
    return {
        "assunto": assunto_nome,
        "titulo": titulo,
        "ganhos": ganhos,
        "restantes": LIMITE_ARTIGO_MES - sm[3],
    }


def assistir_filme(game: Game, filme_id: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if filme_id not in FILMES_POR_ID:
        raise ValueError("Filme ou documentário inválido.")
    _, titulo, info, genero, idade_min, area_id, cog1, cog2, traco = FILMES_POR_ID[filme_id]
    if p.age_at(game.year, game.month) < idade_min:
        raise ValueError(f"\"{titulo}\" é indicado a partir dos {idade_min} anos.")

    st = dados(game, p.id)
    sm = _sessoes_mes(st, _mes(game))
    if sm[4] >= LIMITE_FILME_MES:
        raise ValueError(f"Você já assistiu a {LIMITE_FILME_MES} filmes/documentários neste mês.")

    primeira_vez = filme_id not in st["filmes"]
    ganhos = []
    if engine.treinar_cognicao(p, cog1, 1, elevar_potencial=True):
        ganhos.append(cog1)
    if primeira_vez and cog2 != cog1:
        if engine.treinar_cognicao(p, cog2, 1, elevar_potencial=True):
            ganhos.append(cog2)
    if primeira_vez and traco in p.personality:
        p.personality[traco] = int(min(99, p.personality[traco] + 1))
    p.health = min(100.0, round(p.health + 0.4, 2))
    adicionar_conhecimento(game, p.id, area_id, 2 if primeira_vez else 1)

    if primeira_vez:
        st["filmes"].append(filme_id)
    sm[4] += 1
    game.add_event(p.id, "decisao", f"Assistiu a \"{titulo}\" ({genero}, {info}).")
    return {
        "titulo": titulo,
        "genero": genero,
        "primeira_vez": primeira_vez,
        "ganhos": ganhos,
        "restantes": LIMITE_FILME_MES - sm[4],
    }


def revisar(game: Game, area_id: str) -> dict:
    """Consolida conhecimentos através de revisões (restaura retenção a 100% e reforça memória)."""
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if area_id not in AREAS_POR_ID:
        raise ValueError("Área inválida.")
    st = dados(game, p.id)
    sm = _sessoes_mes(st, _mes(game))
    if sm[1] >= LIMITE_ESTUDO_MES:
        raise ValueError(f"Você já usou todas as {LIMITE_ESTUDO_MES} sessões de estudo neste mês.")
    if st["conhecimentos"].get(area_id, 0) <= 0:
        raise ValueError("Estude ou leia algo nessa área antes de revisar.")
    antes = st["retencao"].get(area_id, 100.0)
    st["retencao"][area_id] = 100.0
    st["conhecimentos"][area_id] += 1
    ganhos = []
    for k in ("memoria", "aprendizagem"):
        if engine.treinar_cognicao(p, k, 1, elevar_potencial=True):
            ganhos.append(k)
    sm[1] += 1
    nome_area = AREAS_POR_ID[area_id][1]
    game.add_event(p.id, "escola", f"Fez revisão espaçada de {nome_area} (retenção restaurada de {antes:.0f}% para 100%).")
    return {"area": nome_area, "retencao_antes": round(antes, 1), "ganhos": ganhos, "restantes": LIMITE_ESTUDO_MES - sm[1]}


def grupo_estudo(game: Game, area_id: str) -> dict:
    """Participa de grupo de estudo com colegas/amigos (ganho intelectual + social)."""
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 12:
        raise ValueError("Grupos de estudo disponíveis a partir dos 12 anos.")
    if area_id not in AREAS_POR_ID:
        raise ValueError("Área inválida.")
    st = dados(game, p.id)
    sm = _sessoes_mes(st, _mes(game))
    if sm[1] >= LIMITE_ESTUDO_MES:
        raise ValueError(f"Você já usou todas as {LIMITE_ESTUDO_MES} sessões de estudo neste mês.")
    adicionar_conhecimento(game, p.id, area_id, 2)
    _add_bonus_anual(st, "bonus_escola", game.year, 4, 18)
    ganhos = []
    for k in ("compreensao_verbal", "aprendizagem"):
        if engine.treinar_cognicao(p, k, 1, elevar_potencial=True):
            ganhos.append(k)
    amigos = [game.characters[fid] for fid in game.friend_ids(p.id) if game.characters[fid].alive]
    if amigos:
        from . import vinculos
        alvo = amigos[(_mes(game) + len(amigos)) % len(amigos)]
        vinculos.registrar_evento(game, p.id, alvo.id, "Grupo de estudos", afinidade=4, respeito=5)
    sm[1] += 1
    nome_area = AREAS_POR_ID[area_id][1]
    game.add_event(p.id, "escola", f"Participou de grupo de estudo em {nome_area}.")
    return {"area": nome_area, "ganhos": ganhos, "restantes": LIMITE_ESTUDO_MES - sm[1]}


def nivel_idioma(pct: float) -> str:
    if pct >= 90:
        return "Fluente"
    if pct >= 70:
        return "Avançado"
    if pct >= 35:
        return "Intermediário"
    if pct > 0:
        return "Básico"
    return "Não iniciado"


def bonus_salarial_idiomas(game: Game, cid: int) -> float:
    st = game.intelecto.get(cid)
    if not st:
        return 1.0
    idiomas = st.get("idiomas", {})
    fluentes = sum(1 for v in idiomas.values() if v >= 70)
    return min(1.15, 1.0 + 0.05 * fluentes)


def estudar_idioma(game: Game, idioma_id: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 6:
        raise ValueError("Estudo de idiomas disponível a partir dos 6 anos.")
    if idioma_id not in IDIOMAS_POR_ID:
        raise ValueError("Idioma inválido.")
    st = dados(game, p.id)
    sm = _sessoes_mes(st, _mes(game))
    if sm[5] >= LIMITE_IDIOMA_MES:
        raise ValueError(f"Você já fez {LIMITE_IDIOMA_MES} aulas de idioma neste mês.")
    atual = float(st["idiomas"].get(idioma_id, 0.0))
    if atual >= 100.0:
        raise ValueError(f"Você já atingiu domínio completo de {IDIOMAS_POR_ID[idioma_id][1]}.")
    passo = 8.0 + 0.06 * p.cognition.get("compreensao_verbal", 50) + 0.04 * p.cognition.get("memoria", 50)
    pat = game.patrimonio.get(p.id)
    if pat and "notebook" in pat.get("equipamentos", []):
        passo += 2.0
    novo = min(100.0, round(atual + passo, 1))
    st["idiomas"][idioma_id] = novo
    ganhos = []
    if engine.treinar_cognicao(p, "compreensao_verbal", 1, elevar_potencial=True):
        ganhos.append("compreensao_verbal")
    if sm[5] == 0 and engine.treinar_cognicao(p, "memoria", 1, elevar_potencial=True):
        ganhos.append("memoria")
    adicionar_conhecimento(game, p.id, "linguagem", 1)
    sm[5] += 1
    nome = IDIOMAS_POR_ID[idioma_id][1]
    niv = nivel_idioma(novo)
    game.add_event(p.id, "escola", f"Estudou {nome} ({novo:.0f}% · {niv}).")
    return {"idioma": nome, "progresso": novo, "nivel": niv, "ganhos": ganhos, "restantes": LIMITE_IDIOMA_MES - sm[5]}


def pesquisar_e_publicar(game: Game, sub_id: str) -> dict:
    """Realiza pesquisa e publica artigo técnico-científico em uma das 48 subdisciplinas."""
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if p.age_at(game.year, game.month) < 15:
        raise ValueError("Pesquisa e publicação disponíveis a partir dos 15 anos.")
    if sub_id not in SUBDISCIPLINAS_POR_ID:
        raise ValueError("Subdisciplina inválida.")
    st = dados(game, p.id)
    sm = _sessoes_mes(st, _mes(game))
    if sm[6] >= LIMITE_PESQUISA_MES:
        raise ValueError("Você já publicou uma pesquisa neste mês. Avance o mês para iniciar outra.")
    sub_nome, _, disc_nome, raiz = SUBDISCIPLINAS_POR_ID[sub_id]
    st["subdisciplinas"][sub_id] = int(st["subdisciplinas"].get(sub_id, 0) + 3)
    pat = game.patrimonio.get(p.id)
    bonus_pc = 1 if (pat and "notebook" in pat.get("equipamentos", [])) else 0
    adicionar_conhecimento(game, p.id, raiz, 3 + bonus_pc)
    _add_bonus_anual(st, "bonus_escola", game.year, 4, 18)
    _add_bonus_anual(st, "bonus_concurso", game.year, 3, 14)
    ganhos = []
    for k in ("abstracao", "resolucao_problemas"):
        if engine.treinar_cognicao(p, k, 1, elevar_potencial=True):
            ganhos.append(k)
    sm[6] += 1
    reg = {"ano": game.year, "mes": game.month, "sub": sub_id, "titulo": f"Estudo em {sub_nome}", "disciplina": disc_nome}
    st["pesquisas"] = (st["pesquisas"] + [reg])[-30:]
    game.add_event(p.id, "universidade", f"Pesquisou e produziu artigo em {disc_nome} — {sub_nome}.")
    return {"disciplina": disc_nome, "subdisciplina": sub_nome, "ganhos": ganhos, "total_pesquisas": len(st["pesquisas"])}


def apply_month(game: Game) -> None:
    """Decaimento gradual da retenção de conhecimento (esquecimento) sem consumir `game.rng`."""
    if not game.intelecto:
        return
    from . import psicologia
    for cid, st in list(game.intelecto.items()):
        c = game.characters.get(cid)
        if c is None or not c.alive:
            continue
        con = st.get("conhecimentos", {})
        ret = st.setdefault("retencao", {})
        mem = c.cognition.get("memoria", 50)
        fator_hab = 0.55 if psicologia.tem_habito(game, cid, "leitura_diaria") else 1.0
        queda = max(0.8, (3.6 - 0.022 * mem) * fator_hab)
        for aid, pts in con.items():
            if pts > 0:
                atual = float(ret.get(aid, 100.0))
                ret[aid] = round(max(35.0, atual - queda), 1)
    # Leitura automática opcional da lista de leitura ao virar o mês (só quando o jogador ativou)
    p = _jogador(game)
    if p is not None:
        st_p = game.intelecto.get(p.id)
        if st_p and st_p.get("auto_ler_fila") and st_p.get("fila_leitura"):
            from . import livros
            livros.ler_fila(game, silencioso=True)


def view(game: Game) -> dict:
    p = _jogador(game)
    if p is None:
        return {
            "disponivel": False,
            "estudo_restante": 0, "ensaio_restante": 0, "artigo_restante": 0, "filme_restante": 0,
            "idioma_restante": 0, "pesquisa_restante": 0,
            "modos_estudo": [], "areas_conhecimento": [], "enciclopedia": [], "idiomas": [],
            "temas_ensaio": [], "filmes": [], "conhecimentos": {}, "retencao": {},
            "ensaios": [], "artigos": [], "pesquisas": [], "filmes_vistos": [],
            "bonus_escola": 0, "bonus_enem": 0, "bonus_concurso": 0,
        }
    st = dados(game, p.id)
    sm = _sessoes_mes(st, _mes(game))
    idade = p.age_at(game.year, game.month)
    vistos = set(st["filmes"])
    sub_map = st.get("subdisciplinas", {})
    ret_map = st.get("retencao", {})
    idiomas_map = st.get("idiomas", {})
    return {
        "disponivel": True,
        "idade": idade,
        "estudo_restante": max(0, LIMITE_ESTUDO_MES - sm[1]),
        "estudo_max": LIMITE_ESTUDO_MES,
        "ensaio_restante": max(0, LIMITE_ENSAIO_MES - sm[2]),
        "ensaio_max": LIMITE_ENSAIO_MES,
        "artigo_restante": max(0, LIMITE_ARTIGO_MES - sm[3]),
        "artigo_max": LIMITE_ARTIGO_MES,
        "filme_restante": max(0, LIMITE_FILME_MES - sm[4]),
        "filme_max": LIMITE_FILME_MES,
        "idioma_restante": max(0, LIMITE_IDIOMA_MES - sm[5]),
        "idioma_max": LIMITE_IDIOMA_MES,
        "pesquisa_restante": max(0, LIMITE_PESQUISA_MES - sm[6]),
        "pesquisa_max": LIMITE_PESQUISA_MES,
        "modos_estudo": [
            {"id": mid, "rotulo": rot, "idade_min": imin, "desc": desc, "pode": idade >= imin}
            for mid, rot, imin, desc in MODOS_ESTUDO
        ],
        "areas_conhecimento": [
            {"id": aid, "rotulo": rot, "cognicao": cog, "pontos": st["conhecimentos"].get(aid, 0),
             "retencao": round(ret_map.get(aid, 100.0), 1)}
            for aid, rot, cog in AREAS_CONHECIMENTO
        ],
        "enciclopedia": [
            {
                "id": did, "nome": dnome, "raiz": raiz,
                "pontos_raiz": st["conhecimentos"].get(raiz, 0),
                "retencao": round(ret_map.get(raiz, 100.0), 1),
                "subs": [{"id": sid, "nome": snome, "pontos": sub_map.get(sid, 0)} for sid, snome in subs],
            }
            for did, dnome, raiz, subs in ENCICLOPEDIA
        ],
        "idiomas": [
            {
                "id": iid, "nome": inome, "uso": iuso,
                "progresso": round(idiomas_map.get(iid, 0.0), 1),
                "nivel": nivel_idioma(idiomas_map.get(iid, 0.0)),
            }
            for iid, inome, iuso in IDIOMAS
        ],
        "temas_ensaio": [
            {"id": tid, "titulo": tit, "area": aid, "area_nome": AREAS_POR_ID[aid][1]}
            for tid, tit, aid, _ in TEMAS_ENSAIO
        ],
        "filmes": [
            {
                "id": fid, "titulo": tit, "info": info, "genero": gen, "idade_min": imin,
                "area": aid, "area_nome": AREAS_POR_ID[aid][1], "visto": fid in vistos,
                "pode": idade >= imin,
            }
            for fid, tit, info, gen, imin, area, _, _, _ in FILMES
            for aid in (area,)
        ],
        "conhecimentos": dict(st["conhecimentos"]),
        "retencao": dict(ret_map),
        "ensaios": list(reversed(st["ensaios"][-10:])),
        "artigos": list(reversed(st["artigos"][-10:])),
        "pesquisas": list(reversed(st.get("pesquisas", [])[-10:])),
        "filmes_vistos": list(st["filmes"]),
        "bonus_escola": bonus_escola_atual(game, p.id),
        "bonus_enem": bonus_enem_atual(game, p.id),
        "bonus_concurso": bonus_concurso_atual(game, p.id),
    }
