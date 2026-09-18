# Endpoint per consultare gli hotel salvati nel database
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Hotel
from app.db.session import get_db
from app.schemas import HotelOut

router = APIRouter()

#endpoint
@router.get("/hotels", response_model=list[HotelOut])
def elenco_hotel(db: Session = Depends(get_db)):
    return db.query(Hotel).all()