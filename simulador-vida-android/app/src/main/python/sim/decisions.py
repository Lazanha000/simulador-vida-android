"""Eventos com decisão (v0.15.0–0.18.0): situação sorteada com SEMPRE 3 opções; o tempo para até o jogador escolher.

Cobertura completa do nascimento (0 anos) à velhice (110 anos):
- Não consome `game.rng`: usa gerador determinístico próprio derivado de (semente, mês absoluto, nº de decisões).
- Efeitos diretos em saúde (`s`), patrimônio em salários mínimos (`m`), cognição (`c`, elevando potencial),
  personalidade (`p`), bônus escolar (`esc`), áreas de conhecimento (`con`) e consequências atrasadas (`depois`).
"""
from __future__ import annotations

import random

from . import engine, intelecto
from .models import Game

ATIVO = True
INTERVALO_MIN = 2        # meses mínimos entre dois eventos
CHANCE_MENSAL = 0.28     # chance por mês (depois do intervalo) de surgir um evento elegível
LIMITE_POR_TURNO = 1     # eventos por chamada de avançar (o jogo para no primeiro)


def _emp(c, g): return bool(c.occupation) and not c.retired
def _adulto_rico(c, g): return c.wealth > 0
def _estudante(c, g): return bool(c.in_school or c.in_college)


EVENTOS = [
    # ---- primeira infância (0–4) ----
    dict(id="primeiros_passos", idade=(0, 2), peso=3, titulo="Primeiras descobertas",
         texto="O mundo ao redor parece cheio de sons, cores e objetos novos para alcançar.",
         ops=[("Tentar alcançar e explorar tudo", "Você engatinha e se apoia nos móveis com entusiasmo.",
               dict(s=1, c={"atencao": 1}, p={"abertura": 2, "extroversao": 1})),
              ("Observar com calma antes de agir", "Você acompanha cada movimento com olhos atentos.",
               dict(c={"atencao": 1, "memoria": 1}, p={"conscienciosidade": 1})),
              ("Ficar colado(a) no colo da família", "O abraço traz segurança e tranquilidade.",
               dict(s=2, p={"amabilidade": 1}))]),
    dict(id="vacina_posto", idade=(0, 4), peso=3, titulo="Dia de posto de saúde",
         texto="Chegou a hora da vacinação e da consulta de rotina no posto do bairro.",
         ops=[("Encarar com coragem e ganhar adesivo", "Uma picadinha rápida e proteção garantida.",
               dict(s=3, p={"conscienciosidade": 1})),
              ("Chorar bastante, mas tomar a vacina", "Passou o susto, e sua imunidade agradece.",
               dict(s=2, p={"neuroticismo": 1})),
              ("Brincar com outras crianças na espera", "A consulta vira até passeio divertido.",
               dict(s=2, p={"extroversao": 2, "amabilidade": 1}))]),
    dict(id="banho_e_cantigas", idade=(0, 3), peso=3, titulo="Cantigas na hora do banho",
         texto="Água morna, espuma e uma cantiga de ninar animada ecoam pelo banheiro.",
         ops=[("Bater palmas e repetir os sons da música", "Você acompanha o ritmo e sorri com cada estrofe.",
               dict(c={"compreensao_verbal": 1, "atencao": 1}, con={"artes": 1})),
              ("Brincar com os barquinhos flutuando na água", "Você testa o que afunda e o que boia.",
               dict(c={"raciocinio_logico": 1, "aprendizagem": 1}, con={"ciencias": 1})),
              ("Relaxar quietinho(a) na toalha macia", "O descanso deixa o corpo leve.",
               dict(s=2, p={"amabilidade": 1, "neuroticismo": -1}))]),
    dict(id="hora_historia_bebe", idade=(1, 4), peso=3, titulo="Hora da história antes de dormir",
         texto="Alguém da família abre um livro ilustrado cheio de bichos e palavras novas.",
         ops=[("Pedir para ler de novo e apontar figuras", "Você repete as palavras e grava cada detalhe.",
               dict(c={"compreensao_verbal": 2, "memoria": 1}, con={"linguagem": 1})),
              ("Inventar um final diferente para a história", "Sua imaginação corre solta antes do sono.",
               dict(c={"criatividade": 2, "compreensao_verbal": 1}, con={"artes": 1})),
              ("Dormir abraçado(a) com o livro", "Uma noite de descanso profundo.",
               dict(s=2, p={"amabilidade": 1}))]),
    dict(id="brinquedo_parque", idade=(2, 5), peso=2, titulo="Brinquedo na pracinha",
         texto="Outra criança pede emprestado o brinquedo com que você estava brincando.",
         ops=[("Emprestar e brincar juntos", "Logo vocês inventam uma brincadeira em dupla.",
               dict(p={"amabilidade": 2, "extroversao": 2})) ,
              ("Combinar de revezar", "Cada um usa um pouco, sem briga.",
               dict(c={"resolucao_problemas": 1}, p={"conscienciosidade": 1, "amabilidade": 1})),
              ("Segurar firme só para você", "Você fica com o brinquedo, mas brinca sozinho(a).",
               dict(p={"amabilidade": -1, "extroversao": -1}))]),
    dict(id="blocos_montar", idade=(2, 5), peso=2, titulo="Caixa de blocos de montar",
         texto="Uma caixa cheia de peças coloridas espera no tapete da sala.",
         ops=[("Tentar construir a torre mais alta possível", "Equilíbrio, queda e nova tentativa até dar certo.",
               dict(c={"raciocinio_logico": 1, "resolucao_problemas": 1}, con={"ciencias": 1})),
              ("Separar tudo por cor e tamanho", "Tudo fica milimetricamente alinhado.",
               dict(c={"atencao": 1}, p={"conscienciosidade": 2})),
              ("Montar uma cidade imaginária", "Cada bloco vira casa, ponte ou foguete.",
               dict(c={"criatividade": 2}, p={"abertura": 1}))]),
    dict(id="creche_descoberta", idade=(3, 5), peso=2, titulo="Atividades na educação infantil",
         texto="Na rodinha de atividades, há pintura, música e jogos de letras.",
         ops=[("Mergulhar nos joguinhos de palavras", "Você aprende novas palavras rápido e gosta da sensação.",
               dict(c={"compreensao_verbal": 2, "aprendizagem": 1}, con={"linguagem": 1})),
              ("Fazer uma pintura cheia de cores", "Seu desenho vai parar no mural da sala.",
               dict(c={"criatividade": 2}, con={"artes": 1})),
              ("Liderar a brincadeira de roda", "Você puxa a fila e anima todo mundo.",
               dict(s=1, p={"extroversao": 2, "amabilidade": 1}))]),

    # ---- infância (5–12) ----
    dict(id="zombaria", idade=(6, 12), peso=3, titulo="Zombaria na escola",
         texto="Um colega começa a zombar de você na frente da turma.",
         ops=[("Ignorar e seguir em frente", "Você respira fundo e finge não ouvir. Dói, mas passa.", dict(s=-1, p={"neuroticismo": 1})),
              ("Responder à altura", "Você revida com uma piada e a turma ri junto. A zombaria perde a graça.", dict(p={"extroversao": 2})),
              ("Contar à professora", "A professora conversa com a turma. Você se sente protegido(a).", dict(p={"amabilidade": 1}))]),
    dict(id="prova_dificil", idade=(6, 17), peso=3, titulo="Prova difícil amanhã",
         texto="Tem prova importante amanhã e você ainda não estudou direito.",
         ops=[("Estudar até tarde", "Você dorme pouco, mas entende a matéria.", dict(s=-1, c={"aprendizagem": 1, "memoria": 1}, esc=4)),
              ("Estudar um pouco e dormir bem", "Meio caminho andado e noite tranquila.", dict(c={"atencao": 1}, esc=2)),
              ("Deixar para lá e brincar", "Foi divertido. A prova, nem tanto.", dict(p={"conscienciosidade": -2},
                  depois=(1, "A nota veio baixa e você ouviu um sermão em casa.", dict(s=-1, p={"conscienciosidade": 1}))))]),
    dict(id="gatinho", idade=(5, 14), peso=2, titulo="Gatinho abandonado",
         texto="Você encontra um gatinho magro na rua, miando perto do portão.",
         ops=[("Levar para casa escondido", "Os pais descobrem, brigam e depois deixam ficar.", dict(m=-0.1, p={"amabilidade": 2})),
              ("Dar água e comida e deixar na rua", "Ele fica rondando a vizinhança. Você ajudou como pôde.", dict(m=-0.02, p={"amabilidade": 1})),
              ("Passar direto", "Você segue o caminho. A cena fica na cabeça por dias.", dict(p={"amabilidade": -1}))]),
    dict(id="dinheiro_chao", idade=(6, 17), peso=2, titulo="Dinheiro no chão",
         texto="Você acha uma nota dobrada no chão do pátio. Ninguém viu.",
         ops=[("Guardar para você", "Você compra um lanche e uma figurinha e fica com um pouco de culpa.", dict(m=0.05, p={"conscienciosidade": -1})),
              ("Entregar na secretaria", "A secretária agradece e anota o seu nome.", dict(p={"conscienciosidade": 2, "amabilidade": 1})),
              ("Dividir com os amigos", "Uma tarde de doce e risadas.", dict(p={"extroversao": 1, "amabilidade": 1}))]),
    dict(id="leitura", idade=(8, 17), peso=2, titulo="Professor indica uma leitura",
         texto="Seu professor sugere um livro que não é obrigatório, mas \"abre a cabeça\".",
         ops=[("Ler com atenção", "A leitura é lenta, mas você sai pensando diferente.", dict(c={"compreensao_verbal": 2, "abstracao": 1}, con={"linguagem": 2})),
              ("Ler só o resumo", "Você pega o essencial sem se esforçar muito.", dict(c={"compreensao_verbal": 1}, con={"linguagem": 1})),
              ("Ignorar a indicação", "A semana segue normal.", dict())]),
    dict(id="feira_ciencias", idade=(7, 13), peso=3, req=_estudante, titulo="Feira de ciências da escola",
         texto="Sua turma precisa montar um projeto para a feira de ciências no sábado.",
         ops=[("Montar experimento prático e explicar tudo", "Você testa hipóteses e encanta quem passa pela bancada.",
               dict(c={"aprendizagem": 2, "raciocinio_logico": 1}, esc=5, con={"ciencias": 2})),
              ("Caprichar no cartaz e nos desenhos", "O visual do estande chama atenção do pátio inteiro.",
               dict(c={"criatividade": 2}, esc=3, con={"artes": 2})),
              ("Fazer só o mínimo combinado", "Vocês entregam no prazo, sem grandes emoções.",
               dict(p={"conscienciosidade": -1}))]),
    dict(id="campeonato_recreio", idade=(7, 13), peso=2, titulo="Torneio no recreio",
         texto="Começa um campeonato na escola e dá para escolher entre futebol na quadra ou xadrez na biblioteca.",
         ops=[("Entrar no time de futebol", "Corrida, suor e gol comemorado com a turma.",
               dict(s=2, p={"extroversao": 2})),
              ("Disputar o torneio de xadrez", "Silêncio, concentração e jogadas calculadas.",
               dict(c={"raciocinio_logico": 2, "atencao": 1}, con={"ciencias": 1})),
              ("Ajudar a organizar a tabela de jogos", "Você vira juiz e cronometrista oficial.",
               dict(p={"conscienciosidade": 2, "amabilidade": 1}))]),
    dict(id="mesada_cofrinho", idade=(7, 14), peso=2, titulo="Moedas no cofrinho",
         texto="Você juntou algumas economias de aniversário e trocados de casa.",
         ops=[("Guardar quase tudo no cofrinho", "Você acompanha o valor crescer mês a mês.",
               dict(m=0.08, p={"conscienciosidade": 2}, con={"economia": 1})),
              ("Comprar um livro ou jogo educativo", "Seu quarto ganha uma novidade bem aproveitada.",
               dict(m=-0.04, c={"compreensao_verbal": 1, "criatividade": 1})),
              ("Comprar doces para dividir na rua", "Todo mundo sorri no caminho de volta.",
               dict(m=-0.04, p={"amabilidade": 2, "extroversao": 1}))]),
    dict(id="biblioteca_bairro", idade=(6, 15), peso=3, titulo="Passeio à biblioteca pública",
         texto="A biblioteca da cidade abriu horário especial com estantes infantis, juvenis e oficinas.",
         ops=[("Fazer carteirinha e pegar dois livros", "Você descobre o prazer de escolher leituras por conta própria.",
               dict(c={"compreensao_verbal": 2, "memoria": 1}, con={"linguagem": 2})),
              ("Participar da oficina de escrita", "Você escreve sua primeira história curta.",
               dict(c={"criatividade": 2, "compreensao_verbal": 1}, con={"artes": 1, "linguagem": 1})),
              ("Só dar uma olhada rápida e sair", "Valeu pela caminhada.",
               dict(s=1))]),

    # ---- adolescência (13–17) ----
    dict(id="festa_prova", idade=(13, 17), peso=3, titulo="Festa na véspera da prova",
         texto="Seus amigos chamam para uma festa na noite anterior a uma prova.",
         ops=[("Ir à festa", "Você se diverte muito e acorda cansado(a).", dict(s=-1, p={"extroversao": 2, "conscienciosidade": -1},
                  depois=(2, "A nota da prova saiu abaixo do esperado e você prometeu se organizar melhor.", dict(p={"conscienciosidade": 1})))),
              ("Ficar em casa estudando", "Você perde a festa, mas vai bem na prova.", dict(c={"aprendizagem": 1}, p={"conscienciosidade": 1}, esc=4)),
              ("Ir por uma hora e voltar cedo", "Um equilíbrio possível: um pouco de cada.", dict(p={"extroversao": 1}, esc=1))]),
    dict(id="oferta_vicio", idade=(14, 17), peso=2, titulo="Uma oferta duvidosa",
         texto="Um colega oferece um cigarro \"só para experimentar\" na saída da escola.",
         ops=[("Aceitar", "A primeira tragada queima a garganta. Você tosse e todos riem.", dict(s=-3, p={"abertura": 1})),
              ("Recusar sem drama", "\"Não quero.\" Ninguém insiste.", dict(p={"conscienciosidade": 1})),
              ("Recusar e chamar o grupo para outro lugar", "Metade vai com você. A rodinha muda de assunto.", dict(p={"extroversao": 1, "amabilidade": 1}))]),
    dict(id="bico", idade=(16, 17), peso=2, titulo="Bico de fim de semana",
         texto="Um vizinho oferece um bico no sábado: ajudar numa mudança, pagamento em dinheiro.",
         ops=[("Aceitar o bico", "Cansaço de sábado, dinheiro no bolso.", dict(m=0.25, s=-1)),
              ("Negociar um valor maior", "Ele topa pagar um pouco mais pela sua firmeza.", dict(m=0.35, p={"extroversao": 1})),
              ("Recusar e descansar", "Sábado livre.", dict(s=1))]),
    dict(id="celular_novo", idade=(13, 17), peso=2, titulo="Celular novo",
         texto="Sai um celular novo que todos da turma querem. O seu está velho.",
         ops=[("Juntar dinheiro por meses", "Quando enfim compra, valeu o esforço.", dict(m=-0.2, p={"conscienciosidade": 2})),
              ("Pedir aos pais", "Eles dão um sermão e acabam ajudando.", dict()),
              ("Ficar com o que tem", "Você descobre que o velho ainda funciona.", dict(m=0.05, p={"conscienciosidade": 1}))]),
    dict(id="olimpiada_escolar", idade=(13, 17), peso=3, req=_estudante, titulo="Olimpíada de Matemática e Redação",
         texto="A escola abre inscrições para uma olimpíada nacional com provas de lógica e texto.",
         ops=[("Treinar listas de exercícios por semanas", "Você pega gosto por resolver problemas difíceis.",
               dict(c={"raciocinio_logico": 2, "resolucao_problemas": 1}, esc=5, con={"ciencias": 2},
                    depois=(3, "Saiu o resultado da olimpíada: você recebeu menção honrosa!", dict(p={"conscienciosidade": 1}, c={"aprendizagem": 1})))),
              ("Focar na prova de redação dissertativa", "Seus argumentos ficam mais claros e bem estruturados.",
               dict(c={"compreensao_verbal": 2, "abstracao": 1}, esc=4, con={"linguagem": 2})),
              ("Participar sem preparação extra", "Foi uma boa experiência de prova.",
               dict(c={"atencao": 1}))]),
    dict(id="gremio_estudantil", idade=(13, 17), peso=2, req=_estudante, titulo="Grêmio estudantil e debate",
         texto="Um grupo está organizando um debate escolar e atividades culturais para os alunos.",
         ops=[("Candidatar-se para coordenar os debates", "Você aprende a falar em público e ouvir opiniões opostas.",
               dict(c={"compreensao_verbal": 1, "resolucao_problemas": 1}, p={"extroversao": 2}, con={"direito": 2})),
              ("Organizar um clube de leitura no intervalo", "Toda semana tem troca de livros e resenhas.",
               dict(c={"compreensao_verbal": 2}, p={"amabilidade": 1}, con={"linguagem": 2})),
              ("Acompanhar da plateia", "Você assiste de perto e anota boas ideias.",
               dict(c={"atencao": 1}))]),
    dict(id="pressao_enem", idade=(16, 17), peso=3, req=_estudante, titulo="Pressão com o futuro e vestibulares",
         texto="Todo mundo pergunta qual carreira você vai seguir e o calendário de provas está chegando.",
         ops=[("Montar cronograma realista de estudos e pausas", "Menos ansiedade e mais constância a cada semana.",
               dict(s=1, c={"aprendizagem": 1, "atencao": 1}, p={"conscienciosidade": 2}, esc=4)),
              ("Estudar em ritmo frenético ignorando o sono", "Você decora muita coisa, mas termina exausto(a).",
               dict(s=-3, c={"memoria": 2}, p={"neuroticismo": 1}, esc=5)),
              ("Conversar com profissionais de várias áreas", "As opções ficam bem mais claras na sua cabeça.",
               dict(c={"compreensao_verbal": 1}, p={"abertura": 2}, con={"humanas": 1, "economia": 1}))]),
    dict(id="primeiro_freela", idade=(15, 17), peso=2, titulo="Projeto para comércio do bairro",
         texto="Um comerciante local precisa organizar planilhas, textos ou artes de divulgação.",
         ops=[("Entregar um trabalho completo e profissional", "Ele fica impressionado e recomenda você a outros.",
               dict(m=0.45, c={"resolucao_problemas": 1, "criatividade": 1}, con={"economia": 1})),
              ("Fazer rápido só pelo dinheiro", "Entrou uma grana, mas sem muito brilho.",
               dict(m=0.25)),
              ("Recusar para priorizar os estudos", "Você guarda tempo para provas e leituras.",
               dict(c={"aprendizagem": 1}, esc=3))]),

    # ---- adulto (18–59) ----
    dict(id="oferta_emprego", idade=(20, 59), peso=3, req=_emp, titulo="Oferta de outro emprego",
         texto="Um conhecido indica você para uma vaga que paga um pouco mais, mas é mais arriscada.",
         ops=[("Aceitar a vaga", "Mudança de rotina e de ares. O salário sobe um pouco.", dict(m=0.4, s=-1, p={"abertura": 1})),
              ("Usar a oferta para pedir aumento", "O chefe resmunga, mas melhora sua situação.", dict(m=0.2, p={"extroversao": 1})),
              ("Recusar e ficar onde está", "Segurança acima de tudo, por ora.", dict(p={"conscienciosidade": 1}))]),
    dict(id="dor_persistente", idade=(25, 90), peso=2, titulo="Dor que não passa",
         texto="Há semanas você sente uma dor que vai e volta.",
         ops=[("Procurar um médico", "Exames, filas e um diagnóstico simples. Alívio.", dict(s=3, m=-0.3)),
              ("Tomar remédio por conta própria", "Melhora por uns dias, volta depois.", dict(s=-1, m=-0.05)),
              ("Esperar passar", "Passa... ou parece que passa.", dict(s=-2))]),
    dict(id="dinheiro_extra", idade=(18, 90), peso=2, titulo="Dinheiro extra",
         texto="Chega um dinheiro inesperado: um acerto de contas atrasado.",
         ops=[("Guardar tudo", "Reserva de emergência engordando.", dict(m=1.0, p={"conscienciosidade": 1}, con={"economia": 1})),
              ("Gastar com algo que você queria", "Prazer imediato.", dict(m=0.2, s=1)),
              ("Investir num curso", "O dinheiro vira conhecimento.", dict(m=0.4, c={"aprendizagem": 1, "resolucao_problemas": 1}, con={"ciencias": 1}))]),
    dict(id="curso_noite", idade=(18, 55), peso=2, titulo="Curso à noite",
         texto="Abriu uma turma noturna de um curso que combina com você. Cabe na rotina, mas apertado.",
         ops=[("Matricular-se", "As noites ficam cheias, a cabeça também.", dict(m=-0.3, s=-1, c={"aprendizagem": 2, "memoria": 1}, con={"ciencias": 2})),
              ("Fazer só o primeiro módulo", "Um gostinho do assunto, sem sufoco.", dict(m=-0.1, c={"aprendizagem": 1}, con={"humanas": 1})),
              ("Deixar passar", "Quem sabe no semestre que vem.", dict())]),
    dict(id="emprestimo", idade=(22, 80), peso=2, req=_adulto_rico, titulo="Pedido de empréstimo",
         texto="Um parente próximo pede dinheiro emprestado, dizendo que devolve logo.",
         ops=[("Emprestar tudo que pediu", "Ele agradece muito. Resta torcer.", dict(m=-0.8, p={"amabilidade": 1})),
              ("Emprestar uma parte", "Você ajuda dentro do que dá.", dict(m=-0.3)),
              ("Recusar com jeito", "Ficou um clima estranho no almoço de domingo.", dict(p={"amabilidade": -1}))]),
    dict(id="viagem_amigos", idade=(18, 70), peso=2, titulo="Convite para viajar",
         texto="Um grupo de amigos monta uma viagem de fim de semana e chama você.",
         ops=[("Ir e curtir", "Estrada, risadas e fotos ruins. Valeu cada centavo.", dict(m=-0.4, s=1, p={"extroversao": 1})),
              ("Ir só no sábado", "Você aproveita metade e gasta metade.", dict(m=-0.15)),
              ("Ficar em casa", "Fim de semana quieto, saudade dos amigos.", dict(p={"extroversao": -1}))]),
    dict(id="burnout_trabalho", idade=(22, 59), peso=3, req=_emp, titulo="Ritmo puxado no trabalho",
         texto="As últimas semanas foram de horas extras, metas apertadas e pouco sono.",
         ops=[("Impor limites e tirar descanso merecido", "Você desacelera, dorme bem e recupera a clareza mental.",
               dict(s=3, p={"conscienciosidade": 1}, c={"atencao": 1})),
              ("Redistribuir tarefas com a equipe", "Menos sobrecarga e melhor organização no setor.",
               dict(s=1, c={"resolucao_problemas": 1}, p={"amabilidade": 1})),
              ("Seguir no limite tomando café", "Você entrega tudo, mas o corpo cobra a conta depois.",
               dict(m=0.35, s=-4, depois=(2, "A exaustão derrubou sua imunidade por alguns dias.", dict(s=-2))))]),
    dict(id="checkup_preventivo", idade=(25, 75), peso=2, titulo="Campanha de check-up de saúde",
         texto="Um mutirão preventivo oferece exames completos e orientação nutricional perto de casa.",
         ops=[("Fazer todos os exames e ajustar hábitos", "Resultados em dia e mais disposição no mês inteiro.",
               dict(s=4, m=-0.1, p={"conscienciosidade": 1})),
              ("Começar caminhadas regulares por conta", "Aos poucos o fôlego melhora bastante.",
               dict(s=2, c={"atencao": 1})),
              ("Deixar para o próximo ano", "A rotina engole a agenda mais uma vez.",
               dict(s=-2))]),
    dict(id="crise_orcamento", idade=(19, 65), peso=3, titulo="Imprevisto no orçamento",
         texto="Um eletrodoméstico essencial quebrou de repente e a conta de manutenção veio salgada.",
         ops=[("Pagar à vista negociando desconto", "Doeu no bolso hoje, mas não virou bola de neve.",
               dict(m=-0.45, p={"conscienciosidade": 1}, con={"economia": 1})),
              ("Fazer renda extra no fim de semana para cobrir", "Cansativo, mas o orçamento fecha no azul.",
               dict(m=0.1, s=-1, c={"resolucao_problemas": 1})),
              ("Parcelar no cartão sem fazer contas", "Resolveu na hora, mas os juros aparecem depois.",
               dict(m=-0.2, depois=(2, "As faturas acumuladas pesaram no orçamento do mês.", dict(m=-0.5, p={"neuroticismo": 1}))))]),
    dict(id="voluntariado_bairro", idade=(18, 80), peso=2, titulo="Projeto voluntário no bairro",
         texto="Moradores estão montando um reforço escolar e horta comunitária aos sábados.",
         ops=[("Dar aulas de leitura e matemática básica", "Ensinar aos outros solidifica seu próprio conhecimento.",
               dict(c={"compreensao_verbal": 1, "aprendizagem": 1}, p={"amabilidade": 2}, con={"humanas": 1})),
              ("Ajudar na horta e na organização física", "Mãos na terra, ar livre e boas conversas.",
               dict(s=2, p={"extroversao": 1, "amabilidade": 1})),
              ("Contribuir com uma doação em dinheiro", "Você apoia de longe conforme pode.",
               dict(m=-0.15, p={"amabilidade": 1}))]),
    dict(id="debate_comunitario", idade=(18, 75), peso=2, titulo="Audiência pública no bairro",
         texto="A prefeitura convocou uma reunião aberta sobre transporte e áreas verdes da região.",
         ops=[("Preparar dados e falar no microfone", "Sua argumentação chama atenção e ganha apoio dos vizinhos.",
               dict(c={"compreensao_verbal": 2, "resolucao_problemas": 1}, p={"extroversao": 1}, con={"direito": 2})),
              ("Ajudar a redigir a pauta coletiva", "Vocês entregam um documento bem fundamentado.",
               dict(c={"compreensao_verbal": 1}, p={"conscienciosidade": 1}, con={"direito": 1, "humanas": 1})),
              ("Só acompanhar as falas", "Você entende melhor os impasses da cidade.",
               dict(con={"humanas": 1}))]),
    dict(id="mentoria_carreira", idade=(26, 65), peso=2, titulo="Pedido de orientação profissional",
         texto="Um(a) jovem conhecido(a) pede conselhos sobre estudos, currículo e mercado de trabalho.",
         ops=[("Dedicar uma tarde para revisar tudo e indicar livros", "A troca faz bem para os dois lados.",
               dict(c={"compreensao_verbal": 1, "memoria": 1}, p={"amabilidade": 2}, con={"linguagem": 1})),
              ("Compartilhar seus erros e acertos práticos", "Uma conversa direta e realista.",
               dict(p={"extroversao": 1, "amabilidade": 1})),
              ("Mandar apenas um áudio curto", "Você ajuda no básico sem perder o ritmo do dia.",
               dict())]),
    dict(id="negocio_arriscado", idade=(21, 65), peso=2, req=_adulto_rico, titulo="Proposta de investimento \"garantido\"",
         texto="Um conhecido apresenta um negócio prometendo retorno rápido e muito acima do mercado.",
         ops=[("Analisar os números e recusar a cilada", "A matemática não fechava — você protege seu patrimônio.",
               dict(c={"raciocinio_logico": 2}, con={"economia": 2})),
              ("Arriscar só uma quantia pequena", "Se der errado, não compromete sua vida.",
               dict(m=-0.3, depois=(3, "O negócio não decolou como prometido e você perdeu parte do valor.", dict(m=-0.2)))),
              ("Entrar com força total na promessa", "Você transfere bastante dinheiro na empolgação.",
               dict(m=-1.2, depois=(3, "O esquema ruiu e deixou prejuízo pesado.", dict(m=-1.0, s=-2))))]),
    dict(id="clube_leitura_cinema", idade=(18, 90), peso=2, titulo="Clube do livro e cinema",
         texto="Um centro cultural abriu encontros quinzenais para debater romances e filmes.",
         ops=[("Participar ativamente dos debates", "Boas referências literárias e novos pontos de vista.",
               dict(c={"compreensao_verbal": 2, "abstracao": 1}, p={"abertura": 2}, con={"linguagem": 1, "artes": 1})),
              ("Ir de vez em quando como ouvinte", "Você sai sempre com boas indicações.",
               dict(c={"criatividade": 1}, con={"artes": 1})),
              ("Prefiro acompanhar filmes e livros sozinho(a)", "No seu próprio tempo, sem agenda fixa.",
               dict(c={"atencao": 1}))]),

    # ---- terceira idade (60+) ----
    dict(id="escrever_memorias", idade=(60, 110), peso=3, titulo="Caderno de memórias",
         texto="Ao rever fotos e cartas antigas, bate a vontade de registrar sua história de vida.",
         ops=[("Escrever um livro de memórias com calma", "Lembranças ganham forma, ritmo e clareza no papel.",
               dict(c={"memoria": 2, "compreensao_verbal": 2}, p={"abertura": 1}, con={"linguagem": 2, "humanas": 1})),
              ("Gravar relatos em áudio para a família", "Filhos, netos e amigos se emocionam ao ouvir.",
               dict(p={"amabilidade": 2, "extroversao": 1}, c={"memoria": 1})),
              ("Organizar apenas um álbum cronológico", "Cada ano vivido encontra seu lugar.",
               dict(c={"atencao": 1}, p={"conscienciosidade": 1}))]),
    dict(id="universidade_aberta", idade=(60, 105), peso=3, titulo="Universidade Aberta da Terceira Idade",
         texto="Uma universidade da região abriu vagas gratuitas em cursos e oficinas para quem tem 60+.",
         ops=[("Matricular-se em história, literatura e filosofia", "A sala cheia de debates renova sua curiosidade.",
               dict(c={"aprendizagem": 2, "compreensao_verbal": 1}, s=1, con={"humanas": 2, "filosofia": 1})),
              ("Fazer oficina de tecnologia e informática", "Você domina novos aplicativos e exercita a mente.",
               dict(c={"raciocinio_logico": 1, "resolucao_problemas": 2}, con={"ciencias": 2})),
              ("Assistir só às palestras abertas", "Leve, interessante e sem compromisso semanal.",
               dict(c={"aprendizagem": 1}))]),
    dict(id="caminhada_praca", idade=(60, 110), peso=3, titulo="Grupo de caminhada na praça",
         texto="Vizinhos da mesma idade se reúnem toda manhã na praça para alongamento e caminhada.",
         ops=[("Ir três vezes por semana sem falta", "O coração, as pernas e o humor respondem rápido.",
               dict(s=4, p={"extroversao": 2, "conscienciosidade": 1})),
              ("Participar aos fins de semana", "Bom passeio matinal com conversa leve.",
               dict(s=2, p={"extroversao": 1})),
              ("Ficar em casa lendo o jornal", "Manhã sossegada na poltrona.",
               dict(c={"compreensao_verbal": 1}, s=-1))]),
    dict(id="conselho_jovens", idade=(62, 110), peso=2, titulo="Conselho para as novas gerações",
         texto="Um(a) jovem da família enfrenta uma encruzilhada parecida com uma que você já viveu.",
         ops=[("Contar sua experiência e debater caminhos", "Sua escuta paciente ajuda muito mais do que ordens.",
               dict(c={"compreensao_verbal": 1, "abstracao": 1}, p={"amabilidade": 2})),
              ("Emprestar um livro que marcou sua juventude", "Um gesto silencioso que atravessa gerações.",
               dict(con={"linguagem": 1}, p={"amabilidade": 1})),
              ("Deixar que aprenda com os próprios passos", "Cada época tem suas próprias respostas.",
               dict(p={"abertura": 1}))]),
    dict(id="consulta_geriatrica", idade=(65, 110), peso=3, titulo="Acompanhamento geriátrico",
         texto="Está na hora de revisar exames, pressão, alimentação e sono.",
         ops=[("Seguir o plano completo de cuidados", "Ajuste fino na rotina traz fôlego e prevenção.",
               dict(s=4, m=-0.15, p={"conscienciosidade": 1})),
              ("Fazer os exames básicos e caminhar mais", "Cuidados simples que já fazem diferença.",
               dict(s=2)),
              ("Adiar a consulta por mais alguns meses", "Você evita a fila, mas perde a chance de prevenir.",
               dict(s=-3))]),
    dict(id="novo_oficio", idade=(60, 105), peso=2, titulo="Aprender uma arte na maturidade",
         texto="Com mais tempo livre, surge a vontade de aprender música, pintura ou marcenaria.",
         ops=[("Praticar todo dia com dedicação", "A coordenação e a mente criativa florescem juntas.",
               dict(c={"criatividade": 2, "atencao": 2}, s=1, con={"artes": 2})),
              ("Fazer aulas em grupo para socializar", "Novas amizades e boas risadas toda semana.",
               dict(c={"criatividade": 1}, p={"extroversao": 2, "amabilidade": 1}, con={"artes": 1})),
              ("Ficar só na admiração", "Você aproveita outros passatempos tranquilos.",
               dict(s=1))]),
    dict(id="viagem_historica", idade=(60, 100), peso=2, titulo="Excursão para cidade histórica",
         texto="Um grupo organiza uma viagem tranquila de ônibus para visitar museus e centros históricos.",
         ops=[("Ir com guia cultural e aproveitar cada museu", "Você volta cheio(a) de histórias e referências.",
               dict(m=-0.35, s=1, c={"memoria": 2}, p={"abertura": 2}, con={"humanas": 2, "artes": 1})),
              ("Ir para descansar na pousada e passear na praça", "Ritmo leve, café quente e zero pressa.",
               dict(m=-0.25, s=2)),
              ("Guardar o dinheiro para imprevistos", "Reserva preservada com tranquilidade.",
               dict(p={"conscienciosidade": 1}))]),

    # ---- v0.20.0: carreira, técnica, vínculos, conflitos e hábitos ----
    dict(id="curso_tecnico_oficina", idade=(15, 22), peso=2, req=_estudante, titulo="Oficina prática de formação técnica",
         texto="O campus técnico abriu vagas em laboratório prático de informática, eletrônica e gestão aos sábados.",
         ops=[("Participar de todos os módulos práticos", "Você sai dominando ferramentas úteis no mercado.",
               dict(c={"resolucao_problemas": 2, "aprendizagem": 1}, esc=4, con={"ciencias": 2})),
              ("Focar só nos projetos de gestão", "Organização financeira e de equipes bem treinada.",
               dict(c={"raciocinio_logico": 1}, esc=3, con={"economia": 2})),
              ("Priorizar as revisões teóricas em casa", "Menos prática, porém boa base de provas.",
               dict(c={"memoria": 1}, esc=2))]),
    dict(id="ic_congresso", idade=(18, 28), peso=2, req=_estudante, titulo="Chamada para congresso acadêmico",
         texto="Seu departamento convidou estudantes para apresentar pôsteres e resumos num simpósio regional.",
         ops=[("Submeter trabalho completo e apresentar em público", "Sua arguição foi elogiada pela banca avaliadora.",
               dict(c={"compreensao_verbal": 2, "abstracao": 1}, p={"extroversao": 1}, con={"ciencias": 2},
                    depois=(2, "O resumo publicado nos anais abriu boas portas acadêmicas.", dict(c={"aprendizagem": 1})))),
              ("Ajudar na comissão organizadora", "Bastidores intensos e ótima rede de contatos.",
               dict(p={"conscienciosidade": 1, "amabilidade": 1}, con={"humanas": 1})),
              ("Assistir apenas como ouvinte", "Você acompanha as palestras principais sem pressão.",
               dict(c={"atencao": 1}))]),
    dict(id="freela_prazo", idade=(18, 55), peso=2, titulo="Projeto autônomo de última hora",
         texto="Um cliente precisa de entrega urgente para segunda-feira, pagando bem acima da média.",
         ops=[("Virar parte do fim de semana e entregar impecável", "Pagamento excelente e cliente fiel conquistado.",
               dict(m=0.55, s=-2, c={"resolucao_problemas": 1}, con={"economia": 1})),
              ("Negociar escopo reduzido e prazo justo", "Ganho equilibrado sem sacrificar o sono.",
               dict(m=0.30, s=1, p={"conscienciosidade": 1})),
              ("Recusar para preservar o descanso", "Você recarrega as energias para a semana.",
               dict(s=2))]),
    dict(id="colega_rival_trabalho", idade=(20, 59), peso=3, req=_emp, titulo="Atrito e competição no trabalho",
         texto="Um(a) colega de setor disputa espaço no mesmo projeto e questionou seu método na reunião.",
         ops=[("Propor alinhamento técnico com dados objetivos", "A postura serena transformou tensão em respeito profissional.",
               dict(c={"resolucao_problemas": 1}, p={"conscienciosidade": 1}, con={"economia": 1})),
              ("Confrontar publicamente na hora", "Clima pesado na equipe nas semanas seguintes.",
               dict(s=-1, p={"extroversao": 1, "amabilidade": -2},
                    depois=(2, "A rivalidade no setor exigiu paciência dobrada no dia a dia.", dict(p={"neuroticismo": 1})))),
              ("Relevar e focar só nas suas entregas", "Você evita desgaste e mantém seu ritmo.",
               dict(p={"conscienciosidade": 1}))]),
    dict(id="socio_empresa", idade=(23, 65), peso=3,
         req=lambda c, g: bool(g.carreira_extra.get(c.id, {}).get("empresa_id")),
         titulo="Proposta de parceria na empresa",
         texto="Um fornecedor estratégico propõe ampliar linhas e compartilhar clientes mediante investimento.",
         ops=[("Fechar parceria com contrato revisado", "As vendas crescem de forma consistente no trimestre.",
               dict(m=0.90, c={"resolucao_problemas": 1}, con={"economia": 2, "direito": 1})),
              ("Testar em projeto-piloto pequeno primeiro", "Risco controlado antes de comprometer o caixa.",
               dict(m=0.35, p={"conscienciosidade": 1})),
              ("Manter operação independente", "Autonomia preservada mesmo com avanço mais lento.",
               dict(p={"conscienciosidade": 1}))]),
    dict(id="crise_fluxo_caixa", idade=(23, 65), peso=2,
         req=lambda c, g: bool(g.carreira_extra.get(c.id, {}).get("empresa_id")),
         titulo="Aperto no fluxo de caixa",
         texto="As vendas esfriaram neste mês e os custos fixos venceram antes dos recebimentos.",
         ops=[("Cortar supérfluos e renegociar prazos", "Organização firme evita dívida cara.",
               dict(m=-0.25, c={"raciocinio_logico": 1}, con={"economia": 2})),
              ("Injetar reserva pessoal temporária", "A empresa respira, mas seu caixa pessoal encolhe.",
               dict(m=-0.75, p={"conscienciosidade": 1})),
              ("Adiar pagamentos e esperar o próximo mês", "Juros e cobranças apertam logo adiante.",
               dict(depois=(1, "Multas e juros encareceram o acerto de contas.", dict(m=-0.85, s=-1))))]),
    dict(id="jantar_familia_tenso", idade=(18, 85), peso=2, titulo="Conversa delicada em família",
         texto="Durante o almoço de domingo, um assunto antigo volta à tona e divide opiniões na mesa.",
         ops=[("Ouvir os lados e mediar com calma", "A tensão diminui e o vínculo sai mais maduro.",
               dict(s=1, p={"amabilidade": 2}, con={"psicologia": 1})),
              ("Defender seu ponto com firmeza até o fim", "Você disse o que pensava, mas o clima esfriou.",
               dict(p={"amabilidade": -1, "extroversao": 1})),
              ("Mudar de assunto e ajudar na cozinha", "Paz preservada sem remoer mágoas.",
               dict(p={"amabilidade": 1}))]),
    dict(id="conflito_vizinho", idade=(20, 85), peso=2, titulo="Atrito com vizinho",
         texto="Obras e som alto fora de hora têm atrapalhado seu sono e sua concentração em casa.",
         ops=[("Conversar educadamente e combinar horários", "Acordo simples resolve o problema rapidamente.",
               dict(s=2, p={"amabilidade": 1, "conscienciosidade": 1})),
              ("Registrar ocorrência formal no condomínio/prefeitura", "Demorou um pouco, mas o silêncio voltou dentro da regra.",
               dict(s=1, con={"direito": 1})),
              ("Bater boca no corredor", "Discussão acalorada aumentou o estresse da semana.",
               dict(s=-2, p={"neuroticismo": 1, "amabilidade": -1}))]),
    dict(id="plano_saude_escolha", idade=(22, 70), peso=2, titulo="Cuidados médicos e prevenção",
         texto="Com o passar dos anos, vale revisar como equilibrar exames preventivos e custos mensais.",
         ops=[("Investir em rotina preventiva e consultas em dia", "Qualidade de vida e tranquilidade nos exames.",
               dict(s=3, m=-0.25, p={"conscienciosidade": 1})),
              ("Combinar UBS/SUS com caminhadas e alimentação leve", "Bom cuidado sem pesar no orçamento.",
               dict(s=2, con={"psicologia": 1})),
              ("Só procurar atendimento em emergência", "Economia hoje que pode cobrar mais caro depois.",
               dict(s=-2))]),
    dict(id="orcamento_investir", idade=(20, 65), peso=2, req=_adulto_rico, titulo="Rebalanceamento financeiro anual",
         texto="Seus rendimentos acumularam e surgiu o momento de decidir onde alocar parte da reserva.",
         ops=[("Diversificar entre renda fixa e longo prazo", "Menos sobressaltos e crescimento consistente.",
               dict(m=0.45, c={"raciocinio_logico": 1}, con={"economia": 2})),
              ("Separar verba para qualificação e livros", "Conhecimento novo se paga em oportunidades.",
               dict(m=-0.20, c={"aprendizagem": 2}, con={"ciencias": 1})),
              ("Deixar tudo parado na conta corrente", "Liquidez imediata, mas a inflação corrói aos poucos.",
               dict(m=-0.10))]),
    dict(id="convite_voluntariado", idade=(16, 80), peso=2, titulo="Mutirão solidário na cidade",
         texto="Uma associação local convida voluntários para arrecadar livros e dar oficinas gratuitas.",
         ops=[("Organizar doação de livros e oficina de leitura", "Impacto real no bairro e novas amizades.",
               dict(s=1, p={"amabilidade": 2, "extroversao": 1}, con={"linguagem": 1, "humanas": 1})),
              ("Ajudar na logística do fim de semana", "Trabalho em equipe bem coordenado.",
               dict(s=1, p={"conscienciosidade": 1, "amabilidade": 1})),
              ("Apenas divulgar entre conhecidos", "Participação discreta dentro do possível.",
               dict())]),
    dict(id="rotina_digital", idade=(13, 65), peso=3, titulo="Excesso de telas e atenção dispersa",
         texto="Você percebeu que passou horas demais rolando o celular tarde da noite.",
         ops=[("Trocar a última hora do dia por livro e sono regular", "Atenção e memória melhoram logo na primeira semana.",
               dict(s=2, c={"atencao": 2, "memoria": 1}, p={"conscienciosidade": 1})),
              ("Silenciar notificações no horário de estudo/trabalho", "Produtividade sobe visivelmente.",
               dict(c={"atencao": 1, "resolucao_problemas": 1})),
              ("Continuar no mesmo ritmo de madrugada", "Cansaço e foco mais curto nos dias seguintes.",
               dict(s=-2, c={"atencao": -1}))]),
]
EVENTOS_POR_ID = {e["id"]: e for e in EVENTOS}


def novo_estado() -> dict:
    return {"pending": None, "count": 0, "last": 0, "depois": []}


def _abs(game: Game) -> int:
    return game.year * 12 + game.month


def _rng(game: Game, extra: str) -> random.Random:
    return random.Random(f"dec:{game.seed}:{_abs(game)}:{game.decisions['count']}:{extra}")


def elegiveis(game: Game, c) -> list[dict]:
    idade = c.age_at(game.year, game.month)
    return [e for e in EVENTOS if e["idade"][0] <= idade <= e["idade"][1] and (e.get("req") is None or e["req"](c, game))]


def tentar(game: Game, c) -> dict | None:
    """Chamada a cada mês processado (pelo `views.avancar`). Cria uma decisão pendente se o sorteio acertar."""
    if not ATIVO or c is None or not c.alive or game.decisions["pending"]:
        return None
    if _abs(game) - game.decisions["last"] < INTERVALO_MIN:
        return None
    r = _rng(game, "chance")
    if r.random() >= CHANCE_MENSAL:
        return None
    lista = elegiveis(game, c)
    if not lista:
        return None
    recentes = set(game.decisions.get("recentes") or [])
    filtrada = [e for e in lista if e["id"] not in recentes]
    pool = filtrada if filtrada else lista
    ev = r.choices(pool, weights=[e["peso"] for e in pool])[0]
    game.decisions["pending"] = {"id": ev["id"], "ano": game.year, "mes": game.month, "pid": c.id}
    return game.decisions["pending"]


def view(game: Game) -> dict | None:
    p = game.decisions["pending"]
    if not p:
        return None
    ev = EVENTOS_POR_ID[p["id"]]
    return {"id": ev["id"], "titulo": ev["titulo"], "texto": ev["texto"], "opcoes": [o[0] for o in ev["ops"]]}


def _aplicar(game: Game, c, ef: dict) -> list[str]:
    notas = []
    if "s" in ef:
        antes = c.health
        c.health = float(max(0, min(100, c.health + ef["s"])))
        if c.health != antes:
            notas.append(f"saúde {c.health - antes:+.0f}")
    if "m" in ef:
        v = ef["m"] * game.macro["min_wage"]
        c.wealth += v
        notas.append(f"{'+' if v >= 0 else '-'}R$ {abs(v):,.0f}".replace(",", "."))
    for k, d in (ef.get("c") or {}).items():
        if k in c.cognition:
            ganho = engine.treinar_cognicao(c, k, d, elevar_potencial=True)
            if ganho:
                notas.append(f"{k.replace('_', ' ')} {ganho:+d}")
    for k, d in (ef.get("p") or {}).items():
        if k in c.personality:
            antes_p = c.personality[k]
            c.personality[k] = int(max(1, min(99, c.personality[k] + d)))
            if c.personality[k] != antes_p:
                notas.append(f"{k} {c.personality[k] - antes_p:+d}")
    if "esc" in ef and ef["esc"]:
        st = intelecto.dados(game, c.id)
        intelecto._add_bonus_anual(st, "bonus_escola", game.year, int(ef["esc"]), 18)
        notas.append(f"estudos +{int(ef['esc'])}")
    for area_id, pts in (ef.get("con") or {}).items():
        if pts > 0:
            intelecto.adicionar_conhecimento(game, c.id, area_id, int(pts))
    return notas


def decidir(game: Game, opcao: int | None) -> dict:
    """Resolve a decisão pendente. `opcao` None = "decidir por mim" (sorteio determinístico). Devolve o resultado."""
    p = game.decisions["pending"]
    if not p:
        raise ValueError("Não há decisão pendente.")
    ev = EVENTOS_POR_ID[p["id"]]
    auto = opcao is None
    if auto:
        opcao = _rng(game, "auto").randrange(3)
    if opcao not in (0, 1, 2):
        raise ValueError("Opção inválida.")
    c = game.characters[p["pid"]]
    rotulo, resultado, ef = ev["ops"][opcao]
    notas = _aplicar(game, c, ef) if c.alive else []
    game.add_event(c.id, "decisao", f"{ev['titulo']}: {rotulo.lower()}. {resultado}" + (f" ({', '.join(notas)})" if notas else ""))
    if ef.get("depois") and c.alive:
        meses, texto, ef2 = ef["depois"]
        game.decisions.setdefault("depois", []).append({"mes": _abs(game) + meses, "pid": c.id, "texto": texto, "ef": ef2})
    rec = list(game.decisions.get("recentes") or [])
    rec.append(ev["id"])
    game.decisions["recentes"] = rec[-10:]
    game.decisions["pending"] = None
    game.decisions["count"] += 1
    game.decisions["last"] = _abs(game)
    rest_turno = int((game.decisions.get("turno") or {}).get("restantes", 0))
    return {"escolhida": opcao, "auto": auto, "rotulo": rotulo, "resultado": resultado, "notas": notas,
            "restantes_avanco": rest_turno}


def atrasadas(game: Game) -> int:
    """Aplica as consequências agendadas cujo mês chegou (chamada a cada mês pelo `views.avancar`). Devolve quantas."""
    fila = game.decisions.get("depois") or []
    if not fila:
        return 0
    agora = _abs(game)
    prontas = [d for d in fila if d["mes"] <= agora]
    game.decisions["depois"] = [d for d in fila if d["mes"] > agora]
    for d in prontas:
        c = game.characters.get(d["pid"])
        if c is None or not c.alive:
            continue
        notas = _aplicar(game, c, d["ef"])
        game.add_event(c.id, "decisao", f"Consequência: {d['texto']}" + (f" ({', '.join(notas)})" if notas else ""))
    return len(prontas)
