# Prenotazione di un itinerario e lista delle prenotazioni dell'utente loggato
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dipendenze import utente_corrente
from app.core.prenotazione import PrenotazioneDuplicata, PrenotazioneNonValida, crea_prenotazione
from app.db.models import Prenotazione, Utente
from app.db.session import get_db
from app.schemas import PrenotazioneIn, PrenotazioneOut

router = APIRouter(prefix="/prenotazioni")


@router.post("", response_model=PrenotazioneOut, status_code=201)
def prenota(
    dati: PrenotazioneIn,
    utente: Utente = Depends(utente_corrente),
    db: Session = Depends(get_db),
):
    try:
        return crea_prenotazione(db, utente, dati)
    except PrenotazioneDuplicata as errore:
        raise HTTPException(status_code=409, detail=str(errore))
    except PrenotazioneNonValida as errore:
        raise HTTPException(status_code=422, detail=str(errore))


@router.get("", response_model=list[PrenotazioneOut])
def le_mie_prenotazioni(
    utente: Utente = Depends(utente_corrente),
    db: Session = Depends(get_db),
):
    # Solo quelle dell'utente del token: l'id utente non arriva mai dal client
    return db.scalars(
        select(Prenotazione)
        .where(Prenotazione.utente_id == utente.id)
        .order_by(Prenotazione.id.desc())
    ).all()