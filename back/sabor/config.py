"""Constantes de negocio del sistema Sabor del Himalaya."""
from decimal import Decimal

CATEGORIAS = ("entrante", "ensalada", "tandoori", "curry", "arroz", "postre", "bebida")
# Categorías que NO sirven como plato principal del menú diario
CATEGORIAS_NO_PRINCIPAL = ("entrante", "ensalada", "postre", "bebida")
ROLES = ("cliente", "chef", "administrador", "personal")

PRECIO_MENU = Decimal("15.00")
MINUTOS_MODIFICACION = 10
HORAS_VALIDEZ_TOKEN = 24

# Estados de cuenta
CUENTA_PENDIENTE = "Pendiente"
CUENTA_ACTIVA = "Activa"
# Estados de plato
PLATO_ACTIVO = "Activo"
PLATO_RETIRADO = "Retirado"
# Estados de pedido
RECIBIDO = "Recibido"
EN_PREPARACION = "En preparación"
ENTREGADO = "Entregado"
CANCELADO = "Cancelado"
SIGUIENTE_ESTADO = {RECIBIDO: EN_PREPARACION, EN_PREPARACION: ENTREGADO}
