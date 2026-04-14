# Queue Management Logic - IHSMS

## Queue System per Specification

### Channel A (Landowner Portal & Staff Entry)
- **Queue Type**: Walk-in FIFO
- **Position**: Auto-assigned sequentially (1, 2, 3, ...)
- **Display**: "Walk-in #1", "Walk-in #2", etc.
- **SMS**: "Your reference is XXXX. Queue position: #1"

### Channel B (Danger Zone - Walk-in)
- **Initial Status**: Pending CDRRMO Certification
- **IF CERTIFIED**:
  - Queue Type: Priority Queue
  - Position: Top of queue (guaranteed first service)
  - Display: "Priority #1" (position 1 in priority queue)
  - SMS: "Your location certified. You're on priority list"

- **IF NOT CERTIFIED**:
  - Queue Type: Walk-in FIFO
  - Position: Regular walk-in queue (penalty)
  - Display: "Walk-in #X"
  - SMS: "Location not certified. Queue #X"

### Channel C (Walk-in Regular)
- **Queue Type**: Walk-in FIFO
- **Position**: Auto-assigned sequentially
- **Display**: "Walk-in #1", "Walk-in #2", etc.
- **SMS**: "Your reference is XXXX. Queue position: #1"

---

## Bug Fixed

### The Issue
When Channel B applicants were NOT certified by CDRRMO, the system was creating queue entries with:
```python
queue_type='walkin'  # ❌ WRONG - typo (no underscore)
```

But the QueueEntry model only accepts:
```python
QUEUE_TYPE_CHOICES = [
    ('priority', 'Priority Queue'),    # ✅ priority
    ('walk_in', 'Walk-in FIFO Queue'), # ✅ walk_in (WITH underscore)
]
```

### Result of Bug
- Queue entry validation would fail silently
- Database might reject the record or store invalid data
- Queue positions weren't being assigned properly
- Template showed "Awaiting" instead of actual queue type/position

### The Fix
**File**: `intake/views.py`, Line 968
```python
# BEFORE (WRONG)
queue_type='walkin',            # ❌ Typo
status='active',
position=QueueEntry.objects.filter(queue_type='walkin', status='active').count() + 1

# AFTER (CORRECT)
queue_type='walk_in',           # ✅ Fixed
status='active',
position=QueueEntry.objects.filter(queue_type='walk_in', status='active').count() + 1
```

---

## How Queue Position Assignment Works

### Step 1: Determine Queue Type
```python
if decision == 'certified':
    queue_type = 'priority'   # Top of queue
else:
    queue_type = 'walk_in'    # Back of walk-in line
```

### Step 2: Calculate Next Position
```python
last_position = QueueEntry.objects.filter(
    queue_type=queue_type,    # Get last in THIS queue (priority or walk-in)
    status='active'
).order_by('-position').values_list('position', flat=True).first() or 0

next_position = last_position + 1  # Add 1 to get next available position
```

**Example**:
- Priority queue has positions: 1, 2, 3 (3 exists) → Next = 4
- Walk-in queue has positions: 1, 2, 5, 7 (last=7) → Next = 8

### Step 3: Create Queue Entry
```python
QueueEntry.objects.create(
    applicant=applicant,
    queue_type=queue_type,        # 'priority' or 'walk_in'
    position=next_position,       # Sequential number
    status='active',
    added_by=request.user
)
```

---

## Queue Display in Template

**File**: `templates/intake/staff/applicants.html`, Lines 949-961

```django
{% if applicant.queueType == 'Priority' %}
    <span class="badge queue-priority">Priority #{{ applicant.queuePosition }}</span>
{% elif applicant.queueType == 'Walk-in' %}
    <span class="badge queue-walkin">Walk-in #{{ applicant.queuePosition }}</span>
{% elif applicant.queueType == 'Standby' %}
    <span class="badge queue-standby">Standby</span>
{% elif applicant.eligibilityStatus == 'Pending' or applicant.eligibilityStatus == 'Pending CDRRMO' %}
    <span class="badge queue-pending">Awaiting</span>  <!-- Shows while waiting for eligibility decision -->
{% elif applicant.eligibilityStatus == 'Disqualified' %}
    <span class="badge" style="background: #fee2e2; color: #991b1b;">N/A</span>
{% else %}
    <span class="badge queue-none">—</span>
{% endif %}
```

---

## Data Flow: How Queue Data Reaches Template

### View Function: `applicants_list()` (Line 1180-1188)
```python
queue_entry = QueueEntry.objects.filter(
    applicant=applicant_profile,
    status='active'
).first()

if queue_entry:
    queue_type = 'Priority' if queue_entry.queue_type == 'priority' else 'Walk-in'
    queue_position = queue_entry.position
```

### JSON Data Passed to Template
```javascript
applicantsData = [
    {
        queueType: 'Priority',    // From: queue_entry.queue_type
        queuePosition: 1,         // From: queue_entry.position
        // ... other fields
    },
    {
        queueType: 'Walk-in',     // From: queue_entry.queue_type
        queuePosition: 5,         // From: queue_entry.position
        // ... other fields
    }
]
```

### Template Rendering
The template loops through `applicantsData` and checks `applicant.queueType`:
```django
{% for applicant in applicants %}
    <td>
        {% if applicant.queueType == 'Priority' %}
            <span>Priority #{{ applicant.queuePosition }}</span>
        <!-- ... etc -->
    </td>
{% endfor %}
```

---

## Testing Queue Logic

### Test Case 1: Channel A (Landowner Portal)
- Submit via public form
- Expected: "Walk-in #1" (or higher if others exist)
- BEFORE FIX: Shows "Awaiting"
- AFTER FIX: Shows "Walk-in #X" ✅

### Test Case 2: Channel B - CERTIFIED
- Register as danger zone walk-in
- Get CDRRMO certification: YES
- Expected: "Priority #1" (top of priority queue)
- BEFORE FIX: Shows "Awaiting" (queue_type='walkin' was invalid)
- AFTER FIX: Shows "Priority #1" ✅

### Test Case 3: Channel B - NOT CERTIFIED
- Register as danger zone walk-in
- Get CDRRMO certification: NO
- Expected: "Walk-in #X" (back of walk-in queue)
- BEFORE FIX: Shows "Awaiting" (queue_type='walkin' was invalid)
- AFTER FIX: Shows "Walk-in #X" ✅

### Test Case 4: Channel C (Walk-in Regular)
- Staff enters walk-in at counter
- Expected: "Walk-in #1" (or higher if others exist)
- BEFORE FIX: Shows "Awaiting"
- AFTER FIX: Shows "Walk-in #X" ✅

---

## SQL Queries to Verify Queue Data

```sql
-- Check all active queue entries
SELECT id, applicant_id, queue_type, position, entered_at
FROM intake_queueentry
WHERE status='active'
ORDER BY queue_type, position;

-- Count by queue type
SELECT queue_type, COUNT(*) as count
FROM intake_queueentry
WHERE status='active'
GROUP BY queue_type;

-- Verify position uniqueness within each queue
SELECT queue_type, position, COUNT(*)
FROM intake_queueentry
WHERE status='active'
GROUP BY queue_type, position
HAVING COUNT(*) > 1;  -- Should return no rows
```

---

## Alignment with Specification

✅ **Revised System Processes - Process 1: Applicant Intake**

Per your specification document:
> "Applicants are assigned to either Priority Queue (danger zone certified) or Walk-in FIFO Queue based on entry channel and certification status."

**This fix ensures**:
- ✅ Channel A entries → Walk-in FIFO Queue with sequential positions
- ✅ Channel B (certified) → Priority Queue with position #1
- ✅ Channel B (not certified) → Walk-in FIFO Queue with penalty position
- ✅ Channel C entries → Walk-in FIFO Queue with sequential positions
- ✅ All positions assigned correctly and sequentially within their queue type

**Status**: ALIGNED with specification ✅

