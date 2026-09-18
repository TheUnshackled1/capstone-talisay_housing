# IHSMS Entity Relationship Diagram

Codebase-accurate ERD from the Django models in `accounts`, `intake`, `applications`, `documents`, `units`, and `cases`.  
Generated from current `models.py` definitions (38 managed models). `dashboard` has no models.

**Draw.io (editable):** open [ERD.drawio](ERD.drawio) in [diagrams.net](https://app.diagrams.net/) or the VS Code/Cursor Draw.io extension.  
Pages: System Overview · Intake · Applications + Documents · Units · Cases.

**Cardinality legend (Crow’s foot):**

| Symbol | Meaning |
|--------|---------|
| `\|\|--\|\|` | Exactly one ↔ exactly one |
| `\|\|--o\|` | One ↔ zero-or-one |
| `\|\|--o{` | One ↔ zero-or-many |
| `}o--o\|` | Zero-or-many ↔ zero-or-one |
| `}o--\|\|` | Zero-or-many ↔ exactly one |

---

## 1. System overview

Hub entity: **`intake.Applicant`**. Staff actions hang off **`accounts.User`**. Housing awards bridge **`Application`** ↔ **`HousingUnit`** via **`LotAward`**. Formal cases live in **`cases.Case`**.

> Draw.io page: **1. System Overview** in [ERD.drawio](ERD.drawio)

```mermaid
erDiagram
  User ||--o{ Applicant : "registers / reviews"
  Barangay ||--o{ Applicant : "resides_in"
  Applicant ||--o| Application : "has"
  Applicant ||--o| CDRRMOCertification : "certifies"
  Applicant ||--o| Blacklist : "may_have"
  Applicant ||--o{ HouseholdMember : "includes"
  Applicant ||--o{ Document : "uploads"
  Applicant ||--o{ QueueEntry : "queues"
  Application ||--o| LotAwarding : "ceremony"
  Application ||--o{ LotAward : "awards"
  RelocationSite ||--o{ HousingUnit : "contains"
  Barangay ||--o{ RelocationSite : "locates"
  HousingUnit ||--o{ LotAward : "occupied_by"
  LotAward ||--o| ConstructionProgress : "tracks"
  Case }o--o| Applicant : "complainant_or_subject"
  Case }o--o| HousingUnit : "related_unit"
  Case ||--o{ CaseAction : "actions"
  Case ||--o{ CaseEvidence : "evidence"
  User {
    bigint id PK
    string username UK
    string position
    string phone
  }
  Barangay {
    bigint id PK
    string name UK
  }
  Applicant {
    uuid id PK
    string reference_number UK
    string full_name
    string status
  }
  Application {
    uuid id PK
    string application_number UK
    string status
  }
  CDRRMOCertification {
    uuid id PK
    string status
  }
  Blacklist {
    uuid id PK
    string reason
  }
  HouseholdMember {
    uuid id PK
    string full_name
  }
  Document {
    uuid id PK
    string document_type
  }
  QueueEntry {
    uuid id PK
    string queue_type
    int position
  }
  LotAwarding {
    uuid id PK
    string lot_number
  }
  RelocationSite {
    uuid id PK
    string name UK
    string code UK
  }
  HousingUnit {
    uuid id PK
    string block_number
    string lot_number
    string status
  }
  LotAward {
    uuid id PK
    string status
  }
  ConstructionProgress {
    uuid id PK
    string stage
  }
  Case {
    uuid id PK
    string case_number UK
    string case_type
    string status
  }
  CaseAction {
    uuid id PK
    string action_type
  }
  CaseEvidence {
    uuid id PK
  }
```

---

## 2. Intake module (`intake`)

Models: `Barangay`, `Applicant`, `HouseholdMember`, `Archive`, `SMSLog`.

> Draw.io page: **2. Intake** in [ERD.drawio](ERD.drawio)
```mermaid
erDiagram
  User ||--o{ Applicant : "registered_by"
  User ||--o{ Applicant : "eligibility_checked_by"
  User ||--o{ Applicant : "module2_handoff_by"
  User ||--o{ Applicant : "form_queue_routed_by"
  User ||--o{ Applicant : "evaluation_approval_by"
  User ||--o{ Archive : "archived_by"
  Barangay ||--o{ Applicant : "barangay"
  Applicant ||--o{ HouseholdMember : "household_members"
  Applicant ||--o{ Archive : "archives"
  Applicant ||--o{ SMSLog : "sms_logs"

  User {
    bigint id PK
    string username UK
    string position
  }
  Barangay {
    bigint id PK
    string name UK
    bool is_active
  }
  Applicant {
    uuid id PK
    string reference_number UK
    string last_name
    string first_name
    string full_name
    string status
    string channel
    decimal monthly_income
    int household_size
    int years_residing
  }
  HouseholdMember {
    uuid id PK
    uuid applicant_id FK
    string full_name
    string relationship
    int age
  }
  Archive {
    uuid id PK
    uuid applicant_id FK
    string reference_number_snapshot
    string full_name_snapshot
    string channel
    bool is_restored
    bool formally_archived
  }
  SMSLog {
    uuid id PK
    uuid applicant_id FK
    string recipient_phone
    string trigger_event
    string status
  }
```

**Notes**

- `Applicant.barangay` uses `PROTECT` (barangay cannot be deleted while referenced).
- Check constraint: `years_residing <= 99`.

---

## 3. Applications + Documents

**Applications:** `Application`, `QueueEntry`, `CDRRMOCertification`, `FieldVerificationPhoto`, `EligibilityCheckDecision`, `SMSLog`.  
**Documents:** `Document`, `DocumentBlob`, `Requirement`, `RequirementSubmission`, `LotAwarding`.

Skip unmanaged `CDRRMOCertificationProxy` (same physical table as `CDRRMOCertification`).

> Draw.io page: **3. Applications + Documents** in [ERD.drawio](ERD.drawio)
```mermaid
erDiagram
  Applicant ||--o| Application : "application"
  Applicant ||--o| CDRRMOCertification : "cdrrmo_certification"
  Applicant ||--o{ QueueEntry : "queue_entries"
  Applicant ||--o{ EligibilityCheckDecision : "eligibility_check_decisions"
  Applicant ||--o{ Document : "documents"
  Applicant ||--o{ RequirementSubmission : "requirement_submissions"
  Applicant ||--o{ ApplicationsSMSLog : "applications_sms_logs"
  User ||--o{ Application : "form_generated_by"
  User ||--o{ QueueEntry : "added_by"
  User ||--o{ CDRRMOCertification : "requested_by"
  User ||--o{ CDRRMOCertification : "result_recorded_by"
  User ||--o{ FieldVerificationPhoto : "uploaded_by"
  User ||--o{ EligibilityCheckDecision : "reviewed_by"
  User ||--o{ Document : "uploaded_by"
  User ||--o{ RequirementSubmission : "verified_by"
  User ||--o{ LotAwarding : "awarded_by"
  CDRRMOCertification ||--o{ FieldVerificationPhoto : "field_photos"
  Requirement ||--o{ RequirementSubmission : "submissions"
  RequirementSubmission ||--o{ Document : "documents"
  Document ||--o| DocumentBlob : "blob_record"
  Application ||--o| LotAwarding : "lot_awarding"

  Applicant {
    uuid id PK
    string reference_number UK
  }
  Application {
    uuid id PK
    string application_number UK
    string status
    int standby_position
  }
  QueueEntry {
    uuid id PK
    string queue_type
    int position
    string status
  }
  CDRRMOCertification {
    uuid id PK
    string status
    string disposition_source
  }
  FieldVerificationPhoto {
    uuid id PK
    uuid certification_id FK
  }
  EligibilityCheckDecision {
    uuid id PK
    string check_key
    string status
  }
  ApplicationsSMSLog {
    uuid id PK
    string trigger_event
    string status
  }
  Requirement {
    string code PK
    string name
    string group
    string vault_document_type
  }
  RequirementSubmission {
    uuid id PK
    string status
  }
  Document {
    uuid id PK
    string document_type
    string file_name
  }
  DocumentBlob {
    bigint id PK
    uuid document_id FK
  }
  LotAwarding {
    uuid id PK
    string lot_number
    string block_number
    string site_name
    bool contract_signed
  }
  User {
    bigint id PK
  }
```

**Notes**

- Unique `(applicant, check_key)` on `EligibilityCheckDecision`.
- Unique active `(queue_type, position)` on `QueueEntry`.
- Unique `(applicant, requirement)` on `RequirementSubmission`.
- Legacy tables: `Requirement` → `applications_requirement`; `RequirementSubmission` → `applications_requirementsubmission`.
- `LotAwarding` is the **ceremony / contract** 1:1 record on an application — distinct from `units.LotAward`.

---

## 4. Units module (`units`)

Housing inventory, lot awards, construction, occupancy monitoring, blacklist, and **legacy** case records.

> Draw.io page: **4. Units** in [ERD.drawio](ERD.drawio)
```mermaid
erDiagram
  Barangay ||--o{ RelocationSite : "barangay"
  User ||--o{ RelocationSite : "caretaker"
  RelocationSite ||--o{ HousingUnit : "units"
  Application ||--o{ LotAward : "lot_awards"
  HousingUnit ||--o{ LotAward : "lot_awards"
  User ||--o{ LotAward : "awarded_by"
  User ||--o{ LotAward : "authenticated_by"
  LotAward ||--o{ LotAwardDocumentValidation : "document_validations"
  LotAward ||--o| ConstructionProgress : "construction_progress"
  ConstructionProgress ||--o{ ConstructionProgressUpdate : "updates"
  Applicant ||--o| Blacklist : "blacklist_record"
  LotAward ||--o{ Blacklist : "blacklist_records"
  HousingUnit ||--o{ Blacklist : "blacklist_records"
  LotAward ||--o{ OccupancyMonitoringCycle : "monitoring_cycles"
  LotAward ||--o{ MonitoringTask : "monitoring_tasks"
  HousingUnit ||--o{ MonitoringTask : "monitoring_tasks"
  MonitoringTask ||--o{ MonitoringReport : "reports"
  LotAward ||--o{ MonitoringReport : "monitoring_reports"
  HousingUnit ||--o{ MonitoringReport : "monitoring_reports"
  MonitoringReport ||--o{ MonitoringReportPhoto : "photos"
  LotAward ||--o{ ExplanationReview : "explanation_reviews"
  HousingUnit ||--o{ ExplanationReview : "explanation_reviews"
  MonitoringReport ||--o{ ExplanationReview : "triggered_explanations"
  LotAward ||--o{ ExtensionRecord : "extensions"
  ExplanationReview ||--o{ ExtensionRecord : "extension_record"
  RelocationSite ||--o{ CaseRecord : "cases"
  CaseRecord ||--o{ CaseUpdate : "updates"
  Applicant ||--o{ UnitsSMSLog : "units_sms_logs"

  RelocationSite {
    uuid id PK
    string name UK
    string code UK
    int total_lots
  }
  HousingUnit {
    uuid id PK
    string block_number
    string lot_number
    string status
    int plan_polygon_index
  }
  LotAward {
    uuid id PK
    string status
    bool via_draw_lots
  }
  LotAwardDocumentValidation {
    uuid id PK
  }
  ConstructionProgress {
    uuid id PK
    string stage
    int percent_complete
  }
  ConstructionProgressUpdate {
    uuid id PK
    string stage
    date visit_date
  }
  Blacklist {
    uuid id PK
    string reason
  }
  OccupancyMonitoringCycle {
    uuid id PK
    string cycle_stage
  }
  MonitoringTask {
    uuid id PK
    string task_type
    string status
    date due_date
  }
  MonitoringReport {
    uuid id PK
    string occupancy_status
    string construction_status
  }
  MonitoringReportPhoto {
    uuid id PK
  }
  ExplanationReview {
    uuid id PK
    string review_status
    string trigger_kind
  }
  ExtensionRecord {
    uuid id PK
    int extension_duration_months
  }
  CaseRecord {
    uuid id PK
    string case_number UK
    string complaint_type
    string status
  }
  CaseUpdate {
    uuid id PK
  }
  UnitsSMSLog {
    uuid id PK
    string status
  }
  Application {
    uuid id PK
  }
  Applicant {
    uuid id PK
  }
  Barangay {
    bigint id PK
  }
  User {
    bigint id PK
  }
```

**Notes**

- Unique `(site, block_number, lot_number)` per housing unit.
- Unique `(site, plan_polygon_index)` when polygon index is set (lot-plan map overlay).
- `units.CaseRecord` / `CaseUpdate` are the **legacy** site-centric case tables; prefer `cases.Case` for new work.

---

## 5. Cases module (`cases`)

Formal case management (current workflow).

> Draw.io page: **5. Cases** in [ERD.drawio](ERD.drawio)
```mermaid
erDiagram
  CaseYearSequence {
    bigint id PK
    int year UK
    int last_number
  }
  User ||--o{ Case : "received_by"
  User ||--o{ Case : "investigated_by"
  User ||--o{ Case : "decided_by"
  User ||--o{ Case : "monitored_by"
  User ||--o{ CaseAction : "created_by"
  User ||--o{ CaseEvidence : "uploaded_by"
  User ||--o{ FieldSettledIncidentLog : "logged_by"
  Applicant ||--o{ Case : "cases_filed"
  Applicant ||--o{ Case : "cases_against"
  HousingUnit ||--o{ Case : "cases"
  Case ||--o{ CaseAction : "actions"
  Case ||--o{ CaseEvidence : "evidence"
  HousingUnit ||--o{ FieldSettledIncidentLog : "settled_incident_logs"
  Applicant ||--o{ FieldSettledIncidentLog : "as_complainant"
  Applicant ||--o{ FieldSettledIncidentLog : "as_subject"

  Case {
    uuid id PK
    string case_number UK
    string case_type
    string status
    string complainant_name
  }
  CaseAction {
    uuid id PK
    string action_type
  }
  CaseEvidence {
    uuid id PK
    string caption
  }
  FieldSettledIncidentLog {
    uuid id PK
    string case_type
    string description
  }
  Applicant {
    uuid id PK
  }
  HousingUnit {
    uuid id PK
  }
  User {
    bigint id PK
  }
```

**Notes**

- `CaseYearSequence` supports yearly case-number allocation (`year` unique).
- `FieldSettledIncidentLog` records field-settled incidents **without** creating a formal `Case`.
- Complainant / subject / unit FKs on `Case` are optional (`SET_NULL`).

---

## 6. Schema gotchas

| Topic | Detail |
|-------|--------|
| **Hub** | `intake.Applicant` is the central beneficiary record. |
| **Two lot concepts** | `documents.LotAwarding` = 1:1 ceremony/contract on `Application`. `units.LotAward` = N awards linking `Application` ↔ `HousingUnit`. |
| **Two case systems** | `units.CaseRecord` (+ `CaseUpdate`) = legacy. `cases.Case` (+ actions/evidence) = current formal workflow. |
| **Three SMSLog tables** | `intake.SMSLog`, `applications.SMSLog`, `units.SMSLog` — same shape, separate tables / related names. |
| **Primary keys** | Most entities: UUID. Exceptions: `User` (bigint), `Barangay`, `CaseYearSequence`, `DocumentBlob` (implicit bigint), `Requirement.code` (string PK). |
| **No custom M2M** | Only inherited `User.groups` / `User.user_permissions` from Django auth. |
| **Unmanaged** | `CDRRMOCertificationProxy` maps to `applications_cdrrmocertification` — do not treat as a second entity. |
| **Staff FKs** | Many `User` FKs use `SET_NULL` so staff deletion does not cascade-delete domain data. |

---

## 7. Model checklist (38 managed)

| App | Models |
|-----|--------|
| **accounts** (1) | `User` |
| **intake** (5) | `SMSLog`, `Barangay`, `Applicant`, `HouseholdMember`, `Archive` |
| **applications** (6) | `Application`, `SMSLog`, `EligibilityCheckDecision`, `QueueEntry`, `CDRRMOCertification`, `FieldVerificationPhoto` |
| **documents** (5) | `Document`, `DocumentBlob`, `Requirement`, `RequirementSubmission`, `LotAwarding` |
| **units** (16) | `RelocationSite`, `HousingUnit`, `LotAward`, `LotAwardDocumentValidation`, `ConstructionProgress`, `ConstructionProgressUpdate`, `Blacklist`, `CaseRecord`, `CaseUpdate`, `SMSLog`, `OccupancyMonitoringCycle`, `MonitoringTask`, `MonitoringReport`, `MonitoringReportPhoto`, `ExplanationReview`, `ExtensionRecord` |
| **cases** (5) | `CaseYearSequence`, `Case`, `CaseAction`, `CaseEvidence`, `FieldSettledIncidentLog` |
| **dashboard** (0) | — |
