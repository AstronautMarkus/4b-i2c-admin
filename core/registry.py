from core import scanner

_INSTANCES = {}


def get_or_create(slug):
    """
    Devuelve (instancia, just_created) para el slug dado.
    just_created=True solo la primera vez, para que el caller sepa si debe
    llamar a setup(). Devuelve (None, False) si el módulo no cargó (inválido).
    """
    instance = _INSTANCES.get(slug)
    if instance is not None:
        return instance, False

    module_cls = scanner.get_module_class(slug)
    if module_cls is None:
        return None, False

    instance = module_cls()
    _INSTANCES[slug] = instance
    return instance, True


def teardown_all(ctx_factory):
    for slug, instance in _INSTANCES.items():
        try:
            instance.teardown(ctx_factory(slug, instance))
        except Exception:
            pass
