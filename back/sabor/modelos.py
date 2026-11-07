from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from . import config as C


@dataclass
class Usuario:
    login: str
    nombre: str
    direccion: str
    correo: str
    salt: str
    password_hash: str
    rol: str = "cliente"
    estado: str = C.CUENTA_PENDIENTE
    token_activacion: Optional[str] = None
    token_expira: Optional[datetime] = None

    def publico(self) -> dict:
        return {"login": self.login, "nombre": self.nombre, "direccion": self.direccion,
                "correo": self.correo, "rol": self.rol, "estado": self.estado}


@dataclass
class Plato:
    codigo: str
    nombre: str
    descripcion: str
    precio: Decimal
    categoria: str
    estado: str = C.PLATO_ACTIVO

    def to_dict(self) -> dict:
        return {"codigo": self.codigo, "nombre": self.nombre, "descripcion": self.descripcion,
                "precio": float(self.precio), "categoria": self.categoria,
                "estado": self.estado}


@dataclass
class MenuDiario:
    fecha: date
    precio: Decimal
    entrantes: list          # códigos de plato
    principales: list
    postres: list
    bebida: str = "Bebida incluida"


@dataclass
class LineaPedido:
    tipo: str                # "plato" | "menu"
    referencia: str          # código de plato o fecha del menú
    descripcion: str
    opciones: dict
    cantidad: int
    precio_unitario: Decimal

    @property
    def subtotal(self) -> Decimal:
        return self.precio_unitario * self.cantidad

    def to_dict(self) -> dict:
        return {"tipo": self.tipo, "referencia": self.referencia,
                "descripcion": self.descripcion, "opciones": self.opciones,
                "cantidad": self.cantidad, "precio_unitario": float(self.precio_unitario),
                "subtotal": float(self.subtotal)}


@dataclass
class Pedido:
    codigo: str
    fecha_hora: datetime
    cliente: str
    direccion: str
    lineas: list
    total: Decimal
    estado: str
    hora_limite: datetime
    fecha_estado: datetime

    def tiempo_restante(self, ahora: datetime) -> int:
        """Segundos que quedan para modificar/cancelar (0 si ya no se puede)."""
        if self.estado != C.RECIBIDO:
            return 0
        return max(0, int((self.hora_limite - ahora).total_seconds()))

    def to_dict(self, ahora: datetime) -> dict:
        t = self.tiempo_restante(ahora)
        return {"codigo": self.codigo, "fecha_hora": self.fecha_hora.isoformat(timespec="seconds"),
                "cliente": self.cliente, "direccion": self.direccion,
                "lineas": [l.to_dict() for l in self.lineas], "total": float(self.total),
                "estado": self.estado, "tiempo_restante_segundos": t, "modificable": t > 0,
                "hora_limite": self.hora_limite.isoformat(timespec="seconds"),
                "fecha_estado": self.fecha_estado.isoformat(timespec="seconds")}
