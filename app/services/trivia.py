"""Retos cotidianos de lectura rápida para visitantes sin formación técnica."""
from random import SystemRandom

def questions():
    bank = [
        {
            "prompt": "Para reparar este circuito y encender tu laptop necesitas conectar la corriente (1) Y presionar el botón de encendido (1). ¿Cuál es la salida del circuito?",
            "options": ["1 - Enciende", "0 - Apagado"],
            "hint": "Una compuerta AND solo da 1 si AMBAS entradas están activas.",
            "correct": 0,
            "explanation": "¡Enciende! Corriente Y botón activos: la salida es 1.",
        },
        {
            "prompt": "Para recargar tu celular puedes usar un tomacorriente O una batería portátil. Con solo tener UNA opción disponible, ¿el teléfono recibe carga?",
            "options": ["1 - Sí recibe carga", "0 - No carga"],
            "hint": "Una compuerta OR se activa si al menos una entrada es 1.",
            "correct": 0,
            "explanation": "¡Sí recibe carga! Basta con tener una opción disponible.",
        },
        {
            "prompt": "¿Por qué NO debemos tirar cables, cargadores o baterías a la basura común?",
            "options": [
                "Porque contienen metales pesados que contaminan el suelo y agua",
                "Porque ocupan poco espacio en el vertedero",
                "Porque se degradan solos en 2 días",
            ],
            "hint": "Piensa en cómo sus materiales pueden afectar al ambiente.",
            "correct": 0,
            "explanation": "¡Exacto! Entrégalos en un punto de recolección RAEE para su gestión adecuada.",
        },
    ]
    for question in bank:
        order = list(range(len(question["options"])))
        SystemRandom().shuffle(order)
        question["correct"] = order.index(question["correct"])
        question["options"] = [question["options"][i] for i in order]
    return bank
