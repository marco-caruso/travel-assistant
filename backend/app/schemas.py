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


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"



class AttivitaPrenotataIn(BaseModel):
    attivita_id: int
    giorno: date


class PrenotazioneIn(BaseModel):
    """Solo id e giorni scelti: il prezzo NON arriva dal client, lo ricalcola il server."""
    volo_andata_id: int
    volo_ritorno_id: int
    hotel_id: int
    attivita: list[AttivitaPrenotataIn] = []
    budget: float | None = Field(default=None, gt=0)  # se presente, il totale non deve superarlo


class AttivitaPrenotataOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    giorno: date
    # Nel database la relazione si chiama "attivita_ref": qui la si legge da quel nome
    # ma nel JSON esce come "attivita".
    attivita: AttivitaOut = Field(validation_alias="attivita_ref")


class PrenotazioneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    stato: str
    data_da: date
    data_a: date
    costo_totale: float
    volo_andata: VoloOut
    volo_ritorno: VoloOut
    hotel: HotelOut
    attivita: list[AttivitaPrenotataOut]


class ChatRichiesta(BaseModel):
    # L'intera conversazione fin qui: il server non tiene memoria tra una chiamata e l'altra
    messaggi: list[MessaggioChat]
    # La proposta in attesa di conferma, così come il server l'ha restituita nell'ultima
    # risposta. Il client la rimanda indietro senza modificarla (None se non c'è).
    proposta: PrenotazioneIn | None = None


class ChatRisposta(BaseModel):
    risposta: str  # testo da mostrare all'utente
    richiesta: RichiestaViaggio | None = None  # dati raccolti finora; None se non c'è stata estrazione
    itinerario: ItinerarioOut | None = None  # presente solo quando è stato generato
    proposta: PrenotazioneIn | None = None  # gli id di quell'itinerario, da rimandare per confermare
    prenotazione: PrenotazioneOut | None = None  # presente solo quando la prenotazione è stata fatta


class DestinazioneOut(BaseModel):
    nazione: str
    citta: str