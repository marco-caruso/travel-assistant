"""
Popola il database con dati sintetici.

ATTENZIONE: ogni esecuzione cancella e ricrea tutte le tabelle (utenti e
prenotazioni compresi). Serve per avere sempre uno schema aggiornato e dati coerenti.

I dati sono generati partendo da ciò che la generazione degli itinerari deve poter
trovare: voli di andata E ritorno su molte date, hotel disponibili per finestre
lunghe, attività disponibili per lunghi periodi. Con date casuali e sparse non si
riuscirebbe mai a comporre un itinerario completo.
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.destinazioni import AEROPORTI_PARTENZA, DESTINAZIONI  # noqa: E402
from app.db.models import Attivita, Base, Hotel, Utente, Volo  # noqa: E402

SEED_CASUALE = 42  # stessi dati a ogni esecuzione: risultati riproducibili
random.seed(SEED_CASUALE)
Faker.seed(SEED_CASUALE)
fake = Faker("it_IT")

GIORNI_COPERTURA = 400  # i voli coprono i prossimi ~13 mesi
PROBABILITA_VOLO = 0.35  # probabilità che in un dato giorno ci sia un volo (per direzione)

# Intervallo di prezzo di un volo (euro): i voli intercontinentali costano di più
COSTO_VOLO = {
    "Parigi": (40, 250),
    "Barcellona": (40, 250),
    "Atene": (50, 300),
    "Tokyo": (500, 1100),
    "New York": (400, 900),
}

# Attività specifiche per città: nomi coerenti con i luoghi reali, altrimenti il modello
# che genera le descrizioni inventa cose senza senso (es. "montagne parigine").
# Ogni città ha lo stesso mix (cultura, natura/sport, relax, nightlife), così le preferenze
# dell'utente trovano corrispondenze in qualunque destinazione. Altre 7 per città sono più sotto.
ATTIVITA_PER_CITTA = {
    "Parigi": [
        "Visita al Museo del Louvre",
        "Tour guidato di Montmartre",
        "Giro in bicicletta lungo la Senna",
        "Giornata nei giardini della Reggia di Versailles",
        "Crociera serale sulla Senna",
        "Pomeriggio di relax in una spa del centro",
        "Serata di cabaret a Pigalle",
        "Lezione di cucina francese",
    ],
    "Barcellona": [
        "Visita alla Sagrada Família e alle opere di Gaudí",
        "Escursione al monastero di Montserrat",
        "Giro in bicicletta sul lungomare",
        "Giornata in spiaggia alla Barceloneta",
        "Crociera al tramonto lungo la costa",
        "Serata di flamenco e tapas nel Born",
        "Visita al Museo Picasso",
        "Lezione di cucina catalana",
    ],
    "Atene": [
        "Visita all'Acropoli e al Partenone",
        "Visita al Museo Archeologico Nazionale",
        "Escursione sul colle del Licabetto",
        "Gita al tempio di Capo Sounion al tramonto",
        "Crociera giornaliera alle isole del Golfo Saronico",
        "Giornata di relax al lago termale di Vouliagmeni",
        "Serata di musica dal vivo nel quartiere di Psyrri",
        "Lezione di cucina greca",
    ],
    "Tokyo": [
        "Tour guidato di Asakusa e del tempio Senso-ji",
        "Visita al Museo Nazionale di Tokyo",
        "Escursione sul monte Takao",
        "Giro in bicicletta intorno al Palazzo Imperiale",
        "Giornata di relax in un onsen tradizionale",
        "Crociera serale nella baia di Tokyo",
        "Serata tra izakaya e karaoke a Shinjuku",
        "Lezione di cucina giapponese",
    ],
    "New York": [
        "Visita al Metropolitan Museum of Art",
        "Tour di Lower Manhattan e della Statua della Libertà",
        "Giro in bicicletta a Central Park",
        "Passeggiata sulla High Line e a Hudson River Park",
        "Crociera serale sull'Hudson",
        "Giornata di relax in una spa di Manhattan",
        "Serata jazz in un club del Greenwich Village",
        "Tour gastronomico a Brooklyn",
    ],
}


# Attività aggiuntive (7 per città, 15 in totale con quelle sopra). Il catalogo deve essere
# molto più grande del numero di giorni da riempire (3-5): con poche attività entrerebbero
# quasi tutte qualunque siano le preferenze, e la ricerca semantica non farebbe differenza.
ATTIVITA_EXTRA_PER_CITTA = {
    "Parigi": [
        "Visita al Museo d'Orsay",
        "Visita alle Catacombe di Parigi",
        "Passeggiata nel Bois de Boulogne",
        "Corsa guidata lungo il Canal Saint-Martin",
        "Escursione in canoa sulla Marna",
        "Percorso in un hammam tradizionale con massaggio",
        "Serata in un jazz club di Saint-Germain",
    ],
    "Barcellona": [
        "Visita a Casa Batlló e Casa Milà",
        "Tour del Barri Gòtic",
        "Passeggiata nel Parc Güell",
        "Giro in kayak lungo la costa di Barcellona",
        "Escursione in e-bike sulla collina del Montjuïc",
        "Pomeriggio di relax in un centro termale del centro storico",
        "Serata di musica elettronica in un club sul lungomare",
    ],
    "Atene": [
        "Visita all'Agorà antica e al Tempio di Efesto",
        "Visita al Museo dell'Acropoli",
        "Passeggiata nel Giardino Nazionale",
        "Lezione di windsurf sulla riviera di Atene",
        "Gita in barca a vela lungo la riviera ateniese",
        "Percorso spa e massaggio in un centro benessere di Kolonaki",
        "Serata in una taverna con musica greca dal vivo a Plaka",
    ],
    "Tokyo": [
        "Visita al tempio Meiji e ai suoi giardini",
        "Tour dei quartieri di Akihabara e della cultura pop",
        "Passeggiata nel parco di Ueno",
        "Lezione di judo in un dojo tradizionale",
        "Gita in giornata ai laghi del monte Fuji",
        "Cerimonia del tè in una sala tradizionale",
        "Serata nei piccoli bar di Golden Gai",
    ],
    "New York": [
        "Visita al Museo di Storia Naturale",
        "Visita al MoMA",
        "Passeggiata nel Prospect Park a Brooklyn",
        "Lezione di boxe in una palestra di Brooklyn",
        "Escursione in kayak sull'Hudson",
        "Lezione di yoga all'aperto a Bryant Park",
        "Serata di stand-up comedy in un club del Lower East Side",
    ],
}


def crea_voli(session: Session, oggi: date, citta: str, aeroporto_arrivo: str) -> None:
    """Per ogni aeroporto di partenza crea voli di andata e di ritorno su giorni casuali."""
    costo_min, costo_max = COSTO_VOLO[citta]
    for aeroporto_partenza in AEROPORTI_PARTENZA:
        for giorno in range(1, GIORNI_COPERTURA):
            data_volo = oggi + timedelta(days=giorno)
            if random.random() < PROBABILITA_VOLO:  # andata
                session.add(Volo(
                    aeroporto_partenza=aeroporto_partenza,
                    aeroporto_arrivo=aeroporto_arrivo,
                    data=data_volo,
                    costo=round(random.uniform(costo_min, costo_max), 2),
                ))
            if random.random() < PROBABILITA_VOLO:  # ritorno (verso opposto)
                session.add(Volo(
                    aeroporto_partenza=aeroporto_arrivo,
                    aeroporto_arrivo=aeroporto_partenza,
                    data=data_volo,
                    costo=round(random.uniform(costo_min, costo_max), 2),
                ))


def crea_dati(session: Session) -> None:
    oggi = date.today()

    for _ in range(3):
        session.add(Utente(
            nome=fake.name(),
            email=fake.unique.email(),
            password_hash="placeholder",  # utenti di esempio: nessuno può accedere, ci si registra dall'app
        ))

    for destinazione in DESTINAZIONI.values():
        citta = destinazione["citta"]

        crea_voli(session, oggi, citta, destinazione["aeroporto"])

        # Hotel: il primo è disponibile per tutto l'orizzonte dei voli (così ogni mese
        # ha almeno un hotel); gli altri hanno finestre più corte e sfalsate, per varietà
        for i in range(4):
            if i == 0:
                disponibile_da = oggi
                disponibile_a = oggi + timedelta(days=GIORNI_COPERTURA)
            else:
                disponibile_da = oggi + timedelta(days=random.randint(0, 30))
                disponibile_a = disponibile_da + timedelta(days=random.randint(250, 380))
            session.add(Hotel(
                nome=f"Hotel {fake.last_name()}",
                citta=citta,
                costo_per_notte=round(random.uniform(40, 300), 2),
                disponibile_da=disponibile_da,
                disponibile_a=disponibile_a,
            ))

        # Attività: le prime 8 della città, disponibili quasi per tutto l'orizzonte dei voli
        for nome_attivita in ATTIVITA_PER_CITTA[citta]:
            disponibile_da = oggi + timedelta(days=random.randint(0, 5))
            disponibile_a = oggi + timedelta(days=random.randint(GIORNI_COPERTURA - 30, GIORNI_COPERTURA))
            session.add(Attivita(
                nome=nome_attivita,
                citta=citta,
                costo=round(random.uniform(10, 150), 2),
                disponibile_da=disponibile_da,
                disponibile_a=disponibile_a,
            ))

    # Attività aggiuntive: create per ultime e con un generatore casuale a parte, così
    # aggiungerle non cambia voli, hotel e le prime 40 attività (id 1-40 restano gli stessi).
    rng_extra = random.Random(SEED_CASUALE + 1)
    for destinazione in DESTINAZIONI.values():
        citta = destinazione["citta"]
        for nome_attivita in ATTIVITA_EXTRA_PER_CITTA[citta]:
            disponibile_da = oggi + timedelta(days=rng_extra.randint(0, 5))
            disponibile_a = oggi + timedelta(days=rng_extra.randint(GIORNI_COPERTURA - 30, GIORNI_COPERTURA))
            session.add(Attivita(
                nome=nome_attivita,
                citta=citta,
                costo=round(rng_extra.uniform(10, 150), 2),
                disponibile_da=disponibile_da,
                disponibile_a=disponibile_a,
            ))

    session.commit()


def main() -> None:
    db_path = ROOT_DIR / "data" / "travel.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        crea_dati(session)

    print(f"Database popolato con dati finti in {db_path}")


if __name__ == "__main__":
    main()