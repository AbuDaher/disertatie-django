# CSV Mapping Fix

Corectează fișierul `sample_data/ebay_discovery_sample.csv` și loaderul CSV din `discovery/services.py`.

Problema anterioară: rândurile CSV aveau o virgulă în plus după `item_url`, ceea ce deplasa valorile:
- `seller_feedback_score` ajungea în `seller_feedback_percent`;
- `seller_feedback_percent` ajungea în `rating`;
- `rating` ajungea în `review_count`;
- `review_count` ajungea în `estimated_orders`;
- `estimated_orders` ajungea în `trend_score`.

După aplicare, trebuie făcută o căutare nouă în `/oportunitati/`. Nu folosi rezultate vechi salvate înainte de patch.
