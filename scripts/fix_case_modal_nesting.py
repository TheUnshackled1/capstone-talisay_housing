from pathlib import Path

p = Path(__file__).resolve().parents[1] / "templates/cases/case_management.html"
t = p.read_text(encoding="utf-8")

old = "            </div>\n\n        <!-- Modal Footer -->"
new = "            </div>\n\n        </motion>\n\n        <!-- Modal Footer -->"
new = "            </div>\n\n        </div>\n\n        <!-- Modal Footer -->"

if old not in t:
    raise SystemExit("marker not found")

t = t.replace(old, new, 1)

t = t.replace(
    'z-index: 1000; padding: 1rem; flex-direction: column;" onclick="closeNewCaseModal',
    'z-index: 1100; padding: 1rem; flex-direction: column;" onclick="closeNewCaseModal',
    1,
)
t = t.replace(
    '<button onclick="openNewCaseModal()" class="cases-add-btn"',
    '<button type="button" onclick="openNewCaseModal()" class="cases-add-btn"',
    1,
)

t = t.replace(
    """function openNewCaseModal() {
    document.getElementById('newCaseModal').style.display = 'flex';
}""",
    """function openNewCaseModal() {
    const caseModal = document.getElementById('caseModal');
    if (caseModal) caseModal.style.display = 'none';
    document.body.style.overflow = 'hidden';
    document.getElementById('newCaseModal').style.display = 'flex';
}""",
)

t = t.replace(
    """function closeNewCaseModal(e) {
    if (e && e.target.id !== 'newCaseModal') return;
    document.getElementById('newCaseModal').style.display = 'none';
}""",
    """function closeNewCaseModal(e) {
    if (e && e.target.id !== 'newCaseModal') return;
    document.getElementById('newCaseModal').style.display = 'none';
    document.body.style.overflow = '';
}""",
)

t = t.replace(
    """function closeCaseModal(e) {
    if (e && e.target.id !== 'caseModal') return;
    document.getElementById('caseModal').style.display = 'none';
}""",
    """function closeCaseModal(e) {
    if (e && e.target.id !== 'caseModal') return;
    document.getElementById('caseModal').style.display = 'none';
    document.body.style.overflow = '';
}""",
)

t = t.replace(
    """function openCaseModal(caseId) {
    currentCaseId = caseId;
    resetCaseModalSections();""",
    """function openCaseModal(caseId) {
    currentCaseId = caseId;
    document.getElementById('newCaseModal').style.display = 'none';
    resetCaseModalSections();
    document.body.style.overflow = 'hidden';""",
)

p.write_text(t, encoding="utf-8")
print("Fixed", p)
