"""
Historical / on-site beneficiary backfill (Option A + C).

Creates Applicant + Application + active LotAward on an existing block/lot,
with backdated awarded_at from beneficiary year — without running intake queues.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from applications.models import Application
from intake.models import Applicant
from units.models import ConstructionProgress, HousingUnit, LotAward, RelocationSite

HISTORICAL_BACKFILL_NOTE = 'Historical backfill'

HISTORICAL_MONITORING_EMPTY_MESSAGE = (
    'There is no 90 Day / 120 Day monitoring history for this beneficiary because they '
    'were registered on-site before the THA monitoring system was created. Scheduled '
    'field visits were not recorded in this system.'
)

HISTORICAL_POSSESSION_NOTE = (
    'These dates reflect when this beneficiary was first placed on the lot (historical record). '
    'They are not used for live compliance monitoring in the system.'
)


def is_historical_lot_award(lot_award) -> bool:
    if not lot_award:
        return False
    return HISTORICAL_BACKFILL_NOTE in (lot_award.notes or '')


def is_historical_applicant(applicant) -> bool:
    """True when applicant was created via historical on-site backfill."""
    if not applicant:
        return False
    app = getattr(applicant, 'application', None)
    if app and HISTORICAL_BACKFILL_NOTE in (app.notes or ''):
        return True
    if app:
        for award in app.lot_awards.all():
            if is_historical_lot_award(award):
                return True
    return False


def document_vault_applicant_q(*, prefix=''):
    """
    Module 3 vault list scope for historical on-site beneficiaries.

    They skip intake archive / Module 2 handoff but still need a vault row with
    empty document slots until staff upload or scan files later.

    Pass prefix='applicant__' when filtering from related models (e.g. Blacklist).
    """
    from django.db.models import Q

    return Q(**{f'{prefix}application__notes__icontains': HISTORICAL_BACKFILL_NOTE}) | Q(
        **{f'{prefix}application__lot_awards__notes__icontains': HISTORICAL_BACKFILL_NOTE}
    )


def intake_registration_exclude_q(*, prefix=''):
    """
    Applicants who belong on Module 4 (housing units / GK Masterlist), not Module 1 ISF Registration.

    Covers historical GK backfill and any head beneficiary with an active lot award on site.
    Pass prefix='applicant__' when filtering from related models.
    """
    from django.db.models import Q

    p = prefix
    return document_vault_applicant_q(prefix=prefix) | Q(
        **{f'{p}application__lot_awards__status': 'active'}
    )


def applicant_excluded_from_intake_registration(applicant) -> bool:
    """True when the person should not appear on Module 1 ISF Registration."""
    if not applicant or not getattr(applicant, 'pk', None):
        return False
    return (
        Applicant.objects.filter(pk=applicant.pk)
        .filter(intake_registration_exclude_q())
        .exists()
    )

CSV_HEADERS = [
    'block',
    'lot',
    'last_name',
    'first_name',
    'middle_name',
    'sex',
    'beneficiary_year',
    'phone',
    'household_size',
    'displacement_reason',
]

CSV_TEMPLATE_ROW = {
    'block': '1',
    'lot': '5',
    'last_name': 'DELA CRUZ',
    'first_name': 'JUAN',
    'middle_name': 'SANTOS',
    'sex': 'M',
    'beneficiary_year': '2019',
    'phone': '09171234567',
    'household_size': '4',
    'displacement_reason': 'danger_zone',
}

_NAME_PART_RE = re.compile(r"^[A-Z\s'\-\.]+$")
_PHONE_RE = re.compile(r'^09\d{9}$')


def normalize_name_part(value: str, *, field_label: str, required: bool = False, max_len: int = 30) -> str:
    text = (value or '').strip().upper()
    if not text:
        if required:
            raise ValueError(f'{field_label} is required.')
        return ''
    if not _NAME_PART_RE.match(text):
        raise ValueError(f'{field_label} must contain letters only.')
    return text[:max_len]


def normalize_phone(value: str) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    digits = re.sub(r'\D', '', text)
    if not _PHONE_RE.match(digits):
        raise ValueError('Phone must be exactly 11 digits starting with 09 (e.g. 09171234567).')
    return digits


def normalize_whole_number(value: str, *, field_label: str, min_val: int = 1, max_val: int | None = None) -> str:
    text = (value or '').strip()
    if not text:
        raise ValueError(f'{field_label} is required.')
    if not text.isdigit():
        raise ValueError(f'{field_label} must be a whole number.')
    num = int(text)
    if num < min_val:
        raise ValueError(f'{field_label} must be at least {min_val}.')
    if max_val is not None and num > max_val:
        raise ValueError(f'{field_label} must be at most {max_val}.')
    return str(num)

VALID_DISPLACEMENT = frozenset({'', 'danger_zone', 'ejected', 'relocated', 'not_abc'})


def csv_template_text():
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_HEADERS, lineterminator='\r\n')
    writer.writeheader()
    writer.writerow(CSV_TEMPLATE_ROW)
    return buf.getvalue()


def parse_beneficiary_date(raw):
    """Parse YYYY or YYYY-MM-DD into timezone-aware datetime (noon local)."""
    text = (raw or '').strip()
    if not text:
        raise ValueError('beneficiary_year is required.')

    if len(text) == 4 and text.isdigit():
        year = int(text)
        if year < 1990 or year > timezone.localdate().year:
            raise ValueError(f'beneficiary_year {year} is out of range.')
        naive = datetime(year, 1, 1, 12, 0, 0)
        return timezone.make_aware(naive, timezone.get_current_timezone())

    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y'):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.year < 1990 or parsed.year > timezone.localdate().year:
                raise ValueError(f'beneficiary_year {parsed.year} is out of range.')
            naive = parsed.replace(hour=12, minute=0, second=0, microsecond=0)
            return timezone.make_aware(naive, timezone.get_current_timezone())
        except ValueError:
            continue
    raise ValueError(
        'beneficiary_year must be YYYY (e.g. 2019) or a date YYYY-MM-DD.'
    )


def _normalize_row(raw: dict) -> dict:
    return {key: (raw.get(key) or '').strip() for key in CSV_HEADERS}


def _parse_row_fields(row: dict) -> dict:
    row = _normalize_row(row)

    block = normalize_whole_number(row['block'], field_label='Block')
    lot = normalize_whole_number(row['lot'], field_label='Lot')
    last_name = normalize_name_part(row['last_name'], field_label='Last name', required=True, max_len=10)
    first_name = normalize_name_part(row['first_name'], field_label='First name', required=True, max_len=15)
    middle_name = normalize_name_part(row['middle_name'], field_label='Middle name', max_len=10)
    phone = normalize_phone(row['phone'])

    year_raw = row['beneficiary_year']
    if re.fullmatch(r'\d{4}', year_raw or ''):
        awarded_at = parse_beneficiary_date(year_raw)
    else:
        awarded_at = parse_beneficiary_date(year_raw)

    sex = row['sex'].upper()[:1] if row['sex'] else ''
    if sex and sex not in ('M', 'F'):
        raise ValueError('sex must be M, F, or blank.')

    displacement = row['displacement_reason'].lower()
    if displacement not in VALID_DISPLACEMENT:
        raise ValueError(
            'displacement_reason must be danger_zone, ejected, relocated, not_abc, or blank.'
        )

    try:
        household_size = int(row['household_size'] or '1')
    except ValueError as exc:
        raise ValueError('household_size must be a whole number.') from exc
    if not str(row['household_size'] or '1').isdigit():
        raise ValueError('household_size must be a whole number.')
    household_size = max(1, min(household_size, 20))

    return {
        **row,
        'block': block,
        'lot': lot,
        'last_name': last_name,
        'first_name': first_name,
        'middle_name': middle_name,
        'phone': phone,
        'sex': sex,
        'displacement_reason': displacement,
        'household_size': household_size,
        'awarded_at': awarded_at,
        'beneficiary_year': awarded_at.year,
    }


@transaction.atomic
def register_historical_beneficiary(*, site: RelocationSite, row: dict, user):
    """
    Create Applicant + Application + LotAward on an existing unit.

    Returns dict with created record ids and reference.
    """
    parsed = _parse_row_fields(row)

    unit = HousingUnit.objects.filter(
        site=site,
        block_number=parsed['block'],
        lot_number=parsed['lot'],
    ).first()
    if not unit:
        raise ValueError(
            f"Block {parsed['block']} Lot {parsed['lot']} does not exist at {site.name}. "
            'Add the unit in Housing Unit monitoring first.'
        )

    existing_award = LotAward.objects.filter(unit=unit, status='active').select_related(
        'application__applicant'
    ).first()
    if existing_award:
        occ = (
            existing_award.application.applicant.full_name
            if getattr(existing_award.application, 'applicant', None)
            else 'another beneficiary'
        )
        raise ValueError(
            f'Block {parsed["block"]} Lot {parsed["lot"]} already has an active award ({occ}).'
        )

    middle = parsed['middle_name']
    last_name = parsed['last_name']
    first_name = parsed['first_name']
    name_parts = [first_name, middle, last_name]
    full_name = ' '.join(p for p in name_parts if p).strip()[:30] or 'Beneficiary'

    barangay = site.barangay
    address = (site.address or site.name or 'Relocation site')[:500]

    applicant = Applicant(
        last_name=last_name,
        first_name=first_name,
        middle_name=middle,
        full_name=full_name,
        sex=parsed['sex'],
        phone_number=parsed['phone'][:20],
        barangay=barangay,
        current_address=address,
        monthly_income=Decimal('0.00'),
        household_size=parsed['household_size'],
        years_residing=0,
        channel='danger_zone',
        status='awarded',
        displacement_reason=parsed['displacement_reason'],
        registered_by=user,
    )
    applicant.save()
    Applicant.objects.filter(pk=applicant.pk).update(created_at=parsed['awarded_at'])

    application = Application.objects.create(
        applicant=applicant,
        status='awarded',
        form_generated_by=user,
        notes=HISTORICAL_BACKFILL_NOTE,
    )
    Application.objects.filter(pk=application.pk).update(
        form_generated_at=parsed['awarded_at'],
        created_at=parsed['awarded_at'],
    )

    award = LotAward.objects.create(
        application=application,
        unit=unit,
        status='active',
        awarded_at=parsed['awarded_at'],
        awarded_by=user,
        via_draw_lots=False,
        notes=f'{HISTORICAL_BACKFILL_NOTE} — beneficiary since {parsed["beneficiary_year"]}',
    )

    ConstructionProgress.objects.get_or_create(
        lot_award=award,
        defaults={
            'stage': 'not_started',
            'percent_complete': 0,
            'updated_by': user,
        },
    )

    unit.status = 'Occupied'
    unit.occupant_name = applicant.full_name
    unit.occupant_id = (applicant.reference_number or '')[:100] or None
    unit.save(update_fields=['status', 'occupant_name', 'occupant_id', 'updated_at'])

    return {
        'reference_number': applicant.reference_number,
        'full_name': applicant.full_name,
        'block': parsed['block'],
        'lot': parsed['lot'],
        'beneficiary_year': parsed['beneficiary_year'],
        'applicant_id': str(applicant.id),
        'application_id': str(application.id),
        'lot_award_id': str(award.id),
        'unit_id': str(unit.id),
    }


def import_historical_beneficiaries_csv(*, site: RelocationSite, uploaded_file, user):
    """
    Parse CSV and register each row. Collects per-line errors without stopping the file.
    """
    raw = uploaded_file.read()
    for encoding in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        raise ValueError('Could not read CSV file encoding.')

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError('CSV file is empty or missing a header row.')

    normalized_headers = [(h or '').strip().lower() for h in reader.fieldnames]
    missing = [h for h in CSV_HEADERS if h not in normalized_headers]
    if missing:
        raise ValueError(f'CSV missing columns: {", ".join(missing)}')

    header_map = {
        (name or '').strip().lower(): name
        for name in reader.fieldnames
    }

    created = []
    errors = []
    line_no = 1
    for raw_row in reader:
        line_no += 1
        if not any((v or '').strip() for v in raw_row.values()):
            continue
        row = {
            key: (raw_row.get(header_map.get(key, key)) or '').strip()
            for key in CSV_HEADERS
        }
        try:
            with transaction.atomic():
                result = register_historical_beneficiary(site=site, row=row, user=user)
            created.append(result)
        except Exception as exc:
            errors.append({'line': line_no, 'message': str(exc), 'row': row})

    return {
        'created_count': len(created),
        'error_count': len(errors),
        'created': created,
        'errors': errors,
    }
