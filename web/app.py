"""
HR Attrition Indicator — Flask AI Assistant
File: web/app.py

One route. One page. Four focused AI actions.
Triggered from Power BI via Web URL action button.

GenAI: Groq API (free tier) with Llama-3 model.
In production: swap for IBM watsonx or Azure OpenAI —
the prompt engineering approach is model-agnostic.

Setup:
    1. Sign up free at https://console.groq.com
    2. Create an API key
    3. Run in terminal: export GROQ_API_KEY="your-key-here"
    4. pip install flask groq sqlalchemy psycopg2-binary joblib pandas

Usage:
    cd web
    python3 app.py
    Open: http://localhost:5000/report?employee_id=1&action=explain

Power BI button URL:
    http://localhost:5000/report?employee_id=[EmployeeID]&action=explain
"""

import os
import sys
import joblib
import pandas as pd
from flask import Flask, render_template, request
from sqlalchemy import create_engine, text
from groq import Groq

# ----------------------------------------------------------------
# Setup — add parent folder to path so genai/ is importable
# ----------------------------------------------------------------
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from genai.prompts import (
    prompt_explain_prediction,
    prompt_retention_plan,
    prompt_risk_profile_summary,
    prompt_exit_interview_summary,
)

app = Flask(__name__)

# update password to match your PostgreSQL install
DB_URL = "postgresql://postgres:postgresql25@localhost:5432/hr_attrition"
engine = create_engine(DB_URL)

# load trained model
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model   = joblib.load(os.path.join(BASE_DIR, 'data', 'model.pkl'))
FEATURES = joblib.load(os.path.join(BASE_DIR, 'data', 'model_features.pkl'))

# Groq client — reads GROQ_API_KEY from environment automatically
groq_client = Groq()

VALID_ACTIONS = {"explain", "retention", "summary", "exit"}


# ----------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------
def get_employee_data(employee_id: int):
    """Fetch employee record from vw_high_risk_employees view."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT * FROM vw_high_risk_employees
                WHERE "EmployeeID" = :eid
                LIMIT 1
            """),
            {"eid": employee_id}
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None


def get_exit_comments(department: str):
    """Fetch exit interview free-text for a department."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT ei."ExitInterviewText"
                FROM "Dim_ExitInterview" ei
                JOIN "Dim_Employee" e  ON ei."EmployeeID" = e."EmployeeID"
                JOIN "Dim_Department" d ON e."DepartmentID" = d."DepartmentID"
                WHERE d."DepartmentName" = :dept
                  AND ei."ExitInterviewText" IS NOT NULL
                ORDER BY ei."ExitDate" DESC
                LIMIT 20
            """),
            {"dept": department}
        )
        return [row[0] for row in result.fetchall()]


def get_risk_score(employee: dict) -> float:
    """Run ML model prediction for this employee."""
    row = {
        'TenureMonths':          employee.get('TenureMonths', 0),
        'PerformanceRating':     employee.get('PerformanceRating', 3),
        'EngagementScore':       employee.get('EngagementScore', 3.5),
        'OvertimeHours':         employee.get('OvertimeHours', 0),
        'PTOHoursUsed':          employee.get('PTOHoursUsed', 0),
        'CommuteDistanceKM':     employee.get('CommuteDistanceKM', 5),
        'pay_band_position':     employee.get('pay_band_position') or 0.5,
        'months_since_last_raise': (employee.get('days_since_last_raise') or 0) / 30,
        'JobLevel_encoded':      hash(str(employee.get('JobLevel'))) % 5,
        'EmploymentType_encoded': 0 if employee.get('EmploymentType') == 'Hourly' else 1,
        'DeptTier_encoded':      hash(str(employee.get('DeptTier'))) % 3,
        'Region_encoded':        hash(str(employee.get('Region'))) % 5,
        'StoreFormat_encoded':   hash(str(employee.get('StoreFormat'))) % 4,
    }
    df_row = pd.DataFrame([row])[FEATURES]
    return float(model.predict_proba(df_row)[0][1])


def call_llm(prompt: str) -> str:
    """Call Groq API with Llama-3, return text response."""
    response = groq_client.chat.completions.create(
        model="llama3-8b-8192",   # free, fast, capable enough for HR reports
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional HR analytics assistant. "
                    "Give clear, empathetic, actionable responses. "
                    "Be concise and do not use unnecessary jargon."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=600,
        temperature=0.4,   # lower = more consistent, less creative
    )
    return response.choices[0].message.content


# ----------------------------------------------------------------
# Routes
# ----------------------------------------------------------------
@app.route('/report')
def report():
    employee_id = request.args.get('employee_id', type=int)
    action      = request.args.get('action', 'explain')

    if not employee_id:
        return render_template('report.html', error="No employee ID provided.")
    if action not in VALID_ACTIONS:
        action = 'explain'

    # fetch employee record
    employee = get_employee_data(employee_id)
    if not employee:
        return render_template(
            'report.html',
            error=f"Employee ID {employee_id} not found or is no longer active."
        )

    # add ML risk score
    employee['attrition_probability'] = get_risk_score(employee)
    employee['days_since_last_raise']  = employee.get('days_since_last_raise') or 0

    # select prompt
    if action == 'explain':
        prompt       = prompt_explain_prediction(employee)
        action_label = "Prediction Explanation"
    elif action == 'retention':
        prompt       = prompt_retention_plan(employee)
        action_label = "Retention Action Plan"
    elif action == 'summary':
        prompt       = prompt_risk_profile_summary(employee)
        action_label = "Risk Profile Summary"
    elif action == 'exit':
        comments     = get_exit_comments(employee.get('DepartmentName', ''))
        prompt       = prompt_exit_interview_summary(
                           comments, employee.get('DepartmentName', 'Unknown'))
        action_label = "Exit Interview Summary"

    # call LLM
    ai_output = call_llm(prompt)

    return render_template(
        'report.html',
        employee=employee,
        action=action,
        action_label=action_label,
        ai_output=ai_output,
    )


@app.route('/')
def index():
    return """
    <h2 style="font-family:Segoe UI;padding:30px">
        HR Attrition AI Assistant
    </h2>
    <p style="font-family:Segoe UI;padding:0 30px">
        Open from Power BI or test directly:
    </p>
    <ul style="font-family:Segoe UI;padding:10px 50px;line-height:2">
      <li><a href="/report?employee_id=1&action=explain">
          Explain prediction — Employee 1</a></li>
      <li><a href="/report?employee_id=1&action=retention">
          Retention plan — Employee 1</a></li>
      <li><a href="/report?employee_id=1&action=summary">
          Risk profile summary — Employee 1</a></li>
      <li><a href="/report?employee_id=1&action=exit">
          Exit interview summary</a></li>
    </ul>
    """


if __name__ == '__main__':
    app.run(debug=True, port=5000)
