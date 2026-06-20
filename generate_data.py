"""
HR Attrition Indicator - Synthetic Data Generator
Generates a realistic retail/customer-service HR dataset implementing the
star schema: Dim_Employee, Dim_Department, Dim_Store, Dim_Compensation,
Dim_PromotionHistory, Dim_EngagementSurvey, Dim_ExitInterview, Dim_Date,
and the monthly snapshot Fact_Employment table.

Key design principle: attrition isn't random. It's driven by a weighted
combination of realistic HR factors (pay vs. band, engagement trend,
overtime, manager quality, tenure stage) so the downstream ML model has
real signal to learn, and the Power BI story is coherent.

Usage:
    python generate_data.py --employees 5000 --years 3 --outdir data
"""

import argparse
import random
from datetime import date, timedelta

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)
np.random.seed(42)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

DEPARTMENTS = [
    ("Sales Floor", "Frontline"),
    ("Cashier", "Frontline"),
    ("Stockroom", "Frontline"),
    ("Customer Service", "Frontline"),
    ("Loss Prevention", "Frontline"),
    ("Merchandising", "Mid"),
    ("Store Management", "Mid"),
    ("Regional Operations", "Corporate"),
    ("Corporate HR", "Corporate"),
    ("Marketing", "Corporate"),
]

REGIONS = ["Northeast", "Southeast", "Midwest", "West", "Southwest"]
STORE_FORMATS = ["Mall", "Flagship", "Outlet", "Strip Mall"]
JOB_LEVELS = ["Frontline", "Team Lead", "Store Manager", "Regional", "Corporate"]
EXIT_REASONS = [
    "Compensation", "Career Growth", "Manager Relationship", "Work-Life Balance",
    "Relocation", "Better Opportunity", "Personal Reasons", "Involuntary - Performance",
    "Involuntary - Restructuring",
]

PAY_BANDS = {
    "Frontline": (15.0, 19.0),       # hourly
    "Team Lead": (19.0, 24.0),       # hourly
    "Store Manager": (55000, 75000), # salaried annual
    "Regional": (80000, 110000),
    "Corporate": (60000, 95000),
}
HOURLY_LEVELS = {"Frontline", "Team Lead"}


def make_stores(n_stores=120):
    rows = []
    for i in range(1, n_stores + 1):
        rows.append({
            "StoreID": i,
            "StoreName": f"{fake.city()} {random.choice(['Mall','Center','Plaza','Square'])}",
            "Region": random.choice(REGIONS),
            "StoreFormat": random.choice(STORE_FORMATS),
            "StoreSizeCategory": random.choice(["Small", "Medium", "Large"]),
        })
    return pd.DataFrame(rows)


def make_departments():
    rows = [{"DepartmentID": i + 1, "DepartmentName": d, "DeptTier": t}
            for i, (d, t) in enumerate(DEPARTMENTS)]
    return pd.DataFrame(rows)


def make_date_dim(start_date, n_months):
    rows = []
    d = date(start_date.year, start_date.month, 1)
    for i in range(n_months):
        # simple fiscal period approximation (retail 4-4-5 not modeled exactly,
        # but FiscalQuarter gives you a realistic axis to slice on in Power BI)
        rows.append({
            "DateID": i + 1,
            "FullDate": d,
            "Year": d.year,
            "Month": d.month,
            "MonthName": d.strftime("%b"),
            "FiscalQuarter": f"Q{((d.month - 1) // 3) + 1} {d.year}",
        })
        # advance one month
        if d.month == 12:
            d = date(d.year + 1, 1, 1)
        else:
            d = date(d.year, d.month + 1, 1)
    return pd.DataFrame(rows)


def pick_pay(job_level, rng_factor=0.0):
    lo, hi = PAY_BANDS[job_level]
    base = random.uniform(lo, hi)
    return round(base * (1 + rng_factor), 2)


def generate(n_employees, n_years, outdir):
    n_months = n_years * 12
    start_date = date.today().replace(day=1) - timedelta(days=n_months * 30)

    dim_store = make_stores()
    dim_department = make_departments()
    dim_date = make_date_dim(start_date, n_months)

    # ---- Employees -------------------------------------------------------
    employees = []
    managers_pool = []  # employee IDs eligible to be managers (Team Lead+)

    for emp_id in range(1, n_employees + 1):
        hire_offset_days = random.randint(0, n_months * 30 - 30)
        hire_date = start_date + timedelta(days=hire_offset_days)

        # job level distribution skewed toward frontline (realistic retail org)
        job_level = random.choices(
            JOB_LEVELS, weights=[70, 15, 8, 4, 3], k=1
        )[0]

        emp = {
            "EmployeeID": emp_id,
            "FullName": fake.name(),
            "Gender": random.choice(["Male", "Female", "Nonbinary"]),
            "DOB": fake.date_of_birth(minimum_age=18, maximum_age=65),
            "HireDate": hire_date,
            "CommuteDistanceKM": round(np.random.exponential(8) + 1, 1),
            "JobLevel": job_level,
            "EmploymentType": "Hourly" if job_level in HOURLY_LEVELS else "Salaried",
            "DepartmentID": random.choice(dim_department["DepartmentID"].tolist()),
            "StoreID": random.choice(dim_store["StoreID"].tolist()),
            "ManagerID": None,  # assigned in second pass
        }
        employees.append(emp)
        if job_level in ("Team Lead", "Store Manager", "Regional"):
            managers_pool.append(emp_id)

    dim_employee = pd.DataFrame(employees)

    # second pass: assign managers (self-referencing FK), avoid self-management
    manager_ids = []
    for _, row in dim_employee.iterrows():
        candidates = [m for m in managers_pool if m != row["EmployeeID"]]
        manager_ids.append(random.choice(candidates) if candidates else None)
    dim_employee["ManagerID"] = manager_ids

    # give each manager a "quality" score (latent, drives team attrition) --
    # this is what lets you compute "manager-driven attrition clusters" later
    manager_quality = {m: round(np.random.beta(5, 2), 2) for m in managers_pool}
    dim_employee["_ManagerQuality"] = dim_employee["ManagerID"].map(
        lambda m: manager_quality.get(m, 0.7)
    )

    # ---- Compensation history (SCD2) -------------------------------------
    comp_rows = []
    comp_id = 1
    emp_current_pay = {}
    for _, row in dim_employee.iterrows():
        eff_date = row["HireDate"]
        base_pay = pick_pay(row["JobLevel"], rng_factor=random.uniform(-0.08, 0.08))
        n_raises = random.choices([0, 1, 2, 3], weights=[35, 35, 20, 10])[0]
        current_pay = base_pay
        events = [(eff_date, base_pay)]
        for _ in range(n_raises):
            gap_days = random.randint(180, 540)
            eff_date = eff_date + timedelta(days=gap_days)
            if eff_date >= date.today():
                break
            current_pay = round(current_pay * random.uniform(1.03, 1.12), 2)
            events.append((eff_date, current_pay))

        for i, (eff, pay) in enumerate(events):
            end = events[i + 1][0] - timedelta(days=1) if i + 1 < len(events) else None
            comp_rows.append({
                "CompensationID": comp_id,
                "EmployeeID": row["EmployeeID"],
                "EffectiveDate": eff,
                "EndDate": end,
                "PayRate": pay,
                "PayBandMin": PAY_BANDS[row["JobLevel"]][0],
                "PayBandMax": PAY_BANDS[row["JobLevel"]][1],
                "IsCurrent": end is None,
            })
            comp_id += 1
        emp_current_pay[row["EmployeeID"]] = events[-1][1]
        dim_employee.loc[dim_employee.EmployeeID == row["EmployeeID"], "_LastRaiseDate"] = events[-1][0]

    dim_compensation = pd.DataFrame(comp_rows)

    # ---- Promotion history (SCD2) -----------------------------------------
    promo_rows = []
    promo_id = 1
    for _, row in dim_employee.iterrows():
        promo_rows.append({
            "PromotionID": promo_id,
            "EmployeeID": row["EmployeeID"],
            "EffectiveDate": row["HireDate"],
            "EndDate": None,
            "JobLevel": row["JobLevel"],
            "IsCurrent": True,
        })
        promo_id += 1
    dim_promotion = pd.DataFrame(promo_rows)

    # ---- Engagement surveys (quarterly per employee, with a trend) -------
    survey_rows = []
    survey_id = 1
    emp_engagement_trend = {}
    for _, row in dim_employee.iterrows():
        start_score = np.random.normal(3.6, 0.7)
        drift = np.random.normal(0, 0.15)  # negative = declining engagement
        emp_engagement_trend[row["EmployeeID"]] = (start_score, drift)
        survey_date = row["HireDate"] + timedelta(days=90)
        q = 0
        while survey_date < date.today():
            score = np.clip(start_score + drift * q + np.random.normal(0, 0.3), 1, 5)
            survey_rows.append({
                "SurveyID": survey_id,
                "EmployeeID": row["EmployeeID"],
                "SurveyDate": survey_date,
                "EngagementScore": round(score, 2),
                "ManagerRelationshipScore": round(
                    np.clip(row["_ManagerQuality"] * 5 + np.random.normal(0, 0.4), 1, 5), 2),
                "WorkloadScore": round(np.clip(np.random.normal(3.2, 0.8), 1, 5), 2),
                "CareerGrowthScore": round(np.clip(np.random.normal(3.0, 0.9), 1, 5), 2),
            })
            survey_id += 1
            survey_date += timedelta(days=90)
            q += 1
    dim_survey = pd.DataFrame(survey_rows)

    # ---- Attrition risk model (drives Fact_Employment + Dim_ExitInterview) ----
    # weighted logistic-ish score combining realistic drivers
    def monthly_attrition_prob(row, tenure_months, overtime_hrs, engagement_score):
        score = -4.2  # base log-odds, low monthly hazard
        # tenure curve: spikes around month 12 and months 36-48
        if 10 <= tenure_months <= 14:
            score += 0.9
        if 34 <= tenure_months <= 50:
            score += 0.6
        if tenure_months < 3:
            score += 0.5  # early flight risk
        # pay vs band position
        lo, hi = PAY_BANDS[row["JobLevel"]]
        pay = emp_current_pay[row["EmployeeID"]]
        band_position = (pay - lo) / (hi - lo) if hi > lo else 0.5
        if band_position < 0.25:
            score += 0.8
        # engagement
        if engagement_score < 2.5:
            score += 1.1
        elif engagement_score < 3.2:
            score += 0.4
        # manager quality
        if row["_ManagerQuality"] < 0.4:
            score += 0.7
        # overtime burnout
        if overtime_hrs > 15:
            score += 0.5
        # commute
        if row["CommuteDistanceKM"] > 25:
            score += 0.3
        prob = 1 / (1 + np.exp(-score))
        return np.clip(prob, 0.002, 0.35)

    # ---- Fact_Employment monthly snapshots + exit events -------------------
    fact_rows = []
    exit_rows = []
    exit_id = 1
    fact_sk = 1

    date_lookup = dict(zip(dim_date["FullDate"], dim_date["DateID"]))

    for _, row in dim_employee.iterrows():
        active = True
        hire_d = row["HireDate"]
        for _, drow in dim_date.iterrows():
            snap_date = drow["FullDate"]
            if snap_date < hire_d or not active:
                continue
            tenure_months = (snap_date.year - hire_d.year) * 12 + (snap_date.month - hire_d.month)

            # latest engagement score as of this snapshot
            emp_surveys = dim_survey[(dim_survey.EmployeeID == row["EmployeeID"]) &
                                      (dim_survey.SurveyDate <= snap_date)]
            engagement = emp_surveys.EngagementScore.iloc[-1] if len(emp_surveys) else 3.5

            overtime = round(max(0, np.random.normal(8, 6)), 1)
            pay = emp_current_pay[row["EmployeeID"]]
            is_hourly = row["EmploymentType"] == "Hourly"

            perf_rating = int(np.clip(round(np.random.normal(3.2, 0.8)), 1, 5))

            attr_prob = monthly_attrition_prob(row, tenure_months, overtime, engagement)
            will_exit = random.random() < attr_prob

            fact_rows.append({
                "EmploymentSK": fact_sk,
                "EmployeeID": row["EmployeeID"],
                "SnapshotDateID": date_lookup[snap_date],
                "DepartmentID": row["DepartmentID"],
                "StoreID": row["StoreID"],
                "ManagerID": row["ManagerID"],
                "MonthlySalary": None if is_hourly else round(pay / 12, 2),
                "HourlyRate": pay if is_hourly else None,
                "OvertimeHours": overtime,
                "PTOHoursUsed": round(max(0, np.random.normal(6, 4)), 1),
                "PTOHoursAvailable": 80,
                "PerformanceRating": perf_rating,
                "EngagementScore": engagement,
                "TenureMonths": tenure_months,
                "IsActive": True,
                "AttritionFlag": will_exit,
                "RegrettedAttritionFlag": will_exit and perf_rating >= 4,
            })
            fact_sk += 1

            if will_exit:
                active = False
                reason = random.choice(EXIT_REASONS) if perf_rating >= 3 else random.choices(
                    EXIT_REASONS, weights=[10,10,10,10,5,8,5,30,12])[0]
                regretted = perf_rating >= 4 and "Involuntary" not in reason
                exit_rows.append({
                    "ExitID": exit_id,
                    "EmployeeID": row["EmployeeID"],
                    "ExitDate": snap_date,
                    "ExitReasonCategory": reason,
                    "ExitInterviewText": fake.paragraph(nb_sentences=3),
                    "WouldRehire": "Y" if regretted else random.choice(["Y", "N"]),
                    "RegrettedExit": regretted,
                })
                exit_id += 1

    fact_employment = pd.DataFrame(fact_rows)
    dim_exit = pd.DataFrame(exit_rows)

    dim_employee = dim_employee.drop(columns=["_ManagerQuality", "_LastRaiseDate"], errors="ignore")

    # ---- write outputs -----------------------------------------------------
    import os
    os.makedirs(outdir, exist_ok=True)
    dim_employee.to_csv(f"{outdir}/dim_employee.csv", index=False)
    dim_department.to_csv(f"{outdir}/dim_department.csv", index=False)
    dim_store.to_csv(f"{outdir}/dim_store.csv", index=False)
    dim_date.to_csv(f"{outdir}/dim_date.csv", index=False)
    dim_compensation.to_csv(f"{outdir}/dim_compensation.csv", index=False)
    dim_promotion.to_csv(f"{outdir}/dim_promotionhistory.csv", index=False)
    dim_survey.to_csv(f"{outdir}/dim_engagementsurvey.csv", index=False)
    dim_exit.to_csv(f"{outdir}/dim_exitinterview.csv", index=False)
    fact_employment.to_csv(f"{outdir}/fact_employment.csv", index=False)

    print(f"Generated {len(dim_employee)} employees, {len(fact_employment)} fact rows, "
          f"{len(dim_exit)} exits ({len(dim_exit)/len(dim_employee):.1%} of headcount).")
    print(f"Regretted exits: {dim_exit.RegrettedExit.sum()} "
          f"({dim_exit.RegrettedExit.mean():.1%} of exits)")
    print(f"Files written to ./{outdir}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--employees", type=int, default=5000)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--outdir", type=str, default="data")
    args = parser.parse_args()
    generate(args.employees, args.years, args.outdir)
