"""
Orchestrazione della conversazione: un solo punto dove si decide, ad ogni messaggio,
cosa fa il sistema. Flusso:

    c'è una proposta in attesa e l'utente conferma -> si prenota (codice, nessun LLM)
    c'è una proposta in attesa e l'utente rifiuta  -> si lascia stare
    altrimenti:
        storico -> estrazione dei dati (LLM) -> validazione (codice)
                -> se manca qualcosa: si fa UNA domanda
                -> se è completa: si genera l'itinerario (codice) e lo si propone

Il LLM interviene solo nell'estrazione, per capire il linguaggio. Cosa chiedere, cosa
proporre e quando prenotare lo decide il codice.

La chat resta senza memoria sul server: la proposta in attesa viaggia nella risposta
("proposta") e il client la rimanda con il messaggio successivo.
"""
from sqlalchemy.orm import Session

from app.core.conferma import e_conferma, e_rifiuto
from app.core.itinerario import NOTTI_MAX, ItinerarioNonTrovato, genera_itinerario
from app.core.prenotazione import (
    PrenotazioneDuplicata,
    PrenotazioneNonValida,
    crea_prenotazione,
    prenotazione_da_itinerario,
)
from app.core.validazione import prossima_domanda, valuta_richiesta
from app.db.models import Prenotazione, Utente
from app.llm.estrazione import estrai_richiesta_viaggio
from app.schemas import ChatRisposta, ItinerarioOut, PrenotazioneIn, PrenotazioneOut


def testo_itinerario(itinerario: ItinerarioOut, spiega_durata: bool = True) -> str:
    """Frase di presentazione. Per ora fissa: i numeri arrivano dall'itinerario, non da un LLM."""
    testo = (
        f"Ho preparato un viaggio di {itinerario.notti} notti a {itinerario.citta} "
        f"({itinerario.nazione}): costo totale {itinerario.costo_totale:.2f} € "
        f"su un budget di {itinerario.budget:.2f} €."
    )
    if itinerario.avvisi:
        testo += " " + " ".join(itinerario.avvisi)
    if spiega_durata and itinerario.notti < NOTTI_MAX:
        # La durata non la sceglie l'utente: è la più lunga che entra nel budget. Dirlo evita
        # che sembri una scelta arbitraria e indica come ottenere un viaggio più lungo.
        testo += (
            f" Ho scelto {itinerario.notti} notti perché è la durata più lunga che ho trovato "
            "entro il budget: con un budget più alto potrei proporti più notti."
        )
    testo += " Vuoi prenotarlo? Scrivi «sì» per confermare, oppure dimmi cosa cambiare."
    return testo


def testo_prenotazione(prenotazione: Prenotazione) -> str:
    return (
        f"Prenotazione confermata (codice {prenotazione.id}): {prenotazione.hotel.citta}, "
        f"dal {prenotazione.data_da:%d/%m/%Y} al {prenotazione.data_a:%d/%m/%Y}, "
        f"totale {prenotazione.costo_totale:.2f} €. La trovi tra le tue prenotazioni."
    )


def _prenota_dalla_chat(db: Session, utente: Utente, proposta: PrenotazioneIn) -> ChatRisposta:
    try:
        prenotazione = crea_prenotazione(db, utente, proposta)
    except PrenotazioneDuplicata as errore:
        return ChatRisposta(risposta=str(errore))
    except PrenotazioneNonValida as errore:
        # Non è un errore del server: la proposta non regge più (o è stata manomessa)
        return ChatRisposta(
            risposta=f"Non riesco a prenotare: {errore} Dimmi se vuoi che prepari una nuova proposta."
        )
    return ChatRisposta(
        risposta=testo_prenotazione(prenotazione),
        prenotazione=PrenotazioneOut.model_validate(prenotazione),
    )


def elabora_chat(
    db: Session,
    messaggi: list[dict],
    utente: Utente,
    proposta: PrenotazioneIn | None = None,
) -> ChatRisposta:
    if proposta is not None:
        ultimo = messaggi[-1]["content"]
        if e_conferma(ultimo):
            return _prenota_dalla_chat(db, utente, proposta)
        if e_rifiuto(ultimo):
            return ChatRisposta(
                risposta="Va bene, non prenoto. Se vuoi, dimmi cosa cambiare (nazione, mese, "
                "attività o budget) e preparo un'altra proposta."
            )

    richiesta = estrai_richiesta_viaggio(messaggi)

    domanda = prossima_domanda(valuta_richiesta(richiesta))
    if domanda is not None:
        return ChatRisposta(risposta=domanda, richiesta=richiesta)

    try:
        itinerario = genera_itinerario(db, richiesta)
    except (ItinerarioNonTrovato, ValueError) as errore:
        # Non è un errore del server: è una risposta di conversazione (es. budget troppo basso)
        return ChatRisposta(risposta=str(errore), richiesta=richiesta)

    nuova_proposta = prenotazione_da_itinerario(itinerario)
    if nuova_proposta == proposta:
        # I dati sono gli stessi di prima, quindi la proposta è identica: dirlo, e spiegare
        # cosa si può cambiare, invece di ripeterla come se niente fosse.
        testo = (
            "Non ho cambiato nulla: posso modificare nazione, mese, preferenze e budget. "
            f"La durata la scelgo io: è la più lunga, fino a {NOTTI_MAX} notti, che entra nel "
            "budget. Con più budget posso proporti più notti, con meno un viaggio più breve "
            "o più economico. " + testo_itinerario(itinerario, spiega_durata=False)
        )
    else:
        testo = testo_itinerario(itinerario)
        
    return ChatRisposta(
        risposta=testo,
        richiesta=richiesta,
        itinerario=itinerario,
        proposta=nuova_proposta,
    )