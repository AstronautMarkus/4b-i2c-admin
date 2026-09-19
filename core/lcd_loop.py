import logging
import socket
import threading
import time

from core import db, registry, scanner
from core.config import WAITING_SCROLL_SECONDS, WEB_PORT
from core.lcd_iface import get_lcd_backend
from core.module_base import ModuleContext

logger = logging.getLogger("lcd_loop")

_STATUS_LOCK = threading.Lock()
_STATUS = {"state": "booting", "current_module": None, "ip": None}


def get_status():
    with _STATUS_LOCK:
        return dict(_STATUS)


def _set_status(**kwargs):
    with _STATUS_LOCK:
        _STATUS.update(kwargs)


def _get_local_ip():
    """Misma técnica que usa el módulo 'network': UDP socket sin enviar datos."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "no network"
    finally:
        s.close()


def _show_boot_screen(display, stop_event):
    display.clear()
    display.write_lines("AstronautMarkus", "Dashboard Pi")
    stop_event.wait(2)


def _show_waiting_screen(display, stop_event, ip):
    """
    Línea 1 fija ("Esperando config"), línea 2 en scroll horizontal continuo
    con la IP:puerto. Se queda acá adentro (sin reiniciar el bucle) hasta que
    cambie la configuración publicada o se pida apagar el proceso.
    """
    _set_status(state="waiting", current_module=None)
    display.clear()

    line1 = "Esperando config"
    message = f"{ip}:{WEB_PORT}".ljust(16) + "   "  # espacio de separación antes de repetir
    period = len(message)
    buffer = message * 3  # suficiente margen para que cualquier ventana de 16 caiga adentro

    version_at_start = db.get_config_version()
    offset = 0
    while not stop_event.is_set() and db.get_config_version() == version_at_start:
        start = offset % period
        display.write_lines(line1, buffer[start:start + 16])
        offset += 1
        stop_event.wait(WAITING_SCROLL_SECONDS)


def _run_entry(entry, display, stop_event, version_at_start):
    slug = entry["module_id"]
    module_logger = logging.getLogger(f"modules.{slug}")
    instance, just_created = registry.get_or_create(slug)
    if instance is None:
        module_logger.warning("Módulo '%s' no disponible, se salta.", slug)
        return

    duration = entry["duration_seconds"]
    tick_seconds = entry["tick_seconds"] or 1

    try:
        if just_created:
            ctx = ModuleContext(0.0, duration, tick_seconds, instance.cache, module_logger, display)
            instance.setup(ctx)

        elapsed = 0.0
        while elapsed < duration:
            if stop_event.is_set() or db.get_config_version() != version_at_start:
                return

            ctx = ModuleContext(elapsed, duration, tick_seconds, instance.cache, module_logger, display)
            result = instance.tick(ctx)
            if result is not None:
                display.write_lines(result[0], result[1])
            _set_status(state="running", current_module=slug)

            sleep_time = min(tick_seconds, duration - elapsed)
            stop_event.wait(sleep_time)
            elapsed += sleep_time
    except Exception as exc:
        module_logger.exception("Error en módulo '%s'", slug)
        db.mark_module_invalid(slug, str(exc))


def run_loop(stop_event):
    display = get_lcd_backend()
    display.init()
    _show_boot_screen(display, stop_event)

    scanner.discover_modules()
    ip = _get_local_ip()
    _set_status(ip=ip)

    while not stop_event.is_set():
        playlist = [e for e in db.get_active_playlist() if e["is_valid"]]

        if not playlist:
            _show_waiting_screen(display, stop_event, ip)
            continue

        version_at_start = db.get_config_version()
        for entry in playlist:
            if stop_event.is_set() or db.get_config_version() != version_at_start:
                break
            _run_entry(entry, display, stop_event, version_at_start)

    display.clear()
    display.write_lines("Shutting down...", "")
