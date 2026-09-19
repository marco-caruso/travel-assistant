"""
Estrae in modo strutturato i dati di viaggio (budget, nazione, preferenze,
periodo) dalla conversazione con l'utente, usando tool use. Utilizza lo stesso pattern
di genera_descrizioni.py, applicato stavolta a una conversazione multi-turno
invece che a una singola attività
"""
from typing import Literal, Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()
client = Anthropic()


class RichiestaViaggio(BaseModel):
    """Stato attuale dei dati di viaggio raccolti finora. Campi non ancora
    forniti dall'utente restano None (o lista vuota per le preferenze)."""
    budget: Optional[float] = None
    nazione: Optional[str] = None
    preferenze: list[Literal["cultura", "sport", "relax", "nightlife", "natura", "altro"]] = []
    periodo: Optional[str] = None  # mese di viaggio, es. "giugno"


STRUMENTO_ESTRAZIONE = {
    "name": "salva_richiesta_viaggio",
    "description": (
        "Salva i dati di viaggio che l'utente ha fornito finora nella "
        "conversazione. Usa null per i campi non ancora specificati, non inventare."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "budget": {
                "type": ["number", "null"],
                "description": "Budget totale in euro, se indicato.",
            },
            "nazione": {
                "type": ["string", "null"],
                "description": "Nazione di destinazione, se indicata.",
            },
            "preferenze": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["cultura", "sport", "relax", "nightlife", "natura", "altro"],
                },
                "description": "Preferenze sulle attività menzionate finora (anche vuota).",
            },
            "periodo": {
                "type": ["string", "null"],
                "description": "Mese di viaggio, se indicato (es. 'giugno').",
            },
        },
        "required": ["budget", "nazione", "preferenze", "periodo"],
    },
}


def estrai_richiesta_viaggio(messaggi: list[dict]) -> RichiestaViaggio:
    """messaggi: storico conversazione nel formato Anthropic, es.
    [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
    Ritorna lo stato completo dei dati raccolti finora (aggregando tutto lo storico)."""
    risposta = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=300,
        tools=[STRUMENTO_ESTRAZIONE],
        tool_choice={"type": "tool", "name": "salva_richiesta_viaggio"},
        messages=messaggi,
    )
    blocco_tool = next(b for b in risposta.content if b.type == "tool_use")
    return RichiestaViaggio.model_validate(blocco_tool.input)