"""
Entry point: inicializa la base de datos, arranca el bucle del LCD en un
hilo de fondo y levanta el servidor web (Flask) en el hilo principal.

Uso:
    python3 app.py                    # LCD_BACKEND=auto (real si hay smbus, si no consola)
    LCD_BACKEND=console python3 app.py  # fuerza el backend de consola (desarrollo)
"""

import logging
import secrets
import threading

from flask import Flask, jsonify

from core import db
from core.config import WEB_HOST, WEB_PORT
from core.lcd_loop import get_status, run_loop
from web.routes import bp as web_bp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # solo firma la cookie de flash; se regenera en cada arranque
app.register_blueprint(web_bp)
stop_event = threading.Event()


@app.get("/api/status")
def api_status():
    return jsonify(get_status())


def main():
    db.init_db()

    loop_thread = threading.Thread(target=run_loop, args=(stop_event,), daemon=True)
    loop_thread.start()

    try:
        app.run(host=WEB_HOST, port=WEB_PORT, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        loop_thread.join(timeout=5)


if __name__ == "__main__":
    main()
