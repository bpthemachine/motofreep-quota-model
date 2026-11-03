"""
MotoFreeP synthetic opportunities (deal-level history)
======================================================

Builds data/opportunities.csv from the tables generate_data.py already wrote,
so every deal ties back to the history:

  * Closed Won amounts add up exactly to each territory-year's actuals
      Rider Seats     -> history_core.actual_rider_seats_usd
      Telemetry Cloud -> history_core.actual_telemetry_committed_usd
                         (contract value; quota credit is 50% commit + 50% consumed)
      AI Race Coach   -> history_overlay.actual_ai_race_coach_usd
  * Deals open on 1 January of a year add up to that territory's starting
    pipeline (history_core.pipeline_coverage_at_start x quota)
  * Open deals at the end of FY2026 form the FY2027 starting pipeline

Sales cycles are drawn so Enterprise deals take longer than Commercial, larger
deals take longer than smaller ones, and Q4 closes more business than Q1.

    python src/generate_opportunities.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(4627)
DATA = Path(__file__).resolve().parent.parent / "data"

history = pd.read_csv(DATA / "history_core.csv")
overlay = pd.read_csv(DATA / "history_overlay.csv")
accounts = pd.read_csv(DATA / "accounts.csv")
territories = pd.read_csv(DATA / "territories.csv")
reps = pd.read_csv(DATA / "reps.csv", parse_dates=["hire_date", "departure_date"])

# Typical deal size (median, $) and sales cycle (median days) by segment and product
DEAL_SIZE = {("Commercial", "Rider Seats"): 22_000, ("Enterprise", "Rider Seats"): 55_000,
             ("Commercial", "Telemetry Cloud"): 28_000, ("Enterprise", "Telemetry Cloud"): 75_000,
             ("Commercial", "AI Race Coach"): 20_000, ("Enterprise", "AI Race Coach"): 38_000}
CYCLE_DAYS = {("Commercial", "Rider Seats"): 95, ("Enterprise", "Rider Seats"): 165,
              ("Commercial", "Telemetry Cloud"): 115, ("Enterprise", "Telemetry Cloud"): 195,
              ("Commercial", "AI Race Coach"): 60, ("Enterprise", "AI Race Coach"): 90}
WIN_RATE = {"Commercial": 0.27, "Enterprise": 0.21}
# Close-month weights: back-loaded quarters, heavy Q4
MONTH_WEIGHT = np.array([0.6, 0.7, 1.1, 0.7, 0.8, 1.1, 0.7, 0.8, 1.1, 0.9, 1.1, 1.8])
MONTH_WEIGHT = MONTH_WEIGHT / MONTH_WEIGHT.sum()

acct_by_terr = {t: g for t, g in accounts.groupby("territory_id")}
seg_of = territories.set_index("territory_id").segment.to_dict()
region_of = territories.set_index("territory_id").region.to_dict()
overlay_of = territories.set_index("territory_id").overlay_territory_id.to_dict()


def rep_in_seat(territory_id, when):
    """rep_id holding the territory on a date, or None if the seat was vacant."""
    r = reps[(reps.territory_id == territory_id) & (reps.hire_date <= when)
             & (reps.departure_date.isna() | (reps.departure_date >= when))]
    return r.rep_id.iloc[0] if len(r) else None


def split_amount(total, median):
    """Break a dollar total into deal sizes that add up exactly."""
    if total <= 0:
        return []
    sizes = []
    while sum(sizes) < total:
        sizes.append(float(rng.lognormal(np.log(median), 0.55)))
    sizes = np.array(sizes) * total / sum(sizes)
    sizes = np.round(sizes, -2)
    sizes[-1] += round(total - sizes.sum(), 2)
    return [s for s in sizes if s > 0]


def cycle_for(seg, product, amount):
    base = CYCLE_DAYS[(seg, product)]
    size_factor = (amount / DEAL_SIZE[(seg, product)]) ** 0.3   # bigger deals take longer
    return int(np.clip(rng.lognormal(np.log(base * size_factor), 0.35), 14, 540))


def close_date_in(year, early=False):
    w = MONTH_WEIGHT.copy()
    if early:                       # deals already open on 1 Jan tend to close in H1
        w = w * np.linspace(1.8, 0.3, 12)
        w = w / w.sum()
    m = rng.choice(12, p=w) + 1
    day = int(rng.integers(1, pd.Timestamp(year=year, month=m, day=1).days_in_month + 1))
    return pd.Timestamp(year=year, month=m, day=day)


rows = []


def add(territory_id, product, amount, stage, created, closed, owner_territory=None):
    seg = seg_of[territory_id]
    acct = acct_by_terr[territory_id].sample(1, random_state=int(rng.integers(1e9))).iloc[0]
    owner_t = owner_territory or territory_id
    when = closed if stage != "Open" else pd.Timestamp("2026-12-31")
    rows.append({
        "account_id": acct.account_id,
        "account_name": acct.account_name,
        "territory_id": territory_id,
        "region": region_of[territory_id],
        "segment": seg,
        "product": product,
        "deal_type": "New logo" if (product == "Rider Seats" and not acct.owns_rider_seats
                                    and rng.random() < 0.7) else "Expansion",
        "owner_territory_id": owner_t,
        "owner_rep_id": rep_in_seat(owner_t, when),
        "amount_usd": amount,
        "stage": stage,
        "created_date": created.date(),
        "close_date": closed.date(),
        "cycle_days": (closed - created).days if stage != "Open" else None,
    })


def build_year(territory_id, year, product, won_total, start_pipeline, seg_owner=None):
    seg = seg_of[territory_id]
    median = DEAL_SIZE[(seg, product)]
    jan1 = pd.Timestamp(year=year, month=1, day=1)

    # 1) Deals already open on 1 January: some win, the rest are lost
    start_deals = split_amount(start_pipeline, median)
    won_from_start = 0.0
    for amt in start_deals:
        closed = close_date_in(year, early=True)
        created = closed - pd.Timedelta(days=cycle_for(seg, product, amt))
        if created >= jan1:
            created = jan1 - pd.Timedelta(days=int(rng.integers(10, 90)))
        wins = won_from_start + amt <= 0.55 * won_total and rng.random() < 0.55
        if wins:
            won_from_start += amt
        add(territory_id, product, amt, "Closed Won" if wins else "Closed Lost",
            created, closed, seg_owner)

    # 2) Deals created and closed inside the year make up the rest of the wins
    remaining = round(won_total - won_from_start, 2)
    for amt in split_amount(remaining, median):
        for _ in range(20):
            closed = close_date_in(year)
            created = closed - pd.Timedelta(days=cycle_for(seg, product, amt))
            if created >= jan1:
                break
        else:
            created = jan1 + pd.Timedelta(days=int(rng.integers(0, 30)))
            closed = max(closed, created + pd.Timedelta(days=21))
        add(territory_id, product, amt, "Closed Won", created, closed, seg_owner)

    # 3) Losses created inside the year, sized to the segment's win rate
    lost_total = remaining * (1 / WIN_RATE[seg] - 1)
    for amt in split_amount(round(lost_total, -2), median):
        for _ in range(20):
            closed = close_date_in(year)
            created = closed - pd.Timedelta(days=int(cycle_for(seg, product, amt) * 0.8))
            if created >= jan1:
                break
        else:
            created = jan1 + pd.Timedelta(days=int(rng.integers(0, 30)))
            closed = max(closed, created + pd.Timedelta(days=21))
        add(territory_id, product, amt, "Closed Lost", created, closed, seg_owner)


# Core products
for h in history.itertuples():
    start_pipe = h.pipeline_coverage_at_start * h.quota_total_usd
    rs_share = h.quota_rider_seats_usd / h.quota_total_usd
    build_year(h.territory_id, h.fiscal_year, "Rider Seats",
               h.actual_rider_seats_usd, round(start_pipe * rs_share, -2))
    build_year(h.territory_id, h.fiscal_year, "Telemetry Cloud",
               h.actual_telemetry_committed_usd, round(start_pipe * (1 - rs_share), -2))

# AI Race Coach: overlay actuals spread over the core territories each overlay covers
core = territories[territories.territory_type == "Core"]
for o in overlay.itertuples():
    covered = core[core.overlay_territory_id == o.territory_id].copy()
    weight = covered.potential_ai_race_coach_usd / covered.potential_ai_race_coach_usd.sum()
    start_cov = 1.2 if o.fiscal_year == 2025 else 2.0      # thin pipeline in launch year
    won = (o.actual_ai_race_coach_usd * weight).round(-2).to_numpy().copy()
    won[-1] += o.actual_ai_race_coach_usd - won.sum()      # keep the overlay total exact
    for c, w, won_c in zip(covered.territory_id, weight, won):
        build_year(c, o.fiscal_year, "AI Race Coach", float(won_c),
                   round(o.quota_ai_race_coach_usd * w * start_cov, -2),
                   seg_owner=o.territory_id)

# FY2027 starting pipeline: deals open on 31 Dec 2026
last = history[history.fiscal_year == 2026].set_index("territory_id")
for t, h in last.iterrows():
    seg = seg_of[t]
    cov = float(np.clip(rng.normal(2.7, 0.6), 1.2, 4.5))
    rs_share = h.quota_rider_seats_usd / h.quota_total_usd
    for product, share in (("Rider Seats", rs_share), ("Telemetry Cloud", 1 - rs_share)):
        for amt in split_amount(round(cov * h.quota_total_usd * 1.12 * share, -2),
                                DEAL_SIZE[(seg, product)]):
            created = pd.Timestamp("2026-12-31") - pd.Timedelta(days=int(rng.integers(5, 240)))
            expected = close_date_in(2027, early=True)
            add(t, product, amt, "Open", created, expected)
ovl_t = territories[territories.territory_type == "Overlay"]
for o in ovl_t.itertuples():
    covered = core[core.overlay_territory_id == o.territory_id]
    for c in covered.territory_id:
        seg = seg_of[c]
        for amt in split_amount(round(float(rng.uniform(150_000, 320_000)), -2),
                                DEAL_SIZE[(seg, "AI Race Coach")]):
            created = pd.Timestamp("2026-12-31") - pd.Timedelta(days=int(rng.integers(5, 150)))
            add(c, "AI Race Coach", amt, "Open", created, close_date_in(2027, early=True),
                owner_territory=o.territory_id)

opps = pd.DataFrame(rows).sort_values(["close_date", "territory_id"]).reset_index(drop=True)
opps.insert(0, "opportunity_id", [f"OPP-{i:05d}" for i in range(1, len(opps) + 1)])
opps["fiscal_year_closed"] = pd.to_datetime(opps.close_date).dt.year
opps.loc[opps.stage == "Open", "fiscal_year_closed"] = None
opps.rename(columns={"close_date": "close_date_or_expected"}, inplace=True)
opps.to_csv(DATA / "opportunities.csv", index=False)

if __name__ == "__main__":
    print(f"opportunities {len(opps):,}")
    print(opps.groupby(["stage"]).amount_usd.agg(["count", "sum"]))
