# TOKYO12R Data Files

## `Sire_data.csv`

Static sire aptitude reference for JRA forecasting.

The values are visually digitized from Sportiva's "種牡馬適性分布図 2026".
The original image is not redistributed in this repository.

Columns:

- `sire_name`: sire name
- `surface_axis`: `-100` means dirt-oriented, `0` neutral, `100` turf-oriented
- `distance_m`: visually estimated suitable distance in meters
- `confidence`: visual reading confidence
- `source`: source identifier

The file is intended as an initial static reference. It should later be
re-estimated from accumulated race results when enough local data exists.
