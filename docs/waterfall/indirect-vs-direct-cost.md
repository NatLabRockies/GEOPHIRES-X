# Indirect vs. direct cost in deep-EGS CAPEX

*What GEOPHIRES-X actually models for indirect costs, how the FOAK and NOAK cases
in this analysis decompose into direct vs. indirect, and a defensible all-in
breakdown for deep enhanced-geothermal (EGS) capital cost. Numbers come from the
runs in [`cost_breakdown.py`](cost_breakdown.py); no reruns were done for this
note — it is a synthesis of that output plus the GEOPHIRES source.*

---

## 1. How GEOPHIRES models indirect cost

GEOPHIRES does **not** report indirect cost as a separate line. It applies
**percentage markups embedded inside every direct cost line** (`Economics.py`):

| Markup | Default | Applied to | Code |
|---|---|---|---|
| Indirect Capital Cost Percentage | **12%** | surface plant, field gathering, exploration | `_indirect_cost_factor` |
| Well Drilling & Completion Indirect % | **5%** | the wellfield (drilling) | `_wellfield_indirect_cost_factor` |
| Reservoir Stimulation Indirect % | **5%** | stimulation | `_stimulation_indirect_cost_factor` |
| Contingency Percentage | **15%** | plant, gathering, exploration, stimulation — **not** drilling | `_contingency_factor` |

Each line is grossed up as `direct × (1 + indirect%) × (1 + contingency%)`
(drilling gets the 5% indirect but **no** contingency). These markups represent
**indirect engineering / EPC / project management** (the indirect %) and a
**risk allowance** (contingency). They are active by default, so every cost
figure in `cost_breakdown.xlsx` already includes them.

## 2. What GEOPHIRES does NOT model

- **Permitting, environmental, land, and owner's / development costs** — there is
  no line for these. They are only *weakly* and *implicitly* present (the generic
  12% "indirect" nominally covers "management," but permitting is not named).
- **Interest during construction (IDC) and inflation during construction** —
  fields exist but were **off** in our runs (FCR model, inflation = 0), so
  construction-period financing is not counted.

→ For a credible *all-in* FOAK number these have to be added on top; the model
output is therefore a **lower bound** on true indirect/soft cost.

## 3. Decomposition of our cases (GEOPHIRES output)

Backing the embedded markups out of the eight cost lines:

| | Direct | Pure indirect (eng/EPC/PM) | Contingency | Indirect + contingency |
|---|---|---|---|---|
| **FOAK (~1.6 MW)** | **87%** ($26.0M) | ~7% ($2.0M) | ~7% ($2.0M) | **13%** ($4.0M) |
| **NOAK (~52 MW)** | **82%** ($206M) | ~8% ($20M) | ~10% ($24M) | **18%** ($45M) |

Two non-obvious points:

- **Exploration (22% of FOAK CAPEX) is *not* indirect cost.** In GEOPHIRES it is
  `≈ 1 + 0.6 × one production well` — i.e. mostly a **direct** development cost (a
  confirmation well + geoscience). It collapses to ~3% at NOAK through scale, so
  it behaves like a fixed development cost but should be kept separate from
  "indirect."
- **The indirect share *rises* FOAK→NOAK (13%→18%)** purely from the cost *mix*:
  FOAK is drilling-dominated (drilling carries only 5% indirect and no
  contingency), while NOAK is surface-plant-dominated (full 12% + 15%). So a
  single fixed indirect % is itself a poor assumption — it depends on what is
  being built.

## 4. A defensible all-in breakdown for deep EGS

GEOPHIRES's ~13% (FOAK) / ~18% (NOAK) is a defensible figure **for "indirect
engineering + contingency" only**. For an *all-in* soft-cost view that a
techno-economic reviewer would accept, add the categories GEOPHIRES omits. The
table below combines GEOPHIRES output (✓) with literature-informed adders (~) and
is intended as an indicative, defensible envelope — **not** precise values.

| Cost category | FOAK share of CAPEX | NOAK share | Source |
|---|---|---|---|
| **Direct** (drilling, plant, stimulation, gathering, exploration-well) | **~65–72%** | **~78–82%** | ✓ GEOPHIRES |
| Indirect engineering / EPC / PM | ~7–10% | ~8–10% | ✓ GEOPHIRES (12%/5% markups) |
| Contingency | ~15–25% | ~10–15% | ~ (GEOPHIRES default 15%; FOAK warrants more) |
| Permitting / environmental / land / owner's | ~8–12% | ~5–8% | ~ not in GEOPHIRES |
| Interest during construction (optional) | ~5–10% | ~5–8% | ~ not active in our runs |
| **All-in indirect + soft (excl. IDC)** | **~28–38%** | **~18–25%** | synthesis |

### Why FOAK soft cost is higher
First-of-a-kind projects carry (a) the **largest contingency** — cost-overrun
risk is highest exactly when nothing has been built before — and (b)
disproportionate **permitting and owner's costs** spread over little output. Both
fall with maturity, which is why the all-in soft share **drops** from FOAK to
NOAK even though GEOPHIRES's *modeled* indirect share rises.

## 5. Key recommendations / conclusions

1. **Use ~13% (FOAK) / ~18% (NOAK) only as "indirect engineering + contingency."**
   It is defensible *for that definition* and is a GEOPHIRES output.
2. **Do not relabel contingency as permitting/owner.** That would zero out the
   risk allowance in the case (FOAK) that needs it most — not defensible. Add
   permitting/owner **on top** instead.
3. **For an all-in FOAK soft-cost figure, quote ~25–35%** (indirect ~7–10% +
   contingency ~15–25% + permitting/owner ~10%), and state IDC is excluded.
4. **Don't assume a single fixed indirect %** across the FOAK→NOAK path — the
   modeled share moves with the drilling-vs-plant mix (13%→18%).
5. **Exploration is a direct development cost, not indirect** — keep it separate.

## 6. Reproduce / extend

```bash
python docs/waterfall/cost_breakdown.py     # FOAK & NOAK line-item CAPEX/O&M (xlsx + csv)
```

To turn the literature-informed adders into model output, raise the indirect %
and contingency % inputs and/or enable interest-during-construction and an add-on
owner/permitting CAPEX, then re-run. See also `cost_breakdown.xlsx`,
`heat_per_well_beats_cost_per_well.md`, and `PHYSICS.md`.
