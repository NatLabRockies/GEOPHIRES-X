.. raw:: html

    <style type="text/css">
        #calibration-with-fervo-implemented-field-design table:nth-of-type(2) {
            max-width: 75% !important;
        }

        #economic-results table td:first-child,
        #economic-results table td:nth-child(2) {
            white-space: preserve nowrap;
        }

        #results section[id] table th:nth-child(2),
        #results section[id] table th:nth-child(3) {
            white-space: preserve nowrap;
        }
    </style>

# GEOPHIRES Case Study: 500 MW EGS Modeled on Fervo Cape Station (February 2026 Update)

.. raw:: html

    <p style="font-style: italic; font-weight: bold;">
    <!-- ⚠️️ This is a deprecated version of the case study. -->
    ℹ️️ <a href="Fervo_Project_Cape-7.html">Click here</a> to view the October 2026 Update preview version (<tt>Fervo_Project_Cape-7</tt>).
    </p>

---

## Introduction

The GEOPHIRES example `Fervo_Project_Cape-5` is a case study[^author] of a 500 MWe EGS project modeled on
a second-of-a-kind (SOAK) analog of Phases I and II of Fervo Energy's [Cape Station project](https://capestation.com/).

[^author]: Case Study Author: Jonathan Pezzino, Scientific Web Services LLC (SWS Geothermal). GitHub profile: [softwareengineerprogrammer](https://github.com/softwareengineerprogrammer).

Key results include **LCOE =** **$85.0/MWh**, **IRR = 22.4%**, and **Total CAPEX =** **$5600/kW**. [Click here to go to the Results section](#results).

[Click here](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=Fervo_Project_Cape-5) to
interactively explore the case study example in the GEOPHIRES web interface.

.. raw:: html

    <style type="text/css">
        #intro-result-images {
            width: 85%;
            margin:auto;
        }
        #intro-result-images img {
            max-width: 49%;
            display: inline;
            vertical-align: top;
        }
    </style>
    <div id="intro-result-images">
        <a href="#production-temperature-profile-section"
            title="Jump to the Production Temperature Profile section">
            <img src="_images/fervo_project_cape-5-power-production.png"
                class="no-active"
                alt="Power Production Profile Graph" />
        </a>

        <a href="#sensitivity-analysis-section"
            title="Jump to the Sensitivity Analysis section">
            <img src="_images/fervo_project_cape-5-sensitivity-analysis-lcoe.png"
                class="no-active"
                alt="LCOE Sensitivity Analysis Results Chart" />
        </a>
    </div>

### Modeling Overview: A Consensus-Based Second-of-a-Kind Analog

This case study models a 500 MWe Enhanced Geothermal System (EGS) project designed to represent a Second-of-a-Kind (
SOAK) deployment.
Rather than serving as an exact facsimile of Cape Station as built, this study estimates what a non-Fervo developer
could achieve on a geologically analogous site, relying primarily on publicly available data and standardized
engineering estimates.
The model assumes the developer is a "fast follower": benefiting from the proof-of-concept established by Cape Station
Phase I but operating without access to Fervo’s private supply chain or proprietary optimization data.

**Public Data Reliance:** Inputs utilize publicly available data for parameter values where applicable, such as geothermal
gradient and reservoir density.
Where data is proprietary or otherwise unknown, values are inferred from public announcements or extrapolated from standard industry
correlations.

**Conservative Constraints:** To ensure the model serves as a robust feasibility test, some inputs are intentionally
conservative compared to Fervo’s stated targets, such as drilling costs and water loss.

**Commercial Viability Threshold:** Implicit in this design is a screening for investment-grade returns.
While inputs prioritized the most realistic and verifiable data available, in select instances where public data
provided a range of potential values rather than a precise figure, inputs were selected from within those bounds to
satisfy a minimum profitability constraint (IRR ≈ 20%).
This approach reflects the reality that a Second-of-a-Kind commercial deployment would generally only proceed if
projected returns offered a sufficient premium to justify the remaining technology risk.
An illustrative example is Fracture Height, which was tuned to yield an effective fracture surface area sufficient
to sustain commercial flow rates and delay thermal breakthrough, ensuring the project meets its long-term revenue
targets.

**Fast Follower Advantage:** By entering the market after Fervo’s initial de-risking campaigns, the modeled developer
avoids the high tuition costs of early experimentation.
For example, while Fervo’s initial drilling costs at Cape Station ranged
from [$9.4M down to $4.8M per well](https://houston.innovationmap.com/fervo-energy-drilling-utah-project-2667300142.html)
as they climbed the learning curve,
this model assumes a developer can bypass those initial high-cost outliers,
instead initiating their campaign at a stabilized commercial baseline (modeled here
at $4.65M/well, aligned with the NREL ATB and 2025 cost curves).
This reflects a developer who capitalizes on established industry knowledge to skip the First-of-a-Kind (FOAK)
premiums but has not yet achieved the fully optimized learning rates of a mature Nth-of-a-Kind (NOAK) operator.

### Intended Use Cases

This case study is designed to function as a public utility for the geothermal sector, serving two primary roles:

**Industry Benchmark:** By relying primarily on verifiable public data and independent expert consensus, this model
establishes a transparent baseline for EGS viability.
It tests the premise that Fervo’s success at Cape Station is a replicable standard for the next-generation geothermal
industry.
The results serve as reference points for what is achievable using current technology in high-grade resources.

**Template for Resource Assessment & Custom Modeling:** The example input file ([Fervo_Project_Cape-5.txt](https://github.com/softwareengineerprogrammer/GEOPHIRES/blob/main/tests/examples/Fervo_Project_Cape-5.txt)) is intended
as customizable template for modeling other resources.
Users can input local geologic data (gradient, rock properties) into this template to evaluate how a Cape Station-style
design would perform in different geographies (e.g., Nevada vs. Utah vs. International).
Different plant sizes and performance targets can be modeled by adjusting the number of production wells, fractures per well,
and other technical & engineering parameters.
The model allows users to stress-test economic assumptions, such as the PPA price or Investment Tax Credit (ITC), to see
how policy changes impact the feasibility of replicating this design elsewhere.

### Disclaimer: Independent Analysis

This case study is an independent techno-economic analysis developed by the author and contributors to the GEOPHIRES
open-source project. It is not affiliated with, sponsored by, or endorsed by Fervo Energy.
The author and contributors are not employees or agents of Fervo Energy, and this work has not been reviewed or
approved by the company. All modeling assumptions, including those derived from public data sources, represent the
independent interpretation of the author and the GEOPHIRES open-source community and do not constitute proprietary
information or official company projections.

Furthermore, as noted in the [Discussion section](#discussion-section), this analysis provides a validated economic baseline rather than a
fully burdened commercial pro-forma. Actual financial results may vary based on project-specific overhead, financing fees,
and operational complexities not explicitly itemized in this study.

## Methodology

The Inputs and Results tables document key assumptions, inputs, and a comparison of results with reference
values.
Note that these are not the exhaustive sets of inputs and results, which are available in source code and
the [web interface](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=Fervo_Project_Cape-5).

See the [Calibration with Fervo-implemented Field Design section](#res-eng-params-calibration-section)
for a detailed explanation of how key case study reservoir engineering input parameters were derived.

### Inputs

See [Fervo_Project_Cape-5.txt](https://github.com/softwareengineerprogrammer/GEOPHIRES/blob/main/tests/examples/Fervo_Project_Cape-5.txt)
in source code for the full set of inputs.
Refer to the [GEOPHIRES Parameters reference](parameters.html#input-parameters) for descriptions and specifications of
all available GEOPHIRES input parameters.

<a id="reservoir-parameters-section"></a>

#### Reservoir Parameters

| Parameter         | Input Value    | Comment      |
|-------------------|-------------------------------------------|-------------|
| Surface Temperature | 13 ℃ |  Surface temperature near Milford, UT (38.4987670, -112.9163432) ([Project InnerSpace, 2025](https://geomap.projectinnerspace.org/test/)). |
| Number of Segments | 3 |  .. N/A  |
| Gradient 1 | 74 ℃/km |  Sedimentary overburden. 200℃ at 8500 ft depth (Fercho et al. 2024); 228.89℃ at 9824 ft (Norbeck et al. 2024). |
| Thickness 1 | 2.5 km |  .. N/A  |
| Gradient 2 | 41 ℃/km |  Crystalline reservoir |
| Thickness 2 | 0.5 km |  .. N/A  |
| Gradient 3 | 39.1 ℃/km |  Sugarloaf appraisal |
| Reservoir Depth | 2.68 km |  Extrapolated from surface temperature, gradient, and average production temperature of shallower and deeper producers in Singh et al., 2025. |
| Reservoir Density | 2800 kg/m³ |  phyllite + quartzite + diorite + granodiorite ([Norbeck et al., 2023](https://doi.org/10.31223/X52X0B)) |
| Reservoir Heat Capacity | 790 J/kg/K |  .. N/A  |
| Reservoir Thermal Conductivity | 3.05 W/m/K |  .. N/A  |
| Reservoir Model | Multiple Parallel Fractures (Gringarten) |  See the [reservoir engineering calibration section](#res-eng-params-calibration-section) for additional details. |
| Number of Fractures per Stimulated Well | 150 |  The model assumes an Extreme Limited Entry stimulation design (Fervo Energy, 2023) utilizing 12 stages with 15 clusters per stage (derived from Singh et al., 2025) and 81–85% stimulation success rate per 2024b ATB Moderate Scenario (NREL, 2025). |
| Fracture Separation | 9.8255 m |  Based on 30 foot cluster spacing (Singh et al., 2025) marginally uprated to align with long-term thermal decline behavior trend towards wider fracture spacing (Fercho et al., 2025). |
| Fracture Shape | Rectangular |  Bench design and fracture geometry in Singh et al., 2025 are given in rectangular dimensions. |
| Fracture Width | 305 m |  Matches intra-bench well spacing of 500 ft (corresponding to fracture length of 1000 ft) (Singh. et al., 2025) |
| Fracture Height | 100 m |  Actual fracture geometry is irregular and heterogeneous; this height complies with the minimum height required by the implemented bench design (200 ft; 60.96 meters) and yields an effective fracture surface area consistent with simulation results in Singh. et al., 2025. |
| Water Loss Fraction | 1% |  &#34;Long-term modeling, calibrated to early field data, predicts circulation recapture rates exceeding 99%&#34; ([Geothermal Mythbusting: Water Use and Impacts](https://fervoenergy.com/geothermal-mythbusting-water-use-and-impacts/); Fervo Energy, 2025). Modeling in Singh et al., 2025 predicts fluid loss of 0.36% to 0.49%. |

<a id="well-bores-parameters-section"></a>

#### Well Bores Parameters

| Parameter         | Input Value    | Comment      |
|-------------------|-------------------------------------------|-------------|
| Number of Production Wells | 56 |  Number of production wells required to produce net generation greater than the PPA minimum and total generation less than nameplate capacity (Gen 2 ORCs gross capacity). |
| Number of Injection Wells per Production Well | 0.666 |  Modeled on the reference case 5-well bench pattern (3 producers : 2 injectors) described in Singh et al., 2025. |
| Nonvertical Length per Multilateral Section | 5000 feet |  Target lateral length given in environmental assessment (BLM, 2024). Note that lateral length is assumed to be an upper bound constraining the number of fractures per well for a given cluster spacing. |
| Production Flow Rate per Well | 107 kg/sec |  Cape Station pilot testing reported a sustained flow rate of 95–100 kg/s and maximum flow rate of 107 kg/s (Fervo Energy, 2024). Modeling by Singh et al. suggests initial flow rates of 120–130 kg/sec that gradually decrease over time (Singh et al., 2025). The case study flow rate is chosen both as a conservative target for long-term sustainability and to achieve a more economically favorable drawdown and redrilling schedule. |
| Production Well Diameter | 8.535 in |  Inner diameter of 9⅝ inch casing size, the next standard casing size up from 7 inches, implied by announcement of &#34;increasing casing diameter&#34; (Fervo Energy, 2025). |
| Injection Well Diameter | 8.535 in |  See Production Well Diameter |
| Production Wellhead Pressure | 303 psi |  Modeled at a constant 300 psi in Singh et al., 2025. We use a marginally uprated value to conform to GEOPHIRES&#39;s calculated minimum wellhead pressure and nominally align with the gradual increase in WHP for constant flow rates modeled by Singh et al. |
| Injectivity Index | 1.38 kg/sec/bar |  Based on ATB Conservative Scenario (NREL, 2025) derated to align with expected parasitic loads of 15–20% and per analyses that suggest lower productivity/injectivitity (Xing et al., 2025; Yearsley and Kombrink, 2024). |
| Productivity Index | 1.13 kg/sec/bar |  See Injectivity Index |
| Ramey Production Wellbore Model | True |  Ramey&#39;s model estimates the geofluid temperature drop in production wells |
| Injection Temperature | 53.6 ℃ |  Calibrated with GEOPHIRES model-calculated reinjection temperature (Beckers and McCabe, 2019). Close to upper bound of Project Red injection temperatures (75–125℉; 23.89–51.67℃) (Norbeck and Latimer, 2023). Note: GEOPHIRES enforces a thermodynamic optimum that overrides higher values, such as the 85°C ORC outlet temperature specified in Cape Station&#39;s plant design (DeGolyer and MacNaughton, 2024) (intended for silica scaling mitigation), resulting in a &#34;maximum theoretical power&#34; scenario. Support for higher reinjection temperatures may be added in future GEOPHIRES versions. |
| Injection Wellbore Temperature Gain | 3 ℃ |  Empirical estimate for high-flow rate wells where rapid fluid velocity minimizes heat uptake during descent (Ramey, 1962). |
| Maximum Drawdown | 0.25% |  This value represents the fractional drop in production temperature compared to the initial temperature that is allowed before the wellfield is redrilled. It is calibrated to maintain the PPA minimum net electricity generation requirement. It is a very small percentage because it is relative to the initial production temperature; the temperature quickly rises higher due to thermal conditioning and plateaus until breakthrough, so any drawdown relative to the initial value signals that the temperature has already declined from its stabilized peak. |

#### Surface Plant Parameters

| Parameter         | Input Value    | Comment      |
|-------------------|-------------------------------------------|-------------|
| Power Plant Type | Supercritical ORC |  Gen 2 ORC units (Turboden, 2025). |
| Plant Lifetime | 30 yr |  Sets the project economic horizon, aligned with Fervo&#39;s anticipated 30-year well life (Fervo Energy, 2025). Modeling Distinction: While Fervo projects physical wellbore integrity for 30 years, GEOPHIRES simulates &#34;redrilling events&#34; to model thermal management of the reservoir volume. This treats the 30-year lifespan as an aggregate of shorter-lived thermal cycles delineated by discrete redrilling events occurring at intervals dictated by the Maximum Drawdown parameter. The modeled cost of each redrilling event is equivalent to the drilling and stimulation cost of the entire wellfield, serving as a conservative cost proxy for the major interventions (e.g., sidetracking and stimulating laterals into fresh rock, or drilling new wells if necessary) required to sustain the PPA target against thermal depletion. |
| Ambient Temperature | 11.17 ℃ |  Average annual temperature of Milford, Utah ([NCEI](https://www.ncei.noaa.gov/access/us-climate-normals/#dataset=normals-annualseasonal&amp;timeframe=30&amp;station=USC00425654)). Note that this value affects heat to power conversion efficiency. The effects of hourly and seasonal ambient temperature fluctuations on efficiency and power generation are not modeled in this version of the case study. |
| Utilization Factor | 91.3% |  (DeGolyer and MacNaughton, 2024) |
| Plant Outlet Pressure | 2000 psi |  McClure, 2024; Singh et al., 2025. |
| Circulation Pump Efficiency | 80% |  .. N/A  |
| Project Latitude | 38.506196 |  .. N/A  |
| Project Longitude | -112.918155 |  .. N/A  |

#### Construction Parameters

| Parameter         | Input Value    | Comment      |
|-------------------|-------------------------------------------|-------------|
| Construction Years | 5 yr |  Ground broken in 2023 (Fervo Energy, 2023). Expected to reach full scale production in 2028 (Fervo Energy, 2025). See [GEOPHIRES documentation](SAM-EM_Multiple-Construction-Years.html) for details on how construction years affect CAPEX, IRR, and other calculations. |
| Construction CAPEX Schedule | 0.014,0.027,0.139,0.431,0.389 | Array of fractions of overnight capital cost expenditure for each year, starting with lower costs during initial years for exploration and increasing to higher costs during later years as buildout progresses. |


#### Economic Parameters

| Parameter         | Input Value    | Comment      |
|-------------------|-------------------------------------------|-------------|
| Economic Model | SAM Single Owner PPA |  The SAM Single Owner PPA economic model is used to calculate financial results including LCOE, NPV, IRR, and pro-forma cash flow analysis. See [GEOPHIRES documentation of SAM Economic Models](https://softwareengineerprogrammer.github.io/GEOPHIRES/SAM-Economic-Models.html) for details on how System Advisor Model financial models are integrated into GEOPHIRES. |
| Inflation Rate | 2.7% |  US inflation as of December 2025. Note: [2024b ATB models lower inflation](https://atb.nrel.gov/electricity/2024b/definitions#inflation). |
| Starting Electricity Sale Price | $95/MWh |  Aligns with Geysers - Sacramento pricing in [2024b ATB](https://atb.nrel.gov/electricity/2024/geothermal) (NREL, 2025). See Sensitivity Analysis for effect of different prices on results. |
| Electricity Escalation Rate Per Year | $0.57/MWh |  Calibrated to reach $100/MWh at project year 11 |
| Fraction of Investment in Bonds | 70% |  Approximate debt required to cover CAPEX after $1 billion sponsor equity per [Matson, 2024](https://www.linkedin.com/pulse/fervo-energy-technology-day-2024-entering-geothermal-decade-matson-n4stc/). Note that this source says that Fervo ultimately wants to target “15% sponsor equity, 15% bridge loan, and 70% construction to term loans”, but this case study does not attempt to model that capital structure precisely. |
| Discount Rate | 12% |  Typical discount rates for higher-risk projects may be 12–15%. |
| Inflated Bond Interest Rate | 7% |  2024b ATB (NREL, 2025) |
| Inflated Bond Interest Rate During Construction | 10.5% |  Higher than interest rate during normal operation to account for increased risk of default prior to COD. Value aligns with ATB discount rate (NREL, 2025). |
| Bond Financing Start Year | -2 yr |  Equity-only for first 2 construction years (ATB) |
| Investment Tax Credit Rate | 30% |  Geothermal Drilling and Completions Apprenticeship Program ensures compliance with ITC labor requirements (Southern Utah University, 2024). |
| Combined Income Tax Rate | 25.55% |  Federal Corporate Income Tax Rate of 21% plus Utah Corporate Franchise and Income Tax Rate of 4.55%. (Note: This input uses a simple summation of statutory rates; the effective combined rate calculated in the model may differ due to standard federal-state tax interactions.) |
| Property Tax Rate | 0.22% |  Utah Inland Port Authority (UIPA) tax differential incentive |
| Capital Cost for Power Plant for Electricity Generation | $1900/kW |  [US DOE, 2021](https://betterbuildingssolutioncenter.energy.gov/sites/default/files/attachments/Waste_Heat_to_Power_Fact_Sheet.pdf). Pricing information not publicly available for Turboden or Baker Hughes Gen 2 ORC units (Turboden, 2025; Jacobs, 2025). |
| Exploration Capital Cost | $30M |  Equivalent to 2024b ATB NF-EGS conservative scenario exploration assumption of 5 full-size wells (NREL, 2025), plus $1M for geophysical and field work, plus 15% contingency, plus 12% indirect costs. |
| Well Drilling Cost Correlation | vertical large diameter, baseline |  2025 NREL Geothermal Drilling Cost Curve Update (Akindipe and Witter, 2025). |
| Well Drilling and Completion Capital Cost Adjustment Factor | 90% (Yields all-in cost of $4.65M/well) |  2024b Geothermal ATB ([NREL, 2025](https://atb.nrel.gov/electricity/2024b/geothermal)). Note: Fervo has claimed lower drilling costs equivalent to an adjustment factor of 0.8 (Latimer, 2025); the case study conservatively uses the higher ATB-aligned value. See [Sensitivity Analysis](#sensitivity-analysis-section) for effect of different drilling costs on results. |
| Reservoir Stimulation Capital Cost per Injection Well | $4M baseline cost; $4.83M all-in cost |  The baseline stimulation cost is calibrated from costs of high-intensity U.S. shale wells (Baytex Energy, 2024; Quantum Proppant Technologies, 2020), which are the closest technological analogue for multi-stage EGS (Gradl, 2018). Costs are also driven by the requirement for high-strength ceramic proppant rather than standard sand, which would crush or chemically degrade (diagenesis) over a 30-year lifecycle at 200℃ (Ko et al., 2023; Shiozawa and McClure, 2014) and the premium for ultra-high-temperature (HT) downhole tools. Note that all-in costs per well are higher than the baseline cost because they include additional indirect costs and contingency. See [Sensitivity Analysis](#sensitivity-analysis-section) for effect of different stimulation costs on results. |
| Reservoir Stimulation Capital Cost per Production Well | $4M baseline cost; $4.83M all-in cost |  See Reservoir Stimulation Capital Cost per Injection Well |
| Field Gathering System Capital Cost Adjustment Factor | 54% |  Gathering costs represent 2% of facilities CAPEX per [Matson, 2024](https://www.linkedin.com/pulse/fervo-energy-technology-day-2024-entering-geothermal-decade-matson-n4stc/). |
| Royalty Rate | 1.75% |  The BLM royalty structure is 1.75% of gross proceeds from electricity sales for the first 10 years of production (Code of Federal Regulations, 2024). |
| Royalty Rate Escalation Start Year | 11 yr |  After the first 10 years of production, the royalty rate escalates to 3.5%. |
| Royalty Rate Escalation | 1.75% |  Escalation at Year 11 from 1.75% to 3.5%. |
| Royalty Rate Maximum | 3.5% |  No further escalation beyond 3.5%. |
| Water Cost Adjustment Factor | 200% |  Local scarcity may increase procurement costs. Development near/on land with active/shut-in oil and gas wells could potentially utilize waste water to recover losses and offset costs. |

<a id="res-eng-params-calibration-section"></a>

### Calibration with Fervo-implemented Field Design

[Designing the Record-Breaking Enhanced Geothermal System at Project Cape](https://www.resfrac.com/wp-content/uploads/2025/06/Singh-2025-Fervo-Project-Cape.pdf) (Singh et al., 2025)
describes reservoir modeling (ResFrac) that informed the Cape Station field implementation[^field-implementation-configuration-note].

[^field-implementation-configuration-note]: Note on Configuration: While the specific Bearskin and Gold pads (Phase II) utilize an inverted 2:3 ratio (3 injectors for 2 producers), this case study assumes the 3:2 ratio identified in the paper's optimization studies ("Study 1") represents the standard repeating module for the full-scale 400+ MWe system. The higher injector count in Phase II is interpreted as a transient requirement for field delineation and initial pressure support (boundary conditions) rather than the long-term commercial standard.

#### Bench Design and Well Spacing

Figure 7 in Singh et al., 2025 (below) shows the well and bench spacing for the Cape Station field design.[^fig-7-note]
Each bench consists of 5 wells, with 2 injectors and 3 producers.
This ratio is encoded by the case study's `Number of Injection Wells per Production Well` parameter (see [Well Bores Parameters](#well-bores-parameters-section)).

The Singh et al. paper models separate upper and lower benches.
GEOPHIRES v3.11 does not support wells with different depths, so the case study's `Reservoir Depth` parameter is
set to a value nominally representing an approximate average depth between the upper and lower benches.
See the [Technical & Engineering Results section](#technical-and-engineering-results-section) for relevant temperature results.

![Singh et al. (2025), Figure 7](_images/singh-et-al-2025_fig-7_well-and-bench-spacing.png)

[^fig-7-note]: The original figure has been cropped and modified to display: "500 ft horizontal" instead of "700 ft horizontal" and "Inter-bench spacing: Vertical spacing between injectors: 700 ft"; per the Conclusions section of the paper: "Based on the results from the study and additional risk analysis, the 500 ft x 200 ft well spacing with a bench spacing of 700 ft was implemented in the field development." (p. 19).

#### Fracture Geometry

Figure 2 in Singh et al., 2025 (below) shows the ResFrac simulated fracture geometry. This figure, along with the bench design in Figure 7,
informed the case study's `Fracture Shape`, `Fracture Width`, `Fracture Height`, and `Number of Fractures per Stimulated Well` parameters (see [Reservoir Parameters](#reservoir-parameters-section)).

Note that the case study does not attempt to strictly replicate the paper's fracture geometry;
rather, the paper specifications were used to derive approximations and/or constraints on parameters whose final values
were ultimately refined based on holistic techno-economic considerations. For example, the intra-bench horizontal well spacing
of 500 ft dictates that fracture half-lengths must be at least 500 ft in order to achieve flow between injectors and producers.
Thus, a minimum fracture length of 1000 ft (305 m) is required (assuming that fractures propagate approximately symmetrically in the horizontal axis),
reflected in the case study's `Fracture Width` parameter value.

Similarly, the intra-bench vertical spacing of 200 ft (61 m) dictates that the fracture height must be at least 200 ft[^intra-bench-vertical-spacing-note].
The case study's `Fracture Height` value was formulated by starting with 61 m and then iteratively uprating until a total effective fracture surface area per well was achieved
that produces results consistent with the paper simulation and other reference values.
The uprated value is also supported by Figure 2's fracture geometry visualization indicating fracture height exceeding intra-bench vertical spacing.

[^intra-bench-vertical-spacing-note]: Note: unlike horizontal propagation, vertical fracture propagation is assumed to be asymmetrical in the upwards direction per "fracture propagation model with uniform frac gradient and no layering will tend to predict fracture growth directly upwards." (p. 3) and fracture geometry shown in Figures 1 and 2.


![Singh et al. (2025), Figure 2](_images/singh-et-al-2025_fig-2_fracture-geometry.png)


#### Simulation Comparison

An equivalent GEOPHIRES simulation was run using the case study's reservoir engineering parameters, with the following modifications to align with Singh et al.'s modeling scenario:

| Parameter         | Input Value    | Comment      |
|-------------------|-------------------------------------------|-------------|
| Number of Production Wells | 4 |  .. N/A  |
| Number of Injection Wells per Production Well | 1.2 |  The Singh et al. scenario has 4 producers and 6 injectors. We model one fewer injector here to account for the combined injection rate being lower for the higher bench separation cases. |
| Maximum Drawdown | 100% |  Redrilling not modeled in Singh et al. scenario. (The equivalent GEOPHIRES simulation allows drawdown to reach up to 100% without triggering redrilling) |
| Plant Lifetime | 15 yr |  .. N/A  |

The following table compares the average production temperature profile from the "700 ft bench spacing" scenario in Singh et al. with the GEOPHIRES simulation.
Note that both figures show temperature in Fahrenheit rather than Celsius.


| Reference Simulation: Fervo-implemented Design (Fig. 18.) | GEOPHIRES Simulation: Case Study Equivalent Scenario |
|---|---|
| <img src="_images/singh-et-al-2025_wht-700-ft-bench-spacing.png" class="no-active" /> | <img src="_images/singh_et_al_base_simulation-production-temperature.png" class="no-active" /> |


While the initial and final (Year 15) temperatures are consistent, the production curves exhibit distinct profiles due to the different modeling approaches:

1. **Reference Simulation (Left):** The Singh et al. (2025) curve reflects a fully coupled numerical simulation (ResFrac) that accounts for complex fracture heterogeneity, inter-well interference, and variable flow paths. The gradual decline starting around Year 3 indicates thermal dispersion, where cold injection fluid mixes with hot reservoir fluid along faster flow paths earlier in the project life.
1. **GEOPHIRES Simulation (Right):** The GEOPHIRES result utilizes the Gringarten (1975) analytical solution for flow in fractured rock. This model assumes a uniform thermal sweep across an idealized fracture surface. Consequently, it maintains a flat, maximum production temperature for a longer duration until the cold front reaches the production well (thermal breakthrough), resulting in a sharper, later decline.

Despite these structural differences, the comparison supports the physical plausibility of the case study's reservoir engineering parameters,
as the Year 1 and Year 15 thermal endpoints align closely with the numerical simulation baseline.

However, the analytical Gringarten model's thermal plateau yields a higher aggregate heat extraction than the numerical model's
gradual decline, representing an optimistic upper bound on performance compared to the conservative heterogeneity
modeled in ResFrac.
To bound this risk, an alternative GEOPHIRES simulation was modeled using the ResFrac profile[^upp-resfrac-profile-note].
Results indicated that to offset the dispersion penalty under heterogeneous flow conditions, the project would require
a higher initial reservoir temperature (achieved via deeper drilling) to compensate for the loss of the thermal plateau.
[Click here](https://gtp.scientificwebservices.com/geophires?shared-geophires-result-id=834b0096-15b1-4dd3-b262-612e9df1342f)
to view a variant GEOPHIRES scenario (`Fervo_Project_Cape-6 Variant: ResFrac Profile + Hotter/Deeper Scenario`)
for a 100 MWe average net production project with a 3 km well depth, yielding approximately 15°C higher production temperatures.

[^upp-resfrac-profile-note]: The simulation utilized GEOPHIRES's [Generic User-Provided Temperature Profile reservoir model](https://softwareengineerprogrammer.github.io/GEOPHIRES/Theoretical-Basis-for-GEOPHIRES.html#reservoir-models) with temperature data derived from Figure 18 in Singh et al. (2025).

The calibration simulation above represents a 15-year unmitigated thermal decline without redrilling.
In the full case study results, the model includes redrilling events that restore production temperature when drawdown thresholds are reached,
resulting in the cyclical profile shown in the [Production Temperature section](#production-temperature-profile-section) below.


## Results

See [Fervo_Project_Cape-5.out](https://github.com/softwareengineerprogrammer/GEOPHIRES/blob/main/tests/examples/Fervo_Project_Cape-5.out)
in source code for the complete results.
Refer to the [GEOPHIRES Parameters reference](parameters.html#outputs) for descriptions and specifications of
all available GEOPHIRES outputs.

### Economic Results

Note that economic results are derived from the [SAM Single Owner PPA Economic Model](SAM-Economic-Models.html#sam-single-owner-ppa) pro-forma cash flow analysis.
The case study result's pro-forma cash flow analysis can be viewed in the `Fervo_Project_Cape-5.out` result file in source code
and in the web interface under the Cash Flow tab.


| Metric        | Result Value   | Reference Value(s) | Reference Source |
|---------------|----------------|--------------------|------------------|
| <span title="Levelized Cost of Energy" class="metric-tooltip-text">LCOE</span> | $85.0/MWh | \$80/MWh      | Horne et al, 2025. |
| <span title="Internal Rate of Return" class="metric-tooltip-text">After-tax IRR</span> <br/> (at Year 30 of Operations) | 22.4% | 15–25% | Typical levered returns for energy projects |
| <span title="Project Net Present Value" class="metric-tooltip-text">NPV</span>  | $199.0M | >$0 | Positive NPVs result in profit  |
| <span title="aka PI aka Value Investment Ratio (VIR) and Profit Investment Ratio (PIR)" class="metric-tooltip-text">Levered Equity <br/> Profitability Index</span>  | 1.33 | >1.0 | Calculations greater than 1.0 indicate the future anticipated discounted cash inflows are greater than the anticipated discounted cash outflows.  |
| <span title="Return on Investment; aka Multiple of Invested Capital (MOIC)" class="metric-tooltip-text">Project ROI</span>  | 4.31 | | .. N/A  |
| <span title="Pro-forma cash flow analysis generated by the SAM Single Owner PPA Economic Model" class="metric-tooltip-text">Cash Flow</span>  | [source code](https://github.com/softwareengineerprogrammer/GEOPHIRES/blob/main/tests/examples/Fervo_Project_Cape-5.out#L225);<br/>[web interface](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=Fervo_Project_Cape-5)[^cash-flow-tab] | | .. N/A  |



[^cash-flow-tab]: Click the Cash Flow tab to view.

Hover over the metric names to view the corresponding definitions.
See [GEOPHIRES Economic Outputs documentation](parameters.html#economic-parameters) for more information.

### Capital Costs (CAPEX)


| Metric                                                                                                                                                                                                    | Result Value                                | Reference Value(s)                               | Reference Source |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------|--------------------------------------------------|------------------|
| <span title="Weighted Average Cost of Capital" class="metric-tooltip-text">WACC</span> | 8.31% | 8.3% | Fervo's target goal is to eventually achieve a "Solar Standard" WACC of 8.3% (Matson, 2024). |
| Exploration Costs | $30M | $23.25M | 2024b ATB NF-EGS conservative scenario exploration assumption of 5 full-size wells (NREL, 2025). Case study result conservatively includes additional costs for geophysical survey, indirect costs, and contingency. |
| Well Drilling and Completion Costs | $437M total <br/> ($4.65M/well) | <$4M/well | Latimer, 2025.                                   |
| Stimulation Costs | $454M total <br/> ($4.83M/well) | $4.65M/well | Based on 46%:54% drilling:stimulation cost ratio (Yusifov & Enriquez, 2025).                        |
| Surface Power Plant Costs | $1.47B  | | |
| Field Gathering System Costs | $48M <br/> (2% of OCC) | 2% of OCC | Matson, 2024. |
| Overnight Capital Cost | $2.44B  | | |
| Total CAPEX | $2.87B <br/> (OCC + interest and inflation during construction) | | |
| Total CAPEX: $/kW | $5600/kW <br/> (based on maximum net electricity generation) | $5000/kW; $4500/kW; $3000–$6000/kW | McClure, 2024; Horne et al, 2025; Latimer, 2025. |


### Operating Costs (OPEX)

| Metric | Result Value | Reference Value(s) | Reference Source |
|-----|-----|-----|-----|
| Wellfield maintenance costs | $5.81M/yr | .. N/A | The built-in correlation for the wellfield OPEX is similar as the surface plant OPEX: it assumes that it consists of 1% of the total wellfield plus field gathering system costs (for annual non-labor costs) and 25% of the labor costs (the other 75% of the labor costs are assigned to the surface plant OPEX). |
| Power plant maintenance costs | $24.87M/yr | .. N/A | GEOPHIRES estimates the annual surface plant OPEX as the sum of 1.5% of the total plant capital cost (for annual non-labor costs), and 75% of the annual labor costs. The other 25% of the labor costs are assigned to the wellfield OPEX. The labor costs are calculated internally in GEOPHIRES using the 2014 labor costs provided by Beckers (2016), indexed to 2017 using the Bureau of Labor Statistics (BLS) Employment Cost Index for utilities (2018). The original 2014 labor cost correlation expresses the labor costs as a function of the plant size (MW) using an approximate logarithmic curve fit to the built-in labor cost data in GETEM. |
| Water costs | $3.19M/yr | .. N/A | Default correlation: Assumes $3.50/1,000 gallons of water. The default correlation is adjusted by the Water Cost Adjustment Factor parameter value of 200%. |
| Average Annual Royalty Cost | $12.36M/yr | .. N/A | The developer&#39;s average annual royalty expense over the project&#39;s operational lifetime. This value combines both production-based royalties (percentage of gross revenue) and any scheduled supplemental royalty payments. |
| Redrilling costs | $89.1M/yr | .. N/A | Total redrilling costs over the Plant Lifetime are calculated as (Drilling and completion costs + Stimulation costs) × Number of times redrilling. The total is then divided over Plant Lifetime years to calculate Redrilling costs per year. |
| Total operating and maintenance costs | $135.33M/yr | .. N/A | .. N/A  |
| Total operating and maintenance costs: $/kW-yr | $264.21/kW-yr | $226.31/kW-yr | 2024b ATB: 2028 Deep EGS Binary Conservative Scenario (NREL, 2025).  |


<a id="technical-and-engineering-results-section"></a>

### Technical & Engineering Results


| Metric                               | Result Value                                              | Reference Value(s) | Reference Source |
|--------------------------------------|-----------------------------------------------------------|--------------------|------------------|
| Minimum Net Electricity Generation   | 499 MW | 500 MW | The announced 500 MWe capacity (Fervo Energy, 2025) is interpreted to mean that the PPA penalizes Cape Station if net electricity generation falls below 500 MWe. |
| Average Net Electricity Generation   | 510 MW | | |
| Maximum Net Electricity Generation   | 512 MW | | |
| Maximum Total Electricity Generation | 600 MW | Upper bound: 600 MW  | Combined nameplate capacity of 10×60 MWe Gen 2 ORCs. A total of 8×60 MWe Gen 2 ORCs have been announced for Phase II; 3 from Turboden and 5 from Baker Hughes (Turboden, 2025; Jacobs, 2025). This equates to 480 MW gross capacity for Phase II's 400 MW net capacity. An equivalent SOAK 500 MW project would therefore require 10 Gen 2 ORC units. (Note that the modular Gen 2 ORCs are not individually modeled in this case study, and are assumed to be combined into a single power plant.) |
| 2-year Average Net Power Production per Production Well | 9.0 MW | 7.6–11.5 MW | Figures 4 and 12 (Singh et al., 2025). |
| Heat to Power Conversion Efficiency  | 13.9% | 19.5% (Likely omits internal plant parasitic loads, such as condenser fans, which GEOPHIRES explicitly accounts for.) | DeGolyer and MacNaughton, 2024. |
| Injection Pumping Parasitic Load <br/> ({Average Pumping Power}/{Average Total Electricity Generation}) | 14.7%  | Upper bound: 16.7% | The Phase II procurement strategy (480 MW gross / 400 MW net) implies a design ceiling of 16.7% for total on-site consumption (including injection pumping). Current SOAK targets for parasitic consumption range from 15–20%, reflecting a planned reduction from the ~25–30% observed in Phase I operations (Norbeck, 2026). |
| Total fracture surface area per well | 4.6×10⁶ m² <br/> (49 million ft²) | Project Red: 2.787×10⁶ m² <br/> (30 million ft²) | Greater fracture surface area expected than Project Red (Fercho et al., 2025). |
| Reservoir Volume | 4,225,156,597 m³ | | Calculated from fracture area × fracture separation × number of fractures per well × number of wells |
| Bottom-hole Temperature <br/> (BHT) | 205.38℃ | 200–241℃ | Fercho et al., 2024; Singh et al., 2025. |
| Initial Production Temperature       | 202℃ | 196–208℃ | Approximate range of initial production temperatures between shallower and deeper producers (Singh et al., 2025). |
| Average Production Temperature       | 203℃ | 199–209℃ | Approximate range of thermally conditioned production temperatures between shallower and deeper producers (Singh et al., 2025). |
| Number of times redrilling           | 3 | 2–5  | Redrilling expected to be required within 5–10 years of project start  |
| Total wells drilled over project lifetime | 376 | Permitted Limit: 320 | The BLM Environmental Assessment (DOI-BLM-UT-C010-2024-0018-EA) authorizes an estimated development of 320 production and injection wells (BLM, 2024). As modeled, the project remains within this regulatory envelope for the first three drilling campaigns (Initial, Year 8, and Year 16), reaching a cumulative total of approximately 282 wells. <br/><br/> The model exceeds the current authorization only during the final redrilling event in Year 24. It is a standard industry assumption that brownfield capacity maintenance activities (e.g. sidetracking existing wells on existing pads) occurring two decades into operations would be authorized through subsequent regulatory actions, such as a Determination of NEPA Adequacy (DNA) or a Categorical Exclusion, given the established baseline of environmental impact. |


<a id="production-temperature-profile-section"></a>

#### Production Temperature Profile

<img src="_images/fervo_project_cape-5-production-temperature.png" class="no-active" style="max-width: 66%;" />

The production temperature profile exhibits distinctive cyclical behavior driven by the interaction between wellbore physics and reservoir thermal evolution:

1. **Thermal Conditioning (Years 1–6)**: The initial rise in production temperature, peaking at approximately 203°C, is driven by the thermal conditioning of the production wellbores. As hot geofluid continuously flows through the wells, the wellbore casing and surrounding rock heat up, reducing conductive heat loss as predicted by the Ramey wellbore model.
2. **Reservoir Drawdown (Years 6–8)**: Following the conditioning peak, temperature declines as the cold front from injection wells reaches the production zone (thermal breakthrough), reducing the produced fluid enthalpy.
3. **Redrilling (End of Years 8, 16, 24)**: The model triggers a redrilling event when the next time step's temperature would fall below the threshold defined by the `Maximum Drawdown` parameter (shown as the dashed orange line). The production temperature does not necessarily actually reach the threshold; redrilling typically preemptively restores the wellfield before that occurs. The cost of these events is amortized as an operational expense over the project lifetime.

#### Power Generation Profile

<img src="_images/fervo_project_cape-5-power-production.png" class="no-active" style="max-width: 66%;" />

Power generation is a direct function of production temperature, so the power production profile mirrors the thermal behavior described above. The graph shows both total (gross) electricity generation and net electricity generation after parasitic losses. The gap between the two curves represents the energy consumed by the circulation pumps.

The horizontal reference lines indicate the 500 MW net PPA minimum production requirement and the 600 MW nameplate capacity (combined capacity of the individual ORC units).

<a id="sensitivity-analysis-section"></a>

## Sensitivity Analysis

The following charts show the sensitivity of key metrics to various inputs.
Each chart shows the sensitivity of a single metric, such as LCOE, to the set of tested input values.
The leftmost chart column shows the parameter being tested and its baseline case study input value in parentheses.
The bars for each row show the deltas of the metric value from the baseline case study value for the values tested for
that parameter.
Green bars indicate favorable outcomes, such as lower LCOE or higher IRR, while gray bars indicate unfavorable outcomes,
such as higher LCOE or lower IRR.
Click the bars to view the sensitivity analysis result for the input value in the web interface.

The parameter values tested below represent discrete sensitivity ranges intended to illustrate the magnitude of economic impact.
They do not imply a specific statistical probability of occurrence.
Future versions of this case study may incorporate formal uncertainty quantification to map the likelihood of these outcomes.

The sensitivity analysis scenarios do not necessarily conform to all constraints and assumptions documented in the case study methodology.
For example, scenarios for Bond Interest Rate have different weighted average cost of capital (WACC) values due to the effect of interest rate on WACC.
This is particularly relevant for technical parameters pertaining to reservoir engineering.
In a real-world design, these variables are physically coupled; for instance, targeting a higher production flow rate
would typically necessitate a larger fracture surface area to mitigate the resulting acceleration in thermal drawdown.
See the [discussion of flow rate below](#impact-of-flow-rate-on-project-economics-section).

Users may wish to perform their own sensitivity analysis
using [GEOPHIRES's Monte Carlo simulation module](Monte-Carlo-User-Guide.html) or other data analysis tools.

### LCOE

.. raw:: html

    <!-- For screen: interactive SVG -->
    <object data="_images/fervo_project_cape-5-sensitivity-analysis-lcoe.svg"
            type="image/svg+xml"
            class="sensitivity-chart-interactive"></object>

    <!-- For print: static PNG -->
    <img src="_images/fervo_project_cape-5-sensitivity-analysis-lcoe.png"
         alt="LCOE Sensitivity Analysis Chart"
         class="sensitivity-chart-print">

#### Impact of PPA Price on LCOE

The sensitivity analysis reveals a positive correlation between the Power Purchase
Agreement (PPA) price and the Levelized Cost of Electricity (LCOE). While counterintuitive, this is a function of SAM
Economic Models treating federal and state income taxes as operating cash outflows.

In SAM Economic Models, the PPA price is a fixed input that determines project revenue. A higher PPA price generates
higher taxable income, which in turn increases the project's annual income tax liability (a negative cash flow). Because
the LCOE calculation aggregates all lifetime project costs, including the tax burden, the additional tax costs incurred
from higher revenues result in a higher calculated LCOE. Conversely, a lower PPA price reduces taxable income, lowers
tax liability, and decreases the resulting LCOE.

### IRR

.. raw:: html

    <object data="_images/fervo_project_cape-5-sensitivity-analysis-irr.svg"
            type="image/svg+xml"
            class="sensitivity-chart-interactive"></object>

    <img src="_images/fervo_project_cape-5-sensitivity-analysis-irr.png"
         alt="IRR Sensitivity Analysis Chart"
         class="sensitivity-chart-print">

### NPV

.. raw:: html

    <object data="_images/fervo_project_cape-5-sensitivity-analysis-project_npv.svg"
            type="image/svg+xml"
            class="sensitivity-chart-interactive"></object>

    <img src="_images/fervo_project_cape-5-sensitivity-analysis-project_npv.png"
         alt="NPV Sensitivity Analysis Chart"
         class="sensitivity-chart-print">


<a id="impact-of-flow-rate-on-project-economics-section"></a>

### Impact of Flow Rate on Project Economics

Higher flow rate per production well does not necessarily result in improved project economics (e.g. lower LCOE or higher IRR).
Higher flow rates result in increased generation in the short term, but also cause faster thermal decline.
Additional make-up wells may need to be drilled to compensate for increased thermal decline and maintain a minimum net generation (redrilling),
the cost of which may offset incremental revenue from increased generation.
This trade-off was considered in reservoir modeling that guided Fervo's field implementation (Singh et al., 2025).

The parametric analysis below visualizes the trade-off within the context of the case study GEOPHIRES scenario,
revealing a sawtooth-shaped profile in the economic metrics (LCOE, IRR, NPV) despite the approximately linear increase in electricity production.
This pattern emerges because GEOPHIRES models capacity maintenance as discrete step functions
(shown in the Number of times redrilling chart) where exceeding the `Maximum Drawdown` threshold forces an entire new
redrilling campaign.
While real-world operators would likely mitigate these sharp transitions through continuous make-up drilling,
dynamic flow rate modulation, or other adaptive reservoir management strategies,
the model highlights a fundamental reality: the economic optimum is not necessarily the maximum achievable flow rate.
Instead, it is the rate that effectively balances immediate generation gains against the potential step-wise increase
in operational costs required to offset thermal decline.
See [Redrilling Assumptions](#technical-operational-considerations) below for further discussion.

<img src="_images/fervo_project_cape-5-sensitivity-analysis-flow-rate.png" class="no-active" style="max-width: 60%;" alt="Flow rate sensitivity analysis graphs" />

## Variants

<a id="Fervo_Project_Cape-6-section"></a>

### 100 MWe Model (Phase I)

The case study also includes a 100 MWe model, `Fervo_Project_Cape-6`, with equivalent capacity to Phase I.
Note that like the 500 MWe model, `Fervo_Project_Cape-6` represents a SOAK project and not the real-world Phase I implementation as built by Fervo.
[Click here](https://gtp.scientificwebservices.com/geophires/?geophires-example-id=Fervo_Project_Cape-6) to view the
100 MWe model in the GEOPHIRES web interface.

Source code: [Fervo_Project_Cape-6.txt](https://github.com/softwareengineerprogrammer/GEOPHIRES/blob/main/tests/examples/Fervo_Project_Cape-6.txt)
and [Fervo_Project_Cape-6.out](https://github.com/softwareengineerprogrammer/GEOPHIRES/blob/main/tests/examples/Fervo_Project_Cape-6.out).

### Reduced Redrilling Scenario

[Click here](https://gtp.scientificwebservices.com/geophires?shared-geophires-result-id=4eb5e843-be61-4518-8fda-7d0b41348e53)
to view a scenario with reduced redrilling in the web interface, representing an effective longer well life compared to the base case.
Redrilling is reduced via greater effective fracture surface area per stimulated well, achieved by an increased number of fractures per well and greater fracture height.
Stimulation cost is increased to nominally reflect the larger required job size.



### ResFrac Profile + Hotter/Deeper Scenario

[Click here](https://gtp.scientificwebservices.com/geophires?shared-geophires-result-id=834b0096-15b1-4dd3-b262-612e9df1342f)
to view the `Fervo_Project_Cape-6 Variant: ResFrac Profile + Hotter/Deeper Scenario` in the web interface.
Note that this scenario models two redrilling events (rather than three) and yields 100 MWe average net generation
(rather than 100 MWe minimum net generation), reflected in the power generation profile below.



![](_images/fervo_project_cape-6_variant-resfrac-deeper-hotter_power-generation-profile.png)

See the [Simulation Comparison section](#simulation-comparison) for details.

### Previous Versions

Documentation is available for the following previous case study versions, which are deprecated in favor of this version.


#### `Fervo_Project_Cape-4`

[Version documentation](Fervo_Project_Cape-4.html)

Last Updated: 2025-08-11

Key differences:

1. Fervo_Project_Cape-5 models multiple construction years instead of a single construction year
1. Fervo_Project_Cape-5 incorporates various reservoir characteristic and engineering updates including:
    1. Segmented geology (gradients)
    1. Ambient and surface temperature refinement
    1. 5-well bench design instead of well pairs (doublets)
    1. 8.5-inch inner well diameter
    1. Productivity/Injectivity indexes instead of impedance model
    1. Stimulation parameters and outcome
1. Fervo_Project_Cape-5 incorporates various reservoir and economic parameter updates including:
    1. BLM royalties
    1. Refined discount and interest rates
    1. Refined tax rates including addition of property tax
1. Fervo_Project_Cape-5 includes more comprehensive sensitivity analysis




<a id="discussion-section"></a>

## Discussion, Limitations, & Future Work

While this case study establishes a validated economic baseline for Second-of-a-Kind (SOAK) EGS using standardized
consensus data, users should interpret results (LCOE, IRR, NPV, etc.) as an assessment of intrinsic project
viability rather than a fully burdened commercial pro-forma.
Several financial, technical, and operational factors were not explicitly modeled and represent areas for future refinement.

Users may wish to explicitly encode these cost factors in their own models by using applicable adjustment parameters.
For OPEX, such parameters may include `Wellfield O&M Cost Adjustment Factor`,
`Surface Plant O&M Cost Adjustment Factor` or `Total O&M Cost`.  For CAPEX, `One-time Flat License Fees Etc` or
`Total Capital Cost` may be appropriate.

### Financial Considerations

The case study economic results focus on project-level cash flows but do not explicitly itemize several overhead costs
and administrative realities often associated with commercial project financing.
Including these may reduce the levered IRR.

1. Transaction & Closing Fees: The Total CAPEX includes interest during construction but does not explicitly budget for debt closing or bank fees. In large-scale energy infrastructure, these transaction costs may constitute a small percent of total debt volume. [Click here](https://github.com/NatLabRockies/GEOPHIRES-X/issues/451) to view the relevant GEOPHIRES tracking issue on GitHub.
1. Reserve Accounts: The cash flow analysis assumes immediate liquidity. It does not model working capital, debt service, or major equipment replacement reserve accounts. Project financial partners may require that the project owner(s) establish and fund reserve accounts. [Click here](https://github.com/NatLabRockies/GEOPHIRES-X/issues/460) to view the relevant GEOPHIRES tracking issue on GitHub.
1. Insurance Premiums: The model does not include a specific line item for insurance. For EGS projects involving deep subsurface risks, insurance premiums could represent an additional annual operating expense. [Click here](https://github.com/NatLabRockies/GEOPHIRES-X/issues/369) to view the relevant GEOPHIRES tracking issue on GitHub.

### Technical & Operational Considerations

1. Grid Interconnection & Transmission: For a 500 MWe project, interconnection costs (substation upgrades, gen-tie lines) can be substantial. Unless the site is adjacent to high-capacity transmission with available queue space, interconnection costs could add materially to the project budget.
1. Seasonal and Hourly Performance Granularity: As noted in the Surface Plant Parameters, this study uses a fixed annual average ambient temperature. It does not model the seasonal or hourly impacts on air-cooled condenser efficiency. In reality, power output would likely dip during peak summer hours and increase during winter. Future versions of GEOPHIRES may add support for these considerations; [click here](https://github.com/NatLabRockies/GEOPHIRES-X/issues/395) to view the relevant GEOPHIRES tracking issue on GitHub.
1. Redrilling Assumptions: Management of thermal decline is modeled as periodic redrilling events that reset the reservoir's heat content to initial conditions at intervals determined by the `Maximum Drawdown` parameter. The cost of these events is amortized into a uniform annual operating expense. In reality, these events may be scheduled as discrete capital-intensive campaigns punctuated by years of lower spending, or as a continuous program of make-up well drilling to mitigate decline. [Click here](https://github.com/NatLabRockies/GEOPHIRES-X/issues/381) to view the relevant GEOPHIRES tracking issue on GitHub.
1. Reservoir Modeling Fidelity: The base case utilizes the Gringarten analytical model, which produces a characteristic thermal plateau maintained until a sharp breakthrough event. A key open question is whether this idealized profile provides an acceptably accurate approximation of drawdown over time, or if it masks the gradual dispersion caused by flow channeling and heterogeneity. Future work should evaluate whether Gringarten remains the optimal scoping proxy, or if an alternative analytical solution[^alt-analytical-solution-proposal] would offer a superior balance of speed and realism by better mimicking the shape of numerical simulation outputs.
1. ORC Efficiency: The power generation results rely on the GEOPHIRES built-in supercritical ORC efficiency correlation, which assumes the selection of an optimal working fluid for each specific geofluid temperature. For further details, please refer to the [Surface Plant section in the Theoretical Basis for GEOPHIRES](Theoretical-Basis-for-GEOPHIRES.html#surface-plant). This limitation may be addressed in the future by [FGEM integration](https://github.com/NatLabRockies/GEOPHIRES-X/issues/395).

[^alt-analytical-solution-proposal]: Possible alternatives might include Residence Time Distribution (RTD) modeling, or a parameterized profile generator based on the Bezier curve approach used in the "ResFrac Profile" variant.

---

## References

Akindipe, D. and Witter. E. (2025). "2025 Geothermal Drilling Cost Curves
Update". https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2025/Akindipe.pdf?t=1740084555

Baytex Energy. (2024). Eagle Ford Presentation.
https://www.baytexenergy.com/content/uploads/2024/04/24-04-Baytex-Eagle-Ford-Presentation.pdf

Beckers, K., McCabe, K. (2019) GEOPHIRES v2.0: updated geothermal techno-economic simulation tool. Geotherm Energy
7,5. https://doi.org/10.1186/s40517-019-0119-6

DeGolyer and MacNaughton. (2024, September 24).
Report as of June 30, 2024 on Heat Initially In Place associated with the Project Cape Area prepared for Fervo Energy.
Securities and Exchange Commission, Exhibit 99.1.
https://www.sec.gov/Archives/edgar/data/1853868/000162828026025821/exhibit991-sx1.htm

Fercho, S., Matson, G., McConville, E., Rhodes, G., Jordan, R., Norbeck, J.. (2024, February 12).
Geology, Temperature, Geophysics, Stress Orientations, and Natural Fracturing in the Milford
Valley, UT Informed by the Drilling Results of the First Horizontal Wells at the Cape Modern
Geothermal Project. https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2024/Fercho.pdf

Fercho, S., Norbeck, J., Dadi, S., Matson, G., Borell, J., McConville, E., Webb, S., Bowie, C., & Rhodes, G. (2025).
Update on the geology, temperature, fracturing, and resource potential at the Cape Geothermal Project informed by data
acquired from the drilling of additional horizontal EGS wells. Proceedings of the 50th Workshop on Geothermal Reservoir
Engineering, Stanford University, Stanford, CA. https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Fercho.pdf

Fervo Energy. (2023, September 19). Fervo’s Commercialization Plans for Enhanced Geothermal Systems (
EGS). https://egi.utah.edu/wp-content/uploads/2023/09/09.45-Emma-McConville-Fervo_EGI_Sept-19-2023.pdf

Fervo Energy. (2023, September 25). Fervo Energy Breaks Ground on the World’s Largest Next-gen Geothermal Project.
https://fervoenergy.com/fervo-energy-breaks-ground-on-the-worlds-largest-next-gen-geothermal-project/

Fervo Energy. (2024, September 10). Fervo Energy’s Record-Breaking Production Results Showcase Rapid Scale Up of
Enhanced
Geothermal. https://www.businesswire.com/news/home/20240910997008/en/Fervo-Energys-Record-Breaking-Production-Results-Showcase-Rapid-Scale-Up-of-Enhanced-Geothermal

Fervo Energy. (2025, March 31). Geothermal Mythbusting: Water Use and
Impacts. https://fervoenergy.com/geothermal-mythbusting-water-use-and-impacts/

Fervo Energy. (2025, April 15). Fervo Energy Announces 31 MW Power Purchase Agreement with Shell
Energy. https://fervoenergy.com/fervo-energy-announces-31-mw-power-purchase-agreement-with-shell-energy/

Fervo Energy (2025, June 11). Fervo Energy Secures $206 Million In New Financing To Accelerate Cape Station Development.
https://fervoenergy.com/fervo-secures-new-financing-to-accelerate-development/

Gradl, C. (2018). Review of Recent Unconventional Completion Innovations and their Applicability to EGS Wells. Stanford
Geothermal Workshop.
https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2018/Gradl.pdf

Horne, R., Genter, A., McClure, M. et al. (2025) Enhanced geothermal systems for clean firm energy generation. Nat. Rev.
Clean Technol. 1, 148–160. https://doi.org/10.1038/s44359-024-00019-9

Jacobs, Trent. (2024, September 16). Fervo and FORGE Report Breakthrough Test Results, Signaling More Progress for
Enhanced
Geothermal. https://jpt.spe.org/fervo-and-forge-report-breakthrough-test-results-signaling-more-progress-for-enhanced-geothermal

Jacobs, Trent. (2025, September 5). Baker Hughes Nabs Award for Next Phase of Fervo Energy's Geothermal Power Plant in
Utah.
https://jpt.spe.org/baker-hughes-nabs-award-for-next-phase-of-fervo-energygeothermal-power-plant-in-utah

Ko, S., Ghassemi, A., & Uddenberg, M. (2023). Selection and Testing of Proppants for EGS.
Proceedings, 48th Workshop on Geothermal Reservoir Engineering, Stanford University, Stanford, California.
https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2023/Ko.pdf

Latimer, T. (2025, February 12). Catching up with enhanced geothermal (D. Roberts,
Interviewer). https://www.volts.wtf/p/catching-up-with-enhanced-geothermal

Matson, M. (2024, September 11). Fervo Energy Technology Day 2024: Entering "the Geothermal Decade" with Next-Generation
Geothermal
Energy. https://www.linkedin.com/pulse/fervo-energy-technology-day-2024-entering-geothermal-decade-matson-n4stc/

McClure, M. (2024, September 12). Digesting the Bonkers, Incredible, Off-the-Charts, Spectacular Results from the Fervo
and FORGE Enhanced Geothermal Projects. ResFrac Corporation Blog.
https://www.resfrac.com/blog/digesting-the-bonkers-incredible-off-the-charts-spectacular-results-from-the-fervo-and-forge-enhanced-geothermal-projects

NCEI. US Climate
Normals. https://www.ncei.noaa.gov/access/us-climate-normals/#dataset=normals-annualseasonal&timeframe=30&station=USC00425654

NREL. (2024). Annual Technology Baseline: Geothermal (2024).
https://atb.nrel.gov/electricity/2024/geothermal

NREL. (2025, February 26). Annual Technology Baseline: Geothermal (2024b).
https://atb.nrel.gov/electricity/2024b/geothermal

Norbeck, J. (2026, February 9). An Update of Activities and Plans at Fervo.
Oral presentation at the 51st Workshop on Geothermal Reservoir Engineering, Stanford University, Stanford, CA.
https://pangea.stanford.edu/ERE/db/GeoConf/Abstract.php?PaperID=9496

Norbeck, J., Gradl, C., Latimer, T. (2024, September 10). Deployment of Enhanced Geothermal System Technology Leads to
Rapid Cost Reductions and Performance Improvements. https://doi.org/10.31223/X5VH8C

Norbeck J., Latimer T. (2023). Commercial-Scale Demonstration of a First-of-a-Kind Enhanced Geothermal
System. https://doi.org/10.31223/X52X0B

Quantum Proppant Technologies. (2020). Well Completion Technology. World
Oil. https://quantumprot.com/uploads/images/2b8583e8ce8038681a19d5ad1314e204.pdf

Shiozawa, S., & McClure, M. (2014). EGS Designs with Horizontal Wells, Multiple Stages, and Proppant. ResFrac.
https://www.resfrac.com/wp-content/uploads/2024/07/Shiozawa.pdf

Singh, A., Galban, G., McClure, M. (2025, June 9).
Proceedings of the 2025 Unconventional Resources Technology Conference.
https://www.resfrac.com/wp-content/uploads/2025/06/Singh-2025-Fervo-Project-Cape.pdf

Southern Utah University. (2024, October 23). Fervo Energy, Southern Utah University, and Elemental Impact Launch
Geothermal Drilling & Completions Apprenticeship Program.
https://www.suu.edu/news/2024/10/geothermal-energy-joint-campaign.html

Turboden. (2025, October 2). Turboden selected to deliver 180 MW of Fervo’s Gen 2 ORC Power Plants at Cape Station in
Utah. https://www.turboden.com/company/media/press/press-releases/4881/turboden-selected-to-deliver-180-mw-of-fervos-gen-2-orc-power-plants-at-cape-station-in-utah

U.S. Department of the Interior Bureau of Land Management. (2024, October).
Finding of No Significant Impact and Decision Record DOI-BLM-UT-C010-2024-0018-EA.
https://eplanning.blm.gov/public_projects/2033002/200625761/20120795/251020775/DOI-BLM-UT-C010-2024-0018-EA_FONSI_DR_%20Fervo%20EA_signed.pdf

US DOE. (2021). Combined Heat and Power Technology Fact Sheet Series: Waste Heat to
Power. https://betterbuildingssolutioncenter.energy.gov/sites/default/files/attachments/Waste_Heat_to_Power_Fact_Sheet.pdf

Xing, P., England, K., Moore, J., McLennan, J. (2025, February 10).
Analysis of the 2024 Circulation Tests at Utah FORGE and the Response of Fiber Optic Sensing
Data.
https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Xing2.pdf

Yearsley, E., Kombrink, H. (2024, November 6).
A critical look at Fervo dataset suggests lower output.
https://geoexpro.com/a-critical-look-at-fervo-dataset-suggests-lower-output/

Yusifov, M., & Enriquez, N. (2025, July). From Core to Code: Powering the Al Revolution with Geothermal Energy.
Project InnerSpace. https://projectinnerspace.org/resources/Powering-the-AI-Revolution.pdf

---

## Footnotes
