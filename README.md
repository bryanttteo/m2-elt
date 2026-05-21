# Module 2 Project – Team Assignment (Enterprise Structure)

## Context
For full project requirements and scope, refer to:
`./assignment/Module 2 Assignment Project V2.pdf`

---

## Overview
This document defines the module ownership, responsibilities, deliverables, and enterprise role mapping for the end-to-end data engineering project.

---

## Team Structure Summary
- Leads are responsible for module ownership and technical direction
- Members support implementation, testing, and execution
- All members contribute to final documentation and presentation

---

## Module Assignments

| Module | Lead | Member Support | Responsibilities | Deliverables | Enterprise Role Mapping |
|---|---|---|---|---|---|
| 1. Data Ingestion | John Phang | Bryan Teo | Load raw datasets into warehouse, build ingestion scripts, define raw tables, handle missing data and data types | Python ingestion scripts, raw tables, ingestion pipeline workflow | Data Engineering |
| 2. Data Warehouse Design | John Phang | Soon Meng | Design star schema, build fact and dimension tables, define relationships, design warehouse structure | ERD diagram, star schema design, SQL warehouse models | Data Architecture / Data Modeling |
| 3. ELT Pipeline (dbt) | Charmaine | Bryan Teo | Build dbt transformation models, clean and transform data, create business metrics and derived fields | dbt staging/intermediate/marts models, transformation SQL | Analytics Engineering |
| 4. Data Quality Testing | Charmaine | Ang Jenn Fang | Define validation rules, implement data quality checks, ensure referential integrity and business logic accuracy | Great Expectations tests, SQL validation scripts, QA reports | Data Quality / Data Governance |
| 5. Data Analysis with Python | Hoong Jun | Lim Chun Wei | Perform EDA, generate KPIs, build insights, create visualizations and business recommendations | Jupyter notebooks, charts, KPI analysis, insights report | Data Analytics / Business Intelligence |
| 6. Pipeline Orchestration (Optional) | Hoong Jun | Soon Meng | Automate pipeline execution, schedule workflows, monitor pipeline runs | Airflow/GitHub Actions workflows, orchestration scripts | Data Orchestration / Data Operations |
| 7. Documentation & Executive Presentation | All Team Members | All Team Members | Technical documentation, architecture diagrams, storytelling, slide deck creation, rehearsal, final presentation delivery | README, architecture diagrams, final report, slide deck, presentation | Cross-functional Data Delivery |

---

## Notes
- Each module lead is accountable for final output quality
- Members support implementation and cross-learning across modules
- Final presentation is a shared responsibility across all members
- Ensure alignment with project requirements in the referenced PDF