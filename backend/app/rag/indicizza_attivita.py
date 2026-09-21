"""
Legge le attività dal database relazionale e le descrizioni generate in
data/descrizioni_attivita.json, poi popola la collection Chroma in data/chroma/
per la ricerca semantica (RAG)
"""
import json
from pathlib import Path

import chromadb

from app.db.models import Attivita
from app.db.session import SessionLocal

ROOT_DIR = Path(__file__).resolve().parents[3]
DESCRIZIONI_PATH = ROOT_DIR / "data" / "descrizioni_attivita.json"
CHROMA_DIR = ROOT_DIR / "data" / "chroma"

# PersistentClient salva su disco invece che solo in memoria; get_or_create_collection
# evita errori se lo script viene rilanciato e la collection esiste già
client_chroma = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = client_chroma.get_or_create_collection("attivita")


def costruisci_documento(nome: str, citta: str, voce: dict) -> str:
    """Testo che verrà trasformato in embedding.

    Include categoria e target in linguaggio naturale invece che nei metadata,
    perché Chroma accetta solo valori singoli nei metadata (non liste) — qui
    invece il linguaggio naturale li porta comunque dentro la ricerca semantica.
    """
    categorie = ", ".join(voce["categoria"])
    target = ", ".join(voce["target"])
    return (
        f"{nome} a {citta}. {voce['descrizione']} "
        f"Categoria: {categorie}. Adatta a: {target}."
    )


def main() -> None:
    descrizioni = json.loads(DESCRIZIONI_PATH.read_text(encoding="utf-8"))

    db = SessionLocal()
    attivita_list = db.query(Attivita).all()
    db.close()

    ids, documents, metadatas = [], [], []
    for attivita in attivita_list:
        voce = descrizioni.get(str(attivita.id))
        if voce is None:
            print(f"Attenzione: nessuna descrizione per attività {attivita.id} ({attivita.nome}), salto.")
            continue

        ids.append(str(attivita.id))
        documents.append(costruisci_documento(attivita.nome, attivita.citta, voce))
        metadatas.append({"citta": attivita.citta})  # unico campo che ha senso filtrare esattamente

    # upsert e non add: se rilanci lo script (es. dopo aver corretto una descrizione)
    # sovrascrive invece di fallire per id duplicati.
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Indicizzate {len(ids)} attività nella collection '{collection.name}'.")


def assicura_indice() -> None:
    """Costruisce l'indice vettoriale se la collection è vuota (es. dopo un clone
    pulito, dato che data/chroma/ non è versionata). Se l'indice c'è già non fa nulla."""
    if collection.count() > 0:
        return
    print(
        "Indice vettoriale assente: lo costruisco ora. Al primo avvio scarica il modello "
        "di embedding, può richiedere qualche decina di secondi."
    )
    main()


if __name__ == "__main__":
    main()