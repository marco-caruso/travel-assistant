# Definizione della forma dei dati che l'API restituisce: converte gli oggetti
# del database (SQLAlchemy) in JSON valido, tramite Pydantic.
from datetime import date

from pydantic import BaseModel, ConfigDict


class HotelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # permette di leggere i campi da un oggetto Hotel

    id: int
    nome: str
    citta: str
    costo_per_notte: float
    disponibile_da: date
    disponibile_a: date