-- Performance indexes on Fact_Employment foreign keys
-- Run this after 01_schema.sql. Postgres does not auto-index FK columns
-- (unlike primary keys), and these joins will be hit constantly in
-- analytical queries (attrition by department, store, manager, month).

CREATE INDEX idx_fact_employee ON "Fact_Employment" ("EmployeeID");
CREATE INDEX idx_fact_snapshotdate ON "Fact_Employment" ("SnapshotDateID");
CREATE INDEX idx_fact_department ON "Fact_Employment" ("DepartmentID");
CREATE INDEX idx_fact_store ON "Fact_Employment" ("StoreID");
CREATE INDEX idx_fact_manager ON "Fact_Employment" ("ManagerID");

-- Also useful: employee-level history tables are always queried by EmployeeID
CREATE INDEX idx_comp_employee ON "Dim_Compensation" ("EmployeeID");
CREATE INDEX idx_promo_employee ON "Dim_PromotionHistory" ("EmployeeID");
CREATE INDEX idx_survey_employee ON "Dim_EngagementSurvey" ("EmployeeID");
CREATE INDEX idx_exit_employee ON "Dim_ExitInterview" ("EmployeeID");
