"""Generate case_management_ronda.html and case_management_second_member.html from shared template."""
from pathlib import Path

src = Path("templates/cases/case_management.html").read_text(encoding="utf-8")

ronda_banner = (
    '        <p style="text-align:center;margin:0 0 0.75rem;font-size:0.72rem;'
    'font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#64748b;">'
    "▸ Ronda / caretaker — field recording</p>\n"
)
ronda_evidence_help = (
    '                        <p class="help-text" style="margin-bottom: 0.5rem;">'
    "Photo or PDF from on-site report (max 6 MB each).</p>\n"
)

ronda = src
ronda = ronda.replace(
    "{% extends base_template|default:'staff_base.html' %}",
    "{% extends 'field_base.html' %}",
)
ronda = ronda.replace(
    "{% if is_ronda %}Caretaker on-site recording · Search beneficiary, upload evidence · Desk reviews{% else %}Every complaint gets a case record · No verbal-only handling{% endif %}",
    "Caretaker on-site recording · Search beneficiary, upload evidence · Desk reviews",
)
old_banner = (
    "        {% if is_ronda %}\n"
    '        <p style="text-align:center;margin:0 0 0.75rem;font-size:0.72rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#64748b;">▸ Ronda / caretaker — field recording</p>\n'
    "        {% endif %}\n"
)
ronda = ronda.replace(old_banner, ronda_banner)
ronda = ronda.replace(
    'value="{% if is_field_desk %}onsite{% else %}office{% endif %}"',
    'value="onsite"',
)
ronda = ronda.replace(
    "{% if is_ronda %}On-site evidence{% else %}Uploaded evidence{% endif %}",
    "On-site evidence",
)
ronda = ronda.replace(
    '                        {% if is_ronda %}<p class="help-text" style="margin-bottom: 0.5rem;">Photo or PDF from on-site report (max 6 MB each).</p>{% endif %}\n',
    ronda_evidence_help,
)
ronda = ronda.replace(
    "const CASE_POSITION = '{{ request.user.position }}';",
    "const CASE_POSITION = 'ronda';",
)

staff = src
staff = staff.replace(
    "{% extends base_template|default:'staff_base.html' %}",
    "{% extends 'staff_base.html' %}",
)
staff = staff.replace(
    "{% if is_ronda %}Caretaker on-site recording · Search beneficiary, upload evidence · Desk reviews{% else %}Every complaint gets a case record · No verbal-only handling{% endif %}",
    "Every complaint gets a case record · No verbal-only handling",
)
staff = staff.replace(old_banner, "")
staff = staff.replace(
    'value="{% if is_field_desk %}onsite{% else %}office{% endif %}"',
    'value="office"',
)
staff = staff.replace(
    "{% if is_ronda %}On-site evidence{% else %}Uploaded evidence{% endif %}",
    "Uploaded evidence",
)
staff = staff.replace(
    '                        {% if is_ronda %}<p class="help-text" style="margin-bottom: 0.5rem;">Photo or PDF from on-site report (max 6 MB each).</p>{% endif %}\n',
    "",
)
staff = staff.replace(
    "const CASE_POSITION = '{{ request.user.position }}';",
    "const CASE_POSITION = 'second_member';",
)

Path("templates/accounts/field/case_management.html").write_text(ronda, encoding="utf-8")
Path("templates/accounts/second_member/case_management.html").write_text(staff, encoding="utf-8")
print("OK: field", len(ronda), "bytes; second_member", len(staff), "bytes")
