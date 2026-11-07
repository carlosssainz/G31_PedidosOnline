"""Datos de ejemplo: cuentas internas, almacén de platos y carta inicial."""

def cargar(s):
    s.usuarios.crear_interno("Dueño", "dueno@himalaya.es", "admin", "admin123", "administrador")
    s.usuarios.crear_interno("Chef", "chef@himalaya.es", "chef", "chef123", "chef")
    s.usuarios.crear_interno("Cocina y reparto", "cocina@himalaya.es", "personal",
                             "personal123", "personal")
    platos = [
        ("Samosa", "Empanadilla frita de patata y guisantes", 4.50, "entrante"),
        ("Tarkari Raas", "Caldo de verduras especiado", 4.00, "entrante"),
        ("Kukhura Ko Raas", "Caldo de pollo con especias", 4.50, "entrante"),
        ("Pakora", "Verduras rebozadas en harina de garbanzo", 4.20, "entrante"),
        ("Ensalada Sadheko", "Ensalada de pepino, tomate y especias", 5.00, "ensalada"),
        ("Pollo Tandoori", "Pollo marinado al horno de barro", 11.50, "tandoori"),
        ("Cordero Tandoori", "Cordero marinado al horno de barro", 13.00, "tandoori"),
        ("Curry de Verduras", "Verduras de temporada con salsa de curry", 9.50, "curry"),
        ("Dal Bhat", "Arroz con lentejas y encurtidos", 8.50, "arroz"),
        ("Gulab Jamun", "Bolitas de leche en almíbar", 3.50, "postre"),
        ("Kheer", "Arroz con leche con cardamomo", 3.50, "postre"),
        ("Lassi de mango", "Yogur batido con mango", 3.00, "bebida"),
        ("Lassi de banana", "Yogur batido con banana", 3.00, "bebida"),
        ("Agua", "Agua mineral 50 cl", 1.50, "bebida"),
        ("Té masala", "Té especiado con leche", 2.50, "bebida"),
    ]
    for n, d, p, c in platos:               # platos que están en la carta
        s.carta.alta_plato(n, d, p, c, en_carta=True)
    # platos que solo están en el almacén (el chef los usa en menús o los mete en carta)
    s.carta.alta_plato("Chatamari", "Tortita de arroz con cobertura", 6.00, "entrante")
    s.carta.alta_plato("Sel Roti", "Rosquilla dulce de arroz", 3.00, "postre")
    s.carta.alta_plato("Choila", "Búfalo/pollo especiado a la parrilla", 10.00, "tandoori")
