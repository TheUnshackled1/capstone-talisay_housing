# 🎯 CRITICAL MISSING UIs - COMPLETE BUILD LIST

**Status**: Corrected Analysis - Ready for Implementation
**Date**: 2026-04-11
**Priority**: URGENT - These block all 11 Revised Processes

---

## 📋 ORGANIZED BY PROCESS: ALL MISSING UIs

### **PROCESS 1 & 2: INTAKE & ELIGIBILITY (6 Screens)**

| # | Screen Name | Process | Actor | Status | Purpose | Sketch |
|---|-------------|---------|-------|--------|---------|--------|
| **1** | Register New Applicant | P1 | Records Officer | ✅ **EXISTS** | Walk-in intake (Ch. A/B/C) | Modal in applicants.html:1602 |
| **2** | CDRRMO Certification Update | P1 | Records Officer | ⚠️ UNCLEAR | Record danger zone verification | Needs UX clarification |
| **3** | **Eligibility Screening Form** | **P2** | **Records Officer** | **❌ CRITICAL** | **Blacklist check + property + income verification** | **New form needed** |
| **4** | Household Member Entry | P2 | Records Officer | ⚠️ PARTIAL | Lock family composition | May exist in modal |
| **5** | Queue Assignment Display | P2 | System | ⚠️ PARTIAL | Show queue position after eligibility | Dashboard shows it |
| **6** | Eligibility Summary Report | P2 | Records Officer | ❌ MISSING | Print/view eligibility decision | Export functionality |

---

### **PROCESS 3: DOCUMENT SUBMISSION (3 Screens)**

| # | Screen Name | Process | Actor | Status | Purpose | Sketch |
|---|-------------|---------|-------|--------|---------|--------|
| **7** | Document Submission Checklist | P3 | Applicant | ✅ **PARTIAL** | Show 7 required docs, collect uploads | Likely in app portal |
| **8** | Requirement Verification Form | P3 | Records Officer | ⚠️ PARTIAL | Staff verify each document | Maybe in modal |
| **9** | Document Management Dashboard | P3 | Records Officer | ⚠️ PARTIAL | Overview of all applicant docs | Dashboard exists |

---

### **PROCESS 4: APPROVAL ROUTING (4 Screens)**

| # | Screen Name | Process | Actor | Status | Purpose | Sketch |
|---|-------------|---------|-------|--------|---------|--------|
| **10** | **Supporting Services Form** | **P4** | **Records Officer** | **❌ MISSING** | **Notarial + Engineering coordination** | **New form needed** |
| **11** | Signatory Routing Tracker | P4 | All staff | ✅ **EXISTS** | Show application routing status | Dashboard (PHASE 1) |
| **12** | OIC Pending Signature Widget | P4 | Victor (OIC) | ✅ **EXISTS** | Applications awaiting OIC signature | OIC dashboard |
| **13** | Head Pending Signature Widget | P4 | Arthur (Head) | ✅ **EXISTS** | Applications awaiting Head signature | Head dashboard |

---

### **PROCESS 5: STANDBY QUEUE (2 Screens)**

| # | Screen Name | Process | Actor | Status | Purpose | Sketch |
|---|-------------|---------|-------|--------|---------|--------|
| **14** | Standby Queue Display | P5 | Jocel, Joie | ⚠️ PARTIAL | Show approved applicants waiting for lots | Dashboard shows counts |
| **15** | Queue Position Management | P5 | System | ⚠️ PARTIAL | Auto-rank priority vs walk-in | Automated, no UI needed |

---

### **PROCESS 6: UNIT AWARDING (4 Screens)**

| # | Screen Name | Process | Actor | Status | Purpose | Sketch |
|---|-------------|---------|-------|--------|---------|--------|
| **16** | **Lot Awarding Draw - Split Screen** | **P6** | **Jocel (4th Member)** | **❌ CRITICAL** | **Assign standby applicants to vacant units** | **NEW: Left panel (applicants) + Right panel (units)** |
| **17** | Unit Availability Updater | P6 | Jocel | ⚠️ PARTIAL | Mark units as vacant/available | May be in admin |
| **18** | Keys & Turnover Checklist | P6 | Jocel | ❌ MISSING | Contract signing + key handover | Physical process |
| **19** | Lot Award Confirmation Letter | P6 | System | ⚠️ PARTIAL | Generate award notice | May auto-generate |

---

### **PROCESS 7: ELECTRICITY MONITORING (2 Screens)**

| # | Screen Name | Process | Actor | Status | Purpose | Sketch |
|---|-------------|---------|-------|--------|---------|--------|
| **20** | Electricity Connection Tracker | P7 | Joie, Laarni (5th) | ⚠️ PARTIAL | Track Negros Power application status | Dashboard shows it |
| **21** | Electricity Update Form | P7 | Laarni | ❌ MISSING | Record coordination updates | Needs manual entry form |

---

### **PROCESS 8: OCCUPANCY VALIDATION (3 Screens)**

| # | Screen Name | Process | Actor | Status | Purpose | Sketch |
|---|-------------|---------|-------|--------|---------|--------|
| **22** | **Occupancy Report Form** | **P8** | **Arcadio (Caretaker)** | **❌ MISSING** | **Weekly: Mark units as occupied/vacant/concern** | **NEW: Mobile-friendly web form (crossplatform)** |
| **23** | **Occupancy Review Form** | **P8** | **Field Officers (Paul, Nonoy, Roberto)** | **❌ MISSING** | **Review + validate caretaker's report** | **NEW: Show flagged units, confirm/override** |
| **24** | Unit Status Dashboard | P8 | All staff | ✅ **EXISTS** | Overview of occupancy rates | Dashboard (PHASE 2) |

---

### **PROCESS 9: COMPLIANCE & REPOSSESSION (5 Screens)**

| # | Screen Name | Process | Actor | Status | Purpose | Sketch |
|---|-------------|---------|-------|--------|---------|--------|
| **25** | **Compliance Notice Issuance Form** | **P9** | **Joie (2nd Member)** | **❌ CRITICAL** | **Create 30-day or 10-day notices** | **NEW: Select unit + reason + deadline** |
| **26** | Compliance Notice Tracker | P9 | Joie, Field Officers | ✅ **EXISTS** | Show active notices + deadlines | Dashboard (PHASE 2) |
| **27** | Response Submission Form | P9 | Beneficiary | ❌ MISSING | Upload explanation letter | Applicant portal feature |
| **28** | Repossession Decision Form | P9 | Victor (OIC) / Arthur (Head) | ❌ MISSING | Approve/deny repossession | Modal or dedicated form |
| **29** | Blacklist Entry Form | P9 | Victor/Arthur | ⚠️ PARTIAL | Tag beneficiary as blacklisted | Manual, may need UI |

---

### **PROCESS 10: COMPLAINT MANAGEMENT (4 Screens)**

| # | Screen Name | Process | Actor | Status | Purpose | Sketch |
|---|-------------|---------|-------|--------|---------|--------|
| **30** | **Case Creation Form** | **P10** | **Field Officers (Paul, Nonoy)** | **❌ MISSING** | **Log complaint/violation + assign type** | **NEW: Intake details + case type + description** |
| **31** | Case Investigation Form | P10 | Field Officers | ❌ MISSING | Record findings + add investigation notes | Modal for updates |
| **32** | Case Referral Form | P10 | Field Officers | ❌ MISSING | Route to City Engineering / OIC / Head | Decision buttons |
| **33** | Case Resolution Form | P10 | Victor/Arthur | ❌ MISSING | Final decision + closure | Modal decision interface |

---

### **PROCESS 11: ANALYTICS & REPORTING (3 Screens)**

| # | Screen Name | Process | Actor | Status | Purpose | Sketch |
|---|-------------|---------|-------|--------|---------|--------|
| **34** | **Reports Export Form** | **P11** | **Joie (Documentation Officer)** | **❌ MISSING** | **Export analytics as PDF/CSV** | **NEW: Date range + report type selectors** |
| **35** | Analytics Dashboard | P11 | All staff (role-specific) | ✅ **EXISTS** | System metrics + performance indicators | Dashboard (PHASE 1 + PHASE 2) |
| **36** | Barangay Demand Analysis | P11 | Field Officers | ⚠️ PARTIAL | Intake by barangay/location | Dashboard shows it |

---

## 🎯 THE 8 ABSOLUTELY CRITICAL UIs (DO THESE FIRST)

### **Tier 1: BLOCKS END-TO-END WORKFLOW** (Must build first)

| Priority | UI # | Name | Process | Blocker | Reason |
|----------|------|------|---------|---------|---------|
| **🔴 #1** | **#3** | **Eligibility Screening Form** | **P2** | **Cannot mark applicants eligible, start queue** | Eligibility is gate for everything |
| **🔴 #2** | **#16** | **Lot Awarding Draw** | **P6** | **Cannot assign units to applicants** | Without this, approved applicants stuck |
| **🔴 #3** | **#25** | **Compliance Notice Issuance** | **P9** | **Cannot issue notices for non-compliance** | Post-award monitoring impossible |
| **🔴 #4** | **#10** | **Supporting Services Form** | **P4** | **Cannot track notarial/engineering progress** | Delays before routing |

---

### **Tier 2: OPERATIONS MONITORING** (High impact)

| Priority | UI # | Name | Process | Blocker | Reason |
|----------|------|------|---------|---------|---------|
| **🟠 #5** | **#22** | **Occupancy Report Form** | **P8** | **No weekly caretaker input** | Caretaker has no way to report |
| **🟠 #6** | **#23** | **Occupancy Review Form** | **P8** | **Field officers can't validate reports** | Flagged units go unreviewed |
| **🟠 #7** | **#30** | **Case Creation Form** | **P10** | **No complaint logging system** | Issues get lost |
| **🟠 #8** | **#34** | **Reports Export** | **P11** | **Cannot generate accomplishment reports** | No documentation for management |

---

## 📐 IMPLEMENTATION ROADMAP

### **WEEK 1: UNBLOCK CORE WORKFLOW**
```
Day 1-2: UI #3 (Eligibility Screening Form)
         ├─ Blacklist check (auto)
         ├─ Property verification input
         ├─ Income verification input
         ├─ Household member lock confirmation
         └─ Decision buttons (ELIGIBLE / DISQUALIFY)

Day 3-4: UI #16 (Lot Awarding Draw - Split Screen)
         ├─ Left: Standby applicants (priority-ordered)
         ├─ Right: Vacant housing units
         ├─ Drag-drop or select assignment
         └─ [CONFIRM AWARDS] button

Day 5: UI #10 (Supporting Services Form)
       ├─ Notarial tracking (status: pending→done)
       ├─ Engineering tracking (status: pending→done)
       └─ [SEND TO ROUTING] button
```

### **WEEK 2: POST-AWARD MANAGEMENT**
```
Day 1-2: UI #25 (Compliance Notice Issuance)
         ├─ Select non-compliant unit
         ├─ Choose reason + notice type
         ├─ Auto-calculate deadline
         └─ SMS preview + [ISSUE] button

Day 3-4: UI #22 (Occupancy Report Form)
         ├─ Mobile-friendly web form (crossplatform)
         ├─ List units: mark occupied/vacant/concern
         └─ [SUBMIT REPORT] button

Day 5: UI #23 (Occupancy Review)
       ├─ Show submitted reports
       ├─ Field officer can confirm/override
       └─ Auto-trigger compliance notice if needed
```

### **WEEK 3: COMPLAINT & REPORTING**
```
Day 1-2: UI #30 (Case Creation Form)
         ├─ Complainant info
         ├─ Case type dropdown (8 types)
         ├─ Description textarea
         └─ [CREATE CASE] button

Day 3-4: UI #34 (Reports Export)
         ├─ Date range pickers
         ├─ Report type checkboxes
         ├─ [Export PDF] + [Export CSV] buttons
         └─ Server-side generation

Day 5: Testing + Refinements
```

---

## 🔍 DETAILED SPECS FOR EACH FORM

### **UI #3: ELIGIBILITY SCREENING FORM - CRITICAL**

```
┌────────────────────────────────────────────────────────────┐
│    INCOME & PROPERTY ELIGIBILITY SCREENING FORM            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ APPLICANT: Maria Cruz (APP-20260325-1111)                │
│ CHANNEL: Danger Zone (Certified ✅)                        │
│                                                            │
│ ══════════════════════════════════════════════════════   │
│ STEP 1: BLACKLIST CHECK (Auto)                           │
│ ══════════════════════════════════════════════════════   │
│ ✅ NOT ON BLACKLIST                                       │
│    Maria Cruz is not permanently disqualified.           │
│                                                            │
│ ══════════════════════════════════════════════════════   │
│ STEP 2: PROPERTY OWNERSHIP VERIFICATION                  │
│ ══════════════════════════════════════════════════════   │
│ Have you checked Assessor's Office for property?         │
│ ◉ NO property owned (✅ PASS)                             │
│ ◯ YES property owned (❌ DISQUALIFY)                      │
│ ◯ NOT YET CHECKED                                         │
│                                                            │
│ ══════════════════════════════════════════════════════   │
│ STEP 3: INCOME VERIFICATION                              │
│ ══════════════════════════════════════════════════════   │
│ Declared Income: ₱8,500/month  (✅ ≤ ₱10,000 limit)     │
│ Verify with applicant?  Monthly Income: [₱8,500]        │
│                                                            │
│ ══════════════════════════════════════════════════════   │
│ STEP 4: HOUSEHOLD COMPOSITION LOCK                       │
│ ══════════════════════════════════════════════════════   │
│ ✅ LOCKED: Maria Cruz (1 person)                         │
│    Household cannot be modified after eligibility        │
│                                                            │
│ ══════════════════════════════════════════════════════   │
│ DECISION:                                                 │
│ ◉ ELIGIBLE → Priority Queue Position 15                  │
│ ◯ DISQUALIFY → [Reason ▼]                                │
│                                                            │
│ Notes: _________________________________               │
│                                                            │
│ [ MARK ELIGIBLE ] [ MARK DISQUALIFIED ] [ CANCEL ]      │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**Backend Logic**:
- Query: `Blacklist.objects.filter(full_name=...)`
- Input: Property ownership (yes/no), Income (decimal)
- Calculate: Queue position (priority=1-20, walkin=21+)
- SMS: Eligibility result to applicant
- Next: QueueEntry created

---

### **UI #16: LOT AWARDING DRAW - SPLIT SCREEN - CRITICAL**

```
┌──────────────────────────┬──────────────────────────┐
│   STANDBY APPLICANTS     │    VACANT HOUSING UNITS   │
├──────────────────────────┼──────────────────────────┤
│ Priority Queue (1-20):   │ GK CABATANGAN:           │
│                          │                          │
│ [1] Maria Cruz (45F)     │ ☐ Block 5, Lot 12        │
│     Household: 1         │ ☐ Block 5, Lot 13        │
│     Income: ₱8,500 ✅    │ ☐ Block 6, Lot 8         │
│     ASSIGN: [Block 6 L8] │ ☐ Block 6, Lot 9         │
│                          │ ☐ Block 7, Lot 5         │
│ [2] Juan Santos (38M)    │ ☐ Block 7, Lot 6         │
│     Household: 3         │ ☐ Block 8, Lot 1         │
│     Income: ₱9,200 ✅    │ ☐ Block 8, Lot 2         │
│     ASSIGN: [_______▼]   │                          │
│                          │ SELECTED:                │
│ [3] Rosa Garcia (52F)    │ ├─ Block 6, L8: Maria C  │
│     Household: 4         │ ├─ Block 7, L5: Juan S   │
│     Income: ₱7,800 ✅    │ └─ [Waiting...]          │
│     ASSIGN: [_______▼]   │                          │
│                          │ STATS:                   │
│ Walk-in FIFO:            │ Standby: 23              │
│ [4] Anna Lopez (35F)     │ Vacant: 8                │
│     ...                  │ Ready: 3/23              │
│                          │                          │
│ [CONFIRM AWARDS]         │                          │
│ [CLEAR SELECTIONS]       │                          │
│ [CANCEL]                 │                          │
│                          │                          │
└──────────────────────────┴──────────────────────────┘
```

**Backend Logic**:
- Query: `QueueEntry.objects.filter(status='active').order_by('position')`
- Query: `HousingUnit.objects.filter(status='vacant')`
- Create: `LotAward(application, unit, awarded_at, awarded_by)`
- Create: `ElectricityConnection(lot_award)`
- Update: `HousingUnit.status = 'occupied'`
- SMS: Award notice to beneficiaries

---

### **UI #25: COMPLIANCE NOTICE ISSUANCE - CRITICAL**

```
┌───────────────────────────────────────────────────────┐
│   COMPLIANCE NOTICE ISSUANCE FORM (M4)                │
├───────────────────────────────────────────────────────┤
│                                                       │
│ UNIT: [ GK Cabatangan - Block 5, Lot 15 ]           │
│       Search: [Block/Lot ______]                      │
│                                                       │
│ BENEFICIARY: Maria Cruz (APP-20260115-0001)          │
│ STATUS: Unoccupied (flagged by caretaker 4/13)      │
│                                                       │
│ REASON FOR NOTICE:                                    │
│ ☐ Nonpayment of Association Dues                     │
│ ☐ Unauthorized Occupant                              │
│ ☐ Structural Damage / Neglect                        │
│ ☐ Illegal Structure / Modification                  │
│ ☐ Unoccupied / Abandoned                             │
│ ☐ Other: ____________________                        │
│                                                       │
│ NOTICE TYPE:                                          │
│ ◉ 30-Day Reminder Notice                             │
│   Deadline: June 10, 2026 (30 days)                 │
│                                                       │
│ ◯ 10-Day Final Notice                                │
│   Deadline: April 21, 2026 (10 days)                │
│                                                       │
│ Description:                                          │
│ [Unit unoccupied for 8+ weeks per weekly reports]   │
│                                                       │
│ SMS PREVIEW:                                          │
│ ⚠️  COMPLIANCE NOTICE                                 │
│ Unit Block 5, Lot 15                                 │
│ Reason: Unoccupied/Abandoned                         │
│ Deadline: June 10, 2026 (30 days)                   │
│ Contact THA immediately.                             │
│                                                       │
│ [ ISSUE NOTICE ] [ SAVE DRAFT ] [ CANCEL ]          │
│                                                       │
└───────────────────────────────────────────────────────┘
```

**Backend Logic**:
- Create: `ComplianceNotice(lot_award, unit, notice_type, deadline, reason)`
- Update: `HousingUnit.status = 'notice_30'` (or `'notice_10'`)
- SMS: Issue notice message to beneficiary
- SMS: Notify field team of flagged unit

---

### **UI #22: OCCUPANCY REPORT FORM - CROSSPLATFORM WEB**

```
┌──────────────────────────┐
│ 📋 WEEKLY OCCUPANCY REPORT
│ Week 4: Apr 7-13, 2026   │
├──────────────────────────┤
│                          │
│ GK CABATANGAN            │
│                          │
│ ☐ Block 5, Lot 12 🟢     │
│ ☐ Block 5, Lot 13 🔴     │
│ ☐ Block 5, Lot 14 🟡     │
│   Note: [locked down?]   │
│ ☐ Block 5, Lot 15 🟢     │
│ ☐ Block 5, Lot 16 🟢     │
│ ☐ Block 6, Lot 1 🔴      │
│ ☐ Block 6, Lot 2 🟢      │
│ ☐ Block 6, Lot 3 🟢      │
│                          │
│ SUMMARY:                 │
│ ✅ Occupied: 6           │
│ ⚠️  Concern: 1           │
│ ❌ Vacant: 1             │
│                          │
│ [ SUBMIT REPORT ]        │
│ [ SAVE DRAFT ]           │
│ [ CANCEL ]               │
│                          │
└──────────────────────────┘
```

**Backend Logic**:
- Create: `OccupancyReport(site, week_start, week_end)`
- Create: `OccupancyReportDetail(report, unit, status)` ×N
- SMS: Notify field officers of flagged units
- Update: Counts (occupied, vacant, concern)

---

## ✅ NEXT IMMEDIATE ACTION

**Ready to start implementing UI #3 (Eligibility Screening)?**

I can provide:
1. **Complete HTML/CSS** for the form (matched to existing design)
2. **Django view** to handle form submission
3. **JavaScript** for dynamic field showing (blacklist auto-check)
4. **Test cases** to verify functionality
5. **Integration points** with existing queue system

Which UI would you like to tackle first? 🚀

