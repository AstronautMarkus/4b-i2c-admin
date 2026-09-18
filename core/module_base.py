import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ModuleContext:
    elapsed: float          # segundos transcurridos en esta activación del slot
    duration: int            # duration_seconds configurado para esta entrada de playlist
    tick_seconds: float       # tick_seconds declarado en el manifest del módulo
    cache: dict                # persiste mientras la instancia del módulo viva
    logger: logging.Logger      # logger con nombre "modules.<slug>"
    display: object               # LCDDisplay, para módulos que necesitan escribir directo (animaciones)


class BaseModule(ABC):
    """Contrato que implementa cada módulo. Una sola instancia vive por proceso (ver core/registry.py)."""

    def __init__(self):
        self.cache = {}

    def setup(self, ctx: ModuleContext) -> None:
        """Se llama una única vez, la primera vez que el módulo se activa."""

    @abstractmethod
    def tick(self, ctx: ModuleContext):
        """
        Se llama cada `tick_seconds` mientras el módulo esté activo.
        Devuelve (linea1, linea2) de hasta 16 caracteres, o None si el módulo
        ya escribió directamente en ctx.display (p.ej. una animación).
        """

    def teardown(self, ctx: ModuleContext) -> None:
        """Se llama al apagar el proceso completo."""
