# v0.14.0 — Interface gráfica jogável com o kit de arte "Manuscrito iluminado"

Como jogar: `python3 main.py` (abre o navegador em http://127.0.0.1:8765). Só biblioteca padrão. `python3 main.py --cli` = interface de texto antiga.
Celular na mesma rede: `python3 main.py --host 0.0.0.0` (qualquer um na rede poderá ver a partida).

## Novo
- Servidor web local (`sim/ui_web.py`) + interface em `web/` (HTML/CSS/JS sem dependências), layout vertical 390x740 adaptável.
- Telas: título (Continuar / Novo jogo / Carregar), nova partida (Nascer numa família / Personagem avulso / Família pronta),
  carregar, jogo (cabeçalho com avatar e dinheiro, diário por idade, 5 barras, navegação com selo de avançar 1 mês/6 meses/1 ano).
- 17 painéis ligados aos dados reais do motor (escola, bens, relações, trabalho, saúde, mente, social, família, biografia com filtros,
  árvore, empresas, panorama, impostos, proteção social, personagens, ajustes) + ficha de qualquer personagem + bem-estar.
- Relatório do turno (ano novo com notícias econômicas), aviso de morte com herdeiros ("In memoriam", tema de luto), autosave, troca de personagem.
- Avatares gerados pelo jogo (`sim/avatar_art.py`, idênticos ao kit): aparência herdada dos pais, sem alterar o formato do save.
- Todos os 148 arquivos de arte são usados (conferido em teste). Guia da arte em `docs/GUIA_DE_ARTE.md`.
- `sim/indicators.py`: "Bem-estar" é indicador DERIVADO e ilustrativo (o motor não tem felicidade); não altera a simulação.
- `tools/baixar_fontes.py`: baixa as fontes para jogar offline (NÃO testado no ambiente de desenvolvimento, sem rede).

## Motor
- Única mudança: "Fez 1 ano." (singular). Regras, saves e RNG intactos; avançar em passos de 1 mês gera o mesmo resultado de avançar N meses (testado).

## Testes
- `tests/test_web.py` (25 testes novos). `tests/e2e_browser.py` (opcional, Playwright): percorre as telas e os 18 painéis sem erro de JS.
- Suíte antiga (231) passava na v0.13.0; rode `python3 -m unittest discover -s tests -t .` para reconfirmar na v0.14.0.

## Limitações conhecidas
- Sem internet as fontes caem para serifadas do sistema (visual menos "gótico").
- Uma partida por servidor; interface pensada para o navegador (não testada em Safari/Firefox).
