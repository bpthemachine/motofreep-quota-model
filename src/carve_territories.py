"""
MotoFreeP FY2027 territory carve
================================

Creates the FY2027 territory map for growth hires, using these rules:

  1. New core territories by region and segment: AMER 5 (Enterprise 3,
     Commercial 2), EMEA 2 (Enterprise 1, Commercial 1), APAC 1 (Enterprise 1).
  2. Every region-segment that gains a territory is rebalanced across all of
     its territories, in this priority order (weights 40/25/20/10/5%):
       1 open pipeline credited for FY2027, 2 FY2026 won core bookings,
       3 core potential, 4 account count, 5 customer count.
     It starts from today's map and moves an account only when that improves
     balance by more than a small penalty, so relationships stay where they can.
  3. Accounts move on 1 Jan 2027. Pipeline protection ("sell what you can see"):
     open deals expected to close by 31 Mar 2027 stay credited to the current
     rep; later deals follow the account to its new rep.
  4. Prior-year quota and actuals are rebased to the new map in proportion to
     each account's FY2026 won bookings, so year-over-year guardrails compare
     like with like.
  5. Customer = owns Rider Seats today; Prospect = owns nothing yet.

Overlay: one new overlay territory in AMER and one in EMEA. Core territories in
each region are re-divided across the overlay team, balancing AI Race Coach
potential.

    python src/carve_territories.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
NEW_BY_SEGMENT = {"Enterprise": 5, "Commercial": 3}
REGION_SLOTS = {"AMER": 5, "EMEA": 2, "APAC": 1}
NEW_OVERLAY_REGIONS = ["AMER", "EMEA"]
PROTECT_UNTIL = pd.Timestamp("2027-03-31")

acc = pd.read_csv(DATA / "accounts.csv")
terr = pd.read_csv(DATA / "territories.csv")
opps = pd.read_csv(DATA / "opportunities.csv", parse_dates=["close_date_or_expected"])
hist = pd.read_csv(DATA / "history_core.csv")

# ---------------------------------------------------------------- account potential
acc["potential_rider_seats_usd"] = (acc.simulator_stations - acc.licensed_stations) * 2_400
acc["potential_telemetry_cloud_usd"] = (np.where(acc.owns_telemetry_cloud, 0.6, 1.0)
                                        * acc.telemetry_volume_index * 4_000)
acc["potential_ai_race_coach_usd"] = (np.where(acc.owns_ai_race_coach, 0.5, 1.0)
                                      * acc.enrolled_students * 180)
acc["potential_core_usd"] = acc.potential_rider_seats_usd + acc.potential_telemetry_cloud_usd
acc["fy2026_territory_id"] = acc.territory_id
acc["fy2027_territory_id"] = acc.territory_id

core = terr[terr.territory_type == "Core"][["territory_id", "region", "segment"]].copy()
core["carved_from"] = ""

# ---------------------------------------------------------------- account-level facts used for balancing
acc["account_status"] = np.where(acc.owns_rider_seats, "Customer", "Prospect")
acc["is_customer"] = (acc.account_status == "Customer").astype(int)
won = opps[opps.stage == "Closed Won"].copy()
won["fy"] = won.fiscal_year_closed.astype(int)
wide = won.pivot_table(index="account_id", columns=["fy", "product"], values="amount_usd",
                       aggfunc="sum", fill_value=0)
wide.columns = [f"won_{p.lower().replace(' ', '_')}_fy{y}_usd" for y, p in wide.columns]
acc = acc.merge(wide, left_on="account_id", right_index=True, how="left")
acc[wide.columns] = acc[wide.columns].fillna(0)
acc["won_core_fy2026_usd"] = acc.won_rider_seats_fy2026_usd + acc.won_telemetry_cloud_fy2026_usd
op_core = opps[(opps.stage == "Open") & (opps["product"] != "AI Race Coach")]
early = op_core[op_core.close_date_or_expected <= PROTECT_UNTIL].groupby("account_id").amount_usd.sum()
late = op_core[op_core.close_date_or_expected > PROTECT_UNTIL].groupby("account_id").amount_usd.sum()
acc["pipeline_protected_usd"] = acc.account_id.map(early).fillna(0)     # stays with FY2026 rep
acc["pipeline_transferable_usd"] = acc.account_id.map(late).fillna(0)   # follows the account
acc["open_pipeline_core_usd"] = acc.pipeline_protected_usd + acc.pipeline_transferable_usd

# ---------------------------------------------------------------- new territories (regional mix agreed: AMER 5, EMEA 2, APAC 1)
NEW_TERRITORIES = [("AMER", "Enterprise", 3), ("AMER", "Commercial", 2), ("EMEA", "Enterprise", 1),
                   ("EMEA", "Commercial", 1), ("APAC", "Enterprise", 1)]
for region, seg, n in NEW_TERRITORIES:
    for _ in range(n):
        k = ((core.region == region) & (core.segment == seg)).sum() + 1
        core = pd.concat([core, pd.DataFrame([{"territory_id": f"{region}-{seg[:3].upper()}-{k:02d}",
                                               "region": region, "segment": seg, "carved_from": "New in FY2027"}])],
                         ignore_index=True)

# ---------------------------------------------------------------- rebalance each region-segment that gained territories
# Priority: 1 open pipeline credited, 2 FY2026 won core bookings, 3 core potential,
# 4 account count, 5 customer count. Starts from today's map and moves an account only when it
# improves balance by more than a small "keep the relationship" penalty, so moves stay minimal.
WEIGHTS = np.array([0.40, 0.25, 0.20, 0.10, 0.05])
MOVE_PENALTY = 0.0015
balance_log = []
for region, seg, _ in NEW_TERRITORIES:
    if any(b["region"] == region and b["segment"] == seg for b in balance_log):
        continue
    tids = list(core.loc[(core.region == region) & (core.segment == seg), "territory_id"])
    g = acc[(acc.region == region) & (acc.segment == seg)].copy()
    t_index = {t: i for i, t in enumerate(tids)}
    home = g.fy2026_territory_id.map(t_index).to_numpy()
    cur = home.copy()
    # per-account contributions: [transferable pipeline, won FY26, potential, 1, customer]; protected pipeline is fixed at home
    X = np.c_[g.pipeline_transferable_usd, g.won_core_fy2026_usd, g.potential_core_usd,
              np.ones(len(g)), g.is_customer].astype(float)
    fixed = np.zeros((len(tids), 5))
    np.add.at(fixed[:, 0], home, g.pipeline_protected_usd.to_numpy())
    totals = X.sum(0) + fixed.sum(0)
    target = totals / len(tids)

    def loads(assign):
        L = fixed.copy()
        np.add.at(L, assign, X)
        return L

    def score(L):
        return float((WEIGHTS * (np.abs(L - target).sum(0) / np.where(totals > 0, totals, 1))).sum())

    L = loads(cur)
    before = L.copy()
    for _pass in range(40):
        improved = False
        for i in np.random.default_rng(_pass).permutation(len(g)):
            best_gain, best_t = 0.0, None
            base = score(L)
            for t in range(len(tids)):
                if t == cur[i]:
                    continue
                L2 = L.copy()
                L2[cur[i]] -= X[i]
                L2[t] += X[i]
                pen = (MOVE_PENALTY if t != home[i] else 0) - (MOVE_PENALTY if cur[i] != home[i] else 0)
                gain = base - score(L2) - pen
                if gain > best_gain + 1e-9:
                    best_gain, best_t = gain, t
            if best_t is not None:
                L[cur[i]] -= X[i]
                L[best_t] += X[i]
                cur[i] = best_t
                improved = True
        if not improved:
            break
    acc.loc[g.index, "fy2027_territory_id"] = [tids[t] for t in cur]
    names = ["open pipeline credited", "FY2026 won core", "core potential", "accounts", "customers"]
    cv = lambda M: (M.std(0) / np.where(M.mean(0) > 0, M.mean(0), 1))
    for k, n in enumerate(names):
        balance_log.append({"region": region, "segment": seg, "territories": len(tids), "metric": n,
                            "priority": k + 1, "weight": WEIGHTS[k],
                            "spread_before_cv": round(float(cv(before)[k]), 3),
                            "spread_after_cv": round(float(cv(L)[k]), 3),
                            "accounts_moved": int((cur != home).sum()),
                            "accounts_in_group": len(g)})
carve_log = pd.DataFrame(balance_log)
acc["moved_in_fy2027_carve"] = acc.fy2026_territory_id != acc.fy2027_territory_id

# ---------------------------------------------------------------- pipeline protection
open_opps = opps[opps.stage == "Open"].merge(
    acc[["account_id", "fy2026_territory_id", "fy2027_territory_id", "moved_in_fy2027_carve"]],
    on="account_id", how="left")
is_core = open_opps["product"] != "AI Race Coach"
protected = open_opps.moved_in_fy2027_carve & (open_opps.close_date_or_expected <= PROTECT_UNTIL)
open_opps["fy2027_credit_territory_id"] = np.where(
    ~is_core, open_opps.owner_territory_id,
    np.where(protected, open_opps.fy2026_territory_id, open_opps.fy2027_territory_id))
open_opps["pipeline_rule"] = np.select(
    [~is_core, ~open_opps.moved_in_fy2027_carve, protected],
    ["Overlay deal (unchanged)", "Account not moved", "Protected: closes by 31 Mar, stays with current rep"],
    default="Transferred: closes after 31 Mar, goes to new rep")
transfers = open_opps[open_opps.moved_in_fy2027_carve & is_core][[
    "opportunity_id", "account_id", "account_name", "product", "amount_usd", "close_date_or_expected",
    "fy2026_territory_id", "fy2027_territory_id", "fy2027_credit_territory_id", "pipeline_rule"]].copy()

# ---------------------------------------------------------------- rebase FY2026 quota and actuals
h26 = hist[hist.fiscal_year == 2026].set_index("territory_id")
w = acc.groupby(["fy2026_territory_id", "fy2027_territory_id"]).won_core_fy2026_usd.sum().reset_index()
w["share_of_parent"] = w.won_core_fy2026_usd / w.groupby("fy2026_territory_id").won_core_fy2026_usd.transform("sum")
w["fy2026_quota_rebased"] = w.share_of_parent * w.fy2026_territory_id.map(h26.quota_total_usd)
w["fy2026_actual_rebased"] = w.share_of_parent * w.fy2026_territory_id.map(h26.actual_total_credited_usd)
rebased = w.groupby("fy2027_territory_id")[["fy2026_quota_rebased", "fy2026_actual_rebased"]].sum().round(-2)

# ---------------------------------------------------------------- territory summary
roll = acc.groupby("fy2027_territory_id").agg(
    accounts=("account_id", "size"),
    customers=("is_customer", "sum"),
    accounts_moved_in=("moved_in_fy2027_carve", "sum"),
    potential_rider_seats_usd=("potential_rider_seats_usd", "sum"),
    potential_telemetry_cloud_usd=("potential_telemetry_cloud_usd", "sum"),
    potential_ai_race_coach_usd=("potential_ai_race_coach_usd", "sum"),
    won_core_fy2026_usd=("won_core_fy2026_usd", "sum"))
pipe = open_opps[is_core].groupby("fy2027_credit_territory_id").amount_usd.sum().rename("open_pipeline_credited_usd")
summary = (core.set_index("territory_id").join(roll).join(rebased).join(pipe).fillna({"open_pipeline_credited_usd": 0}))
summary["potential_core_usd"] = summary.potential_rider_seats_usd + summary.potential_telemetry_cloud_usd
summary["prospects"] = summary.accounts - summary.customers

# ---------------------------------------------------------------- overlay coverage
ovl = terr[terr.territory_type == "Overlay"][["territory_id", "region"]].copy()
for region in NEW_OVERLAY_REGIONS:
    k = (ovl.region == region).sum() + 1
    ovl = pd.concat([ovl, pd.DataFrame([{"territory_id": f"OVL-{region}-{k}", "region": region}])],
                    ignore_index=True)
coverage = {}
for region, g in summary.reset_index().groupby("region"):
    load = {o: 0.0 for o in sorted(ovl.loc[ovl.region == region, "territory_id"])}
    for t in g.sort_values("potential_ai_race_coach_usd", ascending=False).itertuples():
        o = min(load, key=load.get)
        coverage[t.territory_id] = o
        load[o] += t.potential_ai_race_coach_usd
summary["overlay_territory_id"] = summary.index.map(coverage)
summary["share_of_overlay_coach_potential"] = (summary.potential_ai_race_coach_usd /
    summary.groupby("overlay_territory_id").potential_ai_race_coach_usd.transform("sum"))
# AI Race Coach pipeline follows the account's new overlay, with the same 31 Mar protection
co = open_opps[~is_core].copy()
co["new_overlay"] = co.fy2027_territory_id.map(coverage)
co_moved = co.new_overlay != co.owner_territory_id
co_prot = co_moved & (co.close_date_or_expected <= PROTECT_UNTIL)
co["fy2027_credit_territory_id"] = np.where(co_prot, co.owner_territory_id, co.new_overlay)
co["pipeline_rule"] = np.select([~co_moved, co_prot], ["Overlay unchanged",
    "Protected: closes by 31 Mar, stays with current overlay rep"],
    default="Transferred: closes after 31 Mar, goes to new overlay rep")
transfers = pd.concat([transfers, co[co_moved][transfers.columns]], ignore_index=True)
coach_pipe = co.groupby("fy2027_credit_territory_id").amount_usd.sum()
coach_won26 = won[(won["product"] == "AI Race Coach") & (won.fy == 2026)].merge(
    acc[["account_id", "fy2027_territory_id"]], on="account_id")
coach_won26["ovl27"] = coach_won26.fy2027_territory_id.map(coverage)
ovl = ovl.set_index("territory_id")
ovl["core_territories_covered"] = summary.groupby("overlay_territory_id").size()
ovl["potential_ai_race_coach_usd"] = summary.groupby("overlay_territory_id").potential_ai_race_coach_usd.sum()
ovl["fy2026_ai_race_coach_won_rebased_usd"] = coach_won26.groupby("ovl27").amount_usd.sum()
ovl["open_pipeline_ai_race_coach_usd"] = coach_pipe.reindex(ovl.index).fillna(0)
ovl = ovl.fillna(0)

# ---------------------------------------------------------------- write
acc_cols = ["account_id", "account_name", "account_type", "account_status", "region", "segment", "fy2026_territory_id",
            "fy2027_territory_id", "moved_in_fy2027_carve", "simulator_stations", "licensed_stations",
            "enrolled_students", "potential_rider_seats_usd", "potential_telemetry_cloud_usd",
            "potential_ai_race_coach_usd", "arr_rider_seats", "arr_telemetry_cloud", "arr_ai_race_coach",
            "open_pipeline_core_usd", "pipeline_protected_usd", "pipeline_transferable_usd"] + sorted(wide.columns)
acc[acc_cols].round(2).to_csv(DATA / "accounts_fy2027.csv", index=False)
summary.reset_index().rename(columns={"index": "territory_id"}).round(4).to_csv(DATA / "territories_fy2027.csv", index=False)
ovl.reset_index().to_csv(DATA / "overlay_territories_fy2027.csv", index=False)
carve_log.to_csv(DATA / "carve_log_fy2027.csv", index=False)
transfers.to_csv(DATA / "pipeline_transfers_fy2027.csv", index=False)

if __name__ == "__main__":
    print(carve_log.to_string())
    print(summary[summary.region.isin(["AMER","EMEA","APAC"])][["region","segment","accounts","customers","open_pipeline_credited_usd","won_core_fy2026_usd","potential_core_usd"]].sort_index().to_string())
    print(transfers.pipeline_rule.value_counts(), transfers.groupby("pipeline_rule").amount_usd.sum())
    print(ovl.to_string())
    print("check totals:", round(summary.fy2026_quota_rebased.sum()), round(h26.quota_total_usd.sum()),
          round(summary.fy2026_actual_rebased.sum()), round(h26.actual_total_credited_usd.sum()))
