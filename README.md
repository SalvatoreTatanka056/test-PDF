# 📑 PDF Sign & Edit Studio

Un'applicazione desktop moderna, intuitiva e completa con interfaccia grafica visuale per **aprire, visualizzare, modificare, annotare e firmare documenti PDF**.

---

## 🚀 Come Avviare l'Applicazione

Puoi avviare l'applicazione in due modi:

1. **Doppio click sul file**:
   - `avvia.bat`

2. **Da terminale PowerShell / CMD**:
   ```powershell
   python main.py
   ```

All'avvio troverai già caricato un documento di prova (`esempio_contratto.pdf`) per iniziare subito a testare la firma e le modifiche!

---

## ✨ Funzionalità Principali

### ✍️ Firma Digitale e Grafica
1. **Disegna a Mano Libera**:
   - Tavoletta di disegno ad alta risoluzione con campionamento morbido del tratto.
   - Selezione del colore inchiostro: *Blu Penna*, *Nero Classico*, *Blu Notte*, *Rosso*.
   - Regolazione spessore del pennino (da sottile a marcato).
   - Tasto *Annulla Tratto* (Ctrl-Z style) e *Cancella*.
   - **Ritaglio automatico intelligente**: la firma viene ritagliata con precisione sui bordi reali del tratto, senza margini vuoti ingombranti.
2. **Firma Calligrafica (Digitata)**:
   - Digita il tuo nome o le tue iniziali.
   - Scegli tra font calligrafici eleganti disponibili su Windows (*Brush Script*, *Edwardian Script*, *Ink Free*, *Segoe Script*, *Freestyle Script*).
   - Anteprima in tempo reale.
3. **Carica Immagine Firma**:
   - Carica la foto o scansione della tua firma (PNG, JPG, JPEG, BMP).
   - **Rimozione automatica dello sfondo bianco**: rende lo sfondo completamente trasparente con cursore di tolleranza regolabile.
4. **Posizionamento Interattivo sul PDF**:
   - Trascina la firma con il mouse in qualsiasi punto della pagina (es. sulla linea *"Firma per accettazione"*).
   - Ridimensiona la firma trascinando il quadratino nell'angolo inferiore destro o tramite lo slider dimensione.

---

### 🔤 Modifica Contenuti e Testi
- **🧹 Evidenziatore Cancella-Scritto (Colore Foglio)**:
  - Strumento evoluto per **cancellare scritte, testi o porzioni del PDF campionando in tempo reale il colore reale del foglio**.
  - Rileva automaticamente la tonalità esatta dello sfondo circostante (bianco, avorio, crema o sfumature) e riempie l'area cancellata con quel colore esatto, rendendo la cancellazione perfettamente uniforme ed invisibile.
  - Funziona sia su singoli testi che su intere aree (timbri, linee, grafiche, scritte).
  - Rimozione permanente dal PDF con un semplice click o premendo **`Canc`** / **`Backspace`**.
  - **Supporto Annulla (Undo / `Ctrl + Z`)**: ogni cancellazione può essere annullata all'istante ripristinando il contenuto originale.
- **Aggiungi Testo**: inserisci caselle di testo personalizzate, modificabili in tempo reale.
- **Inserisci Data Odierna**: pulsante rapido per apporre la data di oggi formattata (es. `22/11/2026`) accanto alla firma.
- **Timbri Rapidi**: inserisci timbri grafici con bordo arrotondato e badge (*APPROVATO*, *FIRMATA*, *CONFORME ALL'ORIGINALE*, *BOZZA*, *PAGATO*, *RISERVATO*, *ANNULLATO*).

---

### 🖍️ Annotazioni, Censura e Strumenti Grafici
- **Evidenziatore**: traccia rettangoli semitrasparenti per evidenziare clausole o passaggi importanti.
- **Censura / Bianchetto**: copri informazioni sensibili con rettangoli opachi (nero o bianco).
- **Penna a Mano Libera**: disegna note, cerchi, frecce o appunti direttamente sulla pagina PDF.

---

### 📑 Gestione Pagine e Visualizzazione
- **Navigazione Pagine**: pulsanti Pagina Precedente / Successiva e contatore pagine.
- **Ruota Pagina 90°**: ruota in senso orario qualsiasi pagina con orientamento errato.
- **Elimina Pagina**: rimuove pagine non necessarie.
- **Aggiungi Nuova Pagina**: aggiunge una pagina bianca nel punto desiderato.
- **Zoom Fluido**: pulsanti Zoom +, Zoom -, Adatta alla larghezza, e zoom tramite `Ctrl + Rotellina del mouse`.

---

### 💾 Esportazione e Salvataggio
- **Salva**: sovrascrive il documento con le modifiche incorporate in modo permanente.
- **Salva con Nome**: esporta una nuova copia firmata e modificata.
- **Qualità vettoriale e nativa**: testi e immagini vengono integrati ad alta risoluzione senza perdita di qualità dei font originali.

---

## ⌨️ Scorciatoie da Tastiera
| Scorciatoia | Azione |
|---|---|
| `Ctrl + O` | Apri documento PDF |
| `Ctrl + S` | Salva modifiche |
| `Ctrl + Shift + S` | Salva con nome |
| `Ctrl + Z` | Annulla ultima cancellazione / operazione |
| `Ctrl + +` / `Ctrl + -` | Zoom avanti / indietro |
| `Ctrl + Rotella Mouse` | Zoom dinamico |
| `Rotella Mouse` | Scorrimento verticale |
| `Shift + Rotella Mouse` | Scorrimento orizzontale |
| `Canc` / `Backspace` | Elimina l'elemento selezionato |
| `Freccia Sinistra` / `Destra` | Pagina precedente / successiva |

---

## 📁 Struttura del Progetto
- `main.py` & `app.py`: Interfaccia grafica CustomTkinter ed eventi interattivi del canvas.
- `signature_dialog.py`: Finestra modale per disegnare, digitare o caricare firme con rimozione dello sfondo.
- `pdf_engine.py`: Motore PDF basato su PyMuPDF per rendering ad alta definizione, vettorializzazione e salvataggio.
- `avvia.bat`: File di avvio rapido per Windows.
- `esempio_contratto.pdf`: Documento di prova pronto per essere firmato e modificato.
