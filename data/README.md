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

## `muddy_sire_bonus.json`

Static reference for the direct heavy/sloppy-going sire bonus. It stores only
the article-derived sire names, source URLs, and the verification date; it
does not redistribute the source articles. The application applies the bonus
only to the listed horse's sire, only on turf or dirt marked `重` or `不良`,
and caps the direct final-index addition at `+1.8`.
