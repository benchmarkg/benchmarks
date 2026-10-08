"""The record gates (07 S8): verification ceiling, provenance and the derived-field guard (P3-S4-T02).
Moved from ingest/gates.py into the gates package by P5-S2-T05; nothing in them changed."""
from __future__ import annotations

import os

from ingest.gates._common import ROOT, GateError

# ---- the verification ceiling (P3-S4-T02) -----------------------------------------------------------------
#
# 07 S8: "No ingested record above independent-reproduction (rank 3). Rank 3 additionally requires a reachable
# artifact_url." Two locks, so that a future adapter cannot promote itself: the rung must be one
# taxonomy/verification.yaml lets a machine assign (ingest/verification.py), AND its rank must be at most
# CEILING_RANK whatever that file says -- a taxonomy edit marking rung 4 machine-assignable does not lift it.

CEILING_RANK = 3


def ranks(root: str = ROOT) -> dict[str, int]:
    from schema.taxonomy import read_yaml
    return {r['id']: r['rank'] for r in read_yaml(os.path.join(root, 'taxonomy', 'verification.yaml'))['rungs']}


def verification_ceiling(draft: dict, transcript=None, root: str = ROOT) -> None:
    """GateError unless the draft's verification is machine-assignable, at most rank 3, and -- at rank 3 --
    backed by a transcript that was reached (`transcript`: ingest.verification.Transcript) at the draft's
    artifact_url."""
    from ingest.verification import check_machine_claim
    rung = draft.get('verification')                                    # get-default: absent is refused below
    rank = ranks(root).get(rung)                                        # get-default: an unknown rung has no rank
    if rank is None:
        raise GateError('verification-ceiling', 'verification %r is not a rung of taxonomy/verification.yaml' % rung)
    if rank > CEILING_RANK:
        raise GateError('verification-ceiling', '%s is rank %d; no ingested record goes above rank %d '
                        '(independent-reproduction), whatever the taxonomy marks machine-assignable' % (rung, rank, CEILING_RANK))
    try:
        check_machine_claim(rung, transcript, root)
    except ValueError as e:
        raise GateError('verification-ceiling', str(e)) from None
    if rank == CEILING_RANK and transcript.url != draft.get('artifact_url'):    # get-default: absent is a mismatch
        raise GateError('verification-ceiling', 'the reached transcript %s is not the artifact_url %r of the draft'
                        % (transcript.url, draft.get('artifact_url')))        # get-default: as above


# ---- provenance (P3-S4-T02) -------------------------------------------------------------------------------
#
# 07 S8: "Every record carries a complete ingestion block ... A record without provenance must never merge."
# The keys 07 S8 lists, plus last_seen_upstream (04 S9: how an upstream deletion becomes visible). Each must be
# PRESENT; source_record_id may be null only for a source the adapter declares full-replace (04 S9), and
# otherwise must be a content key, never a row ordinal (schema.claim.check_source_record_id).

PROVENANCE_KEYS = ('batch', 'source_adapter', 'adapter_version', 'source_record_id', 'source_url', 'source_licence',
                   'licence_class', 'source_attribution', 'ingested_at', 'review_state', 'field_provenance',
                   'last_seen_upstream')


def provenance(draft: dict, full_replace: bool = False) -> None:
    """GateError unless the draft carries a complete, valid ingestion block."""
    from pydantic import ValidationError

    from schema.claim import Ingestion
    block = draft.get('ingestion')                                      # get-default: absent is refused below
    if not isinstance(block, dict):
        raise GateError('provenance', 'the draft has no ingestion block; a record without provenance never merges')
    missing = [k for k in PROVENANCE_KEYS if k not in block]
    if missing:
        raise GateError('provenance', 'the ingestion block lacks %s' % ', '.join(missing))
    if block['source_record_id'] is None and not full_replace:
        raise GateError('provenance', 'source_record_id is null, which only a full-replace source may declare (04 S9)')
    try:
        Ingestion.model_validate(block)
    except ValidationError as e:
        raise GateError('provenance', ' '.join(str(e).split())) from None


# ---- the derived-field guard (P3-S4-T02) ------------------------------------------------------------------
#
# 07 S8: "No draft contains comparability_key, condition_completeness, headroom or any other build-derived
# field." The others are the fields 04 marks derived and the models compute: a value the build owns, written
# by an adapter, is a value that rots.

DERIVED_FIELDS = frozenset({
    'comparability_key', 'condition_completeness', 'headroom', 'headroom_consumed',      # 07 S8 by name
    'curation_confidence', 'maintenance_status', 'inspect_evals_available', 'stewardship',  # 04: derived
    'higher_is_better',                                                                   # Metric, computed
})


def derived_fields(doc, path: str = '') -> list[str]:
    """Every dotted path in `doc` whose key is a derived field, at any depth."""
    out = []
    if isinstance(doc, dict):
        for k, v in doc.items():
            here = '%s.%s' % (path, k) if path else str(k)
            if k in DERIVED_FIELDS:
                out.append(here)
            out += derived_fields(v, here)
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            out += derived_fields(v, '%s[%d]' % (path, i))
    return out


def derived_field_guard(draft) -> None:
    hits = derived_fields(draft)
    if hits:
        raise GateError('derived-field', 'the draft writes build-derived field(s) %s; only the build computes them'
                        % ', '.join(hits))
