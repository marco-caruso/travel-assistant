# Endpoint della chat: riceve lo storico della conversazione e restituisce la risposta
from anthropic import APIError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dipendenze import utente_corrente
from app.core.chat import elabora_chat
from app.db.models import Utente
from app.db.session import get_db
from app.schemas import ChatRichiesta, ChatRisposta

router = APIRouter()


@router.post("/chat", response_model=ChatRisposta)
def chat(
    richiesta: ChatRichiesta,
    utente: Utente = Depends(utente_corrente),  # serve l'utente: la chat può prenotare per lui
    db: Session = Depends(get_db),
):
    if not richiesta.messaggi or richiesta.messaggi[-1].role != "user":
        raise HTTPException(status_code=422, detail="L'ultimo messaggio deve essere dell'utente.")
    messaggi = [m.model_dump() for m in richiesta.messaggi]
    try:
        return elabora_chat(db, messaggi, utente, richiesta.proposta)
    except APIError as errore:
        # Il servizio del modello linguistico non ha risposto: non è colpa dell'utente
        raise HTTPException(status_code=502, detail=f"Servizio linguistico non disponibile: {errore}")