# COERÊNCIA INTERNA COM OS PROMPTS

Regra: a cada 5 sessões de desenvolvimento, comparar a rota atual com o `PROMPT GERAL.txt`, o `PROTOCOLO.txt` e o `DIRECAO.md`, e registrar abaixo.
Contador: sessões desde a última avaliação = 2 (G1, G2a). **Próxima avaliação: após a sessão da G5 (ou na 5ª sessão contada a partir de agora).**

## Checklist rápido (preencher a cada avaliação)
1. O jogador decide algo em cada sistema novo? (princípios 3 e 5 do PROMPT GERAL)
2. Nada decorativo antes do funcional? 3. Mundo continua rodando sem o jogador? 4. Save íntegro e migrado?
5. Cada sessão foi UMA microatualização? 6. Status dito com evidência (não iniciado → esqueleto → parcial → implementado → testado → verificado)?
7. Android: toda tela nova é usável com o polegar (alvos ≥ 48 px, sem hover, sem teclado)?

## Avaliação 0 (2026-11-24, ponto de partida)
- Rota G1→G4 corrige o desvio antigo (mundo sem escolhas): coerente com PROMPT GERAL §3 e §5.
- Risco 1: o PROMPT GERAL pede muita coisa (política, empreendedorismo, etc.); G1–G4 não as contradizem, mas adiam. Aceitável se o jogo ficar divertido primeiro.
- Risco 2: foco em Android (WebView + Python embarcado via Chaquopy) é pesado para celular fraco e o build depende do GitHub Actions. Não foi testado em aparelho real: status "não verificado".
- Risco 3: 14 eventos repetem rápido; só G2+ dá profundidade. Não aumentar o catálogo antes disso.
- Dívida: suíte completa não rodada na 0.15.0; a CLI não tem decisões (divergência entre interfaces).

## Notas de sessão
- 0.15.1: a G2 foi dividida (foco agora, área de estudo depois) para manter microatualização e porque as áreas ainda não foram decididas pelo dono. Coerente com o PROTOCOLO.
- Erro de processo detectado: a G1 assumiu escala 0–1 sem checar o código; corrigido. Regra: checar a escala/unidade dos dados antes de escrever efeitos.
