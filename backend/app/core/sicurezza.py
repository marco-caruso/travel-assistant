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
import secrets

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