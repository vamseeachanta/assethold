# Sands Investment Group CRE Listings Dataset

**Source:** sandsig.com email newsletters and listing notifications
**Date range:** January 2026 – April 6, 2026
**Total listings:** 500
**Legal scan:** PASSED — no protected client references found

## Files

| File | Size | Description |
|------|------|-------------|
| `listings.json` | 245 KB | Raw extracted listings with all email fields |
| `listings.csv` | 148 KB | Same data, tabular format |
| `listings_enriched.json` | 295 KB | Listings with inferred fields (state, lease type, investment grade, property types) |
| `market_analysis.json` | 3 KB | Aggregated statistics and market overview |

## Key Statistics

- **Cap rates:** 97 listings with explicit cap rates (avg: 7.62%)
- **Prices:** 58 listings with asking prices (avg: $3,067,454)
- **Building SF:** 27 listings (avg: 18,265 SF)
- **Lease years remaining:** 50 listings (avg: 15.5 years)
- **Investment grade tenants:** 46 listings
- **Listing types:** 282 Active, 154 New, 61 Price Reduced, 3 Early Access

## Top Property Types Identified
- NNN (189 listings)
- Retail (36)
- Medical (20)
- Childcare / KinderCare (30)
- Walmart-anchored (14)
- Industrial (14)
- Office (11)
- Gas stations (8)
- Pizza Hut (8)

## Data Extraction Notes
- Structured data extracted from subject lines: cap rates, prices, square footage, lease terms, listing types
- Body text parsing was attempted for address extraction but produces noisy results due to multi-state corporate footers and operator portfolios
- For future work: parse listing URLs to extract precise property addresses from Sands IG website

## Legal Compliance
- Scanned against `.legal-deny-list.yaml` (18 client reference patterns)
- Zero matches found — all data is publicly available CRE market information
- Safe for use in analysis, modeling, and public repos
