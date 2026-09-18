# Endpoint per consultare le attività salvate nel database
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Attivita
from app.db.session import get_db
from app.schemas import AttivitaOut

router = APIRouter()

#endpoint
@router.get("/attivita", response_model=list[AttivitaOut])
def elenco_attivita(db: Session = Depends(get_db)):
    return db.query(Attivita).all()