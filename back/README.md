# Sabor del Himalaya – Backend (Ciclo 1)

Python 3.9+ · solo librería estándar · datos en memoria (dict/list).

    python main.py [puerto]          # API en http://127.0.0.1:8000
    python -m unittest discover -s tests -v

Cuentas de prueba: admin/admin123, chef/chef123, personal/personal123.
Los correos de activación se guardan en `almacen.bandeja_correos` (simulados).
Cada cambio del sistema se registra en `auditoria.log` (ver «Auditoría»).

| HU | Endpoint |
|----|----------|
| 01 | POST /registro |
| 02 | GET /activar?token=… |
| 03 | POST /login → token (cabecera `Authorization: Bearer <token>`) |
| 04 | GET /carta?categoria= |
| 05 | GET /menu?fecha=AAAA-MM-DD |
| 06-08 | Almacén: GET y POST /almacen/platos (admin o chef; `en_carta:true` solo admin) · PUT /almacen/platos/<codigo> y DELETE …?confirmar=true (solo admin) |
| 04/06 | Meter/sacar de la carta (solo admin): POST /carta/<codigo> · DELETE /carta/<codigo> |
| 09 | GET /chef/platos?tipo=entrante\|principal\|postre · POST /chef/menu · DELETE /chef/menu?fecha= |
| 10 | POST /pedidos/resumen · POST /pedidos |
| 11 | GET /pedidos |
| 14 | GET /personal/pedidos · PUT /personal/pedidos/<codigo>/estado |

## Modelo
- **Almacén**: todos los platos (sin temporada). Un plato puede estar *Activo* o *Retirado*.
- **Carta**: subconjunto del almacén. Solo el administrador la modifica (meter/sacar platos, editar precios, dar de baja). El chef puede ver el almacén y crear platos nuevos, pero no meterlos en la carta.
- **Menú diario**: por fecha, con platos activos del almacén (estén o no en la carta) o platos nuevos, que entran en el almacén.
- Solo se pueden pedir sueltos los platos que están en la carta.

## Auditoría
Cada cambio de estado queda en `auditoria.log` (JSON Lines, una línea por evento, se añade al final del archivo; `main.py` lo crea en el directorio de arranque):

    {"fecha_hora":"2026-11-07T13:00:00","actor":"admin","accion":"PLATO_MODIFICADO","entidad":"plato","id":"P0001","detalle":{"cambios":{"precio":{"antes":4.5,"despues":5.0}}}}

- `actor`: usuario autenticado de la petición; `sistema` para la carga inicial; `anonimo` para logins fallidos.
- Acciones: `CLIENTE_REGISTRADO`, `CUENTA_INTERNA_CREADA`, `CUENTA_ACTIVADA`, `SESION_INICIADA`, `LOGIN_FALLIDO`, `PLATO_CREADO`, `PLATO_MODIFICADO` (antes/después), `PLATO_DADO_DE_BAJA`, `CARTA_PLATO_ANADIDO`, `CARTA_PLATO_QUITADO`, `MENU_CONFIGURADO`, `MENU_RETIRADO`, `PEDIDO_CONFIRMADO`, `PEDIDO_ESTADO_CAMBIADO`.
- Solo se registran operaciones realizadas con éxito. Nunca se guardan contraseñas, hashes ni tokens de sesión; el token de activación (y su enlace) sí aparece en `CLIENTE_REGISTRADO`, así que conviene restringir los permisos de lectura de `auditoria.log`.
- `Sistema()` sin `ruta_log` guarda los eventos solo en memoria (`sistema.auditoria.eventos`), útil en tests.
- Si falla la escritura del log, el error va a `stderr` y la operación continúa.
- El archivo no rota: gestionar su tamaño desde fuera si hace falta.
- Código: `sabor/auditoria.py`.
