# Registrazione degli utenti
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.sicurezza import hash_password
from app.db.models import Utente
from app.db.session import get_db
from app.schemas import RegistrazioneIn, UtenteOut

router = APIRouter(prefix="/auth")


@router.post("/registrazione", response_model=UtenteOut, status_code=201)
def registrazione(dati: RegistrazioneIn, db: Session = Depends(get_db)):
    email = dati.email.strip().lower()  # "User@x.it" e "user@x.it" sono lo stesso utente
    if db.scalar(select(Utente).where(Utente.email == email)) is not None:
        raise HTTPException(status_code=409, detail="Esiste già un account con questa email.")
    utente = Utente(nome=dati.nome.strip(), email=email, password_hash=hash_password(dati.password))
    db.add(utente)
    db.commit()
    db.refresh(utente)
    return utente