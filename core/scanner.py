import importlib.util
import json
import logging

from core import db
from core.config import MODULES_DIR
from core.module_base import BaseModule

logger = logging.getLogger("scanner")

REQUIRED_MANIFEST_KEYS = {"title", "tick_seconds"}

# slug -> clase Module ya importada y validada
_MODULE_CLASSES = {}


def validate_manifest(data):
    missing = REQUIRED_MANIFEST_KEYS - data.keys()
    if missing:
        raise ValueError(f"faltan claves en manifest.json: {sorted(missing)}")
    if not isinstance(data["title"], str) or not data["title"].strip():
        raise ValueError("'title' debe ser un string no vacío")
    if not isinstance(data["tick_seconds"], (int, float)) or data["tick_seconds"] <= 0:
        raise ValueError("'tick_seconds' debe ser un número > 0")


def _load_manifest(slug_dir):
    manifest_path = slug_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("falta manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    validate_manifest(data)
    return data


def _load_module_class(slug, slug_dir):
    module_path = slug_dir / "module.py"
    if not module_path.exists():
        raise FileNotFoundError("falta module.py")

    spec = importlib.util.spec_from_file_location(f"modules.{slug}.module", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module_cls = getattr(module, "Module", None)
    if module_cls is None:
        raise AttributeError("module.py no define la clase 'Module'")
    if not (isinstance(module_cls, type) and issubclass(module_cls, BaseModule)):
        raise TypeError("'Module' debe heredar de core.module_base.BaseModule")

    module_cls()  # fuerza validación de abstractmethods (ej. tick() sin implementar)
    return module_cls


def discover_modules(modules_dir=None):
    """Escanea modules_dir, valida cada módulo y actualiza la tabla `modules`."""
    modules_dir = modules_dir or MODULES_DIR
    found_slugs = set()

    if not modules_dir.exists():
        logger.warning("El directorio de módulos no existe: %s", modules_dir)
        return

    for slug_dir in sorted(p for p in modules_dir.iterdir() if p.is_dir()):
        slug = slug_dir.name
        found_slugs.add(slug)

        try:
            manifest = _load_manifest(slug_dir)
            module_cls = _load_module_class(slug, slug_dir)
        except Exception as exc:
            logger.error("Módulo inválido '%s': %s", slug, exc)
            db.upsert_module(slug, {"title": slug}, is_valid=False, error_message=str(exc))
            _MODULE_CLASSES.pop(slug, None)
            continue

        db.upsert_module(slug, manifest, is_valid=True, error_message=None)
        _MODULE_CLASSES[slug] = module_cls

    db.mark_missing_as_invalid(found_slugs)


def get_module_class(slug):
    return _MODULE_CLASSES.get(slug)
