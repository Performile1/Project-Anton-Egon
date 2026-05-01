# Recording Guide - Anton Egon Wardrobe

> **Version:** 2.1 (Studio & Harvester integration)
> **Matchar:** `video/wardrobe_manager.py`, `video/animator.py`, `video/micro_movement.py`, `ui/studio.py`
> 
> **Studio:** Kör `start_studio_mac.sh` (Mac) eller `start_studio_windows.bat` (Windows) för att starta webbaserad inspelningsstudio med teleprompter, ghost overlay och realtids audio-meter.

---

## Tekniska Krav (System Specs)

| Parameter | Värde | Källa |
|-----------|-------|-------|
| **FPS** | 20 fps | `AnimatorConfig.target_fps = 20` |
| **Resolution** | 1280×720 (720p) eller 1920×1080 (1080p) | Teams-optimerat |
| **Transition** | 15 frames = **0.75 sekunder** | `WardrobeConfig.transition_frames = 15` |
| **Buffer** | 250ms = 5 frames | `WardrobeConfig.buffer_ms = 250` |
| **Codec** | H.264 | Teams-kompatibelt |
| **Bitrate** | 5–10 Mbps | |
| **Format** | MP4 | |

---

## Utrustning

- **Kamera:** HD-webbkamera eller DSLR (1080p)
- **Ljus:** Ring light eller softbox – konsekvent, diffust ljus
- **Mikrofon:** USB- eller XLR-mikrofon
- **Bakgrund:** Vit vägg (för chroma key i OBS) eller suddig kontorsbakgrund
- **Stativ:** Markera kameraposition med tejp – **får inte flytta sig mellan outfits**
- **Glasögon:** Ha ett par redo (för outfit_glasses varianten)

---

## Recording Setup Checklista

Innan du börjar – gör detta VARJE gång:

1. ☐ Markera kameraposition med tejp (exakt samma för alla outfits)
2. ☐ Kameran i ögonhöjd, framing: huvud + axlar
3. ☐ Samma avstånd till kameran (mät med måttband)
4. ☐ Ljus PÅ – samma inställning hela sessionen
5. ☐ Stäng av alla fönster, gardin för, inga rörliga objekt i bakgrunden
6. ☐ Mikrofon på plats, popfilter monterat
7. ☐ Tyst rum – stäng av AC, telefon på tyst

---

## DEL 1: Video-inspelning (5 outfits × 8 klipp)

### De 5 outfits (från `OutfitType` i wardrobe_manager.py)

| ID | Outfit | Beskrivning |
|----|--------|-------------|
| `outfit_shirt_01` | Skjorta 1 | Vit/ljusblå klädskjorta |
| `outfit_shirt_02` | Skjorta 2 | Annan färg klädskjorta |
| `outfit_tshirt` | T-shirt | Enfärgad t-shirt (solid color) |
| `outfit_glasses` | Glasögon | Valfri skjorta + glasögon |
| `outfit_casual` | Casual | Avslappnat men professionellt |

### Per outfit: Inspelningsschema med EXAKTA tidstämplar

---

#### KLIPP 1: Idle Loop
- **Filnamn:** `outfit_[namn]_idle.mp4`
- **Spela in:** 3 minuter (180 sekunder) – klipp ner till 30–60s bästa loop
- **Tidstämplar:**

| Tid | Instruktion |
|-----|-------------|
| 0:00–0:30 | Sitt still. Titta i kameran. Naturligt ansikte. |
| 0:30–1:00 | Blinka var 3–5:e sekund. Subtila huvudrörelser. |
| 1:00–1:30 | Mikrouttryck: höj ögonbrynen, liten nick. |
| 1:30–2:00 | Kombinera ovan: blink + nick + neutral. |
| 2:00–2:30 | Upprepa bästa sekvensen. |
| 2:30–3:00 | "Safety take" – extra material. |

- **KRITISKT:** Första och sista framen måste vara identiska (för sömlös loop)
- **Tips:** Använd en timer/metronom för konsekvent blinkning

---

#### KLIPP 2: Action – Drink Water
- **Filnamn:** `action_drink_water.mp4`
- **Total längd:** 4.0 sekunder (80 frames @ 20fps)
- **Tidstämplar:**

| Tid | Frames | Instruktion |
|-----|--------|-------------|
| 0:00.00–0:00.75 | 1–15 | **Transition IN:** Börja från exakt idle-position. Börja röra handen. |
| 0:00.75–0:03.25 | 16–65 | **Action:** Lyft glaset, ta en klunk, sänk glaset. |
| 0:03.25–0:04.00 | 66–80 | **Transition UT:** Återgå till exakt idle-position (15 frames). |

---

#### KLIPP 3: Action – Check Phone
- **Filnamn:** `action_check_phone.mp4`
- **Total längd:** 5.0 sekunder (100 frames @ 20fps)
- **Tidstämplar:**

| Tid | Frames | Instruktion |
|-----|--------|-------------|
| 0:00.00–0:00.75 | 1–15 | **Transition IN:** Titta ner mot telefon. |
| 0:00.75–0:04.25 | 16–85 | **Action:** Titta på telefon, reagera subtilt, lägg tillbaka. |
| 0:04.25–0:05.00 | 86–100 | **Transition UT:** Titta upp, återgå till idle. |

---

#### KLIPP 4: Action – Adjust Glasses
- **Filnamn:** `action_adjust_glasses.mp4`
- **Total längd:** 2.0 sekunder (40 frames @ 20fps)
- **Tidstämplar:**

| Tid | Frames | Instruktion |
|-----|--------|-------------|
| 0:00.00–0:00.50 | 1–10 | **Transition IN:** Lyft handen mot ansiktet. |
| 0:00.50–0:01.25 | 11–25 | **Action:** Justera glasögonen (båge eller nos). |
| 0:01.25–0:02.00 | 26–40 | **Transition UT:** Sänk handen, tillbaka till idle. |

- **OBS:** Spela även in denna även för outfits UTAN glasögon (kan simuleras)

---

#### KLIPP 5: Action – Scratch Head
- **Filnamn:** `action_scratch_head.mp4`
- **Total längd:** 3.0 sekunder (60 frames @ 20fps)
- **Tidstämplar:**

| Tid | Frames | Instruktion |
|-----|--------|-------------|
| 0:00.00–0:00.75 | 1–15 | **Transition IN:** Lyft handen. |
| 0:00.75–0:02.25 | 16–45 | **Action:** Klia/dra genom håret kort. "Funderar"-gest. |
| 0:02.25–0:03.00 | 46–60 | **Transition UT:** Sänk handen, idle. |

---

#### KLIPP 6: Action – Look at Notes
- **Filnamn:** `action_look_notes.mp4`
- **Total längd:** 4.0 sekunder (80 frames @ 20fps)
- **Tidstämplar:**

| Tid | Frames | Instruktion |
|-----|--------|-------------|
| 0:00.00–0:00.75 | 1–15 | **Transition IN:** Börja vrida huvudet åt sidan (~45°). |
| 0:00.75–0:03.25 | 16–65 | **Action:** Titta på "sidoskärm/anteckningar". Skanna med ögonen. |
| 0:03.25–0:04.00 | 66–80 | **Transition UT:** Vrida tillbaka till kameran, idle. |

---

#### KLIPP 7: Action – Stretch
- **Filnamn:** `action_stretch.mp4`
- **Total längd:** 3.5 sekunder (70 frames @ 20fps)
- **Tidstämplar:**

| Tid | Frames | Instruktion |
|-----|--------|-------------|
| 0:00.00–0:00.75 | 1–15 | **Transition IN:** Börja röra axlar/nacke. |
| 0:00.75–0:02.75 | 16–55 | **Action:** Subtil stretch. Rulla axlarna, sträck nacken. |
| 0:02.75–0:03.50 | 56–70 | **Transition UT:** Tillbaka till idle. |

---

#### KLIPP 8: Action – Clear Throat
- **Filnamn:** `action_clear_throat.mp4`
- **Total längd:** 2.5 sekunder (50 frames @ 20fps)
- **Tidstämplar:**

| Tid | Frames | Instruktion |
|-----|--------|-------------|
| 0:00.00–0:00.50 | 1–10 | **Transition IN:** Subtil ansiktsrörelse. |
| 0:00.50–0:01.75 | 11–35 | **Action:** Lätt harkla, svälja. Naturligt. |
| 0:01.75–0:02.50 | 36–50 | **Transition UT:** Tillbaka till idle. |

---

### Sammanfattning per outfit

| Klipp | Fil | Längd | Frames |
|-------|-----|-------|--------|
| Idle Loop | `outfit_[namn]_idle.mp4` | 30–60s (inspelning: 3 min) | 600–1200 |
| Drink Water | `action_drink_water.mp4` | 4.0s | 80 |
| Check Phone | `action_check_phone.mp4` | 5.0s | 100 |
| Adjust Glasses | `action_adjust_glasses.mp4` | 2.0s | 40 |
| Scratch Head | `action_scratch_head.mp4` | 3.0s | 60 |
| Look Notes | `action_look_notes.mp4` | 4.0s | 80 |
| Stretch | `action_stretch.mp4` | 3.5s | 70 |
| Clear Throat | `action_clear_throat.mp4` | 2.5s | 50 |
| **TOTALT** | | **~55s actions + idle** | |

**Actions spelas in EN gång** (delas mellan outfits). Idle spelas in PER outfit.

---

## DEL 2: Röstinspelning (50 meningar × 5 emotioner)

### Emotionella lägen (matchar `micro_movement.py` mood states)

| Emotion | Beskrivning | Antal meningar |
|---------|-------------|----------------|
| **Neutral** | Standard professionell ton | 15 meningar |
| **Entusiastisk** | Positiva nyheter, engagemang | 10 meningar |
| **Seriös** | Viktiga besked, varningar | 10 meningar |
| **Frågande** | Frågor, klargöranden | 10 meningar |
| **Empatisk** | Förstående, lugn | 5 meningar |

### Exempelmeningar per emotion

**Neutral (15st):**
1. "Hej, välkommen till mötet."
2. "Låt oss gå igenom agendan."
3. "Baserat på vår senaste analys ser det lovande ut."
4. "Vi har identifierat tre huvudområden att fokusera på."
5. "Jag skickar en sammanfattning efter mötet."
6. "Om vi tittar på tidplanen..."
7. "Det stämmer, vi ligger i fas."
8. "Har ni fått ta del av underlaget?"
9. "Vi fortsätter enligt plan."
10. "Tack för den uppdateringen."
11. "Jag noterar det och återkommer."
12. "Absolut, det kan vi ordna."
13. "Vi behöver säkerställa att alla parter är med."
14. "Låt mig kolla det snabbt."
15. "Perfekt, då kör vi på det."

**Entusiastisk (10st):**
1. "Det här är riktigt bra resultat!"
2. "Fantastiskt, vi har överträffat målen!"
3. "Jag är imponerad av teamets arbete."
4. "Det är precis den lösningen vi behöver!"
5. "Vilken bra idé, vi kör på det!"
6. "Det här kommer göra stor skillnad!"
7. "Spot on, exakt rätt approach!"
8. "Vi är on track och det ser jättebra ut!"
9. "Det var den bästa pitchen jag hört!"
10. "Grattis till teamet, riktigt starkt!"

**Seriös (10st):**
1. "Vi behöver adressera det här omgående."
2. "Tyvärr visar siffrorna en nedåtgående trend."
3. "Det är viktigt att vi agerar nu."
4. "Jag vill vara transparent med utmaningarna."
5. "Vi har ett gap i budgeten som behöver åtgärdas."
6. "Deadlinen är inte förhandlingsbar."
7. "Det finns risker som vi inte kan ignorera."
8. "Vi behöver ta ett steg tillbaka och utvärdera."
9. "Situationen kräver omedelbar uppmärksamhet."
10. "Jag vill inte skönmåla läget."

**Frågande (10st):**
1. "Hur ser ni på den tidplanen?"
2. "Kan du utveckla det lite mer?"
3. "Vad är er uppfattning om budgeten?"
4. "Har ni testat den lösningen tidigare?"
5. "Vilka alternativ har vi?"
6. "Hur påverkar det er leverans?"
7. "Vad menar du med det specifikt?"
8. "Kan vi förtydliga scope:et?"
9. "Finns det en backup-plan?"
10. "Stämmer det att deadline är i juni?"

**Empatisk (5st):**
1. "Jag förstår att det är en utmaning."
2. "Det är helt förståeligt att ni känner så."
3. "Vi hittar en lösning tillsammans."
4. "Jag hör vad du säger och det är viktigt."
5. "Ta den tid ni behöver, vi är flexibla."

### Audio Pre-roll klipp (matchar `audio/pre_roll.py`)

Spela även in dessa korta klipp separat – de används som instant filler:

| Kategori | Text | Längd |
|----------|------|-------|
| Acknowledgment | "Ja, precis." | 0.6s |
| Acknowledgment | "Jag förstår." | 0.7s |
| Acknowledgment | "Absolut." | 0.5s |
| Acknowledgment | "Mm, exakt." | 0.6s |
| Thinking | "Hmm, bra fråga..." | 0.9s |
| Thinking | "Låt mig se här..." | 0.8s |
| Thinking | "Bra att du tar upp det." | 0.9s |
| Thinking | "Ja, det ska jag kolla..." | 1.0s |
| Transition | "Okej, så..." | 0.6s |
| Transition | "Ja, alltså..." | 0.6s |
| Transition | "Om jag minns rätt..." | 0.8s |
| Confirmation | "Absolut, det stämmer." | 0.8s |
| Confirmation | "Ja, precis så." | 0.7s |
| Empathy | "Jag hör vad du säger." | 0.9s |
| Empathy | "Det förstår jag helt och hållet." | 1.1s |

**Spara som:** `audio/pre_roll_clips/[clip_id].wav` (t.ex. `ack_01.wav`, `think_01.wav`)

### Audio Specs

| Parameter | Värde |
|-----------|-------|
| Sample rate | 48 kHz |
| Bit depth | 16-bit |
| Channels | Mono |
| Format | WAV |
| Normalisering | -3 dB peak |

### Audio Inspelnings-tips
- Samma mikrofon-avstånd för ALLA klipp (markera med tejp)
- Rum med minimal eko
- Samma talhastighet som du normalt har i möten
- Pausa 1s före och efter varje mening
- Gör 3 takes per mening – välj bästa

---

## DEL 3: Post-Processing

### Idle Loop Redigering
1. Öppna 3-min inspelningen i redigerare
2. Hitta bästa 30–60s loop (start/slut-frame matchar)
3. Verifiera: spela loopen 10 gånger – inget "hopp"?
4. Exportera med exakt 20 fps, H.264

### Action Videos
1. Trim till exakta frame-antal (se tabell ovan)
2. Verifiera: första framen = idle-position
3. Verifiera: sista framen = idle-position
4. Kör `video/wardrobe_manager.py` seamless_stitch test

### Bakgrundsersättning (OBS Studio)
1. Lägg till "Color Key" eller "Chroma Key"
2. Välj vit bakgrund som key color
3. Justera similarity och smoothness
4. Lägg till önskad bakgrund (Teams-stil, företagslogga, suddig)

---

## Filstruktur

```
assets/
├── video/
│   ├── outfit_shirt_01_idle.mp4    (30-60s loop)
│   ├── outfit_shirt_02_idle.mp4
│   ├── outfit_tshirt_idle.mp4
│   ├── outfit_glasses_idle.mp4
│   ├── outfit_casual_idle.mp4
│   ├── action_drink_water.mp4      (4.0s / 80 frames)
│   ├── action_check_phone.mp4      (5.0s / 100 frames)
│   ├── action_adjust_glasses.mp4   (2.0s / 40 frames)
│   ├── action_scratch_head.mp4     (3.0s / 60 frames)
│   ├── action_look_notes.mp4       (4.0s / 80 frames)
│   ├── action_stretch.mp4          (3.5s / 70 frames)
│   └── action_clear_throat.mp4     (2.5s / 50 frames)
├── audio/
│   ├── voice_neutral_01.wav – voice_neutral_15.wav
│   ├── voice_enthusiastic_01.wav – voice_enthusiastic_10.wav
│   ├── voice_serious_01.wav – voice_serious_10.wav
│   ├── voice_questioning_01.wav – voice_questioning_10.wav
│   ├── voice_empathic_01.wav – voice_empathic_05.wav
│   └── pre_roll_clips/
│       ├── ack_01.wav – ack_04.wav
│       ├── think_01.wav – think_04.wav
│       ├── trans_01.wav – trans_03.wav
│       ├── conf_01.wav – conf_02.wav
│       └── emp_01.wav – emp_02.wav
```

---

## Tidsuppskattning

| Steg | Tid |
|------|-----|
| Setup & kalibrering | 30 min |
| 5 idle loops (3 min inspelning × 5) | 20 min |
| 7 action-klipp (3 takes × 7) | 30 min |
| Outfit-byten (5 byten × 5 min) | 25 min |
| 50 röstmeningar (3 takes × 50) | 45 min |
| 15 pre-roll klipp | 15 min |
| Post-processing & loop-test | 2–3 timmar |
| **TOTALT** | **~5–6 timmar** |

---

## Lagringsbehov

| Typ | Storlek |
|-----|---------|
| 5 idle loops (720p, 30-60s) | ~300–600 MB |
| 7 action-klipp | ~50–100 MB |
| 50 röstmeningar (WAV) | ~100–150 MB |
| 15 pre-roll klipp (WAV) | ~10 MB |
| **TOTALT** | **~500 MB – 1 GB** |

---

## Kvalitetschecklista (innan du stänger av kameran)

- ☐ Alla 5 idle loops inspelade
- ☐ Alla 7 actions inspelade
- ☐ Alla 50 röstmeningar inspelade
- ☐ Alla 15 pre-roll klipp inspelade
- ☐ Start/slut-frame matchar idle för alla actions
- ☐ Ljus konsekvent genom hela sessionen
- ☐ Bakgrund konsekvent (inga skuggor, rörelser)
- ☐ Kameraposition oförändrad
- ☐ Backup av alla filer gjord
