"""
Builds the two FY2027 workbooks:

  MotoFreeP_FY2027_Territories.xlsx   territory system of record (Fullcast role)
  MotoFreeP_FY2027_Quota_Model.xlsx   quota model, fed by a dated snapshot of the territory file
                                      and the locked plan from the capacity workbook

    python src/build_quota_workbooks.py <roster_snapshot.json> <out_dir>
"""

import json
import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

DATA = Path(__file__).resolve().parent.parent / "data"
roster_json, OUT = Path(sys.argv[1]), Path(sys.argv[2])
SNAP = "20 Oct 2026"

F = "Arial"
H_FILL = PatternFill("solid", fgColor="1F3A5F")
DATA_FILL = PatternFill("solid", fgColor="EEF2F7")
CALC_FILL = PatternFill("solid", fgColor="FFF2CC")
Y = PatternFill("solid", fgColor="FFFF00")
f_h = Font(name=F, bold=True, color="FFFFFF", size=10)
f_b = Font(name=F, bold=True, size=10)
f_t = Font(name=F, bold=True, size=14, color="1F3A5F")
f_n = Font(name=F, size=10)
f_blue = Font(name=F, size=10, color="0000FF")
f_green = Font(name=F, size=10, color="008000")
f_note = Font(name=F, size=9, italic=True, color="595959")
CUR = '$#,##0;($#,##0);-'
PCT = '0.0%'


def header(ws, row, cols, fill=H_FILL):
    for i, h in enumerate(cols, 1):
        c = ws.cell(row, i, h)
        c.font, c.fill = f_h, fill
        c.alignment = Alignment(wrap_text=True, vertical="top")


def df_sheet(wb, name, df, fmts=None, widths=None):
    ws = wb.create_sheet(name)
    header(ws, 1, list(df.columns))
    for r in df.itertuples(index=False):
        ws.append([None if (isinstance(v, float) and pd.isna(v)) else v for v in r])
    for i, col in enumerate(df.columns, 1):
        ws.column_dimensions[get_column_letter(i)].width = (widths or {}).get(col, max(12, min(26, len(col) + 2)))
        fmt = (fmts or {}).get(col) or (CUR if col.endswith("_usd") else None)
        for (cell,) in ws.iter_rows(min_row=2, min_col=i, max_col=i):
            cell.font = f_n
            if fmt:
                cell.number_format = fmt
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def readme(wb, lines):
    ws = wb.active
    ws.title = "README"
    for i, (t, style) in enumerate(lines, 1):
        ws.cell(i, 1, t).font = {"t": f_t, "b": f_b, "n": f_n}[style]
    ws.column_dimensions["A"].width = 140


terr = pd.read_csv(DATA / "territories_fy2027.csv")
ovl = pd.read_csv(DATA / "overlay_territories_fy2027.csv")
acc = pd.read_csv(DATA / "accounts_fy2027.csv")
carve = pd.read_csv(DATA / "carve_log_fy2027.csv")
transfers = pd.read_csv(DATA / "pipeline_transfers_fy2027.csv")
roster = pd.DataFrame(json.load(open(roster_json)))

# ===================================================================== territory workbook
wb = Workbook()
readme(wb, [
    ("MotoFreeP FY2027 Territories — territory system of record", "t"),
    (f"Snapshot as of {SNAP}. All data is synthetic. This file plays the role a territory tool such as Fullcast plays: "
     "it owns the account-to-territory map, and the quota model imports a snapshot of it.", "n"),
    ("", "n"),
    ("Carving rules", "b"),
    ("1. Eight new core territories: AMER 5 (Enterprise 3, Commercial 2), EMEA 2 (Enterprise 1, Commercial 1), APAC 1 (Enterprise 1).", "n"),
    ("2. Each region-segment that gains a territory is rebalanced across all its territories, in priority order: open pipeline "
     "credited, FY2026 won core bookings, core potential, account count, customer count (weights 40/25/20/10/5%).", "n"),
    ("3. Balancing starts from today's map and only moves an account when it improves balance by more than a small "
     "keep-the-relationship penalty. APAC Commercial gained no territory and is unchanged.", "n"),
    ("4. Pipeline protection, 'sell what you can see': accounts move on 1 Jan 2027; open deals expected to close by 31 Mar 2027 "
     "stay credited to the current rep, later deals transfer to the new rep.", "n"),
    ("5. FY2026 quota and actuals are rebased to the new map in proportion to each account's FY2026 won bookings, "
     "so year-over-year guardrails compare like with like.", "n"),
    ("6. Overlay: new OVL-AMER-3 and OVL-EMEA-2; core territories in each region re-divided to balance AI Race Coach potential.", "n"),
    ("", "n"),
    ("Tabs", "b"),
    ("Territory_Summary: one row per FY2027 core territory — potential by product, rebased FY2026 quota and actuals, "
     "open pipeline credited for FY2027, overlay coverage.", "n"),
    ("Overlay_Coverage: one row per overlay territory.", "n"),
    ("Balance_Log: for each rebalanced region-segment, how evenly each metric is spread before and after "
     "(coefficient of variation: standard deviation ÷ average; lower is more even) and how many accounts moved.", "n"),
    ("Pipeline_Transfers: every open deal on a moved account and whether it was protected or transferred.", "n"),
    ("Accounts: all 1,500 accounts with FY2026 and FY2027 territory, potential, ARR, open pipeline and won bookings by "
     "product for FY2023–FY2026.", "n"),
])
ts = terr.rename(columns={"fy2026_quota_rebased": "fy2026_quota_rebased_usd",
                          "fy2026_actual_rebased": "fy2026_actual_rebased_usd"})
ts = ts[["territory_id", "region", "segment", "carved_from", "accounts", "customers", "prospects", "accounts_moved_in",
         "potential_rider_seats_usd", "potential_telemetry_cloud_usd", "potential_core_usd",
         "potential_ai_race_coach_usd", "fy2026_quota_rebased_usd", "fy2026_actual_rebased_usd",
         "won_core_fy2026_usd", "open_pipeline_credited_usd", "overlay_territory_id",
         "share_of_overlay_coach_potential"]]
ts["carved_from"] = ts.carved_from.fillna("").replace("", "—")
df_sheet(wb, "Territory_Summary", ts, {"share_of_overlay_coach_potential": PCT, "accounts": "0",
                                       "accounts_moved_in": "0", "customers": "0", "prospects": "0"})
df_sheet(wb, "Overlay_Coverage", ovl, {"core_territories_covered": "0"})
df_sheet(wb, "Balance_Log", carve, {"weight": PCT, "spread_before_cv": "0.000", "spread_after_cv": "0.000"},
         {"metric": 24})
df_sheet(wb, "Pipeline_Transfers", transfers, {"close_date_or_expected": "yyyy-mm-dd"},
         {"pipeline_rule": 52, "account_name": 34})
df_sheet(wb, "Accounts", acc, {"moved_in_fy2027_carve": None}, {"account_name": 34})
wb.save(OUT / "MotoFreeP_FY2027_Territories.xlsx")

# ===================================================================== quota workbook
q = Workbook()
readme(q, [
    ("MotoFreeP FY2027 Quota Model", "t"),
    (f"Fed by two snapshots taken {SNAP}: the territory file (MotoFreeP_FY2027_Territories.xlsx) and the locked plan "
     "and rep capacity from MotoFreeP_FY2027_Capacity_Plan.xlsx. Values are pasted, not linked, the way a territory-tool "
     "export is imported into a quota model. Re-import when either source changes.", "n"),
    ("", "n"),
    ("How to use", "b"),
    ("1. Plan: confirm the locked targets, then set the yellow planning inputs (allocation weight, guardrails).", "n"),
    ("Hierarchy: who reports to whom, and which territories sit in which team. Leaders are retired premier-class champions.", "n"),
    ("2. Quota_Core: blue-grey columns are linked data — don't edit. Build the cream columns left to right; row 6 says what each one does.", "n"),
    ("3. Quota_Overlay: same pattern for the six overlay territories. Build it before the AI Race Coach credit column on Quota_Core.", "n"),
    ("4. Leadership: the cascade from company to team leader. Section 1 splits targets across geos; section 2 sets every "
     "leader's number and checks the roll-up.", "n"),
    ("5. Checks: updates as the model calculates. Every check should read OK before quotas are published.", "n"),
    ("", "n"),
    ("Colour legend", "b"),
    ("Yellow fill = planning input · Blue text = hardcoded input · Black = formula · Green = link to another tab · "
     "Blue-grey fill = imported data · Cream fill = calculated column", "n"),
    ("", "n"),
    ("The cascade: company → geo leaders → AVPs (AMER only) → team leaders → reps", "b"),
    ("Leaders carry 100% of their number; over-assignment (110%) is added only between team leaders and their reps, so it "
     "never compounds. Geo split is by capacity share. Team leaders also carry 50% AI Race Coach credit, which rolls up.", "n"),
    ("Build order: Leadership tab section 1 (geo split) → Quota_Overlay → Quota_Core → Leadership section 2 (leader numbers "
     "and roll-up) → Checks.", "n"),
    ("", "n"),
    ("Order of the rep calculation (inside each team)", "b"),
    ("Potential share and actuals share within the team → blended share (weight w) → ramp-weighted share, re-normalised within "
     "the team → raw quota = team leader's core number × over-assignment × share → guardrail cap vs. rebased FY2026 quota → "
     "final core quota → + 50% AI Race Coach credit → product split → quota ÷ capacity.", "n"),
    ("Why ramp-weight before allocating: a new or ramping rep gets a smaller share, and the quota they don't carry is spread "
     "across ramped reps, so quotas still add up to target × over-assignment.", "n"),
])
p = q.create_sheet("Plan")
header(p, 1, ["Plan input", "Value", "Units", "Source / note"])
plan = [
    (3, "Locked FY2027 targets", None, None, None, "sec"),
    (4, "Core target (Option 4, meet in the middle)", 20580000, "$", "Capacity_Plan, Capacity!H106", "in"),
    (5, "Net capacity — Enterprise", 9282021, "$", "Capacity_Plan, Capacity!F71", "in"),
    (6, "Net capacity — Commercial", 10872478, "$", "Capacity_Plan, Capacity!F72", "in"),
    (7, "Net capacity — Core total", "=B5+B6", "$", "", "f"),
    (8, "FY2027 target — Enterprise", "=B4*B5/B7", "$", "Core target split by capacity share", "f"),
    (9, "FY2027 target — Commercial", "=B4*B6/B7", "$", "Core target split by capacity share", "f"),
    (10, "FY2027 target — AI Race Coach overlay", 3630000, "$", "Capacity_Plan, Capacity!H110", "in"),
    (12, "Quota setting", None, None, None, "sec"),
    (13, "Over-assignment (quotas sum to this % of target)", 1.10, "%", "110% (Capacity_Plan Inputs!B35)", "in"),
    (14, "Core rep credit on AI Race Coach", 0.5, "%", "Overlay 100%, core rep 50%", "in"),
    (15, "Allocation weight on potential (w)", None, "%", "Share = w × potential share + (1 − w) × FY2026 "
                                                         "actuals share. 50% is a common starting point", "y"),
    (16, "Maximum quota increase vs. rebased FY2026 quota", 0.30, "%", "Design spec default; confirm or change", "y"),
    (18, "Reference: ramped productivity (Capacity_Plan Inputs)", None, None, None, "sec"),
    (19, "Enterprise", 638450, "$", "FY2026 + 13%", "in"),
    (20, "Commercial", 487100, "$", "FY2026 + 13%", "in"),
    (21, "AI Race Coach overlay", 750000, "$", "FY2026 actuals per rep", "in"),
]
for r, label, v, unit, note, kind in plan:
    p.cell(r, 1, label).font = f_b if kind == "sec" else f_n
    if kind == "sec":
        continue
    c = p.cell(r, 2, v)
    c.font = f_blue if kind in ("in", "y") else f_n
    c.number_format = PCT if unit == "%" else CUR
    if kind == "y":
        c.fill = Y
    p.cell(r, 3, unit).font = f_n
    p.cell(r, 4, note).font = f_n
for col, w in zip("ABCD", [48, 16, 8, 80]):
    p.column_dimensions[col].width = w

# --- imports (values)
ti = df_sheet(q, "Territory_Import", ts, {"share_of_overlay_coach_potential": PCT, "accounts": "0",
                                          "accounts_moved_in": "0"})
oi = df_sheet(q, "Overlay_Import", ovl, {"core_territories_covered": "0"})

# --- roster: FY2027 territory -> rep, with ramp factor from capacity snapshot
assign_new = {"TBH-NH3": "AMER-ENT-09", "TBH-NH4": "AMER-ENT-10", "TBH-NH5": "APAC-ENT-04",
              "TBH-NH10": "AMER-ENT-11", "TBH-NH6": "EMEA-ENT-06", "TBH-NH1": "AMER-COM-13",
              "TBH-NH2": "AMER-COM-14", "TBH-NH9": "EMEA-COM-08", "TBH-NH7": "OVL-AMER-3",
              "TBH-NH8": "OVL-EMEA-2"}
roster["fy2027_territory_id"] = roster.apply(lambda r: assign_new.get(r.rep_id, r.territory), axis=1)
roster["rep_name"] = roster.apply(lambda r: r["name"] if isinstance(r["name"], str) and r["name"] else f"To be hired ({r.rep_id})", axis=1)
roster["full_year_ramped_productivity_usd"] = roster.monthly * 12
roster["fy2027_capacity_gross_usd"] = roster.cap.round(0)
roster["ramp_factor"] = (roster.cap / (roster.monthly * 12)).round(4)
ro = roster[["fy2027_territory_id", "rep_id", "rep_name", "segment", "start",
             "full_year_ramped_productivity_usd", "fy2027_capacity_gross_usd", "ramp_factor"]].rename(
    columns={"start": "start_date"})
ro["start_date"] = pd.to_datetime(ro.start_date)
rws = df_sheet(q, "Roster", ro, {"ramp_factor": PCT, "start_date": "yyyy-mm-dd"})
rws.cell(len(ro) + 3, 1, "Ramp factor = rep's FY2027 capacity before the attrition haircut ÷ a full year of ramped "
                         "productivity. 100% = ramped all year; new hires and backfills are lower.").font = f_note
rws.cell(len(ro) + 4, 1, "New-hire territory assignments made in the carve: earliest start dates took the first carved "
                         "territories. Update Capacity_Plan column C to match if you want the two files aligned.").font = f_note

# --- sales hierarchy (leaders are named after retired premier-class champions)
core_ids = list(ts.territory_id)
seg_code = {"Enterprise": "ENT", "Commercial": "COM"}
team_of = {}
for (region, seg), g in ts.groupby(["region", "segment"]):
    n_teams = 2 if region == "AMER" else 1
    order = g.sort_values("potential_core_usd", ascending=False).territory_id.tolist()
    for i, tid in enumerate(order):                       # snake draft keeps teams balanced
        k = i % (2 * n_teams)
        k = k if k < n_teams else 2 * n_teams - 1 - k
        team_of[tid] = f"T-{region}-{seg_code[seg]}" + (f"-{k + 1}" if n_teams > 1 else "")
for tid in ovl.territory_id:
    team_of[tid] = "T-OVERLAY"
leaders = [
    ("L-CRO", "Giacomo Agostini", "Chief Revenue Officer", "Global", "All", "", ""),
    ("L-GEO-AMER", "Kenny Roberts", "Geo leader", "AMER", "All", "", "L-CRO"),
    ("L-GEO-EMEA", "Valentino Rossi", "Geo leader", "EMEA", "All", "", "L-CRO"),
    ("L-GEO-APAC", "Mick Doohan", "Geo leader", "APAC", "All", "", "L-CRO"),
    ("L-AVP-AMER-ENT", "Wayne Rainey", "AVP", "AMER", "Enterprise", "", "L-GEO-AMER"),
    ("L-AVP-AMER-COM", "Kevin Schwantz", "AVP", "AMER", "Commercial", "", "L-GEO-AMER"),
    ("L-TL-AMER-ENT-1", "Eddie Lawson", "Team leader", "AMER", "Enterprise", "T-AMER-ENT-1", "L-AVP-AMER-ENT"),
    ("L-TL-AMER-ENT-2", "Freddie Spencer", "Team leader", "AMER", "Enterprise", "T-AMER-ENT-2", "L-AVP-AMER-ENT"),
    ("L-TL-AMER-COM-1", "Kenny Roberts Jr.", "Team leader", "AMER", "Commercial", "T-AMER-COM-1", "L-AVP-AMER-COM"),
    ("L-TL-AMER-COM-2", "Marco Lucchinelli", "Team leader", "AMER", "Commercial", "T-AMER-COM-2", "L-AVP-AMER-COM"),
    ("L-TL-EMEA-ENT", "Alex Criville", "Team leader", "EMEA", "Enterprise", "T-EMEA-ENT", "L-GEO-EMEA"),
    ("L-TL-EMEA-COM", "Franco Uncini", "Team leader", "EMEA", "Commercial", "T-EMEA-COM", "L-GEO-EMEA"),
    ("L-TL-APAC-ENT", "Casey Stoner", "Team leader", "APAC", "Enterprise", "T-APAC-ENT", "L-GEO-APAC"),
    ("L-TL-APAC-COM", "Wayne Gardner", "Team leader", "APAC", "Commercial", "T-APAC-COM", "L-GEO-APAC"),
    ("L-TL-OVERLAY", "Dani Pedrosa", "Overlay team leader", "Global", "AI Race Coach", "T-OVERLAY", "L-CRO"),
]
lead = pd.DataFrame(leaders, columns=["leader_id", "leader_name", "role", "region", "segment", "team_id", "reports_to_id"])
tmap = pd.DataFrame({"territory_id": list(team_of), "team_id": list(team_of.values())})
lead.to_csv(DATA / "sales_leaders_fy2027.csv", index=False)
tmap.to_csv(DATA / "territory_teams_fy2027.csv", index=False)

hz = q.create_sheet("Hierarchy")
hz["A1"] = "FY2027 sales hierarchy"
hz["A1"].font = f_t
hz["A2"] = ("AVPs only in AMER, where a segment has two teams; elsewhere team leaders report straight to the geo leader. "
            "Teams in AMER were filled by a snake draft on core potential so they come out balanced.")
hz["A2"].font = f_note
header(hz, 4, list(lead.columns))
for i, r in enumerate(lead.itertuples(index=False), 5):
    for j, v in enumerate(r, 1):
        hz.cell(i, j, v).font = f_n
TM0 = 5 + len(lead) + 2
hz.cell(TM0, 1, "Territory → team").font = f_b
header(hz, TM0 + 1, ["territory_id", "team_id"])
for i, r in enumerate(tmap.itertuples(index=False), TM0 + 2):
    hz.cell(i, 1, r.territory_id).font = f_n
    hz.cell(i, 2, r.team_id).font = f_n
TM_FIRST, TM_LAST = TM0 + 2, TM0 + 1 + len(tmap)
for col, w in zip("ABCDEFG", [18, 20, 22, 9, 14, 16, 18]):
    hz.column_dimensions[col].width = w


def build_tab(ws, title, note, data_cols, calc_cols, ids, src_sheet, src_cols, n_src, roster_n):
    """data_cols: (header, source) — source 'R:col' roster, 'H:team' hierarchy, else import column.
       calc_cols: (header, instruction with {header} placeholders, fmt)."""
    ws["A1"], ws["A2"] = title, note
    ws["A1"].font, ws["A2"].font = f_t, f_note
    letters = {h: get_column_letter(i + 1) for i, (h, _) in enumerate(data_cols)}
    nd = len(data_cols)
    letters.update({h: get_column_letter(nd + 1 + j) for j, (h, _, _) in enumerate(calc_cols)})
    ws.cell(4, 1, "Imported data — don't edit").font = f_b
    ws.cell(4, nd + 1, "Calculations").font = f_b
    for i, (h, _) in enumerate(data_cols, 1):
        c = ws.cell(HR, i, h)
        c.font, c.fill, c.alignment = f_h, H_FILL, Alignment(wrap_text=True, vertical="top")
    for j, (h, how, _) in enumerate(calc_cols):
        col = nd + 1 + j
        c = ws.cell(HR, col, h)
        c.font, c.fill, c.alignment = Font(name=F, bold=True, size=10), CALC_FILL, Alignment(wrap_text=True, vertical="top")
        txt = how.format(**{k.replace(" ", "_").replace("'", "").replace("(", "").replace(")", "").replace("÷", "per")
                            .replace(":", "").replace(",", ""): v for k, v in letters.items()})
        g = ws.cell(IR, col, f"{get_column_letter(col)}: {txt}")
        g.font, g.alignment = f_note, Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[HR].height = 42
    ws.row_dimensions[IR].height = 78
    for k, tid in enumerate(ids):
        r = R0 + k
        ws.cell(r, 1, tid).font = f_n
        for i, (h, src) in enumerate(data_cols[1:], 2):
            if src.startswith("R:"):
                col = rcols[src[2:]]
                f = f"=INDEX(Roster!${col}$2:${col}${roster_n + 1},MATCH($A{r},Roster!$A$2:$A${roster_n + 1},0))"
            elif src == "H:team":
                f = f"=INDEX(Hierarchy!$B${TM_FIRST}:$B${TM_LAST},MATCH($A{r},Hierarchy!$A${TM_FIRST}:$A${TM_LAST},0))"
            else:
                col = src_cols[src]
                f = (f"=INDEX({src_sheet}!${col}$2:${col}${n_src + 1},"
                     f"MATCH($A{r},{src_sheet}!$A$2:$A${n_src + 1},0))")
            c = ws.cell(r, i, f)
            c.font, c.fill = f_green, DATA_FILL
            if src.endswith("_usd"):
                c.number_format = CUR
            elif src in ("R:ramp_factor", "share_of_overlay_coach_potential"):
                c.number_format = PCT
            elif src == "R:start_date":
                c.number_format = "yyyy-mm-dd"
        for j, (_, _, fmt) in enumerate(calc_cols):
            c = ws.cell(r, nd + 1 + j)
            c.fill, c.number_format, c.font = CALC_FILL, fmt, f_n
    last = R0 + len(ids) - 1
    ws.cell(last + 2, 1, "Total").font = f_b
    for h, L in letters.items():
        fmt_is_cur = (any(h == d and s and s.endswith("_usd") for d, s in data_cols) or
                      any(h == c and fm == CUR for c, _, fm in calc_cols))
        if fmt_is_cur:
            c = ws.cell(last + 2, ws[f"{L}1"].column, f"=SUM({L}{R0}:{L}{last})")
            c.font, c.number_format = f_b, CUR
    ws.freeze_panes = ws.cell(R0, 2)
    return letters, last


def key(h):
    return h.replace(" ", "_").replace("'", "").replace("(", "").replace(")", "").replace("÷", "per").replace(":", "").replace(",", "")


# --- Roster gets region and team
ro.insert(1, "team_id", ro.fy2027_territory_id.map(team_of))
ro.insert(2, "region", ro.fy2027_territory_id.map(dict(zip(ts.territory_id, ts.region)) | dict(zip(ovl.territory_id, ovl.region))))
del q["Roster"]
rws = df_sheet(q, "Roster", ro, {"ramp_factor": PCT, "start_date": "yyyy-mm-dd"})
q.move_sheet("Roster", offset=-(len(q.sheetnames) - 1 - q.sheetnames.index("Overlay_Import") - 1))
rws.cell(len(ro) + 3, 1, "Ramp factor = rep's FY2027 capacity before the attrition haircut ÷ a full year of ramped "
                         "productivity. 100% = ramped all year; new hires and backfills are lower.").font = f_note
rws.cell(len(ro) + 4, 1, "New-hire territory assignments: earliest start dates took the first new territories. Update "
                         "Capacity_Plan column C to match if you want the two files aligned.").font = f_note
rcols = {c: get_column_letter(i + 1) for i, c in enumerate(ro.columns)}
tcols = {c: get_column_letter(i + 1) for i, c in enumerate(ts.columns)}
ocols = {c: get_column_letter(i + 1) for i, c in enumerate(ovl.columns)}
HR, IR, R0 = 5, 6, 7

# --- Quota_Overlay (the overlay team leader is Dani Pedrosa; reps add up to 110% of his number)
qo = q.create_sheet("Quota_Overlay")
o_data = [("territory_id", None), ("team_id", "H:team"), ("region", "region"), ("rep_id", "R:rep_id"),
          ("rep_name", "R:rep_name"), ("rep start", "R:start_date"), ("core territories covered", "core_territories_covered"),
          ("AI Race Coach potential", "potential_ai_race_coach_usd"),
          ("FY2026 won (rebased)", "fy2026_ai_race_coach_won_rebased_usd"),
          ("open pipeline credited FY2027", "open_pipeline_ai_race_coach_usd"),
          ("FY2027 capacity (rep)", "R:fy2027_capacity_gross_usd"), ("ramp factor", "R:ramp_factor")]
o_calc = [("potential share", "{AI_Race_Coach_potential} ÷ total of {AI_Race_Coach_potential}", PCT),
          ("ramp-weighted share", "{potential_share} × {ramp_factor}, re-normalised to 100%", PCT),
          ("overlay quota", "overlay team leader's number (Leadership, L-TL-OVERLAY) × over-assignment (Plan B13) × "
                            "{ramp-weighted_share}", CUR),
          ("quota ÷ capacity", "{overlay_quota} ÷ {FY2027_capacity_rep}", '0.00"x"')]
o_calc = [(h, how.replace("{ramp-weighted_share}", "{ramp-weighted_share}"), f) for h, how, f in o_calc]
olet, olast = build_tab(qo, "FY2027 AI Race Coach overlay quotas",
                        "Build after Leadership section 1 and before the AI Race Coach credit column on Quota_Core.",
                        o_data, o_calc, list(ovl.territory_id), "Overlay_Import", ocols, len(ovl), len(ro))

# --- Quota_Core
qc = q.create_sheet("Quota_Core")
data_cols = [
    ("territory_id", None), ("team_id", "H:team"), ("region", "region"), ("segment", "segment"),
    ("carved_from", "carved_from"), ("rep_id", "R:rep_id"), ("rep_name", "R:rep_name"), ("rep start", "R:start_date"),
    ("accounts", "accounts"), ("potential Rider Seats", "potential_rider_seats_usd"),
    ("potential Telemetry Cloud", "potential_telemetry_cloud_usd"), ("potential core", "potential_core_usd"),
    ("FY2026 quota rebased", "fy2026_quota_rebased_usd"), ("FY2026 actual rebased", "fy2026_actual_rebased_usd"),
    ("open pipeline credited FY2027", "open_pipeline_credited_usd"),
    ("FY2027 capacity rep", "R:fy2027_capacity_gross_usd"), ("ramp factor", "R:ramp_factor"),
    ("overlay territory", "overlay_territory_id"),
    ("share of overlay coach potential", "share_of_overlay_coach_potential"),
]
calc_cols = [
    ("potential share of team", "{potential_core} ÷ team total of {potential_core} (SUMIFS on {team_id})", PCT),
    ("actuals share of team", "{FY2026_actual_rebased} ÷ team total of {FY2026_actual_rebased}", PCT),
    ("blended share", "Plan w (B15) × {potential_share_of_team} + (1 − w) × {actuals_share_of_team}", PCT),
    ("ramp-weighted share", "{blended_share} × {ramp_factor}, re-normalised to 100% within the team", PCT),
    ("raw quota", "team leader's core number (Leadership section 2, matched on {team_id}) × over-assignment "
                  "(Plan B13) × {ramp-weighted_share}", CUR),
    ("guardrail cap", "{FY2026_quota_rebased} × (1 + Plan B16). If {FY2026_quota_rebased} is 0 (new territory, no "
                      "FY2026 bookings) there is no cap: use {raw_quota}", CUR),
    ("capped quota", "lower of {raw_quota} and {guardrail_cap}", CUR),
    ("excess redistributed", "team total of ({raw_quota} − {capped_quota}), spread by {ramp-weighted_share} across the "
                             "team's uncapped, fully ramped reps ({ramp_factor} = 100%); ramping reps take none. If there "
                             "isn't room, Checks shows the team short of 110%", CUR),
    ("final core quota", "{capped_quota} + {excess_redistributed}. Team total = team leader's number × 110%", CUR),
    ("AI Race Coach credit", "overlay quota for {overlay_territory} (Quota_Overlay) × {share_of_overlay_coach_potential} "
                             "× core credit (Plan B14)", CUR),
    ("total quota", "{final_core_quota} + {AI_Race_Coach_credit}", CUR),
    ("Rider Seats portion", "{final_core_quota} × {potential_Rider_Seats} ÷ {potential_core}", CUR),
    ("Telemetry Cloud portion", "{final_core_quota} × {potential_Telemetry_Cloud} ÷ {potential_core}", CUR),
    ("quota ÷ capacity", "{final_core_quota} ÷ {FY2027_capacity_rep}. Above ~1.2x is a warning sign", '0.00"x"'),
]
qlet, last = build_tab(qc, "FY2027 core quotas — one row per territory, allocated inside each team",
                       "Blue-grey = linked data (don't edit). Cream = build left to right; row 6 says what each does.",
                       data_cols, calc_cols, core_ids, "Territory_Import", tcols, len(ts), len(ro))
widths = {1: 14, 2: 15, 3: 8, 4: 11, 5: 13, 6: 10, 7: 22, 8: 11}
for i in range(1, len(data_cols) + len(calc_cols) + 1):
    qc.column_dimensions[get_column_letter(i)].width = widths.get(i, 15)
for i in range(1, 17):
    qo.column_dimensions[get_column_letter(i)].width = 15
qo.column_dimensions["E"].width = 24

# --- Leadership
ld = q.create_sheet("Leadership")
ld["A1"] = "FY2027 leadership cascade: company → geo → AVP → team leader"
ld["A1"].font = f_t
ld["A2"] = ("Leaders carry 100% of their number. Over-assignment (Plan B13) is applied only between team leaders and "
            "their reps. Build section 1 first, then Quota_Overlay and Quota_Core, then section 2.")
ld["A2"].font = f_note
ld["A4"] = "Section 1 — split each segment's target across geos by capacity share"
ld["A4"].font = f_b
s1_head = ["geo-segment", "region", "segment", "rep capacity in geo-segment", "segment capacity (all geos)",
           "segment target (Plan)", "capacity share", "geo-segment target"]
for i, h in enumerate(s1_head, 1):
    c = ld.cell(5, i, h)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    if i <= 6:
        c.font, c.fill = f_h, H_FILL
    else:
        c.font, c.fill = Font(name=F, bold=True, size=10), CALC_FILL
ld.cell(6, 7, "G: D ÷ E").font = f_note
ld.cell(6, 8, "H: F × G. Check: the three geos add up to the segment target").font = f_note
qP, qR, qS = qlet["FY2027 capacity rep"], qlet["region"], qlet["segment"]
geo_rows = {}
r = 7
for region in ["AMER", "EMEA", "APAC"]:
    for seg in ["Enterprise", "Commercial"]:
        geo_rows[(region, seg)] = r
        ld.cell(r, 1, f"{region} {seg}").font = f_n
        ld.cell(r, 2, region).font = f_n
        ld.cell(r, 3, seg).font = f_n
        fm = [f'=SUMIFS(Quota_Core!${qP}${R0}:${qP}${last},Quota_Core!${qR}${R0}:${qR}${last},B{r},'
              f'Quota_Core!${qS}${R0}:${qS}${last},C{r})',
              f'=SUMIFS(Quota_Core!${qP}${R0}:${qP}${last},Quota_Core!${qS}${R0}:${qS}${last},C{r})',
              f'=IF(C{r}="Enterprise",Plan!$B$8,Plan!$B$9)']
        for j, f in enumerate(fm, 4):
            c = ld.cell(r, j, f)
            c.font, c.fill, c.number_format = f_green, DATA_FILL, CUR
        ld.cell(r, 7).fill, ld.cell(r, 7).number_format = CALC_FILL, PCT
        ld.cell(r, 8).fill, ld.cell(r, 8).number_format = CALC_FILL, CUR
        r += 1
ld.cell(r, 1, "Total").font = f_b
for col in (4, 8):
    c = ld.cell(r, col, f"=SUM({get_column_letter(col)}7:{get_column_letter(col)}{r - 1})")
    c.font, c.number_format = f_b, CUR
S2 = r + 3
ld.cell(S2 - 1, 1, "Section 2 — every leader's number, and the roll-up check").font = f_b
s2_head = ["leader_id", "leader_name", "role", "region", "segment", "team_id", "reports_to_id",
           "team capacity (team leaders)", "core number", "AI Race Coach credit", "total number",
           "rep quota assigned under (team leaders)", "assigned ÷ core number"]
for i, h in enumerate(s2_head, 1):
    c = ld.cell(S2, i, h)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    if i <= 8:
        c.font, c.fill = f_h, H_FILL
    else:
        c.font, c.fill = Font(name=F, bold=True, size=10), CALC_FILL
qT, qAA, qAB = qlet["team_id"], qlet["final core quota"], qlet["AI Race Coach credit"]
guides = {
    9: "I: CRO = Plan B4. Geo leader = sum of their geo-segment targets (section 1). AVP = their geo-segment target. "
       "Team leader = geo-segment target × H ÷ section-1 rep capacity (a geo-segment's only team gets all of it). "
       "Overlay team leader = Plan B10",
    10: "J: team leader = sum of Quota_Core AI Race Coach credit for their team. AVPs, geo leaders and CRO = sum of the "
        "leaders reporting to them. Overlay team leader: 0",
    11: "K: I + J",
    12: "L: team leaders = sum of their reps' final core quota (overlay team leader: overlay quotas)",
    13: "M: L ÷ I. Should be 110% for every team leader",
}
for col, t in guides.items():
    g = ld.cell(S2 + 1, col, t)
    g.font, g.alignment = f_note, Alignment(wrap_text=True, vertical="top")
ld.row_dimensions[S2 + 1].height = 120
LR0 = S2 + 2
for k, row in enumerate(lead.itertuples(index=False)):
    rr = LR0 + k
    for j, v in enumerate(row, 1):
        ld.cell(rr, j, v).font = f_n
    if row.role in ("Team leader", "Overlay team leader"):
        src = (f'=SUMIFS(Quota_Core!${qP}${R0}:${qP}${last},Quota_Core!${qT}${R0}:${qT}${last},F{rr})'
               if row.role == "Team leader" else
               f'=SUM(Quota_Overlay!${olet["FY2027 capacity (rep)"]}${R0}:${olet["FY2027 capacity (rep)"]}${olast})')
        c = ld.cell(rr, 8, src)
        c.font, c.fill, c.number_format = f_green, DATA_FILL, CUR
    for col in range(9, 14):
        c = ld.cell(rr, col)
        c.fill, c.number_format = CALC_FILL, (PCT if col == 13 else CUR)
LLAST = LR0 + len(lead) - 1
for col, w in zip("ABCDEFGHIJKLM", [18, 20, 20, 9, 13, 15, 16, 16, 16, 16, 16, 18, 14]):
    ld.column_dimensions[col].width = w

# --- Checks
ck = q.create_sheet("Checks")
ck["A1"] = "Checks — every row should read OK before quotas are published"
ck["A1"].font = f_t
header(ck, 3, ["Check", "Expected", "Actual", "Status"])
rng = lambda L: f"Quota_Core!${L}${R0}:${L}${last}"
lr = lambda L: f"Leadership!${L}${LR0}:${L}${LLAST}"
X_ = qlet["guardrail cap"]
AF = qlet["quota ÷ capacity"]
checks = [
    ("Geo-segment targets add up to the core target (section 1)", "=Plan!B4", "=Leadership!H13", "money"),
    ("Geo leaders' core numbers add up to the core target", "=Plan!B4",
     f'=SUMIFS({lr("I")},{lr("C")},"Geo leader")', "money"),
    ("Team leaders' core numbers add up to the core target", "=Plan!B4",
     f'=SUMIFS({lr("I")},{lr("C")},"Team leader")', "money"),
    ("Core rep quotas = core target × over-assignment", "=Plan!B4*Plan!B13", f"=SUM({rng(qAA)})", "money"),
    ("Overlay rep quotas = overlay target × over-assignment", "=Plan!B10*Plan!B13",
     f'=SUM(Quota_Overlay!${olet["overlay quota"]}${R0}:${olet["overlay quota"]}${olast})', "money"),
    ("AI Race Coach credit on core = 50% of overlay quotas", "=C8*Plan!B14", f"=SUM({rng(qAB)})", "money"),
    ("Team leaders whose reps don't add up to 110%", 0,
     f'=SUMPRODUCT(({lr("C")}="Team leader")*(ABS({lr("M")}-Plan!B13)>0.001)*({lr("I")}<>0))', "count"),
    ("Territories above the guardrail cap", 0,
     f"=SUMPRODUCT(({rng(qAA)}>{rng(X_)}+1)*({rng(qAA)}<>\"\"))", "count"),
    ("Highest quota ÷ capacity (core)", "≤ 1.20x", f"=MAX({rng(AF)})", "ratio"),
    ("Lowest quota ÷ capacity (core, ramped reps)", "≥ 0.80x",
     f'=MINIFS_PLACEHOLDER', "ratio"),
]
qQ = qlet["ramp factor"]
checks[-1] = (checks[-1][0], checks[-1][1],
              f'=_xlfn.MINIFS({rng(AF)},{rng(qQ)},1,{rng(AF)},">0")', "ratio_min")
for k, (label, exp, act, kind) in enumerate(checks):
    r = 4 + k
    ck.cell(r, 1, label).font = f_n
    e, a = ck.cell(r, 2, exp), ck.cell(r, 3, act)
    for c in (e, a):
        c.font = f_n
        c.number_format = CUR if kind == "money" else ('0.00"x"' if kind.startswith("ratio") else "0")
    if kind == "money":
        st = f'=IF(C{r}=0,"Not built yet",IF(ABS(C{r}-B{r})<=1000,"OK","Off by "&TEXT(C{r}-B{r},"$#,##0")))'
    elif kind == "count":
        st = f'=IF(C{r}=0,"OK",C{r}&" to review")'
    elif kind == "ratio":
        st = f'=IF(C{r}=0,"Not built yet",IF(C{r}<=1.2,"OK","Review"))'
    else:
        st = f'=IF(OR(C{r}=0,C{r}=99),"Not built yet",IF(C{r}>=0.8,"OK","Review"))'
    ck.cell(r, 4, st).font = f_b
ck.cell(4 + len(checks) + 1, 1, "Quota ÷ capacity bands are a starting rule of thumb for a balanced plan, not a "
                                "standard; tune them to MotoFreeP's attainment history.").font = f_note
for col, w in zip("ABCD", [58, 18, 18, 22]):
    ck.column_dimensions[col].width = w

order = ["README", "Plan", "Hierarchy", "Leadership", "Quota_Overlay", "Quota_Core", "Checks",
         "Territory_Import", "Overlay_Import", "Roster"]
q._sheets = [q[n] for n in order]
q.save(OUT / "MotoFreeP_FY2027_Quota_Model.xlsx")
print("built", OUT)
