import secrets

# Each round selects one gate, one number conversion and one environmental challenge.
def questions():
    gate = secrets.choice([("AND", "1", "0", 0), ("OR", "1", "0", 1), ("NOT", "0", "", 1), ("XOR", "1", "1", 0)])
    name, a, b, result = gate
    number = secrets.choice([10, 12, 15])
    q = [
        {"prompt": f"Compuerta {name}: entrada {a}" + (f" y {b}" if b else "") + ". ¿Qué salida repara el circuito?", "options": ["0", "1"], "correct": result,
         "explanation": "AND requiere dos unos; OR al menos uno; NOT invierte; XOR vale uno si las entradas son distintas."},
        {"prompt": f"El bus muestra {number:04b}. ¿Cuál es su valor hexadecimal?", "options": ["0xA", "0xC", "0xF"], "correct": [10,12,15].index(number), "explanation": f"{number:04b} en binario representa {number} en decimal y 0x{number:X} en hexadecimal."},
        {"prompt": "Un dispositivo ya no funciona. ¿Qué ayuda a gestionar sus residuos?", "options": ["Mezclarlo con basura doméstica", "Quemarlo para reducir su tamaño", "Entregarlo a un punto de recolección RAEE"], "correct": 2, "explanation": "La recolección diferenciada facilita recuperar materiales y gestionar componentes que requieren cuidado."}
    ]
    return q
