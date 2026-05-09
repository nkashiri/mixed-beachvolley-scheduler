# Mixed Beach Volleyball Tournament Tools

> **Three Python scripts for generating, assigning, and printing a fair 2v2 mixed beach volleyball tournament.**

---

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Script 1 — `mixedmatches_v1_0.py`](#script-1--mixedmatches_v10py)
- [Script 2 — `player_assign_v1_0.py`](#script-2--player_assign_v10py)
- [Script 3 — `make_scoresheet_v1_0.py`](#script-3--make_scoresheet_v10py)
- [Typical Workflow](#typical-workflow)
- [File Reference](#file-reference)

---
---

# Strumenti per Torneo di Beach Volley Misto

> **Tre script Python per generare, assegnare e stampare un torneo equo di beach volley 2v2 misto.**

---

## Indice

- [Panoramica](#panoramica)
- [Requisiti](#requisiti)
- [Script 1 — `mixedmatches_v1_0.py`](#script-1--mixedmatches_v10py-1)
- [Script 2 — `player_assign_v1_0.py`](#script-2--player_assign_v10py-1)
- [Script 3 — `make_scoresheet_v1_0.py`](#script-3--make_scoresheet_v10py-1)
- [Flusso di lavoro tipico](#flusso-di-lavoro-tipico)
- [Riferimento ai file](#riferimento-ai-file)

---
---

# ENGLISH

---

## Overview

The three scripts form a pipeline:

```
mixedmatches_v1_0.py   →   player_assign_v1_0.py   →   make_scoresheet_v1_0.py
  (generate schedule)         (assign real players)         (print PDF)
```

Each script is independent and can be run on its own; they communicate through CSV files.

---

## Requirements

```
Python 3.9+
numpy
matplotlib
seaborn
reportlab
```

Install with:

```bash
pip install numpy matplotlib seaborn reportlab
```

---

## Script 1 — `mixedmatches_v1_0.py`

### What it does

Generates a complete round-robin 2v2 mixed beach volleyball schedule for **N males and N females** (set `N` at the top of the file). Every match puts one male–female pair against another.

### Hard constraints guaranteed

| # | Constraint |
|---|-----------|
| 1 | Every male pair plays every other male pair exactly once. |
| 2 | Every female pair plays every other female pair exactly once. |
| 3 | Each male partners with any given female at most once. |

### Soft constraint minimised

- **Cross-opposition count** — the number of times any male ends up on the opposite side from any given female. The algorithm minimises the maximum such count across all male–female pairs.

### How it works

1. **Schedule generation** (`generate_best_schedule`): runs up to `num_attempts` (default 1000) independent greedy attempts. In each attempt, male pairs are iterated in a random order. For every male pair, the function scores all unused female pairs by how much they would increase the cross-opposition maximum; the cheapest valid assignment is committed. When the greedy gets stuck (no valid female pair is available), a targeted repair step (`_try_repair`) undoes one prior match to free a female pair and retries. The attempt with the lowest cross-opposition maximum is kept.

2. **Round scheduling** (`save_readable_schedule`): organises the flat match list into rounds so that no player appears more than once per round. Uses swap-based local search with patience-based restarts.

3. **Validation and evaluation** (`validate_rounds`, `create_evaluation_tables`, `create_heatmaps`): checks that each round has no player conflicts, produces four CSV matrices (male–male opposition, female–female opposition, male–female cross-opposition, male–female partnership), and saves a 2×2 heatmap figure.

### How to run

```bash
python mixedmatches_v1_0.py
```

Edit `N = 12` (or any value) near the top of the file to change the number of players.

### Outputs

| File | Description |
|------|-------------|
| `best_matches_readable.csv` | Full schedule grouped into rounds — **input for the next two scripts** |
| `table_male_male_opp.csv` | How many times each male pair opposed each other |
| `table_female_female_opp.csv` | How many times each female pair opposed each other |
| `table_mf_oppositions.csv` | Cross-opposition matrix (males × females) |
| `table_mf_partnerships.csv` | Partnership matrix (males × females) |
| `heatmaps_all.png` | 2×2 heatmap of all four matrices |

---

## Script 2 — `player_assign_v1_0.py`

### What it does

Reads the abstract schedule produced by Script 1 (slot indices M0, M1, … and F0, F1, …) and maps **real named players** onto those slots so that the resulting matches are as balanced as possible in terms of team scores.

### Inputs to configure

Edit the following lists inside the `if __name__ == "__main__":` block:

```python
male_names   = ["Alice", "Bob", ...]   # one name per male player
male_scores  = [5, 4, 6, ...]          # skill score per male player

female_names  = ["Carol", "Dana", ...]
female_scores = [5, 3, 6, ...]
```

Skill scores are single integers representing each player's level; the exact scale is up to you — what matters is the relative differences between players.

### Optimisation objectives

Optimised in strict priority order (no lower-priority term can override a higher one):

| Priority | Metric | Meaning |
|----------|--------|---------|
| 1 | **Max diff** | Largest score difference across all matches — no single match should be wildly unbalanced. |
| 2 | **Signed spread** | Spread between the highest and lowest per-player net signed sum. A player's signed sum is the total of (their team score − opponent score) across all their matches; a high spread means some players consistently get lucky or unlucky pairings. |
| 3 | **Max absolute signed sum** | The single player whose net signed sum is furthest from zero — the individual most favoured or disadvantaged by the schedule. |
| 4 | **Total abs diff** | Sum of score differences across all matches — a tiebreaker for overall smoothness. |

### How it works

**Multi-start hill climbing**: the algorithm runs `num_restarts` (default 300) independent restarts. Each restart:
1. Assigns both male and female players to slots randomly.
2. Runs `steps_per_restart` (default 800) swap attempts: at each step a random pair of males or females is swapped, and the swap is kept only if it strictly improves the composite objective.

The best assignment found across all restarts is returned.

### Outputs

| File | Description |
|------|-------------|
| `best_matches_assigned.csv` | Full schedule with real player names and team scores |
| `balance_heatmap.png` | Heatmap showing each player's signed match score differences, sorted from worst to best |

### How to run

```bash
python player_assign_v1_0.py
```

---

## Script 3 — `make_scoresheet_v1_0.py`

### What it does

Reads `best_matches_readable.csv` and produces a **2-page landscape A4 PDF** ready to print and use courtside. Each page contains three side-by-side panels; each panel has a left column with the match description and an empty right column for writing the result.

### How it works

Uses `reportlab` to draw directly onto a canvas with precise geometry: margins, panel widths, row heights, and column splits are all calculated from the page dimensions so the layout adapts automatically to any number of matches. Alternating row backgrounds and a numbered badge per match make the sheet easy to read.

### How to run

```bash
# Default: reads best_matches_readable.csv, writes tournament_scoresheet.pdf
python make_scoresheet_v1_0.py

# Custom input
python make_scoresheet_v1_0.py my_schedule.csv

# Custom input and output
python make_scoresheet_v1_0.py my_schedule.csv my_scoresheet.pdf
```

### Output

| File | Description |
|------|-------------|
| `tournament_scoresheet.pdf` | 2-page landscape A4 printable scoresheet |

---

## Typical Workflow

```
1.  Edit N in mixedmatches_v1_0.py
    python mixedmatches_v1_0.py
        → best_matches_readable.csv  (and heatmaps for inspection)

2.  Edit player names and scores in player_assign_v1_0.py
    python player_assign_v1_0.py
        → best_matches_assigned.csv
        → balance_heatmap.png        (inspect: is the assignment fair?)

3.  python make_scoresheet_v1_0.py
        → tournament_scoresheet.pdf  (print and bring to the beach)
```

---

## File Reference

| File | Produced by | Consumed by |
|------|-------------|-------------|
| `best_matches_readable.csv` | Script 1 | Scripts 2 and 3 |
| `best_matches_assigned.csv` | Script 2 | — (final output) |
| `tournament_scoresheet.pdf` | Script 3 | — (print this) |
| `heatmaps_all.png` | Script 1 | — (for inspection) |
| `balance_heatmap.png` | Script 2 | — (for inspection) |

---
---

# ITALIANO

---

## Panoramica

I tre script formano una pipeline:

```
mixedmatches_v1_0.py   →   player_assign_v1_0.py   →   make_scoresheet_v1_0.py
  (genera il calendario)     (assegna i giocatori reali)    (stampa il PDF)
```

Ogni script è indipendente e può essere eseguito da solo; comunicano tra loro tramite file CSV.

---

## Requisiti

```
Python 3.9+
numpy
matplotlib
seaborn
reportlab
```

Installazione:

```bash
pip install numpy matplotlib seaborn reportlab
```

---

## Script 1 — `mixedmatches_v1_0.py`

### Cosa fa

Genera un calendario completo di beach volley 2v2 misto con formato round-robin per **N maschi e N femmine** (impostare `N` in cima al file). Ogni partita mette una coppia misto contro un'altra.

### Vincoli rigidi garantiti

| # | Vincolo |
|---|---------|
| 1 | Ogni coppia di maschi affronta ogni altra coppia di maschi esattamente una volta. |
| 2 | Ogni coppia di femmine affronta ogni altra coppia di femmine esattamente una volta. |
| 3 | Ogni maschio fa coppia con ogni femmina al massimo una volta. |

### Vincolo soft minimizzato

- **Conteggio delle opposizioni incrociate** — il numero di volte in cui un maschio si trova sul lato opposto di una data femmina. L'algoritmo minimizza il massimo di questo conteggio su tutte le coppie maschio–femmina.

### Come funziona

1. **Generazione del calendario** (`generate_best_schedule`): esegue fino a `num_attempts` (predefinito 1000) tentativi greedy indipendenti. In ogni tentativo, le coppie di maschi vengono iterate in ordine casuale. Per ogni coppia di maschi, la funzione valuta tutte le coppie di femmine non ancora usate in base a quanto aumenterebbero il massimo di opposizione incrociata; viene assegnata la scelta meno costosa valida. Quando il greedy si blocca, un passo di riparazione mirata (`_try_repair`) annulla una partita precedente per liberare una coppia di femmine e riprova. Viene conservato il tentativo con il massimo di opposizione incrociata più basso.

2. **Organizzazione in gironi** (`save_readable_schedule`): organizza la lista piatta di partite in gironi in modo che nessun giocatore appaia più di una volta per girone. Utilizza una ricerca locale basata su scambi con riavvii basati sulla pazienza.

3. **Validazione e valutazione** (`validate_rounds`, `create_evaluation_tables`, `create_heatmaps`): verifica che ogni girone non abbia conflitti tra giocatori, produce quattro matrici CSV e salva una figura con 4 heatmap.

### Come eseguire

```bash
python mixedmatches_v1_0.py
```

Modificare `N = 12` (o qualsiasi valore) in cima al file per cambiare il numero di giocatori.

### Output

| File | Descrizione |
|------|-------------|
| `best_matches_readable.csv` | Calendario completo raggruppato in gironi — **input per i due script successivi** |
| `table_male_male_opp.csv` | Quante volte ogni coppia di maschi si è affrontata |
| `table_female_female_opp.csv` | Quante volte ogni coppia di femmine si è affrontata |
| `table_mf_oppositions.csv` | Matrice di opposizioni incrociate (maschi × femmine) |
| `table_mf_partnerships.csv` | Matrice di partnership (maschi × femmine) |
| `heatmaps_all.png` | Heatmap 2×2 di tutte e quattro le matrici |

---

## Script 2 — `player_assign_v1_0.py`

### Cosa fa

Legge il calendario astratto prodotto dallo Script 1 (indici slot M0, M1, … e F0, F1, …) e mappa i **giocatori reali con nome** su quegli slot in modo che le partite risultanti siano il più equilibrate possibile in termini di punteggi di squadra.

### Input da configurare

Modificare le seguenti liste nel blocco `if __name__ == "__main__":`:

```python
male_names   = ["Mario", "Luigi", ...]   # un nome per ogni giocatore maschio
male_scores  = [5, 4, 6, ...]            # punteggio di abilità per ogni maschio

female_names  = ["Sara", "Anna", ...]
female_scores = [5, 3, 6, ...]
```

I punteggi di abilità sono interi singoli che rappresentano il livello di ciascun giocatore; la scala esatta dipende da voi — ciò che conta sono le differenze relative tra i giocatori.

### Obiettivi di ottimizzazione

Ottimizzati in ordine di priorità rigorosa (nessun termine di priorità inferiore può prevalere su uno superiore):

| Priorità | Metrica | Significato |
|----------|---------|-------------|
| 1 | **Max diff** | La più grande differenza di punteggio tra le partite — nessuna singola partita dovrebbe essere assurdamente sbilanciata. |
| 2 | **Signed spread** | La differenza tra la somma firmata netta più alta e quella più bassa per giocatore. La somma firmata di un giocatore è il totale di (punteggio della propria squadra − punteggio avversario) in tutte le sue partite; uno spread elevato significa che alcuni giocatori ottengono sistematicamente abbinamenti favorevoli o sfavorevoli. |
| 3 | **Max absolute signed sum** | Il singolo giocatore la cui somma firmata netta è più lontana da zero — l'individuo più avvantaggiato o svantaggiato dal calendario. |
| 4 | **Total abs diff** | Somma delle differenze di punteggio in tutte le partite — criterio di spareggio per la regolarità complessiva. |

### Come funziona

**Hill climbing multi-start**: l'algoritmo esegue `num_restarts` (predefinito 300) riavvii indipendenti. Ogni riavvio:
1. Assegna casualmente sia i giocatori maschi che femmine agli slot.
2. Esegue `steps_per_restart` (predefinito 800) tentativi di scambio: a ogni passo una coppia casuale di maschi o femmine viene scambiata, e lo scambio viene mantenuto solo se migliora strettamente l'obiettivo composito.

Il miglior assegnamento trovato in tutti i riavvii viene restituito.

### Output

| File | Descrizione |
|------|-------------|
| `best_matches_assigned.csv` | Calendario completo con nomi reali dei giocatori e punteggi di squadra |
| `balance_heatmap.png` | Heatmap che mostra le differenze di punteggio firmate per ogni giocatore, ordinate dalla peggiore alla migliore |

### Come eseguire

```bash
python player_assign_v1_0.py
```

---

## Script 3 — `make_scoresheet_v1_0.py`

### Cosa fa

Legge `best_matches_readable.csv` e produce un **PDF A4 orizzontale a 2 pagine** pronto da stampare e usare a bordo campo. Ogni pagina contiene tre pannelli affiancati; ogni pannello ha una colonna sinistra con la descrizione della partita e una colonna destra vuota per scrivere il risultato.

### Come funziona

Usa `reportlab` per disegnare direttamente su un canvas con geometria precisa: margini, larghezze dei pannelli, altezze delle righe e divisioni delle colonne vengono tutti calcolati dalle dimensioni della pagina, così il layout si adatta automaticamente a qualsiasi numero di partite. Gli sfondi a righe alternate e un badge numerato per ogni partita rendono il foglio facile da leggere.

### Come eseguire

```bash
# Predefinito: legge best_matches_readable.csv, scrive tournament_scoresheet.pdf
python make_scoresheet_v1_0.py

# Input personalizzato
python make_scoresheet_v1_0.py mio_calendario.csv

# Input e output personalizzati
python make_scoresheet_v1_0.py mio_calendario.csv mio_tabellone.pdf
```

### Output

| File | Descrizione |
|------|-------------|
| `tournament_scoresheet.pdf` | Tabellone stampabile A4 orizzontale a 2 pagine |

---

## Flusso di lavoro tipico

```
1.  Modificare N in mixedmatches_v1_0.py
    python mixedmatches_v1_0.py
        → best_matches_readable.csv  (e heatmap per ispezione)

2.  Modificare nomi e punteggi in player_assign_v1_0.py
    python player_assign_v1_0.py
        → best_matches_assigned.csv
        → balance_heatmap.png        (controllare: l'assegnamento è equo?)

3.  python make_scoresheet_v1_0.py
        → tournament_scoresheet.pdf  (stampare e portare in spiaggia)
```

---

## Riferimento ai file

| File | Prodotto da | Usato da |
|------|-------------|----------|
| `best_matches_readable.csv` | Script 1 | Script 2 e 3 |
| `best_matches_assigned.csv` | Script 2 | — (output finale) |
| `tournament_scoresheet.pdf` | Script 3 | — (stampare questo) |
| `heatmaps_all.png` | Script 1 | — (per ispezione) |
| `balance_heatmap.png` | Script 2 | — (per ispezione) |
