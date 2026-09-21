"""
Frontend Streamlit: registrazione e login, chat con l'assistente, elenco delle prenotazioni.

Parla solo con l'API REST del backend (non tocca mai il database). Il token di accesso
vive in st.session_state: se ricarichi la pagina del browser si perde e si rifà il login
(limite noto: per conservarlo servirebbero i cookie).

Avvio, dalla radice del progetto (con il backend già acceso):
    uv run streamlit run frontend/app.py
"""
import os
from datetime import date

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
SALUTO = (
    "Ciao! Sono il tuo assistente di viaggio. Dimmi dove vorresti andare, in che mese, "
    "che attività ti piacciono e qual è il tuo budget."
)

st.set_page_config(page_title="Assistente di viaggio", layout="centered")


# ---------------------------------------------------------------------------
# Stato e chiamate all'API
# ---------------------------------------------------------------------------
def inizializza():
    st.session_state.setdefault("token", None)     # token JWT ricevuto al login
    st.session_state.setdefault("utente", None)    # {"id", "nome", "email"}
    st.session_state.setdefault("messaggi", [])    # storico: {"role", "content", "itinerario"?}
    st.session_state.setdefault("proposta", None)  # id della proposta in attesa di conferma
    st.session_state.setdefault("avviso", None)    # messaggio da mostrare nella schermata di accesso
    st.session_state.setdefault("esito", None)     # messaggio dopo una prenotazione riuscita


def esci(avviso: str | None = None):
    for chiave in ("token", "utente", "messaggi", "proposta", "esito"):
        st.session_state.pop(chiave, None)
    st.session_state.avviso = avviso
    st.rerun()


def chiama(metodo: str, percorso: str, **kwargs) -> requests.Response:
    """Unico punto da cui si chiama il backend: aggiunge il token e gestisce gli errori comuni."""
    token = st.session_state.token
    intestazioni = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        risposta = requests.request(
            metodo, API_URL + percorso, headers=intestazioni, timeout=60, **kwargs
        )
    except requests.RequestException:
        st.error(
            "Non riesco a contattare il server. Controlla che il backend sia acceso "
            "(uvicorn app.main:app --reload, dalla cartella backend)."
        )
        st.stop()
    if risposta.status_code == 401 and token:
        esci("Sessione scaduta: accedi di nuovo.")  # token scaduto o non più valido
    return risposta


def dettaglio(risposta: requests.Response) -> str:
    try:
        d = risposta.json().get("detail")
    except ValueError:
        d = None
    return d if isinstance(d, str) else "Richiesta non valida."


def data_it(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


# ---------------------------------------------------------------------------
# Accesso e registrazione
# ---------------------------------------------------------------------------
def accedi(email: str, password: str):
    risposta = chiama("POST", "/auth/login", json={"email": email, "password": password})
    if risposta.status_code != 200:
        st.error(dettaglio(risposta))
        return
    st.session_state.token = risposta.json()["access_token"]
    st.session_state.utente = chiama("GET", "/auth/me").json()
    st.rerun()


def registra(nome: str, email: str, password: str):
    risposta = chiama(
        "POST", "/auth/registrazione", json={"nome": nome, "email": email, "password": password}
    )
    if risposta.status_code == 201:
        accedi(email, password)
    elif risposta.status_code == 409:
        st.error(dettaglio(risposta))
    else:
        st.error("Dati non validi: controlla l'email e usa una password di almeno 8 caratteri.")


def schermata_accesso():
    st.title("Assistente di viaggio")
    if st.session_state.avviso:
        st.warning(st.session_state.avviso)
        st.session_state.avviso = None
    tab_accedi, tab_registrati = st.tabs(["Accedi", "Registrati"])
    with tab_accedi:
        with st.form("form_accesso"):
            email = st.text_input("Email", key="email_accesso")
            password = st.text_input("Password", type="password", key="password_accesso")
            invia = st.form_submit_button("Accedi")
        if invia:
            accedi(email, password)
    with tab_registrati:
        with st.form("form_registrazione"):
            nome = st.text_input("Nome", key="nome_registrazione")
            email = st.text_input("Email", key="email_registrazione")
            password = st.text_input(
                "Password (almeno 8 caratteri)", type="password", key="password_registrazione"
            )
            invia = st.form_submit_button("Crea account")
        if invia:
            registra(nome, email, password)


# ---------------------------------------------------------------------------
# Visualizzazione di un viaggio (usata sia per le proposte sia per le prenotazioni)
# ---------------------------------------------------------------------------
def mostra_viaggio(volo_andata: dict, volo_ritorno: dict, hotel: dict, giorni: list[tuple]):
    """giorni: lista di (data ISO, attività o None)."""
    for etichetta, volo in (("Andata", volo_andata), ("Ritorno", volo_ritorno)):
        st.markdown(
            f"**{etichetta}** {data_it(volo['data'])}: {volo['aeroporto_partenza']} → "
            f"{volo['aeroporto_arrivo']} ({volo['costo']:.2f} €)"
        )
    st.markdown(
        f"**Hotel** {hotel['nome']} ({hotel['citta']}): {hotel['costo_per_notte']:.2f} € a notte"
    )
    st.markdown("**Attività**")
    for giorno, attivita in sorted(giorni, key=lambda g: g[0]):
        if attivita:
            st.markdown(f"- {data_it(giorno)}: {attivita['nome']} ({attivita['costo']:.2f} €)")
        else:
            st.markdown(f"- {data_it(giorno)}: nessuna attività disponibile")


def mostra_itinerario(it: dict):
    colonne = st.columns(4)
    colonne[0].metric("Totale", f"{it['costo_totale']:.2f} €")
    colonne[1].metric("Voli", f"{it['costo_voli']:.2f} €")
    colonne[2].metric("Hotel", f"{it['costo_hotel']:.2f} €")
    colonne[3].metric("Attività", f"{it['costo_attivita']:.2f} €")
    st.caption(f"Budget indicato: {it['budget']:.2f} €")
    giorni = [(g["giorno"], g["attivita"]) for g in it["giorni"]]
    mostra_viaggio(it["volo_andata"], it["volo_ritorno"], it["hotel"], giorni)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
def nuova_conversazione(esito: str | None = None):
    """Dopo una prenotazione si riparte da zero: altrimenti l'estrazione dei dati
    riaggregherebbe quelli del viaggio appena prenotato."""
    st.session_state.messaggi = []
    st.session_state.proposta = None
    st.session_state.esito = esito


def invia_messaggio(testo: str):
    st.session_state.messaggi.append({"role": "user", "content": testo})
    with st.chat_message("user"):
        st.write(testo)
    # Al server vanno solo ruolo e testo: gli itinerari servono solo per mostrarli qui
    storico = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messaggi]
    with st.chat_message("assistant"):
        with st.spinner("Sto pensando..."):
            risposta = chiama(
                "POST", "/chat", json={"messaggi": storico, "proposta": st.session_state.proposta}
            )
    if risposta.status_code != 200:
        st.session_state.messaggi.pop()  # messaggio non elaborato: si può riscrivere
        st.error(dettaglio(risposta))
        return
    dati = risposta.json()
    if dati.get("prenotazione"):
        nuova_conversazione(esito=dati["risposta"])
    else:
        st.session_state.messaggi.append(
            {"role": "assistant", "content": dati["risposta"], "itinerario": dati.get("itinerario")}
        )
        st.session_state.proposta = dati.get("proposta")  # None se non c'è una proposta in attesa
    st.rerun()


def prenota_con_pulsante():
    risposta = chiama("POST", "/prenotazioni", json=st.session_state.proposta)
    if risposta.status_code == 201:
        p = risposta.json()
        nuova_conversazione(
            f"Prenotazione confermata (codice {p['id']}): {p['hotel']['citta']}, dal "
            f"{data_it(p['data_da'])} al {data_it(p['data_a'])}, totale {p['costo_totale']:.2f} €. "
            "La trovi in «Le mie prenotazioni»."
        )
        st.rerun()
    elif risposta.status_code in (409, 422):
        st.error(dettaglio(risposta))
    else:
        st.error("Non è stato possibile prenotare. Riprova.")


def annulla_proposta():
    """Rifiuto esplicito. La proposta esiste solo nel client (il server non tiene stato),
    quindi per annullarla basta azzerarla."""
    st.session_state.proposta = None
    st.session_state.messaggi.append({
        "role": "assistant",
        "content": "Va bene, non prenoto. Se vuoi, dimmi cosa cambiare (nazione, mese, "
        "attività o budget) e preparo un'altra proposta.",
    })
    st.rerun()


def mostra_destinazioni():
    """Riga sempre visibile sotto il titolo: le destinazioni offerte, lette dal backend."""
    risposta = chiama("GET", "/destinazioni")
    if risposta.status_code == 200:
        elenco = ", ".join(f"{d['nazione']} ({d['citta']})" for d in risposta.json())
        st.caption(f"Destinazioni disponibili: {elenco}")


def pagina_chat():
    st.header("Chat con l'assistente")
    mostra_destinazioni()
    if st.session_state.esito:
        st.success(st.session_state.esito)
    messaggi = st.session_state.messaggi
    if not messaggi:
        with st.chat_message("assistant"):
            st.write(SALUTO)  # solo a video: la conversazione inviata al server inizia dall'utente
    for i, m in enumerate(messaggi):
        with st.chat_message(m["role"]):
            st.write(m["content"])
            if m.get("itinerario"):
                with st.expander("Dettagli dell'itinerario", expanded=(i == len(messaggi) - 1)):
                    mostra_itinerario(m["itinerario"])
    if st.session_state.proposta:
        col_prenota, col_annulla, _ = st.columns([2, 2, 3])
        if col_prenota.button("Prenota questo itinerario", type="primary"):
            prenota_con_pulsante()
        if col_annulla.button("Non prenotare"):
            annulla_proposta()
    testo = st.chat_input("Scrivi qui il tuo messaggio")
    if testo:
        st.session_state.esito = None
        invia_messaggio(testo)


# ---------------------------------------------------------------------------
# Elenco delle prenotazioni
# ---------------------------------------------------------------------------
def pagina_prenotazioni():
    risposta = chiama("GET", "/prenotazioni")
    if risposta.status_code != 200:
        st.header("Le mie prenotazioni")
        st.error(dettaglio(risposta))
        return
    prenotazioni = risposta.json()
    st.header(f"Le mie prenotazioni ({len(prenotazioni)})")
    if not prenotazioni:
        st.info("Non hai ancora nessuna prenotazione: chiedi all'assistente di prepararne una.")
        return
    for p in prenotazioni:
        titolo = (
            f"Codice {p['id']} · {p['hotel']['citta']} · {data_it(p['data_da'])} - "
            f"{data_it(p['data_a'])} · {p['costo_totale']:.2f} € · {p['stato']}"
        )
        with st.expander(titolo):
            giorni = [(a["giorno"], a["attivita"]) for a in p["attivita"]]
            mostra_viaggio(p["volo_andata"], p["volo_ritorno"], p["hotel"], giorni)


# ---------------------------------------------------------------------------
# Punto di ingresso
# ---------------------------------------------------------------------------
inizializza()

if not st.session_state.token:
    schermata_accesso()
else:
    with st.sidebar:
        st.write(f"Connesso come **{st.session_state.utente['nome']}**")
        pagina = st.radio("Sezione", ["Chat", "Le mie prenotazioni"], key="pagina")
        if st.button("Esci"):
            esci()
    if pagina == "Chat":
        pagina_chat()
    else:
        pagina_prenotazioni()