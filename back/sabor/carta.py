"""Almacén de platos + carta.

Un plato se da de alta en el ALMACÉN (sin temporada). Después se puede
meter o sacar de la CARTA tantas veces como se quiera, y/o usar en el MENÚ DIARIO.
HU-04 consulta de la carta · HU-06/07/08 gestión de platos.
"""
from __future__ import annotations

from . import config as C
from .auditoria import Auditoria
from .errores import ErrorNegocio
from .modelos import Plato
from .utilidades import dinero, texto_obligatorio


class ServicioCarta:
    def __init__(self, almacen, auditoria=None):
        self.a = almacen
        self.log = auditoria or Auditoria()

    # ---------- auxiliares ----------
    def existe_nombre(self, nombre, categoria, excluir=None) -> bool:
        return any(p.codigo != excluir and p.categoria == categoria
                   and p.nombre.lower() == nombre.lower() for p in self.a.platos.values())

    def _validar_categoria(self, categoria):
        if categoria not in C.CATEGORIAS:
            raise ErrorNegocio(f"Categoría inválida. Valores: {', '.join(C.CATEGORIAS)}")

    def obtener(self, codigo) -> Plato:
        p = self.a.platos.get(codigo)
        if p is None:
            raise ErrorNegocio("El plato no existe", 404)
        return p

    def ver(self, p: Plato) -> dict:
        d = p.to_dict()
        d["en_carta"] = p.codigo in self.a.carta
        return d

    # ---------- HU-04: consulta pública de la carta ----------
    def consultar(self, categoria=None) -> dict:
        if categoria:
            self._validar_categoria(categoria)
        carta = {}
        for p in sorted(self.a.platos.values(), key=lambda x: x.nombre.lower()):
            if (p.codigo in self.a.carta and p.estado == C.PLATO_ACTIVO
                    and (not categoria or p.categoria == categoria)):
                carta.setdefault(p.categoria, []).append(
                    {"codigo": p.codigo, "nombre": p.nombre,
                     "descripcion": p.descripcion, "precio": float(p.precio)})
        return {"carta": carta}

    # ---------- HU-06: alta en el almacén ----------
    def alta_plato(self, nombre, descripcion, precio, categoria, en_carta=False) -> dict:
        nombre = texto_obligatorio(nombre, "nombre")
        descripcion = texto_obligatorio(descripcion, "descripción")
        precio = dinero(precio)
        self._validar_categoria(categoria)
        if self.existe_nombre(nombre, categoria):
            raise ErrorNegocio("Ya existe un plato con ese nombre en la categoría", 409)
        p = Plato(self.a.nuevo_codigo_plato(), nombre, descripcion, precio, categoria)
        self.a.platos[p.codigo] = p
        if en_carta:
            self.a.carta.add(p.codigo)
        self.log.registrar("PLATO_CREADO", "plato", p.codigo,
                           {"nombre": nombre, "categoria": categoria, "precio": float(precio),
                            "en_carta": bool(en_carta)})
        return self.ver(p)

    # ---------- HU-07 ----------
    def modificar_plato(self, codigo, cambios: dict) -> dict:
        p = self.obtener(codigo)
        antes, estaba_en_carta = p.to_dict(), codigo in self.a.carta
        nombre = texto_obligatorio(cambios.get("nombre", p.nombre), "nombre")
        descripcion = texto_obligatorio(cambios.get("descripcion", p.descripcion), "descripción")
        precio = dinero(cambios["precio"]) if "precio" in cambios else p.precio
        categoria = cambios.get("categoria", p.categoria)
        estado = cambios.get("estado", p.estado)
        self._validar_categoria(categoria)
        if estado not in (C.PLATO_ACTIVO, C.PLATO_RETIRADO):
            raise ErrorNegocio("Estado inválido (Activo / Retirado)")
        if self.existe_nombre(nombre, categoria, excluir=codigo):
            raise ErrorNegocio("Ya existe un plato con ese nombre en la categoría", 409)
        p.nombre, p.descripcion, p.precio = nombre, descripcion, precio
        p.categoria, p.estado = categoria, estado
        if estado == C.PLATO_RETIRADO:
            self.a.carta.discard(codigo)
        despues = p.to_dict()
        diff = {k: {"antes": antes[k], "despues": despues[k]}
                for k in despues if antes[k] != despues[k]}
        if diff or (estaba_en_carta and codigo not in self.a.carta):
            if estaba_en_carta and codigo not in self.a.carta:
                diff["en_carta"] = {"antes": True, "despues": False}
            self.log.registrar("PLATO_MODIFICADO", "plato", codigo, {"cambios": diff})
        return self.ver(p)

    # ---------- HU-08: baja (se conserva en el histórico) ----------
    def baja_plato(self, codigo, confirmar=False) -> dict:
        p = self.obtener(codigo)
        if not confirmar:
            raise ErrorNegocio("Debe confirmar la baja del plato")
        estaba_en_carta = codigo in self.a.carta
        p.estado = C.PLATO_RETIRADO
        self.a.carta.discard(codigo)
        self.log.registrar("PLATO_DADO_DE_BAJA", "plato", codigo,
                           {"nombre": p.nombre, "estaba_en_carta": estaba_en_carta})
        return self.ver(p)

    # ---------- meter / sacar de la carta ----------
    def anadir_a_carta(self, codigo) -> dict:
        p = self.obtener(codigo)
        if p.estado != C.PLATO_ACTIVO:
            raise ErrorNegocio("Un plato retirado no puede entrar en la carta")
        if p.precio <= 0:
            raise ErrorNegocio("Asigne un precio al plato antes de meterlo en la carta")
        if codigo not in self.a.carta:
            self.a.carta.add(codigo)
            self.log.registrar("CARTA_PLATO_ANADIDO", "plato", codigo, {"nombre": p.nombre})
        return self.ver(p)

    def quitar_de_carta(self, codigo) -> dict:
        p = self.obtener(codigo)
        if codigo in self.a.carta:
            self.a.carta.discard(codigo)
            self.log.registrar("CARTA_PLATO_QUITADO", "plato", codigo, {"nombre": p.nombre})
        return self.ver(p)

    # ---------- listado de gestión: todo el almacén ----------
    def listado_gestion(self) -> list:
        return [self.ver(p) for p in sorted(self.a.platos.values(), key=lambda x: x.codigo)]
