"""Modelos de dados puros (sem regras de simulação e sem interface)."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

PERSONALIDADE = (
    "abertura",
    "conscienciosidade",
    "extroversao",
    "amabilidade",
    "neuroticismo",
)

COGNICAO = (
    "memoria",
    "atencao",
    "raciocinio_logico",
    "abstracao",
    "criatividade",
    "compreensao_verbal",
    "resolucao_problemas",
    "aprendizagem",
)

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


@dataclass
class Character:
    id: int
    first_name: str
    last_name: str
    sex: str  # "F" ou "M"
    birth_year: int
    birth_month: int  # 1..12
    health: float = 100.0
    alive: bool = True
    death_year: int | None = None
    death_month: int | None = None
    mother_id: int | None = None
    father_id: int | None = None
    family_id: int | None = None
    spouse_id: int | None = None
    personality: dict = field(default_factory=dict)
    cognition: dict = field(default_factory=dict)
    # Potencial cognitivo (teto genético): a cognição atual se desenvolve até ele com a idade.
    cognition_potential: dict = field(default_factory=dict)
    ex_spouse_id: int | None = None  # último cônjuge de quem se separou (divórcio)
    # Educação básica: anos concluídos (0–12: 1–9 fundamental, 10–12 médio).
    schooling_years: int = 0
    in_school: bool = False
    dropped_out: bool = False
    school_performance: int | None = None  # desempenho do último ano letivo (0–100)
    returned_to_school: bool = False  # voltou a estudar depois de adulto (retorno aos estudos)
    # Ensino superior (v0.5.0): anos concluídos (0–4), cursando, formado.
    higher_years: int = 0
    in_college: bool = False
    graduated: bool = False
    # Trabalho (v0.6.0): ocupação atual (ou a última, se aposentado), início do vínculo e da procura
    # (mês absoluto = ano*12+mês), aposentadoria e número de empregos já tidos.
    occupation: str | None = None
    job_start: int | None = None
    seeking_since: int | None = None
    retired: bool = False
    jobs_held: int = 0
    # Carreira e economia (v0.7.0): nível na carreira (0–3) e desde quando, vínculo informal,
    # local de trabalho (nº genérico), meses trabalhados, renda mensal atual e patrimônio (R$ constantes).
    rank: int = 0
    rank_since: int | None = None
    informal: bool = False
    workplace: int | None = None
    experience: int = 0
    income: float = 0.0
    wealth: float = 0.0
    # Seguro-desemprego (v0.9.1): último mês absoluto (ano*12+mês) com parcela e valor mensal.
    unemp_until: int | None = None
    unemp_amount: float = 0.0
    # Guarda (v0.10.0): responsável legal de um menor após o divórcio dos pais (None = padrão: mãe, senão pai).
    guardian_id: int | None = None
    # Namoro (v0.11.0): parceiro de namoro (vínculo mútuo) e mês absoluto (ano*12+mês) de início.
    partner_id: int | None = None
    partner_since: int | None = None
    # Gestação (v0.12.0): mês absoluto (ano*12+mês) do parto previsto e pai biológico (None = não grávida).
    pregnant_until: int | None = None
    pregnancy_father_id: int | None = None
    # Licença-maternidade (v0.13.0): afastada do trabalho até este mês absoluto (formal: licença paga com vínculo;
    # quem deixou o emprego para cuidar do bebê: sem procurar trabalho).
    leave_until: int | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def age_at(self, year: int, month: int) -> int:
        """Idade em anos completos na data (ano, mês)."""
        return ((year * 12 + month) - (self.birth_year * 12 + self.birth_month)) // 12


@dataclass
class Family:
    id: int
    name: str


@dataclass
class Firm:
    """Empresa genérica (v0.8.0): sem instituições reais. `slots` = vagas (capacidade) por ocupação;
    `founded`/`closed` em mês absoluto (ano*12+mês); aberta enquanto `closed` é None."""
    id: int
    name: str
    sector: str
    size: str  # micro | pequena | média | grande
    founded: int
    closed: int | None = None
    slots: dict = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return self.closed is None


@dataclass
class BioEvent:
    char_id: int
    year: int
    month: int
    category: str
    text: str
    seq: int = 0


class Game:
    """Estado completo de uma partida."""

    def __init__(self, name: str, seed: int, year: int = 2026, month: int = 1):
        self.name = name
        self.seed = seed
        self.year = year
        self.month = month
        self.rng = random.Random(seed)
        self.characters: dict[int, Character] = {}
        self.families: dict[int, Family] = {}
        self.biography: list[BioEvent] = []
        # Amizades: (id menor, id maior) -> (ano, mês) em que começaram.
        self.friendships: dict[tuple[int, int], tuple[int, int]] = {}
        self._friends: dict[int, set[int]] = {}
        self.player_id: int | None = None
        self.next_char_id = 1
        self.next_family_id = 1
        # Empresas e vagas (v0.8.0): criadas sob demanda por `sim/firms.py` (sem usar `rng`).
        self.firms: dict[int, Firm] = {}
        self.next_firm_id = 0
        # Decisões do jogador (v0.15.0): evento pendente, contador e mês da última (ver sim/decisions.py).
        self.decisions = {"pending": None, "count": 0, "last": 0, "depois": []}
        # Foco do período por personagem do jogador (v0.15.1): id -> nome (ver sim/foco.py).
        self.foco: dict[int, str] = {}
        # Conversas com amigos (v0.15.4): (a, b) -> último mês (ano*12+mês); ver sim/convivio.py.
        self.convivio: dict[tuple[int, int], int] = {}
        self.memoria: dict[tuple[int, int], int] = {}   # v0.15.9: interações por par (ver convivio)
        self.livros: dict[int, list[str]] = {}   # v0.15.11: livros lidos por personagem (ver sim/livros.py)
        self.convites: dict[tuple[int, int], int] = {}   # v0.15.6: convites (ver convivio.convidar)
        # Área de estudo por personagem do jogador (v0.15.2): id -> área (ver sim/foco.py); padrão "geral".
        self.area: dict[int, str] = {}
        # Macroeconomia (v0.13.0): preços, salário mínimo nominal e orçamento do Estado (ver sim/macro.py).
        self.macro = {"price_level": 1.0, "p_ref": 1.0, "min_wage": 1500.0, "inflation_prev": 0.0,
                      "rec": 0.0, "desp": 0.0, "rec_prev": 0.0, "desp_prev": 0.0, "treasury": 0.0}
        # Educação BR, carreiras extras, política e mundo/patrimônio (v0.17.0)
        self.educacao_br: dict[int, dict] = {}
        self.carreira_extra: dict[int, dict] = {}
        self.politica: dict[int, dict] = {}
        self.cidades: dict[int, str] = {}
        self.patrimonio: dict[int, dict] = {}
        self.noticias: list[dict] = []
        self.intelecto: dict[int, dict] = {}
        # Psicologia/metas/hábitos, vínculos multidimensionais e extrato financeiro (v0.20.0)
        self.psicologia: dict[int, dict] = {}
        self.vinculos: dict[tuple[int, int], dict] = {}
        self.financas_log: dict[int, list[dict]] = {}

    # --- calendário -------------------------------------------------
    def date_str(self) -> str:
        return f"{MESES[self.month - 1]} de {self.year}"

    # --- biografia --------------------------------------------------
    def add_event(self, char_id: int, category: str, text: str,
                  year: int | None = None, month: int | None = None) -> BioEvent:
        ev = BioEvent(
            char_id=char_id,
            year=self.year if year is None else year,
            month=self.month if month is None else month,
            category=category,
            text=text,
            seq=len(self.biography),
        )
        self.biography.append(ev)
        return ev

    def events_for(self, char_id: int | None = None, category: str | None = None,
                   from_year: int | None = None, to_year: int | None = None) -> list[BioEvent]:
        """Consulta cronológica da biografia por personagem, categoria e período."""
        out = [
            e for e in self.biography
            if (char_id is None or e.char_id == char_id)
            and (category is None or e.category == category)
            and (from_year is None or e.year >= from_year)
            and (to_year is None or e.year <= to_year)
        ]
        return sorted(out, key=lambda e: (e.year, e.month, e.seq))

    # --- consultas --------------------------------------------------
    # --- amizades ---------------------------------------------------
    def add_friendship(self, a: int, b: int, year: int | None = None, month: int | None = None) -> None:
        if a == b:
            raise ValueError("ninguém é amigo de si mesmo")
        key = (min(a, b), max(a, b))
        self.friendships[key] = (self.year if year is None else year, self.month if month is None else month)
        self._friends.setdefault(a, set()).add(b)
        self._friends.setdefault(b, set()).add(a)

    def remove_friendship(self, a: int, b: int) -> None:
        self.friendships.pop((min(a, b), max(a, b)), None)
        self._friends.get(a, set()).discard(b)
        self._friends.get(b, set()).discard(a)

    def friend_ids(self, char_id: int) -> list[int]:
        return sorted(self._friends.get(char_id, ()))

    def are_friends(self, a: int, b: int) -> bool:
        return b in self._friends.get(a, ())

    def parents_of(self, c: Character) -> list[Character]:
        return [self.characters[i] for i in (c.mother_id, c.father_id) if i in self.characters]

    def children_of(self, char_id: int) -> list[Character]:
        return [c for c in self.characters.values() if char_id in (c.mother_id, c.father_id)]
