"""Move case management templates into accounts/second_member and accounts/field."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
staff_src = ROOT / "templates/cases/case_management_second_member.html"
staff_dst = ROOT / "templates/accounts/second_member/case_management.html"
field_dst = ROOT / "templates/accounts/field/case_management.html"

staff = staff_src.read_text(encoding="utf-8")
if staff.lstrip().startswith("{# Legacy"):
    staff = staff.split("\n", 1)[1]

staff_dst.parent.mkdir(parents=True, exist_ok=True)
staff_dst.write_text(staff, encoding="utf-8")

field = staff.replace("{% extends 'staff_base.html' %}", "{% extends 'field_base.html' %}", 1)
field = field.replace(
    "Every complaint gets a case record · No verbal-only handling",
    "Caretaker on-site recording · Search beneficiary, upload evidence · Desk reviews",
    1,
)
banner = (
    '    <p style="text-align:center;margin:0 0 0.75rem;font-size:0.72rem;'
    'font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#64748b;">'
    "▸ Ronda / caretaker — field recording</p>\n"
)
needle = (
    '<p class="monitoring-subtitle">Caretaker on-site recording · '
    "Search beneficiary, upload evidence · Desk reviews</p>\n</div>"
)
field = field.replace(needle, needle.replace("</div>", "\n" + banner + "</motion>"), 1)
field = field.replace("</motion>", "</div>", 1)

field = field.replace('id="newReceivedAt" value="office"', 'id="newReceivedAt" value="onsite"', 1)
field = field.replace(
    '<h3 class="tha-section-title">Uploaded evidence</h3>',
    '<h3 class="tha-section-title">On-site evidence</h3>\n'
    '                        <p class="help-text" style="margin-bottom: 0.5rem;">'
    "Photo or PDF from on-site report (max 6 MB each).</p>",
    1,
)
field = field.replace(
    "const CASE_POSITION = 'second_member';",
    "const CASE_POSITION = '{{ case_position }}';",
    1,
)

field_dst.write_text(field, encoding="utf-8")
print(f"Wrote {staff_dst} ({len(staff)} bytes)")
print(f"Wrote {field_dst} ({len(field)} bytes)")
