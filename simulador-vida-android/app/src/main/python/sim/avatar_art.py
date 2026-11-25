"""Gerador SVG dos avatares da v0.14.0+ — estilo ilustrado moderno, expressivo e acolhedor."""

import random

SK = ['#fde0c8', '#f1c29b', '#d99a6c', '#a86b3e', '#6b4228']
SK_SHADE = ['#f2c29d', '#dca276', '#be7d50', '#8b512a', '#522f1a']
HC = ['#1f1d24', '#4e3322', '#a8512b', '#d9a441', '#7d2038']
HC_HI = ['#3b3744', '#6e4a33', '#c96f44', '#ecc268', '#a1344f']

ST = {
    'bebe':        (24, 24, 65, 22, 3.6, 9.2),
    'crianca':     (22, 24, 62, 28, 3.4, 9.0),
    'adolescente': (21, 25, 59, 34, 3.1, 8.8),
    'jovem':       (20, 25, 58, 36, 3.0, 8.6),
    'adulto':      (20, 25, 58, 38, 2.9, 8.6),
    'idoso':       (20, 25, 59, 36, 2.8, 8.6),
}

CLO = {
    'bebe':        ('#fef3c7', '#e0f2fe'),
    'crianca':     ('#fb7185', '#38bdf8'),
    'adolescente': ('#8b5cf6', '#10b981'),
    'jovem':       ('#ec4899', '#2563eb'),
    'adulto':      ('#0d9488', '#334155'),
    'idoso':       ('#64748b', '#475569'),
}

CLO_ACC = {
    'bebe':        ('#f472b6', '#60a5fa'),
    'crianca':     ('#fff1f2', '#e0f2fe'),
    'adolescente': ('#ede9fe', '#d1fae5'),
    'jovem':       ('#fce7f3', '#dbeafe'),
    'adulto':      ('#ccfbf1', '#cbd5e1'),
    'idoso':       ('#e2e8f0', '#cbd5e1'),
}

BG_PAL = {
    'bebe':        ('#fef9c3', '#fde68a'),
    'crianca':     ('#dbeafe', '#bfdbfe'),
    'adolescente': ('#ede9fe', '#ddd6fe'),
    'jovem':       ('#d1fae5', '#a7f3d0'),
    'adulto':      ('#e0f2fe', '#bae6fd'),
    'idoso':       ('#f1f5f9', '#e2e8f0'),
}

DEFS = (
    '<defs>'
    '<filter id="gray"><feColorMatrix type="saturate" values="0.15"/></filter>'
    '<radialGradient id="blush" cx="50%" cy="50%" r="50%">'
    '<stop offset="0%" stop-color="#ff7a90" stop-opacity=".5"/>'
    '<stop offset="100%" stop-color="#ff7a90" stop-opacity="0"/>'
    '</radialGradient>'
    '<linearGradient id="rim" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0%" stop-color="#ffffff" stop-opacity=".9"/>'
    '<stop offset="100%" stop-color="#cbd5e1" stop-opacity=".8"/>'
    '</linearGradient>'
    '</defs>'
)


def avatar(stage, sex, si=1, hi=None, dead=False):
    rx, ry, cy, bw, er, es = ST[stage]
    cx = 60
    f = sex == 'f'
    skin = SK[si]
    shade = SK_SHADE[si]
    hair_idx = hi if hi is not None else (1 if f else 0)
    hair = '#e2e8f0' if stage == 'idoso' else HC[hair_idx]
    hair_hi = '#f8fafc' if stage == 'idoso' else HC_HI[hair_idx]
    cloth = CLO[stage][0 if f else 1]
    collar = CLO_ACC[stage][0 if f else 1]
    bg1, bg2 = ('#334155', '#1e293b') if dead else BG_PAL[stage]
    by = cy + ry + 5
    brow_col = '#94a3b8' if stage == 'idoso' else hair
    gray_flt = ' filter="url(#gray)"' if dead else ''
    outline = '#3f2e26'

    o = ''

    # Cabelo de trás (camada posterior)
    if f and stage in ('adolescente', 'jovem', 'adulto'):
        tail_y = cy + ry + 24
        o += (
            f'<path d="M{cx-rx-4} {cy-6} C{cx-rx-10} {cy+12},{cx-rx-8} {tail_y},{cx-rx+4} {tail_y+2} '
            f'L{cx+rx-4} {tail_y+2} C{cx+rx+8} {tail_y},{cx+rx+10} {cy+12},{cx+rx+4} {cy-6} Z" '
            f'fill="{hair}" stroke="{outline}" stroke-width="1.2" stroke-linejoin="round"/>'
        )
    elif f and stage == 'crianca':
        for s in (-1, 1):
            o += (
                f'<circle cx="{cx+s*(rx+6)}" cy="{cy-2}" r="8.5" fill="{hair}" stroke="{outline}" stroke-width="1.2"/>'
                f'<circle cx="{cx+s*(rx+4)}" cy="{cy-5}" r="2.5" fill="{collar}"/>'
            )
    elif f and stage == 'idoso':
        o += f'<circle cx="{cx}" cy="{cy-ry-4}" r="10.5" fill="{hair}" stroke="{outline}" stroke-width="1.1"/>'

    # Corpo / Roupa moderna com gola arredondada
    o += (
        f'<path d="M{cx-bw} 124 C{cx-bw} {by+4},{cx-bw+6} {by-2},{cx} {by-2} '
        f'C{cx+bw-6} {by-2},{cx+bw} {by+4},{cx+bw} 124 Z" '
        f'fill="{cloth}" stroke="{outline}" stroke-width="1.3"/>'
    )
    o += (
        f'<path d="M{cx-11} {by} Q{cx} {by+11} {cx+11} {by}" '
        f'fill="none" stroke="{collar}" stroke-width="3" stroke-linecap="round"/>'
    )
    if stage in ('jovem', 'adulto') and not f:
        o += f'<path d="M{cx-8} {by+2} L{cx-2} {by+16} M{cx+8} {by+2} L{cx+2} {by+16}" stroke="{collar}" stroke-width="1.6" stroke-linecap="round"/>'

    # Pescoço + sombra suave do queixo
    o += f'<rect x="{cx-6.5}" y="{cy+ry-7}" width="13" height="14" rx="5" fill="{skin}" stroke="{outline}" stroke-width="1.1"/>'
    o += f'<ellipse cx="{cx}" cy="{cy+ry-1}" rx="6.2" ry="3.2" fill="{shade}" fill-opacity=".55"/>'

    # Orelhas
    for s in (-1, 1):
        ex = cx + s * (rx - 0.5)
        o += f'<ellipse cx="{ex}" cy="{cy+3}" rx="4" ry="5.5" fill="{skin}" stroke="{outline}" stroke-width="1.1"/>'
        o += f'<ellipse cx="{ex-s*0.7}" cy="{cy+3.5}" rx="1.8" ry="2.6" fill="{shade}" fill-opacity=".45"/>'
        if f and stage in ('jovem', 'adulto', 'idoso'):
            o += f'<circle cx="{ex}" cy="{cy+8.5}" r="2.2" fill="#fbbf24" stroke="{outline}" stroke-width=".7"/>'

    # Rosto com formato arredondado natural (bochechas suaves, queixo delicado)
    chin_w = rx * 0.58
    o += (
        f'<path d="M{cx-rx} {cy-3} C{cx-rx} {cy-ry-1},{cx+rx} {cy-ry-1},{cx+rx} {cy-3} '
        f'C{cx+rx} {cy+ry*0.72},{cx+chin_w} {cy+ry},{cx} {cy+ry} '
        f'C{cx-chin_w} {cy+ry},{cx-rx} {cy+ry*0.72},{cx-rx} {cy-3} Z" '
        f'fill="{skin}" stroke="{outline}" stroke-width="1.3"/>'
    )

    # Bochechas rosadas suaves
    blush_op = '.78' if stage in ('bebe', 'crianca') else ('.55' if f else '.32')
    for s in (-1, 1):
        o += f'<ellipse cx="{cx+s*(es+4.5)}" cy="{cy+8.5}" rx="5.6" ry="3.6" fill="url(#blush)" fill-opacity="{blush_op}"/>'

    # Cabelo frontal / Franja estilizada
    if stage == 'bebe':
        o += (
            f'<path d="M{cx-4} {cy-ry+1} C{cx-9} {cy-ry-7},{cx+4} {cy-ry-9},{cx+6} {cy-ry-1} '
            f'C{cx+10} {cy-ry-5},{cx+12} {cy-ry+2},{cx+5} {cy-ry+3} Z" '
            f'fill="{hair}" stroke="{outline}" stroke-width="1.1" stroke-linejoin="round"/>'
        )
    elif stage == 'idoso' and not f:
        for s in (-1, 1):
            o += f'<path d="M{cx+s*(rx-3)} {cy-8} Q{cx+s*(rx+3)} {cy-3} {cx+s*(rx-1)} {cy+4} Q{cx+s*(rx-4)} {cy-2} {cx+s*(rx-3)} {cy-8} Z" fill="{hair}" stroke="{outline}" stroke-width="1"/>'
    elif f:
        o += (
            f'<path d="M{cx-rx-2} {cy-1} C{cx-rx-3} {cy-ry-9},{cx+rx+3} {cy-ry-9},{cx+rx+2} {cy-1} '
            f'C{cx+rx-2} {cy-ry+7},{cx+5} {cy-ry+10},{cx} {cy-ry+6} '
            f'C{cx-6} {cy-ry+11},{cx-rx+2} {cy-ry+7},{cx-rx-2} {cy-1} Z" '
            f'fill="{hair}" stroke="{outline}" stroke-width="1.2" stroke-linejoin="round"/>'
        )
        o += f'<path d="M{cx-10} {cy-ry+3} Q{cx} {cy-ry-2} {cx+10} {cy-ry+3}" fill="none" stroke="{hair_hi}" stroke-width="2" stroke-linecap="round" opacity=".55"/>'
    else:
        o += (
            f'<path d="M{cx-rx-1} {cy-2} C{cx-rx-2} {cy-ry-10},{cx+rx+2} {cy-ry-10},{cx+rx+1} {cy-2} '
            f'C{cx+rx-3} {cy-ry+5},{cx+4} {cy-ry+7},{cx-2} {cy-ry+4} '
            f'C{cx-8} {cy-ry+8},{cx-rx+3} {cy-ry+5},{cx-rx-1} {cy-2} Z" '
            f'fill="{hair}" stroke="{outline}" stroke-width="1.2" stroke-linejoin="round"/>'
        )
        o += f'<path d="M{cx-9} {cy-ry+1} Q{cx} {cy-ry-3} {cx+9} {cy-ry+2}" fill="none" stroke="{hair_hi}" stroke-width="2" stroke-linecap="round" opacity=".5"/>'

    # Barba suave moderna (adulto / idoso masculino)
    if not f and stage in ('adulto', 'idoso'):
        beard_op = '.88' if stage == 'idoso' else '.26'
        beard_st = outline if stage == 'idoso' else 'none'
        o += (
            f'<path d="M{cx-rx+2} {cy+6} C{cx-rx+1} {cy+ry+3},{cx+rx-1} {cy+ry+3},{cx+rx-2} {cy+6} '
            f'C{cx+rx-5} {cy+ry-3},{cx-rx+5} {cy+ry-3},{cx-rx+2} {cy+6} Z" '
            f'fill="{hair}" fill-opacity="{beard_op}" stroke="{beard_st}" stroke-width="1"/>'
        )

    # Olhos expressivos com brilho duplo e cílios suaves
    ey = cy + 1
    if dead:
        for s in (-1, 1):
            o += f'<path d="M{cx+s*es-3.5} {ey} Q{cx+s*es} {ey+3.5} {cx+s*es+3.5} {ey}" fill="none" stroke="{outline}" stroke-width="1.6" stroke-linecap="round"/>'
    else:
        for s in (-1, 1):
            ex = cx + s * es
            o += f'<ellipse cx="{ex}" cy="{ey}" rx="{er}" ry="{er*1.12:.2f}" fill="#1e1b24"/>'
            o += f'<circle cx="{ex-1.1}" cy="{ey-1.2}" r="{max(1.0, er*0.38):.2f}" fill="#ffffff"/>'
            o += f'<circle cx="{ex+1.0}" cy="{ey+1.1}" r="{max(0.55, er*0.18):.2f}" fill="#ffffff" fill-opacity=".85"/>'
            if f and stage not in ('bebe',):
                o += f'<path d="M{ex-er} {ey-1.5} Q{ex} {ey-er-1.2} {ex+er+s*1.2} {ey-1.8}" fill="none" stroke="#1e1b24" stroke-width="1.4" stroke-linecap="round"/>'

    # Sobrancelhas expressivas
    if stage != 'bebe':
        bw_len = 4.2 if stage == 'crianca' else 4.8
        by_brow = ey - (er + 3.4)
        for s in (-1, 1):
            ex = cx + s * es
            o += f'<path d="M{ex-bw_len} {by_brow} Q{ex} {by_brow-2.2} {ex+bw_len} {by_brow}" fill="none" stroke="{brow_col}" stroke-width="1.7" stroke-linecap="round"/>'

    # Nariz suave
    o += f'<path d="M{cx-1.4} {ey+5.2} Q{cx} {ey+7.2} {cx+1.6} {ey+5.2}" fill="none" stroke="{shade}" stroke-width="1.4" stroke-linecap="round"/>'

    # Sorriso acolhedor
    my = cy + ry - 8.5
    mw = 3.6 if stage == 'bebe' else 5.2
    if dead:
        o += f'<path d="M{cx-mw+1} {my+1} Q{cx} {my} {cx+mw-1} {my+1}" fill="none" stroke="{outline}" stroke-width="1.4" stroke-linecap="round"/>'
    else:
        lip_col = '#e11d48' if f and stage in ('jovem', 'adulto') else '#b45348'
        o += f'<path d="M{cx-mw} {my} Q{cx} {my+4.5} {cx+mw} {my}" fill="none" stroke="{lip_col}" stroke-width="1.7" stroke-linecap="round"/>'

    # Óculos modernos para idosos
    if stage == 'idoso':
        for s in (-1, 1):
            ex = cx + s * es
            o += f'<circle cx="{ex}" cy="{ey}" r="6.2" fill="#ffffff" fill-opacity=".18" stroke="#334155" stroke-width="1.3"/>'
        o += f'<path d="M{cx-es+6.2} {ey} Q{cx} {ey-1.5} {cx+es-6.2} {ey}" fill="none" stroke="#334155" stroke-width="1.3"/>'

    # Fundo circular moderno com gradiente suave e anel limpo
    grad_bg = (
        f'<linearGradient id="bg_{stage}_{sex}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{bg1}"/><stop offset="100%" stop-color="{bg2}"/></linearGradient>'
    )
    body = (
        f'<defs>{grad_bg}<clipPath id="cl"><circle cx="60" cy="60" r="54"/></clipPath></defs>'
        f'<circle cx="60" cy="60" r="56" fill="url(#bg_{stage}_{sex})"/>'
        f'<g clip-path="url(#cl)"{gray_flt}>{o}</g>'
        + ('<path d="M12 86 L36 112 L26 117 L6 96 Z" fill="#0f172a" fill-opacity=".85" clip-path="url(#cl)"/>' if dead else '')
        + '<circle cx="60" cy="60" r="56" fill="none" stroke="url(#rim)" stroke-width="3.5"/>'
    )
    return body


# --------------------------------------------------------------------------------------------------
# API do jogo (compatível com v0.14.0+ e TestAvatares)
ETAPAS_ARTE = ((0, 'bebe'), (3, 'crianca'), (12, 'adolescente'), (18, 'jovem'), (35, 'adulto'), (60, 'idoso'))
PESO_PELE = (0.22, 0.28, 0.25, 0.15, 0.10)
PESO_CABELO = (0.35, 0.38, 0.14, 0.08, 0.05)


def stage_for_age(age: int) -> str:
    nome = ETAPAS_ARTE[0][1]
    for inicio, n in ETAPAS_ARTE:
        if age >= inicio:
            nome = n
    return nome


def _pick(rng: random.Random, pesos) -> int:
    x, acc = rng.random() * sum(pesos), 0.0
    for i, p in enumerate(pesos):
        acc += p
        if x < acc:
            return i
    return len(pesos) - 1


def look(game, c) -> tuple[int, int]:
    """(tom de pele 0–4, cabelo 0–4) de `c`. Determinístico por (semente, id)."""
    cache = game.__dict__.setdefault("_look_cache", {})
    if c.id in cache:
        return cache[c.id]
    rng = random.Random(f"{game.seed}:look:{c.id}")
    pais = game.parents_of(c)
    if not pais:
        res = (_pick(rng, PESO_PELE), _pick(rng, PESO_CABELO))
    else:
        olhares = [look(game, p) for p in pais]
        media = sum(o[0] for o in olhares) / len(olhares)
        pele = int(media + rng.choice((-0.6, 0.0, 0.0, 0.6)) + 0.5)
        cabelo = rng.choice([o[1] for o in olhares])
        if rng.random() < 0.08:
            cabelo = _pick(rng, PESO_CABELO)
        res = (min(4, max(0, pele)), cabelo)
    cache[c.id] = res
    return res


def svg(stage: str, sex: str, skin: int, hair: int, dead: bool = False) -> str:
    """SVG 120×120 completo (mesmo invólucro dos arquivos do kit). `sex` = 'f' ou 'm'."""
    if stage not in ST or sex not in ('f', 'm') or not 0 <= skin < len(SK) or not 0 <= hair < len(HC):
        raise ValueError("parâmetros de avatar inválidos")
    corpo = avatar(stage, sex, skin, hair, dead)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="120" height="120">{DEFS}{corpo}</svg>'


def url(game, c, age: int) -> str:
    """Rota do avatar de `c`."""
    pele, cabelo = look(game, c)
    return f"/avatar/{stage_for_age(age)}_{c.sex.lower()}_{pele}_{cabelo}{'' if c.alive else '_d'}.svg"
