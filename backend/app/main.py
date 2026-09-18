from fastapi import FastAPI

app = FastAPI(title="Travel Assistant API")


@app.get("/")
def root():
    return {"status": "ok", "message": "Travel Assistant API è attiva"}