"""
MotoFreeP synthetic data generator
==================================

Creates the five tables the quota model runs on. Everything here is invented.
A fixed random seed means anyone who runs this script gets identical files.

    python src/generate_data.py      -> writes CSVs to data/

Story of the fictional company
------------------------------
MotoFreeP sells an AI-enabled motorcycle racing simulator to businesses:
riding academies, race teams, dealerships, sim centers and manufacturers.

  Rider Seats      per-seat subscription, one licence per simulator station
  Telemetry Cloud  consumption: customers commit to credits, then burn them down
  AI Race Coach    outcome-based: paid per rider who passes a certified skills
                   assessment (launched FY2025, sold by a specialist overlay team)

History covers FY2023-FY2026 (calendar years). FY2027 is the year being planned,
so this script deliberately creates NO FY2027 quotas -- that is the model's job.

How attainment is generated (so the README can be honest about it)
-------------------------------------------------------------------
Each territory-year's attainment is built from a hidden formula plus random
noise. Some drivers are linear, one (rep tenure) is curved on purpose, and one
field (enablement_hours) has no effect at all. A regression fitted later should
recover roughly these effects -- which demonstrates the method, not a law of
sales. See ATTAINMENT_DRIVERS below.
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 2027
rng = np.random.default_rng(SEED)

OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)

HISTORY_YEARS = [2023, 2024, 2025, 2026]
COACH_LAUNCH_YEAR = 2025

# ---------------------------------------------------------------------------
# 1. Territories: 40 core (one rep each) + 4 AI Race Coach overlay
# ---------------------------------------------------------------------------
TERRITORY_LAYOUT = {  # region: (enterprise territories, commercial territories)
    "AMER": (8, 12),
    "EMEA": (5, 7),
    "APAC": (3, 5),
}
OVERLAY_LAYOUT = {"AMER": 2, "EMEA": 1, "APAC": 1}

territory_rows = []
for region, (n_ent, n_com) in TERRITORY_LAYOUT.items():
    for segment, n in (("Enterprise", n_ent), ("Commercial", n_com)):
        for i in range(1, n + 1):
            territory_rows.append({
                "territory_id": f"{region}-{segment[:3].upper()}-{i:02d}",
                "territory_type": "Core",
                "region": region,
                "segment": segment,
            })
territories = pd.DataFrame(territory_rows)

# Each overlay rep covers a contiguous slice of the core territories in their region
overlay_rows, coverage = [], {}
for region, n_ovl in OVERLAY_LAYOUT.items():
    core_ids = territories.loc[territories.region == region, "territory_id"].tolist()
    for i, chunk in enumerate(np.array_split(core_ids, n_ovl), start=1):
        ovl_id = f"OVL-{region}-{i}"
        overlay_rows.append({"territory_id": ovl_id, "territory_type": "Overlay",
                             "region": region, "segment": "All"})
        for cid in chunk:
            coverage[cid] = ovl_id
territories["overlay_territory_id"] = territories.territory_id.map(coverage)
territories = pd.concat([territories, pd.DataFrame(overlay_rows)], ignore_index=True)

# ---------------------------------------------------------------------------
# 2. Accounts: about 1,500 business customers and prospects
# ---------------------------------------------------------------------------
ACCOUNT_TYPES = {  # type: (share of accounts, typical stations, buys AI Race Coach?)
    "Riding Academy": (0.30, 10, True),
    "Riding School":  (0.25, 4,  True),
    "Dealership":     (0.20, 3,  False),
    "Sim Center":     (0.12, 14, False),
    "Race Team":      (0.10, 6,  False),
    "Manufacturer":   (0.03, 25, False),
}
NAME_PARTS = ["Apex", "Redline", "Throttle", "Kneedown", "Chicane", "Hairpin",
              "Paddock", "Pitlane", "Gridline", "Torque", "Slipstream", "Holeshot",
              "Lean Angle", "Braking Point", "Rev Limit", "Checkered", "Tank Slap",
              "Highside", "Wheelie", "Countersteer", "Trail Brake", "Quickshift"]
TYPE_SUFFIX = {"Riding Academy": "Riding Academy", "Riding School": "Moto School",
               "Dealership": "Motorcycles", "Sim Center": "Sim Center",
               "Race Team": "Racing", "Manufacturer": "Moto Works"}
CITIES = {
    "AMER": ["Austin", "Denver", "Atlanta", "Phoenix", "Toronto", "Seattle",
             "Charlotte", "Monterey", "Sao Paulo", "Mexico City", "Portland"],
    "EMEA": ["Barcelona", "Mugello", "Le Mans", "Assen", "Silverstone",
             "Valencia", "Munich", "Brno", "Portimao", "Dubai"],
    "APAC": ["Motegi", "Buriram", "Sepang", "Mandalika", "Phillip Island",
             "Jakarta", "Melbourne", "Osaka"],
}

core = territories[territories.territory_type == "Core"].reset_index(drop=True)
# Enterprise territories hold fewer, larger accounts
accounts_per_terr = np.where(core.segment == "Enterprise", 26, 45)
accounts_per_terr[: 1500 - accounts_per_terr.sum()] += 1  # top up to exactly 1,500

types = list(ACCOUNT_TYPES)
type_probs = np.array([v[0] for v in ACCOUNT_TYPES.values()])

acct_rows, used_names = [], set()
for t, n in zip(core.itertuples(), accounts_per_terr):
    for _ in range(n):
        a_type = rng.choice(types, p=type_probs)
        _, base_stations, _ = ACCOUNT_TYPES[a_type]
        size_mult = 2.2 if t.segment == "Enterprise" else 1.0
        stations = max(1, int(rng.lognormal(np.log(base_stations * size_mult), 0.5)))
        # unique, readable account name
        name = None
        while name is None or name in used_names:
            name = (f"{rng.choice(NAME_PARTS)} {TYPE_SUFFIX[a_type]} "
                    f"{rng.choice(CITIES[t.region])}")
            if name in used_names:
                name = f"{name} {rng.integers(2, 9)}"
        used_names.add(name)
        acct_rows.append({
            "account_name": name,
            "account_type": a_type,
            "region": t.region,
            "segment": t.segment,
            "territory_id": t.territory_id,
            "simulator_stations": stations,
            "riders": int(stations * rng.uniform(6, 20)),
            "telemetry_volume_index": round(float(stations * rng.lognormal(0, 0.6)), 1),
            "enrolled_students": (int(stations * rng.uniform(15, 45))
                                  if ACCOUNT_TYPES[a_type][2] else 0),
        })
accounts = pd.DataFrame(acct_rows)
accounts.insert(0, "account_id", [f"A{i:05d}" for i in range(1, len(accounts) + 1)])

# Who owns what today (start of FY2027), and current ARR by product
accounts["owns_rider_seats"] = rng.random(len(accounts)) < 0.62
accounts["licensed_stations"] = np.where(
    accounts.owns_rider_seats,
    np.maximum(1, (accounts.simulator_stations * rng.uniform(0.3, 1.0, len(accounts))).astype(int)),
    0)
accounts["owns_telemetry_cloud"] = accounts.owns_rider_seats & (rng.random(len(accounts)) < 0.38)
accounts["owns_ai_race_coach"] = (accounts.owns_rider_seats & (accounts.enrolled_students > 0)
                                  & (rng.random(len(accounts)) < 0.30))

def scale_to(values, total):
    """Rescale a column so it sums to `total` dollars."""
    values = np.asarray(values, dtype=float)
    return np.round(values / values.sum() * total, -2)

accounts["arr_rider_seats"] = scale_to(accounts.licensed_stations * rng.uniform(0.8, 1.2, len(accounts)), 62_000_000)
accounts["arr_telemetry_cloud"] = scale_to(np.where(accounts.owns_telemetry_cloud,
                                                     accounts.telemetry_volume_index, 0), 14_000_000)
accounts["arr_ai_race_coach"] = scale_to(np.where(accounts.owns_ai_race_coach,
                                                   accounts.enrolled_students, 0), 4_000_000)

# ---------------------------------------------------------------------------
# 3. Territory potential (whitespace dollars still available to sell)
# ---------------------------------------------------------------------------
accounts["_ws_rider_seats"] = (accounts.simulator_stations - accounts.licensed_stations) * 2_400
accounts["_ws_telemetry"] = np.where(accounts.owns_telemetry_cloud, 0.6, 1.0) * accounts.telemetry_volume_index * 4_000
accounts["_ws_coach"] = np.where(accounts.owns_ai_race_coach, 0.5, 1.0) * accounts.enrolled_students * 180

pot = accounts.groupby("territory_id")[["_ws_rider_seats", "_ws_telemetry", "_ws_coach"]].sum()
pot.columns = ["potential_rider_seats_usd", "potential_telemetry_cloud_usd", "potential_ai_race_coach_usd"]
territories = territories.merge(pot.round(-3).reset_index(), on="territory_id", how="left")
# overlay potential = AI Race Coach potential of the core territories it covers
for ovl in territories.loc[territories.territory_type == "Overlay", "territory_id"]:
    covered = territories.overlay_territory_id == ovl
    territories.loc[territories.territory_id == ovl, "potential_ai_race_coach_usd"] = \
        territories.loc[covered, "potential_ai_race_coach_usd"].sum()
accounts = accounts.drop(columns=[c for c in accounts if c.startswith("_ws")])

# ---------------------------------------------------------------------------
# 4. Reps: seat history Jan 2023 - Dec 2026, with attrition and backfills
# ---------------------------------------------------------------------------
# Names assigned in order of first appearance: MotoGP grid, then Moto2,
# then MotoAmerica Superbike (2026 entry lists).
MOTOGP = ["Marc Marquez", "Francesco Bagnaia", "Pedro Acosta", "Brad Binder",
          "Jorge Martin", "Marco Bezzecchi", "Fabio Quartararo", "Alex Rins",
          "Luca Marini", "Joan Mir", "Fabio Di Giannantonio", "Franco Morbidelli",
          "Alex Marquez", "Fermin Aldeguer", "Jack Miller", "Toprak Razgatlioglu",
          "Raul Fernandez", "Ai Ogura", "Maverick Vinales", "Enea Bastianini",
          "Johann Zarco", "Diogo Moreira"]
MOTO2 = ["Joe Roberts", "Filip Salac", "Daniel Holgado", "David Alonso",
         "Izan Guevara", "Alberto Ferrandez", "Barry Baltus", "Tony Arbolino",
         "Sergio Garcia", "Alonso Lopez", "Mario Aji", "Taiyo Furusato",
         "Adrian Huertas", "Daniel Munoz", "Jorge Navarro", "Alex Escrig",
         "Senna Agius", "Manuel Gonzalez", "Aron Canet", "Deniz Oncu",
         "Angel Piqueras", "Ivan Ortola", "Collin Veijer", "Jose Antonio Rueda",
         "Ayumu Sasaki", "Zonta van den Goorbergh", "Celestino Vietti", "Luca Lunetta"]
MOTOAMERICA_SBK = ["Cameron Beaubier", "Mathew Scholtz", "Bobby Fong", "JD Beach",
                   "Sean Dylan Kelly", "Cameron Petersen", "PJ Jacobsen",
                   "Richie Escalante", "Brandon Paasch", "Benjamin Smith",
                   "Jayson Uribe", "Hayden Gillim", "Andrew Lee", "Max Flinders"]
NAME_POOL = iter(MOTOGP + MOTO2 + MOTOAMERICA_SBK)

MONTHS = pd.period_range("2023-01", "2026-12", freq="M")
ANNUAL_ATTRITION = 0.12
monthly_quit = 1 - (1 - ANNUAL_ATTRITION) ** (1 / 12)

rep_rows, seat_log = [], []  # seat_log: one row per territory per month

def new_rep(territory_id, segment, start_period, tenure_at_start=0):
    rep_id = f"R{len(rep_rows) + 1:03d}"
    hire = (start_period - tenure_at_start).to_timestamp()
    rep_rows.append({"rep_id": rep_id, "rep_name": next(NAME_POOL),
                     "territory_id": territory_id, "segment": segment,
                     "hire_date": hire.date(), "departure_date": None})
    return rep_id

seats = territories[["territory_id", "territory_type", "segment"]].copy()
for s in seats.itertuples():
    is_overlay = s.territory_type == "Overlay"
    first_month = pd.Period(f"{COACH_LAUNCH_YEAR}-01", "M") if is_overlay else MONTHS[0]
    rep = new_rep(s.territory_id, s.segment, first_month,
                  0 if is_overlay else int(rng.integers(3, 61)))
    vacant_until = None
    for m in MONTHS:
        if m < first_month:
            continue
        if rep is None and m >= vacant_until:             # backfill hire starts
            rep = new_rep(s.territory_id, s.segment, m)
        seat_log.append({"territory_id": s.territory_id, "month": m, "rep_id": rep})
        if rep is not None and rng.random() < monthly_quit:  # rep leaves at month end
            rep_rows[int(rep[1:]) - 1]["departure_date"] = (m.to_timestamp(how="end")).date()
            rep, vacant_until = None, m + int(rng.integers(2, 4))  # 1-2 empty months

reps = pd.DataFrame(rep_rows)
seat_log = pd.DataFrame(seat_log)

# ---------------------------------------------------------------------------
# 5. History: quota and actuals per core territory per year
# ---------------------------------------------------------------------------
CORE_TARGET = {2022: 10.0e6, 2023: 12.0e6, 2024: 14.5e6, 2025: 16.5e6, 2026: 18.5e6}
TELEMETRY_SHARE = {2022: 0.14, 2023: 0.18, 2024: 0.24, 2025: 0.29, 2026: 0.33}
COACH_TARGET = {2025: 1.5e6, 2026: 2.8e6}
OVER_ASSIGNMENT = 1.12
POTENTIAL_GROWTH = 1.05  # whitespace grew ~5% a year as the market expanded

# Hidden "truth" used to create attainment. Written out so the README can show
# how close the regression gets.
ATTAINMENT_DRIVERS = {
    "baseline": 0.92,
    "tenure_max_lift": 0.22,       # curved: most of the lift lands in year one
    "tenure_months_scale": 9,
    "per_1x_pipeline_coverage": 0.07,
    "per_1x_potential_ratio": 0.035,
    "per_10pct_quota_growth": -0.035,
    "per_10pct_telemetry_share": -0.025,
    "enterprise": -0.02, "emea": -0.02, "apac": -0.04,
    "noise_sd": 0.10,
    "extra_noise_per_telemetry_share": 0.12,  # consumption quotas are more volatile
}
D = ATTAINMENT_DRIVERS

core_t = territories[territories.territory_type == "Core"].set_index("territory_id")
core_pot_total = (core_t.potential_rider_seats_usd + core_t.potential_telemetry_cloud_usd)

prev_quota = {}      # territory -> previous year's total quota
prev_actual_share = (core_pot_total / core_pot_total.sum()) * rng.uniform(0.85, 1.15, len(core_t))
prev_actual_share /= prev_actual_share.sum()
# FY2022 baseline quotas (not output) so FY2023 has a quota-growth figure
prev_quota = (CORE_TARGET[2022] * OVER_ASSIGNMENT * prev_actual_share).to_dict()

hist_rows = []
for year in HISTORY_YEARS:
    years_back = 2027 - year
    pot_rs = core_t.potential_rider_seats_usd / POTENTIAL_GROWTH ** years_back
    pot_tc = core_t.potential_telemetry_cloud_usd / POTENTIAL_GROWTH ** years_back
    pot_share = (pot_rs + pot_tc) / (pot_rs + pot_tc).sum()

    # How quotas were set that year: half potential, half last year's results, plus judgment
    alloc = (0.5 * pot_share + 0.5 * prev_actual_share) * rng.uniform(0.92, 1.08, len(core_t))
    alloc /= alloc.sum()
    total_quota = CORE_TARGET[year] * OVER_ASSIGNMENT * alloc

    # Telemetry share of each territory's quota follows its telemetry potential mix
    tc_mix = pot_tc / (pot_rs + pot_tc)
    tc_share = (TELEMETRY_SHARE[year] * tc_mix / tc_mix.mean()).clip(0.03, 0.75)

    year_months = seat_log[seat_log.month.dt.year == year]
    actual_totals = {}
    for tid, t in core_t.iterrows():
        q = round(float(total_quota[tid]), -3)
        q_tc = round(q * float(tc_share[tid]), -3)
        q_rs = q - q_tc

        months = year_months[year_months.territory_id == tid]
        vacancy_months = int(months.rep_id.isna().sum())
        start_rep = months.iloc[0].rep_id
        if pd.isna(start_rep):
            start_rep = months.rep_id.dropna().iloc[0]
            tenure = 0
        else:
            hire = pd.Timestamp(reps.loc[reps.rep_id == start_rep, "hire_date"].iloc[0])
            tenure = max(0, (year - hire.year) * 12 - (hire.month - 1))

        potential_ratio = float((pot_rs[tid] + pot_tc[tid]) / q)
        pipeline_cov = float(np.clip(
            2.6 + 0.25 * (potential_ratio - 5) + 0.015 * min(tenure, 36) + rng.normal(0, 0.55),
            0.8, 6.0))
        quota_growth = q / prev_quota[tid] - 1
        share_tc = q_tc / q
        enablement_hours = int(rng.integers(4, 40))  # decoy: no effect on results

        att = (D["baseline"]
               + D["tenure_max_lift"] * (1 - np.exp(-tenure / D["tenure_months_scale"])) - D["tenure_max_lift"] / 2
               + D["per_1x_pipeline_coverage"] * (pipeline_cov - 3)
               + D["per_1x_potential_ratio"] * (potential_ratio - 5)
               + D["per_10pct_quota_growth"] * quota_growth * 10
               + D["per_10pct_telemetry_share"] * (share_tc - 0.25) * 10
               + (D["enterprise"] if t.segment == "Enterprise" else 0)
               + {"AMER": 0, "EMEA": D["emea"], "APAC": D["apac"]}[t.region]
               + rng.normal(0, D["noise_sd"] + D["extra_noise_per_telemetry_share"] * share_tc))
        att *= 1 - 0.8 * vacancy_months / 12   # empty seat months cost most of their share
        att = max(0.15, att)

        actual = att * q
        # split actual between products; telemetry is credited 50% commit / 50% consumed
        actual_tc_credit = actual * share_tc * rng.uniform(0.7, 1.3)
        actual_rs = actual - actual_tc_credit
        burn = float(np.clip(rng.normal(0.85, 0.2), 0.3, 1.4))  # consumed / committed
        committed = 2 * actual_tc_credit / (1 + burn)
        consumed = committed * burn

        hist_rows.append({
            "fiscal_year": year, "territory_id": tid, "region": t.region,
            "segment": t.segment, "rep_id_at_start": start_rep,
            "rep_tenure_months_at_start": tenure, "vacancy_months": vacancy_months,
            "quota_total_usd": q, "quota_rider_seats_usd": q_rs,
            "quota_telemetry_cloud_usd": q_tc,
            "actual_rider_seats_usd": round(actual_rs, -2),
            "actual_telemetry_committed_usd": round(committed, -2),
            "actual_telemetry_consumed_usd": round(consumed, -2),
            "actual_telemetry_credited_usd": round(actual_tc_credit, -2),
            "actual_total_credited_usd": round(actual_rs + actual_tc_credit, -2),
            "attainment_pct": round((actual_rs + actual_tc_credit) / q, 4),
            "territory_potential_usd": round(float(pot_rs[tid] + pot_tc[tid]), -3),
            "potential_to_quota_ratio": round(potential_ratio, 3),
            "pipeline_coverage_at_start": round(pipeline_cov, 2),
            "quota_growth_pct": round(quota_growth, 4),
            "telemetry_share_of_quota": round(share_tc, 4),
            "enablement_hours": enablement_hours,
        })
        actual_totals[tid] = actual_rs + actual_tc_credit
        prev_quota[tid] = q

    s = pd.Series(actual_totals)
    prev_actual_share = (s / s.sum()).reindex(core_t.index)

history = pd.DataFrame(hist_rows)

# Overlay history (AI Race Coach), FY2025-FY2026: few rows, so no regression
ovl_rows = []
ovl_t = territories[territories.territory_type == "Overlay"].set_index("territory_id")
for year, target in COACH_TARGET.items():
    share = ovl_t.potential_ai_race_coach_usd / ovl_t.potential_ai_race_coach_usd.sum()
    for tid, t in ovl_t.iterrows():
        q = round(float(target * OVER_ASSIGNMENT * share[tid]), -3)
        att = float(np.clip(rng.normal(0.78 if year == 2025 else 0.92, 0.15), 0.3, 1.5))
        price = 450  # per certified rider
        ovl_rows.append({"fiscal_year": year, "territory_id": tid, "region": t.region,
                         "quota_ai_race_coach_usd": q,
                         "actual_ai_race_coach_usd": round(att * q, -2),
                         "riders_certified": int(att * q / price),
                         "attainment_pct": round(att, 4)})
overlay_history = pd.DataFrame(ovl_rows)

# ---------------------------------------------------------------------------
# 6. Monthly usage for consumption and outcome products, FY2025-FY2026
# ---------------------------------------------------------------------------
usage_rows = []
usage_months = pd.period_range("2025-01", "2026-12", freq="M")
for a in accounts[accounts.owns_telemetry_cloud | accounts.owns_ai_race_coach].itertuples():
    tc_monthly_commit = a.arr_telemetry_cloud / 12
    burn = float(np.clip(rng.normal(0.85, 0.2), 0.3, 1.4))
    for i, m in enumerate(usage_months):
        seasonal = 1 + 0.25 * np.sin(2 * np.pi * (m.month - 3) / 12)  # riding season peaks mid-year
        ramp = min(1.0, 0.5 + i / 12)
        usage_rows.append({
            "account_id": a.account_id, "month": str(m),
            "telemetry_credits_committed_usd": round(tc_monthly_commit, 2) if a.owns_telemetry_cloud else 0.0,
            "telemetry_credits_used_usd": (round(tc_monthly_commit * burn * seasonal * ramp
                                                 * rng.uniform(0.8, 1.2), 2)
                                           if a.owns_telemetry_cloud else 0.0),
            "riders_certified": (int(a.arr_ai_race_coach / 450 / 12 * seasonal * rng.uniform(0.6, 1.4))
                                 if a.owns_ai_race_coach and m.year >= COACH_LAUNCH_YEAR else 0),
        })
usage_monthly = pd.DataFrame(usage_rows)

# ---------------------------------------------------------------------------
# 7. Write files
# ---------------------------------------------------------------------------
accounts.to_csv(OUT / "accounts.csv", index=False)
territories.to_csv(OUT / "territories.csv", index=False)
reps.to_csv(OUT / "reps.csv", index=False)
history.to_csv(OUT / "history_core.csv", index=False)
overlay_history.to_csv(OUT / "history_overlay.csv", index=False)
usage_monthly.to_csv(OUT / "usage_monthly.csv", index=False)

if __name__ == "__main__":
    print(f"accounts        {len(accounts):>6}")
    print(f"territories     {len(territories):>6}")
    print(f"reps            {len(reps):>6}  (names used: {len(reps)} of {len(MOTOGP + MOTO2 + MOTOAMERICA_SBK)})")
    print(f"history_core    {len(history):>6}")
    print(f"history_overlay {len(overlay_history):>6}")
    print(f"usage_monthly   {len(usage_monthly):>6}")
