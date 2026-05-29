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
| Today (FOAK) | 1.6 | 160 | — |
| + Scale (more wells) | 6.3 | 127 | −32 |
| + Temperature | 24.6 | 64 | −63 |
| + Monobore + laterals → flow → turbine | 45.5 | 38 | −26 |
| + Subsurface (lower drawdown) | 52.0 | 34 | −5 |
| + Drilling cost (ROP + NOAK) | 52.0 | 29 | −5 |

The whole story is a **~5.5× reduction in LCOE** ($160 → $29/MWh) reached by a
**~33× increase in net power** (1.6 → 52 MW) at constant plant technology
(subcritical ORC throughout).

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
drilling-cost adjustment factor 1.5 → 1.35 (cross-well learning).

**Physics / economics.** A geothermal project carries large **fixed costs** that
do not scale with the number of wells: exploration, permitting, road and pad
construction, grid interconnection, and the lumpy first-of-a-kind engineering.
A single doublet has to carry all of that on ~1.6 MW. Spreading the same fixed
cost over four doublets (≈6 MW) collapses the $/kW of those shared items.
Drilling several similar wells back-to-back also produces a **learning curve**
(crews, logistics, bit selection), which we credit as a modest drop in the
per-well drilling cost factor.

**Why it matters.** −$32/MWh. This is the cheapest, lowest-technology-risk lever
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
efficiently.

**Why it matters.** −$63/MWh, the single largest lever. It is why next-gen
geothermal chases deeper/hotter rock (and, ultimately, superhot/supercritical
resources). Temperature appears once and carries the **entire conversion-
efficiency story** — there is deliberately no separate "efficiency" lever,
because efficiency is physically coupled to temperature for a fixed plant type;
a separate bar would double-count it.

> **Caveat for the slide:** temperature dominates partly because "today" is a
> cool, marginal resource. It is a legitimate worst-case FOAK, but if reviewers
> object, warming the starting resource rebalances the bars.

---

## Lever 3 — Monobore + laterals → flow → turbine (the bundle)

**What changes in the model:** production/injection diameter 6.625″ → 8.5″;
flow per well 40 → 80 kg/s; productivity & injectivity index 5 → 15 kg/s/bar;
plant capital cost set to a large-unit specific cost (1200 $/kW).

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
plant. Power-block capital cost per kW falls steeply with unit size (a 50 MW
turbine costs far less per kW than a 1 MW unit). We capture this by moving the
plant from the default size-correlated cost down to a large-unit specific cost.

**Why it matters.** −$26/MWh. This is the headline engineering innovation —
"bigger, better wells feeding a big, cheap turbine." Bundling keeps the
narrative honest: the flow is what justifies the big turbine, and the wide bore
is what makes the flow affordable.

> **What is physics vs. assumption here:** the flow → power and the bore →
> pumping relationships are GEOPHIRES *outputs* (real hydraulics). The turbine
> $/kW economy-of-scale is an *input assumption* (a cost curve we assert), not a
> model-derived result.

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

**Why it matters.** −$5/MWh in this ordering — but that *understates* its
importance. Reservoir performance is the dominant **risk**, not just a cost
lever: a poorly connected reservoir (the opposite of this lever) does not merely
cost more, it can make the project produce almost nothing and fail outright.
"Lower drawdown" is what converts a good well into a good 30-year *asset*.

---

## Lever 5 — Drilling cost (ROP + FOAK→NOAK learning)

**What changes in the model:** drilling-cost adjustment factor 1.35 → 0.8.

**Physics / economics.** Drilling is the largest single CAPEX item in deep
geothermal. Two distinct mechanisms drive its cost down:

1. **Rate of penetration (ROP) and "information" innovation** — better bits,
   mud motors, real-time measurement-while-drilling, and the simpler casing
   program a monobore allows. Fewer days on the rig and fewer casing strings
   directly lower $/well. This is *technology* learning.
2. **FOAK → NOAK learning-by-doing** — repeatedly executing the same well design
   moves cost down the experience curve (Wright's law). This is *deployment*
   learning.

We combine both into one cost-factor reduction. Note this lever touches **only
the CAPEX numerator** of the LCOE fraction — it does not change any physics in
the ground (net power is unchanged at 52 MW).

**Why it matters.** −$5/MWh. Modest here only because by this point the plant is
already large and efficient, so drilling is a smaller share of a much lower
total. In a colder/smaller project it would matter much more.

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
| **Turbine $/kW economy of scale** | **Input assumption** |
| **Drilling-cost factors (ROP, FOAK→NOAK)** | **Input assumption** |
| Cost of capital / discount rate | *Not modeled* (fixed charge rate held constant) |

The cost-of-capital lever is intentionally excluded so this chart isolates
**engineering and resource physics**. In reality, moving from a FOAK risk
premium to a NOAK discount rate is often the single largest LCOE lever of all —
but it is a financing story, not a physics one, and belongs on a separate slide.

---

## Reproducing the numbers

```bash
python docs/waterfall/lcoe_waterfall.py
```

Outputs `lcoe_waterfall.png` (the chart) and `lcoe_waterfall.csv` (every step's
LCOE, net MW, well count, flow, pumping, and total CAPEX). All values come from
GEOPHIRES-X driven on top of `tests/examples/example1.txt`; the levers and their
magnitudes are defined at the top of the script.
