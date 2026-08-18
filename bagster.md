# Bagster Operations

## What is Bagster?
Waste Management **Dumpster in a Bag**  
**Model:** 775-658  
**Store:** Home Depot (~$30)  
**Capacity:** up to ~3,300 lb / ~3 cubic yards  
**Heavy materials:** max **~1 cubic yard** of concrete, dirt, brick, rock, sod, etc.

Always check ZIP pickup price on [thebagster.com](https://thebagster.com) before quoting a total.

## Two offers
1. **Coordinate** — client bag + you schedule / advise placement (flat fee)
2. **Demo + load** — your labor fills the bag; bag + WM pickup in the quote

You are not the hauler. WM does pickup.

## Workflow
1. **Price pickup** for the job ZIP (thebagster.com)
2. **Buy bag** — HD ~$30 (or client buys)
3. **Place** — private property, ≥5 ft from structures/vehicles, within ~16 ft of street/drive for crane, no overhead wires
4. **Fill** — straps should meet in the middle over the load; don’t drag the bag once filling starts
5. **Schedule** — thebagster.com or 1-877-789-BAGS; pay WM for collection
6. **Pickup** — typically within a few business days; nobody needs to be home

## Job status (POST to Peekagate `/api/state` only)
```json
{
  "job": "bagster",
  "status": "placed",
  "zip": "12205",
  "placed_at": "2026-08-18T18:00:00Z",
  "notes": "driveway edge, clear of wires"
}
```
Statuses: `placed` | `filling` | `full` | `scheduled` | `picked`

No Flask changes. Workers push; dashboard shows last state.

## Weight / load notes
| Material | Notes |
|----------|--------|
| Drywall, wood, flooring, carpet | Common Bagster loads |
| Heavy (concrete, dirt, brick, sod) | Cap ~1 cubic yard of the bag |
| Prohibited | Hazardous, liquids, etc. — follow WM rules |

## Contractor bags (self-haul, not Bagster)
- Husky 42 gal / HDX / Ultrasac — you haul to transfer station
- Different product; use when Bagster rules or price don’t fit

## Safety / placement
- Don’t overfill past safe strap lift
- Clear path for crane truck
- No bag on public street without checking local rules
- Buffer WM trip/overweight risk in your quote

## Capital Region
Log real pickup $ for ZIPs you work (12205, 12305, etc.) here as you price them:

| ZIP | Pickup $ | Notes | Date |
|-----|----------|-------|------|
| | | | |
