# Travel Assistant

Assistente virtuale conversazionale per la generazione di itinerari di
viaggio personalizzati (volo + hotel + attività), sviluppato come challenge
tecnica per un colloquio di lavoro.

## Indice

- [Panoramica](#panoramica)
- [Stack tecnologico](#stack-tecnologico)
- [Struttura del progetto](#struttura-del-progetto)
- [Requisiti](#requisiti)
- [Setup](#setup)
- [Popolare i dati](#popolare-i-dati)
- [Avviare l'applicazione](#avviare-lapplicazione)
- [API disponibili](#api-disponibili)
- [Stato di avanzamento](#stato-di-avanzamento)
- [Limitazioni note](#limitazioni-note)

## Panoramica

L'utente descrive in linguaggio naturale budget, destinazione, preferenze
sulle attività e periodo di viaggio; il sistema estrae questi dati dalla
conversazione, cerca attività pertinenti tramite ricerca semantica (RAG) e
in futuro comporrà un itinerario completo prenotabile via chat.

Per il razionale delle scelte architetturali (perché FastAPI, perché SQLite,
perché Chroma, come sono state generate le descrizioni delle attività, ecc.)
vedi [`docs/architecture.md`](docs/architecture.md).

## Stack tecnologico

| Componente          | Scelta                          |
|---------------------|----------------------------------|
| Backend             | FastAPI (Python 3.11)           |
| Database relazionale| SQLite + SQLAlchemy 2.0         |
| Database vettoriale | ChromaDB (locale, persistente)  |
| LLM                 | API Claude (Anthropic), Haiku   |
| Gestione pacchetti  | uv                               |
| Dati sintetici      | Faker (locale it_IT)            |
| Frontend            | Streamlit *(in lavorazione)*    |

## Struttura del progetto
```
travel-assistant/
├── backend/
│ └── app/
│ ├── api/ # endpoint FastAPI (hotels, voli, attivita)
│ ├── core/
│ ├── db/ # modelli SQLAlchemy, seed, sessione DB
│ ├── llm/ # estrazione strutturata richieste utente (Claude)
│ ├── rag/ # generazione descrizioni + indicizzazione Chroma
│ ├── main.py
│ └── schemas.py # schemi Pydantic delle risposte API
├── frontend/ # interfaccia Streamlit (in lavorazione)
├── data/
│ ├── travel.db # database SQLite
│ ├── descrizioni_attivita.json
│ └── chroma/ # DB vettoriale (rigenerabile, non versionato)
├── docs/
│ └── architecture.md # note architetturali dettagliate
├── pyproject.toml
└── README.md
```

## Requisiti

- Python 3.11
- [uv](https://docs.astral.sh/uv/) per la gestione delle dipendenze
- Una API key Anthropic (Claude) (ne fornirò una insieme al link della
  repository, così puoi provare il progetto senza dover configurare
  fatturazione sul tuo account).

## Setup

```bash
git clone <url-repo>
cd travel-assistant
uv sync
cp .env.example .env
```

Apri `.env` e incolla la chiave che ti ho fornito dopo `ANTHROPIC_API_KEY=`, poi salva.

## Popolare i dati

Dalla cartella `backend/`, **nell'ordine indicato**:

```bash
cd backend
uv run python -m app.db.seed
uv run python -m app.rag.genera_descrizioni
uv run python -m app.rag.indicizza_attivita
```

## Avviare l'applicazione

```bash
uv run uvicorn app.main:app --reload
```

API su `http://127.0.0.1:8000`, documentazione interattiva su `http://127.0.0.1:8000/docs`.


## API disponibili

| Metodo | Endpoint     | Descrizione                          |
|--------|--------------|---------------------------------------|
| GET    | `/`          | Health check                          |
| GET    | `/hotels`    | Elenco hotel disponibili              |
| GET    | `/voli`      | Elenco voli disponibili               |
| GET    | `/attivita`  | Elenco attività disponibili           |

## Stato di avanzamento

- [x] Modello dati relazionale e dati sintetici
- [x] Endpoint di lettura (hotel, voli, attività)
- [x] Generazione descrizioni attività via Claude (tool use) e indicizzazione vettoriale (RAG)
- [x] Estrazione strutturata dei dati di viaggio dalla conversazione
- [ ] Logica di generazione itinerario (budget/disponibilità/preferenze + RAG)
- [ ] Endpoint utenti (registrazione/autenticazione) e prenotazioni
- [ ] Frontend Streamlit

## Limitazioni note

- Disponibilità di hotel e attività modellata come intervallo di date, non
  come calendario giorno per giorno: nessun controllo di overbooking/capacità.
- Nessuna autenticazione reale implementata ancora (password salvate come
  placeholder nei dati di test).
- Progetto sviluppato con una scadenza breve: copre in modo
  coerente i pezzi più significativi dal punto di vista architetturale
  (RAG, estrazione strutturata) più che l'intera superficie funzionale
  richiesta dalla specifica.
