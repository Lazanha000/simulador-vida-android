# Simulador de Vida Brasileiro v0.14.4

**Jogar:** `python3 main.py` (navegador). Texto: `python3 main.py --cli`. Novidades: ver `DIRECAO.md` (prioridades futuras), `CHANGELOG.md` (0.14.4) e `CHANGELOG_0.14.0.md`.

---

# Simulador de Vida Brasileiro

Simulador de vida por turnos (1 mês / 6 meses / 1 ano), ambientado no Brasil: família, escola, trabalho, empresas e economia. Em desenvolvimento incremental; veja PROJECT_STATE.md para o que já existe.

## Executar
```
python3 main.py
```
Requer Python 3.10+. Sem instalação de pacotes. Os saves ficam em `saves/` (um arquivo `.db` por partida); use `--saves-dir PASTA` para mudar.

## Testar
```
python3 -m unittest discover -s tests -t . -v
```

## Documentos
ARCHITECTURE.md (arquitetura) · PROJECT_STATE.md (estado e próxima tarefa) · CHANGELOG.md · ROADMAP.md · TESTS.md
