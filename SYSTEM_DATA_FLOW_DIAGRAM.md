# IHSMS SYSTEM-WIDE DATA FLOW DIAGRAM
## Talisay City Housing Authority - Complete Data Architecture

---

## LEVEL 1: COMPLETE SYSTEM OVERVIEW

```
╔════════════════════════════════════════════════════════════════════════════════════════╗
║                           IHSMS DATA ECOSYSTEM                                         ║
║                                                                                        ║
║  ENTRY POINTS              PROCESSING          STORAGE              OUTPUT             ║
║  ───────────────            ──────────         ─────────            ──────             ║
║  • Landowner Web            Module 1-6         48 Django       Analytics Dashboard     ║
║  • Walk-in Forms             Processes         Models          (Module 6)              ║
║  • CDRRMO Direct                               in 7 Apps            │                  ║
║    (phone→staff)                               PostgreSQL           ├─ HEADboard      ║
║                                                                      ├─ OIC reports    ║
║  USERS (11 positions)                                               ├─ Field summary  ║
║  ──────────────────                                                 └─ Caretaker view ║
║  • Jay (M1-M3)                                                                         ║
║  • Joiel (M2, M4)                         AUDIT TRAIL                                  ║
║  • Arthur HEAD (M6)                       ───────────                                  ║
║  • Victor OIC (M2, M4, M5)                SMS Logs                                     ║
║  • Jocel (M1-M4)                          Edit Audits                                  ║
║  • Nonoy, Paul, Roberto                   Case Notes                                   ║
║  • Laarni, Rona                           Activity Logs                                ║
║  • On-site Caretaker                                                                   ║
║  • Field Team (multiple)                                                               ║
║                                                                                        ║
╚════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## LEVEL 2: DATA ENTRY CHANNELS & INITIAL INTAKE

### CHANNEL A: LANDOWNER WEB PORTAL
```
┌─────────────────────────────────────────┐
│ Landowner opens system                   │
│ Enters: ISF names, household size,       │
│         income, barangay, years residing │
└──────────────────────────┬────────────────┘
                           ↓
                  ┌────────────────┐
                  │ System creates │
                  │ for EACH ISF:  │
                  └────────┬───────┘
                           ↓
        ┌──────────────────────────────────┐
        │ LandownerSubmission (1 record)   │
        │  ├─ reference_number: AUTO       │
        │  ├─ landowner_name               │
        │  ├─ property_address             │
        │  └─ submitted_at: NOW            │
        └──────┬──────────────────────────┘
               ↓
        (Contains 1+ ISF records)
               ↓
        ┌──────────────────────────────────┐
        │ ISFRecord (1 per ISF) - CREATED  │
        │  ├─ reference_number: ISF-2026-X │
        │  ├─ full_name                    │
        │  ├─ household_members            │
        │  ├─ monthly_income               │
        │  ├─ years_residing               │
        │  ├─ barangay                     │
        │  └─ status: "Entry-Pending"      │
        └──────┬──────────────────────────┘
               ↓
      (M1: Eligibility Check - Auto)
               ↓
        ┌──────────────────────────────────┐
        │ Blacklist Check                  │
        │  ├─ Query: IS applicant in       │     
        │  │           blacklist?          │
        │  ├─ YES → disqualified           │
        │  └─ NO  → proceed to verify      │
        └──────┬──────────────────────────┘
               ↓ (if eligible)
        ┌──────────────────────────────────┐
        │ Applicant Created (Convert)      │
        │  ├─ from: ISFRecord              │
        │  ├─ channel: "landowner"         │
        │  ├─ status: "Eligible"           │
        │  ├─ doc_1-7: false (pending)     │
        │  └─ SMS sent: "Reference: XXX"   │
        └──────┬──────────────────────────┘
               ↓
        ┌──────────────────────────────────┐
        │ QueueEntry Created               │
        │  ├─ queue_type: "walk-in-fifo"   │
        │  ├─ position: auto-assigned      │
        │  ├─ status: "active"             │
        │  └─ entered_at: NOW              │
        └──────────────────────────────────┘
```

### CHANNEL B: WALK-IN DANGER ZONE
```
┌─────────────────────────────────────────┐
│ Applicant walks into office              │
│ Says: "I live in flood-prone area"       │
└──────────────────────────┬────────────────┘
                           ↓
                   (JOCEL RECORDS)
                           ↓
        ┌──────────────────────────────────┐
        │ Applicant Created                │
        │  ├─ channel: "walk-in-danger"    │
        │  ├─ danger_zone_type: [type]     │
        │  ├─ danger_zone_location: [loc]  │
        │  └─ status: "Pending-CDRRMO"     │
        └──────┬──────────────────────────┘
               ↓
        ┌──────────────────────────────────┐
        │ CDRRMOCertification Created      │
        │  ├─ status: "requested"          │
        │  ├─ declared_location: [loc]     │
        │  ├─ requested_at: NOW            │
        │  └─ requested_by: JOCEL          │
        └──────┬──────────────────────────┘
               ↓
      (CDRRMO VISITS LOCATION - Outside System)
               ↓
        (JOCEL UPDATES CDRRMO RESULT)
               ↓
        ┌──────────────────────────────────┐
        │ CDRRMOCertification Updated      │
        │  ├─ status: "certified" OR       │
        │  │          "not_certified"      │
        │  ├─ certified_at: NOW            │
        │  └─ result_recorded_by: JOCEL    │
        └──────┬──────────────────────────┘
               ├─ YES (Certified) ──────────┐
               │                            ↓
               │        ┌──────────────────────────┐
               │        │ QueueEntry Created       │
               │        │  ├─ queue_type: "priority"
               │        │  ├─ position: 1 (TOP!)   │
               │        │  ├─ SMS: "Priority List" │
               │        │  └─ status: "active"     │
               │        └──────────────────────────┘
               │
               └─ NO (Not Certified) ──────┐
                                           ↓
                       ┌──────────────────────────┐
                       │ QueueEntry Created       │
                       │  ├─ queue_type: "walk-in"
                       │  ├─ position: auto-assign │
                       │  ├─ SMS: "Queue #X"      │
                       │  └─ status: "active"     │
                       └──────────────────────────┘
```

### CHANNEL C: WALK-IN REGULAR (FIFO)
```
┌─────────────────────────────────────────┐
│ Applicant walks in (no danger zone)      │
└──────────────────────────┬────────────────┘
                           ↓
                   (JOCEL RECORDS)
                           ↓
        ┌──────────────────────────────────┐
        │ Applicant Created                │
        │  ├─ channel: "walk-in"           │
        │  ├─ status: "Eligible" (auto)    │
        │  └─ SMS: "Reference: XXX"        │
        └──────┬──────────────────────────┘
               ↓
        ┌──────────────────────────────────┐
        │ QueueEntry Created               │
        │  ├─ queue_type: "walk-in-fifo"   │
        │  ├─ position: auto-assign        │
        │  ├─ status: "active"             │
        │  └─ SMS: "Queue #X"              │
        └──────────────────────────────────┘
```

---

## LEVEL 3: DATA PROCESSING MODULES (M1-M6)

### MODULE 1: INTAKE VERIFICATION (Jay)
```
INPUT: Applicant with status "Eligible"
    ↓
    ├─ M1P1: Auto Blacklist Check ────┐
    │         (on entry)               │
    │                                  └─ YES → Disqualify
    │                                     NO  → Continue
    ├─ M1P2: Document Collection        ↓
    │         (7 Group A docs)      ┌────────────────────┐
    │                               │  Document Model    │
    │  REQUIRED DOCUMENTS:          │  ├─ applicant     │
    │  1. Valid ID                  │  ├─ document_type │
    │  2. Marriage Cert (if applicable) ├─ file      │
    │  3. Birth Certificate         │  ├─ uploaded_at   │
    │  4. Income Proof              │  ├─ uploaded_by   │
    │  5. Barangay Clearance        │  └─ notes         │
    │  6. Tax ID (if any)           └────────────────────┘
    │  7. Residence Proof
    │
    ├─ Document Status Tracking:
    │  RequirementSubmission (1 per doc)
    │  ├─ requirement: FK → Requirement (1-7)
    │  ├─ status: "pending" → "submitted" → "verified"
    │  ├─ submitted_at: timestamp
    │  ├─ verified_at: timestamp
    │  └─ rejection_reason: (if rejected)
    │
    └─ Once all 7 verified → Module 2
```

**Data Flow**: `Applicant` → `RequirementSubmission (7x)` → `Document (1-7 files)`

### MODULE 2: APPLICATION PROCESSING (Jay → OIC → Head)
```
INPUT: Applicant with ALL 7 Group A documents verified

M2 GATE: Document Completeness Check
    ├─ IF any document NOT verified
    │  └─ BLOCK: Applicant in "Pending" status
    │
    └─ IF all 7 verified
       └─ PROCEED to application form generation

    ↓
┌─────────────────────────────────────────────┐
│ Application Form Generated (JAY creates)     │
│                                              │
│ Application Model Created:                   │
│  ├─ applicant: FK → Applicant                │
│  ├─ application_number: "2026-0001"          │
│  ├─ status: "form_generated"                 │
│  ├─ form_generated_at: NOW                   │
│  ├─ form_generated_by: JAY                   │
│  └─ [copy from Applicant]                    │
│      ├─ full_name                            │
│      ├─ date_of_birth                        │
│      ├─ household_size                       │
│      ├─ monthly_income                       │
│      └─ barangay                             │
│                                              │
│ HouseholdMember Records Created:             │
│  ├─ For EACH family member                   │
│  ├─ applicant: FK → Applicant                │
│  ├─ full_name                                │
│  ├─ relationship, DOB, sex, etc.             │
│  └─ [Only registered members can reside]     │
└─────────────────┬──────────────────────────┘
                  ↓
         (APPLICATION SIGNED BY APPLICANT)
                  ↓
        ┌──────────────────────────┐
        │ Applicant Signs Form     │
        │ ├─ applicant_signed_at   │
        │ │  = NOW                 │
        │ └─ status: "signed"      │
        └──────┬───────────────────┘
               ↓
      (NOTARIZATION - Outside System)
               ↓
        ┌──────────────────────────┐
        │ Notarization Marked      │
        │ ├─ notarial_completed    │
        │ │  = TRUE                │
        │ ├─ notarial_completed_at │
        │ │  = Date uploaded       │
        │ └─ status: "notarized"   │
        └──────┬───────────────────┘
               ↓
      (ENGINEERING ASSESSMENT)
               ↓
        ┌──────────────────────────────────┐
        │ FacilitatedService Record        │
        │ ├─ application: FK                │
        │ ├─ service_type: "engineering"   │
        │ ├─ status: "initiated"           │
        │ ├─ initiated_at: NOW             │
        │ ├─ initiated_by: JAY             │
        │ └─ (marked complete when done)   │
        └──────┬───────────────────────────┘
               ↓
        ┌──────────────────────────┐
        │ Engineering Complete     │
        │ ├─ engineering_completed │
        │ │  = TRUE                │
        │ ├─ engineering_          │
        │ │  completed_at          │
        │ └─ status: "ready"       │
        └──────┬───────────────────┘
               ↓
 ╔═════════════════════════════════╗
 ║ SIGNATORY ROUTING CHAIN BEGINS  ║
 ║                                 ║
 ║ Path: JAY → OIC → HEAD (3 steps)║
 ╚═════════════════════════════════╝
               ↓
         ┌───────────────────────┐
         │  Jay → OIC (Step 1)   │
         │                       │
         │ SignatoryRouting      │
         │  ├─ application: FK   │
         │  ├─ step: "received"  │
         │  ├─ action_at: NOW    │
         │  ├─ action_by: JAY    │
         │  └─ notes: ""         │
         │                       │
         │ Application Updates:  │
         │  ├─ status: "with_oic"│
         │  └─ SMS: OIC notified │
         │     "New app awaiting │
         │      your signature"  │
         └───────┬───────────────┘
                 ↓
       ┌──────────────────────┐
       │ OIC Signs (Step 2)   │
       │                      │
       │ SignatoryRouting     │
       │  ├─ step:            │
       │  │   "signed_oic"    │
       │  ├─ action_at: NOW   │
       │  ├─ action_by: OIC   │
       │  └─ notes: "..."     │
       │                      │
       │ Application Updates: │
       │  ├─ status:          │
       │  │   "with_head"     │
       │  └─ SMS: HEAD notif. │
       │     "OIC signed app" │
       └────────┬────────────┘
                ↓
      ┌──────────────────────┐
      │ HEAD Signs (Step 3)  │
      │                      │
      │ SignatoryRouting     │
      │  ├─ step:            │
      │  │  "signed_head"    │
      │  ├─ action_at: NOW   │
      │  ├─ action_by: HEAD  │
      │  └─ notes: "..."     │
      │                      │
      │ Application Updates: │
      │  ├─ status:          │
      │  │   "fully_approved" │
      │  ├─ fully_approved_at│
      │  │  = NOW            │
      │  └─ SMS: Applicant   │
      │     "You're approved!"│
      └────────┬────────────┘
               ↓
    ┌─────────────────────────┐
    │ → MOVE TO MODULE 4      │
    │   (Standby Queue)       │
    └─────────────────────────┘
```

**Data Flow**: `Application` → `SignatoryRouting (3 steps)` → `FacilitatedService`

### MODULE 3: DOCUMENT MANAGEMENT (Jocel)
```
INPUT: Application at any stage

M3 PARALLEL PROCESS: Document Archival
    ↓
    ├─ ALL documents received (Group A, B, C)
    │  are stored in Document model
    │
    │  Document Fields:
    │  ├─ applicant: FK → Applicant
    │  ├─ requirement_submission: FK (for Group A)
    │  ├─ document_type: CHOICE field
    │  ├─ title: [human readable]
    │  ├─ file: [upload to storage]
    │  ├─ file_name, file_size, mime_type
    │  ├─ uploaded_at: NOW
    │  ├─ uploaded_by: USER
    │  └─ notes: [audit trail]
    │
    ├─ GROUP A: Applicant requirements
    │  (verified during Module 1)
    │
    ├─ GROUP B: Office-generated docs
    │  ├─ Notarization form
    │  ├─ Engineering assessment
    │  ├─ Application form
    │  └─ Contract
    │
    └─ GROUP C: Post-award docs
       ├─ Electricity bills
       ├─ Occupancy reports
       ├─ Compliance notices
       └─ Photo documentation

    ↓
    Jocel can: Query, Search, Download, Archive all docs
    Attached to applicant's permanent profile
```

**Data Flow**: `Document` ← Various sources (M1, M2, M4, M5)

### MODULE 4: LOT AWARDING & STANDBY QUEUE (Jocel)
```
INPUT: Application status "fully_approved"

M4P1: Standby Queue Management
    ↓
    ┌────────────────────────────────────┐
    │ Application enters Standby         │
    │                                    │
    │ Application Updates:               │
    │  ├─ status: "standby"              │
    │  ├─ standby_position: [position]   │
    │  └─ standby_entered_at: NOW        │
    │                                    │
    │ QueueEntry (M1) Updated:           │
    │  ├─ status: "standby"              │
    │  ├─ completed_at: NOW              │
    │  └─ SMS: "On standby - waiting for│
    │             lot to be available"   │
    └─────────────────────────────────────┘
               ↓
    (JOCEL MANAGES AVAILABLE LOTS)
               ↓
    Housing available? → Plot selection process
               ↓
    ┌────────────────────────────────────┐
    │ LotAwarding Created (Jocel)        │
    │                                    │
    │ ├─ application: FK → Application   │
    │ ├─ lot_number: [block/lot]         │
    │ ├─ site_name: "GK Cabatangan"      │
    │ ├─ awarded_at: NOW                 │
    │ ├─ awarded_by: JOCEL               │
    │ ├─ via_draw_lots: TRUE/FALSE       │
    │ ├─ status: "lot_awarded"           │
    │ └─ notes: [allocation reason]      │
    │                                    │
    │ HousingUnit (units app) Links:     │
    │  ├─ site, block, lot numbers       │
    │  ├─ status: "occupied"             │
    │  └─ occupant_name: Applicant name  │
    │                                    │
    │ Application Updates:               │
    │  ├─ status: "awarded"              │
    │  └─ SMS: "🎉 AWARDED! Lot #X at   │
    │             Site Y. Get electricity│
    │             connection ready"      │
    └─────────────────────────────────────┘
               ↓
    ┌────────────────────────────────────┐
    │ → Move to Module 2 (Electricity)   │
    └────────────────────────────────────┘
```

**Data Flow**: `Application` → `LotAwarding` → `HousingUnit`

### MODULE 2b: ELECTRICITY CONNECTION (Joiel & Laarni)
```
INPUT: Application status "awarded"

M2b: Post-Award Electricity Setup
    ↓
    ┌────────────────────────────────────┐
    │ ElectricityConnection Created      │
    │                                    │
    │ ├─ application: OneToOne           │
    │ ├─ status: "pending"               │
    │ ├─ applied_at: NOW                 │
    │ ├─ applied_by: JOIEL or LAARNI     │
    │ └─ notes: [application details]    │
    │                                    │
    │ → OR in units app:                 │
    │                                    │
    │ LotAward → ElectricityConnection   │
    │  ├─ lot_award: OneToOne            │
    │  ├─ status: "pending" → "approved" │
    │  │            → "completed"        │
    │  ├─ initiated_at, completed_at     │
    │  ├─ negros_power_reference: [ref]  │
    │  └─ meter_number: [when completed] │
    │                                    │
    │ SMS Updates:                       │
    │  ├─ "Applied": Neg. Power notified │
    │  ├─ "Approved": "Your connection   │
    │  │               is approved"      │
    │  └─ "Complete": "Power connected!  │
    │                 Meter: #XXXX"      │
    └────────────────────────────────────┘
               ↓
    (Negros Power inspection - Outside system)
               ↓
    ┌────────────────────────────────────┐
    │ Connection Completed               │
    │                                    │
    │ ElectricityConnection Updated:     │
    │  ├─ status: "completed"            │
    │  ├─ meter_number: [assigned]       │
    │  ├─ connected_at: NOW              │
    │  └─ SMS: "Power is on! Welcome!"   │
    │                                    │
    │ Application fully complete:        │
    │  ├─ has documents (M1, M3)         │
    │  ├─ was signed (M2)                │
    │  ├─ has lot (M4)                   │
    │  └─ has electricity (M2b)          │
    └────────────────────────────────────┘
               ↓
    ┌────────────────────────────────────┐
    │ → Move to Module 4 (Occupancy)     │
    └────────────────────────────────────┘
```

**Data Flow**: `Application` → `ElectricityConnection` → Power confirmation

### MODULE 4 (continued): OCCUPANCY MONITORING (Caretaker + Field Team)
```
INPUT: Awarded beneficiary (HousingUnit occupied)

M4P2: Weekly Occupancy Reporting
    ↓
    ┌────────────────────────────────────────┐
    │ Caretaker submits Weekly Report        │
    │ (via mobile form every Sunday)         │
    │                                        │
    │ OccupancyReport Created:               │
    │  ├─ site: FK → RelocationSite          │
    │  ├─ report_week_start: [date]          │
    │  ├─ report_week_end: [date]            │
    │  ├─ submitted_at: NOW                  │
    │  ├─ submitted_by: CARETAKER            │
    │  ├─ reported_occupied: [count]         │
    │  ├─ reported_vacant: [count]           │
    │  ├─ reported_concerns: [count]         │
    │  └─ status: "submitted"                │
    │                                        │
    │ OccupancyReportDetail (per-unit):      │
    │  ├─ report: FK                         │
    │  ├─ unit: FK → HousingUnit             │
    │  ├─ reported_status: "occupied" OR     │
    │  │                  "vacant" OR        │
    │  │                  "concern"          │
    │  └─ concern_notes: [if any issue]      │
    └──────────────┬──────────────────────────┘
                   ↓
    ┌────────────────────────────────────────┐
    │ Field Team Reviews & Confirms          │
    │ (Nonoy, Paul, Roberto, Rona)           │
    │                                        │
    │ OccupancyReport Updated:               │
    │  ├─ reviewed_at: NOW                   │
    │  ├─ reviewed_by: FIELD_OFFICER         │
    │  ├─ confirmed_occupied: [actual]       │
    │  ├─ confirmed_vacant: [actual]         │
    │  ├─ status: "reviewed"                 │
    │  └─ discrepancy_notes: [if diff]       │
    └────────────────┬────────────────────────┘
                     ↓
    ┌────────────────────────────────────────┐
    │ Data Analysis for Compliance           │
    │                                        │
    │ IF occupied > threshold:               │
    │  ├─ Normal occupancy                   │
    │  └─ No action needed                   │
    │                                        │
    │ IF occupied < threshold:               │
    │  ├─ Possible abandonment               │
    │  └─ → Module 5 (Case Investigation)    │
    │                                        │
    │ IF concern reported:                   │
    │  ├─ Unit issue flagged                 │
    │  └─ → Module 5 (Case Management)       │
    │                                        │
    │ Analytics Updated:                     │
    │  ├─ Occupancy rate (%)                 │
    │  ├─ Vacant units count                 │
    │  └─ Issues needing attention           │
    └────────────────────────────────────────┘
               ↓
    ┌────────────────────────────────────────┐
    │ CYCLE REPEATS WEEKLY                   │
    │ (continuous monitoring)                │
    └────────────────────────────────────────┘
```

**Data Flow**: `HousingUnit` → `OccupancyReport` → `OccupancyReportDetail` → Analysis

### MODULE 5: COMPLIANCE & CASE MANAGEMENT (Victor OIC, Field Team)
```
INPUT: Occupancy concerns OR violation reports

M5P1: Compliance Notice Issuance
    ↓
    ┌────────────────────────────────────────┐
    │ ComplianceNotice Issued                │
    │ (Second Member, M2)                    │
    │                                        │
    │ ├─ lot_award: FK → LotAwarding         │
    │ ├─ unit: FK → HousingUnit              │
    │ ├─ notice_type: "30_day_notice"        │
    │ ├─ reason: [why issued - abandonment,  │
    │ │           unpaid contract, etc]      │
    │ ├─ issued_at: NOW                      │
    │ ├─ issued_by: SECOND_MEMBER            │
    │ ├─ days_granted: 30                    │
    │ ├─ deadline: NOW + 30 days             │
    │ ├─ status: "pending"                   │
    │ └─ SMS: "You have 30 days to comply"   │
    │                                        │
    │ HousingUnit Updated:                   │
    │  ├─ notice_type: "30_day_notice"       │
    │  ├─ notice_date_issued: NOW            │
    │  ├─ notice_deadline: [date]            │
    │  └─ status: "notice_issued"            │
    └──────────────┬──────────────────────────┘
                   ↓ (If deadline passes & no response)
    ┌────────────────────────────────────────┐
    │ ComplianceNotice Escalated             │
    │                                        │
    │ ComplianceNotice.notice_type Updated:  │
    │  ├─ "final_notice"                     │
    │  ├─ days_granted: 10                   │
    │  ├─ deadline: NOW + 10 days            │
    │  └─ SMS: "FINAL WARNING: 10 days left" │
    │                                        │
    │ HousingUnit Updated:                   │
    │  ├─ notice_type: "final_notice"        │
    │  ├─ is_escalated: TRUE                 │
    │  └─ escalation_reason: "abandoned"     │
    └──────────────┬──────────────────────────┘
                   ↓ (If still no response)
    ┌────────────────────────────────────────┐
    │ REPOSSESSION INITIATED                 │
    │                                        │
    │ Case Created:                          │
    │  ├─ case_type: "abandonment" OR        │
    │  │             "violation"             │
    │  ├─ subject_applicant: [beneficiary]   │
    │  ├─ related_unit: [housing unit]       │
    │  ├─ status: "open"                     │
    │  ├─ received_at: NOW                   │
    │  └─ description: "Repossession prep"   │
    │                                        │
    │ ComplianceNotice Updated:              │
    │  ├─ status: "resolved"                 │
    │  ├─ resolution_decision: "repossess"   │
    │  ├─ decided_at: NOW                    │
    │  ├─ decided_by: VICTOR (OIC)           │
    │  └─ SMS: "Unit repossessed due to non- │
    │           compliance. Appeal within 7  │
    │           days."                       │
    │                                        │
    │ LotAward Updated:                      │
    │  ├─ status: "terminated"               │
    │  ├─ end_reason: "abandoned" OR         │
    │  │              "repossessed"          │
    │  └─ ended_at: NOW                      │
    │                                        │
    │ HousingUnit Updated:                   │
    │  ├─ status: "vacant"                   │
    │  ├─ occupant_name: NULL                │
    │  └─ notice_type: NULL                  │
    │                                        │
    │ Blacklist Created:                     │
    │  ├─ applicant: [beneficiary]           │
    │  ├─ reason: "repossession"             │
    │  ├─ original_lot_award: [FK]           │
    │  ├─ original_unit: [FK]                │
    │  ├─ blacklisted_at: NOW                │
    │  └─ blacklisted_by: VICTOR             │
    └────────────────────────────────────────┘

M5P2: Case Management (Investigate violations)
    ↓
    ┌────────────────────────────────────────┐
    │ Case Created (Victor OIC)              │
    │                                        │
    │ Case Model:                            │
    │  ├─ case_number: AUTO (2026-M5-001)    │
    │  ├─ case_type: "complaint" OR "viol."  │
    │  ├─ complainant_applicant: [if benefic]│
    │  ├─ subject_applicant: [accused party] │
    │  ├─ related_unit: [associated unit]    │
    │  ├─ received_at: NOW                   │
    │  ├─ received_by: [who reported]        │
    │  ├─ initial_description: [details]     │
    │  ├─ status: "open"                     │
    │  └─ SMS: "Case #XXXX opened. Reference │
    │            for followup."              │
    │                                        │
    │ CaseNote Created (audit trail):        │
    │  ├─ case: FK                           │
    │  ├─ note: "Case opened"                │
    │  ├─ created_by: VICTOR                 │
    │  └─ created_at: NOW                    │
    └──────────────┬──────────────────────────┘
                   ↓ (Field team investigates)
    ┌────────────────────────────────────────┐
    │ Investigation Phase                    │
    │                                        │
    │ Case Updated:                          │
    │  ├─ status: "investigation"            │
    │  ├─ investigated_by: [field officer]   │
    │  ├─ investigated_at: NOW               │
    │  └─ investigation_notes: [findings]    │
    │                                        │
    │ CaseNote Added:                        │
    │  ├─ note: "Visited unit. Found: ..."   │
    │  ├─ created_by: FIELD_OFFICER          │
    │  └─ created_at: NOW                    │
    │                                        │
    │ SMS: "Case under investigation..."     │
    └──────────────┬──────────────────────────┘
                   ↓ (Resolution decision)
    ┌────────────────────────────────────────┐
    │ Case Resolution                        │
    │                                        │
    │ Case Updated:                          │
    │  ├─ status: "resolved" OR "referred"   │
    │  ├─ decided_by: VICTOR                 │
    │  ├─ decided_at: NOW                    │
    │  ├─ resolution_notes: [decision]       │
    │  └─ resolved_at: NOW                   │
    │                                        │
    │ IF violation confirmed:                │
    │  ├─ → Compliance Notice issued (M5P1)  │
    │  └─ → Escalation path begins           │
    │                                        │
    │ IF referral needed:                    │
    │  ├─ referred_to: [agency]              │
    │  ├─ referred_at: NOW                   │
    │  ├─ referral_notes: [agency details]   │
    │  └─ SMS: "Case referred to XXXX"       │
    │                                        │
    │ CaseNote Added:                        │
    │  ├─ note: "Case RESOLVED: ..."         │
    │  ├─ created_by: VICTOR                 │
    │  └─ created_at: NOW                    │
    └────────────────────────────────────────┘
```

**Data Flow**: `HousingUnit` → `ComplianceNotice` → `Case` → `Blacklist`

### MODULE 6: ANALYTICS & REPORTING (Head & Second Member)
```
INPUT: All data from Modules 1-5 (48 models)

M6P1: Real-time KPI Calculation
    ↓
    Queried from database (no storage):

    1. Monthly Applicants Processed
       = COUNT(Applicant.created_at = THIS_MONTH)

    2. Application Status Distribution
       = GROUPED_COUNT(Application.status)
       Example: 45 "fully_approved", 12 "standby", 8 "with_oic"

    3. Occupancy Rate
       = COUNT(HousingUnit.status="occupied") /
         COUNT(HousingUnit) × 100

    4. Compliance Notice Status
       = COUNT(ComplianceNotice.status="pending"),
         COUNT(ComplianceNotice.status="resolved"),
         COUNT(ComplianceNotice.is_escalated=True)

    5. Avg Processing Time Per Stage
       = AVG(SignatoryRouting.action_at[step2] -
             SignatoryRouting.action_at[step1])
       For each step: Jay→OIC, OIC→Head

    6. Monthly Approval Rate
       = COUNT(Application.status="awarded" in THIS_MONTH) /
         COUNT(Application.status="fully_approved" in THIS_MONTH) × 100

    7. Case Volume & Resolution Rate
       = COUNT(Case.status="open"),
         COUNT(Case.status="resolved" in THIS_MONTH),
         PERCENT = resolved/total in month

    8. Staff Performance & Bottleneck
       = For each user/position:
         COUNT(items assigned),
         AVG(time to complete),
         IDENTIFY delays > 3 days

    ↓
    ┌────────────────────────────────────────┐
    │ Analytics Dashboard Rendered           │
    │ (Real-time, no storage needed)         │
    │                                        │
    │ Views Generated:                       │
    │  ├─ /head/analytics/                   │
    │  │  └─ HEAD Executive View             │
    │  │     (All 8 KPIs)                    │
    │  │                                     │
    │  ├─ /second-member/analytics/          │
    │  │  └─ Second Member Supervisory       │
    │  │     (KPIs & compliance overview)    │
    │  │                                     │
    │  ├─ /oic/analytics/                    │
    │  │  └─ OIC M2, M4, M5 summary          │
    │  │                                     │
    │  ├─ /field/analytics/                  │
    │  │  └─ Field Team M1, M4, M5 summary   │
    │  │                                     │
    │  ├─ /caretaker/analytics/              │
    │  │  └─ Caretaker M4 Occupancy          │
    │  │                                     │
    │  └─ (others for each position)         │
    │                                        │
    │ Monthly Reports:                       │
    │  ├─ /head/reports/?month=2026-04       │
    │  ├─ /second-member/reports/?month=...  │
    │  └─ Detailed breakdowns per module     │
    └────────────────────────────────────────┘
```

**Data Flow**: Modules 1-5 data → SQL queries → Analytics Dashboard

---

## LEVEL 4: COMPLETE DATABASE SCHEMA RELATIONSHIPS

```
                          ┌─────────────────────┐
                          │   Barangay (27)     │
                          │  Reference table    │
                          └────────┬────────────┘
                                   ↓
        ┌──────────────────────────────────────────────────┐
        │                                                  │
        │                   APPLICANT                      │
        │              (Master Profile)                    │
        │           ├─ reference_number                    │
        │           ├─ full_name                           │
        │           ├─ channel (3 types)                   │
        │           ├─ status (eligible/pending/blocked)   │
        │           ├─ doc_1-7 (boolean tracking)          │
        │           └─ barangay (FK)                       │
        │                       ↓                          │
        │      ┌────────────────────────────────┐          │
        │      │  Related to APPLICANT:         │          │
        │      │                                │          │
        │      │  1. ISFRecord (if Channel A)   │          │
        │      │     (nullable OneToOne)        │          │
        │      │                                │          │
        │      │  2. HouseholdMember (1+)       │          │
        │      │     (reverse FK)               │          │
        │      │                                │          │
        │      │  3. RequirementSubmission (7)  │          │
        │      │     (M1 documents tracking)    │          │
        │      │     → Requirement (ref table)  │          │
        │      │                                │          │
        │      │  4. Document (1+)              │          │
        │      │     (archive of all docs)      │          │
        │      │                                │          │
        │      │  5. QueueEntry (1)             │          │
        │      │     (active queue position)    │          │
        │      │                                │          │
        │      │  6. Application (OneToOne)     │          │
        │      │     IF accepted at M2          │          │
        │      │                                │          │
        │      │  7. CDRRMOCertification (opt.) │          │
        │      │     (if Channel B verified)    │          │
        │      │                                │          │
        │      │  8. Case (reverse FK, 2)       │          │
        │      │     (as complainant OR subject)│          │
        │      │                                │          │
        │      │  9. Blacklist (OneToOne)       │          │
        │      │     (if disqualified)          │          │
        └──────┴────────────────────────────────┘          │
                                   ↓
        ┌──────────────────────────────────────────────────┐
        │                 APPLICATION                      │
        │              (M2 Form Submission)                │
        │          ├─ application_number                   │
        │          ├─ applicant (OneToOne FK)              │
        │          ├─ status (pending→awarded)             │
        │          ├─ form_generated_at/by                 │
        │          ├─ applicant_signed_at                  │
        │          ├─ notarial_completed                   │
        │          ├─ engineering_completed                │
        │          ├─ fully_approved_at                    │
        │          └─ standby info                         │
        │                       ↓                          │
        │      ┌────────────────────────────────┐          │
        │      │  Related to APPLICATION:       │          │
        │      │                                │          │
        │      │  1. SignatoryRouting (3+)      │          │
        │      │     (M2 routing chain)         │          │
        │      │     Jay → OIC → HEAD           │          │
        │      │                                │          │
        │      │  2. FacilitatedService (1+)    │          │
        │      │     (notarial, engineering)    │          │
        │      │                                │          │
        │      │  3. ElectricityConnection      │          │
        │      │     (M2b - post award)         │          │
        │      │                                │          │
        │      │  4. LotAwarding (OneToOne)     │          │
        │      │     (M4 lot assignment)        │          │
        │      │     → HousingUnit (FK)         │          │
        │      │     → RelocationSite (FK)      │          │
        └──────┴────────────────────────────────┘          │
                                                          │
└──────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────┐
        │          HOUSING UNITS (M4)              │
        │                                          │
        │  RelocationSite (1-10 sites)             │
        │  ├─ name, code, address                  │
        │  ├─ total_blocks, total_lots             │
        │  ├─ caretaker (FK)                       │
        │  └─ is_active                            │
        │                  ↓                       │
        │      HousingUnit (1-500 units)           │
        │      ├─ site (FK)                        │
        │      ├─ block_number, lot_number         │
        │      ├─ status (occupied/vacant/notice)  │
        │      ├─ occupant_name                    │
        │      ├─ notice_type, notice_deadline     │
        │      └─ is_escalated                     │
        │                                          │
        │      Related to HousingUnit:             │
        │      ├─ LotAward (FK - awarded to this) │
        │      ├─ OccupancyReportDetail (weekly)   │
        │      ├─ ComplianceNotice (escalation)    │
        │      ├─ Case (violations)                │
        │      └─ WeeklyReport (optional)          │
        └──────────────────────────────────────────┘

        ┌──────────────────────────────────────────┐
        │         CASE MANAGEMENT (M5)             │
        │                                          │
        │  Case (complaints & violations)          │
        │  ├─ case_number (auto)                   │
        │  ├─ case_type (complaint/violation)      │
        │  ├─ complainant_applicant (FK, opt.)     │
        │  ├─ subject_applicant (FK, accusing)     │
        │  ├─ related_unit (FK, opt.)              │
        │  ├─ status (open/investi/referred/resol.)│
        │  ├─ received_at, received_by             │
        │  ├─ investigated_by, investigated_at     │
        │  ├─ referred_to, referral_notes          │
        │  ├─ decided_by, decided_at               │
        │  ├─ resolution_notes, resolved_at        │
        │  └─                                      │
        │      CaseNote (audit trail for case)     │
        │      ├─ case (FK)                        │
        │      ├─ note: description                │
        │      ├─ created_by (user)                │
        │      └─ created_at                       │
        └──────────────────────────────────────────┘

        ┌──────────────────────────────────────────┐
        │      OCCUPANCY MONITORING (M4)           │
        │                                          │
        │  OccupancyReport (weekly)                │
        │  ├─ site (FK)                            │
        │  ├─ report_week_start/end                │
        │  ├─ submitted_at, submitted_by           │
        │  ├─ reported_occupied/vacant/concerns    │
        │  ├─ status (submitted/reviewed)          │
        │  ├─ reviewed_at, reviewed_by             │
        │  ├─ confirmed_occupied/vacant            │
        │  └─ discrepancy_notes                    │
        │          ↓                               │
        │  OccupancyReportDetail (per unit)        │
        │  ├─ report (FK)                          │
        │  ├─ unit (FK)                            │
        │  ├─ reported_status                      │
        │  └─ concern_notes                        │
        └──────────────────────────────────────────┘

        ┌──────────────────────────────────────────┐
        │      COMPLIANCE & NOTICES                │
        │                                          │
        │  ComplianceNotice (escalation path)      │
        │  ├─ notice_type: 30-day / final / resol. │
        │  ├─ status: pending / resolved           │
        │  ├─ reason: abandoned, unpaid, etc.      │
        │  ├─ issued_at, issued_by                 │
        │  ├─ deadline                             │
        │  ├─ response_received_at                 │
        │  ├─ resolved_at, resolution_decision     │
        │  ├─ decided_by (OIC)                     │
        │  └─ is_escalated (TRUE = final notice)   │
        │          ↓                               │
        │  IF not complied:                        │
        │  Blacklist (permanent record)            │
        │  ├─ applicant (OneToOne)                 │
        │  ├─ reason: repossessed, violated        │
        │  ├─ original_lot_award (FK)              │
        │  ├─ original_unit (FK)                   │
        │  ├─ blacklisted_at, blacklisted_by       │
        │  └─ [FOREVER excluded from future lots]  │
        └──────────────────────────────────────────┘
```

---

## LEVEL 5: DATA FLOW THROUGH TIME (8-Year Applicant Journey)

```
TIMELINE: From ISF Entry → Lot Award → Lifetime Monitoring

YEAR 0-2:  INTAKE & PROCESSING
────────────────────────────────
Months 1-3:
  Day 1: Applicant enters (LandownerSubmission OR walk-in)
         └─ ISFRecord/Applicant created
         └─ SMS: "Reference #XXXX"

  Week 2-4: Module 1 - Document collection
         └─ RequirementSubmission tracking (7 docs)
         └─ Document upload/verification
         └─ Blacklist auto-check
         └─ SMS: "Missing: Valid ID, Marriage Cert"

  Month 2-3: All documents verified
         └─ Application form generated
         └─ SMS: "Form ready for signing"

  Month 3-4: SignatoryRouting
         └─ Jay reviews & sends to OIC
         └─ OIC reviews @ 5 days (delay flagged if >3 days)
         └─ OIC sends to HEAD
         └─ HEAD signs (final approval)
         └─ SMS: "🎉 APPROVED! Lot will be assigned"

Months 4-12:
  Standby Queue period (varies by lot availability)
         └─ Application status: "standby"
         └─ Monthly SMS: "You're at position #12 in queue"

  When lot available:
         └─ Jocel assigns lot (block, lot number)
         └─ LotAwarding record created
         └─ SMS: "🎉 AWARDED LOT XXX at Site YYY"

  Electricity applied:
         └─ ElectricityConnection created
         └─ Negros Power inspection scheduled
         └─ SMS: "Connection estimated 14 days"

         └─ 2 weeks later: meter installed
         └─ SMS: "Power connected! Meter #1234"

YEAR 2-8:  OCCUPANCY & MONITORING
────────────────────────────────
Weekly (every Sunday):
  Caretaker submits OccupancyReport
         └─ Who's home, who vacant
         └─ Any issues observed
         └─ SMS: "Report submitted"

  Field team reviews (Tuesday AM)
         └─ Visits site, confirms occupancy
         └─ Resolves discrepancies
         └─ SMS: "Occupancy verified"

Monthly (Analytics):
  Occupancy rate calculated
         └─ If 100%: "Good compliance"
         └─ If <70%: "Investigate abandonment"
         └─ SMS alert if concerning

Quarterly:
  Case investigation (if needed)
         └─ Abandonment suspected
         └─ ComplianceNotice issued
         └─ SMS: "30-day notice: unit must be occupied"

         √ If response: Case closed
         ✗ If no response: ESCALATE

            Final notice issued
            └─ 10 days left
            └─ SMS: "FINAL WARNING"

            Still no response?
            └─ ComplianceNotice resolved as "repossess"
            └─ LotAward ended
            └─ Unit marked vacant
            └─ Applicant added to Blacklist
            └─ SMS: "Unit repossessed"
            └─ Case status: "resolved"

        OR

Compliant throughout?
         └─ Year 8: Unit still occupied
         └─ Beneficiary keeps lot
         └─ SMS: "Congratulations! 8-year residency"
         └─ [System continues monitoring]

END STATE OPTIONS:
─────────────────
1. SUCCESSFUL: Still occupied after 8+ years
   └─ Occupancy status: "occupied"
   └─ LotAward status: "active"
   └─ Case status: NONE (no violations)

2. ABANDONED: Vacancy detected
   └─ Occupancy status: "vacant"
   └─ ComplianceNotice issued & resolved
   └─ LotAward status: "terminated"
   └─ Unit available for next applicant
   └─ Blacklist entry created

3. VIOLATION: Unauthorized occupancy, illegal sublet
   └─ Case status: "resolved"
   └─ ComplianceNotice issued & resolved
   └─ LotAward status: "terminated"
   └─ Unit available for next applicant
   └─ Blacklist entry created
```

---

## LEVEL 6: AUDIT TRAIL & DATA INTEGRITY

```
Every action in system is logged:

1. SMSLog (SMS Audit Trail)
   ├─ Every SMS has record:
   │  ├─ recipient_phone
   │  ├─ message_content
   │  ├─ trigger_event (e.g., "application_approved")
   │  ├─ applicant/isf_record linked
   │  ├─ sent_at: timestamp
   │  └─ status: "sent" OR "failed"
   │
   └─ Why: Track communication history

2. ISFEditAudit (Data Correction Audit)
   ├─ Every edit to ISF data tracked:
   │  ├─ field_name: which field changed
   │  ├─ original_value: before
   │  ├─ new_value: after
   │  ├─ edit_reason: why corrected
   │  ├─ edited_by: which staff member
   │  └─ edited_at: timestamp
   │
   └─ Why: Prevent data tampering, track corrections

3. SignatoryRouting (Document Routing History)
   ├─ Every signature recorded:
   │  ├─ step: which person signed
   │  ├─ action_at: when signed
   │  ├─ action_by: who signed
   │  └─ notes: any comments they added
   │
   └─ Why: Track approval chain, detect delays

4. CaseNote (Case Investigation Audit)
   ├─ Every case update tracked:
   │  ├─ case: which case
   │  ├─ note: what was discovered
   │  ├─ created_by: investigator
   │  └─ created_at: when documented
   │
   └─ Why: Investigation transparency, legal record

5. OccupancyReport + OccupancyReportDetail
   ├─ Weekly occupancy audit:
   │  ├─ submitted_by: caretaker
   │  ├─ reviewed_by: field officer
   │  ├─ discrepancy_notes: why different
   │  └─ timestamps for each step
   │
   └─ Why: Verify actual occupancy status

6. Document Model
   ├─ File upload audit:
   │  ├─ uploaded_by: who uploaded
   │  ├─ uploaded_at: timestamp
   │  ├─ file_size, mime_type: integrity check
   │  └─ notes: upload comments
   │
   └─ Why: Document provenance tracking

7. Django User Model (built-in audit)
   ├─ Each User has:
   │  ├─ last_login
   │  ├─ date_joined
   │  └─ is_active status
   │
   └─ Why: Staff activity tracking

PRINCIPLE: ONE DATABASE, ONE TRUTH
───────────────────────────────────
- Single entry point for each data type
- No duplicate storage
- Changes tracked in audit models
- Cannot delete data, only mark "terminated"
- SMS log proves communication
- Every human decision documented
```

---

## LEVEL 7: ANALYTICS PIPELINE

```
INPUT: All 48 models + processed data
       └─ Queried live from PostgreSQL
       └─ No intermediate storage

KPIS CALCULATED:
─────────────────

1. MONTHLY APPLICANTS PROCESSED
   Query: SELECT COUNT(*) FROM applicant
          WHERE created_at >= month_start
   Result type: INTEGER
   Use: Intake volume tracking
   Recalculated: Daily
   Storage: None (live query)

2. APPLICATION STATUS DISTRIBUTION
   Query: SELECT status, COUNT(*) FROM application
          GROUP BY status
   Result type: DICT {status: count}
   Use: Pipeline health check
   Recalculated: Real-time
   Example: {'fully_approved': 45, 'standby': 12, 'with_oic': 8}

3. OCCUPANCY RATE
   Query: SELECT COUNT(*) FILTER(status='occupied'),
                 COUNT(*) FROM housing_unit
   Result type: FLOAT % (0-100)
   Use: Site health indicator
   Recalculated: After each occupancy report
   Example: 87.3% occupancy

4. COMPLIANCE NOTICE STATUS
   Query: SELECT status, COUNT(*) FROM compliance_notice
          GROUP BY status
   Result type: DICT
   Use: Escalation tracking
   Recalculated: Real-time
   Example: {pending: 12, resolved: 84, escalated: 3}

5. AVG PROCESSING TIME PER STAGE
   Query: For each SignatoryRouting step (Jay→OIC, OIC→HEAD)
          Calculate: AVG(step2_time - step1_time)
   Result type: DICT {step_name: days}
   Use: Bottleneck identification
   Recalculated: Weekly
   Example: {jay_to_oic: 2.3, oic_to_head: 1.8}

6. MONTHLY APPROVAL RATE
   Query: COUNT(status='awarded' && created_at=MONTH) /
          COUNT(status='fully_approved' && created_at=MONTH) × 100
   Result type: FLOAT %
   Use: Approval efficiency
   Recalculated: Monthly
   Example: 78% of approved got lots this month

7. CASE VOLUME & RESOLUTION RATE
   Query: COUNT(status='open'),
          COUNT(status='resolved' && resolved_at=MONTH),
          PERCENT = resolved/total
   Result type: DICT
   Use: Compliance effectiveness
   Recalculated: Real-time
   Example: {open: 5, resolved_month: 24, rate: 82%}

8. STAFF PERFORMANCE & BOTTLENECK
   Query: For each User.position & application/case assigned
          - COUNT of items
          - AVG(action_at - received_at) by position
          - FLAGS where delay > 3 days
   Result type: DICT per position
   Use: Identify overloaded staff
   Recalculated: Weekly
   Example: {jay: {count: 45, avg_days: 2.1, bottleneck: false},
             oic: {count: 12, avg_days: 4.7, bottleneck: TRUE}}

OUTPUT: 8 Position-Specific Dashboards
─────────────────────────────────────────

/head/analytics/
├─ All 8 KPIs (executive view)
├─ 6-month trend graphs
├─ Approval funnel visualization
└─ Critical alerts (if bottlenecks)

/oic/analytics/
├─ KPI #5, #6, #7 (M2, M4, M5)
├─ Pending applications detail
├─ Case management summary
└─ Compliance escalation status

/second-member/analytics/
├─ KPI #4 (Compliance)
├─ Document status (M3)
├─ Electricity progress (M2b)
└─ Lot awarding pipeline

/third-member/analytics/
├─ KPI #2 (Application routing)
├─ Signatory queue (M2)
├─ Document verification status (M1)
└─ Processing delays

/fourth-member/analytics/
├─ Queue management (M1, M4)
├─ Lot awarding volume
├─ Property records
└─ Document filing status

/fifth-member/analytics/
├─ Electricity connections (M2b)
├─ Connection rate by month
├─ Average time to completion
└─ Issues/rejected connections

/caretaker/analytics/
├─ KPI #3 (Occupancy)
├─ Weekly report submission status
├─ Unit-by-unit occupancy
└─ Concerns tracked

/field/analytics/
├─ KPI #3, #7 (Occupancy, Cases)
├─ Site inspection summary
├─ Case investigation volume
└─ Compliance verification rate

/second-member/reports/?month=YYYY-MM
├─ Detailed month breakdown
├─ All applications processed
├─ All units state changes
├─ All cases opened/resolved
└─ Exportable summary
```

---

## SUMMARY

This diagram shows:
- **3 Entry Channels** → Data creation
- **6 Active Modules** → M1-M6 processing
- **48 Django Models** → Organized in 7 apps
- **10 Core Processes** → From intake to lifecycle
- **Audit Trails** → Every action logged
- **8 Analytics Dashboards** → Position-specific KPIs
- **8-Year Journey** → Beneficiary lifecycle
- **One Database Principle** → Single source of truth

The system is **100% paper-free** and **fully auditable** with **real-time analytics** on all housing authority operations.
