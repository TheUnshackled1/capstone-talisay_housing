# IHSMS DETAILED DATA FLOW DIAGRAM & ACTOR EXPLANATION
## Talisay City Housing Authority System

---

## SYSTEM OVERVIEW: THE BIG PICTURE

**Who Uses It**: 11 THA staff members (read-only: beneficiaries via SMS only)
**When It's Used**: Every working day, 365 days/year
**Why It Exists**: Replace 100% paper-based processes with one centralized database
**How Long**: From ISF registration → 4-6 years until lot is awarded → lifetime monitoring

---

## PART 1: SYSTEM ENTRY POINTS (3 Ways to Enter)

### ENTRY POINT A: LANDOWNER WEB PORTAL
```
┌──────────────────────────────────────────────────────────────┐
│ LANDOWNER (Outside System) - Sir Juan owns property at Brgy X │
│                                                               │
│ Action: Opens simple web form on phone/computer              │
│ Enters: His name + address + list of ISFs living on property │
│         (Names, household size, income, years residing)       │
└──────────────────────────────────────────────────────────────┘
                             ↓
                    [SYSTEM RECEIVES]
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ SYSTEM AUTOMATICALLY:                                         │
│ 1. Creates applicant profile for EACH ISF in the list        │
│ 2. Assigns unique reference number (ISF-2026-00001, etc)     │
│ 3. Records: Name, barangay, household size, income, channel  │
│ 4. Sets status: "Entry via Landowner - Pending Eligibility"  │
│ 5. SENDS SMS: "Your name was submitted... Reference: XXXX"   │
│                                                               │
│ REASON WHY:                                                   │
│ - Landowner no longer needs to visit office with paper list   │
│ - System creates profile instantly vs. weeks of encoding time │
│ - Applicant gets confirmation that entry was successful       │
└──────────────────────────────────────────────────────────────┘
                             ↓
           [DATA NOW IN SYSTEM DATABASE]
              (Waiting for next step)
```

### ENTRY POINT B: WALK-IN DANGER ZONE
```
┌──────────────────────────────────────────────────────────────┐
│ APPLICANT walks into office & says:                          │
│ "I live in a flood-prone area (Danger Zone)"                 │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ JOCEL CUAYSING (Fourth Member) - Records Officer             │
│                                                               │
│ WHY JOCEL? She is the Queue & Records Manager                │
│                                                               │
│ Actions:                                                      │
│ 1. Opens system and creates applicant profile                │
│ 2. Enters: Name, barangay, household size, income            │
│ 3. TAGS: "Pending CDRRMO Certification" (critical!)          │
│ 4. Records: Date claimed, declared location (riverbank, etc) │
│ 5. Status: "Walk-in Danger Zone - CDRRMO Pending"            │
│                                                               │
│ REASON WHY THIS TAG MATTERS:                                 │
│ - CDRRMO must physically visit location to certify           │
│ - System flags this applicant differently from regular       │
│ - If certified → Priority Queue (served FIRST)               │
│ - If NOT certified → Regular Walk-in Queue (FIFO)            │
└──────────────────────────────────────────────────────────────┘
                             ↓
           [SYSTEM HOLDS APPLICANT IN PENDING STATE]
                      ↓
            JOCEL COORDINATES WITH CDRRMO
          (Phone call - outside system - unchanged)
                      ↓
         CDRRMO VISITS LOCATION (outside system)
      Decides: "YES, this is a danger zone" OR "NO, not danger"
                      ↓
    CDRRMO GIVES PAPER CERTIFICATION TO JOCEL
                      ↓
         JOCEL OPENS APPLICANT PROFILE AND UPDATES:
┌──────────────────────────────────────────────────────────────┐
│ IF CDRRMO CERTIFIED "YES":                                    │
│ - Status changes: "Certified Danger Zone - Priority Queue"    │
│ - Queue placement: TOP of priority queue (guaranteed first)   │
│ - SMS sent: "Your location certified. You're on priority list"│
│                                                               │
│ IF CDRRMO CERTIFIED "NO":                                     │
│ - Status changes: "Not Certified - Walk-in FIFO Queue"        │
│ - Queue placement: Regular walk-in queue (first-come-first)   │
│ - SMS sent: "Location not certified. Queue number: #42"       │
│                                                               │
│ IF STILL PENDING AFTER 14 DAYS:                              │
│ - System automatically FLAGS for Jocel to follow up           │
│ - Jocel calls CDRRMO: "Where's the result for this person?"   │
│ - Applicant not forgotten because system shows red flag       │
└──────────────────────────────────────────────────────────────┘
```

### ENTRY POINT C: REGULAR WALK-IN
```
┌──────────────────────────────────────────────────────────────┐
│ APPLICANT walks in and says:                                 │
│ "I need housing assistance" (no danger zone claim)            │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ JOCEL CUAYSING - Record this walk-in applicant               │
│                                                               │
│ Actions:                                                      │
│ 1. Creates profile with: Name, barangay, household size       │
│ 2. NO "Pending CDRRMO" tag (this person didn't claim danger)  │
│ 3. Status: "Walk-in FIFO Queue - Registered"                 │
│ 4. Queue position: Assigned next available queue number       │
│ 5. SMS sent: "Registered. Your queue #: 87. Reference: XXXX"  │
│                                                               │
│ REASON WHY:                                                   │
│ - Applicant now knows their position in line                  │
│ - System prevents double-registration (paper folders = chaos) │
│ - Queue is transparent (no favoritism)                        │
└──────────────────────────────────────────────────────────────┘
```

---

## PART 2: ELIGIBILITY SCREENING (The Filter)

After ANY entry point (A, B, or C above), applicant must pass eligibility check.

```
┌──────────────────────────────────────────────────────────────┐
│ APPLICANT PROFILE NOW IN SYSTEM (any entry point)             │
│ Status: "Pending Eligibility Screening"                       │
└──────────────────────────────────────────────────────────────┘
                             ↓
        SYSTEM PERFORMS AUTOMATIC BLACKLIST CHECK
┌──────────────────────────────────────────────────────────────┐
│ System checks: Does applicant's name match anyone who:        │
│ - Was previously repossessed (non-compliant)                 │
│ - Is permanently disqualified                                │
│ - Has been blacklisted before                                │
│                                                               │
│ IF MATCH FOUND:                                               │
│ - System BLOCKS further processing instantly                  │
│ - Applicant marked: "DISQUALIFIED - Blacklisted"             │
│ - SMS sent: "You are ineligible. Reason: previous record"     │
│ - Record locked - cannot reapply                              │
│                                                               │
│ REASON WHY:                                                   │
│ - Prevents people who lost unit through non-compliance        │
│ - One person can't apply multiple times under different names │
│ - Protects THA's award integrity                              │
└──────────────────────────────────────────────────────────────┘
                             ↓
        [IF NO BLACKLIST MATCH: Continue to next check]
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ JOCEL VERIFIES PROPERTY OWNERSHIP (Manual - Assessor Office)  │
│                                                               │
│ Actions:                                                      │
│ 1. Calls or visits Assessor's Office                          │
│ 2. Checks: Does applicant or any household member own         │
│    property in Talisay City?                                  │
│ 3. If OWNS property: Applicant DISQUALIFIED immediately      │
│    (reason: has resources, doesn't need housing assistance)  │
│ 4. Records result in system: "Own property at Brgy X"         │
│                                                               │
│ REASON WHY:                                                   │
│ - Socialized housing for poor, not for property owners        │
│ - Prevents wealthy from getting double benefit                │
│ - Fair allocation to truly needy families                     │
└──────────────────────────────────────────────────────────────┘
                             ↓
        [IF OWNS PROPERTY: STOP - Disqualified]
        [IF NO PROPERTY: Continue to next check]
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ JOCEL VERIFIES MONTHLY INCOME (Manual - form review)          │
│                                                               │
│ Actions:                                                      │
│ 1. Applicant shows income proof (payslip, receipts, sworn)    │
│ 2. Jocel records: Monthly income amount                       │
│ 3. If income EXCEEDS PHP 10,000/month: DISQUALIFIED          │
│ 4. If income OK: Record passes                                │
│                                                               │
│ REASON WHY:                                                   │
│ - Program limited to families earning ≤ PHP 10,000/month      │
│ - Targets ultra-poor, not middle class                        │
│ - Limited lots mean must prioritize poorest                   │
└──────────────────────────────────────────────────────────────┘
                             ↓
        [IF INCOME TOO HIGH: STOP - Disqualified]
        [IF INCOME OK: Continue to household check]
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ JOCEL LOCKS HOUSEHOLD COMPOSITION INTO PROFILE (Critical!)    │
│                                                               │
│ Actions:                                                      │
│ 1. Records EVERY family member living in current household:   │
│    Names of spouse (if any), ALL children, others living      │
│ 2. THIS IS LOCKED IN SYSTEM - cannot change later             │
│ 3. When awarded: ONLY these people can legally live in unit   │
│                                                               │
│ REASON WHY:                                                   │
│ - Prevents "loaning" unit to relatives                        │
│ - Prevents renting unit to outsiders                          │
│ - Prevents selling unit informally                            │
│ - Keeps unit for beneficiary family only                      │
│ - THA can enforce: "You can't add new people" rule            │
│ - System shows WHO is supposed to live there                  │
└──────────────────────────────────────────────────────────────┘
                             ↓
        [IF ALL 3 CHECKS PASS: Proceed to queue]
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ SYSTEM PLACES APPLICANT IN CORRECT QUEUE (Type depends on    │
│ entry method + CDRRMO result if applicable)                  │
│                                                               │
│ QUEUE PLACEMENT LOGIC:                                        │
│                                                               │
│ IF: Entry via Landowner + Passed Eligibility                 │
│     → PRIORITY QUEUE (served first when lots available)       │
│                                                               │
│ IF: Danger Zone + CDRRMO CERTIFIED + Passed Eligibility      │
│     → PRIORITY QUEUE (served first)                           │
│                                                               │
│ IF: Danger Zone + NOT CERTIFIED + Passed Eligibility         │
│     → WALK-IN FIFO QUEUE (first-come-first-served)            │
│                                                               │
│ IF: Regular Walk-in + Passed Eligibility                      │
│     → WALK-IN FIFO QUEUE (first-come-first-served)            │
│                                                               │
│ REASON FOR TWO QUEUES:                                        │
│ - Priority people (danger zone certified + landowner endorsed)│
│   are in most urgent housing need                             │
│ - Regular walk-ins are important but lower urgency            │
│ - System serves priority first, then walk-in FIFO             │
│ - When priority queue EMPTY → then serve walk-in queue        │
└──────────────────────────────────────────────────────────────┘
                             ↓
            SMS CONFIRMATION SENT TO APPLICANT
┌──────────────────────────────────────────────────────────────┐
│ "You passed eligibility. Please visit THA office to submit    │
│ your 7 required documents. Reference: XXXX"                   │
│                                                               │
│ REASON WHY SMS:                                               │
│ - Applicant now knows they're eligible (psychological win)    │
│ - Knows what to do next (bring 7 documents)                   │
│ - Has reference number for tracking                           │
│ - Can show SMS to office as proof of eligibility              │
└──────────────────────────────────────────────────────────────┘
```

---

## PART 3: DOCUMENT SUBMISSION & VERIFICATION (The Checklist)

```
┌──────────────────────────────────────────────────────────────┐
│ APPLICANT reads SMS and comes to office with documents        │
│ Brings (or brings some of) the 7 Required Documents:          │
│ 1. Barangay Certificate of Residency                         │
│ 2. Barangay Certificate of Indigency                         │
│ 3. Cedula (Community Tax Certificate)                        │
│ 4. Police Clearance                                          │
│ 5. Certificate of No Property (from Assessor)                │
│ 6. 2x2 Picture (recent photo)                                │
│ 7. Sketch of House Location (simple map)                     │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ JOCEL VERIFIES DOCUMENTS PHYSICALLY (In-person at office)     │
│                                                               │
│ Actions:                                                      │
│ 1. Opens applicant profile in system                          │
│ 2. System displays checklist with 7 boxes (unchecked)         │
│ 3. Examines EACH physical document                            │
│ 4. If document is OK: CLICKS THE BOX in system (checked ✓)    │
│ 5. Progress saved: Can see which items are done, which remain │
│                                                               │
│ Example:                                                      │
│ ✓ Barangay Certificate of Residency (verified)               │
│ ✓ Police Clearance (verified)                                │
│ ☐ Certificate of No Property (still needed)                  │
│ ☐ Cedula (still needed)                                      │
│ ✓ 2x2 Picture (verified)                                     │
│ ☐ Barangay Certificate of Indigency (still needed)           │
│ ☐ Sketch of House Location (still needed)                    │
│                                                               │
│ REASON WHY SYSTEM SAVES PARTIAL PROGRESS:                    │
│ - Applicant might visit 3 times before getting all 7          │
│ - If different staff member serves next applicant,            │
│   they see exactly which items are done                       │
│ - No need to say "Where's the barangay cert again?"           │
│ - Prevents re-doing verification work (saves time)            │
└──────────────────────────────────────────────────────────────┘
                             ↓
        [Applicant leaves with incomplete documents]
        [System saves progress - ready for next visit]
                             ↓
     [Applicant returns WEEKS LATER with remaining docs]
                             ↓
        [Different staff member (or same) opens profile]
        [System shows exactly which 4 items still needed]
        [No need to recheck the 3 already verified items]
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ EVENTUALLY: ALL 7 DOCUMENTS VERIFIED ✓                        │
│                                                               │
│ SYSTEM AUTOMATICALLY:                                         │
│ 1. UNLOCKS the application form                              │
│ 2. PRE-FILLS form with applicant data already in system:      │
│    - Name, barangay, household members, income, etc.         │
│ 3. Generates PDF for printing                                │
│ 4. Jocel prints the form                                     │
│ 5. Gives form to applicant to review and sign                │
│                                                               │
│ REASON WHY PRE-FILLED:                                        │
│ - Data already verified during eligibility check              │
│ - No duplicate data entry (reduces errors)                    │
│ - Saves applicant time (doesn't rewrite name, address, etc)   │
│ - Form is consistent with system data                         │
│ - Quality control: system review vs. handwriting errors       │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ APPLICANT SIGNS FORM AT OFFICE (in person)                  │
│                                                               │
│ Actions:                                                      │
│ 1. Applicant reviews pre-filled data                          │
│ 2. Confirms all information is correct                        │
│ 3. Signs the form in front of Jocel                           │
│ 4. Jocel updates system: "Form signed - Date: MM/DD/YYYY"     │
│ 5. Jocel asks: "Do you need notarial service?" or             │
│    "Engineering assessment?" for engineering works            │
│                                                               │
│ REASON WHY IN-PERSON:                                         │
│ - Signatures authenticate the form                            │
│ - Applicant sees data before signing (not later)              │
│ - THA confirms identity of signer                             │
│ - Prevents false applications                                 │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ JOCEL FACILITATES SUPPORTING SERVICES (if needed)             │
│                                                               │
│ Notarial Service:                                             │
│ - Jocel coordinates with notary or legal help                 │
│ - Often provided free or low-cost by THA connection           │
│ - When completed: System records "Notarial Service: Done"     │
│                                                               │
│ Engineering Assessment:                                      │
│ - For beneficiaries who'll do home improvements               │
│ - Engineer verifies structural plans/feasibility              │
│ - When completed: System records "Engineering: Done"          │
│                                                               │
│ REASON WHY SYSTEM TRACKS THIS:                               │
│ - Knows when applicant is ready for next stage                │
│ - Both services must complete before signatory routing        │
│ - Prevents sending incomplete applications to signatories     │
└──────────────────────────────────────────────────────────────┘
```

---

## PART 4: SIGNATORY ROUTING (The Approval Chain)

```
┌──────────────────────────────────────────────────────────────┐
│ APPLICATION NOW COMPLETE:                                     │
│ ✓ All 7 documents verified                                    │
│ ✓ Form signed by applicant                                    │
│ ✓ Notarial service complete (if applicable)                   │
│ ✓ Engineering complete (if applicable)                        │
│                                                               │
│ PHYSICAL DOCUMENT HANDED TO JAY (Third Member)                │
│ "Time to get approvals," Jocel says                           │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ WHY JAY? (Roland Jay S. Olvido - Third Member)               │
│                                                               │
│ Official Role: Signatory Routing Officer                      │
│ - Only person allowed to move applications through chain      │
│ - Responsible for tracking where each document is             │
│ - Records dates when forwarded and signed                     │
│ - Ensures no document gets stuck with a signatory             │
│                                                               │
│ RESPONSIBILITY:                                               │
│ 1. Keep physical document in hand or physically deliver       │
│ 2. Update system at EACH step with dates                      │
│ 3. Flag delays (if document sits >3 days)                     │
│ 4. Ensure chain is never broken                               │
└──────────────────────────────────────────────────────────────┘
                             ↓
        SIGNATORY CHAIN (3 signatories in order):
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ STEP 1: JAY = FIRST SIGNATORY (Third Member)                 │
│                                                               │
│ Actions:                                                      │
│ 1. Jay receives physical document from Jocel                  │
│ 2. Jay reviews: Are all 7 docs attached? Forms signed?        │
│ 3. If OK: Jay signs the application form                      │
│ 4. Jay updates system: "Signed by Third Member - MM/DD/YYYY"  │
│ 5. Jay forwards document to next signatory (OIC)              │
│ 6. Jay records in system: "Forwarded to OIC - MM/DD/YYYY"     │
│                                                               │
│ WHY JAY IS FIRST:                                             │
│ - Third Member=First signatory per official policy            │
│ - Jay processes all applications into system                  │
│ - Jay knows applicant's eligibility history                   │
│ - Jay signs off that documents are complete                   │
│ - Prevents incomplete applications from reaching next level    │
└──────────────────────────────────────────────────────────────┘
                             ↓
    [DOCUMENT PHYSICALLY TRAVELS TO NEXT SIGNATORY]
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ STEP 2: VICTOR FREGIL = OIC SIGNATORY                         │
│                                                               │
│ (Victor M. Fregil - Officer-in-Charge)                       │
│                                                               │
│ Actions:                                                      │
│ 1. Victor receives physical document from Jay                 │
│ 2. Reviews: Applicant qualified? All signings complete?       │
│ 3. If OK: Victor signs the application form                   │
│ 4. Victor returns physical document to Jay                    │
│ 5. Jay updates system: "Signed by OIC - MM/DD/YYYY"           │
│ 6. Jay records: "Forwarded to Head - MM/DD/YYYY"              │
│                                                               │
│ WHY OIC IS SECOND:                                            │
│ - Officer-in-Charge provides oversight                        │
│ - Catches processing errors before final signature            │
│ - Can delay if documentation incomplete                       │
│ - Represents authority level below Head                       │
│ - Known as middle checkpoint in approval chain                │
└──────────────────────────────────────────────────────────────┘
                             ↓
    [DOCUMENT PHYSICALLY TRAVELS TO FINAL SIGNATORY]
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ STEP 3: ARTHUR MARAMBA = HEAD (Final Signatory)              │
│                                                               │
│ (Arthur Benjamin S. Maramba - First Member / Head)            │
│                                                               │
│ Actions:                                                      │
│ 1. Arthur receives physical document from Jay                 │
│ 2. Reviews for final approval (authority check)               │
│ 3. Arthur signs the application form (FINAL SIGNATURE)        │
│ 4. Arthur returns physical document to Jay                    │
│ 5. Jay updates system: "Signed by Head - MM/DD/YYYY"          │
│ 6. SYSTEM AUTOMATICALLY CHANGES STATUS TO:                    │
│    "Fully Approved - Standing By for Lot Availability"        │
│                                                               │
│ WHY HEAD IS FINAL:                                            │
│ - Only person with authority to award housing                 │
│ - Confirms all three signatories have approved                │
│ - Highest level review before lot awarding                    │
│ - Can reject or request changes                               │
│ - When Head signs = Application 100% approved                 │
│ - No further approvals needed                                 │
└──────────────────────────────────────────────────────────────┘
```

### DELAY FLAGGING SYSTEM
```
┌──────────────────────────────────────────────────────────────┐
│ SYSTEM AUTOMATICALLY MONITORS DELAYS:                         │
│                                                               │
│ If document sits with ANY signatory for >3 days:              │
│ - System CREATES RED FLAG in dashboard                        │
│ - Shows which signatory is holding document                   │
│ - Shows how many days overdue                                 │
│ - OIC (Victor) sees this flag                                 │
│                                                               │
│ Example:                                                      │
│ Forwarded to Head on Day 1                                    │
│ No update by Day 4 = System flags: "DELAYED - 1 day overdue"  │
│ No update by Day 5 = System flags: "DELAYED - 2 days overdue" │
│                                                               │
│ REASON WHY AUTOMATIC FLAG:                                    │
│ - Currently no tracking → folders get lost on desks           │
│ - Applicant waits weeks without knowing application stuck     │
│ - No accountability for signatories                           │
│ - System forces attention = reduces processing time           │
│ - OIC can call signatory: "Where's this application?"         │
└──────────────────────────────────────────────────────────────┘
```

---

## PART 5: STANDBY QUEUE & LOT AWARDING

```
┌──────────────────────────────────────────────────────────────┐
│ ONCE FINAL SIGNATURE RECORDED:                                │
│ System automatically changes status to:                       │
│ "Fully Approved - Standby for Lot Availability"               │
│                                                               │
│ SMS sent to applicant:                                        │
│ "Your application approved! You're on the standby list.      │
│  We will contact you when a lot becomes available."           │
│                                                               │
│ REASON FOR STANDBY QUEUE:                                     │
│ - Lots are LIMITED (only ~500 at GK Cabatangan)               │
│ - Applications being processed continuously                   │
│ - At any moment: 200-300 approved applicants waiting          │
│ - System prioritizes: Priority queue first, then walk-in      │
│ - Fair line = whoever approved first = gets lot first         │
└──────────────────────────────────────────────────────────────┘
                             ↓
        [Applicant waits weeks/months for lot availability]
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ JOCEL MARKS LOTS AS AVAILABLE (when new lots confirmed)      │
│                                                               │
│ Scenario: THA acquires 10 new lots in GK Cabatangan           │
│                                                               │
│ Jocel's Actions:                                              │
│ 1. Confirms with property custodian: "These 10 lots OK"       │
│ 2. Updates system: "Available for awarding: 10 lots"          │
│ 3. System automatically surfaces next eligible applicant      │
│ 4. PRIORITY APPLICANTS listed in order                        │
│ 5. If priority queue empty: WALK-IN APPLICANTS listed         │
│                                                               │
│ SYSTEM SURFACES: Shows to staff: "These 10 applicants         │
│ are next in line. Prepare for lot awarding event."            │
│                                                               │
│ REASON WHY AUTOMATIC:                                         │
│ - Currently: No tracking of who's next                        │
│ - Jocel must manually search folders                          │
│ - Takes hours to find next 10 eligible people                 │
│ - System does instantly with correct priority order           │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ PRE-AWARDING VERIFICATION (for walk-in applicants only)       │
│                                                               │
│ Reason: Walk-in applicants submitted information (not         │
│ verified at intake). Priority applicants already verified.    │
│                                                               │
│ Field Team (Jay, Paul, Roberto, Nonoy) Actions:               │
│ 1. Visit applicant's current residence                        │
│ 2. Verify: Applicant still lives at declared address          │
│ 3. Verify: Household members still same (no additions)        │
│ 4. Verify: Living conditions as declared                      │
│ 5. Record findings in system: "Verified - ready to award"     │
│                                                               │
│ REASON WHY FIELD VERIFICATION:                                │
│ - Walk-ins not field-verified during intake                   │
│ - Could have moved since application                          │
│ - Could have added family members (changes priority)          │
│ - Could have lied about living conditions                     │
│ - Final check before commitment of housing                    │
│ - Prevents awarding to people no longer eligible              │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ LOT AWARDING EVENT (physical process - not system)             │
│                                                               │
│ Scenario: THA holds draw lots event with 10 eligible          │
│ applicants selected                                           │
│                                                               │
│ Process (OUTSIDE SYSTEM):                                     │
│ 1. Applications announced: "These 10 people selected "         │
│ 2. Applicants come forward one by one                         │
│ 3. Each applicant draws/selects their lot location            │
│    "I choose Block C, Lot 15"                                 │
│ 4. THA staff write down assignments on paper/whiteboard       │
│ 5. Event ends with assignments publicly announced             │
│                                                               │
│ Purpose: Fair, transparent, public process                    │
│ Prevents accusation of favoritism                             │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ JOCEL RECORDS ASSIGNMENTS IN SYSTEM (After event)             │
│                                                               │
│ Actions:                                                      │
│ 1. Opens applicant profile in system                          │
│ 2. Enters: Block assigned, Lot number, Date awarded           │
│ 3. Updates status: "Awarded - Block C, Lot 15"                │
│ 4. System AUTOMATICALLY:                                      │
│    - Links beneficiary profile to unit                        │
│    - Marks unit as "Occupied"                                 │
│    - Creates electricity connection section in profile        │
│ 5. SMS sent: "Congratulations! Block C, Lot 15. Report to    │
│    office within 5 days."                                     │
│                                                               │
│ REASON WHY SYSTEM RECORDING:                                  │
│ - Lot status now updated (was "Vacant", now "Occupied")       │
│ - Next standby applicant automatically identified             │
│ - Electricity tracking begins                                 │
│ - Occupancy data now tied to unit                             │
│ - One record = applicant + unit + status                      │
└──────────────────────────────────────────────────────────────┘
```

---

## PART 6: POST-AWARD ELECTRICITY TRACKING

```
┌──────────────────────────────────────────────────────────────┐
│ AFTER LOT AWARDED:                                            │
│ System adds "Electricity Connection" section to beneficiary    │
│ profile                                                        │
│                                                               │
│ LAARNI (Fifth Member) + JOIE (Second Member) Coordinate       │
│                                                               │
│ Team Effort: Both track electricity connection status:         │
│ - Joie prepares memos to Negros Power (her function)         │
│ - Laarni coordinates technical details with utility            │
│ - Both update system at same profile                          │
│                                                               │
│ Stages tracked in same profile:                               │
│ 1. Application submitted to Negros Power - Date & by whom?    │
│ 2. Coordination completed - Date & notes                      │
│ 3. Approval received from Negros Power - Date                 │
│ 4. Physical connection completed - Date                       │
│ 5. Beneficiary notified of completion - Date                  │
│                                                               │
│ WHY IN SAME PROFILE:                                          │
│ - No separate electricity folder                              │
│ - Beneficiary record = Unit status + electricity status       │
│ - One place to check everything about beneficiary             │
│ - Tracks utility access quality of life                       │
│ - Shows progress toward making unit livable                   │
└──────────────────────────────────────────────────────────────┘
```

---

## PART 7: OCCUPANCY MONITORING (Weekly Process)

```
┌──────────────────────────────────────────────────────────────┐
│ EVERY WEEK: Occupancy Check Happens                          │
│                                                               │
│ ARCADIO LOBATON (Caretaker) - On-site at GK Cabatangan       │
│                                                               │
│ Why Arcadio?                                                  │
│ - Lives on-site                                               │
│ - Sees every unit daily                                       │
│ - Knows which units appear occupied, vacant, or problematic   │
│ - Remote monitoring by office staff impossible                │
│ - Trusted source of occupancy truth                           │
│                                                               │
│ Process:                                                      │
│ 1. Arcadio opens SIMPLE MOBILE FORM on phone (no app, no      │
│    login needed - works on slow PisoWifi)                     │
│ 2. Form for each unit shows checkboxes:                       │
│    ☐ Occupied (beneficiary living there)                     │
│    ☐ Vacant (empty, no one there)                             │
│    ☐ Concern Noted (something wrong noted)                    │
│ 3. Takes him 30 minutes for ~500 units                        │
│ 4. Submits form to system                                     │
│ 5. SMS confirmation sent: "Report received - 470 occupied"    │
│                                                               │
│ REASON WHY SIMPLE FORM FOR CARETAKER:                         │
│ - Arcadio not trained in complex systems                      │
│ - Mobile connection unreliable (needs lightweight form)       │
│ - System can't show complex info on slow PisoWifi             │
│ - Simple 3-choice form works everywhere                       │
│ - Takes minimal data, provides maximum value                  │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ FIELD TEAM VERIFIES CARETAKER REPORT                          │
│                                                               │
│ Jay, Paul, Roberto, Nonoy - Field Officers                    │
│                                                               │
│ Process:                                                      │
│ 1. Open system and see Arcadio's weekly submission             │
│ 2. Conducts own site inspection during week                   │
│ 3. Verifies/adjusts Arcadio's reported status                 │
│ 4. If Arcadio said "Occupied", field team confirms            │
│    - See lights on? Furnishings? People visibly living?       │
│ 5. If Arcadio said "Vacant", field team confirms              │
│    - Really empty? Or occupant just away temporarily?         │
│ 6. If Arcadio said "Concern", field team investigates         │
│    - What's the concern? Rule violation? Structural issue?    │
│ 7. Field team updates system: "Verified - Status confirmed"   │
│    OR "Adjusted - Actually vacant (beneficiary moved)"        │
│                                                               │
│ REASON WHY TWO-STEP CHECK:                                    │
│ - Caretaker is on-site but may miss details                   │
│ - Field team trained in rule enforcement                      │
│ - Verification prevents false records                         │
│ - Two perspectives catch occupancy fraud                      │
│ - "Vacant" units can = next awarding opportunity              │
│ - Must be certain before declaring unit available             │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ SYSTEM UPDATES UNIT STATUS FOR ALL STAFF                      │
│                                                               │
│ All staff can now see: "As of [DATE], Unit Status:"           │
│ - Block A: 98 occupied, 2 vacant, 0 under notice               │
│ - Block B: 95 occupied, 4 vacant, 1 under notice               │
│ - Block C: 102 occupied, 3 vacant, 2 under notice              │
│ - etc.                                                         │
│                                                               │
│ One dashboard = ONE VERSION OF TRUTH                          │
│                                                               │
│ REASON WHY IMPORTANT:                                         │
│ - Currently: Hand-drawn physical map (could be days old)       │
│ - Currently: Messenger group chat (chaotic, hard to search)    │
│ - Now: Real-time updated status accessible anywhere           │
│ - Jocel knows exactly how many lots available                  │
│ - Arthur knows occupancy rate instantly                       │
│ - No more "Let me call the caretaker to ask"                   │
└──────────────────────────────────────────────────────────────┘
```

---

## PART 8: COMPLIANCE NOTICES & REPOSSESSION

```
┌──────────────────────────────────────────────────────────────┐
│ FIELD TEAM DISCOVERS NON-COMPLIANCE:                          │
│                                                               │
│ Example: Unit flagged as "Vacant" by Arcadio                  │
│ Field team verifies: Block C, Lot 15 empty for 3 months       │
│ Rule: Beneficiary must occupy unit (can't rent/loan/abandon)  │
│                                                               │
│ Field Team Action:                                            │
│ 1. Flags in system: "Unit C-15 appears abandoned"             │
│ 2. Records: Date flagged, observations, photos if any         │
│ 3. System status: "Flagged for Investigation"                 │
│                                                               │
│ SMS SENT TO BENEFICIARY:                                      │
│ "Notice: Your unit Block C, Lot 15 appears unoccupied.       │
│  Please contact THA office immediately."                      │
│                                                               │
│ REASON FOR SMS:                                               │
│ - Might be legitimate reason (hospitalization, work away)     │
│ - Gives beneficiary chance to explain                         │
│ - Better than immediate notice/repossession                   │
│ - Humane approach: check first, escalate if needed            │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ VICTOR (OIC) OR ARTHUR (HEAD) DECIDES NOTICE LEVEL            │
│                                                               │
│ Victor or Arthur reviews the flagged case:                    │
│ "Is this serious enough for 30-day notice? Or 10-day?"        │
│                                                               │
│ Decision-Making Factors:                                      │
│ - Case 1: Unoccupied 3 months = Likely abandonment            │
│           Decision: 30-day reminder notice (chance to return)  │
│                                                               │
│ - Case 2: Unoccupied 6 months + won't communicate             │
│           Decision: 10-day FINAL notice (escalated)            │
│                                                               │
│ - Case 3: Unit damaged intentionally by occupant              │
│           Decision: Immediate 10-day notice                   │
│                                                               │
│ SYSTEM RECORDS:                                               │
│ - Notice type decided                                         │
│ - Days granted (30 or 10 or other)                            │
│ - Reason for notice                                           │
│                                                               │
│ REASON DECISION POWER AT TOP:                                 │
│ - Sensitive: Taking away someone's home                       │
│ - Requires judgment, not automatic system action               │
│ - Head/OIC ensure fairness                                    │
│ - Can consider special circumstances                          │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ JOIE (Second Member) PREPARES OFFICIAL NOTICE                 │
│                                                               │
│ Why Joie?                                                     │
│ - Official designation: "Prepares notices and memos"          │
│ - Trained in official communication                           │
│ - Uses proper language and legal format                       │
│ - Represents THA authority                                    │
│                                                               │
│ Actions:                                                      │
│ 1. Creates official notice document in system                 │
│ 2. Pre-fills: Beneficiary name, unit address, notice type     │
│ 3. Enters: Days granted (30 or 10), deadline date             │
│ 4. System calculates: "Deadline: [DATE]"                      │
│ 5. Registers notice as "Active" in system                     │
│ 6. Stores copy in beneficiary's profile                       │
│                                                               │
│ SMS SENT TO BENEFICIARY:                                      │
│ "REMINDER NOTICE: Your unit Block C, Lot 15 flagged for      │
│  non-compliance. You have 30 days to visit THA office and     │
│  explain. Deadline: [DATE]. Contact: [PHONE]"                 │
│                                                               │
│ REASON FOR FORMAL NOTICE:                                     │
│ - Official record (not informal threat)                       │
│ - Beneficiary has legal right to respond                      │
│ - 30 or 10 days = reasonable time to gather explanation       │
│ - Deadline clear = no confusion                               │
│ - System tracks: Did beneficiary respond? When?               │
└──────────────────────────────────────────────────────────────┘
                             ↓
            [SYSTEM MONITORS DEADLINE AUTOMATICALLY]
                             ↓
        [When 5 days before deadline: System flags for follow-up]
        [Field team contacts beneficiary: "5 days left"]
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ BENEFICIARY RESPONDS (Or Doesn't)                             │
│                                                               │
│ SCENARIO 1: BENEFICIARY RESPONDS                              │
│ - Visits office or sends written explanation                  │
│ - Paul (field officer at office) receives explanation         │
│ - Paul records in system: "Response received - [DATE]"        │
│ - Paul uploads explanation letter to profile                  │
│                                                               │
│ VICTOR OR ARTHUR REVIEWS EXPLANATION:                         │
│ - "The beneficiary says son was in hospital - valid reason"   │
│ - OR "Beneficiary says tenant paying rent - invalid reason"   │
│                                                               │
│ Decision:                                                     │
│ - IF VALID: Case marked "Resolved - Valid Reason"             │
│   Unit stays with beneficiary. Notice ended.                  │
│                                                               │
│ - IF INVALID: Proceed to repossession                         │
│                                                               │
│ SCENARIO 2: BENEFICIARY DOESN'T RESPOND                       │
│ - Deadline passes with no response                            │
│ - System automatically marks: "Escalated - No Response"       │
│ - Case proceeds automatically to repossession                 │
│                                                               │
│ REASON FOR RESPONSE:                                          │
│ - Gives benefit of doubt                                      │
│ - Might be emergency (hospitalization, family loss)           │
│ - Respects human dignity and circumstances                    │
│ - Documented process = fair treatment                         │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ JOCEL RECORDS REPOSSESSION                                    │
│                                                               │
│ Why Jocel?                                                    │
│ - Property Custodian of all THA housing                       │
│ - Responsible for unit inventory                              │
│ - Records formal repossession in the books                    │
│ - Updates blacklist                                           │
│                                                               │
│ Actions:                                                      │
│ 1. Receives repossession decision from Victor/Arthur          │
│ 2. Updates system: "Repossessed - [DATE]"                     │
│ 3. Unit status changed: "Vacant - Available"                  │
│ 4. Tags beneficiary: "BLACKLISTED"                            │
│ 5. Records reason: "Non-compliance with occupancy rule"       │
│ 6. Blacklist entry locked into system permanently             │
│                                                               │
│ SMS SENT TO BENEFICIARY:                                      │
│ "Your housing unit Block C, Lot 15 has been formally         │
│  repossessed. You are permanently disqualified from future    │
│  housing assistance applications. [CONTACT INFO]"             │
│                                                               │
│ REASON FOR BLACKLIST:                                         │
│ - Prevents reapplication under same name                      │
│ - Prevents beneficiary from getting another lot               │
│ - Permanent record of non-compliance                          │
│ - System checks blacklist DURING ELIGIBILITY                  │
│ - If name matched: Immediately disqualified, no exceptions    │
│                                                               │
│ CONSEQUENCE:                                                  │
│ - Beneficiary forfeits housing opportunity                    │
│ - Cannot try again later with THA                             │
│ - Serious punishment for rule-breaking                        │
│ - But: Fair process given before repossession                 │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ SYSTEM SURFACE NEXT STANDBY APPLICANT AUTOMATICALLY            │
│                                                               │
│ Actions:                                                      │
│ 1. Unit now Vacant - Available                                │
│ 2. System identifies next person from standby queue           │
│ 3. Usually: No new draw lots needed (automatic assignment)    │
│ 4. Paul or Nonoy contacts: "Your unit assigned: Block C-15"   │
│ 5. New beneficiary comes to office for turnover               │
│                                                               │
│ REASON FOR AUTOMATIC REASSIGNMENT:                            │
│ - No waiting for next awarding event                          │
│ - Utilizes repossessed unit quickly                           │
│ - Next applicant gets housing faster                          │
│ - No duplicate draw lots ceremony needed                      │
│ - Streamlined reallocation process                            │
└──────────────────────────────────────────────────────────────┘
```

---

## PART 9: COMPLAINT/CASE MANAGEMENT

```
┌──────────────────────────────────────────────────────────────┐
│ SCENARIO: HOUSING-RELATED COMPLAINT RECEIVED                  │
│                                                               │
│ Two Entry Points:                                             │
│                                                               │
│ AT OFFICE:                         AT GK CABATANGAN:          │
│ Resident comes to office           Resident approaches Nonoy  │
│ Talks to Paul (Ronda/Field)         On-site at GK Cabatangan  │
│                                                               │
│ Case Types That Get Logged:                                   │
│ 1. Boundary dispute (my lot vs neighbor's lot)                │
│ 2. Structural issue (roof leaking, wall cracking)             │
│ 3. Interpersonal conflict (noisy neighbor, harassment)        │
│ 4. Illegal transfer (sold unit to outsider)                   │
│ 5. Unauthorized occupant (added family member illegally)      │
│ 6. Property damage (unit intentionally vandalized)            │
│ 7. Noise complaint (loud music at night)                      │
│ 8. Other (everything else housing-related)                    │
│                                                               │
│ CURRENTLY (before system):                                    │
│ - Nonoy handles verbally: "Let's talk to the neighbor"       │
│ - No record kept                                              │
│ - If not resolved immediately: Dropped/forgotten              │
│ - No case number or follow-up mechanism                       │
│ - Management has NO DATA on complaints received               │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ PAUL OR NONOY - LOGS CASE IN SYSTEM                          │
│                                                               │
│ Actions:                                                      │
│ 1. Opens system immediately when complaint received           │
│ 2. Creates new case record                                    │
│ 3. System auto-generates case number: "CASE-2026-00847"      │
│ 4. Enters:                                                    │
│    - Complainant name and link to beneficiary profile         │
│    - Complaint type (boundary, structural, etc.)              │
│    - Date received and time received                          │
│    - Initial notes (what was said)                            │
│    - Who received it (Paul at office or Nonoy on-site)        │
│ 5. Status: Marked "Open"                                      │
│                                                               │
│ SMS CONFIRMATION:                                             │
│ "Case recorded. Your case number is CASE-2026-00847.         │
│  We will follow up on your concern. Thank you."               │
│                                                               │
│ REASON FOR IMMEDIATE LOGGING:                                 │
│ - Complaint now official record (not hearsay)                 │
│ - Case number = tracking mechanism                            │
│ - Owner knows complaint documented                            │
│ - Prevents "I never reported this" disputes                   │
│ - Creates accountability for office                           │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ PAUL/NONOY ATTEMPT FIRST-LEVEL RESOLUTION                    │
│                                                               │
│ Process:                                                      │
│ 1. Tries to resolve on the spot through dialogue              │
│    - Talk to both parties if applicable                       │
│    - Find common ground                                       │
│    - Simple solutions (move fence 1 meter, reduce music time) │
│                                                               │
│ Outcome A: RESOLVED IMMEDIATELY                               │
│ - Paul/Nonoy updates: "Resolved on [DATE]"                    │
│ - Case status: Changed to "Resolved"                          │
│ - Records outcome: "Both agreed to move fence"                │
│ - SMS sent: "Your concern resolved. Thank you."               │
│ - Case CLOSED                                                 │
│                                                               │
│ Outcome B: UNRESOLVED - NEEDS ESCALATION                     │
│ - Paul/Nonoy updates: "Unable to resolve - need investigation"│
│ - Case status: Changed to "Under Investigation"               │
│ - Records reason: "Boundary dispute needs City Engineering"   │
│                                                               │
│ REASON FOR FIRST-LEVEL:                                       │
│ - Most complaints can be resolved by listening                │
│ - Prevents unnecessary escalations                            │
│ - Shows complainant their concern taken seriously             │
│ - Reduces pressure on management                              │
│ - Faster resolution = resident satisfaction                   │
└──────────────────────────────────────────────────────────────┘
                             ↓
        [If resolved: Case closed, customer satisfied]
        [If unresolved: Proceed to escalation]
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ ESCALATION PATHS (depends on complaint type)                  │
│                                                               │
│ PATH 1: BOUNDARY DISPUTE → City Engineering Referral          │
│ - Paul/Nonoy records: "Referred to City Engineering"          │
│ - Records referral date and engineer contact                  │
│ - THA staff (outside of system) coordinates with City         │
│   Engineering for site measurement and decision               │
│ - When City Engineering issues ruling: Records outcome        │
│ - Case status: "Resolved - City Engineering Decision"         │
│                                                               │
│ PATH 2: STRUCTURAL ISSUE → Field Team Investigation           │
│ - Paul/Nonoy escalates: "Building appears structurally unsafe"│
│ - Records: Date and photos/description of damage              │
│ - Jay, Paul, Roberto, or Nonoy investigates:                  │
│   - Measures damage                                           │
│   - Documents findings                                        │
│   - Determines if safety risk                                 │
│ - If risk: Recommends repair or relocation                    │
│ - Victor/Arthur approves recommendation                       │
│ - Case resolved with action taken                             │
│                                                               │
│ PATH 3: INTERPERSONAL CONFLICT → OIC Escalation               │
│ - Paul/Nonoy escalates to: Victor Fregil (OIC)               │
│ - Victor reviews case notes                                   │
│ - Victor decides: "Warn both parties" or "Separate residents" │
│ - Records decision and action taken                           │
│ - Case marked "Resolved - OIC Decision"                       │
│                                                               │
│ PATH 4: ILLEGAL TRANSFER → Policy Enforcement                 │
│ - Paul/Nonoy: "Beneficiary sold unit to outsider"             │
│ - Escalates to: Victor or Arthur (policy violation)           │
│ - Decision: "Unit must revert to beneficiary or repossess"    │
│ - Jocel processes: Tags blacklist if unit lost                │
│ - Next applicant assigned if repossessed                      │
│ - Case resolved with policy enforcement                       │
│                                                               │
│ REASON FOR ESCALATION PATHS:                                  │
│ - Different problems need different solutions                 │
│ - Specialization: Engineering for structures, OIC for policy  │
│ - Documents entire decision trail                             │
│ - Prevents same issue from reappearing                        │
│ - Creates case history for future reference                   │
└──────────────────────────────────────────────────────────────┘
```

---

## PART 10: ANALYTICS DASHBOARD (Real-Time Reports)

```
┌──────────────────────────────────────────────────────────────┐
│ WHO USES ANALYTICS & WHY:                                     │
│                                                               │
│ ARTHUR (Head/First Member):                                   │
│ - Views: Pipeline status, awarding pace, lot utilization      │
│ - When requested by Mayor: "How many applicants? Lots awarded?"│
│ - System shows answer instantly (was taking days before)      │
│                                                               │
│ VICTOR (OIC):                                                 │
│ - Views: Application bottlenecks, signatory turnaround times  │
│ - When making decisions: "Where's our processing slowing down?"│
│ - System shows:  "Apps stuck in routing 5+ days" = fix needed │
│                                                               │
│ JOCEL:                                                        │
│ - Views: Lot utilization, available units, CDRRMO aging list  │
│ - Daily monitoring: "How many units vacant? When queue runs  │
│   out of applicants?"                                         │
│ - System shows instantly instead of manual count              │
│                                                               │
│ JOIE:                                                         │
│ - Views: Awarding pace by quarter, household count            │
│ - When reporting to Mayor/PDO/Full Disclosure Portal:        │
│   "How many awarded Q1 2026?" System shows (was hours manual) │
│                                                               │
│ FIELD TEAM (Jay, Paul, Roberto, Nonoy):                       │
│ - Views: Barangay demand breakdown, eligible applicants      │
│ - Planning decision: "Which barangay has most applicants?    │
│   Where should next relocation project be?"                   │
│ - System shows automatically (was guesswork before)           │
│                                                               │
│ NONOY:                                                        │
│ - Views: Household count, sex breakdown, occupancy rate      │
│ - When attending seminars: "How many households live here?"   │
│ - Answers instantly from dashboard (was calling caretaker)    │
└──────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────┐
│ 8 ANALYTICS ITEMS AUTOMATICALLY COMPUTED:                    │
│                                                               │
│ 1. DEMAND DISTRIBUTION (By barangay)                         │
│    What: Total applicants from each of 27 barangays           │
│    Why: Field team identifies where housing need is greatest  │
│    Display: Bar chart or list: Brgy A: 58 applicants,         │
│             Brgy B: 42, Brgy C: 91, etc.                      │
│                                                               │
│ 2. APPLICATION PIPELINE (Stage breakdown)                     │
│    What: Count at each processing stage                       │
│    Why: Arthur/Victor see bottlenecks (routing takes too long)│
│    Display: Funnel chart:                                     │
│             - Pending Documents: 150                          │
│             - Documents Complete: 120                         │
│             - In Routing: 45 (bottleneck!)                    │
│             - Standby: 232                                    │
│             - Awarded: 1,247                                  │
│                                                               │
│ 3. AWARDING PACE (By year and quarter)                       │
│    What: Lots awarded each Q1, Q2, Q3, Q4 per year            │
│    Why: Joie reports to Mayor, PDO, Full Disclosure Portal   │
│    Display: Bar chart or table:                               │
│             2024 Q1: 92 lots                                  │
│             2024 Q2: 87 lots                                  │
│             2024 Q3: 101 lots                                 │
│             2024 Q4: 95 lots                                  │
│             2025 Q1: 84 lots (current quarter)                │
│                                                               │
│ 4. HOUSEHOLD DEMOGRAPHICS                                    │
│    What: Total households, # males, # females, avg size       │
│    Why: Nonoy answers at conferences, PDO planning            │
│    Display: Summary:                                          │
│             - Total Households: 472                           │
│             - Males: 1,258                                    │
│             - Females: 1,342                                  │
│             - Children (<18): 892                             │
│             - Average family: 5.5 people                      │
│                                                               │
│ 5. LOT UTILIZATION (Occupied vs Vacant vs Under Notice)       │
│    What: Unit status count across all units at GK Cabatangan  │
│    Why: Jocel judges availability for next awarding event     │
│    Display: Status breakdown:                                 │
│             - Occupied: 472                                   │
│             - Vacant: 8                                       │
│             - Under 30-day notice: 3                          │
│             - Under 10-day notice: 1                          │
│             - Total units: 484                                │
│             - Occupancy rate: 97.5%                           │
│                                                               │
│ 6. COMPLIANCE RATE (Notices issued vs complied vs repossessed)│
│    What: Outcome tracking of compliance notice process        │
│    Why: Arthur/Victor judge if occupancy rules are working    │
│    Display: Summary:                                          │
│             - Notices issued: 127 total (lifetime)            │
│             - Complied/resolved: 108 (85%)                    │
│             - Repossessed: 19 (15%)                           │
│             - Current active notices: 4                       │
│                                                               │
│ 7. CDRRMO CERTIFICATION AGING (Days waiting per applicant)    │
│    What: List of each person still waiting for CDRRMO result  │
│    Why: Jocel identifies who to follow up with                │
│    Display: List with aging:                                  │
│             - Juan dela Cruz: 18 days pending (overdue)       │
│             - Maria Garcia: 12 days pending                   │
│             - etc.                                            │
│             - Shows: oldest case first, days waiting, follow-up│
│                                                               │
│ REASON FOR AUTOMATION:                                        │
│ - All data already entered during normal operations           │
│ - System computes automatically from live database            │
│ - No duplicate data entry for "analytics only"                │
│ - Numbers always current (not end-of-month manual counts)     │
│ - Managers can see trends instantly vs. waiting for reports   │
│ - Enables data-driven decision making                         │
│ - Shows improvement opportunities (e.g., slow routing stage)   │
└──────────────────────────────────────────────────────────────┘
```

---

## COMPLETE DATA FLOW VISUALIZATION

```
                    ┌─────────────────────────────────────┐
                    │  EXTERNAL ENTRY POINTS              │
                    │ (Outside System / Before System)    │
                    └─────────────────────────────────────┘
                              │
                    ┌─────────┼─────────┐
                    │         │         │
            ┌───────▼──┐  ┌───▼────┐  ┌─▼──────────┐
            │ Landowner│  │ Walk-in │  │ Walk-in    │
            │ Web Form │  │ Danger  │  │ Regular    │
            │ (Channel)│  │ Zone    │  │            │
            └────┬─────┘  └────┬────┘  └──┬─────────┘
                 │             │           │
                 └─────────────┼───────────┘
                               │
                    ┌──────────▼──────────┐
                    │ SYSTEM CREATES      │
                    │ APPLICANT PROFILE   │
                    │ - Reference #       │
                    │ - Queue placement   │
                    │ - SMS sent          │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ ELIGIBILITY CHECK   │
                    │ - Blacklist match?  │
                    │ - Property owned?   │
                    │ - Income OK?        │
                    │ - Household locked  │
                    └──────────┬──────────┘
                       ┌───────┴────────┐
                       │                │
           ┌───────────▼┐       ┌──────▼──────────┐
           │DISQUALIFIED│       │ QUEUE PLACEMENT │
           │(Blacklist/ │       │ - Priority      │
           │Property/   │       │ - Walk-in FIFO  │
           │Income)     │       └────────┬────────┘
           └────────────┘                │
                          ┌──────────────▼────────────┐
                          │ DOCUMENT VERIFICATION     │
                          │ (7-requirements checklist)│
                          │ Jocel verifies,           │
                          │ system tracks progress    │
                          └──────────┬───────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │ ALL 7 VERIFIED?     │
                      ┌───┤ YES ─►              │
                      │   └────────────────────┘
                      │
            ┌─────────▼────────┐
            │ APPLICATION FORM │
            │ Generated        │
            │ Pre-filled       │
            │ Printed          │
            │ Applicant signs  │
            └────────┬─────────┘
                     │
           ┌─────────▼────────┐
           │ SIGNATORY ROUTING│
           │ Jay (3rd) → OIC  │
           │ OIC → Head       │
           │ (Dates tracked   │
           │ + delay flags)   │
           └────────┬─────────┘
                    │
           ┌────────▼────────┐
           │ STANDBY QUEUE   │
           │ Waiting for     │
           │ lot availability│
           │ SMS confirmation│
           └────────┬────────┘
                    │
    ┌───────────────▼────────────────┐
    │ LOTS AVAILABLE - AWARDING EVENT│
    │ - Field verification (walk-in) │
    │ - Draw lots (physical)          │
    │ - Jocel records assignment      │
    └────────────┬──────────────────┘
                 │
    ┌────────────▼──────────────┐
    │ BENEFICIARY PROFILE        │
    │ - Linked to unit           │
    │ - Electricity section added│
    │ - Status: Occupied         │
    └────────────┬───────────────┘
                 │
    ┌────────────▼──────────────────┐
    │ ELECTRICITY COORDINATION       │
    │ Laarni + Joie track status    │
    │ Statuses tracked:             │
    │ - Application submitted       │
    │ - Coordination completed      │
    │ - Approved                    │
    │ - Connected                   │
    └────────────┬──────────────────┘
                 │
    ┌────────────▼──────────────────┐
    │ OCCUPANCY MONITORING (Weekly) │
    │ - Arcadio submits weekly form │
    │ - Field team verifies         │
    │ - System updates status       │
    │ - Dashboard updates in real   │
    │   time                        │
    └────────────┬──────────────────┘
                 │
    ┌────────────▴──────────┐
    │                       │
    │   HAPPY PATH:         │  UNHAPPY PATH:
    │   Unit occupied       │  Unit vacant/non-compliant
    │   Beneficiary lives   │  ↓
    │   Annual renewals     │  Flag for investigation
    │   Life goes on        │  ↓
    │   (monitor forever)   │  Notice issued (30/10 days)
    │                       │  ↓
    │                       │  Beneficiary responds?
    │                       │  ↓
    │                       │  Valid excuse → Case closed
    │                       │  No response → Repossession
    │                       │  ↓
    │                       │  Jocel records repossession
    │                       │  → Blacklist
    │                       │  → Unit vacant
    │                       │  → Next applicant offered
    │                       │
    └───────┬───────────────┘
            │
    ┌───────▼──────────────┐
    │ COMPLAINT CASES      │
    │ - Logged by Paul/    │
    │   Nonoy               │
    │ - Attempt resolution  │
    │ - Escalate if needed  │
    │ - City Eng/OIC/Head   │
    │ - Case resolved       │
    └───────┬──────────────┘
            │
    ┌───────▼──────────────┐
    │ ANALYTICS DASHBOARD  │
    │ (All data aggregated)│
    │ - Demand (barangay)  │
    │ - Pipeline funnel    │
    │ - Awarding pace      │
    │ - Household count    │
    │ - Lot utilization    │
    │ - Compliance rate    │
    │ - CDRRMO aging       │
    │ (Real-time, no manual│
    │  count needed)       │
    └──────────────────────┘

```

---

## KEY PRINCIPLES EMBEDDED IN DATA FLOW

1. **ONE DATABASE = ONE TRUTH**
   - Any staff update visible to all staff
   - Different staff member attends next = sees complete record
   - No parallel folders or conflicting versions

2. **SYSTEM + HUMAN DECISION**
   - System collects data and flags issues
   - Humans (Victor/Arthur) make judgment decisions
   - Not all decisions can be automated

3. **TRANSPARENCY FOR APPLICANTS**
   - SMS at every stage ("You're eligible," "You're awarded")
   - Case numbers for complaint tracking
   - Applicant knows their position in queue

4. **PERMANENT AUDIT TRAIL**
   - Every action recorded with date/time/person
   - Blacklist protects system integrity
   - Compliance notices documented completely

5. **ROLE-BASED SPECIALIZATION**
   - Each person has specific functions
   - System enforces role responsibilities
   - Prevents "anyone can do anything"

6. **AUTOMATION FOR ROUTINE, HUMAN FOR EXCEPTIONS**
   - System auto-calculates deadlines and flags delays
   - System places applicants in correct queues
   - Humans decide whether exceptions are valid

---

## END OF DATA FLOW DOCUMENTATION
