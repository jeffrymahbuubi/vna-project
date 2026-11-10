# Mid-Term Report SPEC — VNA Data-Acquisition Project (LibreVNA → Keysight E5063A)

> **What this file is.** A living, single-source-of-truth **guide for writing the MIRDC
> mid-term progress report**. It fixes the report's audience, structure, thesis, the
> consolidated facts/figures library, and — most importantly — a **resource & path map**
> so any future writing session can pull the right evidence without re-deriving it.
> This SPEC is **not** the report itself; it is the scaffold that the report is written against.

- **Status:** v2 (2026-07-03) — **full draft written** at `docs/midterm-report-draft.md` and reviewed section-by-section. This file is the guide; the draft is the deliverable.
- **Author:** Aunuun Jeffry Mahbuubi (`66674041+jeffrymahbuubi@users.noreply.github.com`)
- **Advisor:** Prof. Che-Wei Lin
- **Lab:** NCKU — Wearable Technology and Mobile Healthcare Laboratory (WTMH)
- **Collaborator / report audience:** MIRDC (Metal Industries Research & Development Centre); contact "Peter".
- **Created:** 2026-07-02
- **Provenance of facts below:** the 8 progress decks in `REPORT/` (parsed via netmind-parse-pdf),
  the project codebase, the `docs/` specs, and the claude-flow memory namespaces
  (`librevna-vna-project`, `e5063a-research`, `e5063a-migration`).

---

## 1. Report parameters (locked)

| Parameter | Value |
|---|---|
| Document type | Formal technical **progress report** for MIRDC (mid-term) |
| Language | English |
| Tone | Formal, technical, evidence-driven |
| Structure | **Chronological by development phase** (see §4) |
| Source outline template | `REPORT/20260701/Sumary_of_VNA_Work.docx` (skeleton: Introduction → Materials & Methods → Conclusions & Future Work) |
| Scope (4 required themes) | (a) LibreVNA data-acquisition development; (b) E5063A data-acquisition development; (c) instrument specifications + rationale for switching to E5063A; (d) GUI capability comparison (LibreVNA vs E5063A) |

**Reconciling the two structure signals.** The user selected a *chronological-by-phase*
narrative; the `.docx` skeleton is a *scientific-report* skeleton. Resolve by nesting: keep the
scientific top-level frame (Introduction / Materials & Methods / Results / Conclusions & Future
Work) and make the **chronological phases the backbone of the Materials & Methods + Results body**.
See §4 for the concrete merged outline.

**Drafting decisions applied in the written draft (2026-07-03):**
- **Neutral engineering scope.** Clinical/project *motivation* is trimmed throughout (title, abstract, §1.1, §1.2, §2.3, §4.2) — the report is authored from the DAQ-engineer's side; the PM (boss) owns the motivation. Only frequency (Hz) facts are retained. Title reads "…for **RF Resonance Tracking**" (not "Physiological Monitoring").
- **Figures** use a single running sequence **Figure 1–9** (journal style), each with an in-text callout ("…see Figure N") placed just before the figure; placeholders keep `Source: REPORT/…` for image embedding. Tables still use section numbering (2.1, 3.1, 3.3–3.5).
- **§2.5 (E5063A GUI)** expanded to describe the full built feature set (Setup/Acquire/History screens, host ECal + recall, live S₁₁ preview, display toggles, WTMH branding, `.exe`).
- **Appendix B** added: verified-public external links (see §8.6).

---

## 2. One-paragraph thesis (the story the report tells)

> The project builds a **software data-acquisition tool that continuously tracks the resonant
> frequency (minimum-S₁₁ point) of an RF sensor** placed on a MIRDC blood-vessel prototype, so
> that sub-millimetre tissue deformation (breathing ~0.2–0.4 Hz, heartbeat ~1–2 Hz) can be read
> out as a frequency-shift time-series. The controlling requirement is **update rate**: the
> monitoring band is **200–250 MHz at 801 points**, and a useful physiological sampling rate needs
> **> 20–25 Hz**. Development began on the low-cost open-source **LibreVNA**, which — after a full
> Python/SCPI acquisition pipeline and a packaged GUI were built — was shown to be **capped at
> ~7 Hz at that operating point** (host/GUI-bound), below requirement. The project therefore
> **migrated to the commercial Keysight E5063A ENA** already available to the collaborator, which
> reaches **~26–39 Hz continuous at the identical operating point** (peak ~133 Hz at reduced point
> counts) and supports **host-driven calibration**. A second-generation GUI — architecturally the
> same MVP design but with more user-facing features — was built and packaged as a standalone
> executable for the collaborator.

---

## 3. Timeline / phase map (backbone of the narrative)

| Phase | When | Instrument | Report decks | One-line summary |
|---|---|---|---|---|
| **P1 — LibreVNA baseline** | Feb 2026 | LibreVNA | `20260203`, `20260204`, `20260205` | Device setup + SOLT cal; Python/SCPI S11 pipeline; sweep-speed baseline; IFBW sweep; single-vs-continuous benchmark |
| **P2 — LibreVNA GUI + monitor** | Feb 2026 | LibreVNA | `20260226` | Packaged MVP GUI "LibreVNA Data Collector": Device Sanity Check + Continuous Monitoring; moves to 200–250 MHz / 801 pt blood-vessel band; exposes the ~7 Hz ceiling |
| **P3 — E5063A migration** | May 2026 | E5063A | `20260522`, `20260528` | Feasibility/handover (docs-only, code from scratch); first hardware bring-up; first head-to-head speed comparison (3.6× single-mode) |
| **P4 — E5063A GUI + packaging** | Jun 2026 | E5063A | `20260602`, `20260604` | Continuous-mode IFBW characterization (peak 39.34 Hz @ 801 pt); host-side ECal; three-screen GUI redesign; completed 3-feature GUI; points×span study (peak 133 Hz); standalone `.exe` |

*(REPORT dirs `20260202/20260210/20260212/20260224/20260225` hold cal files / screen-recording
videos only — no report deck. Use the videos as demo evidence if needed, not as narrative sources.)*

---

## 4. Prescribed report outline (merged frame + chronological body)

Each subsection lists **what to write** and **which source(s) back it** (see §8 for full paths).

### 1. Introduction
- **1.1 Measurement principle** — RF resonant sensor; minimum-S₁₁ tracking; resonance ~233.5 MHz, shift ±0.15–0.25 MHz at ~0.2–0.4 Hz / ~1–2 Hz modulation. **Neutral engineering scope — do NOT state project motivation** (the PM/boss owns that); keep only the frequency (Hz) facts. *Sources:* memory `project/librevna-dev/project-objective`, deck `20260226`.
- **1.2 The controlling requirement** — update rate > 20–25 Hz at the 200–250 MHz / 801-pt monitoring band; why rate matters (Nyquist vs ~1–2 Hz heartbeat). *Sources:* deck `20260204` (GUIDE.txt target), `20260226`.
- **1.3 Report roadmap** — state the four phases (§3).

### 2. Materials & Methods
- **2.1 Instruments & specifications** — LibreVNA vs E5063A spec table (§6); calibration methods (SOLT manual vs ECal host-driven). *Sources:* decks `20260203`, `20260522`, `20260602`; §6 here.
- **2.2 Phase 1 — LibreVNA acquisition pipeline** — SOLT calibration + verification (RL > 30 dB); Python/SCPI S11 sweep; single vs continuous acquisition architecture (polling vs streaming-callback on port 19001); IFBW parameter sweep method (30 sweeps, mean+std). *Sources:* decks `20260203`, `20260204`, `20260205`; scripts `1_`–`6_`.
- **2.3 Phase 2 — LibreVNA GUI (Data Collector)** — MVP architecture; Device Sanity Check + Continuous Monitoring modes; `.cal`/`.yaml`-driven config; min-S11 logging → Dataflux CSV; packaging. *Sources:* deck `20260226`; `code/LibreVNA-dev/gui/`.
- **2.4 Phase 3 — E5063A bring-up** — feasibility (PyVISA/SCPI, KIOLS); connection/probe; host-side ECal (N7550A); matching the operating point (200–250 MHz / 801 pt / 300 kHz IFBW / −5 dBm / S11); SCPI acquisition patterns (BUS-trigger single; latched continuous). *Sources:* decks `20260522`, `20260528`, `20260602`; scripts `probe/configure/calibrate_e5063a.py`; `docs/E5063A_SCPI_Reference.md`.
- **2.5 Phase 4 — E5063A GUI + packaging** — three-screen MVP redesign; host-side calibration; live trace preview; History; standalone executable. *Sources:* decks `20260602`, `20260604`; `code/ena-dev/gui/`; `docs/e5063a-gui-spec.md`, `docs/e5063a-packaging.md`.
- **2.6 Benchmark methodology** — 30 consecutive sweeps; metrics = mean sweep time, update rate (Hz), noise floor (dB), trace jitter (dB); `:VNA:ACQ:FIN?`/streaming (LibreVNA) vs REAL32-binary + latched status (E5063A); **no fixed `time.sleep()`**. *Sources:* `REPORT/20260204/GUIDE.txt`; memory `phase-3-results`, `realworld-bench-design`.

### 3. Results
- **3.1 LibreVNA speed characterization** — baseline 5.13 Hz single; continuous 19.22 Hz (2.43–2.45 GHz band); **~7 Hz at the 200–250 MHz / 801-pt monitor band** (the binding number). Reproduce Tables/§5. *Sources:* decks `20260204`, `20260205`, `20260226`.
- **3.2 Speed↔quality trade-off** — IFBW vs jitter vs noise floor (both instruments). *Sources:* decks `20260204`, `20260205`, `20260602`.
- **3.3 E5063A speed characterization** — single 18.5 Hz @ 30 kHz; continuous 26.24–39.34 Hz @ 801 pt (8-IFBW table); points×span study, peak 133 Hz. *Sources:* decks `20260528`, `20260602`, `20260604`; `docs/e5063a-20260604-sweep-rate-analysis.md`.
- **3.4 Head-to-head & rationale for switching** — same-operating-point comparison (§7 numbers): LibreVNA ~7 Hz vs E5063A 26–39 Hz; 3.6× single-mode; web-server throughput problem → direct-USB. *Sources:* decks `20260528`, `20260602`; §6/§7 here.
- **3.5 GUI capability comparison** — the "same architecture, more features" table (§9); screenshots/videos. *Sources:* decks `20260226`, `20260602`, `20260604`.

### 4. Conclusions & Future Work
- Achievements: full acquisition pipeline on both instruments; validated E5063A meets the rate requirement; packaged collaborator-ready GUI.
- Open / future: real-world validation on the live blood-vessel prototype; log-interval auto-mode; deeper accuracy (frequency-resolution Δf) analysis; possible LibreVNA USB-direct path (~33 Hz) if staying low-cost. *Sources:* memories `project_e5063a_bloodvessel_accuracy_tradeoff`, `planned-features`; decks `20260226`, `20260604`.

---

## 5. Consolidated facts & figures library (cite these verbatim)

> ⚠ **Operating-point discipline.** Numbers are only comparable at the *same* operating point.
> Early LibreVNA work used the **2.43–2.45 GHz WiFi band, 300 pt** (a learning/validation regime).
> The **actual monitoring band is 200–250 MHz, 801 pt**. Always label which regime a number belongs to.

### 5.1 LibreVNA — 2.43–2.45 GHz, 300 pt (validation regime)
| Metric | Value | Source |
|---|---|---|
| Cal quality (S11 return loss) | **> 30 dB** across band (GUI *and* Python/SCPI) | `20260203`, `20260204` |
| Single-sweep baseline (50 kHz IFBW) | **5.13 Hz** (0.1949 s; std 0.03 Hz) | `20260204` |
| IFBW sweep, single (50/10/1 kHz) | 5.12 / 4.07 / 1.24 Hz; NF −54.11/−53.83/−53.73 dB; jitter 2.36/1.54/0.31 dB | `20260204` |
| Single vs Continuous @ 50 kHz | **5.15 Hz vs 19.22 Hz (≈3.7×)** | `20260205` |
| Continuous plateau (150→50 kHz) | **19.22 Hz** (sweep-time-bound, not noise-bound) | `20260205` |
| Continuous @ 10 kHz / 1 kHz | 10.00 Hz / 1.57 Hz | `20260205` |
| Noise floor (all IFBW) | ~ **−50.5 dB** (flat) | `20260205` |

### 5.2 LibreVNA — 200–250 MHz, 801 pt (monitoring band ← binding case)
| Metric | Value | Source |
|---|---|---|
| Frequency step | ~0.0625 MHz (62.5 kHz/pt) | `20260226` |
| Monitor/continuous rate **(50 kHz IFBW)** | **~7.1–7.4 Hz** (mean ≈ 7.3 Hz; n = 7 runs × 30 sweeps) | `20260226`; raw `code/LibreVNA-dev/data/20260223/` |
| Min usable log-interval | **~140 ms** (cannot beat mean sweep time) | `20260226` |
| 60 s recording | ~400 points → **~6.8 Hz** effective | `20260226` |
| Band dependence | 2.43–2.44 GHz ≈ 15 Hz vs 200–250 MHz ≈ 7 Hz | `20260226` |

> **⚠ Monitoring-band IFBW coverage is a single point.** The ~7 Hz figure is at **50 kHz IFBW only** —
> the only 200–250 MHz / 801-pt data (deck `20260226` + raw `code/LibreVNA-dev/data/20260223/`, 7 collections
> × 30 continuous sweeps) uses one IFBW. **No IFBW sweep was run on the monitoring band**; the full IFBW
> curve exists only on the 2.43–2.45 GHz validation band (§5.1). Only qualitative IFBW notes exist for
> 200–250 MHz (1 kHz "lags", 50 kHz "faster"). A like-for-like IFBW curve vs. the E5063A would need new
> measurement (§11.7).

### 5.3 E5063A — 200–250 MHz, 801 pt (MIRDC operating point)
| Metric | Value | Source |
|---|---|---|
| Single-mode @ 30 kHz IFBW | **18.5 Hz** (vs LibreVNA 5.1 Hz → **3.6×**) | `20260528` |
| **Continuous-mode, 8-IFBW sweep (801 pt):** | | `20260602` |
| &nbsp;&nbsp;300 kHz | **39.34 Hz** (25.42 ms); jitter 0.0042 dB | `20260602` |
| &nbsp;&nbsp;150 kHz | 35.78 Hz; jitter 0.0027 dB | `20260602` |
| &nbsp;&nbsp;125 kHz | 35.86 Hz | `20260602` |
| &nbsp;&nbsp;100 kHz | 32.87 Hz | `20260602` |
| &nbsp;&nbsp;75 kHz | 29.69 Hz | `20260602` |
| &nbsp;&nbsp;50 kHz | **26.24 Hz** (38.11 ms) | `20260602` |
| &nbsp;&nbsp;10 kHz | 10.03 Hz | `20260602` |
| &nbsp;&nbsp;1 kHz | 1.26 Hz (791.8 ms) | `20260602` |
| Noise floor (all IFBW) | ~ **−1.637 dB** (flat) | `20260602` |
| Trace jitter | 0.0002 dB (1 kHz) → 0.0042 dB (300 kHz) | `20260602` |
| Points×IFBW peak (200/250 MHz) | **133 Hz** at fewest points / highest IFBW | `20260604` |
| Span effect (801 pt) | 230–250 MHz (20 MHz span) faster than 200–250 MHz (50 MHz span) | `20260604` |

> **133 Hz vs 39 Hz — not a contradiction.** 39.34 Hz is the **operating-point** figure (801 pt,
> 300 kHz IFBW). 133 Hz is a **capability ceiling** at reduced point counts / highest IFBW. State
> both, but anchor the "meets requirement" claim to **39.34 Hz (300 kHz) / 26.24 Hz (50 kHz) at 801 pt**.

---

## 6. Instrument specifications table (for theme (c))

| | **LibreVNA** | **Keysight E5063A ENA** |
|---|---|---|
| Class | Open-source, low-cost | Commercial lab-grade |
| Approx. cost | ~US$150 | ~US$10k+ |
| Frequency range | 100 kHz – 6 GHz | Model/option-dependent (unit used at 200–250 MHz) |
| Ports | 2-port | 2-port (1-port S11 used) |
| Form factor | USB-powered, palm-sized | Benchtop, Windows-embedded |
| Host interface | SCPI/TCP (GUI port 1234) + streaming servers (19000/19001/19002) | USBTMC-USB488 via VISA (Keysight IO Libraries Suite) |
| VISA resource | — | `USB0::0x2A8D::0x5D01::MY54806798::0::INSTR` |
| Serial / FW | (varies) | `MY54806798` / A.07.06 |
| Calibration | Manual SOLT (cal kit) via LibreVNA-GUI | **Host-driven ECal** (Keysight N7550A) — no front panel |
| Resonance tracking | Software `np.argmin(S11)` | Software min-S11 per sweep |
| Rate @ 200–250 MHz / 801 pt | **~7 Hz** (monitor, host-bound) | **26–39 Hz** continuous (peak 133 Hz reduced-pt) |
| Data format | JSON stream / CSV | Binary REAL32 + SWAP |

**Rationale for the switch (theme (c)) — write as a 4-point argument:**
1. **Requirement:** MIRDC blood-vessel monitoring needs > 20–25 Hz at 200–250 MHz / 801 pt.
2. **LibreVNA ceiling:** best sustained ~7 Hz at that operating point (host/GUI-bound; single mode only 5.13 Hz on the validation band) — **below requirement**.
3. **Prior bottleneck:** the collaborator's earlier development used a **web-server** data path whose throughput was insufficient; the agreed objective was a **direct USB** connection.
4. **E5063A meets it:** the commercial ENA already available to the collaborator reaches **26–39 Hz continuous** at the identical operating point (3.6× single-mode head-to-head) → migrate.

---

## 7. Head-to-head comparison (same operating point: 200–250 MHz / 801 pt)

| Comparison | LibreVNA | E5063A | Speed-up |
|---|---|---|---|
| Single mode @ 30 kHz IFBW | 5.1 Hz | 18.5 Hz | **3.6×** [`20260528`] |
| Monitor/continuous @ operating point | ~7 Hz | 26.24 Hz (50 kHz) – 39.34 Hz (300 kHz) | **~3.7–5.6×** [`20260226`,`20260602`] |

*(For a fully apples-to-apples continuous-vs-continuous row, the cleanest single number is
**LibreVNA ~7 Hz monitor vs E5063A ~26–39 Hz continuous** at 200–250 MHz / 801 pt.)*

---

## 8. Resource & path map (all report source material)

> Repo root = `.../54. LibreVNA Vector Network Analyzer/CODE/VNA-Project/`.
> REPORT root = `.../54. LibreVNA Vector Network Analyzer/REPORT/`.
>
> **Deliverable draft:** `docs/midterm-report-draft.md`  ·  **This guide:** `docs/midterm-report-spec.md`

### 8.1 Progress decks (PDF + PPTX; **parse PDFs with netmind-parse-pdf**)
| Date | PDF path | Phase | Content |
|---|---|---|---|
| 2026-02-03 | `REPORT/20260203/20260203.pdf` | P1 | LibreVNA setup, SOLT cal, verification (RL > 30 dB) |
| 2026-02-04 | `REPORT/20260204/20260204.pdf` | P1 | Python/SCPI validation, sweep-speed baseline, IFBW sweep (+ `GUIDE.txt` requirements) |
| 2026-02-05 | `REPORT/20260205/20260205.pdf` | P1 | Single vs continuous benchmark (+ `.xlsx` data templates) |
| 2026-02-26 | `REPORT/20260226/20260205.pdf` | P2 | LibreVNA GUI Data Collector guide; 200–250 MHz / 801 pt; ~7 Hz monitor |
| 2026-05-22 | `REPORT/20260522/20260522.pdf` | P3 | E5063A feasibility / handover (docs-only) |
| 2026-05-28 | `REPORT/20260528/20260528.pdf` | P3 | E5063A bring-up; 3.6× single-mode comparison; web-server bottleneck |
| 2026-06-02 | `REPORT/20260602/20260602.pdf` | P4 | Continuous 8-IFBW characterization; host ECal; 3-screen GUI redesign |
| 2026-06-04 | `REPORT/20260604/20260604.pdf` | P4 | Completed 3-feature GUI; standalone `.exe`; points×span study (133 Hz) |

Report skeleton: `REPORT/20260701/Sumary_of_VNA_Work.docx`.
Demo videos (optional evidence): `REPORT/2026021{0,2}/`, `REPORT/20260224/`, `REPORT/20260225/*.mp4`.

### 8.2 Data artifacts (for reproducing tables/figures)
- `REPORT/20260204/ifbw_*_traces_*.csv`, `sweep_speed_baseline_*.csv`, `ifbw_sweep_summary_*.csv`
- `REPORT/20260205/single_sweep_test_20260205_225940.xlsx`, `continuous_sweep_test_20260205_230028.xlsx` (the byte-compatible xlsx schema template reused by E5063A benches)
- `code/LibreVNA-dev/data/20260223/` — **LibreVNA monitoring-band raw sweeps** (200–250 MHz / 801 pt, 50 kHz IFBW, 7 collections × 30 continuous sweeps → ~7.3 Hz; per-run `summary.txt`). *This is the source of the §5.2 ~7 Hz figure.*
- `REPORT/20260202/Center_2_4_GHz_Span_20_MHz.cal`, `REPORT/20260203/SOLT_1_2_43G-2_45G_300pt.cal`

### 8.3 Code (methods evidence)
| Area | Path |
|---|---|
| LibreVNA scripts (0–8) | `code/LibreVNA-dev/scripts/` (`1_cal_check`, `2_s11_cal_verification`, `3_sweep_speed_baseline`, `4_ifbw_parameter_sweep`, `5_continuous_sweep_speed`, `6_gui_mode_sweep_test`, `8_plot_monitor_data`) |
| LibreVNA GUI (MVP) | `code/LibreVNA-dev/gui/7_realtime_vna_plotter_mvp.py` + `gui/mvp/` |
| E5063A scripts | `code/ena-dev/scripts/` (`probe_e5063a`, `configure_e5063a`, `calibrate_e5063a`, `bench_e5063a_rates`, `bench_e5063a_realworld`, `check_instrument_state`) |
| E5063A GUI (MVP) | `code/ena-dev/gui/e5063a_data_collector.py` + `gui/mvp/` |
| E5063A packaged exe | `REPORT/20260604/E5063A-Data-Collector/` (+ `code/ena-dev/gui/dist/`) |

### 8.4 Companion specs (deeper detail than the decks)
- `docs/project-overview.md` — LibreVNA project overview
- `docs/e5063a-migration-spec.md` — E5063A migration SPEC (decisions, status table)
- `docs/E5063A_SCPI_Reference.md` — SCPI ground truth ⛔ (never cite `9018-07931…pdf` — mislabeled 4155B manual)
- `docs/e5063a-gui-spec.md`, `docs/e5063a-gui-ux-spec.md`, `docs/e5063a-gui-design-system.md` — GUI build
- `docs/e5063a-packaging.md` — standalone `.exe` packaging
- `docs/e5063a-20260604-sweep-rate-analysis.md` — points×IFBW rate model

### 8.5 Memory (background context, verify before citing — snapshot pre-dates final GUI)
- claude-flow namespaces: `librevna-vna-project`, `e5063a-research`, `e5063a-migration`, **`midterm-report`** (this report's own memories)
- File memory: `MEMORY.md` index + `project_*` / `reference_*` entries (incl. `project_midterm_report_spec.md`)

### 8.6 External links (verified public, 2026-07-03 — compiled in the draft's Appendix B)
- Project repo — https://github.com/jeffrymahbuubi/VNA-Project
- Third-party E5063A automation (backend, MIT) — https://github.com/zuwasi/keysight-ena-e5063a-python-automation
- Keysight E5063A product — https://www.keysight.com/find/e5063a
- Keysight IO Libraries Suite (VISA driver) — https://www.keysight.com/find/iosuite
- E5063A programming help — https://helpfiles.keysight.com/csg/e5063a/programming/programming.htm
- N7550A ECal — https://www.keysight.com/us/en/product/N7550A/electronic-calibration-module-ecal-dc-4-ghz-2-port.html
- LibreVNA (jankae, GPL-3.0) — https://github.com/jankae/LibreVNA  *(note: `librevna.org` does not exist)*
- PyVISA — https://pyvisa.readthedocs.io  (repo https://github.com/pyvisa/pyvisa)

---

## 9. GUI capability comparison (theme (d)) — "same design, more features"

**Bird-eye view (shared architecture — write this as the framing):** both GUIs are **PySide6
Model-View-Presenter** apps with a **threaded (QThread) instrument backend**, driven by a saved
**calibration/config**, exposing the **same two core modes** — *Device Sanity Check* (multi-IFBW
sweep → summary of mean sweep time / noise floor / trace jitter) and *Continuous Monitoring*
(log the **minimum-S₁₁ frequency per sweep** → Dataflux-compatible CSV) — auto-saving timestamped
outputs and packaged as a **standalone Windows executable** with WTMH lab branding.

**Where the E5063A GUI adds capability:**
| Capability | LibreVNA GUI (P2) | E5063A GUI (P4) |
|---|---|---|
| Screen layout | Single page (config + preview together) | **Multi-screen: Setup → Acquire → History** |
| Calibration | Manual SOLT in the LibreVNA-GUI software first | **Host-side ECal control from the app** (no separate software) |
| Live signal preview | Basic | **Live S₁₁ trace preview** before/during/after collection |
| Session history | — | **Data Collection History page** (revisit past configs + data) |
| Display controls | Fixed | Y-axis / display-mode toggles, two-column config grid |
| Update rate | ~7 Hz | 26–39 Hz (peak 133 Hz) |
| Packaging | `.exe` (`LibreVNA Data Collector.exe`) | `.exe` (`E5063A-Data-Collector`, one-directory) |

*Screenshots/videos:* LibreVNA GUI figs in `20260226` (Menu / Frequency / Mode areas, monitor plot);
E5063A GUI in `20260602` (1st config-UI fig; 2nd live-UI was a placeholder) and `20260604` (all three
features as screen-recording videos — the intervening completion).

---

## 10. Writing conventions

- **Units/notation:** S₁₁ (dB), IFBW in kHz, rate in Hz, sweep time in ms; keep 2 decimals for rates.
- **Always tag operating point** on every rate number (band + points) — see §5 warning.
- **Terminology:** "update rate" (Hz) not "FPS"; "trace jitter" = mean over points of cross-sweep std; "noise floor" = mean S11 over sweeps×points; "Continuous Monitoring" = min-S11-frequency logging mode.
- **Naming:** "Keysight E5063A ENA", "LibreVNA"; the tools are "LibreVNA Data Collector" and "E5063A Data Collector".
- **Figures:** prefer reproducing the decks' own tables/plots; cite the deck date as the source.

---

## 11. Cautions & open items (resolve before final)

1. **Deck OCR artifacts (`20260528`):** the parsed script name `bench_e5063aRates.py` and some GitHub/IO-Suite URLs are link-render artifacts. Real script is `code/ena-dev/scripts/bench_e5063a_rates.py`; do not quote the OCR'd URLs.
2. **`133 Hz` framing** — capability ceiling, not the operating-point rate (§5.3 note).
3. **Noise-floor scale mismatch** — LibreVNA decks report ~−50 dB; E5063A decks report ~−1.637 dB. These are different quantities/references (return-loss level vs the E5063A "noise floor" column definition). Do **not** compare the two numbers directly; describe each in its own context.
4. **Memory staleness** — claude-flow migration memories are a late-May/early-June snapshot ("GUI not started"); the GUI is in fact complete/packaged. Trust the decks + repo for status.
5. **Real-world validation gap** — both GUIs are validated on the bench, **not yet on the live blood-vessel prototype** (stated in `20260226` and `20260604`). Frame this honestly as future work.
6. **`E5063A_參考資料` collaborator docs** are in Chinese; translate any quoted specs.
7. **Monitoring-band IFBW gap** — LibreVNA's ~7 Hz is measured at **50 kHz IFBW only** (§5.2); no IFBW sweep exists at 200–250 MHz. A like-for-like IFBW curve vs. the E5063A would need new measurement (optional future work).

---

## 12. How to use this SPEC next session

1. Read this file top-to-bottom; open the phase decks you need from §8.1 (re-parse with netmind only if you need verbatim text).
2. Draft section-by-section per §4, pulling numbers from §5 and the spec table from §6/§7.
3. Keep every rate number tagged with its operating point (§5 warning, §10).
4. Update §5 if any deck is re-measured or a new deck is added; bump the version line in the header.
