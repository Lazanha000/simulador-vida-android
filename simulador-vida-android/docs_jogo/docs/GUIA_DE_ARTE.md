# Simulador — kit de arte "Manuscrito iluminado"

Tudo em SVG (vetorial, escala sem perder qualidade). Os SVGs **não têm texto**: os rótulos (nome, idade, "Escola"…) são desenhados pelo jogo com as fontes abaixo.

## Paleta
| Nome | Hex | Uso |
|---|---|---|
| Pergaminho | #f3e5b6 / #d8bb78 | fundo |
| Ouro | #c9a227 / #f6e3a1 | bordas, anéis, destaques |
| Lápis-lazúli | #1d3a8a | avatares, ícones, capitulares |
| Vermelhão | #b3261e | selo, ênfase, capitular |
| Vinho | #7a1f1f | títulos, faixas |
| Malaquita | #2f6b45 | saúde, trabalho |
| Roxo | #5a2a6a | amizade, namoro |
| Ocre | #c77d1a | bens, formatura |
| Tinta | #3b2410 | texto |
| Cinza-cinza | #6f6a60 | desabilitado, fim |

## Fontes (Google Fonts, licença OFL)
- **UnifrakturMaguntia**: nome do personagem, título, números do selo e capitulares.
- **IM Fell English** (regular e itálico): todo o texto corrido, rótulos, faixas de idade (caixa-alta com espaçamento de 3 px).

## Regras de uso
- Texto sobre pergaminho: cor tinta. Texto sobre faixa/selo/capitular: ouro claro.
- Moldura de tela, painéis e diálogos: esticar com 9-slice (cantos fixos de 40 px).
- `faixa_borda_64x16` repete horizontalmente. `pergaminho_tile_256` repete nos dois eixos.
- Barras: desenhe `barra_fundo`, depois recorte `barra_cheia_*` na largura proporcional ao valor (com 4 px de margem interna).
- Selo: estados normal/pressed/disabled; use `selo_1mes`, `selo_6meses` e `selo_1ano` nos botões de avanço do jogo.
- Falecido: `avatar_falecido_*`, `moldura_tela_luto`, `pergaminho_luto_tile`, `faixa_luto`.
- Capitular: ponha a letra inicial do primeiro parágrafo (UnifrakturMaguntia, ouro claro) sobre a moldura.

## Avatares
Etapas: bebê (0–2), criança (3–11), adolescente (12–17), jovem (18–34), adulto (35–59), idoso (60+); sexo f/m; 5 tons de pele em `avatares/variantes/`. O gerador aceita cor de cabelo: `avatar(etapa, sexo, pele, cabelo, dead)`.

## Arquivos

### Ícones da barra e menus (96×96)
- `icones/icone_escola.svg`
- `icones/icone_bens.svg`
- `icones/icone_relacoes.svg`
- `icones/icone_trabalho.svg`
- `icones/icone_saude.svg`
- `icones/icone_cognicao.svg`
- `icones/icone_social.svg`
- `icones/icone_familia.svg`
- `icones/icone_biografia.svg`
- `icones/icone_arvore.svg`
- `icones/icone_empresas.svg`
- `icones/icone_panorama.svg`
- `icones/icone_impostos.svg`
- `icones/icone_salvar.svg`
- `icones/icone_carregar.svg`
- `icones/icone_config.svg`
- `icones/icone_seguro.svg`

### Miniaturas de eventos da biografia (96×96)
- `eventos/evento_nascimento.svg`
- `eventos/evento_morte.svg`
- `eventos/evento_casamento.svg`
- `eventos/evento_divorcio.svg`
- `eventos/evento_namoro.svg`
- `eventos/evento_gravidez.svg`
- `eventos/evento_gemeos.svg`
- `eventos/evento_escola_inicio.svg`
- `eventos/evento_formatura.svg`
- `eventos/evento_emprego.svg`
- `eventos/evento_promocao.svg`
- `eventos/evento_demissao.svg`
- `eventos/evento_aposentadoria.svg`
- `eventos/evento_amizade.svg`
- `eventos/evento_amizade_fim.svg`
- `eventos/evento_heranca.svg`
- `eventos/evento_ciclo_economico.svg`
- `eventos/evento_inflacao.svg`
- `eventos/evento_guarda.svg`

### Avatares — medalhões por etapa de vida e sexo (120×120)
- `avatares/avatar_bebe_f.svg`
- `avatares/avatar_bebe_m.svg`
- `avatares/avatar_crianca_f.svg`
- `avatares/avatar_crianca_m.svg`
- `avatares/avatar_adolescente_f.svg`
- `avatares/avatar_adolescente_m.svg`
- `avatares/avatar_jovem_f.svg`
- `avatares/avatar_jovem_m.svg`
- `avatares/avatar_adulto_f.svg`
- `avatares/avatar_adulto_m.svg`
- `avatares/avatar_idoso_f.svg`
- `avatares/avatar_idoso_m.svg`
- `avatares/avatar_falecido_f.svg`
- `avatares/avatar_falecido_m.svg`

### Variações de tom de pele (120×120)
- `avatares/variantes/avatar_bebe_f_pele1.svg`
- `avatares/variantes/avatar_bebe_f_pele2.svg`
- `avatares/variantes/avatar_bebe_f_pele3.svg`
- `avatares/variantes/avatar_bebe_f_pele4.svg`
- `avatares/variantes/avatar_bebe_f_pele5.svg`
- `avatares/variantes/avatar_bebe_m_pele1.svg`
- `avatares/variantes/avatar_bebe_m_pele2.svg`
- `avatares/variantes/avatar_bebe_m_pele3.svg`
- `avatares/variantes/avatar_bebe_m_pele4.svg`
- `avatares/variantes/avatar_bebe_m_pele5.svg`
- `avatares/variantes/avatar_crianca_f_pele1.svg`
- `avatares/variantes/avatar_crianca_f_pele2.svg`
- `avatares/variantes/avatar_crianca_f_pele3.svg`
- `avatares/variantes/avatar_crianca_f_pele4.svg`
- `avatares/variantes/avatar_crianca_f_pele5.svg`
- `avatares/variantes/avatar_crianca_m_pele1.svg`
- `avatares/variantes/avatar_crianca_m_pele2.svg`
- `avatares/variantes/avatar_crianca_m_pele3.svg`
- `avatares/variantes/avatar_crianca_m_pele4.svg`
- `avatares/variantes/avatar_crianca_m_pele5.svg`
- `avatares/variantes/avatar_adolescente_f_pele1.svg`
- `avatares/variantes/avatar_adolescente_f_pele2.svg`
- `avatares/variantes/avatar_adolescente_f_pele3.svg`
- `avatares/variantes/avatar_adolescente_f_pele4.svg`
- `avatares/variantes/avatar_adolescente_f_pele5.svg`
- `avatares/variantes/avatar_adolescente_m_pele1.svg`
- `avatares/variantes/avatar_adolescente_m_pele2.svg`
- `avatares/variantes/avatar_adolescente_m_pele3.svg`
- `avatares/variantes/avatar_adolescente_m_pele4.svg`
- `avatares/variantes/avatar_adolescente_m_pele5.svg`
- `avatares/variantes/avatar_jovem_f_pele1.svg`
- `avatares/variantes/avatar_jovem_f_pele2.svg`
- `avatares/variantes/avatar_jovem_f_pele3.svg`
- `avatares/variantes/avatar_jovem_f_pele4.svg`
- `avatares/variantes/avatar_jovem_f_pele5.svg`
- `avatares/variantes/avatar_jovem_m_pele1.svg`
- `avatares/variantes/avatar_jovem_m_pele2.svg`
- `avatares/variantes/avatar_jovem_m_pele3.svg`
- `avatares/variantes/avatar_jovem_m_pele4.svg`
- `avatares/variantes/avatar_jovem_m_pele5.svg`
- `avatares/variantes/avatar_adulto_f_pele1.svg`
- `avatares/variantes/avatar_adulto_f_pele2.svg`
- `avatares/variantes/avatar_adulto_f_pele3.svg`
- `avatares/variantes/avatar_adulto_f_pele4.svg`
- `avatares/variantes/avatar_adulto_f_pele5.svg`
- `avatares/variantes/avatar_adulto_m_pele1.svg`
- `avatares/variantes/avatar_adulto_m_pele2.svg`
- `avatares/variantes/avatar_adulto_m_pele3.svg`
- `avatares/variantes/avatar_adulto_m_pele4.svg`
- `avatares/variantes/avatar_adulto_m_pele5.svg`
- `avatares/variantes/avatar_idoso_f_pele1.svg`
- `avatares/variantes/avatar_idoso_f_pele2.svg`
- `avatares/variantes/avatar_idoso_f_pele3.svg`
- `avatares/variantes/avatar_idoso_f_pele4.svg`
- `avatares/variantes/avatar_idoso_f_pele5.svg`
- `avatares/variantes/avatar_idoso_m_pele1.svg`
- `avatares/variantes/avatar_idoso_m_pele2.svg`
- `avatares/variantes/avatar_idoso_m_pele3.svg`
- `avatares/variantes/avatar_idoso_m_pele4.svg`
- `avatares/variantes/avatar_idoso_m_pele5.svg`

### Molduras e painéis
- `ui/moldura_tela_390x740.svg`
- `ui/moldura_tela_luto_390x740.svg`
- `ui/moldura_dialogo_320x220.svg`
- `ui/painel_cabecalho_390x84.svg`
- `ui/faixa_borda_64x16.svg`
- `ui/placa_dinheiro_140x48.svg`
- `ui/toast_pergaminho_300x48.svg`
- `ui/slot_barra_icone_96.svg`

### Ornamentos
- `ui/divisor_1_300x24.svg`
- `ui/divisor_2_300x24.svg`
- `ui/divisor_3_300x24.svg`

### Faixas e títulos
- `ui/faixa_idade_240x34.svg`
- `ui/faixa_titulo_360x72.svg`
- `ui/faixa_ano_novo_300x44.svg`
- `ui/faixa_luto_300x44.svg`

### Capitulares (moldura da letra inicial, 64×64)
- `ui/capitular_azul_64.svg`
- `ui/capitular_vermelha_64.svg`
- `ui/capitular_verde_64.svg`

### Selo de cera (botão central, 128×128)
- `ui/selo_avancar_normal.svg`
- `ui/selo_avancar_pressed.svg`
- `ui/selo_avancar_disabled.svg`
- `ui/selo_1mes.svg`
- `ui/selo_6meses.svg`
- `ui/selo_1ano.svg`

### Barras de status (300×18)
- `ui/barra_fundo_300x18.svg`
- `ui/barra_cheia_saude_296x10.svg`
- `ui/barra_cheia_cognicao_296x10.svg`
- `ui/barra_cheia_social_296x10.svg`
- `ui/barra_cheia_patrimonio_296x10.svg`
- `ui/barra_cheia_felicidade_296x10.svg`

### Botões de menu (220×44)
- `ui/botao_menu_normal_220x44.svg`
- `ui/botao_menu_hover_220x44.svg`
- `ui/botao_menu_pressed_220x44.svg`
- `ui/botao_menu_disabled_220x44.svg`

### Ícone do app
- `ui/icone_app_512.svg`

### Fundos
- `fundos/pergaminho_tile_256.svg`
- `fundos/pergaminho_luto_tile_256.svg`
- `fundos/tela_titulo_390x740.svg`
