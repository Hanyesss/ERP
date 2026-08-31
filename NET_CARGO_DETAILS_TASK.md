# ERP task — populate «Детали груза» for NET shipment orders (+ price/kg)

## Problem
NET (PARCEL/warehouse) shipments arrive at `POST /api/integration/net/shipments`
and are turned into a logistics Order by `upsert_net_shipment`
(`backend/app/integrations/net_app/service.py`). That function currently sets
only `total_sale_cny`, `notes` (a text blob) and `tracking_number` — it creates
**no `OrderItem` rows**. So the order's «Детали груза» table (наименование, вес,
объём, плотность, цена/кг, стоимость груза, мест) is empty for every NET order.
Weight shows only inside the notes string; volume/price-per-kg are lost.

WH now DOES send volume (fixed on the WH side): the payload `NetShipmentIn`
carries `total_weight_kg`, `total_volume_m3`, and per box `weight_kg`,
`volume_m3`, `paid_rub`, `parcels_count`, `city`, `box_code`. (Schema already had
these fields in `net_app/schemas.py`.)

## What to build
In `upsert_net_shipment`, on both create and update, (re)build the order's
`OrderItem` rows from `payload.boxes` — **one OrderItem per box** (delete existing
NET-generated items first so re-sync is idempotent). Map each box → OrderItem:

- `name`         = f"{box.box_code} · {box.city}"   (e.g. "МОС-00006 · Москва")
- `weight_kg`    = box.weight_kg
- `volume_m3`    = box.volume_m3
- `density_kg_m3`= weight_kg / volume_m3  (guard divide-by-zero → None)
- `places_count` = box.parcels_count
- `quantity`     = box.parcels_count, `unit` = "шт"
- `price_per_kg` = **derived**, NOT manual (this is the user's rule):
    price_per_kg (USD) = (box revenue in USD) / weight_kg
    where box revenue = box.paid_rub converted to USD at the ERP rate
    (reuse the same FX path as `_shipment_revenue_cny`; RUB→USD via the order's
    date rate). `price_per_kg_currency = "USD"`. Guard weight 0 → None.
- `cargo_value` / `cargo_value_currency`: leave null for NET (we don't get a
  declared goods value from NET) — or set to the box revenue if the form needs it.

Order-level: keep `total_sale_cny` as today (from `total_paid_rub`). The delivery
"стоимость доставки" cost article stays whatever the ERP already does for
logistics — do NOT double-count: NET revenue is the client-paid total, it is the
`total_sale`, not a cost.

## Idempotency
`upsert_net_shipment` is keyed by `shipment_ref`. On update, delete the order's
existing NET-origin OrderItems and recreate from the current payload, so WH's
`⟳ ERP` re-sync (POST /api/shipments/{sid}/resync) correctly refreshes weight/
volume/price-per-kg.

## Verify
Re-sync SHP-000006 from WH (it already re-pushes with volume). Open NET-SHP-000006
in ERP → «Детали груза» should list 5 rows (one per box) with вес, объём,
плотность, цена/кг (USD, derived), мест. Note: demo boxes whose parcels have no
measured dims will show volume 0 — that's data, not a bug.
