"""A seeded violation for scripts/check_no_get_default.py (P5-S4-T06). Never imported.

Line 11 is the failure 07 S9.2 names: a renamed upstream field would read as a score of 0.0 and
flow into a PR looking like data. The lint must exit 1 on this directory.
"""


def normalise(row):
    return {
        'name': row['Model version'],
        'score': row.get('Score', 0.0),
    }
