# Development of a High–Update-Rate VNA Data-Acquisition System for RF Resonance Tracking: From LibreVNA to Keysight E5063A

**Mid-Term Progress Report**

| | |
|---|---|
| **Prepared for** | MIRDC — Metal Industries Research & Development Centre |
| **Author** | Aunuun Jeffry Mahbuubi (`66674041+jeffrymahbuubi@users.noreply.github.com`) |
| **Advisor** | Prof. Che-Wei Lin |
| **Affiliation** | National Cheng Kung University (NCKU) — Wearable Technology and Mobile Healthcare Laboratory (WTMH) |
| **Reporting period** | February 2026 – June 2026 |
| **Date** | July 2026 |

> *Draft v1 — generated against `docs/midterm-report-spec.md`. Figures are marked as
> placeholders `[Figure … : source]`; insert the corresponding image from the cited progress
> deck. All update-rate figures are tagged with their operating point (frequency band + point
> count) because rates are only comparable at an identical operating point.*

---

## Abstract

This project develops a software **data-acquisition (DAQ) system** that continuously tracks the
resonant frequency of a radio-frequency (RF) sensor for a prototype supplied by MIRDC. The sensor's
resonance appears as the minimum of the reflection coefficient (S₁₁); changes in the loading near
the sensor shift this minimum-S₁₁ frequency by ~±0.15–0.25 MHz around ~233.5 MHz, at modulation
rates of ~0.2–0.4 Hz and ~1–2 Hz. The governing engineering requirement is the **measurement update
rate**, which must exceed **20–25 Hz** at the operating point of **200–250 MHz, 801 points**.

Development began on the low-cost, open-source **LibreVNA**. A complete Python/SCPI acquisition
pipeline and a packaged graphical user interface (GUI) were built and validated; however, at the
required operating point the LibreVNA is **host-/GUI-bound to ~7 Hz**, below requirement. The
project therefore **migrated to the commercial Keysight E5063A ENA**, which achieves
**26–39 Hz sustained** at the identical operating point (with a demonstrated capability ceiling of
~133 Hz at reduced point counts) and additionally supports **host-driven calibration**. A
second-generation GUI — architecturally identical to the LibreVNA tool but with an expanded feature
set — was implemented and compiled into a standalone Windows executable for the collaborator. This
report documents the four development phases chronologically and presents the benchmark evidence
that motivated the instrument change.

---

## 1. Introduction

### 1.1 Measurement principle

The system tracks the resonant frequency of an RF sensor operated in a 1-port reflection
configuration. The sensor exhibits a reflection-coefficient minimum (minimum S₁₁, i.e. maximum
return loss) at its resonant frequency, and this minimum shifts as the loading near the sensor
changes. In the present system the resonance lies near **233.5 MHz**, and the frequency excursion of
interest is on the order of **±0.15–0.25 MHz**, appearing at modulation rates of roughly
**0.2–0.4 Hz** and **1–2 Hz**. The data-acquisition task addressed in this report is therefore to
sweep S₁₁ over a narrow band around this resonance and **log the minimum-S₁₁ frequency of every
sweep** as a scalar time-series.

### 1.2 Problem statement and the controlling requirement

The measurement chain is a Vector Network Analyzer (VNA) performing repeated S₁₁ sweeps over a
narrow band centred on the sensor resonance, with software extracting the minimum-S₁₁ frequency of
each sweep. The **binding design constraint is the update rate**: the number of complete sweeps the
system can acquire, process, and log per second. To sample the ~1–2 Hz modulation with adequate
margin and fidelity (rather than merely satisfying the Nyquist minimum), the collaborator's
requirement is an update rate of **greater than 20–25 Hz** at the fixed operating point of
**200–250 MHz span, 801 frequency points**. A second, softer requirement is measurement
**quality** — the trace noise/jitter must remain small enough that the S₁₁ minimum can be located
reliably.

### 1.3 Approach and report roadmap

Two instruments were pursued in sequence. The **LibreVNA** — an open-source, USB-powered VNA
(~US$150, 100 kHz–6 GHz) — was evaluated first on cost grounds. When its achievable update rate at
the required operating point proved insufficient, the project migrated to the **Keysight E5063A ENA**,
a commercial benchtop instrument already available to the collaborator. The remainder of this report
follows the work chronologically through four phases:

| Phase | Period | Instrument | Focus |
|---|---|---|---|
| **1** | Feb 2026 | LibreVNA | Device setup, calibration, Python/SCPI acquisition pipeline, sweep-speed and IFBW characterization |
| **2** | Feb 2026 | LibreVNA | Packaged GUI "Data Collector"; move to the 200–250 MHz / 801-pt monitoring band; exposure of the rate ceiling |
| **3** | May 2026 | E5063A | Feasibility, hardware bring-up, first head-to-head speed comparison |
| **4** | Jun 2026 | E5063A | Performance characterization, host-side calibration, redesigned multi-screen GUI, standalone executable |

Sections 2 (Materials & Methods) and 3 (Results) are organised around these phases; Section 4 draws
conclusions and defines the remaining work.

---

## 2. Materials and Methods

### 2.1 Instruments and specifications

Table 2.1 summarises the two instruments. Both are two-port VNAs operated here in a **1-port S₁₁**
configuration; both are controlled from a Windows host over a standard instrument-control interface
using **SCPI** (Standard Commands for Programmable Instruments).

**Table 2.1 — Instrument specifications.**

| | LibreVNA | Keysight E5063A ENA |
|---|---|---|
| Class / cost | Open-source, ~US$150 | Commercial lab-grade, ~US$10k+ |
| Frequency range | 100 kHz – 6 GHz | Model/option dependent (operated at 200–250 MHz) |
| Form factor | USB-powered, palm-sized | Benchtop (Windows-embedded) |
| Host interface | SCPI over TCP (GUI port 1234) + dedicated streaming servers (ports 19000/19001/19002) | USBTMC-USB488 via VISA (Keysight IO Libraries Suite) |
| Instrument identity | — | S/N `MY54806798`, firmware A.07.06; VISA `USB0::0x2A8D::0x5D01::MY54806798::0::INSTR` |
| Calibration | Manual SOLT (mechanical cal kit) via the LibreVNA-GUI software | Electronic Calibration (ECal, Keysight N7550A), **host-driven** |
| Resonance tracking | Software `argmin(S₁₁)` per sweep | Software minimum-S₁₁ per sweep |
| Data transfer | JSON stream / CSV | Binary IEEE-488.2 block (REAL32 + byte-swap) |

The **calibration philosophy differs** between the two: the LibreVNA is calibrated by manually
connecting Short-Open-Load-Through (SOLT) standards through its own GUI, whereas the E5063A is
calibrated with an **electronic calibration module (ECal)** that can be driven entirely from the
host application — a capability later exploited in the Phase 4 GUI.

### 2.2 Phase 1 — LibreVNA acquisition pipeline (February 2026)

**Calibration and verification.** A full 2-port SOLT calibration (seven standard measurements:
Short/Open/Load on each port plus one Through) was performed with the supplied SMA cal kit. Initial
work used a 2.44 GHz centre / 20 MHz span / 300-point configuration (the 2.4 GHz band was used as a
convenient validation regime). Calibration quality was confirmed by measuring a 50 Ω reference,
obtaining an S₁₁ return loss **> 30 dB** across the band, first through the LibreVNA GUI (v1.6.4) and
then reproduced through the Python/SCPI interface — establishing that the programmatic path matches
the vendor GUI. The calibration setup and the resulting verification trace are shown in Figure 1.

`[Figure 1: SOLT calibration setup and verification — S₁₁ return loss > 30 dB. Source: REPORT/20260203, Figs. 4–5.]`

**Acquisition software.** A Python driver issues SCPI commands to load the calibration file and
perform S₁₁ sweeps. Two acquisition architectures were implemented:

- **Single-sweep mode** — a synchronous, single-threaded loop that triggers one sweep, polls for
  completion (`:VNA:ACQ:FIN?`), then reads the trace. Every SCPI command's response is read back to
  prevent communication-buffer corruption, and no fixed `time.sleep()` delays are used (both would
  otherwise degrade or bias the rate).
- **Continuous mode** — an asynchronous, two-threaded design: a main thread starts acquisition while
  a background thread receives data from the LibreVNA **streaming server on TCP port 19001**. This
  path exists because the SCPI command server, while suitable for configuration, is not designed for
  reading data while the device is actively capturing.

**IFBW parameter sweep.** To characterise the speed–quality trade-off, the intermediate-frequency
bandwidth (IFBW) was varied (50 kHz, 10 kHz, 1 kHz) and, in a later run, across a finer set
(150–1 kHz), recording sweep time, update rate, S₁₁ noise floor, and per-point trace jitter over
**30 consecutive sweeps** for statistical stability.

Scripts: `code/LibreVNA-dev/scripts/` — `1_librevna_cal_check`, `2_s11_cal_verification_sweep`,
`3_sweep_speed_baseline`, `4_ifbw_parameter_sweep`, `5_continuous_sweep_speed`,
`6_librevna_gui_mode_sweep_test`.

### 2.3 Phase 2 — LibreVNA GUI "Data Collector" (February 2026)

The acquisition backend was wrapped in a **PySide6 graphical application** following the
**Model–View–Presenter (MVP)** architecture, with all instrument I/O running on background threads
to keep the interface responsive (Figure 2). The GUI is configured from a calibration file (`.cal`) and a YAML
file (`.yaml`) and exposes two operating modes:

- **Device Sanity Check** — runs full sweeps across one or more IFBW values and reports a summary of
  mean sweep time, noise floor, and trace jitter, verifying the instrument's behaviour for a given
  calibration file.
- **Continuous Monitoring** — repeatedly sweeps and **logs the minimum-S₁₁ frequency (Hz) and
  magnitude (dB) of every sweep** to a Dataflux-compatible CSV file, producing the resonance-shift
  time-series.

Crucially, in this phase the operating point was moved to the **actual monitoring band of
200–250 MHz with 801 points** (frequency step ≈ 62.5 kHz), matching the datasets and operating point
provided by MIRDC. The application was compiled into a standalone
Windows executable ("LibreVNA Data Collector"), requiring no Python environment on the target
machine.

`[Figure 2: LibreVNA Data Collector GUI — menu/config/mode areas and monitoring plot. Source: REPORT/20260226, Figs. 1–5.]`

Code: `code/LibreVNA-dev/gui/7_realtime_vna_plotter_mvp.py` and `gui/mvp/`.

### 2.4 Phase 3 — E5063A feasibility and hardware bring-up (May 2026)

**Feasibility.** It was first confirmed that the E5063A can be controlled from Python over SCPI via
the **PyVISA** library, in a manner analogous to the LibreVNA. The materials handed over by the
collaborator contained **documentation only — no reusable codebase** — so the E5063A acquisition
software was developed from scratch, using a public third-party E5063A/Python project as a reference
and beginning development before physical instrument access to minimise later bring-up errors.

**Bring-up.** The **Keysight IO Libraries Suite** was installed as the VISA driver, and the
instrument was connected to the host by USB (Type-A to Type-B). Connection and identity were
verified programmatically (`*IDN?` → `Keysight Technologies,E5063A,MY54806798,A.07.06`). The
instrument was calibrated and its operating point pinned to match the LibreVNA monitoring
configuration: **200–250 MHz, 801 points, 300 kHz IFBW, −5 dBm, 1-port S₁₁**.

**Acquisition patterns.** Two SCPI acquisition strategies were established: a **host-paced single
sweep** (`:TRIG:SOUR BUS` + `:INIT:IMM` / `:TRIG:SING` / `*OPC?` → binary trace read) and a
**continuous latched read** (using the Operation Status "measuring" bit). Traces are read in
**binary REAL32** format, which is both faster and more robust than ASCII.

Scripts: `code/ena-dev/scripts/` — `probe_e5063a`, `configure_e5063a`, `calibrate_e5063a`,
`bench_e5063a_rates`, `bench_e5063a_realworld`, `check_instrument_state`. SCPI reference:
`docs/E5063A_SCPI_Reference.md`.

### 2.5 Phase 4 — E5063A GUI and packaging (June 2026)

Following collaborator feedback, the single-page GUI concept was **redesigned into a multi-screen
application** — the "**E5063A Data Collector**" — built on the same PySide6 Model–View–Presenter
foundation as the LibreVNA tool but with a substantially expanded feature set. The instrument is
driven through a single VISA session running on a dedicated worker thread, so the interface stays
responsive during USB/SCPI I/O, and the application restores the instrument to its normal live
(free-run) state whenever it connects, stops a run, or closes.

The application is organised as a **three-screen workflow** (Figure 3):

- **Setup screen** — the operator connects to the instrument (which is auto-identified) and defines
  the acquisition: start/stop frequency, number of points, IF bandwidth, and source power. Two
  calibration paths are offered entirely from the host, without touching the front panel: run a
  **1-port S₁₁ electronic calibration (ECal)** using the Keysight N7550A module, or **recall a
  previously saved calibration state** selected from a dropdown of the calibration files stored on
  the instrument. Newly created or recalled calibrations appear in the dropdown automatically, and
  the output data file is named here before acquisition begins.
- **Acquire screen** — provides the two acquisition functions together with a **live S₁₁ preview**
  that free-runs as soon as the operator proceeds to this screen (mirroring the instrument's own
  display) — before, during, and after a recording:
  - *Continuous Monitoring* — the primary function. It repeatedly sweeps and **logs the
    minimum-S₁₁ frequency (Hz) and magnitude (dB) of every sweep** to a Dataflux-compatible CSV file,
    at the continuous-mode update rate characterised in Section 3.3. A recording can run for a fixed
    duration or open-endedly until the operator stops it.
  - *Device Sanity Check* — sweeps across a set of IF-bandwidth values and exports a summary
    workbook (`.xlsx`) of mean sweep time, update rate, noise floor, and trace jitter, so the
    instrument's speed-versus-quality behaviour can be verified for a chosen configuration.
  - The preview provides **display options** — the full trace (magnitude versus frequency) or the
    tracked minimum-S₁₁ scalar — and the monitoring time-series can be switched between
    minimum-frequency and magnitude on its vertical axis.
- **History screen** — lists previous recording sessions and lets the operator revisit each
  recording's configuration (points, IF bandwidth, frequency range) and its collected data.

The application carries the laboratory's (NCKU WTMH) branding as a window/taskbar icon and a header
emblem on every screen, and follows a consistent visual design system for a clean, touch-friendly
layout. It was compiled into a **standalone Windows executable**; the end user need only install the
instrument driver and the Keysight IO Libraries Suite (the native VISA driver, which cannot be
bundled) — no Python environment is required.

`[Figure 3: E5063A Data Collector — Setup / Acquire / History screens. Source: REPORT/20260602 Figs. 3–5 and REPORT/20260604 Videos 1–3.]`

Code: `code/ena-dev/gui/e5063a_data_collector.py` and `gui/mvp/`. Specs: `docs/e5063a-gui-spec.md`,
`docs/e5063a-gui-ux-spec.md`, `docs/e5063a-packaging.md`.

### 2.6 Benchmark methodology

All sweep-rate benchmarks follow a common protocol to enable fair comparison:

- **≥ 30 consecutive sweeps** per configuration; report mean, standard deviation, minimum and
  maximum sweep time.
- Metrics: **mean sweep time (ms)**, **update rate (Hz)** = 1 / mean sweep time, **noise floor (dB)**,
  and **trace jitter (dB)** (the mean over frequency points of the sweep-to-sweep standard deviation).
- **No fixed delays** — completion is detected by polling (`:VNA:ACQ:FIN?` on LibreVNA;
  streaming-callback boundary; or the E5063A operation-status "measuring" bit) rather than by
  `time.sleep()`.
- On the E5063A, traces are read as **binary REAL32** to remove data-transfer from the critical path.

---

## 3. Results

> **Operating-point discipline.** Section 3.1–3.2 report LibreVNA numbers; note that the earliest
> LibreVNA benchmarks (§3.1a) were taken on the **2.43–2.45 GHz / 300-pt** validation band, whereas
> the binding monitoring result (§3.1b) and all E5063A numbers are at **200–250 MHz / 801 pt**.

### 3.1 LibreVNA speed characterization

**(a) Validation band (2.43–2.45 GHz, 300 points).** The single-sweep baseline achieved a mean
update rate of **5.13 Hz** (0.1949 s/sweep). Switching to continuous (streaming) mode raised this to
**19.22 Hz** at 50 kHz IFBW — a **3.7–3.8× speed-up** — and the continuous rate plateaued at
19.22 Hz across the 50–150 kHz IFBW range (i.e. it is sweep-time-bound rather than noise-bound in
that range). Neither mode reached the 25 Hz target on this band. The per-mode sweep time and update
rate across IFBW are shown in Figure 4.

**Table 3.1 — LibreVNA single vs. continuous update rate (2.43–2.45 GHz, 300 pt).**

| IFBW | Single (Hz) | Continuous (Hz) | Speed-up |
|---|---|---|---|
| 150 kHz | 5.11 | 19.22 | 3.76× |
| 50 kHz | 5.15 | 19.22 | 3.73× |
| 10 kHz | 4.08 | 10.00 | 2.45× |
| 1 kHz | 1.24 | 1.57 | 1.27× |

`[Figure 4: LibreVNA sweep-time and update-rate vs. IFBW, single vs. continuous. Source: REPORT/20260205, Figs. 1–2.]`

**(b) Monitoring band (200–250 MHz, 801 points) — the binding result.** At the actual operating
point, the packaged GUI's Continuous Monitoring mode achieves only a **~7 Hz** update rate: the
minimum usable log interval is ≈ **140 ms**, and a 60-second recording yields ≈ 400 samples
(≈ 6.8 Hz effective). The band dependence is significant — the same instrument sweeps at ≈ 15 Hz on
the 2.43–2.44 GHz band but only ≈ 7 Hz at 200–250 MHz — and the 200–250 MHz band is precisely the
one required for the sensor. **This ~7 Hz ceiling is the quantitative motivation for the instrument
change.**

### 3.2 Speed–quality trade-off (IFBW)

Reducing the IFBW lowers the receiver noise bandwidth, which **reduces trace jitter** at the cost of
a longer sweep (lower rate). On the LibreVNA validation band, trace jitter fell from ~2.36 dB
(50 kHz) to ~1.54 dB (10 kHz) to ~0.31 dB (1 kHz), while the update rate fell from 5.12 to 1.24 Hz;
the S₁₁ noise floor remained essentially flat (~−54 dB) across IFBW (Figure 5). The same qualitative trade-off
holds on the E5063A (§3.3). The design implication is that **IFBW is the primary runtime speed knob**,
and — importantly — changing IFBW does **not** invalidate the calibration (unlike changes to
frequency span or point count), so it can be exposed as a user setting.

`[Figure 5: Trace jitter vs. IFBW (per-point and mean). Source: REPORT/20260204, Fig. 4; REPORT/20260205, Fig. 4.]`

### 3.3 E5063A speed characterization

**Single mode.** At the matched operating point (200–250 MHz, 801 pt) and 30 kHz IFBW, the E5063A
single-sweep rate is **18.5 Hz**, versus **5.1 Hz** for the LibreVNA under the same configuration —
a **3.6× improvement** in the slower of the two acquisition modes.

**Continuous mode.** The E5063A's continuous mode was characterised across eight IFBW settings at
the 801-point operating point (Table 3.3). It reaches **39.34 Hz at 300 kHz IFBW** and remains above
the 20 Hz requirement down to ~75 kHz IFBW; at 50 kHz it delivers **26.24 Hz**. The single- and
continuous-mode update rate and the trace jitter are plotted against IFBW in Figure 6.

**Table 3.3 — E5063A continuous-mode performance (200–250 MHz, 801 pt).**

| IFBW | Mean sweep time (ms) | Update rate (Hz) | Trace jitter (dB) |
|---|---|---|---|
| 300 kHz | 25.42 | **39.34** | 0.0042 |
| 150 kHz | 27.95 | 35.78 | 0.0027 |
| 125 kHz | 27.88 | 35.86 | 0.0027 |
| 100 kHz | 30.42 | 32.87 | 0.0021 |
| 75 kHz | 33.68 | 29.69 | 0.0018 |
| 50 kHz | 38.11 | **26.24** | 0.0015 |
| 10 kHz | 99.74 | 10.03 | 0.0007 |
| 1 kHz | 791.80 | 1.26 | 0.0002 |

`[Figure 6: E5063A update rate (single vs. continuous) and trace jitter vs. IFBW. Source: REPORT/20260602, Figs. 1–2.]`

**Capability ceiling (points × span).** A further study varied the point count (101–1001) and the
frequency span. The peak update rate reached **~133 Hz** at the fewest points and highest IFBW, and
a narrower span (230–250 MHz vs 200–250 MHz) yields a higher rate at fixed points (Figure 7). This ~133 Hz
figure is a **capability ceiling at reduced point counts**, not the operating-point rate; the
operating-point (801-pt) figures of 26–39 Hz remain the values relevant to the requirement.

`[Figure 7: E5063A update rate vs. number of points across IFBW, and vs. frequency span. Source: REPORT/20260604, Figs. 1–2.]`

### 3.4 Head-to-head comparison and rationale for the instrument change

At the **identical operating point (200–250 MHz, 801 points)**:

**Table 3.4 — LibreVNA vs. E5063A at the operating point.**

| Comparison | LibreVNA | E5063A | Speed-up |
|---|---|---|---|
| Single mode @ 30 kHz IFBW | 5.1 Hz | 18.5 Hz | **3.6×** |
| Continuous / monitor mode | ~7 Hz | 26.24 Hz (50 kHz) – 39.34 Hz (300 kHz) | **~3.7–5.6×** |

Two factors drove the decision to switch:

1. **The LibreVNA is rate-limited at the required operating point** (~7 Hz in monitor mode),
   comfortably below the 20–25 Hz requirement, and this limit is host-/GUI-bound rather than a
   simple parameter choice.
2. **The prior data-collection approach was throughput-limited.** The collaborator's earlier
   development streamed data through a **web server** (Figure 8), whose throughput did not satisfy the
   requirement; the agreed objective was to move to a **direct USB connection**. The E5063A, driven
   directly over USB/VISA, both eliminates that bottleneck and, as a more capable commercial
   instrument, clears the update-rate requirement with margin.

`[Figure 8: Prior web-server data-collection path (throughput bottleneck). Source: REPORT/20260528, Fig. 1.]`

> **Note on the "noise floor" columns.** The LibreVNA decks report a noise floor of ~−50 dB and the
> E5063A decks ~−1.637 dB; these use different reference definitions and are **not** directly
> comparable. Each should be read within its own instrument's context; the metric used for
> cross-instrument comparison here is update rate (and, secondarily, trace jitter).

### 3.5 GUI capability comparison

Both GUIs share the same architectural "bird's-eye" design — a **PySide6 Model–View–Presenter**
application with a **threaded instrument backend**, driven by a saved calibration/configuration, and
exposing the same two core modes (**Device Sanity Check** and **Continuous Monitoring** with
minimum-S₁₁ logging to a Dataflux-compatible CSV), packaged as a standalone Windows executable. The
**E5063A GUI extends this common base with additional user-facing capability** (Table 3.5); the two
interfaces are placed side by side in Figure 9.

**Table 3.5 — GUI capability comparison.**

| Capability | LibreVNA Data Collector (Phase 2) | E5063A Data Collector (Phase 4) |
|---|---|---|
| Screen layout | Single page (config + preview combined) | **Multi-screen: Setup → Acquire → History** |
| Calibration control | Manual SOLT via the LibreVNA-GUI software | **Host-side ECal control from within the app** |
| Live signal preview | Basic | **Live S₁₁ trace preview** before/during/after collection |
| Session history | — | **Data Collection History** page (revisit past configs + data) |
| Display controls | Fixed | Y-axis / display-mode toggles; two-column configuration grid |
| Update rate at operating point | ~7 Hz | 26–39 Hz (ceiling ~133 Hz) |
| Deployment | Standalone `.exe` | Standalone `.exe` |

In short, the second-generation E5063A GUI is the **same tool, elevated**: the operator can now
configure the instrument, calibrate it, preview the live signal, collect data, and revisit past
sessions — all from one host application, without touching the instrument front panel or a separate
programming environment.

`[Figure 9: Side-by-side of the two GUIs (single-page vs. three-screen). Source: REPORT/20260226 vs. REPORT/20260602 & 20260604.]`

---

## 4. Conclusions and Future Work

### 4.1 Conclusions

- A complete **VNA data-acquisition pipeline** — calibration, Python/SCPI control, single- and
  continuous-sweep acquisition, minimum-S₁₁ resonance logging, and a packaged GUI — was implemented
  and validated on **two instruments**.
- On the **LibreVNA**, the system is fully functional but **rate-limited to ~7 Hz** at the required
  200–250 MHz / 801-point operating point, below the 20–25 Hz requirement.
- Migrating to the **Keysight E5063A** raises the sustained update rate to **26–39 Hz** at the
  identical operating point (a 3.6–5.6× improvement) with very low trace jitter, **meeting the
  requirement with margin**, and enables **host-driven calibration**.
- A **second-generation GUI** was delivered on the same MVP architecture with an expanded feature
  set (multi-screen workflow, host-side calibration, live preview, session history) and compiled
  into a **standalone executable** for the collaborator.

### 4.2 Future work

1. **Real-world validation on the target hardware.** Both GUIs are validated on the
   bench; the E5063A tool must now be exercised on the actual MIRDC-provided device to confirm the
   resonance-tracking behaviour under operational conditions.
2. **Accuracy / frequency-resolution analysis.** Quantify whether the current minimum-frequency
   precision (set by the frequency step Δf = span / (N − 1)) is sufficient for the frequency
   excursion of interest, and evaluate whether a narrower span or interpolation is warranted. See
   `docs/e5063a-20260604-sweep-rate-analysis.md`.
3. **Log-interval auto-mode.** Automatically derive/validate the monitoring log interval against the
   measured mean sweep time so recorded metadata is never misleading.
4. **Operating-point recommendation.** Consolidate the speed–quality trade-off into a recommended
   default (e.g. ~50 kHz IFBW ≈ 26 Hz for a balance of rate and stability, or 300 kHz ≈ 39 Hz for
   maximum rate) for the collaborator's routine use.
5. **(Optional) LibreVNA direct-USB path.** If a low-cost option remains of interest, a direct-USB
   driver bypassing the LibreVNA GUI is projected to reach ~33 Hz.

---

## Appendix A — Source material and data provenance

| Item | Location |
|---|---|
| Report guide/SPEC | `docs/midterm-report-spec.md` |
| Progress decks (PDF+PPTX) | `REPORT/{20260203, 20260204, 20260205, 20260226, 20260522, 20260528, 20260602, 20260604}/` |
| LibreVNA benchmark data | `REPORT/20260204/*.csv`, `REPORT/20260205/*.xlsx` |
| LibreVNA code | `code/LibreVNA-dev/scripts/` (0–8), `code/LibreVNA-dev/gui/` |
| E5063A code | `code/ena-dev/scripts/`, `code/ena-dev/gui/` |
| E5063A packaged executable | `REPORT/20260604/E5063A-Data-Collector/` |
| Companion specs | `docs/project-overview.md`, `docs/e5063a-migration-spec.md`, `docs/E5063A_SCPI_Reference.md`, `docs/e5063a-gui-*.md`, `docs/e5063a-packaging.md` |

*All quantitative values in Section 3 are traceable to the cited progress decks; see
`docs/midterm-report-spec.md` §5 for the per-number provenance table.*

---

## Appendix B — Online Resources / Links

Links provided for reference and for integration into related reporting. All were confirmed
publicly accessible as of July 2026.

**Project and source code**

| Resource | Link |
|---|---|
| Project repository (this work) | https://github.com/jeffrymahbuubi/VNA-Project |
| Third-party E5063A Python/SCPI automation suite (reused as the E5063A control backend; MIT license) | https://github.com/zuwasi/keysight-ena-e5063a-python-automation |

**Keysight E5063A — instrument, driver and documentation**

| Resource | Link |
|---|---|
| E5063A ENA product page | https://www.keysight.com/find/e5063a |
| IO Libraries Suite — VISA driver (required on the data-collection PC) | https://www.keysight.com/find/iosuite |
| E5063A programming / SCPI help files | https://helpfiles.keysight.com/csg/e5063a/programming/programming.htm |
| N7550A Electronic Calibration (ECal) module, DC–4 GHz, 2-port | https://www.keysight.com/us/en/product/N7550A/electronic-calibration-module-ecal-dc-4-ghz-2-port.html |

**LibreVNA**

| Resource | Link |
|---|---|
| LibreVNA firmware + GUI (J. Käberich; GPL-3.0) | https://github.com/jankae/LibreVNA |

**Software libraries**

| Resource | Link |
|---|---|
| PyVISA — Python instrument control (documentation) | https://pyvisa.readthedocs.io |
| PyVISA — source repository | https://github.com/pyvisa/pyvisa |

*Note: `keysight.com/find/iosuite` and `keysight.com/find/e5063a` are stable Keysight vanity URLs
that redirect to the current downloads / product pages.*
