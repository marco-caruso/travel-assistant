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

from app.db.models import Attivita, Base, Hotel, Utente, Volo  # noqa: E402

fake = Faker("it_IT")

DESTINAZIONI = ["Parigi", "Barcellona", "Atene", "Tokyo", "New York"]

AEROPORTI_PARTENZA = ["CAG", "FCO", "MXP"]
AEROPORTI_ARRIVO = {
    "Parigi": "CDG", "Barcellona": "BCN", "Atene": "ATH",
    "Tokyo": "NRT", "New York": "JFK",
}

NOMI_ATTIVITA = [
    "Tour guidato del centro storico", "Escursione in montagna",
    "Serata in un locale con musica dal vivo", "Giornata di relax alle terme",
    "Visita a un museo d'arte", "Lezione di cucina locale",
    "Escursione in bicicletta", "Crociera serale",
]


def data_casuale_entro_un_anno() -> date:
    return date.today() + timedelta(days=random.randint(1, 365))


def crea_dati(session: Session) -> None:
    for _ in range(3):
        session.add(Utente(
            nome=fake.name(),
            email=fake.unique.email(),
            password_hash="placeholder",  # la gestiamo quando scriviamo l'autenticazione
        ))

    for citta in DESTINAZIONI:
        aeroporto_arrivo = AEROPORTI_ARRIVO[citta]

        for _ in range(6):
            session.add(Volo(
                aeroporto_partenza=random.choice(AEROPORTI_PARTENZA),
                aeroporto_arrivo=aeroporto_arrivo,
                data=data_casuale_entro_un_anno(),
                costo=round(random.uniform(80, 600), 2),
            ))

        for _ in range(4):
            disponibile_da = data_casuale_entro_un_anno()
            disponibile_a = disponibile_da + timedelta(days=random.randint(30, 90))
            session.add(Hotel(
                nome=f"Hotel {fake.last_name()}",
                citta=citta,
                costo_per_notte=round(random.uniform(40, 300), 2),
                disponibile_da=disponibile_da,
                disponibile_a=disponibile_a,
            ))

        for nome_attivita in random.sample(NOMI_ATTIVITA, 5):
            session.add(Attivita(
                nome=nome_attivita,
                citta=citta,
                costo=round(random.uniform(10, 150), 2),
                data_disponibile=data_casuale_entro_un_anno(),
            ))

    session.commit()


def main() -> None:
    db_path = ROOT_DIR / "data" / "travel.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        crea_dati(session)

    print(f"Database popolato con dati finti in {db_path}")


if __name__ == "__main__":
    main()