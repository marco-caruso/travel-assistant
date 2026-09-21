"""
Gestione sicura delle password.

Non si salva mai la password: si salva il suo "hash", cioè il risultato di una funzione
a senso unico da cui non si torna indietro. Per controllare un login si ricalcola l'hash
della password inserita e lo si confronta con quello salvato.

Usiamo scrypt, presente nella libreria standard di Python (nessuna dipendenza da
installare): è una funzione pensata per le password, volutamente lenta e "pesante" in
memoria, così provare milioni di password diventa costoso. Ogni utente ha un "salt"
casuale, così due utenti con la stessa password hanno hash diversi.
"""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from dotenv import load_dotenv


# Parametri di costo di scrypt: valori standard raccomandati per un uso interattivo
_N, _R, _P = 2**14, 8, 1


def _calcola_hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=32)


def hash_password(password: str) -> str:
    """Ritorna una stringa 'scrypt$<salt>$<hash>' da salvare nel database."""
    salt = secrets.token_bytes(16)
    return f"scrypt${salt.hex()}${_calcola_hash(password, salt).hex()}"


def verifica_password(password: str, salvato: str) -> bool:
    try:
        schema, salt_hex, hash_hex = salvato.split("$")
        if schema != "scrypt":
            return False
        atteso = bytes.fromhex(hash_hex)
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False  # formato non riconosciuto (es. il "placeholder" dei dati di prova)
    # compare_digest confronta in tempo costante: non rivela quanti caratteri coincidono
    return hmac.compare_digest(_calcola_hash(password, salt), atteso)



# ---------------------------------------------------------------------------
# Token di accesso (JWT)
#
# Dopo il login il server consegna un "gettone" firmato. Il client lo rimanda in ogni
# richiesta protetta (header "Authorization: Bearer <token>"): il server non deve
# ricordare chi ha fatto login (niente sessioni in memoria), gli basta controllare la firma.
# Dentro il token ci sono: "sub" (id dell'utente), "iat" (emesso il) ed "exp" (scade il).
# Il token è firmato, NON cifrato: chiunque può leggerne il contenuto, ma nessuno può
# modificarlo senza conoscere la chiave segreta. Per questo non ci si mette mai la password.
# ---------------------------------------------------------------------------
load_dotenv()

ALGORITMO = "HS256"   # firma simmetrica: la stessa chiave firma e verifica
ORE_VALIDITA = 8      # niente refresh token: scaduto, si rifà il login


class TokenNonValido(Exception):
    """Token scaduto, manomesso o malformato. Il messaggio è mostrabile all'utente."""


def _chiave_segreta() -> str:
    chiave = os.getenv("JWT_SECRET")
    if not chiave:
        # Meglio fermarsi che usare una chiave di ripiego: con una chiave nota a tutti
        # chiunque potrebbe fabbricarsi un token valido.
        raise RuntimeError("JWT_SECRET non impostata: aggiungila al file .env (vedi .env.example).")
    return chiave


def crea_token(utente_id: int) -> str:
    adesso = datetime.now(timezone.utc)
    payload = {
        "sub": str(utente_id),  # lo standard JWT vuole una stringa
        "iat": adesso,
        "exp": adesso + timedelta(hours=ORE_VALIDITA),
    }
    return jwt.encode(payload, _chiave_segreta(), algorithm=ALGORITMO)


def leggi_token(token: str) -> int:
    """Ritorna l'id utente contenuto nel token, oppure solleva TokenNonValido."""
    try:
        # algorithms=[...] è obbligatorio: senza, un attaccante potrebbe dichiarare
        # nel token un algoritmo più debole (o "none") e farsi accettare.
        payload = jwt.decode(
            token, _chiave_segreta(), algorithms=[ALGORITMO], options={"require": ["exp", "sub"]}
        )
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise TokenNonValido("Sessione scaduta: accedi di nuovo.")
    except (jwt.InvalidTokenError, ValueError):
        raise TokenNonValido("Token non valido.")