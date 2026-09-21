# Note architetturali — Travel Assistant

Questo documento spiega le scelte principali del progetto e il loro perché. Per
installare ed eseguire tutto vedi il [README](../README.md).

## Principio guida: il codice decide, il modello no

Un modello linguistico è bravo a capire il linguaggio naturale e pessimo a fare da
fonte di verità: inventerebbe prezzi e disponibilità. Per questo il sistema è diviso così:

- **Claude** interviene in un solo punto: trasformare la conversazione in dati strutturati
  (budget, nazione, preferenze, mese).
- **Il codice** valida quei dati, decide quale domanda fare, compone l'itinerario e lo prenota,
  leggendo prezzi e date dal database.
- **La ricerca semantica (RAG)** ordina le attività per affinità con le preferenze e restituisce
  solo id; i dettagli e i prezzi si leggono sempre dal database relazionale.

Effetto: i risultati sono prevedibili, verificabili e testabili, e il modello non può
«promettere» un viaggio che non esiste.

## Stack

- **FastAPI**: Pydantic è riusato sia per validare le API sia per l'estrazione strutturata con Claude.
- **SQLite + SQLAlchemy 2.0**: basta per la scala della challenge; lo schema è portabile su Postgres.
- **ChromaDB** (`PersistentClient` su disco) con embedding di default (modello ONNX locale): nessun
  costo né API esterna per gli embedding.
- **Claude Haiku 4.5** con tool use, per costi e latenza contenuti.
- **Streamlit** per il frontend (vedi sotto). **uv** per i pacchetti, **Faker** per i dati sintetici.
- Naming in italiano per coerenza col dominio; unica eccezione il suffisso `Out` sugli schemi di risposta.

## Modello dati

Entità: `Utente`, `Volo`, `Hotel`, `Attivita`, `Prenotazione` (con tabella ponte
`PrenotazioneAttivita`, perché un itinerario ha più attività in giorni diversi).

Dati sintetici: 5 città (una per nazione), 4 hotel e 15 attività per città, voli di andata e
ritorno per circa 13 mesi da un aeroporto di partenza a scelta tra CAG, FCO e MXP. Sono generati
pensando a cosa deve poter trovare il generatore di itinerari: con date casuali e sparse non si
riuscirebbe mai a comporre un viaggio completo.

`Attivita` non ha campi di categoria o target: quell'informazione qualitativa vive solo nel database
vettoriale, collegata via id, per non duplicare i dati tra i due database.

## RAG: descrizioni, indicizzazione, ricerca

**Descrizioni.** Le 75 attività sono arricchite con descrizione, categorie e target ideali generati con
Claude (`genera_descrizioni.py`) invece che scritti a mano, per avere varietà semantica sufficiente.
Categorie e target sono liste (un tour è insieme «cultura» e adatto a «famiglie» e «coppie») con vocabolario
controllato: cultura, sport, relax, nightlife, natura, altro / famiglie, giovani, sportivi, coppie, altro.
Lo script scrive in un JSON intermedio (`data/descrizioni_attivita.json`), rivedibile a mano prima
dell'indicizzazione.

Nota sul tool use: la prima versione chiedeva il JSON a parole e falliva a intermittenza (enum non
rispettati). Il tool use guida il modello verso lo schema dichiarato, ma non lo garantisce al 100%:
per questo restano una validazione Pydantic finale e un retry (max 3 tentativi).

**Indicizzazione.** Chroma accetta solo valori scalari nei metadata: categoria e target sono quindi scritti
in linguaggio naturale nel testo indicizzato, e nei metadata resta solo `citta`, l'unico campo per cui serve
un filtro esatto. L'indice è un dato derivato (DB + JSON): non è versionato, e il backend lo costruisce da
solo all'avvio se la collection è vuota, così chi clona il progetto non deve ricordarsi un passo in più.

**Ricerca.** Ogni preferenza viene tradotta in una breve frase descrittiva (un embedding confronta meglio
frase con frase che parola con frase) e cercata separatamente, filtrando per città. Le classifiche si
fondono con il metodo Borda: chi è molto adatto a una preferenza e discreto per l'altra batte chi è
generico. Una ricerca con tutte le preferenze in un'unica frase mescolerebbe i significati e darebbe
risultati sfocati. «Altro» è ignorato: non porta informazione utile per ordinare.

**Dimensione del catalogo.** Una prima versione aveva 8 attività per città con 5 giorni da riempire: entrava più di metà del catalogo qualunque fosse la preferenza, e la ricerca semantica quasi non cambiava l'itinerario. Portare il catalogo a 15 attività per città (75 in totale) rende la selezione significativa. Per lo stesso motivo il prompt di classificazione chiede categorie selettive: con la prima versione «cultura» compariva su 7 attività su 8 a Parigi, ora su circa un terzo del catalogo.

Limite osservato (Parigi): le prime posizioni sono coerenti con la preferenza (relax → spa e hammam, sport → bicicletta e corsa, nightlife → jazz club e cabaret), ma nelle successive compare qualche attività fuori tema (per esempio il Louvre tra le prime cinque per «sport»). La causa più probabile è l'embedding di default, pensato per l'inglese, su testi in italiano.

## Conversazione: estrazione, validazione, chat

- **Estrazione** (`llm/estrazione.py`): a ogni turno si passa l'intera conversazione e si chiede lo stato
  aggregato completo, con campi `None` se non ancora forniti. È più semplice e meno soggetto a bug che
  estrarre solo l'ultimo messaggio e fare il merge a mano.
- **Validazione** (`core/validazione.py`): distingue un dato *mancante* (basta chiederlo) da uno *non valido*
  (detto, ma inutilizzabile, come una nazione non servita). L'ordine delle domande è fisso (nazione, mese,
  preferenze, budget) e lo decide il codice, non il modello, quindi è prevedibile.
- **Chat senza stato** (`core/chat.py`): il server non tiene sessioni. Il client rimanda la conversazione
  intera più la `proposta`, cioè gli id dell'itinerario in attesa di conferma. Costa qualche byte in più a
  ogni richiesta, ma il backend resta scalabile e non c'è stato da sincronizzare o perdere.
- **Conferma** (`core/conferma.py`): «sì» e «no» sono riconosciuti da regole (tutte le parole del messaggio
  devono essere parole di conferma o neutre, senza accenti né maiuscole). Il caso «sì ma costa troppo» non
  è una conferma e genera una nuova proposta: prenotare per un equivoco sarebbe l'errore peggiore. Se la
  nuova proposta è identica alla precedente, l'assistente lo dice e spiega cosa può cambiare.

## Generazione dell'itinerario

`core/itinerario.py`, tutto deterministico:

1. Dal mese si ricava la finestra di partenza (mese passato → anno prossimo).
2. La durata non è un input: si prova la più lunga (5 notti) e si scende fino a 3 finché budget e
   disponibilità lo permettono. Il budget è un tetto, non una cifra da spendere.
3. Per ogni durata si sceglie la combinazione più economica di volo di andata, ritorno (stesso aeroporto di
   partenza, dopo esattamente N notti) e hotel disponibile per tutto il soggiorno.
4. Prima di accettarla si tiene da parte il costo delle attività più economiche, per non spendere tutto
   in voli e hotel e restare con giorni vuoti.
5. Un'attività per notte: la più adatta secondo il RAG, disponibile quel giorno e sostenibile col budget
   residuo (dopo ogni scelta devono restare i soldi per le attività più economiche ancora libere).

Se non c'è soluzione, il messaggio dice quanto servirebbe almeno. Se un giorno resta senza attività, compare
un avviso.

## Autenticazione

Login con **JWT** (HS256, 8 ore, nessun refresh) e password con **scrypt**. Il segreto viene da `JWT_SECRET`
(niente valore di ripiego). Il decode accetta solo l'algoritmo atteso e richiede `exp` e `sub`. Con email
sconosciuta o password errata la risposta è la stessa 401 generica, e per l'email sconosciuta si calcola
comunque un hash fittizio: non si rivela quali email sono registrate né con i messaggi né con i tempi.

## Prenotazione

Il client invia **solo gli id** (voli, hotel, attività con giorno); il server rilegge tutto dal database e
ricontrolla: esistenza, aeroporti e città, date, ritorno coerente con l'andata, disponibilità di hotel e
attività nei giorni indicati, budget. Il prezzo lo ricalcola lui: un client non può prenotare a un prezzo
scelto da sé. Tutto avviene in una sola transazione. Una prenotazione identica già fatta dallo stesso utente
dà 409, dati non validi 422. Dalla chat la prenotazione parte dalla `proposta` salvata dal client, con gli
stessi controlli del pulsante.

## Frontend

Streamlit, scelto consapevolmente al posto di HTML/JS o React: la traccia dice che la grafica non è
oggetto di valutazione, e il tempo è meglio speso su backend e AI. È un **client HTTP puro**: importa solo
`requests` e `streamlit`, non tocca mai il database né la ricerca semantica. Passare a React vorrebbe dire
sostituire un solo file, senza toccare l'API. La sessione (token, chat) sta in `st.session_state`. Il tema
viola in modalità chiara e scura è in `.streamlit/config.toml`. Dopo una prenotazione la chat riparte da
zero, altrimenti l'estrazione riaggregherebbe i dati del viaggio appena prenotato.

## Semplificazioni dichiarate e cosa cambierebbe in produzione

| Semplificazione                                   | In produzione                                     |
|---------------------------------------------------|---------------------------------------------------|
| Disponibilità come intervallo di date, senza posti | Calendario con capienza e blocco dei posti        |
| SQLite, schema creato dal seed                    | Postgres + migrazioni (Alembic)                   |
| Prenotazione subito «confermata», niente pagamento | Stati (in attesa, pagata, annullata) e pagamento  |
| JWT 8 ore, senza refresh né revoca                | Refresh token, cookie httpOnly, revoca            |
| Endpoint di consultazione pubblici                | Rate limiting e autenticazione dove serve         |
| Una città per nazione, un'attività al giorno      | Più città, più attività, itinerari multi-città    |
| Sessione Streamlit in memoria, niente storico     | Storico conversazioni salvato sul database        |
| Embedding di default (inglese) su testi italiani  | Modello multilingue; valutare la qualità con un set di query di prova |
| Nessun test automatico nel repository             | Test di unità sulla logica di itinerario e prenotazione |

## Preparazione dei dati

Ordine di esecuzione, solo se si rigenerano i dati (i file forniti sono già coerenti):
`seed` (DB relazionale, cancella utenti e prenotazioni) → `genera_descrizioni` (JSON, chiama Claude) →
`indicizza_attivita` (indice vettoriale). Il seed è riproducibile, ma le date dei voli partono dal giorno
in cui lo si esegue.
