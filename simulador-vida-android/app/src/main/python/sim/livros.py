"""Livros (v0.15.11–0.18.0): catálogo de 129 obras reais com páginas, progresso contínuo e áreas de conhecimento.

Mudanças da v0.18.0:
- Leitura baseada em páginas reais e capacidade mensal (`capacidade_mes`), acabando com o limite artificial de "1 livro por mês":
  livros curtos podem ser lidos em conjunto no mesmo mês, enquanto calhamaços avançam em sessões até concluir.
- Progresso salvo em `game.intelecto[cid]["progresso_livros"]` (persiste entre meses e saves).
- Cada livro concede tipos específicos de conhecimento (`conhecimentos`) além de ganhos garantidos de cognição,
  elevando também `cognition_potential` via `engine.treinar_cognicao` para que `compreensao_verbal` nunca trave.
- `view(game)` separa claramente `nao_lidos`, `em_andamento` e `lidos` (para ocultar já lidos e movê-los à aba Lidos).
"""
from __future__ import annotations

from . import engine, intelecto
from .models import Game

CATALOGO = [
    ("reinacoes_narizinho", "Reinações de Narizinho", "Monteiro Lobato", 1931, "infantil", 1),
    ("pequeno_principe", "O Pequeno Príncipe", "Antoine de Saint-Exupéry", 1943, "fábula", 1),
    ("alice", "Alice no País das Maravilhas", "Lewis Carroll", 1865, "fantasia", 1),
    ("ou_isto_ou_aquilo", "Ou Isto ou Aquilo", "Cecília Meireles", 1964, "poesia", 1),
    ("flicts", "Flicts", "Ziraldo", 1969, "infantil", 1),
    ("arca_de_noe", "A Arca de Noé", "Vinicius de Moraes", 1970, "poesia", 1),
    ("marcelo_marmelo", "Marcelo, Marmelo, Martelo", "Ruth Rocha", 1976, "infantil", 1),
    ("bolsa_amarela", "A Bolsa Amarela", "Lygia Bojunga", 1976, "infantil", 1),
    ("menino_maluquinho", "O Menino Maluquinho", "Ziraldo", 1980, "infantil", 1),
    ("menina_bonita", "Menina Bonita do Laço de Fita", "Ana Maria Machado", 1986, "infantil", 1),
    ("pinoquio", "As Aventuras de Pinóquio", "Carlo Collodi", 1883, "infantil", 1),
    ("magico_de_oz", "O Mágico de Oz", "L. Frank Baum", 1900, "fantasia", 1),
    ("jardim_secreto", "O Jardim Secreto", "Frances Hodgson Burnett", 1911, "infantil", 1),
    ("peter_pan", "Peter Pan", "J. M. Barrie", 1911, "fantasia", 1),
    ("narnia_leao", "O Leão, a Feiticeira e o Guarda-Roupa", "C. S. Lewis", 1950, "fantasia", 1),
    ("laranja_lima", "O Meu Pé de Laranja Lima", "José Mauro de Vasconcelos", 1968, "infantojuvenil", 2),
    ("droga_obediencia", "A Droga da Obediência", "Pedro Bandeira", 1984, "aventura", 2),
    ("hobbit", "O Hobbit", "J. R. R. Tolkien", 1937, "fantasia", 2),
    ("robinson_crusoe", "Robinson Crusoé", "Daniel Defoe", 1719, "aventura", 2),
    ("viagens_gulliver", "As Viagens de Gulliver", "Jonathan Swift", 1726, "aventura", 2),
    ("ilha_tesouro", "A Ilha do Tesouro", "Robert Louis Stevenson", 1883, "aventura", 2),
    ("viagem_centro_terra", "Viagem ao Centro da Terra", "Júlio Verne", 1864, "ficção científica", 2),
    ("vinte_mil_leguas", "Vinte Mil Léguas Submarinas", "Júlio Verne", 1870, "ficção científica", 2),
    ("volta_mundo_80", "A Volta ao Mundo em 80 Dias", "Júlio Verne", 1872, "aventura", 2),
    ("tres_mosqueteiros", "Os Três Mosqueteiros", "Alexandre Dumas", 1844, "aventura", 2),
    ("conde_monte_cristo", "O Conde de Monte Cristo", "Alexandre Dumas", 1845, "aventura", 2),
    ("moreninha", "A Moreninha", "Joaquim Manuel de Macedo", 1844, "romance", 2),
    ("sargento_milicias", "Memórias de um Sargento de Milícias", "Manuel Antônio de Almeida", 1854, "romance", 2),
    ("o_guarani", "O Guarani", "José de Alencar", 1857, "romance", 2),
    ("luciola", "Lucíola", "José de Alencar", 1862, "romance", 2),
    ("iracema", "Iracema", "José de Alencar", 1865, "romance", 2),
    ("inocencia", "Inocência", "Visconde de Taunay", 1872, "romance", 2),
    ("escrava_isaura", "A Escrava Isaura", "Bernardo Guimarães", 1875, "romance", 2),
    ("senhora", "Senhora", "José de Alencar", 1875, "romance", 2),
    ("alienista", "O Alienista", "Machado de Assis", 1882, "conto", 2),
    ("bras_cubas", "Memórias Póstumas de Brás Cubas", "Machado de Assis", 1881, "romance", 3),
    ("quincas_borba", "Quincas Borba", "Machado de Assis", 1891, "romance", 3),
    ("dom_casmurro", "Dom Casmurro", "Machado de Assis", 1899, "romance", 3),
    ("o_ateneu", "O Ateneu", "Raul Pompeia", 1888, "romance", 3),
    ("o_mulato", "O Mulato", "Aluísio Azevedo", 1881, "romance", 3),
    ("o_cortico", "O Cortiço", "Aluísio Azevedo", 1890, "romance", 3),
    ("os_sertoes", "Os Sertões", "Euclides da Cunha", 1902, "história", 3),
    ("policarpo_quaresma", "Triste Fim de Policarpo Quaresma", "Lima Barreto", 1915, "romance", 3),
    ("macunaima", "Macunaíma", "Mário de Andrade", 1928, "romance", 3),
    ("o_quinze", "O Quinze", "Rachel de Queiroz", 1930, "romance", 2),
    ("cacau", "Cacau", "Jorge Amado", 1933, "romance", 3),
    ("capitaes_areia", "Capitães da Areia", "Jorge Amado", 1937, "romance", 2),
    ("sao_bernardo", "São Bernardo", "Graciliano Ramos", 1934, "romance", 3),
    ("vidas_secas", "Vidas Secas", "Graciliano Ramos", 1938, "romance", 2),
    ("angustia", "Angústia", "Graciliano Ramos", 1936, "romance", 3),
    ("fogo_morto", "Fogo Morto", "José Lins do Rego", 1943, "romance", 3),
    ("tempo_e_vento", "O Tempo e o Vento (O Continente)", "Érico Veríssimo", 1949, "romance", 3),
    ("sentimento_mundo", "Sentimento do Mundo", "Carlos Drummond de Andrade", 1940, "poesia", 3),
    ("rosa_do_povo", "A Rosa do Povo", "Carlos Drummond de Andrade", 1945, "poesia", 3),
    ("romanceiro_inconfidencia", "Romanceiro da Inconfidência", "Cecília Meireles", 1953, "poesia", 3),
    ("morte_vida_severina", "Morte e Vida Severina", "João Cabral de Melo Neto", 1955, "poesia", 2),
    ("grande_sertao", "Grande Sertão: Veredas", "João Guimarães Rosa", 1956, "romance", 3),
    ("gabriela_cravo", "Gabriela, Cravo e Canela", "Jorge Amado", 1958, "romance", 3),
    ("quarto_despejo", "Quarto de Despejo", "Carolina Maria de Jesus", 1960, "biografia", 2),
    ("hora_estrela", "A Hora da Estrela", "Clarice Lispector", 1977, "romance", 3),
    ("os_lusiadas", "Os Lusíadas", "Luís Vaz de Camões", 1572, "poesia", 3),
    ("padre_amaro", "O Crime do Padre Amaro", "Eça de Queirós", 1875, "romance", 3),
    ("primo_basilio", "O Primo Basílio", "Eça de Queirós", 1878, "romance", 3),
    ("os_maias", "Os Maias", "Eça de Queirós", 1888, "romance", 3),
    ("divina_comedia", "A Divina Comédia", "Dante Alighieri", 1321, "poesia", 3),
    ("romeu_julieta", "Romeu e Julieta", "William Shakespeare", 1597, "teatro", 2),
    ("hamlet", "Hamlet", "William Shakespeare", 1603, "teatro", 3),
    ("dom_quixote", "Dom Quixote", "Miguel de Cervantes", 1605, "romance", 3),
    ("orgulho_preconceito", "Orgulho e Preconceito", "Jane Austen", 1813, "romance", 3),
    ("frankenstein", "Frankenstein", "Mary Shelley", 1818, "ficção científica", 3),
    ("jane_eyre", "Jane Eyre", "Charlotte Brontë", 1847, "romance", 3),
    ("morro_ventos", "O Morro dos Ventos Uivantes", "Emily Brontë", 1847, "romance", 3),
    ("moby_dick", "Moby Dick", "Herman Melville", 1851, "aventura", 3),
    ("madame_bovary", "Madame Bovary", "Gustave Flaubert", 1857, "romance", 3),
    ("miseraveis", "Os Miseráveis", "Victor Hugo", 1862, "romance", 3),
    ("crime_castigo", "Crime e Castigo", "Fiódor Dostoiévski", 1866, "romance", 3),
    ("guerra_e_paz", "Guerra e Paz", "Liev Tolstói", 1869, "romance", 3),
    ("anna_karenina", "Anna Karenina", "Liev Tolstói", 1877, "romance", 3),
    ("irmaos_karamazov", "Os Irmãos Karamázov", "Fiódor Dostoiévski", 1880, "romance", 3),
    ("metamorfose", "A Metamorfose", "Franz Kafka", 1915, "novela", 3),
    ("o_processo", "O Processo", "Franz Kafka", 1925, "romance", 3),
    ("grande_gatsby", "O Grande Gatsby", "F. Scott Fitzgerald", 1925, "romance", 3),
    ("admiravel_mundo_novo", "Admirável Mundo Novo", "Aldous Huxley", 1932, "ficção científica", 3),
    ("o_estrangeiro", "O Estrangeiro", "Albert Camus", 1942, "romance", 3),
    ("revolucao_bichos", "A Revolução dos Bichos", "George Orwell", 1945, "fábula política", 2),
    ("a_peste", "A Peste", "Albert Camus", 1947, "romance", 3),
    ("mil_novecentos_84", "1984", "George Orwell", 1949, "ficção científica", 3),
    ("apanhador_centeio", "O Apanhador no Campo de Centeio", "J. D. Salinger", 1951, "romance", 2),
    ("fundacao", "Fundação", "Isaac Asimov", 1951, "ficção científica", 3),
    ("velho_e_o_mar", "O Velho e o Mar", "Ernest Hemingway", 1952, "novela", 2),
    ("fahrenheit_451", "Fahrenheit 451", "Ray Bradbury", 1953, "ficção científica", 3),
    ("sol_para_todos", "O Sol é Para Todos", "Harper Lee", 1960, "romance", 2),
    ("duna", "Duna", "Frank Herbert", 1965, "ficção científica", 3),
    ("cem_anos", "Cem Anos de Solidão", "Gabriel García Márquez", 1967, "romance", 3),
    ("o_principe", "O Príncipe", "Nicolau Maquiavel", 1532, "política", 3),
    ("discurso_metodo", "Discurso do Método", "René Descartes", 1637, "filosofia", 3),
    ("leviata", "Leviatã", "Thomas Hobbes", 1651, "política", 3),
    ("principia", "Princípios Matemáticos da Filosofia Natural", "Isaac Newton", 1687, "física", 3),
    ("espirito_leis", "O Espírito das Leis", "Montesquieu", 1748, "direito", 3),
    ("contrato_social", "Do Contrato Social", "Jean-Jacques Rousseau", 1762, "política", 3),
    ("delitos_penas", "Dos Delitos e das Penas", "Cesare Beccaria", 1764, "direito", 3),
    ("riqueza_nacoes", "A Riqueza das Nações", "Adam Smith", 1776, "economia", 3),
    ("critica_razao_pura", "Crítica da Razão Pura", "Immanuel Kant", 1781, "filosofia", 3),
    ("manifesto", "Manifesto do Partido Comunista", "Karl Marx e Friedrich Engels", 1848, "política", 3),
    ("origem_especies", "A Origem das Espécies", "Charles Darwin", 1859, "biologia", 3),
    ("o_capital", "O Capital (livro I)", "Karl Marx", 1867, "economia", 3),
    ("zaratustra", "Assim Falou Zaratustra", "Friedrich Nietzsche", 1883, "filosofia", 3),
    ("o_suicidio", "O Suicídio", "Émile Durkheim", 1897, "sociologia", 3),
    ("interpretacao_sonhos", "A Interpretação dos Sonhos", "Sigmund Freud", 1899, "psicologia", 3),
    ("etica_protestante", "A Ética Protestante e o Espírito do Capitalismo", "Max Weber", 1905, "sociologia", 3),
    ("curso_linguistica", "Curso de Linguística Geral", "Ferdinand de Saussure", 1916, "linguística", 3),
    ("casa_grande_senzala", "Casa-Grande & Senzala", "Gilberto Freyre", 1933, "sociologia", 3),
    ("logica_pesquisa", "A Lógica da Pesquisa Científica", "Karl Popper", 1934, "filosofia", 3),
    ("raizes_do_brasil", "Raízes do Brasil", "Sérgio Buarque de Holanda", 1936, "história", 3),
    ("teoria_geral", "A Teoria Geral do Emprego, do Juro e da Moeda", "John Maynard Keynes", 1936, "economia", 3),
    ("formacao_brasil_cont", "Formação do Brasil Contemporâneo", "Caio Prado Júnior", 1942, "história", 3),
    ("geografia_fome", "Geografia da Fome", "Josué de Castro", 1946, "geografia", 3),
    ("segundo_sexo", "O Segundo Sexo", "Simone de Beauvoir", 1949, "filosofia", 3),
    ("condicao_humana", "A Condição Humana", "Hannah Arendt", 1958, "filosofia", 3),
    ("formacao_economica", "Formação Econômica do Brasil", "Celso Furtado", 1959, "economia", 3),
    ("revolucoes_cientificas", "A Estrutura das Revoluções Científicas", "Thomas Kuhn", 1962, "filosofia", 3),
    ("pedagogia_oprimido", "Pedagogia do Oprimido", "Paulo Freire", 1968, "educação", 3),
    ("vigiar_e_punir", "Vigiar e Punir", "Michel Foucault", 1975, "sociologia", 3),
    ("gene_egoista", "O Gene Egoísta", "Richard Dawkins", 1976, "biologia", 3),
    ("cosmos", "Cosmos", "Carl Sagan", 1980, "ciência", 2),
    ("breve_historia_tempo", "Uma Breve História do Tempo", "Stephen Hawking", 1988, "física", 3),
    ("povo_brasileiro", "O Povo Brasileiro", "Darcy Ribeiro", 1995, "sociologia", 3),
    ("sapiens", "Sapiens", "Yuval Noah Harari", 2011, "história", 3),
    ("rapido_e_devagar", "Rápido e Devagar", "Daniel Kahneman", 2011, "psicologia", 3),
    # --- Lote v0.20.0 (expansão para 205 obras reais verificadas) ---
    ("elementos_euclides", "Os Elementos", "Euclides", -300, "matemática", 3),
    ("etica_nicomaco", "Ética a Nicômaco", "Aristóteles", -340, "filosofia", 3),
    ("a_republica", "A República", "Platão", -375, "filosofia", 3),
    ("meditacoes_marcus", "Meditações", "Marco Aurélio", 180, "filosofia", 2),
    ("iliada", "Ilíada", "Homero", -750, "poesia", 3),
    ("odisseia", "Odisseia", "Homero", -720, "poesia", 3),
    ("arte_da_guerra", "A Arte da Guerra", "Sun Tzu", -500, "política", 2),
    ("dialogo_galileu", "Diálogo sobre os Dois Máximos Sistemas do Mundo", "Galileu Galilei", 1632, "física", 3),
    ("tratado_tolerancia", "Tratado sobre a Tolerância", "Voltaire", 1763, "filosofia", 3),
    ("candido", "Cândido, ou o Otimismo", "Voltaire", 1759, "novela", 2),
    ("fausto", "Fausto", "Johann Wolfgang von Goethe", 1808, "teatro", 3),
    ("utopia", "Utopia", "Thomas More", 1516, "filosofia", 3),
    ("meditacoes_descartes", "Meditações Metafísicas", "René Descartes", 1641, "filosofia", 3),
    ("etica_spinoza", "Ética", "Baruch Spinoza", 1677, "filosofia", 3),
    ("segundo_tratado_governo", "Segundo Tratado sobre o Governo Civil", "John Locke", 1689, "política", 3),
    ("federalista", "O Federalista", "Alexander Hamilton, James Madison e John Jay", 1788, "direito", 3),
    ("democracia_america", "A Democracia na América", "Alexis de Tocqueville", 1835, "política", 3),
    ("sobre_liberdade", "Sobre a Liberdade", "John Stuart Mill", 1859, "filosofia", 3),
    ("alemanha_humboldt", "Quadros da Natureza", "Alexander von Humboldt", 1808, "geografia", 3),
    ("tabela_periodica_mendeleev", "Princípios de Química", "Dmitri Mendeleev", 1869, "química", 3),
    ("teoria_relatividade", "Sobre a Teoria da Relatividade Especial e Geral", "Albert Einstein", 1916, "física", 3),
    ("o_que_e_vida", "O Que é Vida?", "Erwin Schrödinger", 1944, "biologia", 3),
    ("licoes_fisica_feynman", "Lições de Física (Vol. 1)", "Richard Feynman", 1963, "física", 3),
    ("tio_tungstenio", "Tio Tungstênio", "Oliver Sacks", 2001, "química", 2),
    ("homem_confundiu_mulher", "O Homem que Confundiu sua Mulher com um Chapéu", "Oliver Sacks", 1985, "psicologia", 2),
    ("codigo_turing", "Computação e Inteligência", "Alan Turing", 1950, "tecnologia", 3),
    ("arte_programar", "A Arte da Programação de Computadores (Vol. 1)", "Donald Knuth", 1968, "tecnologia", 3),
    ("homem_que_calculava", "O Homem que Calculava", "Malba Tahan", 1938, "matemática", 2),
    ("apologia_matematico", "Em Defesa de um Matemático", "G. H. Hardy", 1940, "matemática", 2),
    ("como_resolver", "A Arte de Resolver Problemas", "George Pólya", 1945, "matemática", 2),
    ("estruturas_gordon", "Estruturas, ou Por Que as Coisas Não Caem", "J. E. Gordon", 1978, "engenharia", 2),
    ("design_coisas", "O Design do Dia a Dia", "Donald Norman", 1988, "engenharia", 2),
    ("primavera_silenciosa", "Primavera Silenciosa", "Rachel Carson", 1962, "biologia", 2),
    ("dupla_helice", "A Dupla Hélice", "James D. Watson", 1968, "biologia", 2),
    ("mundo_assombrado", "O Mundo Assombrado pelos Demônios", "Carl Sagan", 1995, "ciência", 2),
    ("natureza_espaco", "A Natureza do Espaço", "Milton Santos", 1996, "geografia", 3),
    ("por_uma_outra_glob", "Por uma Outra Globalização", "Milton Santos", 2000, "geografia", 3),
    ("historia_econ_brasil", "História Econômica do Brasil", "Caio Prado Júnior", 1945, "economia", 3),
    ("casa_dos_espiritos", "A Casa dos Espíritos", "Isabel Allende", 1982, "romance", 2),
    ("pedro_paramo", "Pedro Páramo", "Juan Rulfo", 1955, "romance", 3),
    ("ficcoes_borges", "Ficções", "Jorge Luis Borges", 1944, "conto", 3),
    ("rayuela", "O Jogo da Amarelinha", "Julio Cortázar", 1963, "romance", 3),
    ("nome_da_rosa", "O Nome da Rosa", "Umberto Eco", 1980, "romance", 3),
    ("se_isto_e_um_homem", "É Isto um Homem?", "Primo Levi", 1947, "biografia", 3),
    ("diario_anne_frank", "O Diário de Anne Frank", "Anne Frank", 1947, "biografia", 2),
    ("dracula", "Drácula", "Bram Stoker", 1897, "romance", 2),
    ("retrato_dorian", "O Retrato de Dorian Gray", "Oscar Wilde", 1890, "romance", 2),
    ("coracao_das_trevas", "O Coração das Trevas", "Joseph Conrad", 1899, "novela", 3),
    ("ulisses_joyce", "Ulisses", "James Joyce", 1922, "romance", 3),
    ("mrs_dalloway", "Mrs. Dalloway", "Virginia Woolf", 1925, "romance", 3),
    ("vinhas_da_ira", "As Vinhas da Ira", "John Steinbeck", 1939, "romance", 3),
    ("sol_nasce_hemingway", "O Sol Também se Levanta", "Ernest Hemingway", 1926, "romance", 2),
    ("ensaios_cegueira", "Ensaio sobre a Cegueira", "José Saramago", 1995, "romance", 3),
    ("memorial_convento", "Memorial do Convento", "José Saramago", 1982, "romance", 3),
    ("livro_desassossego", "Livro do Desassossego", "Fernando Pessoa", 1982, "filosofia", 3),
    ("mensagem_pessoa", "Mensagem", "Fernando Pessoa", 1934, "poesia", 2),
    ("primeiras_estorias", "Primeiras Estórias", "Guimarães Rosa", 1962, "conto", 3),
    ("sagarana", "Sagarana", "Guimarães Rosa", 1946, "conto", 3),
    ("lacos_familia", "Laços de Família", "Clarice Lispector", 1960, "conto", 2),
    ("perto_coracao_selvagem", "Perto do Coração Selvagem", "Clarice Lispector", 1943, "romance", 3),
    ("memorias_carcere", "Memórias do Cárcere", "Graciliano Ramos", 1953, "biografia", 3),
    ("menino_engenho", "Menino de Engenho", "José Lins do Rego", 1932, "romance", 2),
    ("mar_morto", "Mar Morto", "Jorge Amado", 1936, "romance", 2),
    ("dona_flor", "Dona Flor e Seus Dois Maridos", "Jorge Amado", 1966, "romance", 2),
    ("ciranda_pedra", "Ciranda de Pedra", "Lygia Fagundes Telles", 1954, "romance", 2),
    ("meninas_lygia", "As Meninas", "Lygia Fagundes Telles", 1973, "romance", 3),
    ("lavoura_arcaica", "Lavoura Arcaica", "Raduan Nassar", 1975, "romance", 3),
    ("relato_certo_oriente", "Relato de um Certo Oriente", "Milton Hatoum", 1989, "romance", 2),
    ("poncia_vicencio", "Ponciá Vicêncio", "Conceição Evaristo", 2003, "romance", 2),
    ("torto_arado", "Torto Arado", "Itamar Vieira Junior", 2019, "romance", 2),
    ("auto_barca_inferno", "Auto da Barca do Inferno", "Gil Vicente", 1517, "teatro", 2),
    ("navio_negreiro", "O Navio Negreiro", "Castro Alves", 1869, "poesia", 2),
    ("alguma_poesia", "Alguma Poesia", "Carlos Drummond de Andrade", 1930, "poesia", 2),
    ("educacao_pela_pedra", "A Educação pela Pedra", "João Cabral de Melo Neto", 1966, "poesia", 3),
    ("historia_riqueza_homem", "História da Riqueza do Homem", "Leo Huberman", 1936, "economia", 2),
    ("economia_basica_sowell", "Economia Básica", "Thomas Sowell", 2000, "economia", 2),
]
_POR_ID = {x[0]: x for x in CATALOGO}
IDADE_MIN = {1: 6, 2: 12, 3: 15}
VERBAL_MIN = {1: 10, 2: 24, 3: 38}

PAGINAS_POR_ID = {
    "reinacoes_narizinho": 192, "pequeno_principe": 96, "alice": 160, "ou_isto_ou_aquilo": 64,
    "flicts": 48, "arca_de_noe": 72, "marcelo_marmelo": 64, "bolsa_amarela": 144,
    "menino_maluquinho": 112, "menina_bonita": 32, "pinoquio": 192, "magico_de_oz": 176,
    "jardim_secreto": 288, "peter_pan": 208, "narnia_leao": 184, "laranja_lima": 192,
    "droga_obediencia": 176, "hobbit": 320, "robinson_crusoe": 320, "viagens_gulliver": 312,
    "ilha_tesouro": 240, "viagem_centro_terra": 256, "vinte_mil_leguas": 416, "volta_mundo_80": 240,
    "tres_mosqueteiros": 672, "conde_monte_cristo": 1248, "moreninha": 184, "sargento_milicias": 192,
    "o_guarani": 368, "luciola": 160, "iracema": 144, "inocencia": 208,
    "escrava_isaura": 192, "senhora": 288, "alienista": 96, "bras_cubas": 240,
    "quincas_borba": 272, "dom_casmurro": 256, "o_ateneu": 256, "o_mulato": 304,
    "o_cortico": 272, "os_sertoes": 624, "policarpo_quaresma": 224, "macunaima": 208,
    "o_quinze": 160, "cacau": 144, "capitaes_areia": 280, "sao_bernardo": 208,
    "vidas_secas": 176, "angustia": 256, "fogo_morto": 368, "tempo_e_vento": 672,
    "sentimento_mundo": 96, "rosa_do_povo": 192, "romanceiro_inconfidencia": 240,
    "morte_vida_severina": 96, "grande_sertao": 608, "gabriela_cravo": 416,
    "quarto_despejo": 200, "hora_estrela": 96, "os_lusiadas": 384, "padre_amaro": 512,
    "primo_basilio": 432, "os_maias": 720, "divina_comedia": 560, "romeu_julieta": 144,
    "hamlet": 176, "dom_quixote": 1056, "orgulho_preconceito": 416, "frankenstein": 240,
    "jane_eyre": 560, "morro_ventos": 384, "moby_dick": 656, "madame_bovary": 368,
    "miseraveis": 1512, "crime_castigo": 592, "guerra_e_paz": 1536, "anna_karenina": 864,
    "irmaos_karamazov": 928, "metamorfose": 104, "o_processo": 272, "grande_gatsby": 208,
    "admiravel_mundo_novo": 288, "o_estrangeiro": 136, "revolucao_bichos": 152, "a_peste": 304,
    "mil_novecentos_84": 336, "apanhador_centeio": 256, "fundacao": 272, "velho_e_o_mar": 128,
    "fahrenheit_451": 216, "sol_para_todos": 368, "duna": 688, "cem_anos": 448,
    "o_principe": 144, "discurso_metodo": 112, "leviata": 576, "principia": 544,
    "espirito_leis": 768, "contrato_social": 176, "delitos_penas": 144, "riqueza_nacoes": 960,
    "critica_razao_pura": 720, "manifesto": 80, "origem_especies": 528, "o_capital": 896,
    "zaratustra": 368, "o_suicidio": 448, "interpretacao_sonhos": 640, "etica_protestante": 288,
    "curso_linguistica": 312, "casa_grande_senzala": 736, "logica_pesquisa": 544,
    "raizes_do_brasil": 224, "teoria_geral": 432, "formacao_brasil_cont": 400,
    "geografia_fome": 320, "segundo_sexo": 928, "condicao_humana": 416,
    "formacao_economica": 352, "revolucoes_cientificas": 264, "pedagogia_oprimido": 256,
    "vigiar_e_punir": 312, "gene_egoista": 384, "cosmos": 384, "breve_historia_tempo": 256,
    "povo_brasileiro": 480, "sapiens": 464, "rapido_e_devagar": 608,
    "elementos_euclides": 544, "etica_nicomaco": 320, "a_republica": 416, "meditacoes_marcus": 192,
    "iliada": 576, "odisseia": 480, "arte_da_guerra": 128, "dialogo_galileu": 512,
    "tratado_tolerancia": 192, "candido": 144, "fausto": 528, "utopia": 160,
    "meditacoes_descartes": 128, "etica_spinoza": 352, "segundo_tratado_governo": 208,
    "federalista": 592, "democracia_america": 768, "sobre_liberdade": 176,
    "alemanha_humboldt": 368, "tabela_periodica_mendeleev": 480, "teoria_relatividade": 160,
    "o_que_e_vida": 144, "licoes_fisica_feynman": 560, "tio_tungstenio": 384,
    "homem_confundiu_mulher": 272, "codigo_turing": 96, "arte_programar": 672,
    "homem_que_calculava": 288, "apologia_matematico": 144, "como_resolver": 240,
    "estruturas_gordon": 384, "design_coisas": 320, "primavera_silenciosa": 336,
    "dupla_helice": 208, "mundo_assombrado": 512, "natureza_espaco": 384,
    "por_uma_outra_glob": 176, "historia_econ_brasil": 352, "casa_dos_espiritos": 448,
    "pedro_paramo": 144, "ficcoes_borges": 192, "rayuela": 624, "nome_da_rosa": 560,
    "se_isto_e_um_homem": 224, "diario_anne_frank": 352, "dracula": 464,
    "retrato_dorian": 272, "coracao_das_trevas": 144, "ulisses_joyce": 960,
    "mrs_dalloway": 224, "vinhas_da_ira": 592, "sol_nasce_hemingway": 256,
    "ensaios_cegueira": 312, "memorial_convento": 368, "livro_desassossego": 528,
    "mensagem_pessoa": 112, "primeiras_estorias": 192, "sagarana": 368,
    "lacos_familia": 160, "perto_coracao_selvagem": 208, "memorias_carcere": 688,
    "menino_engenho": 160, "mar_morto": 272, "dona_flor": 544, "ciranda_pedra": 224,
    "meninas_lygia": 288, "lavoura_arcaica": 192, "relato_certo_oriente": 160,
    "poncia_vicencio": 144, "torto_arado": 264, "auto_barca_inferno": 96,
    "navio_negreiro": 64, "alguma_poesia": 96, "educacao_pela_pedra": 112,
    "historia_riqueza_homem": 320, "economia_basica_sowell": 624,
}

GENERO_COGNICAO = {
    "infantil": "criatividade", "fábula": "criatividade", "fantasia": "criatividade", "poesia": "criatividade",
    "infantojuvenil": "atencao", "aventura": "atencao", "teatro": "compreensao_verbal", "conto": "compreensao_verbal",
    "novela": "abstracao", "romance": "memoria", "biografia": "memoria",
    "ficção científica": "abstracao", "fábula política": "abstracao", "filosofia": "abstracao",
    "política": "resolucao_problemas", "direito": "resolucao_problemas",
    "economia": "raciocinio_logico", "física": "raciocinio_logico", "matemática": "raciocinio_logico",
    "química": "aprendizagem", "engenharia": "resolucao_problemas", "tecnologia": "raciocinio_logico",
    "biologia": "aprendizagem", "ciência": "aprendizagem", "sociologia": "aprendizagem",
    "história": "memoria", "geografia": "memoria", "educação": "aprendizagem",
    "psicologia": "atencao", "linguística": "compreensao_verbal",
}

GENERO_AREAS = {
    "infantil": ("linguagem", "artes"),
    "fábula": ("linguagem", "filosofia"),
    "fantasia": ("artes", "linguagem"),
    "poesia": ("artes", "linguagem"),
    "infantojuvenil": ("linguagem", "psicologia"),
    "aventura": ("linguagem", "humanas"),
    "teatro": ("artes", "linguagem"),
    "conto": ("linguagem", "psicologia"),
    "novela": ("linguagem", "filosofia"),
    "romance": ("linguagem", "humanas"),
    "biografia": ("humanas", "psicologia"),
    "ficção científica": ("ciencias", "filosofia"),
    "fábula política": ("direito", "humanas"),
    "filosofia": ("filosofia", "linguagem"),
    "política": ("direito", "humanas"),
    "direito": ("direito", "filosofia"),
    "economia": ("economia", "humanas"),
    "física": ("ciencias", "filosofia"),
    "biologia": ("ciencias",),
    "ciência": ("ciencias", "filosofia"),
    "sociologia": ("humanas", "direito"),
    "história": ("humanas",),
    "geografia": ("humanas", "economia"),
    "educação": ("humanas", "psicologia"),
    "psicologia": ("psicologia", "ciencias"),
    "linguística": ("linguagem", "filosofia"),
    "matemática": ("economia", "ciencias"),
    "química": ("ciencias",),
    "engenharia": ("economia", "ciencias"),
    "tecnologia": ("ciencias", "economia"),
}

CONHECIMENTOS_OBRA = {
    "dom_casmurro": ("linguagem", "psicologia"),
    "bras_cubas": ("linguagem", "filosofia"),
    "crime_castigo": ("linguagem", "psicologia"),
    "os_sertoes": ("humanas", "ciencias"),
    "pedagogia_oprimido": ("humanas", "filosofia"),
    "vigiar_e_punir": ("direito", "humanas"),
    "o_capital": ("economia", "humanas"),
    "riqueza_nacoes": ("economia", "filosofia"),
    "teoria_geral": ("economia",),
    "formacao_economica": ("economia", "humanas"),
    "sapiens": ("humanas", "ciencias"),
    "rapido_e_devagar": ("psicologia", "economia"),
    "mil_novecentos_84": ("direito", "ciencias"),
    "admiravel_mundo_novo": ("ciencias", "filosofia"),
    "o_principe": ("direito", "humanas"),
    "espirito_leis": ("direito", "filosofia"),
    "principia": ("ciencias",),
    "breve_historia_tempo": ("ciencias",),
    "cosmos": ("ciencias", "artes"),
}


def paginas_livro(livro_id: str) -> int:
    if livro_id in PAGINAS_POR_ID:
        return PAGINAS_POR_ID[livro_id]
    obra = _POR_ID.get(livro_id)
    if not obra:
        return 200
    return {1: 120, 2: 240, 3: 360}[obra[5]]


def conhecimentos_livro(livro_id: str) -> tuple[str, ...]:
    if livro_id in CONHECIMENTOS_OBRA:
        return CONHECIMENTOS_OBRA[livro_id]
    obra = _POR_ID.get(livro_id)
    if not obra:
        return ("linguagem",)
    return GENERO_AREAS.get(obra[4], ("linguagem",))


def _jogador(game: Game):
    p = game.characters.get(game.player_id) if game.player_id is not None else None
    return p if p is not None and p.alive else None


def _mes(game: Game) -> int:
    return game.year * 12 + game.month


def _motivo(game: Game, p, nivel: int, lido: bool) -> str | None:
    if lido:
        return "Já lido."
    if p.age_at(game.year, game.month) < IDADE_MIN[nivel]:
        return f"A partir de {IDADE_MIN[nivel]} anos."
    if p.cognition.get("compreensao_verbal", 0) < VERBAL_MIN[nivel]:
        return f"Exige compreensão verbal {VERBAL_MIN[nivel]}."
    return None


def capacidade_mes(game: Game, p) -> int:
    """Capacidade de leitura em páginas/mês baseada na idade, atenção, compreensão verbal, foco, hábito e biblioteca."""
    idade = p.age_at(game.year, game.month)
    base = 180 if idade < 10 else 280 if idade < 14 else 350 if idade < 18 else 400
    at = p.cognition.get("atencao", 50)
    vb = p.cognition.get("compreensao_verbal", 50)
    bonus_foco = 160 if game.foco.get(p.id) == "estudar" else 0
    psi = game.psicologia.get(p.id)
    bonus_hab = 120 if (psi and "leitura_diaria" in psi.get("habitos", [])) else 0
    pat = game.patrimonio.get(p.id)
    bonus_bib = 150 if (pat and "biblioteca" in pat.get("equipamentos", [])) else 0
    return max(220, int(round(base + (at + vb) * 2.2 + bonus_foco + bonus_hab + bonus_bib)))


def paginas_usadas_mes(game: Game, cid: int) -> int:
    st = intelecto.dados(game, cid)
    pm = st.get("paginas_mes")
    mes = _mes(game)
    if isinstance(pm, list) and len(pm) == 2 and pm[0] == mes:
        return int(pm[1])
    return 0


def interesses(game: Game, char_id: int) -> dict[str, int]:
    cont: dict[str, int] = {}
    for lid in game.livros.get(char_id, []):
        obra = _POR_ID.get(lid)
        if obra is not None:
            g = obra[4]
            cont[g] = cont.get(g, 0) + 1
    return dict(sorted(cont.items(), key=lambda kv: (-kv[1], kv[0])))


def view(game: Game, genero: str | None = None, busca: str | None = None) -> dict:
    p = _jogador(game)
    generos = sorted({x[4] for x in CATALOGO})
    if p is None:
        return {
            "disponivel": False, "motivo": "Nenhum personagem vivo.", "itens": [],
            "nao_lidos": [], "em_andamento": [], "lidos": [],
            "total_lidos": 0, "total_catalogo": len(CATALOGO),
            "paginas_mes_total": 0, "paginas_mes_usadas": 0, "paginas_mes_restantes": 0,
            "interesses": {}, "conhecimentos": {}, "generos": generos,
        }
    lidos_set = set(game.livros.get(p.id, []))
    st = intelecto.dados(game, p.id)
    progresso_map = st.get("progresso_livros", {})
    cap_total = capacidade_mes(game, p)
    usadas = paginas_usadas_mes(game, p.id)
    restantes = max(0, cap_total - usadas)
    termo = (busca or "").strip().lower()

    itens = []
    for id_, titulo, autor, ano, gen, nivel in CATALOGO:
        if genero and gen != genero:
            continue
        if termo and termo not in titulo.lower() and termo not in autor.lower():
            continue
        lido = id_ in lidos_set
        total_pags = paginas_livro(id_)
        prog = total_pags if lido else min(total_pags, int(progresso_map.get(id_, 0)))
        pct = 100 if lido else int(round(100 * prog / max(1, total_pags)))
        areas = conhecimentos_livro(id_)
        area_rotulos = [intelecto.AREAS_POR_ID[a][1] for a in areas if a in intelecto.AREAS_POR_ID]
        m = _motivo(game, p, nivel, lido)
        itens.append({
            "id": id_, "titulo": titulo, "autor": autor, "ano": ano, "genero": gen, "nivel": nivel,
            "paginas": total_pags, "progresso": prog, "faltam": max(0, total_pags - prog), "percentual": pct,
            "conhecimentos": list(areas), "conhecimento_rotulos": area_rotulos,
            "cog_principal": GENERO_COGNICAO.get(gen, "compreensao_verbal"),
            "lido": lido, "em_andamento": (not lido and prog > 0),
            "pode": m is None and restantes > 0, "motivo": m,
        })

    nao_lidos = [x for x in itens if not x["lido"]]
    em_andamento = [x for x in nao_lidos if x["em_andamento"]]
    lidos_itens = [x for x in itens if x["lido"]]
    motivo_mes = None if restantes > 0 else "Capacidade de leitura deste mês esgotada. Avance o mês para continuar."
    return {
        "disponivel": restantes > 0,
        "motivo": motivo_mes,
        "itens": itens,
        "nao_lidos": nao_lidos,
        "em_andamento": em_andamento,
        "lidos": lidos_itens,
        "total_lidos": len(lidos_set),
        "total_catalogo": len(CATALOGO),
        "paginas_mes_total": cap_total,
        "paginas_mes_usadas": usadas,
        "paginas_mes_restantes": restantes,
        "interesses": interesses(game, p.id),
        "conhecimentos": dict(st.get("conhecimentos", {})),
        "generos": generos,
    }


def ler(game: Game, livro_id: str, paginas: int | None = None) -> dict:
    p = _jogador(game)
    if p is None:
        raise ValueError("Nenhum personagem vivo do jogador.")
    if livro_id not in _POR_ID:
        raise ValueError("Livro inexistente.")
    _, titulo, autor, _, genero, nivel = _POR_ID[livro_id]
    lidos = game.livros.setdefault(p.id, [])
    m = _motivo(game, p, nivel, livro_id in lidos)
    if m:
        raise ValueError(m)

    cap_total = capacidade_mes(game, p)
    mes = _mes(game)
    st = intelecto.dados(game, p.id)
    pm = st.get("paginas_mes")
    usadas = int(pm[1]) if isinstance(pm, list) and len(pm) == 2 and pm[0] == mes else 0
    restantes = cap_total - usadas
    if restantes <= 0:
        raise ValueError("Capacidade de leitura deste mês esgotada. Avance o mês para continuar lendo.")

    total_pags = paginas_livro(livro_id)
    prog_map = st.setdefault("progresso_livros", {})
    prog_antes = int(prog_map.get(livro_id, 0))
    faltam = max(0, total_pags - prog_antes)
    limite = faltam if paginas is None else max(1, min(faltam, int(paginas)))
    lidas_agora = min(limite, restantes)
    prog_depois = prog_antes + lidas_agora

    st["paginas_mes"] = [mes, usadas + lidas_agora]
    concluido = prog_depois >= total_pags

    ganhos = []
    # Marcos intermediários a cada 250 páginas lidas (mantém obras longas recompensadoras desde o 1º mês)
    marcos_antes = prog_antes // 250
    marcos_depois = prog_depois // 250
    for _ in range(max(0, marcos_depois - marcos_antes)):
        if engine.treinar_cognicao(p, "compreensao_verbal", 1, elevar_potencial=True):
            ganhos.append("compreensao_verbal")

    areas = conhecimentos_livro(livro_id)
    cog_gen = GENERO_COGNICAO.get(genero)
    if concluido:
        prog_map.pop(livro_id, None)
        lidos.append(livro_id)
        game.convivio[(-4, p.id)] = mes

        # Ganho garantido de compreensão verbal + habilidade específica do gênero/nível
        bonus_verbal = 2 if total_pags >= 500 else 1
        if engine.treinar_cognicao(p, "compreensao_verbal", bonus_verbal, elevar_potencial=True):
            if "compreensao_verbal" not in ganhos:
                ganhos.append("compreensao_verbal")
        if cog_gen and cog_gen != "compreensao_verbal":
            if engine.treinar_cognicao(p, cog_gen, 1, elevar_potencial=True) and cog_gen not in ganhos:
                ganhos.append(cog_gen)
        if nivel == 3 and cog_gen != "raciocinio_logico" and total_pags >= 240:
            if engine.treinar_cognicao(p, "raciocinio_logico", 1, elevar_potencial=True) and "raciocinio_logico" not in ganhos:
                ganhos.append("raciocinio_logico")
        if total_pags >= 700 and engine.treinar_cognicao(p, "atencao", 1, elevar_potencial=True):
            if "atencao" not in ganhos:
                ganhos.append("atencao")

        pts_conh = 2 + (1 if total_pags >= 300 else 0) + (1 if total_pags >= 650 else 0)
        for a in areas:
            intelecto.adicionar_conhecimento(game, p.id, a, pts_conh)

        game.add_event(p.id, "decisao", f"Leu \"{titulo}\", de {autor} ({total_pags} págs).")
    else:
        prog_map[livro_id] = prog_depois
        # Pequeno ganho de conhecimento pelo progresso parcial em obras longas
        if lidas_agora >= 120:
            intelecto.adicionar_conhecimento(game, p.id, areas[0], 1)
        game.add_event(p.id, "escola", f"Avançou na leitura de \"{titulo}\" ({prog_depois}/{total_pags} págs).")

    return {
        "titulo": titulo,
        "autor": autor,
        "genero": genero,
        "concluido": concluido,
        "paginas_lidas_agora": lidas_agora,
        "progresso": prog_depois,
        "total_paginas": total_pags,
        "paginas_restantes_mes": max(0, cap_total - (usadas + lidas_agora)),
        "ganhos": ganhos,
        "conhecimentos": [intelecto.AREAS_POR_ID[a][1] for a in areas if a in intelecto.AREAS_POR_ID],
    }
