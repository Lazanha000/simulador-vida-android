"""Ponte Android: sobe o servidor HTTP do jogo (sim.ui_web, sem alterações) em 127.0.0.1 para o WebView."""
import threading

from sim import ui_web

_app = None
_srv = None


def start(saves_dir, web_dir, port=8765):
    global _app, _srv
    if _srv is not None:
        return _srv.server_address[1]
    ui_web.WEB = web_dir  # os arquivos web/ ficam em pasta real, extraída dos assets
    _srv, _app = ui_web.criar_servidor(saves_dir, "127.0.0.1", port, False)
    threading.Thread(target=_srv.serve_forever, daemon=True).start()
    return _srv.server_address[1]


def flush():
    """Chamado em onPause/onStop: o Android pode matar o processo sem aviso."""
    if _app is None:
        return
    with _app.lock:
        if _app.game is not None and _app.dirty and _app.autosave:
            _app._salvar()
