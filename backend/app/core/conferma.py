"""
Riconoscimento di "sì, prenota" e "no, lascia stare" nell'ultimo messaggio dell'utente.

Prenotare è l'unica azione della chat con conseguenze, quindi qui si sceglie la prudenza:
un messaggio conta come conferma SOLO se ogni sua parola è una parola di conferma o una
parola neutra ("sì", "ok, prenota pure", "va bene, procedi"). Se c'è anche una sola parola
sconosciuta ("sì, ma costa troppo", "no, prenota a giugno") NON è una conferma, e la chat
prosegue normalmente (nuova estrazione, nuova proposta). L'errore possibile è quindi solo
"non ho capito la conferma, riscrivila", mai una prenotazione fatta per sbaglio.

Nessun modello linguistico: è codice deterministico e testabile. In produzione si potrebbe
usare un LLM per classificare l'intento, tenendo però lo stesso principio: nel dubbio non
si prenota
"""
import re
import unicodedata

CONFERMA = {
    "si", "ok", "okay", "certo", "conferma", "confermo", "confermiamo", "prenota", "prenotalo",
    "prenotiamo", "prenotami", "procedi", "perfetto", "vai", "benissimo", "volentieri", "bene",
    "d", "accordo",
}
RIFIUTO = {"no", "non", "annulla", "basta", "stop", "lascia", "perdere", "nulla", "niente"}

# Parole che non cambiano il senso: si accettano in entrambi i casi
NEUTRE = {
    "pure", "grazie", "va", "il", "lo", "la", "l", "viaggio", "itinerario", "questo", "e", "per",
    "favore", "adesso", "ora", "subito", "allora", "dai", "proprio", "mi", "piace", "voglio",
    "prenotare", "prenotarlo", "prenoto", "piu", "ancora", "di", "ho", "cambiato", "idea",
    "interessa",
}


def _parole(testo: str) -> list[str]:
    # minuscolo e senza accenti: "Sì" e "si" sono la stessa parola
    senza_accenti = "".join(
        c for c in unicodedata.normalize("NFD", testo.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.findall(r"[a-z]+", senza_accenti)


def e_conferma(testo: str) -> bool:
    parole = _parole(testo)
    return (
        bool(parole)
        and any(p in CONFERMA for p in parole)
        and all(p in CONFERMA or p in NEUTRE for p in parole)
    )


def e_rifiuto(testo: str) -> bool:
    parole = _parole(testo)
    return (
        bool(parole)
        and any(p in RIFIUTO for p in parole)
        and all(p in RIFIUTO or p in NEUTRE for p in parole)
    )