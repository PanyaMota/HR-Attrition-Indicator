CREATE TABLE "Dim_Employee" (
  "EmployeeID" int PRIMARY KEY,
  "FullName" varchar,
  "Gender" varchar,
  "DOB" date,
  "HireDate" date,
  "CommuteDistanceKM" decimal,
  "JobLevel" varchar,
  "EmploymentType" varchar,
  "DepartmentID" int,
  "StoreID" int,
  "ManagerID" int
);

CREATE TABLE "Dim_Department" (
  "DepartmentID" int PRIMARY KEY,
  "DepartmentName" varchar,
  "DeptTier" varchar
);

CREATE TABLE "Dim_Store" (
  "StoreID" int PRIMARY KEY,
  "StoreName" varchar,
  "Region" varchar,
  "StoreFormat" varchar,
  "StoreSizeCategory" varchar
);

CREATE TABLE "Dim_Date" (
  "DateID" int PRIMARY KEY,
  "FullDate" date,
  "Year" int,
  "Month" int,
  "MonthName" varchar,
  "FiscalQuarter" varchar
);

CREATE TABLE "Dim_Compensation" (
  "CompensationID" int PRIMARY KEY,
  "EmployeeID" int,
  "EffectiveDate" date,
  "EndDate" date,
  "PayRate" decimal,
  "PayBandMin" decimal,
  "PayBandMax" decimal,
  "IsCurrent" boolean
);

CREATE TABLE "Dim_PromotionHistory" (
  "PromotionID" int PRIMARY KEY,
  "EmployeeID" int,
  "EffectiveDate" date,
  "EndDate" date,
  "JobLevel" varchar,
  "IsCurrent" boolean
);

CREATE TABLE "Dim_EngagementSurvey" (
  "SurveyID" int PRIMARY KEY,
  "EmployeeID" int,
  "SurveyDate" date,
  "EngagementScore" decimal,
  "ManagerRelationshipScore" decimal,
  "WorkloadScore" decimal,
  "CareerGrowthScore" decimal
);

CREATE TABLE "Dim_ExitInterview" (
  "ExitID" int PRIMARY KEY,
  "EmployeeID" int,
  "ExitDate" date,
  "ExitReasonCategory" varchar,
  "ExitInterviewText" text,
  "WouldRehire" varchar,
  "RegrettedExit" boolean
);

CREATE TABLE "Fact_Employment" (
  "EmploymentSK" int PRIMARY KEY,
  "EmployeeID" int,
  "SnapshotDateID" int,
  "DepartmentID" int,
  "StoreID" int,
  "ManagerID" int,
  "MonthlySalary" decimal,
  "HourlyRate" decimal,
  "OvertimeHours" decimal,
  "PTOHoursUsed" decimal,
  "PTOHoursAvailable" decimal,
  "PerformanceRating" int,
  "EngagementScore" decimal,
  "TenureMonths" int,
  "IsActive" boolean,
  "AttritionFlag" boolean,
  "RegrettedAttritionFlag" boolean
);

COMMENT ON COLUMN "Dim_Employee"."JobLevel" IS 'Frontline, Team Lead, Store Manager, Regional, Corporate';

COMMENT ON COLUMN "Dim_Employee"."EmploymentType" IS 'Hourly or Salaried';

COMMENT ON COLUMN "Dim_Employee"."ManagerID" IS 'self-referencing';

COMMENT ON COLUMN "Dim_Department"."DeptTier" IS 'Frontline, Mid, Corporate';

COMMENT ON COLUMN "Dim_Compensation"."EndDate" IS 'null = current record (SCD Type 2)';

COMMENT ON COLUMN "Dim_PromotionHistory"."EndDate" IS 'null = current record (SCD Type 2)';

COMMENT ON COLUMN "Dim_ExitInterview"."WouldRehire" IS 'Y or N';

COMMENT ON COLUMN "Fact_Employment"."MonthlySalary" IS 'null if hourly';

COMMENT ON COLUMN "Fact_Employment"."HourlyRate" IS 'null if salaried';

COMMENT ON COLUMN "Fact_Employment"."PerformanceRating" IS '1-5';

ALTER TABLE "Dim_Employee" ADD FOREIGN KEY ("DepartmentID") REFERENCES "Dim_Department" ("DepartmentID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "Dim_Employee" ADD FOREIGN KEY ("StoreID") REFERENCES "Dim_Store" ("StoreID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "Dim_Employee" ADD FOREIGN KEY ("ManagerID") REFERENCES "Dim_Employee" ("EmployeeID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "Dim_Compensation" ADD FOREIGN KEY ("EmployeeID") REFERENCES "Dim_Employee" ("EmployeeID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "Dim_PromotionHistory" ADD FOREIGN KEY ("EmployeeID") REFERENCES "Dim_Employee" ("EmployeeID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "Dim_EngagementSurvey" ADD FOREIGN KEY ("EmployeeID") REFERENCES "Dim_Employee" ("EmployeeID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "Dim_ExitInterview" ADD FOREIGN KEY ("EmployeeID") REFERENCES "Dim_Employee" ("EmployeeID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "Fact_Employment" ADD FOREIGN KEY ("EmployeeID") REFERENCES "Dim_Employee" ("EmployeeID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "Fact_Employment" ADD FOREIGN KEY ("SnapshotDateID") REFERENCES "Dim_Date" ("DateID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "Fact_Employment" ADD FOREIGN KEY ("DepartmentID") REFERENCES "Dim_Department" ("DepartmentID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "Fact_Employment" ADD FOREIGN KEY ("StoreID") REFERENCES "Dim_Store" ("StoreID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "Fact_Employment" ADD FOREIGN KEY ("ManagerID") REFERENCES "Dim_Employee" ("EmployeeID") DEFERRABLE INITIALLY IMMEDIATE;
