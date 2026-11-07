"""API REST JSON sobre http.server (librería estándar)."""
from __future__ import annotations
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .auditoria import fijar_actor
from .errores import ErrorNegocio

# Cada handler recibe: (sistema, token, ruta, query, body)
def _u(s, t, *roles):
    return s.usuarios.autenticar(t, *roles)

def _alta_plato(s, t, b):
    """El chef puede dar de alta platos en el almacén, pero solo el admin puede meterlos en la carta."""
    en_carta = bool(b.get("en_carta"))
    _u(s, t, "administrador") if en_carta else _u(s, t, "administrador", "chef")
    return s.carta.alta_plato(b.get("nombre"), b.get("descripcion"), b.get("precio"),
                              b.get("categoria"), en_carta)


RUTAS = [
    # --- HU-01..03: cuentas ---
    ("POST", r"/registro", lambda s, t, r, q, b: s.usuarios.registrar_cliente(
        b.get("nombre"), b.get("direccion"), b.get("correo"), b.get("login"), b.get("password"))),
    ("GET", r"/activar", lambda s, t, r, q, b: s.usuarios.activar_cuenta(q.get("token"))),
    ("POST", r"/login", lambda s, t, r, q, b: s.usuarios.login(b.get("login"), b.get("password"))),
    # --- HU-04, HU-05: consulta pública ---
    ("GET", r"/carta", lambda s, t, r, q, b: s.carta.consultar(q.get("categoria"))),
    ("GET", r"/menu", lambda s, t, r, q, b: s.menu.consultar_menu(q.get("fecha"))),
    # --- HU-06..08: almacén de platos y carta ---
    # Ver el almacén y dar de alta platos (sin carta): administrador o chef
    ("GET", r"/almacen/platos", lambda s, t, r, q, b: (_u(s, t, "administrador", "chef"), s.carta.listado_gestion())[1]),
    ("POST", r"/almacen/platos", lambda s, t, r, q, b: _alta_plato(s, t, b)),
    # Todo lo que afecta a la carta: SOLO administrador
    ("PUT", r"/almacen/platos/(?P<codigo>[^/]+)", lambda s, t, r, q, b: (_u(s, t, "administrador"),
        s.carta.modificar_plato(r["codigo"], b))[1]),
    ("DELETE", r"/almacen/platos/(?P<codigo>[^/]+)", lambda s, t, r, q, b: (_u(s, t, "administrador"),
        s.carta.baja_plato(r["codigo"], str(q.get("confirmar", "")).lower() == "true"))[1]),
    ("POST", r"/carta/(?P<codigo>[^/]+)", lambda s, t, r, q, b: (_u(s, t, "administrador"), s.carta.anadir_a_carta(r["codigo"]))[1]),
    ("DELETE", r"/carta/(?P<codigo>[^/]+)", lambda s, t, r, q, b: (_u(s, t, "administrador"), s.carta.quitar_de_carta(r["codigo"]))[1]),
    # --- HU-09: menú diario (chef) ---
    ("GET", r"/chef/platos", lambda s, t, r, q, b: (_u(s, t, "chef"), s.menu.platos_para_slot(q.get("tipo")))[1]),
    ("POST", r"/chef/menu", lambda s, t, r, q, b: (_u(s, t, "chef"), s.menu.configurar_menu(
        b.get("fecha"), b.get("entrantes"), b.get("principales"), b.get("postres"), b.get("bebida")))[1]),
    ("DELETE", r"/chef/menu", lambda s, t, r, q, b: (_u(s, t, "chef"), s.menu.quitar_menu(q.get("fecha")))[1]),
    # --- HU-10, HU-11: pedidos (cliente) ---
    ("POST", r"/pedidos/resumen", lambda s, t, r, q, b: (_u(s, t, "cliente"), s.pedidos.resumen(b.get("items")))[1]),
    ("POST", r"/pedidos", lambda s, t, r, q, b: s.pedidos.confirmar(_u(s, t, "cliente"), b.get("items"), b.get("direccion"))),
    ("GET", r"/pedidos", lambda s, t, r, q, b: s.pedidos.mis_pedidos(_u(s, t, "cliente"))),
    # --- HU-14: personal ---
    ("GET", r"/personal/pedidos", lambda s, t, r, q, b: (_u(s, t, "personal"), s.pedidos.pedidos_entrantes())[1]),
    ("PUT", r"/personal/pedidos/(?P<codigo>[^/]+)/estado", lambda s, t, r, q, b: (_u(s, t, "personal"),
        s.pedidos.actualizar_estado(r["codigo"], b.get("estado")))[1]),
]
RUTAS = [(m, re.compile(p), f) for m, p, f in RUTAS]


def crear_servidor(sistema, host="127.0.0.1", puerto=8000) -> ThreadingHTTPServer:
    candado = threading.Lock()   # el almacén en memoria no es thread-safe

    class Manejador(BaseHTTPRequestHandler):
        def _responder(self, estado, cuerpo):
            data = json.dumps(cuerpo, ensure_ascii=False).encode()
            self.send_response(estado)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.end_headers()
            self.wfile.write(data)

        def _atender(self, metodo):
            url = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self._responder(400, {"ok": False, "error": "JSON inválido"})
            auth = self.headers.get("Authorization", "")
            token = auth[7:] if auth.startswith("Bearer ") else None
            fijar_actor(None)   # cada petición empieza sin actor
            try:
                for m, patron, fn in RUTAS:
                    r = patron.fullmatch(url.path)
                    if m == metodo and r:
                        with candado:
                            datos = fn(sistema, token, r.groupdict(), query, body)
                        return self._responder(200, {"ok": True, "datos": datos})
                self._responder(404, {"ok": False, "error": "Ruta no encontrada"})
            except ErrorNegocio as e:
                self._responder(e.estado, {"ok": False, "error": e.mensaje})
            except Exception:  # pragma: no cover
                self._responder(500, {"ok": False, "error": "Error interno"})

        def do_GET(self): self._atender("GET")
        def do_POST(self): self._atender("POST")
        def do_PUT(self): self._atender("PUT")
        def do_DELETE(self): self._atender("DELETE")
        def do_OPTIONS(self): self._responder(204, {})
        def log_message(self, *a): pass

    return ThreadingHTTPServer((host, puerto), Manejador)
