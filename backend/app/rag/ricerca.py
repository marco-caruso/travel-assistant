"""
Ricerca semantica (RAG) sulle attività: date le preferenze dell'utente, ordina le
attività di una città per affinità. Legge la collection creata da indicizza_attivita.py.
"""
from functools import lru_cache
from pathlib import Path

import chromadb

ROOT_DIR = Path(__file__).resolve().parents[3]
CHROMA_DIR = ROOT_DIR / "data" / "chroma"

# I testi indicizzati sono frasi descrittive, e un modello di embedding confronta meglio
# una frase con un'altra frase che una parola sola ("natura") con una frase. Per questo
# ogni preferenza viene tradotta in una breve descrizione prima di cercare.
# "altro" non compare: non porta informazione utile per ordinare, quindi viene ignorata.
DESCRIZIONE_PREFERENZE = {
    "cultura": "visite a musei, monumenti, siti storici e luoghi d'arte",
    "sport": "attività sportive e fisiche, escursioni a piedi, giri in bicicletta",
    "relax": "relax e benessere, spa, terme, momenti tranquilli e rilassanti",
    "nightlife": "vita notturna, serate in locali con musica e spettacoli",
    "natura": "natura all'aria aperta, parchi, giardini, montagne, mare e paesaggi",
}


@lru_cache(maxsize=1)
def _collection():
    # Aperta al primo uso e riusata: aprire il client Chroma a ogni richiesta sarebbe lento
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection("attivita")


def _classifica(citta: str, testo: str, n: int) -> list[int]:
    """Id delle attività di `citta`, dalla più alla meno simile a `testo`.

    Il filtro `where` limita la ricerca alla città (unico campo filtrabile in modo
    esatto); l'ordine lo decide la similarità semantica tra `testo` e i testi indicizzati.
    """
    risultato = _collection().query(query_texts=[testo], n_results=n, where={"citta": citta})
    return [int(i) for i in risultato["ids"][0]]


def _fondi_classifiche(classifiche: list[list[int]]) -> list[int]:
    """Unisce più classifiche in una sola (metodo Borda): ogni posizione vale punti,
    più è alta più ne vale, e i punti ottenuti nelle varie classifiche si sommano.
    Un'attività molto adatta a una preferenza e discreta per l'altra batte una
    generica, che non eccelle in nessuna."""
    punteggi: dict[int, int] = {}
    for classifica in classifiche:
        for posizione, id_attivita in enumerate(classifica):
            punteggi[id_attivita] = punteggi.get(id_attivita, 0) + (len(classifica) - posizione)
    return sorted(punteggi, key=lambda i: punteggi[i], reverse=True)


def cerca_attivita(citta: str, preferenze: list[str], n: int = 20) -> list[int]:
    """Ritorna gli id delle attività di `citta`, dalla più alla meno pertinente.

    Una ricerca per ogni preferenza, poi le classifiche vengono fuse: cercare tutte le
    preferenze in un'unica frase mescolerebbe i significati e darebbe risultati sfocati.
    Lista vuota se non ci sono preferenze utili (chi chiama userà un altro criterio).
    """
    classifiche = [
        _classifica(citta, DESCRIZIONE_PREFERENZE[p], n)
        for p in preferenze
        if p in DESCRIZIONE_PREFERENZE
    ]
    return _fondi_classifiche(classifiche)