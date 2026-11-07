"""Almacén en memoria: únicamente estructuras de datos propias de Python."""


class Almacen:
    def __init__(self):
        self.usuarios = {}           # login -> Usuario
        self.login_por_correo = {}   # correo(minúsculas) -> login
        self.login_por_token = {}    # token de activación -> login
        self.sesiones = {}           # token de sesión -> login
        self.platos = {}             # código -> Plato (almacén de todos los platos)
        self.carta = set()           # códigos de los platos que están en la carta
        self.menus = {}              # date -> MenuDiario
        self.pedidos = {}            # código -> Pedido
        self.bandeja_correos = []    # correos "enviados" (simulación)
        self._sec_plato = 0
        self._sec_pedido = 0

    def nuevo_codigo_plato(self) -> str:
        self._sec_plato += 1
        return f"P{self._sec_plato:04d}"

    def nuevo_codigo_pedido(self) -> str:
        self._sec_pedido += 1
        return f"PED-{self._sec_pedido:05d}"
