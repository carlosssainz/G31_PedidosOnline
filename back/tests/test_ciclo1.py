import sys, os, json, tempfile, unittest
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sabor.sistema import Sistema
from sabor.datos_iniciales import cargar
from sabor.errores import ErrorNegocio
from sabor.auditoria import fijar_actor


class RelojFalso:
    def __init__(self): self.t = datetime(2026, 11, 7, 13, 0)
    def ahora(self): return self.t
    def avanzar(self, **kw): self.t += timedelta(**kw)


class TestCiclo1(unittest.TestCase):
    def setUp(self):
        fijar_actor(None)    # el actor es por hilo: no arrastrar el de otro test
        self.reloj = RelojFalso()
        self.s = Sistema(self.reloj)
        cargar(self.s)

    def cliente(self, login="ana"):
        s = self.s
        s.usuarios.registrar_cliente("Ana Pérez", "C/ Mayor 1", f"{login}@mail.com", login, "secreto1")
        token = s.almacen.bandeja_correos[-1]["enlace"].split("=")[1]
        s.usuarios.activar_cuenta(token)
        return s.usuarios.autenticar(s.usuarios.login(login, "secreto1")["token"])

    # HU-01/02/03
    def test_registro_activacion_login(self):
        s = self.s
        with self.assertRaises(ErrorNegocio): s.usuarios.registrar_cliente("", "d", "a@b.com", "x", "123456")
        with self.assertRaises(ErrorNegocio): s.usuarios.registrar_cliente("n", "d", "malcorreo", "x", "123456")
        s.usuarios.registrar_cliente("Ana", "d", "ana@mail.com", "ana", "secreto1")
        with self.assertRaises(ErrorNegocio) as e: s.usuarios.registrar_cliente("A", "d", "o@mail.com", "ana", "secreto1")
        self.assertEqual(e.exception.estado, 409)
        self.assertEqual(len(s.almacen.bandeja_correos), 1)
        with self.assertRaises(ErrorNegocio) as e: s.usuarios.login("ana", "secreto1")
        self.assertEqual(e.exception.estado, 403)
        with self.assertRaises(ErrorNegocio) as e: s.usuarios.login("ana", "mal")
        self.assertEqual(e.exception.estado, 401)
        with self.assertRaises(ErrorNegocio): s.usuarios.activar_cuenta("token-falso")
        s.usuarios.activar_cuenta(s.almacen.bandeja_correos[0]["enlace"].split("=")[1])
        self.assertEqual(s.usuarios.login("ana", "secreto1")["rol"], "cliente")

    def test_token_expirado(self):
        s = self.s
        s.usuarios.registrar_cliente("Ana", "d", "ana@mail.com", "ana", "secreto1")
        self.reloj.avanzar(hours=25)
        with self.assertRaises(ErrorNegocio):
            s.usuarios.activar_cuenta(s.almacen.bandeja_correos[0]["enlace"].split("=")[1])

    # HU-04/06/07/08: almacén y carta
    def test_almacen_y_carta(self):
        s = self.s
        nombres = lambda: [p["nombre"] for p in s.carta.consultar()["carta"].get("entrante", [])]
        self.assertNotIn("Chatamari", nombres())            # está en el almacén, no en la carta
        cod = {p.nombre: p.codigo for p in s.almacen.platos.values()}
        s.carta.anadir_a_carta(cod["Chatamari"])
        self.assertIn("Chatamari", nombres())
        s.carta.quitar_de_carta(cod["Chatamari"])           # fuera de carta a voluntad
        self.assertNotIn("Chatamari", nombres())
        self.assertIn(cod["Chatamari"], s.almacen.platos)   # sigue en el almacén
        p = s.carta.alta_plato("Momo", "Dumplings al vapor", "6.5", "entrante")
        self.assertFalse(p["en_carta"]); self.assertNotIn("temporada", p)
        with self.assertRaises(ErrorNegocio): s.carta.alta_plato("momo", "x", 5, "entrante")
        with self.assertRaises(ErrorNegocio): s.carta.alta_plato("Raro", "x", -3, "entrante")
        m = s.carta.modificar_plato(p["codigo"], {"precio": 7})
        self.assertEqual((m["codigo"], m["precio"]), (p["codigo"], 7.0))
        s.carta.anadir_a_carta(p["codigo"])
        with self.assertRaises(ErrorNegocio): s.carta.baja_plato(p["codigo"])   # sin confirmar
        s.carta.baja_plato(p["codigo"], True)               # baja: sale de la carta
        self.assertNotIn("Momo", nombres())
        with self.assertRaises(ErrorNegocio): s.carta.anadir_a_carta(p["codigo"])
        self.assertIn(p["codigo"], s.almacen.platos)        # histórico conservado

    # HU-05/09
    def test_menu_diario(self):
        s = self.s
        hoy = self.reloj.ahora().date().isoformat()
        self.assertFalse(s.menu.consultar_menu(hoy)["disponible"])
        cod = {p.nombre: p.codigo for p in s.almacen.platos.values()}
        ent = [{"codigo": cod["Samosa"]}, {"codigo": cod["Pakora"]},
               {"nuevo": {"nombre": "Momo", "descripcion": "Dumplings", "categoria": "entrante"}}]
        pri = [{"codigo": cod["Pollo Tandoori"]}, {"codigo": cod["Dal Bhat"]}, {"codigo": cod["Curry de Verduras"]}]
        pos = [{"codigo": cod["Kheer"]}, {"codigo": cod["Gulab Jamun"]}]
        with self.assertRaises(ErrorNegocio): s.menu.configurar_menu(hoy, ent[:2], pri, pos)
        with self.assertRaises(ErrorNegocio): s.menu.configurar_menu(hoy, ent, [{"codigo": cod["Samosa"]}] + pri[:2], pos)
        self.assertNotIn("Momo", [p.nombre for p in s.almacen.platos.values()])  # atómico
        m = s.menu.configurar_menu(hoy, ent, pri, pos)
        self.assertEqual(m["precio"], 15.0)
        self.assertEqual(len(m["entrantes"]), 3)
        momo = [p for p in s.almacen.platos.values() if p.nombre == "Momo"][0]
        self.assertNotIn(momo.codigo, s.almacen.carta)      # entra en el almacén, no en la carta
        # el chef también puede usar platos del almacén que no están en la carta
        self.assertIn("Chatamari", [p["nombre"] for p in s.menu.platos_para_slot("entrante")])
        self.assertIn("Momo", [p["nombre"] for p in s.menu.platos_para_slot("entrante")])
        self.assertTrue(s.menu.consultar_menu(hoy)["disponible"])
        self.assertNotIn("Momo", str(s.carta.consultar()))   # no aparece en la carta pública
        with self.assertRaises(ErrorNegocio): s.carta.anadir_a_carta(momo.codigo)  # sin precio aún
        s.carta.modificar_plato(momo.codigo, {"precio": 6})
        s.carta.anadir_a_carta(momo.codigo)                  # ahora sí puede pasar a la carta
        self.assertIn("Momo", str(s.carta.consultar()))

    # HU-10/11/14
    def test_pedido_completo(self):
        s = self.s
        hoy = self.reloj.ahora().date().isoformat()
        cod = {p.nombre: p.codigo for p in s.almacen.platos.values()}
        s.menu.configurar_menu(hoy,
            [{"codigo": cod["Samosa"]}, {"codigo": cod["Pakora"]}, {"codigo": cod["Ensalada Sadheko"]}],
            [{"codigo": cod["Pollo Tandoori"]}, {"codigo": cod["Dal Bhat"]}, {"codigo": cod["Curry de Verduras"]}],
            [{"codigo": cod["Kheer"]}, {"codigo": cod["Gulab Jamun"]}])
        ana = self.cliente()
        items = [{"tipo": "menu", "fecha": hoy, "cantidad": 2,
                  "opciones": {"entrante": cod["Samosa"], "principal": cod["Dal Bhat"], "postre": cod["Kheer"]}},
                 {"tipo": "plato", "id": cod["Lassi de mango"], "cantidad": 1}]
        self.assertEqual(s.pedidos.resumen(items)["importe_total"], 33.0)
        with self.assertRaises(ErrorNegocio):
            s.pedidos.resumen([{"tipo": "menu", "fecha": hoy, "opciones": {"entrante": cod["Pakora"], "principal": cod["Samosa"], "postre": cod["Kheer"]}}])
        with self.assertRaises(ErrorNegocio): s.pedidos.confirmar(ana, [])
        with self.assertRaises(ErrorNegocio):   # plato solo en almacén: no se puede pedir suelto
            s.pedidos.resumen([{"tipo": "plato", "id": cod["Chatamari"], "cantidad": 1}])
        ped = s.pedidos.confirmar(ana, items)
        self.assertEqual((ped["estado"], ped["total"], ped["direccion"]), ("Recibido", 33.0, "C/ Mayor 1"))
        self.assertEqual(ped["tiempo_restante_segundos"], 600)
        self.reloj.avanzar(minutes=4)
        mis = s.pedidos.mis_pedidos(ana)[0]
        self.assertEqual((mis["tiempo_restante_segundos"], mis["modificable"]), (360, True))
        self.assertEqual(len(s.pedidos.pedidos_entrantes()), 1)
        with self.assertRaises(ErrorNegocio): s.pedidos.actualizar_estado(ped["codigo"], "Entregado")  # salta fase
        s.pedidos.actualizar_estado(ped["codigo"], "En preparación")
        self.assertEqual(s.pedidos.mis_pedidos(ana)[0]["estado"], "En preparación")
        self.assertFalse(s.pedidos.mis_pedidos(ana)[0]["modificable"])
        s.pedidos.actualizar_estado(ped["codigo"], "Entregado")
        self.assertEqual(s.pedidos.pedidos_entrantes(), [])
        with self.assertRaises(ErrorNegocio): s.pedidos.actualizar_estado(ped["codigo"], "En preparación")

    def test_permisos_y_pedido_ajeno(self):
        s = self.s
        ana = self.cliente("ana"); bea = self.cliente("bea")
        cod = {p.nombre: p.codigo for p in s.almacen.platos.values()}
        s.pedidos.confirmar(ana, [{"tipo": "plato", "id": cod["Samosa"], "cantidad": 3}])
        self.assertEqual(s.pedidos.mis_pedidos(bea), [])
        tok = s.usuarios.login("ana", "secreto1")["token"]
        with self.assertRaises(ErrorNegocio) as e: s.usuarios.autenticar(tok, "administrador")
        self.assertEqual(e.exception.estado, 403)
        with self.assertRaises(ErrorNegocio) as e: s.usuarios.autenticar(None, "cliente")
        self.assertEqual(e.exception.estado, 401)

    def test_solo_admin_toca_la_carta(self):
        from sabor import api
        s = self.s
        ruta = lambda m, p: next(f for mm, pat, f in api.RUTAS if mm == m and pat.fullmatch(p))
        tok = lambda u, pw: s.usuarios.login(u, pw)["token"]
        chef, admin = tok("chef", "chef123"), tok("admin", "admin123")
        cod = {p.nombre: p.codigo for p in s.almacen.platos.values()}
        def llamar(m, p, token, body=None, q=None):
            r = api.re.compile(r"(?P<codigo>[^/]+)$").search(p)
            return ruta(m, p)(s, token, {"codigo": r.group(1)} if r else {}, q or {}, body or {})
        nuevo = {"nombre": "Momo", "descripcion": "d", "precio": 6, "categoria": "entrante"}
        # el chef puede ver el almacén y crear platos SIN carta...
        llamar("GET", "/almacen/platos", chef)
        self.assertFalse(llamar("POST", "/almacen/platos", chef, nuevo)["en_carta"])
        # ...pero no tocar la carta
        pruebas = [("POST", "/almacen/platos", {**nuevo, "nombre": "Otro", "en_carta": True}, None),
                   ("POST", f"/carta/{cod['Chatamari']}", None, None),
                   ("DELETE", f"/carta/{cod['Samosa']}", None, None),
                   ("PUT", f"/almacen/platos/{cod['Samosa']}", {"precio": 1}, None),
                   ("DELETE", f"/almacen/platos/{cod['Samosa']}", None, {"confirmar": "true"})]
        for m, p, body, q in pruebas:
            with self.assertRaises(ErrorNegocio) as e: llamar(m, p, chef, body, q)
            self.assertEqual(e.exception.estado, 403, (m, p))
        self.assertIn(cod["Samosa"], s.almacen.carta)
        # el administrador sí
        llamar("POST", f"/carta/{cod['Chatamari']}", admin)
        self.assertIn(cod["Chatamari"], s.almacen.carta)
        llamar("DELETE", f"/carta/{cod['Chatamari']}", admin)
        self.assertNotIn(cod["Chatamari"], s.almacen.carta)


    # Auditoría: cada cambio queda en el log
    def test_auditoria(self):
        s = self.s
        ev = s.auditoria.eventos
        acciones = lambda: [e["accion"] for e in ev]
        self.assertIn("CUENTA_INTERNA_CREADA", acciones())     # datos iniciales
        self.assertIn("PLATO_CREADO", acciones())
        self.assertTrue(all(e["actor"] == "sistema" for e in ev))
        ev.clear()
        ana = self.cliente()
        self.assertEqual(acciones(), ["CLIENTE_REGISTRADO", "CUENTA_ACTIVADA", "SESION_INICIADA"])
        self.assertTrue(all(e["actor"] == "ana" for e in ev))
        # el token de activación del correo queda en el log
        token_act = s.almacen.bandeja_correos[-1]["enlace"].split("=")[1]
        self.assertEqual(ev[0]["detalle"]["token_activacion"], token_act)
        self.assertEqual(ev[0]["detalle"]["enlace"], f"/activar?token={token_act}")
        # el actor es el usuario autenticado en la petición
        tok = s.usuarios.login("admin", "admin123")["token"]
        s.usuarios.autenticar(tok, "administrador")
        cod = {p.nombre: p.codigo for p in s.almacen.platos.values()}
        s.carta.modificar_plato(cod["Samosa"], {"precio": 5})
        e = ev[-1]
        self.assertEqual((e["accion"], e["actor"], e["id"]), ("PLATO_MODIFICADO", "admin", cod["Samosa"]))
        self.assertEqual(e["detalle"]["cambios"]["precio"], {"antes": 4.5, "despues": 5.0})
        s.carta.quitar_de_carta(cod["Samosa"])
        self.assertEqual(ev[-1]["accion"], "CARTA_PLATO_QUITADO")
        n = len(ev)
        s.carta.quitar_de_carta(cod["Samosa"])                 # sin cambio real: sin evento
        with self.assertRaises(ErrorNegocio): s.carta.baja_plato(cod["Samosa"])   # fallo: sin evento
        self.assertEqual(len(ev), n)
        # pedidos
        ped = s.pedidos.confirmar(ana, [{"tipo": "plato", "id": cod["Pakora"], "cantidad": 2}])
        e = ev[-1]
        self.assertEqual((e["accion"], e["actor"], e["id"]), ("PEDIDO_CONFIRMADO", "ana", ped["codigo"]))
        self.assertEqual(e["detalle"]["total"], 8.4)
        s.pedidos.actualizar_estado(ped["codigo"], "En preparación")
        self.assertEqual(ev[-1]["detalle"], {"anterior": "Recibido", "nuevo": "En preparación"})
        # menú
        hoy = self.reloj.ahora().date().isoformat()
        s.menu.configurar_menu(hoy,
            [{"codigo": cod["Pakora"]}, {"codigo": cod["Ensalada Sadheko"]},
             {"nuevo": {"nombre": "Momo", "descripcion": "d", "categoria": "entrante"}}],
            [{"codigo": cod["Pollo Tandoori"]}, {"codigo": cod["Dal Bhat"]}, {"codigo": cod["Curry de Verduras"]}],
            [{"codigo": cod["Kheer"]}, {"codigo": cod["Gulab Jamun"]}])
        self.assertEqual(acciones()[-2:], ["PLATO_CREADO", "MENU_CONFIGURADO"])
        s.menu.quitar_menu(hoy)
        self.assertEqual(ev[-1]["accion"], "MENU_RETIRADO")
        # login fallido
        with self.assertRaises(ErrorNegocio): s.usuarios.login("ana", "mal")
        self.assertEqual((ev[-1]["accion"], ev[-1]["actor"]), ("LOGIN_FALLIDO", "anonimo"))
        # nunca contraseñas ni tokens de sesión
        volcado = json.dumps(ev)
        self.assertNotIn("secreto1", volcado); self.assertNotIn(tok, volcado)

    def test_auditoria_en_archivo(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "sub", "auditoria.log")
            s = Sistema(self.reloj, ruta_log=ruta)
            cargar(s)
            with open(ruta, encoding="utf-8") as f:
                lineas = [json.loads(l) for l in f.read().splitlines()]
            self.assertEqual(len(lineas), 21)                   # 3 cuentas + 18 platos
            self.assertEqual(set(lineas[0]), {"fecha_hora", "actor", "accion", "entidad", "id", "detalle"})
            self.assertEqual(lineas[0]["fecha_hora"], "2026-11-07T13:00:00")


if __name__ == "__main__":
    unittest.main()
