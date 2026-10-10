# SAM Economic Models

GEOPHIRES SAM Economic Models leverage [NREL's SAM Financial Models](https://sam.nrel.gov/financial-models.html)
by transforming GEOPHIRES parameters into SAM parameters and running the corresponding SAM model
with [PySAM](https://github.com/NREL/pysam).

## SAM Single Owner PPA

Corresponding SAM Financial
Model: [Power Purchase Agreement (PPA): Single owner](https://sam.nrel.gov/financial-models/utility-scale-ppa)

### Parameters

The following table describes how GEOPHIRES parameters are transformed into SAM parameters, as implemented in
[EconomicsSam.py](https://github.com/softwareengineerprogrammer/GEOPHIRES/blob/274786e6799d32dad3f42a2a04297818b811f24c/src/geophires_x/EconomicsSam.py#L135-L195).
(Note that the source code implementation determines actual behavior in the case of any discrepancies.)

| GEOPHIRES Parameter(s)                                                                                                                          | SAM Category                                           | SAM Input(s)                                                                                                 | SAM Module(s)                     | SAM Parameter Name(s)                                        | Comment                                                                                                                                                                                                                                                                                                                                                     |
|-------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|-----------------------------------|--------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `Maximum Total Electricity Generation`                                                                                                          | Generation Profile                                     | `Nameplate capacity`                                                                                         | `Singleowner`                     | `system_capacity`                                            | .. N/A                                                                                                                                                                                                                                                                                                                                                      |
| `Utilization Factor`                                                                                                                            | Generation Profile                                     | `Nominal capacity factor`                                                                                    | `Singleowner`                     | `user_capacity_factor`                                       | .. N/A                                                                                                                                                                                                                                                                                                                                                      |
| `Net Electricity Generation`                                                                                                                    | AC Degradation                                         | `Annual AC degradation rate` schedule                                                                        | `Utilityrate5`                    | `degradation`                                                | Percentage difference of each year's `Net Electricity Generation` from `Maximum Total Electricity Generation` is input as SAM as the degradation rate schedule in order to match SAM's generation profile to GEOPHIRES                                                                                                                                      |
| `Total CAPEX`                                                                                                                                   | Installation Costs                                     | `Total Installed Cost`                                                                                       | `Singleowner`                     | `total_installed_cost`                                       | `Total CAPEX` = `Overnight Capital Cost` + `Inflation costs during construction` + `Interest during construction` - `Other Incentives` - `One-time Grants Etc`                                                                                                                                                                                              |
| `Total O&M Cost`, `Inflation Rate`                                                                                                              | Operating Costs                                        | `Fixed operating cost`, `Escalation rate` set to `Inflation Rate` × -1                                       | `Singleowner`                     | `om_fixed`, `om_fixed_escal`                                 | .. N/A                                                                                                                                                                                                                                                                                                                                                      |
| `Royalty Supplemental Payments`                                                                                                                 | Operating Costs                                        | `Fixed operating cost` schedule                                                                              | `Singleowner`                     | `om_fixed`                                                   | Royalty supplemental payments during the operational phase are added to the fixed operating cost according to the schedule.                                                                                                                                                   |
| `Royalty Rate`, `Royalty Rate Escalation`, `Royalty Rate Escalation Start Year`, `Royalty Rate Maximum`; `Royalty Rate Schedule`                | Operating Costs                                        | `Variable operating cost`                                                                                    | `Singleowner`                     | `om_production`                                              | The royalty is modeled as a tax-deductible variable operating expense. GEOPHIRES uses the provided schedule, or calculates a schedule of $/MWh values based on the PPA price and Royalty Rate for each year, with optional escalation, escalation start year, and cap (maximum). This ensures the total annual expense in SAM accurately matches the royalty payment due on gross revenue. |
| `Plant Lifetime`                                                                                                                                | Financial Parameters → Analysis Parameters             | `Analysis period`                                                                                            | `CustomGeneration`, `Singleowner` | `CustomGeneration.analysis_period` | Also used as `Singleowner.term_tenor` when `Debt Tenor` is not provided.                                                                                                                                                                                                                                                                                                                                                      |
| `Inflation Rate`                                                                                                                                | Financial Parameters → Analysis Parameters             | `Inflation rate`                                                                                             | `Utilityrate5`                    | `inflation_rate`                                             | .. N/A                                                                                                                                                                                                                                                                                                                                                      |
| `Discount Rate`                                                                                                                                 | Financial Parameters → Analysis Parameters             | `Real discount rate`                                                                                         | `Singleowner`                     | `real_discount_rate`                                         | .. N/A                                                                                                                                                                                                                                                                                                                                                      |
| `Combined Income Tax Rate`                                                                                                                      | Financial Parameters → Project Tax and Insurance Rates | `Federal income tax rate`\: minimum of {21%, CITR}; and `State income tax rate`: maximum of {0%; CITR - 21%} | `Singleowner`                     | `federal_tax_rate`,  `state_tax_rate`                        | GEOPHIRES does not have separate parameters for federal and state income tax so the rates are split from the combined rate based on an assumption of a maximum federal tax rate of 21% and the residual amount being the state tax rate.                                                                                                                    |
| `Property Tax Rate`                                                                                                                             | Financial Parameters                                   | `Property tax rate`                                                                                          | `Singleowner`                     | `property_tax_rate`                                          | .. N/A                                                                                                                                                                                                                                                                                                                                                      |
| `Fraction of Investment in Bonds`                                                                                                               | Financial Parameters → Project Term Debt               | `Debt percent`                                                                                               | `Singleowner`                     | `debt_percent`                                               | .. N/A                                                                                                                                                                                                                                                                                                                                                      |
| `Inflated Bond Interest Rate`                                                                                                                   | Financial Parameters → Project Term Debt               | `Annual interest rate`                                                                                       | `Singleowner`                     | `term_int_rate`                                              | .. N/A                                                                                                                                                                                                                                                                                                                                                      |
| `Debt Tenor` | Financial Parameters → Project Term Debt | `Tenor` | `Singleowner` | `term_tenor` | Defaults to `Plant Lifetime` if not provided. May not exceed `Plant Lifetime`. Counted from the Commercial Operation Date (COD; Year 1); construction years are not counted. Debt drawn during construction is effectively refinanced as term debt at COD; see [Construction Debt at COD](SAM-EM_Multiple-Construction-Years.html#construction-debt-at-cod). |
| `Depreciation Schedule` | Financial Parameters → Depreciation | `Allocations`: 100% to `20-yr Straight Line` (default) or `5-yr MACRS` | `Singleowner` | `depr_alloc_sl_20_percent`, `depr_alloc_macrs_5_percent` | The entire depreciable basis is allocated to one class. 5-year MACRS is the statutory class for facilities that claim the technology-neutral clean electricity credits (IRC sections 48E and 45Y). SAM counts the resulting early-year tax losses as tax benefits in the years they occur, which assumes the owner can use them (for example, against other taxable income or through a tax equity partner). |
| `Starting Electricity Sale Price`, `Ending Electricity Sale Price`, `Electricity Escalation Rate Per Year`, `Electricity Escalation Start Year` | Revenue                                                | `PPA price`                                                                                                  | `Singleowner`                     | `ppa_price_input`                                            | GEOPHIRES's pricing model is used to create a PPA price schedule that is passed to SAM.                                                                                                                                                                                                                                                                     |
| `Total AddOn Profit Gained`                                                                                                                     | Revenue → Capacity Payments                            | `Fixed amount`, `Capacity payment amount`                                                                    | `Singleowner`                     | `cp_capacity_payment_type = 1`, `cp_capacity_payment_amount` |                                                                                                                                                                                                                                                                                                                                                             |
| `Starting Carbon Credit Value`, `Ending Carbon Credit Value`, `Carbon Escalation Rate Per Year`, `Carbon Escalation Start Year`                 | Revenue → Capacity Payments                            | `Fixed amount`, `Capacity payment amount`                                                                    | `Singleowner`                     | `cp_capacity_payment_type = 1`, `cp_capacity_payment_amount` |                                                                                                                                                                                                                                                                                                                                                             |
| `Starting Heat Sale Price`, `Ending Heat Sale Price`, `Heat Escalation Rate Per Year`, `Heat Escalation Start Year`                             | Revenue → Capacity Payments                            | `Fixed amount`, `Capacity payment amount`                                                                    | `Singleowner`                     | `cp_capacity_payment_type = 1`, `cp_capacity_payment_amount` |                                                                                                                                                                                                                                                                                                                                                             |
| `Starting Cooling Sale Price`, `Ending Cooling Sale Price`, `Cooling Escalation Rate Per Year`, `Cooling Escalation Start Year`                 | Revenue → Capacity Payments                            | `Fixed amount`, `Capacity payment amount`                                                                    | `Singleowner`                     | `cp_capacity_payment_type = 1`, `cp_capacity_payment_amount` |                                                                                                                                                                                                                                                                                                                                                             |
| `Investment Tax Credit Rate`                                                                                                                    | Incentives → Investment Tax Credit (ITC)               | `Federal` → `Percentage (%)`                                                                                 | `Singleowner`                     | `itc_fed_percent`                                            | Note that unlike the BICYCLE Economic Model's `Total capital costs`, SAM Economic Model's `Total CAPEX` is the total installed cost and does not subtract ITC value (if present).                                                                                                                                                                           |
| `State Investment Tax Credit Amount`                                                                                                            | Incentives → Investment Tax Credit (ITC)               | `State` → `Amount ($)`                                                                                       | `Singleowner`                     | `itc_sta_amount`                                             |                                                                                                                                                                                                                                                                                                                                                             |
| `Production Tax Credit Electricity`                                                                                                             | Incentives → Production Tax Credit (PTC)               | `Federal` → `Amount ($/kWh)`                                                                                 | `Singleowner`                     | `ptc_fed_amount`                                             | .. N/A                                                                                                                                                                                                                                                                                                                                                      |
| `Production Tax Credit Duration`                                                                                                                | Incentives → Production Tax Credit (PTC)               | `Federal` → `Term (years)`                                                                                   | `Singleowner`                     | `ptc_fed_term`                                               | .. N/A                                                                                                                                                                                                                                                                                                                                                      |
| `Production Tax Credit Inflation Adjusted`, `Inflation Rate`                                                                                    | Incentives → Production Tax Credit (PTC)               | `Federal` → `Escalation (%/yr)`                                                                              | `Singleowner`                     | `ptc_fed_escal`                                              | If `Production Tax Credit Inflation Adjusted` = True, GEOPHIRES set's SAM's PTC escalation rate to the inflation rate. SAM applies the escalation rate to years 2 and later of the project cash flow. Note that this produces escalation rates that are similar to inflation-adjusted equivalents, but not exactly equal.                                   |
| `Other Incentives` + `One-time Grants Etc`                                                                                                      | Incentives → Investment Based Incentive (IBI)          | `Other`  → `Amount ($)`                                                                                      | `Singleowner`                     | `ibi_oth_amount`                                             | .. N/A                                                                                                                                                                                                                                                                                                                                                      |

.. <RST_Comment>
.. Comment entries of ".. N/A" render as blank in the final RST, by design.
.. This entry value is required because m2r2 (https://pypi.org/project/m2r2/) seems to choke and bail on rendering
.. the entire table when blank comment entries are blank. Make sure to check this doesn't happen when making changes
.. to this file by running `tox -e docs` and opening `dist/docs/SAM-Economic-Models.html` in your browser!
..
.. TODO: Generate this programmatically (like schema generator) to prevent drift between code and documentation.
.. </RST_Comment>

### Limitations

1. The following power plant types/surface applications are not supported: Heat Pump, District Heating, and Reservoir Thermal Energy Storage (SUTRA). Subcritical ORC, Supercritical ORC, Single Flash, Double Flash, Industrial heat, and Absorption Chiller power plant types are supported.
2. Add-ons with electricity and heat are not currently supported. (Add-ons CAPEX, OPEX, and profit are supported.)

## Multiple Construction Years

[Multiple Construction Years example web interface link](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-5)

For projects with extended development timelines, GEOPHIRES SAM Economic Models improve financial accuracy by simulating the pre-revenue
construction phase.
SAM Economic Models account for the timing of capital deployment (Construction CAPEX Schedule), inflation, and Interest
During Construction (IDC)
based on the value of `Construction Years` parameter.
The simulation calculates a capitalized cost at the Commercial Operation Date (COD; Year 1), ensuring that the final
depreciation basis, debt sizing, and resulting metrics (LCOE, IRR, NPV) correctly reflect the time value of money during
construction.
Debt drawn during construction, including capitalized IDC, is effectively refinanced as term debt at COD and repaid over
`Debt Tenor` years starting in Year 1.

See [SAM Economic Models: Multiple Construction Years documentation](SAM-EM_Multiple-Construction-Years.html).

## Add-Ons

[Add-Ons example web interface link](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-3)

SAM Economic Models incorporate add-ons directly, unlike other GEOPHIRES economic models, which calculate separate
extended economics.
Total Add-on CAPEX is added to Total CAPEX.
Total Add-on OPEX is added to Total operating and maintenance costs.
Total AddOn Profit Gained per year is treated as fixed amount Capacity payment revenue.

Add-ons CAPEX, OPEX, and profit are supported.
Add-ons with electricity and heat are not currently supported, but may be supported in the future.

## Royalties

SAM Economic Models can model royalty agreements where compensation is paid to a third party (the "royalty holder").
GEOPHIRES supports two complementary mechanisms for these agreements: **production-based royalties**
(a percentage of the project's gross revenue)
and **supplemental royalty payments** (a scheduled fixed cash flow, such as option payments or land leases).

From the perspective of the project developer (Single Owner), these payments are modeled as tax-deductible expenses to ensure accurate after-tax metrics (NPV, IRR, etc.).
The two mechanisms are mapped to SAM differently:

1. **Production-based royalties**: GEOPHIRES translates the percentage rate into a year-by-year schedule for SAM's Variable operating cost (`om_production`) input, calculated against the PPA price to accurately reflect a cut of the gross revenue.
    1. [Production-based royalties example web interface link](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-4)
1. **Supplemental payments**: These are split between the construction and operational phases. Payments made during construction are capitalized into the project's basis (added to the total installed cost and debt-financed), while payments during the operational phase are treated as fixed O&M expenses (`om_fixed`).
    1. [Supplemental royalty payments example web interface link](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-4b) (also includes production-based royalties specified as a schedule)

Input Parameters:

1. `Royalty Rate` (production-based royalties): The percentage of the project's gross annual revenue paid to the royalty holder. It can be optionally
   escalated by providing `Royalty Rate Escalation` and capped with `Royalty Rate Maximum`, starting at
   `Royalty Rate Escalation Start Year`.
    1. Alternatively, you can provide `Royalty Rate Schedule` to explicitly define the rates over time using the scheduling syntax (see below), beginning at Year 1 (beginning of operations).
1. `Royalty Supplemental Payments`: A scheduled cash flow of absolute payments (in M$) made to the royalty holder. This is useful for modeling option payments, land leases, or minimum fixed royalties.
    1. Scheduling Syntax: Schedules are defined using a `<value> * <years>` duration format. If a duration is omitted, that value becomes the terminal value and repeats for the remainder of the project.
    1. Example:` 1.0 * 3, 0.1 `results in \$1M/year for the first 3 years, dropping to $100k/year for all remaining years.
    1. Note: The `Royalty Supplemental Payments` schedule begins at the first year of construction (unlike `Royalty Rate Schedule`) . If you wish to defer payments until operations begin, pad the front of your schedule with zeros (e.g., `0.0 * 2, 0.5` for a 2-year construction period).
1. `Royalty Holder Discount Rate` (optional): The discount rate used to calculate the Net Present Value (NPV) of the
   royalty holder's income stream. This is separate from the project's main discount rate to reflect the different risk
   profiles of the two parties.

Output Parameters:

1. **Cash Flow**:
    1. The production-based royalty rate schedule is displayed in the `Royalty rate (%)` line item, and its corresponding dollar expense is included in `O&M production-based expense ($)`.
    1. Operational supplemental payments are rolled into the `O&M fixed expense ($)` line item. Pre-revenue supplemental payments are capitalized into the project's `Installed cost ($)`.
1. `Average Annual Royalty Cost`: The developer's average annual royalty expense over the project's lifetime after
   construction is complete (Year 1). The same value is also output as `Royalty Holder Average Annual Revenue`.
1. `Royalty Holder Total Revenue`: The total gross (pre-tax), undiscounted royalty income over the project's lifetime.
1. `Royalty Holder NPV`: The pre-tax Net Present Value of the royalty holder's income stream, calculated using the
   `Royalty Holder Discount Rate`. This is a pre-tax value because the model does not account for the royalty holder's
   specific tax liabilities.

## Carbon Credits

[Carbon Credits Revenue example web interface link](https://gtp.scientificwebservices.com/geophires?geophires-example-id=example_SAM-single-owner-PPA-6_carbon-revenue)

Carbon credits revenue is included in `Capacity payment revenue ($)`.
It is calculated according to the [CalculateCarbonRevenue function in Economics.py](https://github.com/NREL/GEOPHIRES-X/blob/dc7e54a81ac946f2f4f0f7a4f79cdfea7320f532/src/geophires_x/Economics.py#L249-L288).

See relevant parameters and outputs in [GEOPHIRES Parameters documentation](parameters.html#economics):

1. `Do Carbon Price Calculations`
1. `Starting Carbon Credit Value`
1. `Ending Carbon Credit Value`
1. `Carbon Escalation Start Year`
1. `Carbon Escalation Rate Per Year`
1. `Current Grid CO2 production`
1. `Total Avoided Carbon Emissions`

## End Uses and Surface Applications

SAM Economic Models support a variety of geothermal end-use options and surface applications, extending beyond pure electricity generation to include:

* **Electricity**
* **Direct-Use Heat**
* **Cogeneration** (Combined Heat and Power; CHP)
* **Cooling** (Absorption Chiller)

For detailed information on how these different configurations are modeled financially, including cash flow reporting adjustments, CHP cost allocation methodologies, and configuration-specific examples, see the [SAM Economic Models: End Uses and Surface Applications documentation](SAM-EM_End-Uses-and-Surface-Applications.html).

## Examples

1. [Case Study: 500 MWe EGS Project Modeled on Fervo Cape Station](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=Fervo_Project_Cape-7) | [Case Study Documentation](Fervo_Project_Cape-7.html)
1. [SAM Single Owner PPA: 50 MWe](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA)
1. [50 MWe with Add-ons](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-3)
1. [50 MWe with Royalties](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-4)
1. [Royalty Schedule & Supplemental Payments](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-4b)
1. [Multiple Construction Years](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-5)
1. [Carbon Credits](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-6_carbon-revenue)
1. [Cogeneration (Combined Heat and Power; CHP)](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-7_chp)
1. [CHP with Carbon Credits](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-7b_chp-cc)
1. [Direct-Use Heat](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-8_heat)
1. [Cooling (Absorption Chiller)](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-9_cooling)
1. [SAM Single Owner PPA: 400 MWe BICYCLE Comparison](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=example_SAM-single-owner-PPA-2)

## Re-creating SAM Economic Model Results in the SAM Desktop Application

First, open `src/geophires_sam_economics/Generic_400_MWe.sam`
in the SAM desktop application.

Next, run GEOPHIRES for your input, e.g.:

```
python -mgeophires_x my-geophires-input.txt
```

Then check `src/geophires_x/all_messages_conf.log` for the SAM Economics Parameter Mapping entry:

```
23-05-2025 10:09:35 : INFO : EconomicsSam : calculate_sam_economics : 151 : (Process Details : (1378, MainProcess), Thread Details : (8589068352, MainThread)): SAM Economics Parameter Mapping:
-----------------  --------------------  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
SAM Module         Parameter             Value
Custom Generation  analysis_period       20
Custom Generation  user_capacity_factor  90.0
Utility Rate       inflation_rate        2.0
Utility Rate       degradation           [1.2734946600673935, 0.7001040275842613, 0.5267634676194525, 0.4244824247238818, 0.3529717582311231, 0.29852256883429373, 0.2548483024454293, 0.21855974702202877, 0.18762922644042462, 0.1607514026827296, 0.13703877682895466, 0.11586181507372084, 0.09675857340703789, 0.07938054662917803, 0.06345865490418974, 0.0487810281945756, 0.03517801101748528, 0.02251175220012943, 0.010668799824934945, 0.0]
Single Owner       analysis_period       20
Single Owner       total_installed_cost  264606243.76608825
Single Owner       om_fixed              [7193902.821741002]
Single Owner       om_fixed_escal        -2.0
Single Owner       system_capacity       59020.69007804236
Single Owner       federal_tax_rate      [21.0]
Single Owner       state_tax_rate        [7.0]
Single Owner       itc_fed_percent       [30.0]
Single Owner       property_tax_rate     0.0
Single Owner       ppa_price_input       [0.08, 0.08, 0.08322, 0.08644, 0.08966, 0.09288, 0.0961, 0.09932, 0.10254, 0.10576, 0.10898000000000001, 0.1122, 0.11542, 0.11864, 0.12186, 0.12508, 0.1283, 0.13152, 0.13474, 0.13796]
Single Owner       debt_percent          40.0
Single Owner       real_discount_rate    8.0
Single Owner       term_tenor            20
Single Owner       term_int_rate         5.0
Single Owner       ibi_oth_amount        0.0
-----------------  --------------------  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
```

You can then manually enter the parameters from the logged mapping into the SAM desktop app.

![](_images/sam-desktop-app-manually-enter-system-capacity-from-geophires-log.png)

## Using SAM Economic Models with Existing GEOPHIRES Inputs

In many cases, all you need to do to use SAM Economic Models for your existing GEOPHIRES inputs is to change the
`Economic Model` parameter value.
For example, if your GEOPHIRES `.txt` file contained the following:

```
# *** Financial Parameters ***
Economic Model, 2, -- Standard Levelized Cost Model
Discount Rate, .05
Plant Lifetime, 25
```

You would change it to:

```
# *** Financial Parameters ***
Economic Model, 5, -- SAM Single Owner PPA Economic Model
Discount Rate, .05
Plant Lifetime, 25
```

For inputs with the BICYCLE economic model, such as the following:

```
# *** Financial Parameters ***
Economic Model, 3, -- BICYCLE
Inflated Equity Interest Rate, .08
Plant Lifetime, 30
```

Change `Economic Model` and replace `Inflated Equity Interest Rate` with a suitable `Discount Rate` and
`Inflation Rate`:

```
# *** Financial Parameters ***
Economic Model, 5, -- SAM Single Owner PPA Economic Model
Discount Rate, .08
Inflation Rate, .03
Plant Lifetime, 30
```
