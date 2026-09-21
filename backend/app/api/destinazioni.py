# Elenco delle destinazioni offerte dall'agenzia
from fastapi import APIRouter
from app.core.destinazioni import DESTINAZIONI
from app.schemas import DestinazioneOut

router = APIRouter()

@router.get("/destinazioni", response_model=list[DestinazioneOut])
def elenco_destinazioni():
    # Stessa fonte usata dal seed e dalla generazione degli itinerari: un solo posto da aggiornare
    return list(DESTINAZIONI.values())