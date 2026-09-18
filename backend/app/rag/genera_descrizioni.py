"""
Genera, per ogni attività nel database, una descrizione testuale e informazioni
sul target ideale usando l'API di Claude. Il risultato viene salvato in
data/descrizioni_attivita.json — da qui verrà poi letto da indicizza_attivita.py
per popolare la collection Chroma.

Perché uno script separato dall'indicizzazione: così puoi rileggere/correggere
le descrizioni generate prima che finiscano nel vettoriale.
"""
import json
from pathlib import Path
from typing import Literal

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from app.db.models import Attivita
from app.db.session import SessionLocal

load_dotenv()  # legge il file .env e lo carica come variabili d'ambiente

client = Anthropic()  # legge da sola ANTHROPIC_API_KEY dall'ambiente, non va passata a mano


class DescrizioneGenerata(BaseModel):
    """Forma attesa della risposta di Claude per una singola attività.

    Literal invece di str: se Claude risponde con un valore fuori da questa lista,
    la validazione fallisce subito invece di lasciar passare un'etichetta a caso
    che poi rovinerebbe il matching con le preferenze utente.

    Liste e non valori singoli: un'attività può ragionevolmente appartenere a più
    categorie o piacere a più target contemporaneamente (es. un tour guidato va
    bene sia per famiglie che per coppie) — costringere a un solo valore fa solo
    fallire la validazione quando Claude, giustamente, prova a dirne due.
    """
    descrizione: str
    categoria: list[Literal["cultura", "sport", "relax", "nightlife", "altro"]]
    target: list[Literal["famiglie", "giovani", "sportivi", "coppie", "altro"]]


# Schema formale che Claude deve rispettare: a differenza di chiedere "rispondi in
# JSON" a parole, questo vincola il modello a produrre esattamente questi campi,
# con questi tipi ed esattamente questi valori enum per categoria e target.
STRUMENTO_CLASSIFICAZIONE = {
    "name": "salva_classificazione",
    "description": "Salva la descrizione turistica e la classificazione di un'attività.",
    "input_schema": {
        "type": "object",
        "properties": {
            "descrizione": {
                "type": "string",
                "description": "Descrizione turistica breve, 1-2 frasi, in italiano.",
            },
            "categoria": {
                "type": "array",
                "items": {"type": "string", "enum": ["cultura", "sport", "relax", "nightlife", "altro"]},
                "description": "Una o più categorie a cui appartiene l'attività.",
            },
            "target": {
                "type": "array",
                "items": {"type": "string", "enum": ["famiglie", "giovani", "sportivi", "coppie", "altro"]},
                "description": "Uno o più pubblici a cui l'attività piacerebbe di più.",
            },
        },
        "required": ["descrizione", "categoria", "target"],
    },
}


def genera_descrizione_per_attivita(nome: str, citta: str, tentativi: int = 3) -> DescrizioneGenerata:
    """Chiede a Claude descrizione + categoria + target per una singola attività.

    Forza la risposta dentro STRUMENTO_CLASSIFICAZIONE via tool_choice, invece di
    chiedere JSON a parole: elimina sia il parsing manuale sia gran parte del
    rischio che Claude si inventi un valore fuori dall'enum. Il retry resta come
    rete di sicurezza per i casi residui.
    """
    prompt = f'Attività: "{nome}" a {citta}. Descrivila brevemente e classificala.'

    for tentativo in range(1, tentativi + 1):
        risposta = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            tools=[STRUMENTO_CLASSIFICAZIONE],
            tool_choice={"type": "tool", "name": "salva_classificazione"},
            messages=[{"role": "user", "content": prompt}],
        )
        blocco_tool = next(b for b in risposta.content if b.type == "tool_use")
        try:
            return DescrizioneGenerata.model_validate(blocco_tool.input)
        except ValidationError as errore:
            print(f"  tentativo {tentativo}/{tentativi} non valido ({errore}), riprovo...")

    raise RuntimeError(f"Nessuna risposta valida per '{nome}' dopo {tentativi} tentativi")


ROOT_DIR = Path(__file__).resolve().parents[3]
OUTPUT_PATH = ROOT_DIR / "data" / "descrizioni_attivita.json"


def main() -> None:
    db = SessionLocal()
    attivita_list = db.query(Attivita).all()
    db.close()  # non ci serve più: le chiamate a Claude non toccano il DB

    risultati = {}
    for attivita in attivita_list:
        print(f"Genero descrizione per: {attivita.nome} ({attivita.citta})...")
        descrizione = genera_descrizione_per_attivita(attivita.nome, attivita.citta)
        risultati[str(attivita.id)] = descrizione.model_dump()

    OUTPUT_PATH.write_text(
        json.dumps(risultati, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Salvate {len(risultati)} descrizioni in {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
