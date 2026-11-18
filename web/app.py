"""
HR Attrition Indicator - Flask AI Assistant (fixed)
File: web/app.py

One route, one page, four focused AI actions.

Setup (each new Git Bash session):
    export GROQ_API_KEY="your-key"
    export DB_PASSWORD="your-postgres-password"

Run:
    cd web && python3 app.py
    Open: http://localhost:5000/report?employee_id=1&action=explain
"""

import os
import sys
import joblib
import pandas as pd
from flask import Flask, render_template, request
from sqlalchemy import create_engine, text
from groq import Groq

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from genai.prompts import (
    prompt_explain_prediction,
    prompt_retention_plan,
    prompt_risk_profile_summary,
    prompt_exit_interview_summary,
)

app = Flask(__name__)

DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
engine = create_engine(
    f"postgresql://postgres:{DB_PASSWORD}@localhost:5432/hr_attrition"
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model = joblib.load(os.path.join(BASE_DIR, 'data', 'model.pkl'))
FEATURES = joblib.load(os.path.join(BASE_DIR, 'data', 'model_features.pkl'))

groq_client = Groq()  # reads GROQ_API_KEY from environment
GROQ_MODEL = "llama-3.1-8b-instant"

VALID_ACTIONS = {"explain", "retention", "summary", "exit"}

# LabelEncoder sorts classes alphabetically, so these match the notebook.
ENCODERS = {
    "JobLevel": {"Corporate": 0, "Frontline": 1, "Regional": 2,
                 "Store Manager": 3, "Team Lead": 4},
    "EmploymentType": {"Hourly": 0, "Salaried": 1},
    "DeptTier": {"Corporate": 0, "Frontline": 1, "Mid": 2},
    "Region": {"Midwest": 0, "Northeast": 1, "Southeast": 2,
               "Southwest": 3, "West": 4},
    "StoreFormat": {"Flagship": 0, "Mall": 1, "Outlet": 2, "Strip Mall": 3},
}


def get_employee_data(employee_id):
    """Latest monthly snapshot for one employee, with the fields the report needs."""
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT
                f."EmployeeID", e."FullName", e."JobLevel", e."EmploymentType",
                e."CommuteDistanceKM", dept."DepartmentName", dept."DeptTier",
                s."StoreName", s."StoreFormat", s."Region",
                f."TenureMonths", f."PerformanceRating", f."EngagementScore",
                f."OvertimeHours", f."PTOHoursUsed", f."PTOHoursAvailable",
                ROUND(
                    COALESCE(f."HourlyRate" - c."PayBandMin",
                             f."MonthlySalary" * 12 - c."PayBandMin")::decimal
                    / NULLIF(c."PayBandMax" - c."PayBandMin", 0), 2
                ) AS pay_band_position,
                (CURRENT_DATE - c."EffectiveDate"::date) AS days_since_last_raise
            FROM "Fact_Employment" f
            JOIN "Dim_Employee"   e    ON f."EmployeeID"   = e."EmployeeID"
            JOIN "Dim_Department" dept ON f."DepartmentID" = dept."DepartmentID"
            JOIN "Dim_Store"      s    ON f."StoreID"      = s."StoreID"
            JOIN "Dim_Compensation" c  ON e."EmployeeID"   = c."EmployeeID"
                                      AND c."IsCurrent"    = TRUE
            WHERE f."EmployeeID" = :eid
            ORDER BY f."SnapshotDateID" DESC
            LIMIT 1
        """), {"eid": employee_id}).mappings().fetchone()
    if not row:
        return None
    emp = {k: (float(v) if hasattr(v, "as_tuple") else v) for k, v in dict(row).items()}
    return emp


def get_exit_comments(department):
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT ei."ExitInterviewText"
            FROM "Dim_ExitInterview" ei
            JOIN "Dim_Employee"   e ON ei."EmployeeID" = e."EmployeeID"
            JOIN "Dim_Department" d ON e."DepartmentID" = d."DepartmentID"
            WHERE d."DepartmentName" = :dept
              AND ei."ExitInterviewText" IS NOT NULL
            ORDER BY ei."ExitDate" DESC
            LIMIT 20
        """), {"dept": department})
        return [r[0] for r in result.fetchall()]


def get_risk_score(emp):
    row = {
        'TenureMonths': emp['TenureMonths'],
        'PerformanceRating': emp['PerformanceRating'],
        'EngagementScore': emp['EngagementScore'],
        'OvertimeHours': emp['OvertimeHours'],
        'PTOHoursUsed': emp['PTOHoursUsed'],
        'CommuteDistanceKM': emp['CommuteDistanceKM'],
        'pay_band_position': emp['pay_band_position'] if emp['pay_band_position'] is not None else 0.5,
        'months_since_last_raise': (emp['days_since_last_raise'] or 0) / 30,
        'JobLevel_encoded': ENCODERS['JobLevel'].get(emp['JobLevel'], 0),
        'EmploymentType_encoded': ENCODERS['EmploymentType'].get(emp['EmploymentType'], 0),
        'DeptTier_encoded': ENCODERS['DeptTier'].get(emp['DeptTier'], 0),
        'Region_encoded': ENCODERS['Region'].get(emp['Region'], 0),
        'StoreFormat_encoded': ENCODERS['StoreFormat'].get(emp['StoreFormat'], 0),
    }
    return float(model.predict_proba(pd.DataFrame([row])[FEATURES])[0][1])


def add_flags_and_tier(emp):
    emp['flag_low_engagement'] = int(emp['EngagementScore'] < 3.0)
    emp['flag_high_overtime'] = int(emp['OvertimeHours'] > 15)
    emp['flag_long_commute'] = int(emp['CommuteDistanceKM'] > 25)
    emp['flag_no_raise_1yr'] = int((emp['days_since_last_raise'] or 0) > 365)
    emp['flag_low_pto_use'] = int(emp['PTOHoursUsed'] < 8)
    emp['flag_tenure_spike_1yr'] = int(10 <= emp['TenureMonths'] <= 14)
    emp['flag_tenure_spike_4yr'] = int(34 <= emp['TenureMonths'] <= 50)
    p = emp['attrition_probability']
    emp['risk_tier'] = 'High' if p >= 0.6 else 'Medium' if p >= 0.3 else 'Low'


def call_llm(prompt):
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content":
                "You are a professional HR analytics assistant. Give clear, "
                "empathetic, actionable responses. Be concise, avoid jargon."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=600,
        temperature=0.4,
    )
    return response.choices[0].message.content


@app.route('/report')
def report():
    employee_id = request.args.get('employee_id', type=int)
    action = request.args.get('action', 'explain')

    if not employee_id:
        return render_template('report.html', error="No employee ID provided.")
    if action not in VALID_ACTIONS:
        action = 'explain'

    employee = get_employee_data(employee_id)
    if not employee:
        return render_template('report.html',
                               error=f"Employee ID {employee_id} not found.")

    employee['attrition_probability'] = get_risk_score(employee)
    add_flags_and_tier(employee)

    if action == 'explain':
        prompt, label = prompt_explain_prediction(employee), "Prediction Explanation"
    elif action == 'retention':
        prompt, label = prompt_retention_plan(employee), "Retention Action Plan"
    elif action == 'summary':
        prompt, label = prompt_risk_profile_summary(employee), "Risk Profile Summary"
    else:
        dept = employee['DepartmentName']
        prompt = prompt_exit_interview_summary(get_exit_comments(dept), dept)
        label = "Exit Interview Summary"

    try:
        ai_output = call_llm(prompt)
    except Exception as exc:
        ai_output = f"AI service error: {exc}"

    return render_template('report.html', employee=employee, action=action,
                           action_label=label, ai_output=ai_output)


@app.route('/')
def index():
    return ('<h2 style="font-family:Segoe UI;padding:30px">HR Attrition AI Assistant</h2>'
            '<ul style="font-family:Segoe UI;line-height:2">'
            '<li><a href="/report?employee_id=1&action=explain">Explain - Employee 1</a></li>'
            '<li><a href="/report?employee_id=1&action=retention">Retention plan - Employee 1</a></li>'
            '<li><a href="/report?employee_id=1&action=summary">Risk summary - Employee 1</a></li>'
            '<li><a href="/report?employee_id=1&action=exit">Exit summary - Employee 1</a></li>'
            '</ul>')


if __name__ == '__main__':
    app.run(debug=True, port=5000)
