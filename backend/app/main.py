# Punto di ingresso dell'applicazione: crea il server FastAPI
# e collega i vari gruppi di endpoint (hotel, voli, attività)
from fastapi import FastAPI
from app.api.hotels import router as hotels_router
from app.api.voli import router as voli_router
from app.api.attivita import router as attivita_router
from app.api.itinerari import router as itinerari_router
from app.api.chat import router as chat_router
from app.api.auth import router as auth_router

app = FastAPI(title="Travel Assistant API")

app.include_router(hotels_router)
app.include_router(voli_router)
app.include_router(attivita_router)
app.include_router(itinerari_router)
app.include_router(chat_router)
app.include_router(auth_router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Travel Assistant API è attiva"}