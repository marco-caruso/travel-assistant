"""
Prenotazione di un itinerario.

Il client (Streamlit, la chat, /docs) manda solo GLI ID di ciò che l'utente ha scelto:
voli, hotel, attività con il loro giorno. Tra la proposta e la prenotazione può essere
cambiato qualcosa, e soprattutto il client non è mai una fonte affidabile (chiunque può
chiamare l'API a mano con un prezzo inventato). Per questo qui si rivalida tutto dal
database e il costo totale si ricalcola: dal client non arriva nessun prezzo.

Semplificazione dichiarata: non c'è controllo di capacità (posti, camere). In produzione
servirebbero camere e posti con un controllo transazionale, per non venderli due volte
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.destinazioni import DESTINAZIONI
from app.db.models import Attivita, Hotel, Prenotazione, PrenotazioneAttivita, Utente, Volo
from app.schemas import AttivitaPrenotataIn, ItinerarioOut, PrenotazioneIn

CITTA_PER_AEROPORTO = {d["aeroporto"]: d["citta"] for d in DESTINAZIONI.values()}


class PrenotazioneNonValida(Exception):
    """L'itinerario non si può prenotare. Il messaggio è pensato per l'utente."""


class PrenotazioneDuplicata(Exception):
    """Lo stesso itinerario è già stato prenotato da questo utente."""


def crea_prenotazione(
    db: Session, utente: Utente, dati: PrenotazioneIn, oggi: date | None = None
) -> Prenotazione:
    oggi = oggi or date.today()

    andata = db.get(Volo, dati.volo_andata_id)
    ritorno = db.get(Volo, dati.volo_ritorno_id)
    hotel = db.get(Hotel, dati.hotel_id)
    if andata is None or ritorno is None or hotel is None:
        raise PrenotazioneNonValida("Un volo o l'hotel dell'itinerario non esiste più.")

    # --- coerenza di voli e hotel ---
    citta = CITTA_PER_AEROPORTO.get(andata.aeroporto_arrivo)
    if citta is None:
        raise PrenotazioneNonValida("Il volo di andata non va verso una destinazione servita.")
    if andata.data <= oggi:
        raise PrenotazioneNonValida("Il volo di andata è già partito o parte oggi: non è prenotabile.")
    if (ritorno.aeroporto_partenza != andata.aeroporto_arrivo
            or ritorno.aeroporto_arrivo != andata.aeroporto_partenza):
        raise PrenotazioneNonValida("Il volo di ritorno non corrisponde a quello di andata.")
    if ritorno.data <= andata.data:
        raise PrenotazioneNonValida("Il volo di ritorno deve essere dopo quello di andata.")
    if hotel.citta != citta:
        raise PrenotazioneNonValida(f"L'hotel non si trova a {citta}.")
    if not (hotel.disponibile_da <= andata.data and hotel.disponibile_a >= ritorno.data):
        raise PrenotazioneNonValida("L'hotel non è disponibile per tutto il soggiorno.")

    # --- attività: una sola volta ciascuna, in città, dentro il soggiorno, disponibili quel giorno ---
    scelte: list[tuple[Attivita, date]] = []
    gia_viste: set[int] = set()
    for voce in sorted(dati.attivita, key=lambda v: v.giorno):
        attivita = db.get(Attivita, voce.attivita_id)
        if attivita is None:
            raise PrenotazioneNonValida(f"L'attività {voce.attivita_id} non esiste.")
        if attivita.id in gia_viste:
            raise PrenotazioneNonValida(f"L'attività «{attivita.nome}» è indicata più di una volta.")
        gia_viste.add(attivita.id)
        if attivita.citta != citta:
            raise PrenotazioneNonValida(f"L'attività «{attivita.nome}» non è a {citta}.")
        if not (andata.data <= voce.giorno < ritorno.data):
            raise PrenotazioneNonValida(f"Il {voce.giorno:%d/%m/%Y} è fuori dal soggiorno.")
        if not (attivita.disponibile_da <= voce.giorno <= attivita.disponibile_a):
            raise PrenotazioneNonValida(
                f"L'attività «{attivita.nome}» non è disponibile il {voce.giorno:%d/%m/%Y}."
            )
        scelte.append((attivita, voce.giorno))

    # --- prezzo: sempre ricalcolato qui, con le stesse regole del generatore di itinerari ---
    notti = (ritorno.data - andata.data).days
    totale = round(
        andata.costo + ritorno.costo + notti * hotel.costo_per_notte
        + sum(a.costo for a, _ in scelte),
        2,
    )
    if dati.budget is not None and totale > dati.budget:
        raise PrenotazioneNonValida(
            f"Il totale ({totale:.2f} €) supera il budget indicato ({dati.budget:.2f} €)."
        )

    # --- niente doppioni: stesso itinerario già prenotato dallo stesso utente ---
    doppione = db.scalar(
        select(Prenotazione.id).where(
            Prenotazione.utente_id == utente.id,
            Prenotazione.volo_andata_id == andata.id,
            Prenotazione.volo_ritorno_id == ritorno.id,
            Prenotazione.hotel_id == hotel.id,
            Prenotazione.stato == "confermata",
        )
    )
    if doppione is not None:
        raise PrenotazioneDuplicata("Hai già prenotato questo itinerario.")

    # --- salvataggio: prenotazione e attività insieme, in un'unica transazione ---
    prenotazione = Prenotazione(
        utente_id=utente.id,
        volo_andata_id=andata.id,
        volo_ritorno_id=ritorno.id,
        hotel_id=hotel.id,
        stato="confermata",
        data_da=andata.data,
        data_a=ritorno.data,
        costo_totale=totale,
    )
    prenotazione.attivita = [
        PrenotazioneAttivita(attivita_id=a.id, giorno=giorno) for a, giorno in scelte
    ]
    db.add(prenotazione)
    db.commit()  # o si salva tutto o niente
    db.refresh(prenotazione)
    return prenotazione



def prenotazione_da_itinerario(itinerario: ItinerarioOut) -> PrenotazioneIn:
    """Gli id di un itinerario proposto, nella forma che serve per prenotarlo."""
    return PrenotazioneIn(
        volo_andata_id=itinerario.volo_andata.id,
        volo_ritorno_id=itinerario.volo_ritorno.id,
        hotel_id=itinerario.hotel.id,
        attivita=[
            AttivitaPrenotataIn(attivita_id=g.attivita.id, giorno=g.giorno)
            for g in itinerario.giorni
            if g.attivita is not None
        ],
        budget=itinerario.budget,
    )