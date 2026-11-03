# MotoFreeP FY2027 Quota Model

An end-to-end sales planning model for a fictional company, built on fully synthetic data: capacity, territory carve, leadership cascade, rep quotas, pipeline coverage, and a regression-based attainment forecast used as a gut check on the quotas.

**Try the demo:** [Team quota review](https://bpthemachine.github.io/motofreep-quota-model/). Pick a team leader, move quota between reps inside a fixed team total, and watch the guardrails and the attainment forecast update.

## The company

MotoFreeP sells an AI-enabled motorcycle racing simulator to riding academies, schools, dealerships, sim centers, race teams and manufacturers. It has about $80M of starting ARR and 1,500 accounts, and its three product lines each use a different pricing model:

| Product | Pricing model | What counts toward quota |
|---|---|---|
| Rider Seats | Per seat: a licence per simulator station | New annual contract value at signature |
| Telemetry Cloud | Consumption: committed credits drawn down, overage at on-demand rates | 50% of committed value at signing + 50% of consumed revenue in-year |
| AI Race Coach | Outcome-based: paid per rider who passes a certified skills assessment | Outcome revenue realized, floored at the contracted minimum |

AI Race Coach is sold by a specialist overlay team with partial dual credit: the overlay rep gets 100% and the core rep 50%.

The FY2027 plan has 48 core territories (AMER, EMEA and APAC; Enterprise and Commercial) and 6 overlay territories. History covers FY2023 to FY2026. Reps are named after current MotoGP, Moto2 and MotoAmerica riders, and leaders after retired premier-class champions.

## How the plan was built

1. **Targets.** Commercial at FY2026 actuals + 15%, Enterprise at + 14%. The AI Race Coach target comes from an attach-rate goal (31% to 60% of 487 eligible customers), not a growth rate.
2. **Capacity.** A monthly, rep-by-rep model: ramped productivity derived from history (+13%, the four-year average), ramp curves matched to measured sales cycles, a vacancy backfill lag and an attrition haircut. The first build showed a 19% gap to the target. History-backed productivity, earlier start dates, more hires and two overlay reps closed most of it.
3. **Plan locked.** A scenario table compared investing, lowering the target to capacity, and meeting in the middle. The plan is $20.58M core and $3.63M overlay, against $20.15M and $3.53M of capacity.
4. **Territory carve.** 8 new core territories and 2 overlay. Each region-segment was rebalanced on open pipeline, FY2026 bookings, potential, accounts and customers. Deals closing by March 31 stay with the current rep, and prior-year quota was rebased onto the new map.
5. **Quota cascade.** CRO → geo leaders → AVPs (AMER only) → team leaders → reps. Leaders carry 100% of their number; over-assignment happens once, between team leaders and reps. Inside each team, reps are allocated on 50% potential and 50% FY2026 actuals, ramp-weighted.
6. **Guardrails.** No quota above 1.2x the rep's FY2027 capacity or more than +50% above their FY2026 rebased quota. Quota a capped rep can't take spreads to teammates with headroom.
7. **Coverage.** Open pipeline against plan, with separate conversion rates for starting pipeline and pipeline created in-year, plus creation deadlines.
8. **Attainment forecast.** A regression that predicts each territory's attainment from start-of-year inputs, written into the quota model and rolled up to every leader (below).

Every workbook has a Checks tab. All 12 quota model checks pass.

## The attainment forecast

This part draws on my MBA coursework in Predictive Analytics. The dataset is synthetic, with relationships planted on purpose, so the regression demonstrates the method; it doesn't discover a real-world truth.

**Round 1 failed its test.** Trained on FY2023–FY2025 and tested on FY2026, the model lost to simply predicting the training average (RMSE 0.181 vs. 0.158) and was about 7 points too pessimistic. My diagnosis was that Telemetry Cloud's share of quota rose every year and was standing in for a year-over-year decline, and that FY2026 values sat outside the training range.

**Round 2 followed a review with my professor:**
- **Predictor audit.** In-year vacancy months and enablement hours aren't known on January 1, so both came out. Vacancy belongs in the capacity model's attrition haircut instead.
- **Chronological backtest.** Two folds (train FY2023 → test FY2024; train FY2023–24 → test FY2025) scored four specifications against two baselines: the training average and each territory's prior-year attainment.
- **Choice.** The specification without telemetry share had the lowest average error and the smallest bias. Removing it cut fold 1's bias from 21 points to 4, which supported the round 1 diagnosis.
- **Inference.** Refit on all four years with territory-clustered standard errors. Clustering changed little: residuals barely correlate year to year, and territory effects add nothing (F-test p = 0.29).

| | Train average | Prior year | Chosen model |
|---|---|---|---|
| RMSE, average of two folds | 0.152 | 0.235 | **0.141** |
| Rank correlation (Spearman) | n/a | −0.31 | 0.41 |

Prior-year attainment was the worst predictor of all: last year's laggards tended to bounce back.

**Final model** (160 territory-years, adjusted R² 0.27):

| Predictor | Effect |
|---|---|
| Tenure, capped at 12 months | About +2 points of attainment per month in year one |
| Pipeline coverage at start | About +6 points per extra 1x of coverage |
| Quota growth vs. prior year | About −2.5 points per 10% of growth |
| Potential ÷ quota | About +4 points per +1 |
| Region and segment | Not significant; kept as controls |

**What the gut check found.** With 110% over-assignment, reps with a forecast were on track for 76% of quota. The cause was the post-carve quota growth on ramped reps, up to +93%. Lowering over-assignment to 105% and adding the +50% growth cap lifted that to 79% and cut the biggest increase to +50%. The forecast for the company plan stayed at about 83%, because moving quota between reps doesn't change the total the team has to deliver. The remaining gap traces to the 13% productivity growth assumption.

Most FY2027 inputs sit outside the training range after the re-carve, so the quota model flags each out-of-range territory, shows an 80% range rather than a single number, and gives no forecast for new or heavily ramping territories.

## What's in the repo

| Path | Contents |
|---|---|
| `excel/MotoFreeP_FY2027_Capacity_Plan.xlsx` | Inputs, capacity by rep and month, hiring plan, roll-forward, scenarios, history, opportunities |
| `excel/MotoFreeP_FY2027_Territories.xlsx` | Territory summary, overlay coverage, balance log, pipeline transfers, account assignments |
| `excel/MotoFreeP_FY2027_Quota_Model.xlsx` | Plan inputs, hierarchy, leadership cascade, core and overlay quotas, coverage, forecast model, checks |
| `excel/MotoFreeP_Attainment_Regression.xlsx` | Scatter plots, model comparisons, the round 1 holdout test, the predictor audit, chronological backtest folds and summary |
| `data/` | Synthetic source data and FY2027 outputs as CSV ([field notes](data/README.md)) |
| `src/generate_data.py`, `src/generate_opportunities.py` | Generate the synthetic company, history and opportunities |
| `src/carve_territories.py` | Territory carve and rebalance |
| `src/build_quota_workbooks.py` | Builds the quota workbook template (the calculations were then built in Excel) |
| `src/s2_clustered.R` | Final regression with territory-clustered standard errors |
| `docs/index.html` | The team-leader demo, served by GitHub Pages |

## Running it

The workbooks open in Excel (Microsoft 365) with no setup. To regenerate the data, install the packages in `requirements.txt` and run `python src/generate_data.py`, then `python src/generate_opportunities.py`. To rerun the regression, open R in the `data/` folder, run `install.packages(c("sandwich", "lmtest"))` once, then `source("../src/s2_clustered.R")`.

## Assumptions and limitations

- All data is synthetic. Relationships in the attainment data were planted, including one field with no effect, to test whether the method finds what's real.
- Four years of history means only two honest backtest folds. A numeric year trend could be tested in only one, so it wasn't adopted.
- The forecast extrapolates for most FY2027 territories. Treat it as a signal for where to look, not a prediction of anyone's final number.
- Over-assignment, guardrails and allocation weights are inputs on the Plan tab, so the model can be re-run under other choices.

## Who built what

I made the planning and modeling decisions and built the core capacity and quota calculations in Excel. Claude generated the synthetic data, scripts and workbook templates. My Predictive Analytics professor was consulted on the attainment forecast model.
