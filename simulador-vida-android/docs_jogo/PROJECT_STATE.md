# PROJECT_STATE

Versão: 0.20.0 | Atualizado: 2026-11-25 | Fase atual: Grande atualização v0.20.0 concluída (psicologia, vínculos multidimensionais, enciclopédia/idiomas/205 livros, cursos técnicos, estágio/freela/expansão, equipamentos/plano de saúde/extrato, save v19)

## Como executar e testar
- Jogar (Web local): `PYTHONPATH=app/src/main/python python3 app/src/main/python/main.py` (Python 3.10+, só biblioteca padrão; saves em `saves/*.db`)
- Jogar (CLI): `PYTHONPATH=app/src/main/python python3 app/src/main/python/main.py --cli`
- Testes: `PYTHONPATH=app/src/main/python:docs_jogo python3 -m unittest discover -s docs_jogo/tests -t docs_jogo -v` (E2E opcionais com Playwright/Chromium: `tests/e2e_browser.py`, `tests/e2e_morte.py`, `tests/e2e_morte_herdeiros.py`, `tests/e2e_voltar_memoria.py`)
- APK Android: compilado via GitHub Actions (`.github/workflows/build-apk.yml`) ou localmente com JDK 17 + Android SDK 34 + Gradle 8.7 (`gradle assembleDebug` — este contêiner não possui Java/Android SDK/Gradle instalados).

## Já funciona (verificado por teste)
- Criar partida com semente; criar personagem de qualquer idade (0–110) e família (mãe, pai, 0–10 filhos, idades coerentes).
- Calendário mensal; avançar 1 mês / 6 meses / 1 ano, com virada de ano correta.
- Idade (muda exatamente no mês de nascimento), etapas de vida, saúde, mortalidade, morte e luto familiar.
- Mortalidade calibrada: expectativa simulada ≈ 75 anos (teste de faixa 73–77); saúde não colapsa na velhice.
- Cônjuge: vínculo mútuo na criação da família, exibido na ficha, com luto de viúvo(a) na biografia.
- Nascimento de filhos durante a simulação: casais vivos com mulher de 15–44 anos, intervalo mínimo de 15 meses, máximo de 10 filhos; ≈1,87 filho por mulher medido; eventos na biografia dos pais e do bebê.
- Casamento durante a simulação: solteiros vivos ≥18 anos se unem por sorteio mensal, com sexos diferentes, diferença de idade ≤10 anos e sem parentesco próximo; viúvos casam de novo; ≈59% dos solteiros de 20–29 anos casados em 10 anos; evento `casamento` para os dois.
- Biografia cronológica com filtro por personagem, categoria e período.
- Salvar/carregar em SQLite (atômico); continuar após carregar produz o mesmo resultado que não parar (estado do RNG persistido).
- CLI completa: novo/carregar, ver/listar/trocar personagem, criar personagem/família, avançar, biografia, salvar.

- Herança no nascimento: personalidade e potencial cognitivo vêm dos pais (herdabilidade 0,4 / 0,5 + ruído); correlação filho–pais ≈0,3; média e variância da população estáveis.
- Cognição se desenvolve com a idade (35% do potencial ao nascer → 100% aos 18).
- Divórcio: risco anual ≈1,4% por casal, modulado pela personalidade e pela idade; ex-cônjuge registrado; recasamento permitido (nunca com o ex); eventos para o casal e os filhos menores.
- Parentesco ampliado bloqueia união entre avós/netos, tios/sobrinhos e primos de 1º grau.
- Mortalidade materna no parto (risco pequeno, sobe com idade e saúde baixa).
- CLI: estado civil, ex-cônjuge, cognição atual/potencial das crianças, opção 11 (árvore familiar).
- Círculo social: amizades mensais por afinidade de personalidade e extroversão (máx. 8 amigos vivos, faixa de idade, sem parentes); luto de amigo; o casamento escolhe o parceiro no círculo (amigos e amigos de amigos), com 40% de chance de conhecer alguém de fora se o círculo não tiver parceiro compatível. Interruptor `engine.CIRCULO_SOCIAL`.
- Educação básica: matrícula aos 6 anos (fevereiro), ano letivo (dezembro) com desempenho por cognição ajustada à idade, conscienciosidade e saúde; aprovação/reprovação, abandono, conclusão do fundamental (9 anos) e do médio (12); colegas de turma ganham peso nas amizades. Medido: ≈92% concluem o fundamental, ≈72% o médio, ≈6% de reprovação. Interruptor `engine.EDUCACAO`.
- Ensino superior (4 anos): ingresso em fevereiro por idade e aptidão, aprovação/reprovação/abandono anual, formatura; retorno aos estudos de adultos (18–45 anos) que pararam antes de concluir o médio. Medido: ≈34% ingressam e ≈24% se formam (coorte até ~30 anos); ≈3% retornam. Interruptor `engine.ENSINO_SUPERIOR`.
- Trabalho (v0.6.0, `sim/work.py` + `engine._work`): ≥16 anos fora da escola entram no mercado ("procura trabalho"); contratação mensal por aptidão (cognição + conscienciosidade), idade e saúde; ocupação sorteada entre 19 ocupações genéricas que exigem escolaridade e aptidão mínimas (formação importa, não garante: ≈42–48% dos graduados em vaga de nível superior); perda de emprego (menor com conscienciosidade alta e vínculo longo); troca para ocupação melhor após formação maior; aposentadoria a partir de 60 anos (todos aos 75). Medido: ≈83–94% empregados e 6–17% de desemprego aos 25–54 anos. Interruptor `engine.TRABALHO`.
- Situação de trabalho inicial de adultos criados/carregados sem RNG (`work.default_work`). Ficha da CLI mostra "Trabalho".
- Economia e carreira (v0.7.0, `sim/economy.py` + `work.py` + `engine.economy.apply_month`): salário por ocupação × nível (júnior/pleno/sênior/chefia) × experiência × formal/informal (informal −20%, 1,5× mais demissões); promoção só para formais (≥24 meses no nível, ×aptidão); renda mensal e patrimônio por personagem; domicílio (casal + dependentes) com custo de vida, poupança por conscienciosidade, rendimento, dívida limitada e auxílio social por baixa renda per capita; aposentadoria com benefício (formal 70% do último salário; informal 1 mínimo); herança na morte (cônjuge/filhos); colegas de trabalho (mesmo local) pesam ×3 nas amizades. Medido: renda média dos empregados ≈2,2 mínimos, Gini ≈0,35, endividados 4–11%. Valores ilustrativos, em reais constantes. Interruptor `engine.ECONOMIA`.
- CLI: opção 12 (Finanças do domicílio) e 13 (Panorama econômico); ficha mostra renda, patrimônio, nível e vínculo.
- Empresas e vagas (v0.8.0, `sim/firms.py` + `engine._work`): 24 empresas genéricas iniciais (7 setores, 4 portes) com vagas por ocupação; contratação e troca de ocupação só em ocupações com vaga livre; `workplace` = id da empresa (colegas = mesma empresa); em janeiro: fechamento de empresas por porte (demite todos), enxugamento de vagas excedentes, dissolução de empresas vazias e reposição de vagas até vacância-alvo de 12% (expandindo ou fundando). Informalidade depende do porte. Medido: emprego 25–54 anos ≈84–87%; vacância cai com a população (≈67% com 12 famílias, ≈22% com ~800 pessoas). Interruptor `firms.ATIVO`.
- CLI: opção 14 (Empresas e vagas); ficha mostra a empresa.
- Ciclo econômico (v0.9.0, `sim/cycle.py`): índice anual determinístico por semente e ano (−1 a +1, sem `game.rng`, nada a salvar) que modula contratação (×0,55–1,45), demissão (×0,5–1,5), fechamento de empresas (×0,2–1,8) e vacância-alvo (×0,5–1,5). Medido: emprego 25–54 anos ≈87,7% (≈87,2% sem ciclo), desvio 4,7 pp; correlação índice × emprego ≈0,33. Interruptor `cycle.ATIVO`. Panorama mostra o clima.
- Seguro-desemprego (v0.9.1): demissão involuntária de vínculo formal com ≥12 meses → 60% do último salário (piso 1, teto 2 mínimos), 4 ou 5 parcelas; novo emprego ou aposentadoria encerra. Ficha mostra a última parcela. Interruptor `economy.SEGURO_ATIVO`.
- Prêmio salarial por porte (v0.9.2): micro 0,90 / pequena 0,97 / média 1,06 / grande 1,14 sobre o salário (e a aposentadoria). Interruptor `economy.PREMIO_PORTE`. Renda média dos empregados ≈+6,6%.
- Fim de amizades (v0.10.0): afastamento anual-base 5% por amizade (maior com baixa afinidade/diferença de idade; menor entre colegas e em amizades longas); evento `amizade_fim`. Interruptor `engine.FIM_AMIZADES`.
- Gêmeos (v0.10.0): 1,2% dos partos; evento `gemeos`. Interruptor `engine.GEMEOS`.
- Guarda dos filhos (v0.10.0): no divórcio, menores de 18 ficam com a mãe (maioria) ou o pai (pesa a renda); `guardian_id` define o domicílio e o sustento. Interruptor `engine.GUARDA`.
- Namoro (v0.11.0, `sim/romance.py`): casais entre solteiros ≥16 anos (círculo social, afinidade, regras de parentesco/idade), término e pedido de casamento (≥6 meses, ambos ≥18); eventos `namoro`/`namoro_fim`; sem `game.rng` (gerador local por semente/mês). Medido: casamentos ≈ iguais aos da 0.10.0 (85–98 contra 83–86 em 300 adultos/10 anos). Interruptor `romance.ATIVO`.
- Gestação (v0.12.0): concepção → 9 meses → parto; perda gestacional de 8% no 3º mês; grávida não engravida; pai falecido não impede o parto; morte da mãe encerra a gestação; eventos `gravidez`. Medido: 1,73 → 1,68 filho/mulher em 25 anos (parto imediato × gestação). Interruptor `engine.GESTACAO`.
- Macroeconomia (v0.13.0, `sim/macro.py`): inflação anual determinística por (semente, ano) = 4,5% + 2 pp × índice do ciclo + ruído (limites 1–12%); índice de preços sobe todo mês; o salário mínimo nominal só é reajustado em janeiro (inflação do ano anterior + ganho real 1–2%). Salários, aposentadoria, seguro e auxílio são múltiplos do mínimo nominal; o custo de vida segue os preços; o patrimônio rende a taxa real + inflação e a dívida cobra juros + inflação (teto da dívida acompanha os preços). Efeito: o poder de compra cai ao longo do ano e é recomposto em janeiro. Medido (20 anos, 3 sementes): preços ×2,2–2,5 (≈4,2% a.a.), mínimo real 1,23–1,25× (≈+1,1% a.a.). Estado em `game.macro` (salvo em `meta`). Interruptor `macro.ATIVO`.
- Impostos e orçamento do Estado (v0.13.0, `economy.income_tax`): só vínculo formal e não aposentado pagam previdência (8% até 6 mínimos) + IR progressivo (faixas 2,5/3,5/5/7 mínimos; 0–27,5%); alíquota efetiva de 8% (1 mínimo) a ≈15% (6 mínimos) e ≈24% (12). O saldo do domicílio desconta o imposto. Orçamento: receita = impostos; despesa = aposentadorias + seguro + assistência a ≥65 + licenças-maternidade + auxílio social; `game.macro` guarda ano corrente, ano anterior e caixa acumulado; panorama mostra. Sem retroalimentação (o déficit não muda regras). Medido: despesa > receita (aposentadorias sem contribuição prévia modelada; população envelhece). Interruptor `economy.IMPOSTOS`.
- Pensão alimentícia (v0.13.0, `economy.alimony_flows`): o genitor vivo, adulto e com renda que não é o guardião (nem cônjuge dele) repassa 15% da renda por 1 filho menor (+5% por filho adicional, teto 30%) ao guardião; entra na renda dos dois domicílios (finanças da CLI mostram pago/recebido). Interruptor `economy.PENSAO`.
- Licença-maternidade (v0.13.0, `engine._maternity`, `economy.on_leave`): no parto, mãe formal empregada tem 4 meses de licença com salário integral (pago pelo Estado); estabilidade contra demissão durante a gestação e a licença (só vínculo formal); 6% das formais e 25% das informais deixam o emprego para cuidar do bebê e ficam 12 meses sem procurar trabalho (`Character.leave_until`). Sorteios por gerador local (não consome `game.rng`). Eventos `trabalho`. Interruptor `engine.LICENCA` (só vale com `GESTACAO` ligada).
- Save v14 (v1–v13 legíveis; coluna `leave_until` e chave `macro` em `meta`; saves antigos começam com preços 1,0, mínimo R$ 1.500 e caixa zerado).
- Save v13 (v1–v12 legíveis; escolaridade, trabalho, economia e empresas inferidos na carga; seguro-desemprego sem benefício em curso em saves antigos).

## v0.19.0 — navegação e memória (verificado em Chromium; APK não testado em aparelho)
- Botão **Voltar** em todas as telas de Ações (volta ao menu Ações) e gancho do botão físico do Android (`window.__simVoltar` ← `MainActivity.onBackPressed`). Memória de busca/filtros/abas/seleções/rolagem por partida (`ui.js: memoria/lembrar`), opção "Lembrar onde eu estava" em Ajustes. Teste: `tests/e2e_voltar_memoria.py` (Playwright). Detalhes no CHANGELOG 0.19.0.
- Tela nova com listas, filtros, abas ou campos: use `lembrar('tela.campo', el)`, `seg(..., 'tela.aba')` e `dialogo({ aoVoltar, rolagem })` para herdar o comportamento.

## v0.20.0 — grande atualização sistêmica
- **Psicologia (`sim/psicologia.py`)**: valores e medos derivados da personalidade; 4 hábitos mensais (`exercicio`, `leitura_diaria`, `meditacao`, `voluntariado`); catálogo de 15 objetivos individuais (até 3 ativos com verificação e recompensas); indicador opcional de QI (`qi_estimado`) e persistência em `meta['psicologia']`.
- **Vínculos multidimensionais e diversidade afetiva (`sim/vinculos.py`, `sim/encontros.py`)**: relações em 5 dimensões (`afinidade`, `confianca`, `intimidade`, `respeito`, `hostilidade`), histórico de memórias, 6 ações (`conversar`, `convidar`, `apoiar`, `networkar`, `confrontar`, `reconciliar`), rivalidade (≥50) e inimizade (≥80); preferência afetiva configurável (`oposto`, `mesmo`, `todos`).
- **Enciclopédia, idiomas e leitura (`sim/intelecto.py` + `sim/livros.py`)**: 16 áreas × 48 subdisciplinas com pesquisa e publicação científica; 6 idiomas (Inglês, Espanhol, Francês, Alemão, Italiano e Libras) com bônus salarial até +15%; curva mensal de esquecimento (`retencao`) recuperável via revisão espaçada e grupos de estudo; catálogo ampliado de 129 para **205 obras reais**.
- **Educação e ocupações (`sim/educacao_br.py` + `sim/work.py` + `sim/firms.py`)**: 5 cursos técnicos (Instituto Federal gratuito ou rede privada, `ocupacao_preferida`), `CURSO_TIPO` (Bacharelado/Licenciatura/Tecnólogo) e 4 novas ocupações de nível superior (`psicologo`, `economista`, `pesquisador`, `designer`).
- **Carreiras e participação (`sim/carreiras.py`)**: estágio/meio período compatível com estudos, projetos freelancer (até 2/mês), expansão ativa de empresa própria (`micro → pequena → média → grande`), participação em movimentos sociais e proposição de projetos de lei em mandato eletivo.
- **Mundo e utilidades (`sim/mundo.py`)**: 4 equipamentos pessoais (`notebook`, `biblioteca`, `kit_esportivo`, `instrumento`) com bônus reais, plano de saúde particular mensal, registro e extrato de movimentações financeiras e notícia real do Censo Demográfico decenal (2030+).
- **Decisões, UI e persistência (`sim/decisions.py` + `sim/persistence.py` + `sim/ui_web.py` + `sim/panels.py` + `web/js/panels.js`)**: +12 eventos de 3 opções; 19 novas rotas HTTP e novas abas/telas na interface web; **Save v19** preservando todos os estados novos com migração retrocompatível a partir de v1–v18.

## Estrutura
- Motor e regras: `sim/models.py`, `sim/factory.py`, `sim/engine.py`, `sim/persistence.py` (SQLite, schema v19).
- Trabalho e macroeconomia: `sim/work.py`, `sim/firms.py`, `sim/cycle.py`, `sim/economy.py`, `sim/macro.py`.
- Vida pessoal, educação e intelecto: `sim/romance.py`, `sim/conhecidos.py`, `sim/convivio.py`, `sim/encontros.py`, `sim/vinculos.py`, `sim/psicologia.py`, `sim/educacao_br.py`, `sim/intelecto.py`, `sim/livros.py`.
- Sociedade, carreira e decisões: `sim/decisions.py`, `sim/foco.py`, `sim/carreiras.py`, `sim/mundo.py`, `sim/achievements.py`, `sim/herdeiros.py`, `sim/saude.py`, `sim/moradia.py`, `sim/familia.py`, `sim/tempo.py`.
- Interfaces e WebView Android: `sim/ui_web.py`, `sim/panels.py`, `sim/ui_cli.py`, `app/src/main/assets/web/` (`index.html`, `js/app.js`, `js/ui.js`, `js/panels.js`, `css/style.css`), `app/src/main/java/com/lazanha/simulador/MainActivity.kt`.
- Documentação e testes: `docs_jogo/` (`ARCHITECTURE.md`, `CHANGELOG.md`, `ROADMAP.md`, `TESTS.md`, `tests/`). Detalhes em `ARCHITECTURE.md`.

## Incompleto / limitações atuais
- Gestação e licença-paternidade: gestação concentrada em relacionamentos; sem licença-paternidade dedicada.
- Orçamento do Estado sem retroalimentação macroeconômica dinâmica (déficit fiscal não reajusta juros/impostos automaticamente; inflação modelada de forma exógena ao emprego); sem câmbio externo.
- Personalidade base (Big Five) permanece estável após a vida adulta (oscilações de bem-estar ocorrem via eixos de `psicologia`).
- CLI (`sim/ui_cli.py`) continua sem todas as sub-telas interativas da interface web/Android (`ui_web.py` + `panels.py`), sendo a WebUI a experiência principal.
- Compilação do APK: o projeto Android (`build.gradle.kts`, `settings.gradle.kts`) está configurado na v0.20.0 (`versionCode = 2000000`), porém não pôde ser compilado nem testado em dispositivo neste ambiente (ausência de JDK, Android SDK e Gradle no contêiner); compilação automatizada via `.github/workflows/build-apk.yml`.

## Problemas conhecidos (resumo técnico)
1. As taxas de mortalidade e faixas salariais continuam ilustrativas e calibradas para jogabilidade em reais constantes.
2. Em populações muito pequenas nas simulações, o piso de vagas abertas por ocupação pode suavizar picos locais de desemprego.
3. Os testes E2E em Playwright (`tests/e2e_*.py`) são opcionais e requerem `playwright` + Chromium instalados fora da biblioteca padrão.

