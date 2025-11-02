from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from django.db import transaction

from .models import Segment


@dataclass(frozen=True)
class SegmentSeed:
    """
    Encapsulates the metadata required to create a default Segment instance.
    """

    name: str
    description: str
    code: str


DEFAULT_SEGMENTS: Sequence[SegmentSeed] = (
    SegmentSeed(
        name="All Contacts",
        description="All contacts that have an email address.",
        code="""\
def apply(qs):
    return qs.filter(
        email__isnull=False,
    ).exclude(
        email__exact='',
    ).distinct()
""",
    ),
    SegmentSeed(
        name="Staff Contacts",
        description="Staff-owned contacts that have an email address.",
        code="""\
def apply(qs):
    return qs.filter(
        owner__isnull=False,
        owner__is_staff=True,
        email__isnull=False,
    ).exclude(
        email__exact='',
    ).distinct()
""",
    ),
    SegmentSeed(
        name="Verified Users",
        description="Contacts linked to auth users with verified email addresses.",
        code="""\
def apply(qs):
    return qs.filter(
        attributes__auth_user_id__isnull=False,
        attributes__auth_user_email_verified=True,
        email__isnull=False,
    ).exclude(
        email__exact='',
    ).distinct()
""",
    ),
)

LEGACY_SEGMENTS_TO_REMOVE: Sequence[str] = (
    "Verified Contacts",
)

LEGACY_SEGMENT_CODE_VARIANTS: dict[str, tuple[str, ...]] = {
    "All Contacts": (
        """\
def apply(qs):
    return qs.distinct()
""",
    ),
    "Staff Contacts": (
        """\
def apply(qs):
    return qs.filter(owner__isnull=False, owner__is_staff=True).distinct()
""",
    ),
}

LEGACY_SEGMENT_DESCRIPTIONS: dict[str, tuple[str, ...]] = {
    "All Contacts": (
        "Every contact stored in the CRM.",
    ),
    "Staff Contacts": (
        "Contacts owned by staff users.",
    ),
}


def ensure_default_segments(segment_seeds: Iterable[SegmentSeed] | None = None) -> list[Segment]:
    """
    Ensure that the default Segment records exist.

    Segments are only created when missing; an existing segment is preserved
    to avoid clobbering manual edits made by administrators.
    """

    seeds = tuple(segment_seeds) if segment_seeds is not None else DEFAULT_SEGMENTS
    created_segments: list[Segment] = []

    seed_names = {seed.name for seed in seeds}

    with transaction.atomic():
        if LEGACY_SEGMENTS_TO_REMOVE:
            Segment.objects.filter(name__in=LEGACY_SEGMENTS_TO_REMOVE).exclude(
                name__in=seed_names
            ).delete()

        for seed in seeds:
            segment, created = Segment.objects.get_or_create(
                name=seed.name,
                defaults={"description": seed.description, "code": seed.code},
            )
            if not created:
                fields_to_update: dict[str, str] = {}
                legacy_desc = LEGACY_SEGMENT_DESCRIPTIONS.get(seed.name, ())
                if not segment.description or segment.description in legacy_desc:
                    fields_to_update["description"] = seed.description
                legacy_variants = {
                    variant.strip()
                    for variant in LEGACY_SEGMENT_CODE_VARIANTS.get(seed.name, ())
                }
                if not segment.code or segment.code.strip() in legacy_variants:
                    fields_to_update["code"] = seed.code

                if fields_to_update:
                    for field, value in fields_to_update.items():
                        setattr(segment, field, value)
                    segment.save(update_fields=[*fields_to_update.keys(), "updated_at"])
            else:
                created_segments.append(segment)

    return created_segments
