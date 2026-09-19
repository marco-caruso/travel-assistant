# Note architetturali — Travel Assistant

Assistente virtuale conversazionale per la generazione di itinerari di viaggio
personalizzati (volo + hotel + attività), sviluppato come challenge tecnica.
Questo documento riassume le scelte fatte finora e il perché.

## Stack e motivazioni

- **Backend: FastAPI** (Python), invece delle alternative suggerite
  (Node.js/Django/Flask/Rails) — scelto per coerenza con Pydantic, che viene
  riusato sia per la validazione delle API sia per l'estrazione strutturata
  via LLM.
- **DB relazionale: SQLite + SQLAlchemy 2.0** — sufficiente per la scala del
  progetto nei tempi disponibili; lo schema è comunque pensato per essere
  portabile su Postgres senza modifiche concettuali.
- **DB vettoriale: ChromaDB**, `PersistentClient` locale su disco, embedding
  function di default (modello ONNX scaricato automaticamente al primo uso,
  nessun costo o dipendenza da API esterne per gli embedding).
- **LLM: API Claude (Anthropic)**, modello Haiku per contenere i costi.
- **Gestione pacchetti:** uv. **Dati sintetici:** Faker (locale it_IT).
- **Frontend (in corso):** Streamlit.
- Convenzione: naming in italiano per coerenza col dominio (endpoint, campi,
  variabili); unica eccezione il suffisso `Out` sugli schemi Pydantic di
  risposta API.

## Modello dati relazionale

Entità principali: `Utente`, `Volo`, `Hotel`, `Attivita`, `Prenotazione`
(con tabella ponte `PrenotazioneAttivita` per gestire più attività per
itinerario).

Scelta deliberata: `Attivita` non ha campi di categoria o target — quella
informazione qualitativa vive solo nel database vettoriale, collegata via id,
per non duplicare dati tra i due database.

Semplificazione dichiarata: la disponibilità di hotel e attività è modellata
come intervallo di date, non come calendario giorno per giorno — questo
significa che non c'è controllo di overbooking/capacità. Scelta consapevole
per restare nei tempi della challenge.

## RAG: descrizioni e indicizzazione vettoriale

Le 25 attività seedate sono state arricchite con descrizione testuale,
categoria e target ideale generati tramite l'API Claude (script
`genera_descrizioni.py`), invece che scritti a mano o con template — per
velocità e per ottenere varietà semantica sufficiente a rendere utile la
ricerca RAG.

Dettagli di design rilevanti:
- **Categoria e target sono liste**, non valori singoli: un'attività può
  ragionevolmente piacere a più pubblici o appartenere a più categorie
  insieme (es. un tour è sia "cultura" che adatto a "famiglie" e "coppie").
- **Vocabolario controllato** (cultura/sport/relax/nightlife/altro per la
  categoria; famiglie/giovani/sportivi/coppie/altro per il target), allineato
  al linguaggio che l'utente userà per esprimere le proprie preferenze —
  così il matching successivo è diretto.
- **Tool use invece di JSON testuale**: la prima versione, basata su un
  prompt che chiedeva JSON a parole, falliva a intermittenza perché il
  modello non rispettava sempre l'enum richiesto. Il tool use di Claude
  vincola strutturalmente la risposta allo schema dichiarato; resta comunque
  un retry (max 3 tentativi) come rete di sicurezza, e una validazione
  Pydantic finale.
- **Script di generazione separato dall'indicizzazione**: le descrizioni
  vengono salvate in un JSON intermedio (`data/descrizioni_attivita.json`)
  revisionabile a mano prima di finire nel vettoriale.
- **Document vs metadata in Chroma**: i metadata accettano solo valori
  scalari, quindi categoria e target sono inclusi in linguaggio naturale nel
  testo embeddato (`document`), mentre nei metadata resta solo `citta`, unico
  campo per cui ha senso un filtro esatto.

La ricerca semantica è stata testata e funziona correttamente (query di
prova su "relax e romantico" ha correttamente premiato le attività più
pertinenti).

## Estrazione strutturata delle richieste utente

Script `app/llm/estrazione.py`: dato lo storico della conversazione, estrae
budget, nazione, preferenze (stesso vocabolario delle categorie attività) e
periodo tramite tool use, con campi opzionali (`None` se non ancora forniti).

Scelta di design: a ogni turno si passa l'intero storico della conversazione
e si chiede lo stato aggregato completo, invece di estrarre solo l'ultimo
messaggio e fare merge manuale — più semplice e meno soggetto a bug. Testato
con conversazioni multi-turno: i dati dati in turni precedenti non vengono persi.

## Stato di avanzamento

Completato: modelli relazionali, dati sintetici, endpoint di sola lettura
(`/hotels`, `/voli`, `/attivita`), generazione descrizioni e indicizzazione
vettoriale delle attività, estrazione strutturata delle richieste utente.

Da fare: logica di generazione itinerario (vincoli di budget/disponibilità/
preferenze combinati con ricerca RAG), endpoint di registrazione utenti e
prenotazioni, frontend Streamlit.