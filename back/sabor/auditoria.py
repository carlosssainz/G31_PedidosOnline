"""Registro de auditoría: cada cambio de estado del sistema queda en un log.

Formato JSON Lines (una línea JSON por evento), añadido al final del archivo:
  {"fecha_hora": "...", "actor": "admin", "accion": "PLATO_CREADO",
   "entidad": "plato", "id": "P0001", "detalle": {...}}
Si `ruta` es None los eventos solo se guardan en memoria (`self.eventos`), útil en tests.
Nunca se registran contraseñas, hashes ni tokens.
"""
from __future__ import annotations
import contextvars
import json
import sys
import threading
from pathlib import Path

from .utilidades import Reloj

# Usuario que ejecuta la petición en curso (lo fija `autenticar`; una variable por hilo/petición)
_actor = contextvars.ContextVar("actor_auditoria", default=None)


def fijar_actor(login):
    _actor.set(login)


class Auditoria:
    def __init__(self, reloj=None, ruta=None):
        self.reloj = reloj or Reloj()
        self.ruta = Path(ruta) if ruta else None
        self.eventos = []
        self._candado = threading.Lock()
        if self.ruta:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)

    def registrar(self, accion, entidad, ident, detalle=None, actor=None) -> dict:
        evento = {"fecha_hora": self.reloj.ahora().isoformat(timespec="seconds"),
                  "actor": actor or _actor.get() or "sistema",
                  "accion": accion, "entidad": entidad, "id": str(ident),
                  "detalle": detalle or {}}
        with self._candado:
            if self.ruta is None:
                self.eventos.append(evento)
            else:
                try:
                    with self.ruta.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(evento, ensure_ascii=False, default=str) + "\n")
                except OSError as e:   # no tumbar el servidor si falla el disco
                    print(f"[AUDITORIA] No se pudo escribir el log: {e}", file=sys.stderr)
        return evento
