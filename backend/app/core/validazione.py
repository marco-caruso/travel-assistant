"""
Controllo della richiesta di viaggio raccolta finora dalla conversazione.

Distingue due casi diversi: un dato "mancante" (l'utente non l'ha ancora detto, basta
chiederlo) e un dato "non valido" (l'utente l'ha detto ma non possiamo usarlo, es. una
nazione che non serviamo). Decide anche quale domanda fare per prima. Nessun modello
linguistico qui: cosa chiedere lo decide il codice, in modo prevedibile e testabile
"""
from dataclasses import dataclass, field

from app.core.destinazioni import nazioni_disponibili, trova_destinazione
from app.core.itinerario import MESI
from app.llm.estrazione import RichiestaViaggio

# Ordine in cui si chiedono i dati: prima dove e quando, poi i gusti, infine il budget.
ORDINE_DOMANDE = ["nazione", "periodo", "preferenze", "budget"]

DOMANDE = {
    "nazione": "In quale nazione ti piacerebbe andare?",
    "periodo": "In quale mese vorresti partire?",
    "preferenze": "Che tipo di attività preferisci? Per esempio cultura, sport, relax, nightlife o natura.",
    "budget": "Qual è il tuo budget totale per il viaggio, in euro?",
}


@dataclass
class EsitoValidazione:
    mancanti: list[str] = field(default_factory=list)       # campi non ancora forniti
    problemi: dict[str, str] = field(default_factory=dict)  # campo -> messaggio per l'utente

    @property
    def completa(self) -> bool:
        return not self.mancanti and not self.problemi


def valuta_richiesta(richiesta: RichiestaViaggio) -> EsitoValidazione:
    esito = EsitoValidazione()

    if not richiesta.nazione:
        esito.mancanti.append("nazione")
    elif trova_destinazione(richiesta.nazione) is None:
        esito.problemi["nazione"] = (
            f"Non ho destinazioni disponibili per '{richiesta.nazione}'. "
            f"Posso proporti: {', '.join(nazioni_disponibili())}. Quale preferisci?"
        )

    if not richiesta.periodo:
        esito.mancanti.append("periodo")
    elif not any(mese in richiesta.periodo.lower() for mese in MESI):
        esito.problemi["periodo"] = (
            f"Non riesco a interpretare '{richiesta.periodo}' come mese. "
            "In quale mese vorresti partire (es. giugno)?"
        )

    if not richiesta.preferenze:
        esito.mancanti.append("preferenze")

    if richiesta.budget is None:
        esito.mancanti.append("budget")
    elif richiesta.budget <= 0:
        esito.problemi["budget"] = "Il budget deve essere maggiore di zero. Qual è il tuo budget in euro?"

    return esito


def prossima_domanda(esito: EsitoValidazione) -> str | None:
    """La prossima domanda da fare, o None se la richiesta è completa e valida.
    I dati non validi hanno la precedenza: vanno corretti prima di andare avanti."""
    for campo in ORDINE_DOMANDE:
        if campo in esito.problemi:
            return esito.problemi[campo]
    for campo in ORDINE_DOMANDE:
        if campo in esito.mancanti:
            return DOMANDE[campo]
    return None