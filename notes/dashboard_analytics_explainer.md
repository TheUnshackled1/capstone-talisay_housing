# Dashboard Analytics Deep-Dive

## 1. Why is this Descriptive Analytics?

**Descriptive Analytics** answers the question: **"What happened?"** or **"What is the current state?"**

Your dashboard exclusively uses **counts, distributions, breakdowns, and proportions** derived from existing database records. It does NOT predict future outcomes (Predictive) or recommend actions (Prescriptive).

| Justification Criteria | Your Dashboard | Analytics Type |
|---|---|---|
| Summarizes historical/current data | ✅ All charts show counts from the database | **Descriptive** |
| Uses statistical measures (counts, sums, ratios, percentages) | ✅ Every widget uses `Count()`, `sum()`, percentage bars | **Descriptive** |
| Answers "What happened?" / "What is?" | ✅ "How many applicants per status?", "How many voters?", "What is the gender split?" | **Descriptive** |
| Makes future predictions | ❌ No forecasting, no ML models | ~~Predictive~~ |
| Recommends specific actions | ❌ No automated decision-making | ~~Prescriptive~~ |

> **Panel-ready answer:** "The system employs **Descriptive Analytics** because every dashboard widget summarizes and visualizes existing records from the PostgreSQL database using aggregate functions (`COUNT`, `GROUP BY`, conditional aggregation). The purpose is to present the **current state** and **historical snapshot** of housing applicants, cases, housing units, and voter registration — answering 'What is happening?' rather than predicting or prescribing future outcomes."

---

## 2. Where Is Each Chart's Data Fetched From?

All data originates from the Python function [`_staff_reports_analytics_payload()`](file:///c:/Users/jtcor/Documents/capstone/accounts/views.py#L737) in `accounts/views.py`. This single function runs **all** the database queries and passes the results to the template.

| Dashboard Widget | Database Model(s) Queried | Backend Code Location | Django ORM Query Used |
|---|---|---|---|
| **Applicants by Status** (Registered: 19, Evaluation: 3, Form: 5, Lot Awarded: 21) | `Applicant`, `Archive`, `Application`, `LotAward` | [views.py L997–L1038](file:///c:/Users/jtcor/Documents/capstone/accounts/views.py#L997-L1038) | `Archive.objects.filter(formally_archived=False)` for Registered; `_staff_analytics_module2_counts()` for Evaluation & Form; `isf_population_stats()` for Lot Awarded |
| **Applicant Situation** (CDRRMO: 19, Ejected: 6, Displaced: 7, None: 13) | `Applicant` | [views.py L1040–L1103](file:///c:/Users/jtcor/Documents/capstone/accounts/views.py#L1040-L1103) | `Applicant.objects.filter(id__in=active_pipeline_ids).values('id', 'displacement_reason')` — groups by `displacement_reason` column |
| **ISF Population Overall** (Beneficiaries: 21, Population: 22) | `LotAward`, `Applicant`, `HouseholdMember` | [views.py L928–L964](file:///c:/Users/jtcor/Documents/capstone/accounts/views.py#L928-L964) | `isf_population_stats(isf_site)` — counts active lot awards + household members |
| **Registered Voters** (With: 9, No: 20) | `Applicant` | [views.py L1341–L1361](file:///c:/Users/jtcor/Documents/capstone/accounts/views.py#L1341-L1361) | `Applicant.objects.filter(status='awarded').values('is_registered_voter_talisay').annotate(count=Count('id'))` |
| **Gender Distribution** (Male: 4, Female: 15) | `Applicant`, `HouseholdMember` | `isf_population_stats()` helper | Counts `sex='M'` and `sex='F'` across awarded beneficiaries and their household members |
| **Top Barangays** | `Applicant`, `Barangay` | [views.py L917–L926](file:///c:/Users/jtcor/Documents/capstone/accounts/views.py#L917-L926) | `Applicant.objects.exclude(barangay_id__isnull=True).values(place_name=F('barangay__name')).annotate(count=Count('id')).order_by('-count')[:12]` |
| **Housing Units by Status** (Unit: 18, Occupied: 3, Vacant: 244) | `HousingUnit`, `LotAward`, `ConstructionProgress` | [views.py L1121–L1178](file:///c:/Users/jtcor/Documents/capstone/accounts/views.py#L1121-L1178) | `HousingUnit.objects.values('status').annotate(count=Count('id'))` — then splits Occupied into Housing Unit vs plain Occupied |
| **Blacklisted** (Repossessed: 1) | `UnitsBlacklist` | [views.py L1321–L1335](file:///c:/Users/jtcor/Documents/capstone/accounts/views.py#L1321-L1335) | `UnitsBlacklist.objects.values('reason').annotate(count=Count('id'))` |
| **Case Aging Distribution** (0-3d, 4-7d, etc.) | `Case` | [views.py L1226–L1250](file:///c:/Users/jtcor/Documents/capstone/accounts/views.py#L1226-L1250) | Single SQL aggregate with conditional `Count('pk', filter=Q(...))` for each band |
| **Cases by Status** (Pending: 6, Settlement: 3, etc.) | `Case` | [views.py L1184–L1194](file:///c:/Users/jtcor/Documents/capstone/accounts/views.py#L1184-L1194) | `Case.objects.filter(received_at__gte=period_start).values('status').annotate(count=Count('id'))` |
| **Cases by Type** (Lot Boundary: 6, Noise: 3, etc.) | `Case` | [views.py L1196–L1202](file:///c:/Users/jtcor/Documents/capstone/accounts/views.py#L1196-L1202) | `Case.objects.filter(...).values('case_type').annotate(count=Count('id'))` |

---

## 3. Is the Data Fetching Correct?

| Widget | Correctness Check | Verdict |
|---|---|---|
| **Applicants by Status** | Uses the exact same queries as each module page (applicants.html, applications_list.html, etc.) so numbers always match navigation. Comment at L994 confirms this. | ✅ Correct |
| **Applicant Situation** | Queries only `active_pipeline_ids` (union of Registered + Evaluation + Form + Awarded), not archived applicants. Correctly groups by `displacement_reason`. | ✅ Correct |
| **ISF Population** | Uses `isf_population_stats()` which counts active `LotAward` records + historical occupant rows. Matches GK Masterlist. | ✅ Correct |
| **Registered Voters** | Filters to `status='awarded'` only (lot-awarded beneficiaries), then groups by `is_registered_voter_talisay` boolean. | ✅ Correct |
| **Gender Distribution** | Counts M/F across beneficiaries and their household members from awarded applicants. | ✅ Correct |
| **Housing Units** | Splits "Occupied" into "Housing Unit" (historical + on-file construction) and plain "Occupied" — mirrors the monitoring page KPI. | ✅ Correct |
| **Cases** | Period-scoped (`received_at` within filter range). Uses Django ORM `annotate(count=Count('id'))`. | ✅ Correct |
| **Case Aging** | Uses a single SQL aggregate with conditional counts per time band. Mathematically consistent (bands are mutually exclusive). | ✅ Correct |

---

## 4. Why 10-Minute Cache Instead of Real-Time?

The cache is set at [views.py L244](file:///c:/Users/jtcor/Documents/capstone/accounts/views.py#L244):
```python
cache.set(_cache_key, analytics_data, 600)  # 10-minute TTL (shared via DatabaseCache)
```

| Question | Answer |
|---|---|
| **Why cache at all?** | The analytics payload runs **30+ database queries** across 10+ tables (`Applicant`, `Application`, `Case`, `HousingUnit`, `LotAward`, `Document`, `ConstructionProgress`, etc.). Without caching, this caused a **~14-second page load** per worker (noted in the code comment at L233–L234). |
| **Why 10 minutes?** | It's a balance between **freshness** and **performance**. Housing data doesn't change every second — new applicants register maybe a few times per day. A 10-minute window means staff always see data that is at most 10 minutes old, which is acceptable for a reporting dashboard. |
| **Why not real-time?** | Real-time would mean re-running all 30+ queries on every single page load. On Railway (your deployment platform), this would cause **worker timeouts** and slow down all other requests. The code comment explicitly says: *"Previously caused a ~14s cold hit per worker."* |
| **Can I force fresh data?** | Yes! Adding `?refresh=1` to the dashboard URL bypasses the cache entirely (see [L231](file:///c:/Users/jtcor/Documents/capstone/accounts/views.py#L231): `_force_refresh = request.GET.get('refresh') == '1'`). |
| **Is the cache shared?** | Yes. It uses Django's `DatabaseCache` backend, meaning all Railway dynos (workers) share the same cached result. One worker computes it, all workers benefit. |

> **Panel-ready answer:** "We use a 10-minute DatabaseCache TTL because the analytics payload executes over 30 aggregate queries across 10+ database tables. Without caching, each dashboard load took approximately 14 seconds. Since housing management data changes infrequently (registrations happen a few times daily, not per second), a 10-minute staleness window is acceptable for a descriptive reporting dashboard. Staff can force a live refresh at any time by appending `?refresh=1` to the URL."
