# Dipendenze riusabili degli endpoint: "chi sta facendo questa richiesta?"
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.sicurezza import TokenNonValido, leggi_token
from app.db.models import Utente
from app.db.session import get_db

# auto_error=False: l'errore per l'header mancante lo solleviamo noi, in modo uniforme (401)
schema_bearer = HTTPBearer(auto_error=False)


def utente_corrente(
    credenziali: HTTPAuthorizationCredentials | None = Depends(schema_bearer),
    db: Session = Depends(get_db),
) -> Utente:
    """Da usare come `utente: Utente = Depends(utente_corrente)` in ogni endpoint protetto."""
    intestazione = {"WWW-Authenticate": "Bearer"}
    if credenziali is None:
        raise HTTPException(status_code=401, detail="Autenticazione richiesta.", headers=intestazione)
    try:
        utente_id = leggi_token(credenziali.credentials)
    except TokenNonValido as errore:
        raise HTTPException(status_code=401, detail=str(errore), headers=intestazione)
    utente = db.get(Utente, utente_id)
    if utente is None:  # token valido ma utente nel frattempo cancellato (es. reseed)
        raise HTTPException(status_code=401, detail="Utente non trovato.", headers=intestazione)
    return utente