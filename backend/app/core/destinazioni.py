"""
Destinazioni supportate dal sistema.

L'utente esprime la destinazione come nazione ("Francia"), ma i dati nel database
sono per città e aeroporto. Questa mappa è il ponte tra i due, ed è usata sia dal
seed (per generare i dati) sia dalla generazione degli itinerari (per interpretare
la richiesta).

Semplificazione dichiarata: una sola città per nazione. Per aggiungere una
destinazione basta una riga in DESTINAZIONI (e rilanciare il seed).
"""

AEROPORTI_PARTENZA = ["CAG", "FCO", "MXP"]

DESTINAZIONI = {
    "francia": {"nazione": "Francia", "citta": "Parigi", "aeroporto": "CDG"},
    "spagna": {"nazione": "Spagna", "citta": "Barcellona", "aeroporto": "BCN"},
    "grecia": {"nazione": "Grecia", "citta": "Atene", "aeroporto": "ATH"},
    "giappone": {"nazione": "Giappone", "citta": "Tokyo", "aeroporto": "NRT"},
    "stati uniti": {"nazione": "Stati Uniti", "citta": "New York", "aeroporto": "JFK"},
}

# Il modello che estrae i dati dalla chat può restituire la nazione in forme diverse
# ("USA", "France", ...): qui normalizziamo le varianti più probabili.
ALIAS = {
    "france": "francia",
    "spain": "spagna",
    "españa": "spagna",
    "greece": "grecia",
    "japan": "giappone",
    "usa": "stati uniti",
    "stati uniti d'america": "stati uniti",
    "america": "stati uniti",
    "united states": "stati uniti",
}


def trova_destinazione(nazione: str) -> dict | None:
    """Ritorna {"nazione", "citta", "aeroporto"} oppure None se non supportata."""
    chiave = nazione.strip().lower()
    chiave = ALIAS.get(chiave, chiave)
    return DESTINAZIONI.get(chiave)


def nazioni_disponibili() -> list[str]:
    return [d["nazione"] for d in DESTINAZIONI.values()]