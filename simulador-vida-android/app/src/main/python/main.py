import sys


def run(argv: list[str]) -> int:
    """Sem argumentos: interface gráfica no navegador (v0.14.0). `--cli`: a interface de texto (v0.1–0.13)."""
    if "--cli" in argv:
        from sim.ui_cli import main as cli_main
        return cli_main([a for a in argv if a != "--cli"])
    from sim.ui_web import main as web_main
    return web_main(argv)


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
