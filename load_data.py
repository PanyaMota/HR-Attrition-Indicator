"""
HR Attrition Indicator — PostgreSQL Data Loader
Loads all 9 generated CSVs into the hr_attrition database
in correct foreign-key dependency order.

Usage:
    python3 load_data.py
"""

import pandas as pd
from sqlalchemy import create_engine, text
import os

# -----------------------------------------------------------------------
# Connection — update password to match your PostgreSQL install
# -----------------------------------------------------------------------
DB_URL = "postgresql://postgres:postgresql25@localhost:5432/hr_attrition"
DATA_DIR = "data"

engine = create_engine(DB_URL)

DATE_COLS = {
    "fulldate", "dob", "hiredate", "effectivedate", "enddate",
    "surveydate", "exitdate"
}


def load_table(filename, table_name):
    filepath = os.path.join(DATA_DIR, filename)
    print(f"Loading {filename} -> {table_name}...", end=" ")
    df = pd.read_csv(filepath)

    for col in df.columns:
        col_lower = col.lower()
        if col_lower in DATE_COLS:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        elif df[col].dtype == object:
            try:
                sample = df[col].dropna()
                if len(sample) == 0:
                    continue
                lower_vals = set(str(v).lower() for v in sample.unique())
                if lower_vals.issubset({"true", "false"}):
                    df[col] = df[col].map(
                        {"True": True, "False": False,
                         "true": True, "false": False}
                    )
            except Exception:
                pass

    df.to_sql(table_name, engine, if_exists="append", index=False)
    print(f"{len(df):,} rows loaded.")
    return len(df)


def clear_tables():
    print("Clearing existing data...")
    with engine.connect() as conn:
        conn.execute(text('TRUNCATE TABLE "Fact_Employment" CASCADE'))
        conn.execute(text('TRUNCATE TABLE "Dim_ExitInterview" CASCADE'))
        conn.execute(text('TRUNCATE TABLE "Dim_EngagementSurvey" CASCADE'))
        conn.execute(text('TRUNCATE TABLE "Dim_PromotionHistory" CASCADE'))
        conn.execute(text('TRUNCATE TABLE "Dim_Compensation" CASCADE'))
        conn.execute(text('TRUNCATE TABLE "Dim_Employee" CASCADE'))
        conn.execute(text('TRUNCATE TABLE "Dim_Store" CASCADE'))
        conn.execute(text('TRUNCATE TABLE "Dim_Department" CASCADE'))
        conn.execute(text('TRUNCATE TABLE "Dim_Date" CASCADE'))
        conn.commit()
    print("All tables cleared.")


def main():
    print("=" * 55)
    print("HR Attrition Indicator -- Data Loader")
    print("=" * 55)

    clear_tables()

    total_rows = 0
    total_rows += load_table("dim_date.csv",       "Dim_Date")
    total_rows += load_table("dim_department.csv", "Dim_Department")
    total_rows += load_table("dim_store.csv",      "Dim_Store")

    # Dim_Employee has a self-referencing FK (ManagerID -> EmployeeID).
    # Disable the constraint during load so employees can reference
    # managers that haven't been inserted yet, then re-enable after.
    print("Disabling ManagerID FK constraint for bulk load...")
    with engine.connect() as conn:
        conn.execute(text(
            'ALTER TABLE "Dim_Employee" '
            'DISABLE TRIGGER ALL'
        ))
        conn.commit()

    total_rows += load_table("dim_employee.csv", "Dim_Employee")

    print("Re-enabling ManagerID FK constraint...")
    with engine.connect() as conn:
        conn.execute(text(
            'ALTER TABLE "Dim_Employee" '
            'ENABLE TRIGGER ALL'
        ))
        conn.commit()

    total_rows += load_table("dim_compensation.csv",     "Dim_Compensation")
    total_rows += load_table("dim_promotionhistory.csv", "Dim_PromotionHistory")
    total_rows += load_table("dim_engagementsurvey.csv", "Dim_EngagementSurvey")
    total_rows += load_table("dim_exitinterview.csv",    "Dim_ExitInterview")
    total_rows += load_table("fact_employment.csv",      "Fact_Employment")

    print("=" * 55)
    print(f"Done. {total_rows:,} total rows loaded across 9 tables.")
    print("=" * 55)


if __name__ == "__main__":
    main()
