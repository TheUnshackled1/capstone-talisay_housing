# Role-Based Dashboard Implementation
## Talisay City Housing Authority - IHSMS

**Date Created:** 2026-04-03  
**Developer Reference:** Staff Dashboard System

---

## Overview

The IHSMS dashboard system provides **role-specific interfaces** for each THA staff member. Each user sees widgets, statistics, and action items relevant to their official responsibilities as defined in the system modules documentation.

## Architecture

### Dynamic Dashboard Approach
- **One main template** (`dashboard.html`) with role-based widget includes
- **Role-specific widget partials** for each staff position
- **Context data** customized per role in `accounts/views.py`
- **Shared CSS** for consistent styling across all dashboards

### File Structure

```
templates/accounts/
├── dashboard.html                    # Main dashboard template (base)
├── dashboard_head.html              # Widgets for Arthur Maramba (Head)
├── dashboard_oic.html               # Widgets for Victor Fregil (OIC)
├── dashboard_second_member.html     # Widgets for Joie Tingson
├── dashboard_third_member.html      # Widgets for Jay Olvido
├── dashboard_fourth_member.html     # Widgets for Jocel Cuaysing
└── dashboard_fifth_member.html      # Widgets for Laarni Hellera

static/css/
├── dashboard.css                    # Base dashboard styles
└── dashboard_widgets.css            # Widget-specific styles
```

---

## Staff Dashboard Breakdown

### 1. **Arthur Benjamin S. Maramba** (Head / First Member)
**Position:** `head`  
**Modules:** M2 (final signatory), M6 (receives reports)

**Dashboard Widgets:**
- ✅ **Awaiting Your Signature** - Applications pending final approval
- ✅ **System Overview** - Total applicants, approvals, units, occupancy rate
- ✅ **Analytics & Reports** - Recent reports with download links

**Stats Cards:**
- Total Applicants
- Awaiting Signature
- Housing Units
- Monthly Reports

**Primary Actions:**
- Sign Applications (final approval)
- View Analytics Dashboard

---

### 2. **Victor M. Fregil** (OIC-THA)
**Position:** `oic`  
**Modules:** M2 (OIC signatory), M4 (compliance decisions), M5 (escalated complaints)

**Dashboard Widgets:**
- ✅ **Awaiting OIC Signature** - Applications pending OIC approval
- ✅ **Compliance Cases** - Units flagged for non-compliance
- ✅ **Escalated Cases** - Complaints requiring OIC decision
- ✅ **This Month's Activity** - Applications signed, decisions made, cases resolved

**Stats Cards:**
- Total Applicants
- Awaiting Signature
- Compliance Cases
- Escalated Complaints

**Primary Actions:**
- Review & Sign Applications
- Decide on Compliance Cases
- Review Escalated Complaints

---

### 3. **Lourynie Joie V. Tingson** (Second Member)
**Position:** `second_member`  
**Modules:** M2 (notices, electricity), M3 (docs oversight), M4 (compliance notices), M6 (reports)

**Dashboard Widgets:**
- ✅ **Priority Tasks** - Compliance notices to prepare
- ✅ **Electricity Connections** - Connection tracking with progress bars
- ✅ **Document Oversight** - Applicants with incomplete documents
- ✅ **Upcoming Reports** - Reports due for Full Disclosure Portal

**Stats Cards:**
- Total Applicants
- Pending Notices
- Electricity Pending
- Incomplete Documents

**Primary Actions:**
- Prepare Compliance Notices
- Track Electricity Connections
- Monitor Document Completeness
- Generate Reports

---

### 4. **Jocel O. Cuaysing** (Fourth Member)
**Position:** `fourth_member`  
**Modules:** M1 (masterlist, eligibility, queue), M2 (requirements, lot awarding), M3 (documents), M4 (property custodian)

**Dashboard Widgets:**
- ✅ **Priority Queue** - CDRRMO-certified and landowner-endorsed applicants
- ✅ **Walk-in FIFO Queue** - Regular walk-in applicants by queue number
- ✅ **Pending CDRRMO Certification** - Danger zone applicants awaiting certification (with aging flags)
- ✅ **Incomplete Requirements** - 7-requirements checklist progress per applicant
- ✅ **Lot Awarding** - Available lots, standby queue, ready-to-award count
- ✅ **Property Custodian** - Blacklist count, repossessed units

**Stats Cards:**
- Queue Today
- Incomplete Requirements
- Documents Filed
- Lots for Awarding

**Primary Actions:**
- Register Applicant
- Check Requirements (7-step checklist)
- Manage Queue
- Lot Awarding

**Key Features:**
- **Aging alerts** for CDRRMO pending > 14 days
- **Progress bars** for requirements completion (X/7)
- **Awarding readiness** summary (available lots vs standby queue)

---

### 5. **Roland Jay S. Olvido** (Third Member)
**Position:** `third_member`  
**Modules:** M1 (census, field verification), M2 (signatory routing), M4 (site inspection), M5 (violation investigation)

**Dashboard Widgets:**
- ✅ **Signatory Routing** - Documents in routing (Ready for OIC → With OIC → Ready for Head → With Head)
- ✅ **Field Verification** - Applicants needing field verification
- ✅ **Site Inspections** - Scheduled inspections with date, location, purpose
- ✅ **Violation Investigations** - Active investigation cases

**Stats Cards:**
- Census Records
- Pending Verification
- Site Inspections
- Open Investigations

**Primary Actions:**
- Route Documents (OIC → Head)
- Schedule Field Verification
- Conduct Site Inspection
- Update Investigation

**Key Features:**
- **Status tracking** for document routing stages
- **Calendar view** for inspection schedule
- **Investigation tracking** with days-open counter

---

### 6. **Laarni C. Hellera** (Fifth Member)
**Position:** `fifth_member`  
**Modules:** M2 (electricity connection tracking)

**Dashboard Widgets:**
- ✅ **Connection Queue** - Electricity applications with 4-step progress (Docs → NPC → Approved → Connected)
- ✅ **Pending with Negros Power** - Applications submitted to Negros Power with aging flags
- ✅ **This Month's Progress** - Connections completed, documents submitted, pending connections

**Stats Cards:**
- Pending Connections
- Connected This Month
- Awaiting Negros Power
- Monthly Notices

**Primary Actions:**
- New Connection Request
- Track Status with Negros Power
- Mark Connected
- Generate Monthly Report

**Key Features:**
- **4-step progress visualization** (Docs → NPC → Approved → Connected)
- **Aging alerts** for applications > 30 days with Negros Power
- **Card-based layout** for quick status overview

---

## Usage

### For Testing

**Login as different users to see role-specific dashboards:**

| Username | Password | Position | Dashboard Features |
|----------|----------|----------|-------------------|
| `arthur.maramba` | `tha2026` | Head | Final approvals, analytics |
| `victor.fregil` | `tha2026` | OIC | OIC approvals, compliance decisions |
| `joie.tingson` | `tha2026` | Second Member | Notices, electricity, reports |
| `jay.olvido` | `tha2026` | Third Member | Routing, verification, inspections |
| `jocel.cuaysing` | `tha2026` | Fourth Member | Queue, requirements, lot awarding |
| `laarni.hellera` | `tha2026` | Fifth Member | Electricity connections only |

---

## Implementation Status

### ✅ Completed
- [x] Main dashboard template with role detection
- [x] Role-specific widget templates (6 staff members)
- [x] Comprehensive CSS for all widget patterns
- [x] Role-based stats cards
- [x] Role-based quick actions
- [x] Dynamic widget inclusion system
- [x] Context structure in `views.py`

### 🔄 To Do (Connected to Module Development)
- [ ] Connect widgets to actual database queries (Module 1-6 models)
- [ ] Implement SMS notification triggers
- [ ] Add real-time updates via WebSockets (optional)
- [ ] Implement pagination for long lists
- [ ] Add export/print functionality for reports

---

**End of Documentation**
