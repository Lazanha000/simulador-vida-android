# DIREÇÃO — o que falta para o jogo ser um JOGO (registrado em 2026-11-23)

Este documento complementa o `PROMPT GERAL.txt` (que continua valendo) e orienta as próximas microatualizações.
Ele registra o diagnóstico feito com o dono do projeto e as prioridades que ele pediu.

## 1. Diagnóstico honesto (v0.14.3)
O que está sólido: o MUNDO simulado (idade, família, nascimentos, casamento, escola, trabalho, empresas, economia, impostos, morte e herança), a interface no navegador e 256 testes.

O que está faltando, e é o centro do jogo: **o jogador não decide nada.** Hoje as únicas ações são avançar 1 mês/6 meses/1 ano, trocar de personagem e criar personagem. Estudar, trabalhar, fazer amizade, namorar acontecem sozinhos, por sorteio. O PROMPT GERAL pede "autonomia" e "decisões que produzem consequências" (princípios 3 e 5) e diz que "eventos importantes poderão interromper a progressão e solicitar decisões" (§5), mas isso nunca foi implementado. Foi um desvio de prioridade: sistemas de mundo vieram antes do sistema de escolhas.

### Fatos verificados no código sobre pessoas e relações
- Pessoas só são criadas em 3 momentos: no início da partida (família ou personagem avulso), em nascimentos e quando o jogador cria personagem/família. **Não existem desconhecidos novos.** Um personagem avulso começa com população 1: não há ninguém para conhecer (por isso "Amigos vivos 0 de 8").
- Nomes, sexo, personalidade e cognição são sorteados (com semente) e a personalidade é herdada parcialmente dos pais; ou seja, as pessoas SÃO diferentes entre si, mas o mundo é minúsculo e fechado.
- Amizades e namoros acontecem automaticamente entre NPCs já existentes. O jogador não pode puxar conversa, convidar, namorar nem terminar.
- Regras de idade que já existem: amizade só a partir dos 6 anos e com diferença de idade limitada (3 anos até os 11, 6 até os 17, 12 depois); namoro/casamento só a partir dos 18, sem parentesco próximo. Portanto, um bebê/criança não se relaciona com pessoas bem mais velhas (intencional), mas isso nunca foi mostrado ao jogador. Não existe aplicativo de relacionamentos.

## 2. Requisitos pedidos pelo dono do projeto (valem daqui em diante)
R1. **Autonomia do jogador sobre o personagem**: ele escolhe, por exemplo, se estuda ou não, e quanto.
R2. **Evento com escolhas a cada período**: ao avançar o tempo, aparece na tela uma situação gerada aleatoriamente com **3 opções** (sempre 3), e a escolha mexe na vida e nas estatísticas. Em 1 mês, o evento é ocasional; ao avançar 6 meses/1 ano, o jogo para em cada evento importante.
R3. **Estudo com escolha de área** (exatas, humanas etc.; usar a divisão menos cansativa e mais imersiva) com efeito real em cognição e desempenho.
R4. **Livros reais** (futuro): catálogo de cerca de 1.000 obras para o jogador escolher o que ler.
R5. **Conhecer pessoas e interagir com elas**, com pessoas geradas com nomes, famílias, vínculos e personalidades diferentes, e regras de idade claras.

## 3. Trilha de jogabilidade (PRIORIDADE sobre as demais fases; cada item = 1 microatualização, nesta ordem)
**G1 — [FEITA em 0.15.0, verificação completa pendente] Eventos com decisão (framework + primeiro pacote).** Estrutura de evento interativo: condição (idade, ocupação, dinheiro, saúde...), peso de sorteio, texto, **3 opções** e efeitos (atributos, dinheiro, relações, biografia, consequências com atraso). Pausa o avanço de tempo e abre uma tela de escolha; opção "decidir por mim" (sorteia). Limite de eventos por turno para não cansar. Estado pendente salvo no save (nova versão de save, migrando as antigas). Semente/RNG preservados. Primeiro pacote: ~15 eventos para infância, adolescência e adulto. Testes: determinismo, save/load no meio de uma decisão, cada opção aplica seu efeito.
**G2 — [G2a FEITA em 0.15.1: foco; G2b FEITA em 0.15.2: área de estudo] Rotina e estudo.** "Foco do período" escolhido pelo jogador (estudar, trabalhar, socializar, descansar), e, dentro de estudar, a área (proposta inicial alinhada às 4 áreas do ENEM: Linguagens, Humanas, Natureza, Matemática), com efeito real em cognição específica e notas; custo em energia/bem-estar.
**G3 — Mundo social vivo.** (a) Gerar conhecidos novos sob demanda (vizinhança, colegas de escola e de trabalho, amigos de amigos), com nome, família, idade e personalidade próprios, persistidos; (b) ações do jogador: conhecer pessoas, conversar, convidar, aprofundar amizade, namorar, terminar, romper; (c) regras de idade explícitas e mostradas na tela (menores não namoram adultos; relacionamentos românticos só entre maiores de 18; aplicativo de relacionamentos só para maiores de 18, mostrando 3 candidatos gerados); (d) interação com consequências (afinidade, memória do relacionamento).
**G4 — Livros reais.** Catálogo de ~1.000 obras com metadados (título, autor, ano, gênero, nível); leitura afeta vocabulário/cognição/interesses. Só metadados, nunca texto de obras. Montar em lotes (~100 por microatualização) e auditar os dados item a item antes de entrar no jogo.

Depois de G1–G4 voltam as fases do ROADMAP (trabalho meio período, crédito/imóveis, política...), agora também com escolhas do jogador em cada sistema.

## 4. Regra para toda atualização futura
Nenhum sistema novo é "feito" se o jogador só assiste. Cada sistema precisa responder: **o que o jogador pode escolher aqui, e qual a consequência?** Registrar essa resposta no CHANGELOG.
