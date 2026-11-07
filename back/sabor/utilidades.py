from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .errores import ErrorNegocio


class Reloj:
    """Reloj inyectable (permite simular el paso del tiempo en los tests)."""

    def ahora(self) -> datetime:
        return datetime.now()


def dinero(valor) -> Decimal:
    """Convierte a Decimal positivo con 2 decimales o lanza ErrorNegocio."""
    try:
        d = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        raise ErrorNegocio("El precio debe ser un número positivo")
    if not d.is_finite() or d <= 0:
        raise ErrorNegocio("El precio debe ser un número positivo")
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_fecha(texto) -> date:
    try:
        return date.fromisoformat(str(texto))
    except ValueError:
        raise ErrorNegocio("Fecha inválida, use el formato AAAA-MM-DD")


def texto_obligatorio(valor, nombre: str) -> str:
    if valor is None or not str(valor).strip():
        raise ErrorNegocio(f"El campo '{nombre}' es obligatorio")
    return str(valor).strip()
