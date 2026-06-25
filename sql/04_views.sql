-- =============================================================
-- HR Attrition Indicator — Analytical Views
-- Database: hr_attrition (PostgreSQL)
-- Purpose: Clean, pre-joined views that Power BI connects to.
--          These are the semantic bridge between the physical
--          star schema and the Power BI semantic layer.
-- Run after: 03_analytical_queries.sql (queries validated)
-- =============================================================


-- =============================================================
-- VIEW 1: Monthly attrition rate by department
-- Used in: Power BI trend line chart, dept slicer
-- =============================================================
CREATE OR REPLACE VIEW vw_monthly_attrition_by_dept AS
SELECT
    d."FullDate"                                            AS snapshot_month,
    d."Year",
    d."Month",
    d."MonthName",
    d."FiscalQuarter",
    dept."DepartmentName",
    dept."DeptTier",
    COUNT(f."EmployeeID")                                   AS headcount,
    SUM(CASE WHEN f."AttritionFlag" THEN 1 ELSE 0 END)     AS exits,
    SUM(CASE WHEN f."RegrettedAttritionFlag"
             THEN 1 ELSE 0 END)                            AS regretted_exits,
    ROUND(
        SUM(CASE WHEN f."AttritionFlag" THEN 1 ELSE 0 END)::decimal
        / NULLIF(COUNT(f."EmployeeID"), 0) * 100, 2
    )                                                       AS attrition_rate_pct,
    ROUND(
        SUM(CASE WHEN f."RegrettedAttritionFlag"
                 THEN 1 ELSE 0 END)::decimal
        / NULLIF(COUNT(f."EmployeeID"), 0) * 100, 2
    )                                                       AS regretted_rate_pct
FROM "Fact_Employment" f
JOIN "Dim_Date"       d    ON f."SnapshotDateID" = d."DateID"
JOIN "Dim_Department" dept ON f."DepartmentID"   = dept."DepartmentID"
GROUP BY
    d."FullDate", d."Year", d."Month", d."MonthName",
    d."FiscalQuarter", dept."DepartmentName", dept."DeptTier";


-- =============================================================
-- VIEW 2: Regretted vs non-regretted attrition summary
-- Used in: Power BI donut chart, KPI cards, dept breakdown
-- =============================================================
CREATE OR REPLACE VIEW vw_regretted_attrition AS
SELECT
    dept."DepartmentName",
    dept."DeptTier",
    s."Region",
    e."JobLevel",
    d."FiscalQuarter",
    d."Year",
    SUM(CASE WHEN f."AttritionFlag" THEN 1 ELSE 0 END)           AS total_exits,
    SUM(CASE WHEN f."RegrettedAttritionFlag"
             THEN 1 ELSE 0 END)                                  AS regretted_exits,
    SUM(CASE WHEN f."AttritionFlag"
             AND NOT f."RegrettedAttritionFlag"
             THEN 1 ELSE 0 END)                                  AS non_regretted_exits,
    ROUND(
        SUM(CASE WHEN f."RegrettedAttritionFlag"
                 THEN 1 ELSE 0 END)::decimal
        / NULLIF(SUM(CASE WHEN f."AttritionFlag"
                          THEN 1 ELSE 0 END), 0) * 100, 1
    )                                                             AS regretted_pct
FROM "Fact_Employment" f
JOIN "Dim_Employee"   e    ON f."EmployeeID"   = e."EmployeeID"
JOIN "Dim_Department" dept ON f."DepartmentID" = dept."DepartmentID"
JOIN "Dim_Store"      s    ON f."StoreID"      = s."StoreID"
JOIN "Dim_Date"       d    ON f."SnapshotDateID" = d."DateID"
WHERE f."AttritionFlag" = TRUE
GROUP BY
    dept."DepartmentName", dept."DeptTier", s."Region",
    e."JobLevel", d."FiscalQuarter", d."Year";


-- =============================================================
-- VIEW 3: Cost of attrition by job level
-- Used in: Power BI KPI card (total $ cost), bar chart by level
-- =============================================================
CREATE OR REPLACE VIEW vw_cost_of_attrition AS
SELECT
    e."JobLevel",
    e."EmploymentType",
    dept."DepartmentName",
    s."Region",
    d."Year",
    d."FiscalQuarter",
    COUNT(f."EmployeeID")                                   AS total_exits,
    ROUND(AVG(
        CASE WHEN e."EmploymentType" = 'Hourly'
             THEN f."HourlyRate" * 2080
             ELSE f."MonthlySalary" * 12
        END), 0)                                            AS avg_annual_salary,
    ROUND(SUM(
        CASE WHEN e."EmploymentType" = 'Hourly'
             THEN f."HourlyRate" * 2080
             ELSE f."MonthlySalary" * 12
        END
        * CASE e."JobLevel"
            WHEN 'Frontline'     THEN 0.5
            WHEN 'Team Lead'     THEN 0.75
            WHEN 'Store Manager' THEN 1.5
            WHEN 'Regional'      THEN 2.0
            WHEN 'Corporate'     THEN 2.0
            ELSE 1.0
          END), 0)                                          AS total_replacement_cost,
    CASE e."JobLevel"
        WHEN 'Frontline'     THEN 0.5
        WHEN 'Team Lead'     THEN 0.75
        WHEN 'Store Manager' THEN 1.5
        WHEN 'Regional'      THEN 2.0
        WHEN 'Corporate'     THEN 2.0
        ELSE 1.0
    END                                                     AS replacement_cost_factor
FROM "Fact_Employment" f
JOIN "Dim_Employee"   e    ON f."EmployeeID"    = e."EmployeeID"
JOIN "Dim_Department" dept ON f."DepartmentID"  = dept."DepartmentID"
JOIN "Dim_Store"      s    ON f."StoreID"       = s."StoreID"
JOIN "Dim_Date"       d    ON f."SnapshotDateID" = d."DateID"
WHERE f."AttritionFlag" = TRUE
GROUP BY
    e."JobLevel", e."EmploymentType", dept."DepartmentName",
    s."Region", d."Year", d."FiscalQuarter";


-- =============================================================
-- VIEW 4: Tenure cohort analysis
-- Used in: Power BI bar chart showing exit volume by tenure band
-- =============================================================
CREATE OR REPLACE VIEW vw_tenure_cohort AS
SELECT
    CASE
        WHEN f."TenureMonths" < 3   THEN '1. 0-3 months'
        WHEN f."TenureMonths" < 12  THEN '2. 3-12 months'
        WHEN f."TenureMonths" < 24  THEN '3. 1-2 years'
        WHEN f."TenureMonths" < 36  THEN '4. 2-3 years'
        WHEN f."TenureMonths" < 48  THEN '5. 3-4 years'
        ELSE                             '6. 4+ years'
    END                                                     AS tenure_band,
    dept."DepartmentName",
    e."JobLevel",
    COUNT(*)                                                AS total_exits,
    SUM(CASE WHEN f."RegrettedAttritionFlag"
             THEN 1 ELSE 0 END)                            AS regretted_exits,
    ROUND(AVG(f."EngagementScore"), 2)                     AS avg_engagement_at_exit,
    ROUND(AVG(f."PerformanceRating"), 2)                   AS avg_performance_at_exit,
    ROUND(AVG(f."OvertimeHours"), 1)                       AS avg_overtime_at_exit
FROM "Fact_Employment" f
JOIN "Dim_Employee"   e    ON f."EmployeeID"   = e."EmployeeID"
JOIN "Dim_Department" dept ON f."DepartmentID" = dept."DepartmentID"
WHERE f."AttritionFlag" = TRUE
GROUP BY tenure_band, dept."DepartmentName", e."JobLevel";


-- =============================================================
-- VIEW 5: Manager attrition clustering
-- Used in: Power BI table — "managers with highest team attrition"
-- This is one of the most actionable views in the whole project.
-- =============================================================
CREATE OR REPLACE VIEW vw_manager_clustering AS
SELECT
    mgr."EmployeeID"                                        AS manager_id,
    mgr."FullName"                                          AS manager_name,
    mgr."JobLevel"                                          AS manager_level,
    dept."DepartmentName",
    s."Region",
    COUNT(DISTINCT f."EmployeeID")                          AS team_headcount,
    SUM(CASE WHEN f."AttritionFlag"
             THEN 1 ELSE 0 END)                            AS team_exits,
    SUM(CASE WHEN f."RegrettedAttritionFlag"
             THEN 1 ELSE 0 END)                            AS team_regretted_exits,
    ROUND(
        SUM(CASE WHEN f."AttritionFlag"
                 THEN 1 ELSE 0 END)::decimal
        / NULLIF(COUNT(DISTINCT f."EmployeeID"), 0) * 100, 1
    )                                                       AS team_attrition_rate_pct,
    ROUND(AVG(f."EngagementScore"), 2)                     AS avg_team_engagement
FROM "Fact_Employment" f
JOIN "Dim_Employee"   mgr  ON f."ManagerID"    = mgr."EmployeeID"
JOIN "Dim_Department" dept ON f."DepartmentID" = dept."DepartmentID"
JOIN "Dim_Store"      s    ON f."StoreID"      = s."StoreID"
GROUP BY
    mgr."EmployeeID", mgr."FullName", mgr."JobLevel",
    dept."DepartmentName", s."Region"
HAVING COUNT(DISTINCT f."EmployeeID") >= 5;


-- =============================================================
-- VIEW 6: High-risk active employees
-- Used in: Power BI "employees to watch" table
--          + ML model feature table
--          + Flask AI assistant (fetched by EmployeeID)
-- This is the most important view — it's what the Power BI
-- "Generate AI Insights" button queries via the Flask app.
-- =============================================================
CREATE OR REPLACE VIEW vw_high_risk_employees AS
SELECT
    e."EmployeeID",
    e."FullName",
    e."JobLevel",
    e."EmploymentType",
    e."CommuteDistanceKM",
    dept."DepartmentName",
    dept."DeptTier",
    s."StoreName",
    s."Region",
    mgr."FullName"                                          AS manager_name,
    f."TenureMonths",
    f."PerformanceRating",
    f."EngagementScore",
    f."OvertimeHours",
    f."PTOHoursUsed",
    f."PTOHoursAvailable",

    -- pay band position (0=bottom, 1=top of band)
    ROUND(
        COALESCE(
            (f."HourlyRate"    - c."PayBandMin"),
            (f."MonthlySalary" * 12 - c."PayBandMin")
        )::decimal
        / NULLIF(c."PayBandMax" - c."PayBandMin", 0), 2
    )                                                       AS pay_band_position,

    c."PayBandMin",
    c."PayBandMax",
    c."EffectiveDate"                                       AS last_raise_date,
    CURRENT_DATE - c."EffectiveDate"                       AS days_since_last_raise,

    -- individual risk flags
    CASE WHEN f."EngagementScore" < 3.0 THEN 1 ELSE 0 END              AS flag_low_engagement,
    CASE WHEN f."OvertimeHours" > 15 THEN 1 ELSE 0 END                 AS flag_high_overtime,
    CASE WHEN e."CommuteDistanceKM" > 25 THEN 1 ELSE 0 END             AS flag_long_commute,
    CASE WHEN (CURRENT_DATE - c."EffectiveDate") > 365
         THEN 1 ELSE 0 END                                              AS flag_no_raise_1yr,
    CASE WHEN f."PTOHoursUsed" < 8
         THEN 1 ELSE 0 END                                              AS flag_low_pto_use,
    CASE WHEN f."TenureMonths" BETWEEN 10 AND 14
         THEN 1 ELSE 0 END                                              AS flag_tenure_spike_1yr,
    CASE WHEN f."TenureMonths" BETWEEN 34 AND 50
         THEN 1 ELSE 0 END                                              AS flag_tenure_spike_4yr,

    -- composite risk score (0-7)
    (
        CASE WHEN f."EngagementScore" < 3.0 THEN 1 ELSE 0 END +
        CASE WHEN f."OvertimeHours" > 15 THEN 1 ELSE 0 END +
        CASE WHEN e."CommuteDistanceKM" > 25 THEN 1 ELSE 0 END +
        CASE WHEN (CURRENT_DATE - c."EffectiveDate") > 365 THEN 1 ELSE 0 END +
        CASE WHEN f."PTOHoursUsed" < 8 THEN 1 ELSE 0 END +
        CASE WHEN f."TenureMonths" BETWEEN 10 AND 14 THEN 1 ELSE 0 END +
        CASE WHEN f."TenureMonths" BETWEEN 34 AND 50 THEN 1 ELSE 0 END
    )                                                                   AS risk_flag_count,

    -- risk tier label (used in Power BI conditional formatting)
    CASE
        WHEN (
            CASE WHEN f."EngagementScore" < 3.0 THEN 1 ELSE 0 END +
            CASE WHEN f."OvertimeHours" > 15 THEN 1 ELSE 0 END +
            CASE WHEN e."CommuteDistanceKM" > 25 THEN 1 ELSE 0 END +
            CASE WHEN (CURRENT_DATE - c."EffectiveDate") > 365 THEN 1 ELSE 0 END +
            CASE WHEN f."PTOHoursUsed" < 8 THEN 1 ELSE 0 END +
            CASE WHEN f."TenureMonths" BETWEEN 10 AND 14 THEN 1 ELSE 0 END +
            CASE WHEN f."TenureMonths" BETWEEN 34 AND 50 THEN 1 ELSE 0 END
        ) >= 4 THEN 'High'
        WHEN (
            CASE WHEN f."EngagementScore" < 3.0 THEN 1 ELSE 0 END +
            CASE WHEN f."OvertimeHours" > 15 THEN 1 ELSE 0 END +
            CASE WHEN e."CommuteDistanceKM" > 25 THEN 1 ELSE 0 END +
            CASE WHEN (CURRENT_DATE - c."EffectiveDate") > 365 THEN 1 ELSE 0 END +
            CASE WHEN f."PTOHoursUsed" < 8 THEN 1 ELSE 0 END +
            CASE WHEN f."TenureMonths" BETWEEN 10 AND 14 THEN 1 ELSE 0 END +
            CASE WHEN f."TenureMonths" BETWEEN 34 AND 50 THEN 1 ELSE 0 END
        ) >= 2 THEN 'Medium'
        ELSE 'Low'
    END                                                                 AS risk_tier

FROM "Fact_Employment" f
JOIN "Dim_Employee"    e    ON f."EmployeeID"   = e."EmployeeID"
JOIN "Dim_Department"  dept ON f."DepartmentID" = dept."DepartmentID"
JOIN "Dim_Store"       s    ON f."StoreID"      = s."StoreID"
JOIN "Dim_Employee"    mgr  ON f."ManagerID"    = mgr."EmployeeID"
JOIN "Dim_Compensation" c   ON e."EmployeeID"   = c."EmployeeID"
                            AND c."IsCurrent"   = TRUE
WHERE f."IsActive" = TRUE;
