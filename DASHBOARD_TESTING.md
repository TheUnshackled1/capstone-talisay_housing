# Dashboard Testing Checklist

## ✅ Pre-Testing Setup

- [ ] All template files created in `templates/accounts/`
  - [ ] `dashboard_head.html`
  - [ ] `dashboard_oic.html`
  - [ ] `dashboard_second_member.html`
  - [ ] `dashboard_third_member.html`
  - [ ] `dashboard_fourth_member.html`
  - [ ] `dashboard_fifth_member.html`

- [ ] CSS file created: `static/css/dashboard_widgets.css`
- [ ] CSS linked in `dashboard.html` (line 11)
- [ ] `accounts/views.py` updated with role-specific context
- [ ] Users seeded via `python manage.py seed_users`

---

## 🧪 Test Each Dashboard

### Test 1: Head Dashboard (Arthur Maramba)
- [ ] Login: `arthur.maramba` / `tha2026`
- [ ] See "Welcome, Arthur Benjamin!" banner
- [ ] Stats cards show: Total Applicants, Awaiting Signature, Housing Units, Monthly Reports
- [ ] Quick actions: Sign Applications, View Analytics
- [ ] Widgets section shows:
  - [ ] Awaiting Your Signature widget
  - [ ] System Overview widget
  - [ ] Analytics & Reports widget
- [ ] All widgets show empty states (no data yet)
- [ ] No console errors in browser

### Test 2: OIC Dashboard (Victor Fregil)
- [ ] Login: `victor.fregil` / `tha2026`
- [ ] See "Welcome, Victor!" banner
- [ ] Stats cards show: Total Applicants, Awaiting Signature, Compliance Cases, Escalated Complaints
- [ ] Quick actions: Review Applications, Compliance Decisions, Review Cases
- [ ] Widgets section shows:
  - [ ] Awaiting OIC Signature widget
  - [ ] Compliance Cases widget
  - [ ] Escalated Cases widget
  - [ ] This Month's Activity widget
- [ ] No console errors

### Test 3: Second Member Dashboard (Joie Tingson) ⭐
- [ ] Login: `joie.tingson` / `tha2026`
- [ ] See "Welcome, Lourynie Joie!" banner
- [ ] Role subtitle shows "Second Member"
- [ ] Stats cards show: Total Applicants, Pending Notices, Electricity Pending, Incomplete Docs
- [ ] Quick actions: Prepare Notices, Track Electricity, Document Oversight, Generate Reports
- [ ] Widgets section shows:
  - [ ] Priority Tasks widget (notices to prepare)
  - [ ] Electricity Connections widget
  - [ ] Document Oversight widget
  - [ ] Upcoming Reports widget
- [ ] All empty states display correctly
- [ ] No console errors

### Test 4: Third Member Dashboard (Jay Olvido)
- [ ] Login: `jay.olvido` / `tha2026`
- [ ] See "Welcome, Roland Jay!" banner
- [ ] Stats cards show: Census Records, Pending Verification, Site Inspections, Open Investigations
- [ ] Quick actions: Field Verification, Route Documents, Site Inspection, Investigations
- [ ] Widgets section shows:
  - [ ] Signatory Routing widget
  - [ ] Field Verification widget
  - [ ] Site Inspections widget
  - [ ] Violation Investigations widget
- [ ] No console errors

### Test 5: Fourth Member Dashboard (Jocel Cuaysing) ⭐
- [ ] Login: `jocel.cuaysing` / `tha2026`
- [ ] See "Welcome, Jocel!" banner
- [ ] Role subtitle shows "Fourth Member"
- [ ] Stats cards show: Queue Today, Incomplete Requirements, Documents Filed, Lots for Awarding
- [ ] Quick actions: Register Applicant, Check Requirements, Manage Queue, Lot Awarding
- [ ] Widgets section shows:
  - [ ] Priority Queue widget
  - [ ] Walk-in FIFO Queue widget
  - [ ] Pending CDRRMO Certification widget
  - [ ] Incomplete Requirements widget
  - [ ] Lot Awarding widget
  - [ ] Property Custodian widget
- [ ] All empty states display correctly
- [ ] No console errors

### Test 6: Fifth Member Dashboard (Laarni Hellera)
- [ ] Login: `laarni.hellera` / `tha2026`
- [ ] See "Welcome, Laarni!" banner
- [ ] Stats cards show: Pending Connections, Connected This Month, Awaiting Negros Power, Monthly Notices
- [ ] Quick actions: New Connection, Track Status, Mark Connected, Monthly Report
- [ ] Widgets section shows:
  - [ ] Connection Queue widget
  - [ ] Pending with Negros Power widget
  - [ ] This Month's Progress widget
- [ ] No console errors

---

## 🎨 Visual Testing

### Layout
- [ ] Widgets display in grid layout (responsive columns)
- [ ] Cards have proper shadows and hover effects
- [ ] Spacing between widgets is consistent
- [ ] Mobile view: Widgets stack vertically

### Typography
- [ ] Widget titles are bold and clear
- [ ] Badge text is readable
- [ ] Empty state messages display properly
- [ ] Icons render correctly

### Colors
- [ ] Badges show correct colors:
  - Blue for info/general
  - Green for success
  - Amber/yellow for warnings
  - Red for urgent/critical
  - Purple for reports
- [ ] Empty state icons are light gray
- [ ] Hover effects work on cards and buttons

---

## 🐛 Common Issues & Fixes

### Issue: Template not found
**Error:** `TemplateDoesNotExist at /dashboard/`  
**Fix:** Check file path is exactly `templates/accounts/dashboard_[role].html`

### Issue: CSS not loading
**Error:** Widgets look unstyled  
**Fix:** 
1. Check `{% load static %}` at top of dashboard.html
2. Verify CSS link: `{% static 'css/dashboard_widgets.css' %}`
3. Run `python manage.py collectstatic` if needed

### Issue: Wrong dashboard shown
**Error:** All users see same widgets  
**Fix:** Check `user.position` value in database matches template conditions

### Issue: Context variables undefined
**Error:** Template errors about missing variables  
**Fix:** All context variables should default to 0 or [] in views.py

---

## ✨ Success Criteria

You've successfully implemented the dashboards if:

1. ✅ Each staff member sees a **different dashboard**
2. ✅ Widgets match their **official responsibilities**
3. ✅ All **empty states** display correctly (no errors)
4. ✅ **Stats cards** show appropriate metrics per role
5. ✅ **Quick actions** are role-specific
6. ✅ **No console errors** in browser
7. ✅ Dashboard is **responsive** (test mobile view)
8. ✅ User can **navigate** between modules from sidebar

---

## 📋 Next Development Steps

Once testing passes:

1. **Connect Module 1 (Intake)** data to dashboard contexts
2. **Connect Module 2 (Applications)** data
3. **Implement Module 3 (Documents)** queries
4. **Build Module 4 (Housing Units)** and connect
5. **Add Module 5 (Cases)** data
6. **Wire up Module 6 (Analytics)** reports

Each module connection will populate the relevant widgets across different staff dashboards.

---

**Status:** _Dashboard infrastructure complete. Ready for data integration._
