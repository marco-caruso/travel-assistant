"""
Orchestrazione della conversazione: un solo punto dove si decide, ad ogni messaggio,
cosa fa il sistema. Il flusso è sempre lo stesso:

    storico -> estrazione dei dati (LLM) -> validazione (codice)
            -> se manca qualcosa: si fa UNA domanda
            -> se è completa: si genera l'itinerario (codice) e lo si presenta

Il LLM interviene solo nel primo passo, per capire il linguaggio. Cosa chiedere e cosa
proporre lo decide il codice.
"""
from sqlalchemy.orm import Session

from app.core.itinerario import ItinerarioNonTrovato, genera_itinerario
from app.core.validazione import prossima_domanda, valuta_richiesta
from app.llm.estrazione import estrai_richiesta_viaggio
from app.schemas import ChatRisposta, ItinerarioOut


def testo_itinerario(itinerario: ItinerarioOut) -> str:
    """Frase di presentazione. Per ora fissa: i numeri arrivano dall'itinerario, non da un LLM."""
    testo = (
        f"Ho preparato un viaggio di {itinerario.notti} notti a {itinerario.citta} "
        f"({itinerario.nazione}): costo totale {itinerario.costo_totale:.2f} € "
        f"su un budget di {itinerario.budget:.2f} €."
    )
    if itinerario.avvisi:
        testo += " " + " ".join(itinerario.avvisi)
    return testo


def elabora_chat(db: Session, messaggi: list[dict]) -> ChatRisposta:
    richiesta = estrai_richiesta_viaggio(messaggi)

    domanda = prossima_domanda(valuta_richiesta(richiesta))
    if domanda is not None:
        return ChatRisposta(risposta=domanda, richiesta=richiesta)

    try:
        itinerario = genera_itinerario(db, richiesta)
    except (ItinerarioNonTrovato, ValueError) as errore:
        # Non è un errore del server: è una risposta di conversazione (es. budget troppo basso)
        return ChatRisposta(risposta=str(errore), richiesta=richiesta)

    return ChatRisposta(
        risposta=testo_itinerario(itinerario),
        richiesta=richiesta,
        itinerario=itinerario,
    )