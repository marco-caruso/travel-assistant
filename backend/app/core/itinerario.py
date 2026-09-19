"""
Generazione dell'itinerario: combina volo di andata e ritorno, hotel e attività
rispettando budget, disponibilità e preferenze.

Scelta di design: la parte "rigida" (date, disponibilità, costi) è codice deterministico
che interroga il database relazionale. 
Il modello linguistico non decide mai prezzi odisponibilità, perché li inventerebbe 
o comunque avrebbe allucinazioni. 
La ricerca semantica (RAG) interviene solo dove serve davvero: ordinare le attività 
per affinità con le preferenze dell'utente.
"""
import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.destinazioni import nazioni_disponibili, trova_destinazione
from app.db.models import Attivita, Hotel, Volo
from app.llm.estrazione import RichiestaViaggio
from app.rag.ricerca import cerca_attivita
from app.schemas import AttivitaOut, GiornoOut, HotelOut, ItinerarioOut, VoloOut

NOTTI_MIN = 3
NOTTI_MAX = 5

MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}


class ItinerarioNonTrovato(Exception):
    """Nessun itinerario valido. Il messaggio è pensato per essere mostrato all'utente."""


@dataclass
class Combinazione:
    andata: Volo
    ritorno: Volo
    hotel: Hotel
    notti: int
    costo: float  # voli + hotel


def finestra_periodo(periodo: str, oggi: date) -> tuple[date, date]:
    """Da un mese ("marzo") ricava il primo e l'ultimo giorno utili di partenza.

    Se il mese è già passato quest'anno si intende l'anno prossimo. Nel mese corrente
    si parte dal giorno dopo oggi.
    """
    testo = periodo.lower()
    mese = next((numero for nome, numero in MESI.items() if nome in testo), None)
    if mese is None:
        raise ItinerarioNonTrovato(
            f"Non riesco a interpretare il periodo '{periodo}': indicami un mese (es. giugno)."
        )
    anno = oggi.year if mese >= oggi.month else oggi.year + 1
    primo = date(anno, mese, 1)
    ultimo = date(anno, mese, calendar.monthrange(anno, mese)[1])
    return max(primo, oggi + timedelta(days=1)), ultimo


def _combinazione_piu_economica(
    notti: int,
    voli_andata: list[Volo],
    ritorni: dict[tuple[str, date], Volo],
    hotel_citta: list[Hotel],
) -> Combinazione | None:
    """Tra tutte le combinazioni con esattamente `notti` notti, quella che costa meno.

    Il ritorno deve partire dalla destinazione ed atterrare nello stesso aeroporto da
    cui si è partiti, `notti` giorni dopo l'andata. L'hotel deve essere disponibile per
    tutto il soggiorno.
    """
    migliore = None
    for andata in voli_andata:
        ritorno = ritorni.get((andata.aeroporto_partenza, andata.data + timedelta(days=notti)))
        if ritorno is None:
            continue
        hotel_liberi = [
            h for h in hotel_citta
            if h.disponibile_da <= andata.data and h.disponibile_a >= ritorno.data
        ]
        if not hotel_liberi:
            continue
        hotel = min(hotel_liberi, key=lambda h: h.costo_per_notte)
        costo = andata.costo + ritorno.costo + notti * hotel.costo_per_notte
        if migliore is None or costo < migliore.costo:
            migliore = Combinazione(andata, ritorno, hotel, notti, costo)
    return migliore


def _costo_minimo_attivita(costi: list[float], quante: int) -> float:
    """Costo delle `quante` attività più economiche: il minimo indispensabile per
    riempire quei giorni, dato che ogni attività si usa una volta sola."""
    return sum(sorted(costi)[:quante])


def _ordina_attivita(citta: str, preferenze: list[str], attivita: list[Attivita]) -> list[Attivita]:
    """Attività dalla più alla meno adatta alle preferenze (RAG). Quelle che la ricerca
    non classifica, o tutte se non ci sono preferenze, vanno in ordine di prezzo."""
    posizione = {id_: i for i, id_ in enumerate(cerca_attivita(citta, preferenze))}
    fuori_classifica = len(posizione)
    return sorted(attivita, key=lambda a: (posizione.get(a.id, fuori_classifica), a.costo))


def genera_itinerario(
    db: Session, richiesta: RichiestaViaggio, oggi: date | None = None
) -> ItinerarioOut:
    mancanti = [
        nome for nome, valore in
        [("budget", richiesta.budget), ("nazione", richiesta.nazione), ("periodo", richiesta.periodo)]
        if not valore
    ]
    if mancanti:
        raise ValueError("Dati mancanti per generare l'itinerario: " + ", ".join(mancanti))

    oggi = oggi or date.today()
    destinazione = trova_destinazione(richiesta.nazione)
    if destinazione is None:
        raise ItinerarioNonTrovato(
            f"Non ho destinazioni disponibili per '{richiesta.nazione}'. "
            f"Posso proporti: {', '.join(nazioni_disponibili())}."
        )
    inizio, fine = finestra_periodo(richiesta.periodo, oggi)
    citta, aeroporto = destinazione["citta"], destinazione["aeroporto"]

    voli_andata = db.query(Volo).filter(
        Volo.aeroporto_arrivo == aeroporto, Volo.data.between(inizio, fine)
    ).all()
    voli_ritorno = db.query(Volo).filter(
        Volo.aeroporto_partenza == aeroporto,
        Volo.data.between(inizio + timedelta(days=NOTTI_MIN), fine + timedelta(days=NOTTI_MAX)),
    ).all()
    hotel_citta = db.query(Hotel).filter(Hotel.citta == citta).all()
    attivita_citta = db.query(Attivita).filter(Attivita.citta == citta).all()

    # Indice dei ritorni per (aeroporto di arrivo, data), tenendo il più economico:
    # trovare il ritorno giusto per un'andata diventa una ricerca diretta, non un ciclo.
    ritorni: dict[tuple[str, date], Volo] = {}
    for volo in voli_ritorno:
        chiave = (volo.aeroporto_arrivo, volo.data)
        if chiave not in ritorni or volo.costo < ritorni[chiave].costo:
            ritorni[chiave] = volo

    # Si prova prima la durata più lunga e si scende solo se il budget non basta.
    # La combinazione scelta è la più economica di quella durata: il budget è un tetto,
    # non una cifra da spendere tutta. Oltre a voli e hotel si tiene da parte il costo delle
    # attività più economiche della città: senza, si potrebbe spendere tutto in voli e hotel
    # e non poter più riempire i giorni.
    costi_attivita = [a.costo for a in attivita_citta]
    scelta = None
    minimo_necessario = None
    for notti in range(NOTTI_MAX, NOTTI_MIN - 1, -1):
        combinazione = _combinazione_piu_economica(notti, voli_andata, ritorni, hotel_citta)
        if combinazione is None:
            continue
        necessario = combinazione.costo + _costo_minimo_attivita(costi_attivita, notti)
        if minimo_necessario is None or necessario < minimo_necessario:
            minimo_necessario = necessario
        if necessario <= richiesta.budget:
            scelta = combinazione
            break

    if scelta is None:
        if minimo_necessario is None:
            raise ItinerarioNonTrovato(
                f"Non trovo voli e hotel disponibili per {destinazione['nazione']} a {richiesta.periodo}."
            )
        raise ItinerarioNonTrovato(
            f"Con {richiesta.budget:.0f} € non riesco a comporre il viaggio: per "
            f"{destinazione['nazione']} a {richiesta.periodo} servono almeno circa "
            f"{minimo_necessario:.0f} € tra voli, hotel e attività."
        )

    # Una attività per ogni notte del soggiorno, la più adatta tra quelle disponibili quel
    # giorno e sostenibili col budget rimasto. Dopo ogni scelta devono restare i soldi per le
    # attività più economiche ancora libere, così le prime scelte (le più adatte, ma magari
    # care) non lasciano gli ultimi giorni vuoti.
    ordinate = _ordina_attivita(citta, richiesta.preferenze, attivita_citta)
    giorni_viaggio = [scelta.andata.data + timedelta(days=i) for i in range(scelta.notti)]
    budget_residuo = richiesta.budget - scelta.costo
    usate: set[int] = set()
    giorni: list[GiornoOut] = []
    avvisi: list[str] = []
    costo_attivita = 0.0

    for indice, giorno in enumerate(giorni_viaggio):
        giorni_restanti = len(giorni_viaggio) - indice - 1
        attivita = next(
            (
                a for a in ordinate
                if a.id not in usate
                and a.disponibile_da <= giorno <= a.disponibile_a
                and a.costo + _costo_minimo_attivita(
                    [b.costo for b in attivita_citta if b.id not in usate and b.id != a.id],
                    giorni_restanti,
                ) <= budget_residuo
            ),
            None,
        )
        if attivita is None:
            avvisi.append(f"Nessuna attività disponibile entro il budget per il {giorno:%d/%m/%Y}.")
            giorni.append(GiornoOut(giorno=giorno))
            continue
        usate.add(attivita.id)
        budget_residuo -= attivita.costo
        costo_attivita += attivita.costo
        giorni.append(GiornoOut(giorno=giorno, attivita=AttivitaOut.model_validate(attivita)))

    costo_voli = round(scelta.andata.costo + scelta.ritorno.costo, 2)
    costo_hotel = round(scelta.notti * scelta.hotel.costo_per_notte, 2)
    costo_attivita = round(costo_attivita, 2)
    return ItinerarioOut(
        nazione=destinazione["nazione"],
        citta=citta,
        notti=scelta.notti,
        volo_andata=VoloOut.model_validate(scelta.andata),
        volo_ritorno=VoloOut.model_validate(scelta.ritorno),
        hotel=HotelOut.model_validate(scelta.hotel),
        giorni=giorni,
        costo_voli=costo_voli,
        costo_hotel=costo_hotel,
        costo_attivita=costo_attivita,
        costo_totale=round(costo_voli + costo_hotel + costo_attivita, 2),
        budget=richiesta.budget,
        avvisi=avvisi,
    )