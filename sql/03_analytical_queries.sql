-- =============================================================
-- HR Attrition Indicator — Analytical Queries
-- Database: hr_attrition (PostgreSQL)
-- Purpose: Power BI dashboard + ML feature engineering
-- Run after: 01_schema.sql, 02_indexes.sql, load_data.py
-- =============================================================


-- =============================================================
-- QUERY 1: Monthly attrition rate by department
-- =============================================================
-- HR logic: attrition rate = exits in period / avg headcount.
-- Monthly granularity lets Power BI show trends over time.
-- Slicing by department reveals which areas are bleeding talent.
-- =============================================================

SELECT
    d."FullDate"                                        AS snapshot_month,
    d."FiscalQuarter",
    dept."DepartmentName",
    dept."DeptTier",
    COUNT(f."EmployeeID")                               AS headcount,
    SUM(CASE WHEN f."AttritionFlag" THEN 1 ELSE 0 END) AS exits,
    ROUND(
        SUM(CASE WHEN f."AttritionFlag" THEN 1 ELSE 0 END)::decimal
        / NULLIF(COUNT(f."EmployeeID"), 0) * 100, 2
    )                                                   AS attrition_rate_pct
FROM "Fact_Employment" f
JOIN "Dim_Date"       d    ON f."SnapshotDateID" = d."DateID"
JOIN "Dim_Department" dept ON f."DepartmentID"   = dept."DepartmentID"
GROUP BY
    d."FullDate", d."FiscalQuarter",
    dept."DepartmentName", dept."DeptTier"
ORDER BY d."FullDate", attrition_rate_pct DESC;


-- =============================================================
-- QUERY 2: Regretted vs non-regretted attrition
-- =============================================================
-- HR logic: not all exits are equal. Regretted = high performer
-- (rating >= 4) leaving voluntarily. This is the segment that
-- costs the most and matters most to retain.
-- This query is the foundation of your "risk segmentation" story.
-- =============================================================

SELECT
    dept."DepartmentName",
    SUM(CASE WHEN f."AttritionFlag" THEN 1 ELSE 0 END)           AS total_exits,
    SUM(CASE WHEN f."RegrettedAttritionFlag" THEN 1 ELSE 0 END)  AS regretted_exits,
    SUM(CASE WHEN f."AttritionFlag"
             AND NOT f."RegrettedAttritionFlag" THEN 1 ELSE 0 END) AS non_regretted_exits,
    ROUND(
        SUM(CASE WHEN f."RegrettedAttritionFlag" THEN 1 ELSE 0 END)::decimal
        / NULLIF(SUM(CASE WHEN f."AttritionFlag" THEN 1 ELSE 0 END), 0) * 100, 1
    )                                                             AS regretted_pct
FROM "Fact_Employment" f
JOIN "Dim_Department" dept ON f."DepartmentID" = dept."DepartmentID"
WHERE f."AttritionFlag" = TRUE
GROUP BY dept."DepartmentName"
ORDER BY regretted_exits DESC;


-- =============================================================
-- QUERY 3: Cost of attrition by job level
-- =============================================================
-- HR logic: replacement cost = salary * factor (varies by level).
-- Frontline = 0.5x (fast to hire, low ramp time)
-- Team Lead  = 0.75x
-- Store Mgr  = 1.5x  (long ramp, P&L ownership)
-- Regional+  = 2.0x  (executive search, longest time-to-productivity)
-- This turns attrition from a % into a dollar figure — the
-- number a CHRO actually cares about presenting to the CFO.
-- =============================================================

SELECT
    e."JobLevel",
    COUNT(f."EmployeeID")                               AS total_exits,
    ROUND(AVG(
        CASE
            WHEN e."EmploymentType" = 'Hourly'
            THEN f."HourlyRate" * 2080   -- annualise hourly rate
            ELSE f."MonthlySalary" * 12
        END
    ), 0)                                               AS avg_annual_salary,
    ROUND(AVG(
        CASE
            WHEN e."EmploymentType" = 'Hourly'
            THEN f."HourlyRate" * 2080
            ELSE f."MonthlySalary" * 12
        END
    ) * CASE e."JobLevel"
        WHEN 'Frontline'     THEN 0.5
        WHEN 'Team Lead'     THEN 0.75
        WHEN 'Store Manager' THEN 1.5
        WHEN 'Regional'      THEN 2.0
        WHEN 'Corporate'     THEN 2.0
        ELSE 1.0
    END, 0)                                             AS avg_replacement_cost,
    ROUND(SUM(
        CASE
            WHEN e."EmploymentType" = 'Hourly'
            THEN f."HourlyRate" * 2080
            ELSE f."MonthlySalary" * 12
        END
    ) * CASE e."JobLevel"
        WHEN 'Frontline'     THEN 0.5
        WHEN 'Team Lead'     THEN 0.75
        WHEN 'Store Manager' THEN 1.5
        WHEN 'Regional'      THEN 2.0
        WHEN 'Corporate'     THEN 2.0
        ELSE 1.0
    END, 0)                                             AS total_replacement_cost
FROM "Fact_Employment" f
JOIN "Dim_Employee" e ON f."EmployeeID" = e."EmployeeID"
WHERE f."AttritionFlag" = TRUE
GROUP BY e."JobLevel"
ORDER BY total_replacement_cost DESC;


-- =============================================================
-- QUERY 4: Tenure cohort analysis
-- =============================================================
-- HR logic: attrition risk is non-linear. It spikes around
-- month 12 (honeymoon period ends, better offers come in) and
-- again around months 36-48 (career plateau, no promotion).
-- This query maps exit volume to tenure stage so you can see
-- exactly where on the curve your org is losing people.
-- =============================================================

SELECT
    CASE
        WHEN f."TenureMonths" < 3   THEN '0-3 months'
        WHEN f."TenureMonths" < 12  THEN '3-12 months'
        WHEN f."TenureMonths" < 24  THEN '1-2 years'
        WHEN f."TenureMonths" < 36  THEN '2-3 years'
        WHEN f."TenureMonths" < 48  THEN '3-4 years'
        ELSE '4+ years'
    END                                                 AS tenure_band,
    COUNT(*)                                            AS total_exits,
    SUM(CASE WHEN f."RegrettedAttritionFlag"
             THEN 1 ELSE 0 END)                        AS regretted_exits,
    ROUND(AVG(f."EngagementScore"), 2)                 AS avg_engagement_at_exit,
    ROUND(AVG(f."PerformanceRating"), 2)               AS avg_performance_at_exit
FROM "Fact_Employment" f
WHERE f."AttritionFlag" = TRUE
GROUP BY tenure_band
ORDER BY MIN(f."TenureMonths");


-- =============================================================
-- QUERY 5: Manager attrition clustering
-- =============================================================
-- HR logic: a disproportionate share of regretted attrition
-- traces back to a small number of managers. If a manager's
-- team has unusually high exits, that's a management problem —
-- not a compensation or market problem. This query surfaces
-- the top 20 managers by team attrition rate, which becomes
-- one of the most actionable insights in your dashboard.
-- =============================================================

SELECT
    mgr."EmployeeID"                                    AS manager_id,
    mgr."FullName"                                      AS manager_name,
    mgr."JobLevel"                                      AS manager_level,
    COUNT(DISTINCT f."EmployeeID")                      AS team_size,
    SUM(CASE WHEN f."AttritionFlag" THEN 1 ELSE 0 END) AS team_exits,
    SUM(CASE WHEN f."RegrettedAttritionFlag"
             THEN 1 ELSE 0 END)                        AS team_regretted_exits,
    ROUND(
        SUM(CASE WHEN f."AttritionFlag" THEN 1 ELSE 0 END)::decimal
        / NULLIF(COUNT(DISTINCT f."EmployeeID"), 0) * 100, 1
    )                                                   AS team_attrition_rate_pct
FROM "Fact_Employment" f
JOIN "Dim_Employee" mgr ON f."ManagerID" = mgr."EmployeeID"
GROUP BY mgr."EmployeeID", mgr."FullName", mgr."JobLevel"
HAVING COUNT(DISTINCT f."EmployeeID") >= 5   -- exclude tiny teams (noise)
ORDER BY team_attrition_rate_pct DESC
LIMIT 20;


-- =============================================================
-- QUERY 6: High-risk employee segments (current active employees)
-- =============================================================
-- HR logic: combines the key attrition drivers into a composite
-- risk profile for currently active employees. This is the
-- query that feeds directly into your ML feature table and
-- your Power BI "who to watch" segment view.
-- Flags: low pay band position, declining engagement,
--        high overtime, long commute, no recent raise.
-- =============================================================

SELECT
    e."EmployeeID",
    e."FullName",
    e."JobLevel",
    e."EmploymentType",
    dept."DepartmentName",
    s."Region",
    f."TenureMonths",
    f."PerformanceRating",
    f."EngagementScore",
    f."OvertimeHours",
    e."CommuteDistanceKM",

    -- pay band position: 0 = at minimum, 1 = at maximum
    ROUND(
        (f."HourlyRate" - c."PayBandMin")::decimal
        / NULLIF(c."PayBandMax" - c."PayBandMin", 0), 2
    )                                                   AS pay_band_position,

    -- days since last compensation change
    CURRENT_DATE - c."EffectiveDate"                   AS days_since_last_raise,

    -- composite risk flags (each maps to a known driver)
    CASE WHEN f."EngagementScore" < 3.0 THEN 1 ELSE 0 END          AS flag_low_engagement,
    CASE WHEN f."OvertimeHours" > 15 THEN 1 ELSE 0 END             AS flag_high_overtime,
    CASE WHEN e."CommuteDistanceKM" > 25 THEN 1 ELSE 0 END         AS flag_long_commute,
    CASE WHEN (CURRENT_DATE - c."EffectiveDate") > 365
         THEN 1 ELSE 0 END                                          AS flag_no_raise_1yr,
    CASE WHEN f."TenureMonths" BETWEEN 10 AND 14 THEN 1 ELSE 0 END AS flag_tenure_spike_1yr,
    CASE WHEN f."TenureMonths" BETWEEN 34 AND 50 THEN 1 ELSE 0 END AS flag_tenure_spike_4yr,

    -- total risk flags (0-6): higher = more at-risk
    (
        CASE WHEN f."EngagementScore" < 3.0 THEN 1 ELSE 0 END +
        CASE WHEN f."OvertimeHours" > 15 THEN 1 ELSE 0 END +
        CASE WHEN e."CommuteDistanceKM" > 25 THEN 1 ELSE 0 END +
        CASE WHEN (CURRENT_DATE - c."EffectiveDate") > 365 THEN 1 ELSE 0 END +
        CASE WHEN f."TenureMonths" BETWEEN 10 AND 14 THEN 1 ELSE 0 END +
        CASE WHEN f."TenureMonths" BETWEEN 34 AND 50 THEN 1 ELSE 0 END
    )                                                               AS risk_flag_count

FROM "Fact_Employment" f
JOIN "Dim_Employee"    e    ON f."EmployeeID"   = e."EmployeeID"
JOIN "Dim_Department"  dept ON f."DepartmentID" = dept."DepartmentID"
JOIN "Dim_Store"       s    ON f."StoreID"      = s."StoreID"
JOIN "Dim_Compensation" c   ON e."EmployeeID"   = c."EmployeeID"
                            AND c."IsCurrent"   = TRUE
WHERE f."IsActive" = TRUE
ORDER BY risk_flag_count DESC, f."EngagementScore" ASC;

