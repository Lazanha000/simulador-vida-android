"""Vínculos sociais multidimensionais, família, colegas e rivalidade (v0.20.0).

Implementa o §4.6 do Prompt-Mestre:
- Cada relacionamento possui: afinidade, confiança, intimidade, respeito, hostilidade e histórico de memórias.
- Permite interagir diretamente com familiares (pais, cônjuge, filhos, irmãos), parceiro(a), amigos,
  colegas de trabalho e rivais/inimigos.
- Ações com consequências reais: conversar, convidar, apoiar (inclusive financeiramente), estudar/networkar junto,
  confrontar (gera rivalidade/inimizade) e reconciliar.
- Nunca consome `game.rng`.
"""
from __future__ import annotations

from . import engine, intelecto, work
from .models import Character, Game

ACOES_VINCULO = {
    "conversar": "Conversar com atenção",
    "convidar": "Convidar para sair / jantar",
    "apoiar": "Apoiar e aconselhar",
    "networkar": "Estudar ou trocar experiências profissionais",
    "confrontar": "Discutir / confrontar",
    "reconciliar": "Pedir desculpas e reconciliar",
}


def _chave(a: int, b: int) -> tuple[int, int]:
    return (min(a, b), max(a, b))


def _mes(game: Game) -> int:
    return game.year * 12 + game.month


def _jogador(game: Game) -> Character | None:
    p = game.characters.get(game.player_id) if game.player_id is not None else None
    return p if p is not None and p.alive else None


def _relacao_rotulo(game: Game, p: Character, o: Character) -> str:
    if p.spouse_id == o.id and engine.has_active_spouse(game, p):
        return "Esposa" if o.sex == "F" else "Marido"
    if p.partner_id == o.id:
        return "Namorada" if o.sex == "F" else "Namorado"
    if o.id in (p.mother_id, p.father_id):
        return "Mãe" if o.sex == "F" else "Pai"
    if p.id in (o.mother_id, o.father_id):
        return "Filha" if o.sex == "F" else "Filho"
    if (p.mother_id and p.mother_id == o.mother_id) or (p.father_id and p.father_id == o.father_id):
        return "Irmã" if o.sex == "F" else "Irmão"
    if game.are_friends(p.id, o.id):
        return "Amiga" if o.sex == "F" else "Amigo"
    if engine._coworkers(p, o):
        return "Colega de trabalho"
    st = game.vinculos.get(_chave(p.id, o.id))
    if st:
        if st.get("hostilidade", 0) >= 80:
            return "Inimiga" if o.sex == "F" else "Inimigo"
        if st.get("hostilidade", 0) >= 50:
            return "Rival"
    return "Conhecido(a)"


def estado(game: Game, a_id: int, b_id: int) -> dict:
    k = _chave(a_id, b_id)
    if k in game.vinculos:
        st = game.vinculos[k]
        st.setdefault("historico", [])
        st.setdefault("ultimo_mes", 0)
        return st
    a, b = game.characters.get(a_id), game.characters.get(b_id)
    aff_base = int(round(engine.affinity(a, b) * 60 + 20)) if a and b else 50
    conf, inti, resp, host = 45, 35, 50, 5
    if a and b:
        if a.spouse_id == b.id or a.partner_id == b.id:
            aff_base = max(aff_base, 72)
            conf, inti, resp = 70, 75, 70
        elif a.id in (b.mother_id, b.father_id) or b.id in (a.mother_id, a.father_id):
            aff_base = max(aff_base, 70)
            conf, inti, resp = 75, 70, 75
        elif game.are_friends(a.id, b.id):
            aff_base = max(aff_base, 62)
            conf, inti, resp = 60, 52, 60
        elif engine._coworkers(a, b):
            conf, inti, resp = 48, 25, 62
    st = {
        "afinidade": max(0, min(100, aff_base)),
        "confianca": conf,
        "intimidade": inti,
        "respeito": resp,
        "hostilidade": host,
        "historico": [],
        "ultimo_mes": 0,
    }
    game.vinculos[k] = st
    return st


def registrar_evento(game: Game, a_id: int, b_id: int, nota: str, **deltas: int) -> dict:
    st = estado(game, a_id, b_id)
    for campo, d in deltas.items():
        if campo in ("afinidade", "confianca", "intimidade", "respeito", "hostilidade"):
            st[campo] = max(0, min(100, int(st[campo] + d)))
    st["historico"] = (st["historico"] + [f"{game.month:02d}/{game.year}: {nota}"])[-8:]
    return st


def pessoas_proximas(game: Game) -> list[dict]:
    p = _jogador(game)
    if p is None:
        return []
    now = (game.year, game.month)
    mes = _mes(game)
    ids: list[int] = []
    seen = {p.id}

    def add_id(cid: int | None):
        if cid is not None and cid not in seen:
            o = game.characters.get(cid)
            if o is not None and o.alive:
                seen.add(cid)
                ids.append(cid)

    add_id(p.spouse_id if engine.has_active_spouse(game, p) else None)
    add_id(p.partner_id)
    add_id(p.mother_id)
    add_id(p.father_id)
    for ch in sorted(game.children_of(p.id), key=lambda x: x.id):
        add_id(ch.id)
    for par in game.parents_of(p):
        for ir in sorted(game.children_of(par.id), key=lambda x: x.id):
            add_id(ir.id)
    for fid in game.friend_ids(p.id):
        add_id(fid)
    if work.is_employed(p) and p.workplace is not None:
        for o in sorted(game.characters.values(), key=lambda x: x.id):
            if o.alive and o.id != p.id and engine._coworkers(p, o):
                add_id(o.id)
                if len(ids) >= 24:
                    break
    for (a, b), vst in game.vinculos.items():
        if p.id in (a, b) and vst.get("hostilidade", 0) >= 40:
            add_id(b if a == p.id else a)

    out = []
    for oid in ids:
        o = game.characters[oid]
        st = estado(game, p.id, oid)
        out.append({
            "id": oid,
            "nome": o.full_name,
            "idade": o.age_at(*now),
            "relacao": _relacao_rotulo(game, p, o),
            "afinidade": st["afinidade"],
            "confianca": st["confianca"],
            "intimidade": st["intimidade"],
            "respeito": st["respeito"],
            "hostilidade": st["hostilidade"],
            "rival": st["hostilidade"] >= 50,
            "inimigo": st["hostilidade"] >= 80,
            "interagiu_mes": st.get("ultimo_mes") == mes,
            "historico": list(reversed(st.get("historico", []))),
            "eh_amigo": game.are_friends(p.id, oid),
            "eh_colega": engine._coworkers(p, o),
        })
    return out


def interagir(game: Game, alvo_id: int, acao: str) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if acao not in ACOES_VINCULO:
        raise ValueError("Ação de vínculo inválida.")
    o = game.characters.get(alvo_id)
    if o is None or not o.alive or o.id == p.id:
        raise ValueError("Pessoa não encontrada ou falecida.")
    mes = _mes(game)
    st = estado(game, p.id, o.id)
    if st.get("ultimo_mes") == mes:
        raise ValueError(f"Você já teve uma interação importante com {o.first_name} neste mês.")
    idade_p = p.age_at(game.year, game.month)
    idade_o = o.age_at(game.year, game.month)
    custo = 0.0
    msg = ""

    if acao == "conversar":
        if st["hostilidade"] >= 70:
            raise ValueError(f"A hostilidade com {o.first_name} está alta; tente reconciliar antes.")
        registrar_evento(game, p.id, o.id, "Conversa sincera", afinidade=5, confianca=3, intimidade=4, hostilidade=-2)
        p.health = min(100.0, round(p.health + 0.3, 2))
        k = _chave(p.id, o.id)
        game.convivio[k] = mes
        game.memoria[k] = game.memoria.get(k, 0) + 1
        msg = f"Teve uma conversa significativa com {o.full_name}."
    elif acao == "convidar":
        if st["hostilidade"] >= 70:
            raise ValueError(f"A hostilidade com {o.first_name} impede um convite amigável.")
        custo = round(0.04 * game.macro["min_wage"], 2) if idade_p >= 18 else 0.0
        if p.wealth < custo:
            raise ValueError("Patrimônio insuficiente para o convite.")
        p.wealth = round(p.wealth - custo, 2)
        registrar_evento(game, p.id, o.id, "Momento de lazer juntos", afinidade=9, confianca=5, intimidade=7, hostilidade=-4)
        p.health = min(100.0, round(p.health + 0.6, 2))
        k = _chave(p.id, o.id)
        game.convivio[k] = mes
        game.convites[k] = mes
        game.memoria[k] = game.memoria.get(k, 0) + 1
        msg = f"Saiu e fortaleceu os laços com {o.full_name}."
    elif acao == "apoiar":
        custo = round(0.05 * game.macro["min_wage"], 2) if idade_p >= 18 and idade_o >= 16 and p.wealth >= 0.05 * game.macro["min_wage"] else 0.0
        if custo > 0:
            p.wealth = round(p.wealth - custo, 2)
            o.wealth = round(o.wealth + custo, 2)
        registrar_evento(game, p.id, o.id, "Apoio e solidariedade", afinidade=6, confianca=9, respeito=8, hostilidade=-6)
        p.personality["amabilidade"] = min(99, p.personality.get("amabilidade", 50) + 1)
        msg = f"Apoiou {o.full_name} em um momento importante."
    elif acao == "networkar":
        if min(idade_p, idade_o) < 12:
            raise ValueError("Estudo conjunto / networking disponível a partir dos 12 anos.")
        registrar_evento(game, p.id, o.id, "Troca intelectual / profissional", afinidade=4, confianca=4, respeito=8)
        engine.treinar_cognicao(p, "compreensao_verbal", 1, elevar_potencial=True)
        if p.in_school or p.in_college:
            ist = intelecto.dados(game, p.id)
            intelecto._add_bonus_anual(ist, "bonus_escola", game.year, 2, 18)
        if work.is_employed(p) and engine._coworkers(p, o):
            p.experience += 1
        msg = f"Estudou e trocou ideias com {o.full_name}."
    elif acao == "confrontar":
        registrar_evento(game, p.id, o.id, "Discussão séria", afinidade=-14, confianca=-12, respeito=-6, hostilidade=28)
        p.health = max(0.0, round(p.health - 0.5, 2))
        if st["hostilidade"] >= 50 and game.are_friends(p.id, o.id):
            game.remove_friendship(p.id, o.id)
        rot = "inimigo(a)" if st["hostilidade"] >= 80 else "rival" if st["hostilidade"] >= 50 else "atrito"
        msg = f"Discutiu seriamente com {o.full_name} (clima de {rot})."
    elif acao == "reconciliar":
        if st["hostilidade"] < 15:
            raise ValueError(f"Não há conflito relevante com {o.first_name}.")
        registrar_evento(game, p.id, o.id, "Reconciliação", afinidade=10, confianca=8, respeito=6, hostilidade=-30)
        msg = f"Buscou diálogo e reduziu as tensões com {o.full_name}."

    st["ultimo_mes"] = mes
    cat = "amizade_fim" if acao == "confrontar" else "amizade"
    game.add_event(p.id, cat, msg)
    game.add_event(o.id, cat, f"Interação com {p.full_name}: {ACOES_VINCULO[acao].lower()}.")
    return {
        "alvo": o.full_name,
        "acao": acao,
        "custo": custo,
        "mensagem": msg,
        "estado": dict(st),
    }
