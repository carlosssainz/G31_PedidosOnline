from .almacen import Almacen
from .auditoria import Auditoria
from .carta import ServicioCarta
from .menu import ServicioMenu
from .pedidos import ServicioPedidos
from .usuarios import ServicioUsuarios
from .utilidades import Reloj


class Sistema:
    """Contenedor de servicios con un único almacén en memoria."""

    def __init__(self, reloj=None, ruta_log=None):
        self.reloj = reloj or Reloj()
        self.auditoria = Auditoria(self.reloj, ruta_log)
        self.almacen = Almacen()
        self.usuarios = ServicioUsuarios(self.almacen, self.reloj, self.auditoria)
        self.carta = ServicioCarta(self.almacen, self.auditoria)
        self.menu = ServicioMenu(self.almacen, self.carta, self.reloj, self.auditoria)
        self.pedidos = ServicioPedidos(self.almacen, self.reloj, self.auditoria)
