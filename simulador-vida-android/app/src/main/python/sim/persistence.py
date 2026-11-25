"""Persistência em SQLite (biblioteca padrão). Salvamento atômico."""
from __future__ import annotations

import json
import os
import sqlite3

from . import economy, factory, firms, work
from .models import BioEvent, Character, Family, Firm, Game

SCHEMA_VERSION = 19
# Versões antigas legíveis (v7 = trabalho; v8 = carreira e economia; v9 = empresas e vagas; v10 = seguro-desemprego). v1 não tem spouse_id; v2 não tem cognition_potential/ex_spouse_id
# (potencial = cognição atual, ex = None);
# o arquivo só é convertido para a versão atual no próximo salvamento.
SUPPORTED_VERSIONS = {str(i) for i in range(1, SCHEMA_VERSION + 1)}

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE families (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE characters (
    id INTEGER PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
    sex TEXT NOT NULL, birth_year INTEGER NOT NULL, birth_month INTEGER NOT NULL,
    health REAL NOT NULL, alive INTEGER NOT NULL,
    death_year INTEGER, death_month INTEGER,
    mother_id INTEGER, father_id INTEGER, family_id INTEGER,
    personality TEXT NOT NULL, cognition TEXT NOT NULL,
    spouse_id INTEGER,
    cognition_potential TEXT,
    ex_spouse_id INTEGER,
    schooling_years INTEGER,
    in_school INTEGER,
    dropped_out INTEGER,
    school_performance INTEGER,
    returned_to_school INTEGER,
    higher_years INTEGER,
    in_college INTEGER,
    graduated INTEGER,
    occupation TEXT,
    job_start INTEGER,
    seeking_since INTEGER,
    retired INTEGER,
    jobs_held INTEGER,
    rank INTEGER,
    rank_since INTEGER,
    informal INTEGER,
    workplace INTEGER,
    experience INTEGER,
    income REAL,
    wealth REAL,
    unemp_until INTEGER,
    unemp_amount REAL,
    guardian_id INTEGER,
    partner_id INTEGER,
    partner_since INTEGER,
    pregnant_until INTEGER,
    pregnancy_father_id INTEGER,
    leave_until INTEGER
);
CREATE TABLE firms (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, sector TEXT NOT NULL, size TEXT NOT NULL,
    founded INTEGER NOT NULL, closed INTEGER, slots TEXT NOT NULL
);
CREATE TABLE friendships (a INTEGER NOT NULL, b INTEGER NOT NULL, year INTEGER NOT NULL,
    month INTEGER NOT NULL, PRIMARY KEY (a, b));
CREATE TABLE biography (
    seq INTEGER PRIMARY KEY, char_id INTEGER NOT NULL,
    year INTEGER NOT NULL, month INTEGER NOT NULL,
    category TEXT NOT NULL, text TEXT NOT NULL
);
"""


def save_game(game: Game, path: str) -> None:
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    st = game.rng.getstate()
    meta = {
        "schema_version": SCHEMA_VERSION,
        "name": game.name,
        "seed": game.seed,
        "year": game.year,
        "month": game.month,
        "player_id": "" if game.player_id is None else game.player_id,
        "next_char_id": game.next_char_id,
        "next_family_id": game.next_family_id,
        "next_firm_id": game.next_firm_id,
        "rng_state": json.dumps([st[0], list(st[1]), st[2]]),
        "macro": json.dumps(game.macro),
        "decisions": json.dumps(game.decisions),
        "foco": json.dumps(game.foco),
        "convivio": json.dumps([[a, b, m] for (a, b), m in game.convivio.items()]),
        "memoria": json.dumps([[a, b, m] for (a, b), m in game.memoria.items()]),
        "livros": json.dumps(game.livros),
        "convites": json.dumps([[a, b, m] for (a, b), m in game.convites.items()]),
        "area": json.dumps(game.area),
        "educacao_br": json.dumps(game.educacao_br),
        "carreira_extra": json.dumps(game.carreira_extra),
        "politica": json.dumps(game.politica),
        "cidades": json.dumps(game.cidades),
        "patrimonio": json.dumps(game.patrimonio),
        "noticias": json.dumps(game.noticias),
        "intelecto": json.dumps(game.intelecto),
        "psicologia": json.dumps(game.psicologia),
        "vinculos": json.dumps([[a, b, v] for (a, b), v in game.vinculos.items()]),
        "financas_log": json.dumps(game.financas_log),
    }
    con = sqlite3.connect(tmp)
    try:
        with con:
            con.executescript(_SCHEMA)
            con.executemany("INSERT INTO meta VALUES (?, ?)",
                            [(k, str(v)) for k, v in meta.items()])
            con.executemany("INSERT INTO families VALUES (?, ?)",
                            [(f.id, f.name) for f in game.families.values()])
            con.executemany(
                "INSERT INTO characters VALUES (" + ",".join("?" * 46) + ")",
                [(c.id, c.first_name, c.last_name, c.sex, c.birth_year, c.birth_month,
                  c.health, int(c.alive), c.death_year, c.death_month,
                  c.mother_id, c.father_id, c.family_id,
                  json.dumps(c.personality), json.dumps(c.cognition), c.spouse_id,
                  json.dumps(c.cognition_potential), c.ex_spouse_id,
                  c.schooling_years, int(c.in_school), int(c.dropped_out), c.school_performance,
                  int(c.returned_to_school), c.higher_years, int(c.in_college), int(c.graduated),
                  c.occupation, c.job_start, c.seeking_since, int(c.retired), c.jobs_held,
                  c.rank, c.rank_since, int(c.informal), c.workplace, c.experience, c.income, c.wealth,
                  c.unemp_until, c.unemp_amount, c.guardian_id, c.partner_id, c.partner_since,
                  c.pregnant_until, c.pregnancy_father_id, c.leave_until)
                 for c in game.characters.values()])
            con.executemany("INSERT INTO firms VALUES (?,?,?,?,?,?,?)",
                            [(f.id, f.name, f.sector, f.size, f.founded, f.closed, json.dumps(f.slots, sort_keys=True))
                             for f in sorted(game.firms.values(), key=lambda x: x.id)])
            con.executemany("INSERT INTO friendships VALUES (?,?,?,?)",
                            [(a, b, y, m) for (a, b), (y, m) in sorted(game.friendships.items())])
            con.executemany("INSERT INTO biography VALUES (?,?,?,?,?,?)",
                            [(e.seq, e.char_id, e.year, e.month, e.category, e.text)
                             for e in game.biography])
    finally:
        con.close()
    os.replace(tmp, path)


def load_game(path: str) -> Game:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    con = sqlite3.connect(path)
    try:
        try:
            meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"arquivo de save inválido: {exc}") from exc
        if meta.get("schema_version") not in SUPPORTED_VERSIONS:
            raise ValueError(f"versão de save não suportada: {meta.get('schema_version')}")

        g = Game(meta["name"], int(meta["seed"]), int(meta["year"]), int(meta["month"]))
        s = json.loads(meta["rng_state"])
        g.rng.setstate((s[0], tuple(s[1]), s[2]))
        g.player_id = int(meta["player_id"]) if meta["player_id"] != "" else None
        g.next_char_id = int(meta["next_char_id"])
        g.next_family_id = int(meta["next_family_id"])
        if "foco" in meta:   # v0.15.1; antes: todos equilibrados
            g.foco = {int(k): v for k, v in json.loads(meta["foco"]).items()}
        if "convivio" in meta:   # v0.15.4; antes: sem conversas registradas
            g.convivio = {(int(a), int(b)): int(m) for a, b, m in json.loads(meta["convivio"])}
        if "memoria" in meta:   # v0.15.9
            g.memoria = {(int(a), int(b)): int(m) for a, b, m in json.loads(meta["memoria"])}
        if "livros" in meta:   # v0.15.11
            g.livros = {int(k): list(v) for k, v in json.loads(meta["livros"]).items()}
        if "convites" in meta:   # v0.15.6
            g.convites = {(int(a), int(b)): int(m) for a, b, m in json.loads(meta["convites"])}
        if "area" in meta:   # v0.15.2; antes: área geral
            g.area = {int(k): v for k, v in json.loads(meta["area"]).items()}
        if "educacao_br" in meta:
            g.educacao_br = {int(k): v for k, v in json.loads(meta["educacao_br"]).items()}
        if "carreira_extra" in meta:
            g.carreira_extra = {int(k): v for k, v in json.loads(meta["carreira_extra"]).items()}
        if "politica" in meta:
            g.politica = {int(k): v for k, v in json.loads(meta["politica"]).items()}
        if "cidades" in meta:
            g.cidades = {int(k): v for k, v in json.loads(meta["cidades"]).items()}
        if "patrimonio" in meta:
            g.patrimonio = {int(k): v for k, v in json.loads(meta["patrimonio"]).items()}
        if "noticias" in meta:
            g.noticias = list(json.loads(meta["noticias"]))
        if "intelecto" in meta:
            g.intelecto = {int(k): v for k, v in json.loads(meta["intelecto"]).items()}
        if "psicologia" in meta:
            g.psicologia = {int(k): v for k, v in json.loads(meta["psicologia"]).items()}
        if "vinculos" in meta:
            g.vinculos = {(int(a), int(b)): dict(v) for a, b, v in json.loads(meta["vinculos"])}
        if "financas_log" in meta:
            g.financas_log = {int(k): list(v) for k, v in json.loads(meta["financas_log"]).items()}
        if "decisions" in meta:   # v15; antes: sem decisão pendente
            g.decisions.update(json.loads(meta["decisions"]))
        if "macro" in meta:   # v14; antes: preços e salário mínimo no valor inicial, Estado zerado
            g.macro.update(json.loads(meta["macro"]))

        for fid, name in con.execute("SELECT id, name FROM families ORDER BY id"):
            g.families[fid] = Family(fid, name)
        con.row_factory = sqlite3.Row  # colunas por nome: tolera saves v1/v2 (colunas ausentes)
        for r in con.execute("SELECT * FROM characters ORDER BY id"):
            cols = r.keys()

            def opt(name):
                return r[name] if name in cols else None
            ch = Character(
                id=r["id"], first_name=r["first_name"], last_name=r["last_name"], sex=r["sex"],
                birth_year=r["birth_year"], birth_month=r["birth_month"], health=r["health"],
                alive=bool(r["alive"]), death_year=r["death_year"], death_month=r["death_month"],
                mother_id=r["mother_id"], father_id=r["father_id"], family_id=r["family_id"],
                personality=json.loads(r["personality"]), cognition=json.loads(r["cognition"]),
                spouse_id=opt("spouse_id"), ex_spouse_id=opt("ex_spouse_id"))
            pot = json.loads(opt("cognition_potential")) if opt("cognition_potential") else None
            ch.cognition_potential = pot if pot else dict(ch.cognition)
            if opt("schooling_years") is None:  # v1–v4: escolaridade inferida (sem RNG)
                ch.schooling_years, ch.in_school = factory.default_schooling(
                    ch.age_at(g.year, g.month), ch.personality, ch.cognition)
                ch.in_school = ch.in_school and ch.alive
            else:
                ch.schooling_years, ch.in_school = r["schooling_years"], bool(r["in_school"])
                ch.dropped_out, ch.school_performance = bool(r["dropped_out"]), r["school_performance"]
            if opt("higher_years") is not None:  # v6; antes: sem ensino superior
                ch.returned_to_school = bool(opt("returned_to_school"))
                ch.higher_years, ch.in_college = opt("higher_years"), bool(opt("in_college"))
                ch.graduated = bool(opt("graduated"))
            if opt("jobs_held") is not None:  # v7
                ch.occupation, ch.job_start, ch.seeking_since = opt("occupation"), opt("job_start"), opt("seeking_since")
                ch.retired, ch.jobs_held = bool(opt("retired")), opt("jobs_held")
            else:  # v1–v6: situação de trabalho inferida (sem game.rng), gravada no próximo salvamento
                g.characters[ch.id] = ch
                work.default_work(g, ch)
            if opt("wealth") is not None:  # v8
                ch.rank, ch.rank_since, ch.informal = opt("rank"), opt("rank_since"), bool(opt("informal"))
                ch.workplace, ch.experience = opt("workplace"), opt("experience")
                ch.income, ch.wealth = opt("income"), opt("wealth")
            else:  # v1–v7: carreira, renda e patrimônio inferidos (sem game.rng), gravados no próximo salvamento
                economy.initial_economy(g, ch)
            if opt("unemp_amount") is not None:  # v10: seguro-desemprego (v≤9: sem benefício em curso)
                ch.unemp_until, ch.unemp_amount = opt("unemp_until"), opt("unemp_amount")
            ch.guardian_id = opt("guardian_id")  # v11 (antes: sem guarda)
            ch.partner_id, ch.partner_since = opt("partner_id"), opt("partner_since")  # v12 (antes: sem namoro)
            ch.pregnant_until, ch.pregnancy_father_id = opt("pregnant_until"), opt("pregnancy_father_id")  # v13 (antes: sem gestação)
            ch.leave_until = opt("leave_until")  # v14 (antes: sem licença-maternidade)
            g.characters[ch.id] = ch
        con.row_factory = None
        has_firms = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='firms'").fetchone()
        if has_firms:  # v9
            g.next_firm_id = int(meta.get("next_firm_id", 0))
            for fid, name, sector, size, founded, closed, slots in con.execute(
                    "SELECT id, name, sector, size, founded, closed, slots FROM firms ORDER BY id"):
                g.firms[fid] = Firm(fid, name, sector, size, founded, closed, json.loads(slots))
        elif firms.ATIVO:  # v1–v8: empresas criadas e trabalhadores realocados (sem game.rng)
            firms.reconcile(g, force=True)
        has_fr = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='friendships'").fetchone()
        if has_fr:  # v1–v3 não têm a tabela: sem amizades
            for a, b, y, m in con.execute("SELECT a, b, year, month FROM friendships ORDER BY a, b"):
                g.add_friendship(a, b, y, m)
        for seq, cid, y, m, cat, text in con.execute(
                "SELECT seq, char_id, year, month, category, text FROM biography ORDER BY seq"):
            g.biography.append(BioEvent(cid, y, m, cat, text, seq))
        return g
    finally:
        con.close()
