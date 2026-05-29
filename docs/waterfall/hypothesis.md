# Hypotheses & Assumptions — LCOE Sensitivity Waterfall

*Companion to `lcoe_waterfall.py` and `PHYSICS.md`. This file records **exactly
what is assumed and what is changed at each step** of the cumulative sensitivity
analysis, and checks every value against **what is realistically achievable by
2035** for next-generation enhanced geothermal (EGS). Values that did not survive
that check were changed and the model re-run; those changes are noted below.*

The analysis runs GEOPHIRES-X on top of `tests/examples/example1.txt`, starting
from a first-of-a-kind (FOAK) field and applying five levers cumulatively. It
lands at **~$52/MWh — the EXPECTED (central, Monte-Carlo-median) 2035 cost** —
from a **~$192/MWh** FOAK start, while keeping every input within a defensible
2035 envelope.

> **Re-anchored to the median (May 2026).** An earlier version landed at
> **$45/MWh — the DOE "moonshot" target**. The Monte Carlo (§3b) then showed $45
> is only a *favorable* (~P15–P20) outcome — beaten by ~19 % of runs — so the
> waterfall is now anchored on **central, not favorable, cost assumptions** and
> lands at the **$52 median**. The two changes that move $45 → $52 are: cost of
> capital at the **median** fixed charge rate (5.8 %, not an optimistic 5.0 %),
> and plant cost at GEOPHIRES's **own** size correlation (2480 $/kW, no
> economy-of-scale discount). The $45 moonshot remains reachable, just not the
> central expectation.

---

## 1. The "today" FOAK baseline

This is meant to be a *conservative, early-commercial* EGS project — expensive,
small, and not yet optimized.

| Parameter | Value | Hypothesis / rationale | 2035-realistic? |
|---|---|---|---|
| Reservoir model | Multiple parallel fractures (EGS) | Standard EGS heat-exchange model in GEOPHIRES | n/a (today) |
| Depth | 3 km | A modest first project depth | ✔ already common |
| Gradient | 50 °C/km (~165 °C) | A good-but-not-flagship resource | ✔ |
| Wells | 1 producer + 1 injector | Single doublet pilot | ✔ |
| Well diameter | 6.625″ | Narrow / telescoped conventional completion | ✔ |
| Flow per well | 40 kg/s | Un-stimulated, modest deliverability | ✔ |
| Productivity/injectivity index | 5 kg/s/bar | Typical un-optimized EGS connectivity | ✔ |
| Fractures / height | 20 / 900 m | Limited stimulated volume | ✔ |
| Plant | Subcritical ORC (binary) | Held constant across **all** steps | ✔ |
| Utilization factor | 0.85 | Conservative baseload availability | ✔ (often higher) |
| Drilling cost factor | **1.7** (FOAK premium) | Early EGS wells run well above the generic cost correlation | ✔ FOAK is expensive |
| Cost of capital (FCR) | **5.8 %** (held throughout) | Central/median fixed charge rate (see §3b); applied to every step | ✔ central, not optimistic |

**Resulting FOAK LCOE: ~$192/MWh, ~1.6 MW net.** This is consistent with
published FOAK EGS estimates (commonly ~$150–200+/MWh), so the *starting point*
is realistic rather than artificially inflated.

---

## 2. Lever-by-lever assumptions and 2035 realism check

Each lever is applied **on top of** the previous state. "Δ" is the LCOE change.

### Lever 1 — Scale (more wells) Δ = −$42/MWh
- **Change:** production/injection wells 1 → **4**; drilling cost factor 1.7 → **1.5**.
- **Hypothesis:** "Drill the field, not the well." Fixed costs (exploration,
  pads, interconnection, FOAK engineering) are amortized over more output, and
  drilling several similar wells produces a modest learning credit.
- **2035 realism:** ✔ **Very realistic — already happening.** Fervo's Cape
  Station is drilling *dozens* of wells; 4 doublets (8 wells, ~6 MW at this
  stage) is a small commercial field. The learning credit (1.7→1.5, ~12 %) is
  modest versus observed drilling learning rates.

### Lever 2 — Temperature Δ = −$75/MWh (largest lever)
- **Change:** depth 3 → **4 km**, gradient 50 → **60 °C/km** (~256 °C average
  production temperature).
- **Hypothesis:** Hotter rock → more exergy per kg → higher conversion
  efficiency. The plant's **heat-to-power efficiency is ~18.9 %** at this
  temperature (a GEOPHIRES output, realistic for subcritical ORC).
- **2035 realism:** ✔ **Realistic for a targeted high-gradient site, with a
  caveat.** 60 °C/km is well above the continental average (~25–30 °C/km) but is
  exactly what next-gen developers target: Utah FORGE and Fervo's Utah sites sit
  at ~70 °C/km. 256 °C at 4 km is an attractive but genuine deep-EGS resource —
  and crucially **below** superhot/supercritical (>374 °C), so no exotic
  materials are assumed.
- **⚠ Caveat (documented, not hidden):** this is a *site-selection* assumption,
  not a generic one. A cooler 52 °C/km site lands at ~$53/MWh instead of $45 (see
  §3). The temperature is the single biggest swing factor in the whole analysis.

### Lever 3 — Monobore + laterals → flow → turbine Δ = −$12/MWh
- **Change:** diameter 6.625″ → **8.5″**; flow 40 → **80 kg/s**; PI/II 5 → **10
  kg/s/bar**; plant cost set to **2480 $/kW**.
- **Hypothesis:** A wider monobore plus horizontal/multilateral laterals push
  more flow per well at low parasitic pumping (friction ∝ 1/diameter⁵). The bar
  is almost entirely the flow → power jump — in the central case we assert **no**
  turbine economy-of-scale discount.
- **2035 realism:**
  - Flow **80 kg/s/well**: ✔ **demonstrated** — Fervo has reported ~80–100 kg/s
    from horizontal EGS wells. This is at the achievable frontier, not beyond it.
    *(Sensitivity: dropping to 65 kg/s costs ~$4/MWh.)*
  - PI/II **10**: ✔ **lowered from an earlier 15 after this check** — 15 was
    optimistic; 10 is a solid-but-realistic stimulated value. *(Sensitivity:
    LCOE is nearly insensitive to PI here because pumping is small — PI 15→8
    moves it <$0.3/MWh — so the conservative value costs nothing.)*
  - Plant **2480 $/kW**: ✔ **central** — this is GEOPHIRES's *own* size-correlated
    estimate for this plant, i.e. **no asserted discount**. Utility ORC binary
    plants run ~$2000–3000/kW. *(Earlier versions used 1200 $/kW — rejected as
    ~half the correlation — then 2300 $/kW — a modest favorable discount; the
    central case removes the discount.)*

### Lever 4 — Subsurface (lower drawdown) Δ = −$8/MWh
- **Change:** fractures 20 → **60**, fracture height 900 → **1000 m** (larger
  heat-exchange area).
- **Hypothesis:** A larger, well-distributed fracture network (more frac stages
  along multilateral laterals) keeps produced-fluid temperature high over the
  30-year life. With the small baseline network the reservoir draws down; with
  the larger one it stays near-isothermal.
- **2035 realism:** ✔ **realistic geometry, corrected after this check.** An
  earlier version used 1500 m fracture height, which is geologically tall;
  testing showed **1500/40, 1000/60 and 800/80 give identical results** (the
  reservoir is already thermally stable), so the value was changed to the more
  defensible **60 fractures × 1000 m**, representing many frac stages from
  horizontal laterals rather than implausibly tall single fractures.

### Lever 5 — Drilling cost (ROP + FOAK→NOAK) Δ = −$3/MWh
- **Change:** drilling cost factor 1.5 → **1.2**.
- **Hypothesis:** Faster penetration, real-time measurement-while-drilling, the
  simpler monobore casing program, and learning-by-doing lower $/well.
- **2035 realism:** ✔ **deliberately conservative.** Factor 1.2 keeps a **~20 %
  premium over the generic well-cost correlation** — i.e. a 4 km deep, 256 °C
  NOAK well is *not* assumed cheaper than a conventional well. The implied cost
  is **~$7.9M/well**, which is realistic-to-conservative for a deep hot well by
  2035 (Fervo is already near ~$5M for shallower, cooler wells). We explicitly
  did **not** drive the factor below 1.0.

---

## 3. Realism verification summary

| Assumption | Final value | 2035 benchmark | Verdict | Action taken |
|---|---|---|---|---|
| Field size | 4 doublets / ~52 MW | Fervo Cape: dozens of wells | Realistic | kept |
| Gradient / temperature | 60 °C/km / ~256 °C | FORGE & Fervo Utah ~70 °C/km | Realistic *for a targeted site* | kept + caveat |
| Flow per well | 80 kg/s | Fervo ~80–100 kg/s demonstrated | Realistic (frontier) | kept |
| Productivity index | 10 kg/s/bar | stimulated EGS | Realistic | **lowered 15→10** |
| Plant cost | 2480 $/kW | ORC binary $2000–3000/kW | Central (= GEOPHIRES correlation) | **raised 2300→2480 (no discount)** |
| Fracture network | 60 × 1000 m | multilateral frac stages | Realistic | **changed from 40 × 1500 m** |
| Drilling cost | factor 1.2 (~$7.9M/well) | Fervo trending to ~$5M (shallower) | Conservative | kept (not driven <1.0) |
| Efficiency | 18.9 % | subcritical ORC at 256 °C | Realistic | kept |
| Cost of capital | FCR **5.8 %** (held throughout) | central NOAK financing | Central (median) | **raised 5.0→5.8 % (re-anchor)** |

**Net result of the realism pass:** the engineering inputs were tightened to
realistic values (PI 15→10; fracture geometry 40×1500 m → 60×1000 m; plant
1200→2300→2480 $/kW), and the two *favorable* cost assumptions were finally moved
to their **central** values (plant cost to the GEOPHIRES correlation; cost of
capital 5.0→5.8 %). With those central values the stack lands at **$52.3/MWh**,
the Monte Carlo **median** (§3b) — the expected case, not a favorable one.

---

## 3b. Robustness: tornado + Monte Carlo (`tornado_montecarlo.py`)

The waterfall is a single deterministic path. To test how sensitive the $45/MWh
endpoint really is, `tornado_montecarlo.py` perturbs the NOAK endpoint two ways.

### Tornado — one driver at a time

Each waterfall category — **plus cost of capital, which the waterfall excluded** —
is swung between a favorable and an unfavorable but realistic 2035 value, holding
everything else at the NOAK base ($45). Ranges:

| Driver (tornado category) | Favorable | NOAK base | Unfavorable |
|---|---|---|---|
| Temperature (gradient) | 68 °C/km | 60 | 52 |
| **Cost of capital (FCR)** | 4 % | 5 % | 9 % |
| Monobore→flow→turbine | flow 92 kg/s, plant 2000 $/kW | 80 / 2300 | flow 66, plant 2800 |
| Subsurface / drawdown | 100 frac × 1200 m | 60 × 1000 | 30 × 650 |
| Drilling cost (factor) | 0.95 | 1.2 | 1.5 |
| Scale / field size | 6 doublets | 4 | 3 |

**Result (`tornado.png`):** ranked by swing —

1. **Cost of capital — by far the largest ($39 ↔ $70, swing ~$31).** This
   confirms the earlier critique: the single biggest LCOE lever is *financing*,
   not engineering, and the waterfall omitted it on purpose. The moonshot is far
   more sensitive to the discount rate than to any physics lever.
2. Flow + turbine bundle ($39 ↔ $54) and temperature ($40 ↔ $53) — the dominant
   *engineering/resource* levers, as expected.
3. **Subsurface is asymmetric and downside-only ($45 ↔ $59):** a good reservoir
   cannot push below base (the base is already near-isothermal) but a bad one
   adds ~$14/MWh. Reservoir performance is a *risk to manage*, not an upside —
   exactly as argued in `PHYSICS.md`.
4. Drilling cost and field size are comparatively small swings at this endpoint.

### Monte Carlo — all drivers varied simultaneously

800 GEOPHIRES runs, each drawing every driver independently from a **triangular
distribution** (min, mode = NOAK base, max):

| Driver | min | mode | max |
|---|---|---|---|
| Gradient (°C/km) | 52 | 60 | 68 |
| Flow per well (kg/s) | 66 | 80 | 92 |
| Plant cost ($/kW) | 2000 | 2300 | 2800 |
| Drilling factor | 0.95 | 1.2 | 1.5 |
| Cost of capital (FCR) | 0.04 | 0.05 | 0.09 |
| Productivity/injectivity index | 7 | 10 | 14 |
| Number of fractures | 30 | 60 | 100 |
| Fracture height (m) | 700 | 1000 | 1200 |
| Field size (doublets) | 3 | 4 | 6 |

**Result (`montecarlo.png`, 400 runs):**

| Statistic | LCOE ($/MWh) |
|---|---|
| P10 (favorable) | **42.9** |
| P50 (median) | **52.4** |
| P90 (unfavorable) | **64.9** |
| Mean | 52.9 |
| Share of runs meeting the $45 target | **18.8 %** |

All 400 runs (their sampled inputs + LCOE), these summary statistics, the input
distributions, and the tornado are saved to **`montecarlo_results.xlsx`** (and a
diffable `montecarlo_results.csv`). The draws are reproducible from fixed
per-chunk seeds, so the workbook can be regenerated with
`python tornado_montecarlo.py excel` without re-running GEOPHIRES.

The distribution is **right-skewed**: the median is ~$52, and only ~1 run in 5
actually beats $45. The long upside tail is driven mainly by the **cost-of-capital
and reservoir-drawdown** draws, while the favorable tail is bounded because
several physics levers (especially subsurface) cannot improve much beyond the
already-optimized base.

**Interpretation — this is the most important honest finding of the whole
analysis, and the reason the waterfall was re-anchored.** The engineering-optimum
point ($45/MWh) is **not the expected outcome; it is a favorable (~P15–P20)
case.** The *expected* LCOE under realistic 2035 uncertainty is the median
**~$52/MWh — which is what the deterministic waterfall now reports.** Hitting the
$45 moonshot reliably depends as much on **low-cost financing** (the
cost-of-capital draw) and a **well-behaved reservoir** as on the engineering
levers. The honest framing: "$52 is the central expectation; $45 is achievable
but requires several things to go right at once."

---

## 4. Honest caveats carried into the slide

1. **Temperature is a site-selection assumption.** The headline depends on a
   high-gradient (~60 °C/km) resource. On a merely good site (~52 °C/km) the
   endpoint is ~$53/MWh. State this as "for the high-gradient sites next-gen
   geothermal targets," not as a generic national number.
2. **Three inputs are assumptions, not GEOPHIRES outputs:** plant $/kW, the
   drilling cost factors, and cost of capital. All are held at **central** values
   (plant = the model's own correlation; drilling above a generic well cost; FCR
   at the median 5.8 %) so the endpoint is the expected case, not a favorable one.
3. **Cost of capital is the dominant lever and is now included (held constant).**
   The tornado shows FCR swings the endpoint more than any physics lever
   (≈$39↔$70 over 4–9 %). It is held *constant* at the central 5.8 % rather than
   made a waterfall bar, because it is a *financing* story, not physics; its full
   effect is shown in the tornado/Monte Carlo. The $45 moonshot is essentially
   the same project financed cheaply (~5 %) and with a small plant-cost discount.
4. **Flow is at the demonstrated frontier (80 kg/s).** Achievable today in the
   best wells; assuming it as the field-wide norm by 2035 is a genuine (but
   defensible) bet on stimulation/lateral technology maturing.

---

## 5. Reproducing

```bash
python docs/waterfall/lcoe_waterfall.py
```

Produces `lcoe_waterfall.png` and `lcoe_waterfall.csv`. All lever definitions and
magnitudes live at the top of the script; change them there and re-run to test
alternative hypotheses.
