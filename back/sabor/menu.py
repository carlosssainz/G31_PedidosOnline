"""HU-05 Consulta del menú diario, HU-09 Configuración por el chef.

El chef puede usar CUALQUIER plato activo del almacén (esté o no en la carta)
o crear platos nuevos, que entran en el almacén para reutilizarlos después.
"""
from __future__ import annotations
from decimal import Decimal

from . import config as C
from .auditoria import Auditoria
from .errores import ErrorNegocio
from .modelos import MenuDiario, Plato
from .utilidades import dinero, parse_fecha, texto_obligatorio

SLOTS = {"entrante": 3, "principal": 3, "postre": 2}
NOMBRES_PLURAL = {"entrante": "entrantes", "principal": "principales", "postre": "postres"}


def categoria_valida_para(slot: str, categoria: str) -> bool:
    if slot == "entrante":
        return categoria in ("entrante", "ensalada")
    if slot == "postre":
        return categoria == "postre"
    return categoria not in C.CATEGORIAS_NO_PRINCIPAL      # principal


class ServicioMenu:
    def __init__(self, almacen, carta, reloj, auditoria=None):
        self.a = almacen
        self.carta = carta
        self.reloj = reloj
        self.log = auditoria or Auditoria(reloj)

    # EQ Desplegable Platos (P11): platos del almacén aptos para cada hueco
    def platos_para_slot(self, slot) -> list:
        if slot not in SLOTS:
            raise ErrorNegocio("Tipo de plato inválido (entrante / principal / postre)")
        return [{"codigo": p.codigo, "nombre": p.nombre, "categoria": p.categoria,
                 "en_carta": p.codigo in self.a.carta}
                for p in sorted(self.a.platos.values(), key=lambda x: x.nombre.lower())
                if p.estado == C.PLATO_ACTIVO and categoria_valida_para(slot, p.categoria)]

    # HU-09
    def configurar_menu(self, fecha, entrantes, principales, postres, bebida=None) -> dict:
        f = parse_fecha(fecha)
        if f < self.reloj.ahora().date():
            raise ErrorNegocio("No se puede configurar el menú de una fecha pasada")
        listas = {"entrante": entrantes, "principal": principales, "postre": postres}

        # 1) validar TODO antes de crear nada (operación atómica)
        resueltos, nuevos = {}, set()
        for slot, cantidad in SLOTS.items():
            lista = listas[slot]
            if not isinstance(lista, list) or len(lista) != cantidad:
                raise ErrorNegocio(f"Debe definir exactamente {cantidad} "
                                   f"{NOMBRES_PLURAL[slot]}")
            vistos, items = set(), []
            for ref in lista:
                if not isinstance(ref, dict):
                    raise ErrorNegocio("Cada opción debe indicar 'codigo' o 'nuevo'")
                if "codigo" in ref:
                    p = self.carta.obtener(ref["codigo"])
                    if p.estado != C.PLATO_ACTIVO:
                        raise ErrorNegocio(f"El plato '{p.nombre}' está retirado")
                    if not categoria_valida_para(slot, p.categoria):
                        raise ErrorNegocio(f"'{p.nombre}' ({p.categoria}) no es válido "
                                           f"como {slot}")
                    clave = ("c", p.codigo)
                    items.append(("existente", p))
                elif "nuevo" in ref:
                    d = ref["nuevo"] or {}
                    nombre = texto_obligatorio(d.get("nombre"), "nombre del plato nuevo")
                    desc = texto_obligatorio(d.get("descripcion"), "descripción del plato nuevo")
                    cat = d.get("categoria")
                    if cat not in C.CATEGORIAS or not categoria_valida_para(slot, cat):
                        raise ErrorNegocio(f"La categoría del plato nuevo '{nombre}' no es "
                                           f"válida como {slot}")
                    precio = dinero(d["precio"]) if d.get("precio") not in (None, "") \
                        else Decimal("0.00")
                    if self.carta.existe_nombre(nombre, cat) or (nombre.lower(), cat) in nuevos:
                        raise ErrorNegocio(f"Ya existe '{nombre}'; selecciónelo por su código", 409)
                    nuevos.add((nombre.lower(), cat))
                    clave = ("n", nombre.lower())
                    items.append(("nuevo", (nombre, desc, precio, cat)))
                else:
                    raise ErrorNegocio("Cada opción debe indicar 'codigo' o 'nuevo'")
                if clave in vistos:
                    raise ErrorNegocio(f"Hay {NOMBRES_PLURAL[slot]} repetidos")
                vistos.add(clave)
            resueltos[slot] = items

        # 2) los platos nuevos entran en el almacén (NO en la carta); se guarda el menú
        codigos = {}
        for slot, items in resueltos.items():
            codigos[slot] = []
            for tipo, dato in items:
                if tipo == "existente":
                    codigos[slot].append(dato.codigo)
                else:
                    nombre, desc, precio, cat = dato
                    p = Plato(self.a.nuevo_codigo_plato(), nombre, desc, precio, cat)
                    self.a.platos[p.codigo] = p
                    codigos[slot].append(p.codigo)
                    self.log.registrar("PLATO_CREADO", "plato", p.codigo,
                                       {"nombre": nombre, "categoria": cat, "precio": float(precio),
                                        "en_carta": False, "origen": f"menu {f.isoformat()}"})
        menu = MenuDiario(f, C.PRECIO_MENU, codigos["entrante"], codigos["principal"],
                          codigos["postre"], (bebida or "Bebida incluida").strip())
        reemplaza = f in self.a.menus
        self.a.menus[f] = menu
        self.log.registrar("MENU_CONFIGURADO", "menu", f.isoformat(),
                           {"reemplaza_anterior": reemplaza, "entrantes": menu.entrantes,
                            "principales": menu.principales, "postres": menu.postres,
                            "bebida": menu.bebida})
        return self._a_dict(menu)

    # HU-05
    def consultar_menu(self, fecha=None) -> dict:
        f = parse_fecha(fecha) if fecha else self.reloj.ahora().date()
        menu = self.a.menus.get(f)
        if menu is None:
            return {"fecha": f.isoformat(), "disponible": False,
                    "mensaje": "El menú diario no está disponible para este día"}
        return self._a_dict(menu)

    def quitar_menu(self, fecha) -> dict:
        f = parse_fecha(fecha)
        menu = self.a.menus.pop(f, None)
        if menu is None:
            raise ErrorNegocio("No hay menú configurado para esa fecha", 404)
        self.log.registrar("MENU_RETIRADO", "menu", f.isoformat(),
                           {"entrantes": menu.entrantes, "principales": menu.principales,
                            "postres": menu.postres})
        return {"mensaje": f"Menú del {f.isoformat()} retirado"}

    def _a_dict(self, m: MenuDiario) -> dict:
        def ver(codigos):
            return [{"codigo": c, "nombre": self.a.platos[c].nombre,
                     "descripcion": self.a.platos[c].descripcion} for c in codigos]
        return {"fecha": m.fecha.isoformat(), "disponible": True, "precio": float(m.precio),
                "entrantes": ver(m.entrantes), "principales": ver(m.principales),
                "postres": ver(m.postres), "bebida": m.bebida}
