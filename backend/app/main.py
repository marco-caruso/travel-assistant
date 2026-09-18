# Punto di ingresso dell'applicazione: crea il server FastAPI
# e collega i vari gruppi di endpoint (hotel, voli, attività)
from fastapi import FastAPI
from app.api.hotels import router as hotels_router
from app.api.voli import router as voli_router
from app.api.attivita import router as attivita_router

app = FastAPI(title="Travel Assistant API")

app.include_router(hotels_router)
app.include_router(voli_router)
app.include_router(attivita_router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Travel Assistant API è attiva"}