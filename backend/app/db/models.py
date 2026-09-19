from datetime import date

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Classe base da cui erediteranno tutte le tabelle."""
    pass


class Utente(Base):
    __tablename__ = "utenti"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    prenotazioni: Mapped[list["Prenotazione"]] = relationship(back_populates="utente")


class Volo(Base):
    __tablename__ = "voli"

    id: Mapped[int] = mapped_column(primary_key=True)
    aeroporto_partenza: Mapped[str] = mapped_column(String(10))
    aeroporto_arrivo: Mapped[str] = mapped_column(String(10))
    data: Mapped[date]
    costo: Mapped[float]


class Hotel(Base):
    __tablename__ = "hotel"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    citta: Mapped[str] = mapped_column(String(100))
    costo_per_notte: Mapped[float]
    disponibile_da: Mapped[date]
    disponibile_a: Mapped[date]


class Attivita(Base):
    __tablename__ = "attivita"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    citta: Mapped[str] = mapped_column(String(100))
    costo: Mapped[float]
    # Intervallo di disponibilità (come per gli hotel), non una data singola:
    # una data sola renderebbe quasi impossibile trovare un'attività per ogni giorno.
    disponibile_da: Mapped[date]
    disponibile_a: Mapped[date]


class Prenotazione(Base):
    __tablename__ = "prenotazioni"

    id: Mapped[int] = mapped_column(primary_key=True)
    utente_id: Mapped[int] = mapped_column(ForeignKey("utenti.id"))
    # Due chiavi verso la stessa tabella "voli": andata e ritorno.
    volo_andata_id: Mapped[int] = mapped_column(ForeignKey("voli.id"))
    volo_ritorno_id: Mapped[int] = mapped_column(ForeignKey("voli.id"))
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"))
    stato: Mapped[str] = mapped_column(String(20), default="in_attesa")
    data_da: Mapped[date]
    data_a: Mapped[date]
    costo_totale: Mapped[float]

    utente: Mapped["Utente"] = relationship(back_populates="prenotazioni")
    # Con due FK verso la stessa tabella SQLAlchemy non sa quale usare:
    # foreign_keys lo dice esplicitamente per ogni relationship.
    volo_andata: Mapped["Volo"] = relationship(foreign_keys=[volo_andata_id])
    volo_ritorno: Mapped["Volo"] = relationship(foreign_keys=[volo_ritorno_id])
    hotel: Mapped["Hotel"] = relationship()
    attivita: Mapped[list["PrenotazioneAttivita"]] = relationship(back_populates="prenotazione")


class PrenotazioneAttivita(Base):
    """Tabella ponte: collega una prenotazione a più attività, ciascuna con il suo giorno."""
    __tablename__ = "prenotazione_attivita"

    id: Mapped[int] = mapped_column(primary_key=True)
    prenotazione_id: Mapped[int] = mapped_column(ForeignKey("prenotazioni.id"))
    attivita_id: Mapped[int] = mapped_column(ForeignKey("attivita.id"))
    giorno: Mapped[date]

    prenotazione: Mapped["Prenotazione"] = relationship(back_populates="attivita")
    attivita_ref: Mapped["Attivita"] = relationship()