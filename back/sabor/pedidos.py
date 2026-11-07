"""HU-10 Confección/confirmación, HU-11 Consulta de estado, HU-14 Actualización."""
from __future__ import annotations
from datetime import timedelta
from decimal import Decimal

from . import config as C
from .auditoria import Auditoria
from .errores import ErrorNegocio
from .modelos import LineaPedido, Pedido
from .utilidades import parse_fecha, texto_obligatorio


class ServicioPedidos:
    def __init__(self, almacen, reloj, auditoria=None):
        self.a = almacen
        self.reloj = reloj
        self.log = auditoria or Auditoria(reloj)

    # ---- construcción de líneas (compartida por resumen y confirmación) ----
    def _lineas(self, items) -> list:
        if not isinstance(items, list) or not items:
            raise ErrorNegocio("El pedido debe contener al menos un producto")
        lineas = []
        for it in items:
            if not isinstance(it, dict):
                raise ErrorNegocio("Producto del pedido inválido")
            try:
                cantidad = int(it.get("cantidad", 1))
            except (TypeError, ValueError):
                raise ErrorNegocio("La cantidad debe ser un número entero")
            if cantidad <= 0:
                raise ErrorNegocio("La cantidad debe ser mayor que cero")
            tipo = it.get("tipo")
            if tipo == "plato":
                lineas.append(self._linea_plato(it, cantidad))
            elif tipo == "menu":
                lineas.append(self._linea_menu(it, cantidad))
            else:
                raise ErrorNegocio("El tipo de producto debe ser 'plato' o 'menu'")
        return lineas

    def _linea_plato(self, it, cantidad) -> LineaPedido:
        p = self.a.platos.get(it.get("id"))
        if p is None or p.estado != C.PLATO_ACTIVO or p.codigo not in self.a.carta:
            raise ErrorNegocio(f"El plato '{it.get('id')}' no está disponible en la carta")
        return LineaPedido("plato", p.codigo, p.nombre, {}, cantidad, p.precio)

    def _linea_menu(self, it, cantidad) -> LineaPedido:
        f = parse_fecha(it.get("fecha"))
        menu = self.a.menus.get(f)
        if menu is None:
            raise ErrorNegocio("El menú diario no está disponible para este día", 409)
        if f < self.reloj.ahora().date():
            raise ErrorNegocio("No se puede pedir el menú de una fecha pasada")
        ops = it.get("opciones") or {}
        elegidas = {}
        for slot, validos in (("entrante", menu.entrantes), ("principal", menu.principales),
                              ("postre", menu.postres)):
            codigo = ops.get(slot)
            if codigo not in validos:
                raise ErrorNegocio(f"Debe elegir un {slot} válido del menú del día")
            elegidas[slot] = self.a.platos[codigo].nombre
        return LineaPedido("menu", f.isoformat(), f"Menú diario {f.isoformat()}", elegidas,
                           cantidad, menu.precio)

    @staticmethod
    def _total(lineas) -> Decimal:
        return sum((l.subtotal for l in lineas), Decimal("0.00"))

    # EO Resumen del Pedido (antes de confirmar)
    def resumen(self, items) -> dict:
        lineas = self._lineas(items)
        return {"lineas": [l.to_dict() for l in lineas], "importe_total": float(self._total(lineas))}

    # HU-10
    def confirmar(self, usuario, items, direccion=None) -> dict:
        lineas = self._lineas(items)
        direccion = texto_obligatorio(direccion or usuario.direccion, "dirección de entrega")
        ahora = self.reloj.ahora()
        pedido = Pedido(self.a.nuevo_codigo_pedido(), ahora, usuario.login, direccion, lineas,
                        self._total(lineas), C.RECIBIDO,
                        ahora + timedelta(minutes=C.MINUTOS_MODIFICACION), ahora)
        self.a.pedidos[pedido.codigo] = pedido
        self.log.registrar("PEDIDO_CONFIRMADO", "pedido", pedido.codigo,
                           {"cliente": usuario.login, "direccion": direccion,
                            "total": float(pedido.total),
                            "lineas": [l.to_dict() for l in lineas]}, actor=usuario.login)
        return pedido.to_dict(ahora)

    # HU-11
    def mis_pedidos(self, usuario) -> list:
        ahora = self.reloj.ahora()
        propios = [p for p in self.a.pedidos.values() if p.cliente == usuario.login]
        return [p.to_dict(ahora) for p in sorted(propios, key=lambda x: x.fecha_hora, reverse=True)]

    # EQ Pedidos Entrantes (HU-14)
    def pedidos_entrantes(self) -> list:
        activos = [p for p in self.a.pedidos.values()
                   if p.estado in (C.RECIBIDO, C.EN_PREPARACION)]
        return [{"codigo": p.codigo, "hora": p.fecha_hora.isoformat(timespec="seconds"),
                 "direccion": p.direccion,
                 "productos": [f"{l.cantidad} x {l.descripcion}" for l in p.lineas],
                 "estado": p.estado}
                for p in sorted(activos, key=lambda x: x.fecha_hora)]

    # HU-14
    def actualizar_estado(self, codigo, nuevo_estado) -> dict:
        p = self.a.pedidos.get(codigo)
        if p is None:
            raise ErrorNegocio("El pedido no existe", 404)
        if p.estado == C.CANCELADO:
            raise ErrorNegocio("El pedido está cancelado y no puede actualizarse", 409)
        if C.SIGUIENTE_ESTADO.get(p.estado) != nuevo_estado:
            raise ErrorNegocio(f"Transición no permitida: {p.estado} → {nuevo_estado}", 409)
        ahora = self.reloj.ahora()
        anterior = p.estado
        p.estado, p.fecha_estado = nuevo_estado, ahora
        self.log.registrar("PEDIDO_ESTADO_CAMBIADO", "pedido", codigo,
                           {"anterior": anterior, "nuevo": nuevo_estado})
        return p.to_dict(ahora)
