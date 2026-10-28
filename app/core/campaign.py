"""Contenido oficial compartido por persistencia, API y vistas."""
from enum import Enum

COLLECTION_POINT = "Facultad de tecnología e innovación (Edificio A)"


class Category(str, Enum):
    celulares = "Celulares"
    cargadores = "Cargadores"
    cables = "Cables"
    teclados = "Teclados"
    mouse = "Mouse"
    audifonos = "Audífonos"
    otros = "Otros aparatos en desuso"
