# Heat per well beats cost per well

*Why next-generation geothermal wins on **energy per well**, not **cost per
well** — and why that makes the "drilling cost" lever look deceptively small in
the LCOE waterfall. All numbers come from GEOPHIRES-X; the full line-item
breakdown is in [`cost_breakdown.xlsx`](cost_breakdown.xlsx).*

---

## The conventional wisdom is correct — at first-of-a-kind scale

Everyone says **drilling dominates geothermal capital cost**, and GEOPHIRES
agrees. For the conservative FOAK case (~1.6 MW), drilling & completion is
**49 % of total CAPEX** — by far the largest single line. So far, so expected.

| FOAK CAPEX line | Share | LCOE contribution |
|---|---|---|
| **Drilling & completion** | **49 %** | **$72/MWh** |
| Exploration | 22 % | $33/MWh |
| Surface power plant | 20 % | $29/MWh |
| Stimulation | 5 % | $7/MWh |
| Field gathering | 3.5 % | $5/MWh |

## So why does the "drilling cost" lever only move LCOE by ~$3?

In the cost-reduction waterfall, the explicit *drilling-cost* lever (a ~20 % cut
in $/well from rate-of-penetration and learning) is worth only **−$3/MWh** — tiny
next to Temperature (−$75) or the flow bundle (−$12). If drilling dominates
CAPEX, shouldn't cutting it dominate the savings?

The resolution is the LCOE definition itself:

```
            FCR · CAPEX  +  annual O&M           cost per well
   LCOE  =  ───────────────────────────   ∝   ───────────────────
              annual net electricity            energy per well
```

There are **two** ways to cut a well's contribution to $/MWh:

1. **Numerator — make the well cheaper** ($/well). This is the drilling-cost
   lever. It is real but bounded: a well is a hole in hot rock, and there is a
   floor to what it costs.
2. **Denominator — make the well produce more energy** (MW·h per well). This is
   effectively unbounded by comparison, and it is where next-gen geothermal wins.

**Next-gen geothermal attacks the denominator**, and the waterfall books that
win under *Temperature* and *Flow*, not under *Drilling cost*.

## The evidence: cost per well went *up*; energy per well went up ~8×

Comparing the FOAK well to the NOAK well in GEOPHIRES:

| Metric | FOAK (~1.6 MW) | NOAK (~52 MW) | Change |
|---|---|---|---|
| Drilling **cost per well** | $7.4M | $7.9M | **+7 % (rose!)** |
| Net power **per well** | ~1.6 MW | ~13 MW | **~8× more** |
| Drilling **$/MWh** contribution | $72/MWh | $9.6/MWh | **−87 %** |
| Drilling **share of CAPEX** | 49 % | 25 % | halved |
| Total **CAPEX per kW** | ~$18,900/kW | ~$4,840/kW | **−74 %** |

The NOAK well is **more** expensive to drill, not less — it is deeper (4 km vs
3 km) and wider (8.5″ vs 6.6″). Yet its contribution to LCOE collapses, because
the *same drilling dollars are spread over ~8× more energy*. That 8× comes from:

* **Temperature** — hotter fluid carries more exergy per kilogram, so each kg
  produced converts to far more electricity (conversion efficiency rises with
  resource temperature).
* **Flow** — a wider monobore plus horizontal/multilateral laterals push far more
  kilograms per well at low parasitic pumping (well-friction loss scales like
  1/diameter⁵, so a fatter hole flows much more for little extra pump power).

Power per well ≈ **flow × usable enthalpy(T)**. Both factors scale energy per
well *without* scaling drilling cost proportionally. That is the whole game.

## The one-line takeaway

> **Drilling is ~half of first-of-a-kind capital, and we cut its cost-per-MWh by
> ~8× — but almost entirely by getting ~8× more energy per well (hotter rock +
> higher flow), not by drilling cheaper wells. Heat per well beats cost per
> well.**

This is why the strategy is "drill *better* wells," not merely "drill *cheaper*
wells": chase higher-temperature resource and higher per-well flow, and add
enough wells to amortize fixed costs (exploration falls from $33/MWh to $1/MWh
purely through scale).

## Important caveat: the cost frontier *moves*

Cheaper drilling still matters — the −$3/MWh lever is real, and burning off the
FOAK drilling premium is part of the *Scale* lever. But note where the dominant
capital cost ends up at NOAK:

| NOAK CAPEX line | Share | LCOE contribution |
|---|---|---|
| **Surface power plant** | **67 %** | **$25/MWh** |
| Drilling & completion | 25 % | $9.6/MWh |
| Exploration | 3 % | $1.1/MWh |

Once the wells are hot and high-flow, **the power block — not drilling — becomes
the single biggest capital line** (here we deliberately use GEOPHIRES's full
size-correlated plant cost, ~2480 $/kW, with no economy-of-scale discount). So
the cost-reduction frontier shifts: drilling dominates the *first* well; the
*surface plant* dominates the mature field.

---

## Reproduce

```bash
python docs/waterfall/cost_breakdown.py     # writes cost_breakdown.xlsx (+ .csv)
```

The workbook has three sheets — `overview`, `capital_costs`, `om_costs` — and
each line item carries its exact `$/MWh` LCOE contribution (the components
reconcile to the GEOPHIRES breakeven price, checked at runtime). See also
`PHYSICS.md` (the per-lever physics) and `hypothesis.md` (assumptions + Monte
Carlo).
