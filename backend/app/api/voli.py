# Endpoint per consultare i voli salvati nel database
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Volo
from app.db.session import get_db
from app.schemas import VoloOut

router = APIRouter()

#endpoint
@router.get("/voli", response_model=list[VoloOut])
def elenco_voli(db: Session = Depends(get_db)):
    return db.query(Volo).all()