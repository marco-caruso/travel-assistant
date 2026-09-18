# Punto di ingresso dell'applicazione: crea il server FastAPI
# e collega i vari gruppi di endpoint (per ora solo /hotels)
from fastapi import FastAPI
from app.api.hotels import router as hotels_router

app = FastAPI(title="Travel Assistant API")

app.include_router(hotels_router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Travel Assistant API è attiva"}