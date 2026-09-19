from collections import defaultdict

import psutil
from flask import Blueprint, flash, redirect, render_template, request, url_for

from core import db, scanner
from core.lcd_loop import get_status

bp = Blueprint("web", __name__)


@bp.app_context_processor
def inject_nav_context():
    return {
        "nav_status": get_status(),
        # interval > 0 hace una medición propia y aislada: no interfiere con el
        # cache de interval=None que usa el módulo 'hardware' en el hilo del LCD.
        "sidebar_hw": {
            "cpu": round(psutil.cpu_percent(interval=0.05)),
            "ram": round(psutil.virtual_memory().percent),
        },
    }


@bp.get("/")
def index():
    playlist = db.get_active_playlist()
    modules = db.list_modules()

    valid_count = sum(1 for m in modules if m["is_valid"])
    invalid_count = len(modules) - valid_count

    duration_by_title = defaultdict(int)
    for entry in playlist:
        duration_by_title[entry["title"]] += entry["duration_seconds"]

    return render_template(
        "index.html",
        playlist=playlist,
        modules=modules,
        valid_count=valid_count,
        invalid_count=invalid_count,
        duration_chart=list(duration_by_title.items()),
        validity_chart=[["Válidos", valid_count], ["Inválidos", invalid_count]],
    )


@bp.get("/modules")
def modules_list():
    return render_template("modules.html", modules=db.list_modules())


@bp.post("/modules/rescan")
def modules_rescan():
    scanner.discover_modules()
    flash("Escaneo completado.", "success")
    return redirect(url_for("web.modules_list"))


@bp.get("/playlist")
def playlist_editor():
    return render_template(
        "playlist.html",
        modules=db.list_modules(),
        playlist=db.get_active_playlist(),
    )


@bp.post("/playlist")
def playlist_publish():
    valid_ids = {m["id"] for m in db.list_modules() if m["is_valid"]}
    module_ids = request.form.getlist("module_id")
    durations = request.form.getlist("duration_seconds")

    entries = []
    for module_id, duration in zip(module_ids, durations):
        if module_id not in valid_ids:
            continue
        try:
            duration_seconds = max(1, int(duration))
        except (TypeError, ValueError):
            continue
        entries.append((module_id, duration_seconds))

    if not entries:
        flash("La playlist debe tener al menos una entrada válida.", "error")
        return redirect(url_for("web.playlist_editor"))

    db.replace_playlist(entries)
    flash(f"Playlist publicada con {len(entries)} entradas.", "success")
    return redirect(url_for("web.playlist_editor"))


@bp.post("/reset")
def factory_reset():
    db.factory_reset()
    flash("Se restauró la configuración de fábrica: el sistema queda esperando configuración.", "success")
    return redirect(url_for("web.index"))
