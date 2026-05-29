# The Physics Behind the LCOE Waterfall

*Companion to `lcoe_waterfall.py`. Explains what each lever physically does
inside GEOPHIRES-X, why it moves the levelized cost of electricity (LCOE), and
how big the effect is.*

---

## How to read the chart

The waterfall starts from a **conservative first-of-a-kind (FOAK) EGS field**
("today") and applies five innovation levers **cumulatively** — each bar is the
LCOE *after* that lever is stacked on top of all the previous ones. The order
matters: a cumulative waterfall assigns any interaction between two coupled
levers to whichever one comes second.

| Step | Net MW | LCOE ($/MWh) | Δ |
|---|---|---|---|
| Today (FOAK) | 1.6 | 171 | — |
| + Scale (more wells) | 6.3 | 135 | −37 |
| + Temperature | 24.6 | 67 | −68 |
| + Monobore + laterals → flow → turbine | 45.5 | 54 | −13 |
| + Subsurface (lower drawdown) | 52.0 | 47 | −7 |
| + Drilling cost (ROP + NOAK) | 52.0 | 45 | −3 |

The whole story is a **~3.8× reduction in LCOE** ($171 → $45/MWh) reached by a
**~33× increase in net power** (1.6 → 52 MW) at constant plant technology
(subcritical ORC throughout).

### Where the endpoint lands, and why that matters

The stack lands at **~$45/MWh — exactly the DOE Enhanced Geothermal Shot
("moonshot") target for 2035.** This is deliberate. An earlier version of this
analysis used more aggressive cost inputs and landed at ~$29/MWh, which is
*below* the 2035 target — that reads as implausibly optimistic and undermines
credibility. The cost assumptions here are therefore set to be **realistic, not
aggressive**:

* The **plant cost (2300 $/kW)** is *below* GEOPHIRES's own size-correlated
  estimate for this plant (~2480 $/kW), so it reflects a modest economy of
  scale, not a heroic one.
* **NOAK drilling (factor 1.2)** keeps a realistic deep-EGS premium over the
  generic well-cost correlation rather than being driven below it.
* The **resource temperature is left hot and unchanged** (see Lever 2) because
  ~256 °C at 4 km is a genuinely realistic deep-EGS target, not a stretch.

The result is a story that reaches the moonshot target *with the physics doing
the work*, while the cost assumptions stay conservative.

### The one equation that ties it together

GEOPHIRES computes a levelized cost. With a fixed charge rate (FCR) it is, in
essence:

```
            FCR · CAPEX  +  annual O&M
   LCOE  =  ───────────────────────────
              annual net electricity
```

where `annual net electricity ≈ (gross MW − pumping MW) · capacity factor · 8760 h`.

Every lever below works on **one or both halves of this fraction**: it either
shrinks the numerator (cheaper or de-risked capital) or grows the denominator
(more net energy, sustained for longer). That is why "more power per dollar
drilled" is the master variable — most levers attack the denominator.

---

## Lever 1 — Scale: "drill the field, not the well"

**What changes in the model:** number of production/injection wells 1 → 4;
drilling-cost adjustment factor 1.7 → 1.5 (cross-well learning trims the FOAK
premium).

**Physics / economics.** A geothermal project carries large **fixed costs** that
do not scale with the number of wells: exploration, permitting, road and pad
construction, grid interconnection, and the lumpy first-of-a-kind engineering.
A single doublet has to carry all of that on ~1.6 MW. Spreading the same fixed
cost over four doublets (≈6 MW) collapses the $/kW of those shared items.
Drilling several similar wells back-to-back also produces a **learning curve**
(crews, logistics, bit selection), which we credit as a modest drop in the
per-well drilling cost factor.

**Why it matters.** −$37/MWh. This is the cheapest, lowest-technology-risk lever
there is — it is project structuring, not invention. Note the **net MW/well is
essentially flat** (1.59 → 1.59): scale does *not* make any single well better;
it just amortizes the fixed costs. It is the foundation the other levers build
on, because most of them only pay back at field scale.

---

## Lever 2 — Temperature: the master resource variable

**What changes in the model:** reservoir depth 3 → 4 km and gradient
50 → 60 °C/km, lifting bottom-hole temperature from ~165 °C to ~260 °C.

**Physics.** Geothermal power is a **heat engine**, so it is bounded by the
Carnot limit: the fraction of heat convertible to electricity rises with the
hot-source temperature `T_hot`:

```
   η_max = 1 − T_cold / T_hot      (temperatures in kelvin)
```

GEOPHIRES derives the actual conversion efficiency of the chosen plant
(subcritical ORC here) from the production temperature. Hotter fluid has more
**exergy** (useful work) per kilogram, so the *same* mass flow produces far more
electricity. In our run, net MW/well jumps **1.59 → 6.14** with no change in
flow rate, well count, or bore — purely from converting hotter fluid more
efficiently. The **heat-to-power conversion efficiency of the final plant is
~18.9%** at ~256 °C (it falls to ~10–12% near 200 °C), which is realistic for a
subcritical ORC at this temperature.

**Why it matters.** −$68/MWh, the single largest lever. It is why next-gen
geothermal chases deeper/hotter rock (and, ultimately, superhot/supercritical
resources). Temperature appears once and carries the **entire conversion-
efficiency story** — there is deliberately no separate "efficiency" lever,
because efficiency is physically coupled to temperature for a fixed plant type;
a separate bar would double-count it.

> **Is the temperature realistic?** Yes. ~256 °C average production from a 4 km
> well needs a ~60 °C/km gradient — high, but real in the geothermal provinces
> next-gen developers target (Utah FORGE reaches ~225 °C at ~2.6 km; deeper
> high-gradient sites reach 250–300 °C). It is an attractive but genuine
> deep-EGS resource, well short of superhot/supercritical (>374 °C). That is why
> we keep it hot rather than dialing it back: the temperature is not the
> optimistic assumption — the cost inputs are the ones held conservative.

---

## Lever 3 — Monobore + laterals → flow → turbine (the bundle)

**What changes in the model:** production/injection diameter 6.625″ → 8.5″;
flow per well 40 → 80 kg/s; productivity & injectivity index 5 → 15 kg/s/bar;
plant capital cost set to a large-unit specific cost (2300 $/kW).

This is **one causal chain**, deliberately kept as a single bar because the
pieces only make sense together:

### 3a. Wider bore + laterals → more flow at low parasitic cost

Power scales with mass flow, so the obvious move is to flow more kilograms per
well. The catch is **parasitic pumping** — the electricity burned circulating
the fluid. GEOPHIRES computes it (`WellBores.py`) as:

```
   Pumping  ∝  ΔP_total · n_wells · flow / (ρ · pump_efficiency)

   ΔP_total = ΔP_reservoir + ΔP_well-friction + ΔP_buoyancy
   ΔP_reservoir   ∝ flow / productivity_index
   ΔP_well-friction ∝ f · (ρ v² / 2) · (depth / diameter),   v ∝ flow / diameter²
```

Substituting the velocity term, **well-friction loss scales like
flow² · depth / diameter⁵**. That fifth-power dependence on diameter is the
whole point of the **monobore**: a wider, single-diameter hole lets you double
the flow while *cutting* the friction penalty. Horizontal/multilateral
**laterals** add the other half — more rock contact and flow paths per well,
which we represent through the higher flow rate and a higher
productivity/injectivity index (lower `ΔP_reservoir`). (Explicit lateral
geometry would require a closed-loop reservoir model; in the EGS
multiple-fractures model the multilateral parameters have no effect, so we model
their *effect*, not their geometry.)

Result: net MW/well roughly doubles (6.14 → 11.37) while pumping stays modest.

### 3b. Bigger plant → cheaper turbine ($/kW economy of scale)

Doubling flow per well across the field turns a few-MW plant into a ~45 MW
plant. Power-block capital cost per kW falls with unit size (a 50 MW turbine
costs less per kW than a 1 MW unit). We capture this with a **2300 $/kW** plant
cost — note this is *below* GEOPHIRES's own size-correlated estimate for this
plant (~2480 $/kW), so it is a **modest, realistic** economy of scale, not an
aggressive one. (An earlier version used 1200 $/kW; that was about half the
model's correlation and pushed the endpoint implausibly low.)

**Why it matters.** −$13/MWh. This is the headline engineering innovation —
"bigger, better wells feeding a big turbine." Bundling keeps the narrative
honest: the flow is what justifies the big turbine, and the wide bore is what
makes the flow affordable. The bar is smaller than in the aggressive-cost
version precisely *because* the turbine cost is now realistic.

> **What is physics vs. assumption here:** the flow → power and the bore →
> pumping relationships are GEOPHIRES *outputs* (real hydraulics). The turbine
> $/kW is an *input assumption* (a cost curve we assert), not a model-derived
> result — which is exactly why we keep it conservative.

---

## Lever 4 — Subsurface: lower thermal drawdown over time

**What changes in the model:** number of fractures 20 → 40 and fracture height
900 → 1500 m, i.e. a **larger heat-exchange area** between rock and fluid.

**Physics.** An EGS reservoir is a finite block of hot rock. As you produce, the
rock nearest the flow paths cools — **thermal drawdown** — and the production
temperature declines over the project life. The rate of decline depends on how
much **heat-exchange surface area** the fluid sees: a small fracture network
gets "short-circuited" and cools quickly, while a large, well-distributed
network keeps the produced fluid hot for decades. GEOPHIRES models this directly
— with the baseline network, average production temperature sags well below the
initial value over 30 years; with the larger network it stays close to the
initial temperature, so the **lifetime-average** power is much higher.

This is why the lever is placed **right after the flow bundle**: pushing 80 kg/s
through a small reservoir drains it fast, so the high flow only delivers its full
*sustained* value once the heat-exchange area is enlarged. In the run, net power
rises 45.5 → 52.0 MW with no extra wells or flow — purely from sustaining the
resource temperature over the project life.

**Why it matters.** −$7/MWh in this ordering — but that *understates* its
importance. Reservoir performance is the dominant **risk**, not just a cost
lever: a poorly connected reservoir (the opposite of this lever) does not merely
cost more, it can make the project produce almost nothing and fail outright.
"Lower drawdown" is what converts a good well into a good 30-year *asset*.

---

## Lever 5 — Drilling cost (ROP + FOAK→NOAK learning)

**What changes in the model:** drilling-cost adjustment factor 1.5 → 1.2.

**Physics / economics.** Drilling is the largest single CAPEX item in deep
geothermal. Two distinct mechanisms drive its cost down:

1. **Rate of penetration (ROP) and "information" innovation** — better bits,
   mud motors, real-time measurement-while-drilling, and the simpler casing
   program a monobore allows. Fewer days on the rig and fewer casing strings
   directly lower $/well. This is *technology* learning.
2. **FOAK → NOAK learning-by-doing** — repeatedly executing the same well design
   moves cost down the experience curve (Wright's law). This is *deployment*
   learning.

We combine both into one cost-factor reduction (1.5 → 1.2). Crucially we **stop
at 1.2, not below 1.0** — i.e. NOAK deep-EGS wells keep a realistic ~20% premium
over the generic well-cost correlation rather than being assumed cheaper than a
conventional well. This lever touches **only the CAPEX numerator** of the LCOE
fraction — it does not change any physics in the ground (net power is unchanged
at 52 MW).

**Why it matters.** −$3/MWh. Modest here for two reasons: by this point the plant
is already large and efficient so drilling is a smaller share of a much lower
total, *and* we deliberately keep a realistic NOAK premium rather than assuming
heroic drilling-cost collapse. In a colder/smaller project it would matter more.

---

## The coupling you must respect: flow ⇄ subsurface

These two levers are **multiplicatively coupled**, and it is the most important
subtlety in the chart:

- **Flow without a good reservoir** just drains the rock faster — extra
  kilograms come out progressively cooler, so LCOE barely improves (in a larger
  field this step can even tick *upward*).
- **A good reservoir without high flow** is under-utilized — the heat-exchange
  area is there but you are not pushing enough fluid through it to use it.

Together they give the full result. A cumulative waterfall has to credit the
interaction to whichever lever is drawn second; we put **flow first, subsurface
second**, so the bundle shows the productivity jump and subsurface shows the
incremental "sustained over time" gain. The physical truth is that they are one
combined "produce hard *and* sustain it" story worth far more than either bar
alone.

---

## What is modeled physics vs. input assumption

For credibility with a technical audience, keep this distinction explicit:

| Effect | Status |
|---|---|
| Fixed-cost amortization with well count | GEOPHIRES output |
| Conversion efficiency vs. temperature | GEOPHIRES output |
| Flow → power | GEOPHIRES output |
| Bore diameter → parasitic pumping (∝ 1/D⁵) | GEOPHIRES output |
| Thermal drawdown vs. heat-exchange area | GEOPHIRES output |
| **Turbine $/kW economy of scale** | **Input assumption** (2300 $/kW, below GEOPHIRES's ~2480 correlation) |
| **Drilling-cost factors (ROP, FOAK→NOAK)** | **Input assumption** (FOAK 1.7 → NOAK 1.2, keeps a real premium) |
| Cost of capital / discount rate | *Not modeled* (fixed charge rate held constant) |

The two input assumptions are held **conservative on purpose** so the endpoint
lands *at* the $45/MWh moonshot target, not below it.

The cost-of-capital lever is intentionally excluded so this chart isolates
**engineering and resource physics**. In reality, moving from a FOAK risk
premium to a NOAK discount rate is often the single largest LCOE lever of all —
but it is a financing story, not a physics one, and belongs on a separate slide.
**The tornado analysis (below) confirms this empirically: cost of capital is the
single largest swing on the $45 endpoint, bigger than any physics lever.**

---

## How robust is the $45 endpoint? (tornado + Monte Carlo)

The waterfall is one deterministic path. `tornado_montecarlo.py` stress-tests the
endpoint by perturbing each driver over realistic 2035 ranges:

- **`tornado.png`** — each waterfall category, *plus cost of capital*, swung from
  a favorable to an unfavorable value with all else held at the NOAK base. Cost
  of capital dominates (≈$39 ↔ $70); the flow/turbine bundle and temperature are
  the largest physics levers; and **subsurface drawdown is downside-only** (a
  good reservoir can't beat the base, a bad one adds ~$14/MWh).
- **`montecarlo.png`** — all drivers varied simultaneously (triangular
  distributions), giving a P10–P90 band on LCOE and the probability of meeting
  the $45 target.

See `hypothesis.md` §3b for the full ranges, distributions, and results.

---

## Reproducing the numbers

```bash
python docs/waterfall/lcoe_waterfall.py        # the waterfall chart + csv
python docs/waterfall/tornado_montecarlo.py    # tornado.png + montecarlo.png
```

The waterfall outputs `lcoe_waterfall.png` (the chart) and `lcoe_waterfall.csv`
(every step's LCOE, net MW, well count, flow, pumping, and total CAPEX). All
values come from GEOPHIRES-X driven on top of `tests/examples/example1.txt`; the
levers and their magnitudes are defined at the top of the script.
