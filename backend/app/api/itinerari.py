# Endpoint per generare un itinerario a partire dai dati di viaggio raccolti
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.itinerario import ItinerarioNonTrovato, genera_itinerario
from app.db.session import get_db
from app.llm.estrazione import RichiestaViaggio
from app.schemas import ItinerarioOut

router = APIRouter()


@router.post("/itinerari", response_model=ItinerarioOut)
def crea_itinerario(richiesta: RichiestaViaggio, db: Session = Depends(get_db)):
    try:
        return genera_itinerario(db, richiesta)
    except ItinerarioNonTrovato as errore:
        raise HTTPException(status_code=404, detail=str(errore))
    except ValueError as errore:
        raise HTTPException(status_code=422, detail=str(errore))