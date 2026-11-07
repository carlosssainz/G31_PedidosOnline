class ErrorNegocio(Exception):
    """Error de regla de negocio. `estado` se usa como código HTTP en la API."""

    def __init__(self, mensaje: str, estado: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.estado = estado
