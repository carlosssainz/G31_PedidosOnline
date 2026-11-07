"""Arranque: python main.py [puerto]"""
import sys
from sabor.api import crear_servidor
from sabor.datos_iniciales import cargar
from sabor.sistema import Sistema

if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    sistema = Sistema(ruta_log="auditoria.log")
    cargar(sistema)
    srv = crear_servidor(sistema, puerto=puerto)
    print(f"Sabor del Himalaya escuchando en http://127.0.0.1:{puerto}")
    print("Log de auditoría: auditoria.log")
    print("Cuentas: admin/admin123, chef/chef123, personal/personal123")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
