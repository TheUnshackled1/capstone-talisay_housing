# Intake Applicants Proceed + SMS Flow Map

This is a one-screen debug map for:
- `/intake/staff/<position>/applicants/`
- Proceed actions
- Current SMS behavior (console-only tracing, SMS disabled in these flows)

## End-to-End Chain (Proceed Actions)

1. Intake applicants page actions (frontend):
   - `templates/intake/staff/applicants.html`
   - Buttons and handlers:
     - `Proceed to LIST OF APPLICANTS` -> `proceedToArchive(...)`
     - `Proceed to Application & Eligibility` -> `proceedToEvaluationFromArchiveRequirements()`

2. Shared backend endpoint:
   - `intake/urls.py`
   - `path('staff/<str:position>/proceed-to-applications/', views.proceed_to_applications, name='proceed_to_applications')`

3. Backend handoff/archive logic:
   - `intake/views.py` -> `proceed_to_applications(request, position)`
   - Behavior:
     - Archives applicant via `Archive.get_or_create(...)`
     - If `promote_to_module2=1`, sets:
       - `applicant.module2_handoff_at`
       - `applicant.module2_handoff_by`
   - Returns JSON success message

4. Promotion flag difference:
   - `proceedToArchive(...)` -> no `promote_to_module2` (archive/list path)
   - `proceedToEvaluationFromArchiveRequirements()` -> sends `promote_to_module2=1` (Module 2 handoff path)

## Current SMS Behavior (Important)

- Both proceed flows call `intake:proceed_to_applications`.
- `proceed_to_applications` currently does **not** call SMS send logic.
- Therefore:
  - Proceed to LIST OF APPLICANTS -> no SMS sent
  - Proceed to Application & Eligibility -> no SMS sent

## Console Tracing (Current Prep)

- `templates/intake/staff/applicants.html` includes:
  - `logSmsDispatchPlan(flowName, details)`
- This logs:
  - flow name
  - endpoint
  - `provider: 'Semaphore'`
  - `providerReady: false`
  - `smsActive: false`
- This is console-only preparation for future SMS integration.

## Related Deadline Flow

1. Frontend:
   - `setDocumentDeadline()` in `templates/intake/staff/applicants.html`
   - Sends `action=set_doc_deadline` to `intake:update_eligibility`

2. Backend:
   - `intake/views.py` -> `update_eligibility(...)`
   - `if action == 'set_doc_deadline': ...`
   - Contains:
     - `# TODO: Send SMS notification to applicant with deadline`

3. Current result:
   - Deadline is saved and status changes to `requirements`
   - No SMS is sent yet

## Quick Debug Playbook

1. Click proceed button and inspect browser console:
   - Confirm `[Intake SMS Plan]` log appears with expected flow and flags.

2. Verify network call:
   - `POST /intake/staff/<position>/proceed-to-applications/`
   - Check JSON `success`.

3. Verify backend state:
   - `Archive` row created/exists.
   - For Module 2 route, `module2_handoff_at/by` are set.

4. If expecting SMS:
   - Confirm current code path has no send call in `proceed_to_applications`.
   - For deadline action, confirm TODO remains unimplemented.

