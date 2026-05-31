# Warehouse Design  (Module 2)
**Owner:** Charmaine · **Support:** Soon Meng · **Role:** Data Architecture / Modeling

## Purpose
Design the **star schema** that Module 3 (dbt) implements. This folder is the *design*, not the build — it defines the contract everyone downstream depends on.

## Needs (inputs)
- <img width="50" height="30" alt="image" src="https://github.com/user-attachments/assets/8f942755-4d55-49a7-9971-9f11ee78ad84" /> The bronze table shapes from M1 (`raw_commerce.*` columns).
- Understanding of the business questions M5 must answer (revenue, segmentation, delivery).

## Produces (outputs)
- **`m2-elt_star_schema.drawio`** — overview plan of the dimensional model.
  Documentation: [Drive](https://drive.google.com/file/d/1Cb-3G_E0OHcwrz1ZmtNZbWm5-XjAtr71/view?usp=drive_link).
- **`PDF: m2-elt_star_schema`** — entity-relationship diagram of the dimensional model.
  ![Star Schema](image.png)
  Online: [dbdiagramio](https://dbdiagram.io/d/m2-elt-6a16fd13b62396d22c82645d)
  Documentation: [Drive](https://drive.google.com/file/d/1U9KXC5qSOBrSx2dRwdxkpBp_2FdNcUku/view?usp=drive_link)
- Problem Statement and Business Questions, [link](https://docs.google.com/document/d/1geYQtT6bjmq3rdpn3qysy86DH5Obn2BB2E5qaGAfY4s/edit?usp=drive_link)
- Refer to [file on Problem Statement and Business Questions](https://docs.google.com/document/d/1geYQtT6bjmq3rdpn3qysy86DH5Obn2BB2E5qaGAfY4s/edit?usp=drive_link): **`star_schema.md`** — the dimensional model spec: dimensions, facts, grains, surrogate keys, and the consumer-mart column contracts.

## Hand-off to next (→ M3, M4, M5)
This is the **central contract**. Once `star_schema.md` is committed:
- M3 implements these exact dim/fct/mart shapes in dbt.
- M4 writes tests against these columns and relationships.
- M5 builds charts assuming these mart columns exist.
All three can work in parallel against this spec before M3 finishes building.

## Design summary (see star_schema.md for detail)
- **Dimensions:** dim_customer, dim_product, dim_seller, dim_date.
- **Fact:** fct_order_items (grain: one row per order line item).
- **Consumer marts:** mart_customer_360 (RFM, CLV), mart_monthly_revenue (gmv by month × category).
