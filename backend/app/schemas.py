# Definizione della forma dei dati che l'API restituisce: converte gli oggetti
# del database (SQLAlchemy) in JSON valido, tramite Pydantic.
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.llm.estrazione import RichiestaViaggio


class HotelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # permette di leggere i campi da un oggetto Hotel
    id: int
    nome: str
    citta: str
    costo_per_notte: float
    disponibile_da: date
    disponibile_a: date

class VoloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # permette di leggere i campi da un oggetto Volo
    id: int
    aeroporto_partenza: str
    aeroporto_arrivo: str
    data: date
    costo: float

class AttivitaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # permette di leggere i campi da un oggetto Attivita
    id: int
    nome: str
    citta: str
    costo: float
    disponibile_da: date
    disponibile_a: date

class GiornoOut(BaseModel):
    giorno: date
    attivita: AttivitaOut | None = None  # None se per quel giorno non c'è un'attività adatta


class ItinerarioOut(BaseModel):
    nazione: str
    citta: str
    notti: int
    volo_andata: VoloOut
    volo_ritorno: VoloOut
    hotel: HotelOut
    giorni: list[GiornoOut]
    costo_voli: float
    costo_hotel: float
    costo_attivita: float
    costo_totale: float
    budget: float
    avvisi: list[str] = []

class MessaggioChat(BaseModel):
    """Un messaggio della conversazione, nello stesso formato usato dall'API di Anthropic."""
    role: Literal["user", "assistant"]
    content: str


class ChatRichiesta(BaseModel):
    # L'intera conversazione fin qui: il server non tiene memoria tra una chiamata e l'altra
    messaggi: list[MessaggioChat]


class ChatRisposta(BaseModel):
    risposta: str # testo da mostrare all'utente
    richiesta: RichiestaViaggio # dati raccolti finora (utile per debug e frontend)
    itinerario: ItinerarioOut | None = None  # presente solo quando è stato generato

class RegistrazioneIn(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UtenteOut(BaseModel):
    """Volutamente senza password né hash: non devono mai uscire dall'API."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    email: str