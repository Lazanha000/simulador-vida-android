# ARCHITECTURE

## Decisões técnicas
- Python 3 + biblioteca padrão + SQLite: executa localmente, sem dependências, sem serviços pagos nem APIs externas.
- Interface de texto agora; a camada de interface é separada, então pode ser trocada depois sem tocar nas regras.

## Camadas e responsabilidades
| Arquivo | Responsabilidade |
|---|---|
| `sim/models.py` | Dados puros: `Character`, `Family`, `Firm`, `BioEvent`, `Game` (estado da partida, calendário, biografia, amizades). Sem regras. |
| `sim/work.py` | Trabalho (v0.6.0): tabela de ocupações genéricas e regras puras (elegibilidade, contratação, perda de emprego, aposentadoria, situação inicial). Sem dependência do motor; importado por `factory`, `engine`, `persistence` e `ui_cli`. |
| `sim/firms.py` | Empresas e vagas (v0.8.0): criação determinística de empresas genéricas, vagas por ocupação, escolha de empresa, fechamento, rebalanceamento anual e panorama de vacância. Sem `game.rng` (gerador local da semente). Importa `work` e `models`; `work.start_job` e `economy` o usam (import tardio em `start_job` evita ciclo). |
| (gestação, v0.12.0) | Vive em `sim/engine.py` (`_conceive`, `_pregnancy_step`, `_births`): campos `pregnant_until`/`pregnancy_father_id` em `Character`; perda, gêmeos e morte materna usam gerador local por (semente, mês, mãe). |
| `sim/romance.py` | Namoro (v0.11.0): casais, término e pedido de casamento. Sem `game.rng` (gerador local por semente/mês/id). Usa `engine` por import tardio (funções de parentesco, casamento, círculo social, afinidade). `engine._tick` chama `romance.run` depois dos divórcios e antes dos casamentos. |
| `sim/cycle.py` | Ciclo econômico (v0.9.0): índice anual determinístico por semente e ano (AR(1)), fatores de contratação, demissão, fechamento e vacância. Sem `game.rng`, sem estado a salvar; importado por `engine`, `firms` e `economy`. |
| `sim/macro.py` | Macroeconomia (v0.13.0): inflação anual (determinística por semente/ano), índice de preços, salário mínimo dinâmico, caixa do Estado em `game.macro`. Não usa `game.rng`; importa só `cycle` (sem import circular com `economy`). `economy` consome `macro.min_wage/price_level`. |
| `sim/economy.py` | Economia (v0.7.0; seguro-desemprego 0.9.1; prêmio por porte 0.9.2): salário, benefício, domicílios, custo de vida, poupança/dívida, herança, Gini e panorama. Funções puras ou determinísticas, sem `game.rng`. Importa `work` e `models`; importado por `factory`, `engine`, `persistence` e `ui_cli`. |
| `sim/factory.py` | Criação de partida, personagens e famílias (datas de nascimento coerentes); herança de traços e fração de desenvolvimento cognitivo. |
| `sim/engine.py` | Passagem do tempo (`advance_months`), idade, etapas, saúde, mortalidade, morte, luto, nascimentos (`_births`), escola (`_school`, inclui superior e retorno aos estudos), trabalho (`_work`), amizades (`_friendships`), divórcios (`_divorces`) e casamentos (`_marriages`, escolhe parceiro no círculo social), nessa ordem, depois das mortes de cada mês. |
| `sim/persistence.py` | Salvar/carregar em SQLite (esquema **v19**, tolera saves v1–v18), gravação atômica via arquivo temporário. |
| `sim/psicologia.py` | Psicologia, valores, medos, 4 hábitos mensais, 15 metas de vida e QI opcional (v0.20.0; sem `game.rng`). |
| `sim/vinculos.py` | Vínculos multidimensionais (afinidade, confiança, intimidade, respeito, hostilidade, memórias), família, colegas e rivais/inimigos (v0.20.0; sem `game.rng`). |
| `sim/intelecto.py` | Estudo dirigido, redação/ensaio, artigos, filmes, 16 áreas enciclopédicas (48 subdisciplinas), 6 idiomas, revisão espaçada, grupos de estudo, pesquisa e curva de esquecimento (v0.18.0–v0.20.0). |
| `sim/livros.py` | Catálogo de 205 obras reais, leitura por páginas, capacidade mensal e ganho de cognição/conhecimentos (v0.15.11–v0.20.0). |
| `sim/educacao_br.py` | ENEM, universidades brasileiras, SISU/PROUNI/FIES, vestibular, IC, pós-graduação e cursos técnicos (v0.17.0–v0.20.0). |
| `sim/carreiras.py` | Concursos públicos, abertura e expansão de empresas, estágio/meio período, freelancers, política, movimentos sociais e projetos de lei (v0.17.0–v0.20.0). |
| `sim/mundo.py` | Cidades brasileiras, imóveis, veículos, equipamentos pessoais, plano de saúde, investimentos, empréstimos, extrato financeiro e noticiário `[REAL]`/`[SIMULADA]` (v0.17.0–v0.20.0). |
| `sim/decisions.py` | Eventos interativos de 3 opções e consequências com atraso (v0.15.0–v0.20.0). |
| `sim/views.py` & `sim/panels.py` | Serialização de estado, avanço mensal com pausas em decisão e painéis de leitura da UI web. |
| `sim/ui_web.py` & `sim/ui_cli.py` | Servidor HTTP local + WebView Android e modo CLI. Não contêm regras de simulação. |
| `main.py` & `android_launcher.py` | Pontos de entrada desktop/CLI e Android (Chaquopy). |

## Regras de projeto
- Toda aleatoriedade usa `game.rng`, consumida em ordem determinística (ids crescentes). O estado do RNG é salvo, então carregar e continuar é idêntico a não parar.
- O tempo avança sempre mês a mês; passos de 6 e 12 meses são repetições do passo mensal.
- Novos sistemas entram como funções chamadas dentro de `engine._tick`, na ordem cronológica do mês.
- Ordem do mês em `_tick`: avançar calendário → por personagem vivo (id crescente): aniversário (inclui desenvolvimento cognitivo), saúde, morte → nascimentos (e morte no parto) → escola (matrícula em fevereiro, resultado em dezembro) → trabalho (aposentadoria, perda de emprego, troca de ocupação, promoção, entrada no mercado e contratação) → economia (`economy.apply_month`: renda, experiência, saldo do domicílio, rendimentos; herança acontece em `_die`) → amizades → divórcios → casamentos. Recém-nascidos só entram no laço no mês seguinte.
- Situações iniciais determinísticas (escolaridade, trabalho, economia) usam gerador local e nunca `game.rng`, para não alterar o fluxo do RNG na criação/carga. O mesmo vale para a carreira em curso (promoção, formal/informal, local de trabalho): `work.local_rng(game, c, sal)` deriva de semente+personagem+mês+sal.
- Mudanças no esquema de save exigem incrementar `SCHEMA_VERSION` e uma migração. Padrão adotado (v1→v2): colunas novas ficam no fim da tabela; `SUPPORTED_VERSIONS` lista as versões legíveis; o loader preenche padrões para o que falta e o arquivo antigo só é regravado no formato atual em um novo salvamento.

## Riscos técnicos
1. Calibração das probabilidades (hoje ilustrativas).
2. Crescimento do número de NPCs: o laço mensal é O(personagens); `_births` já usa índice mãe→filhos por mês; `_marriages` monta a lista de solteiros por mês e, a cada união, varre os candidatos (O(solteiros)); otimizar quando necessário.
3. Evolução do esquema de save sem migração.
4. Conteúdo real (instituições, livros): deve ficar em dados separados e verificáveis, sem inventar fatos.
