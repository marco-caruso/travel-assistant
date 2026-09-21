# Registrazione, login e profilo dell'utente
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dipendenze import utente_corrente
from app.core.sicurezza import crea_token, hash_password, verifica_password
from app.db.models import Utente
from app.db.session import get_db
from app.schemas import LoginIn, RegistrazioneIn, TokenOut, UtenteOut

router = APIRouter(prefix="/auth")

# Hash di una password qualunque: se l'email non esiste verifichiamo comunque contro questo,
# così la risposta impiega lo stesso tempo e non si può scoprire quali email sono registrate.
_HASH_FINTO = hash_password("password-che-nessuno-usera")


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


@router.post("/login", response_model=TokenOut)
def login(dati: LoginIn, db: Session = Depends(get_db)):
    utente = db.scalar(select(Utente).where(Utente.email == dati.email.strip().lower()))
    password_ok = verifica_password(dati.password, utente.password_hash if utente else _HASH_FINTO)
    if utente is None or not password_ok:
        # Stesso messaggio per "email sconosciuta" e "password errata"
        raise HTTPException(status_code=401, detail="Email o password non corrette.")
    return TokenOut(access_token=crea_token(utente.id))


@router.get("/me", response_model=UtenteOut)
def profilo(utente: Utente = Depends(utente_corrente)):
    return utente