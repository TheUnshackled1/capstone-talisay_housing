# Dashboard Template Reorganization

## Summary
Reorganized dashboard templates by position for improved readability and maintainability.

## Changes Made

### Directory Structure
Created position-based folders in `templates/accounts/`:
```
templates/accounts/
├── head/
│   └── dashboard.html (formerly dashboard_head.html)
├── oic/
│   └── dashboard.html (formerly dashboard_oic.html)
├── second_member/
│   └── dashboard.html (formerly dashboard_second_member.html)
├── third_member/
│   └── dashboard.html (formerly dashboard_third_member.html)
├── fourth_member/
│   └── dashboard.html (formerly dashboard_fourth_member.html)
├── fifth_member/
│   └── dashboard.html (formerly dashboard_fifth_member.html)
├── dashboard.html (main template)
├── dashboard_second_member_new.html (backup/alternative version)
└── login.html
```

### Files Moved
| Old Path | New Path |
|----------|----------|
| `templates/accounts/dashboard_head.html` | `templates/accounts/head/dashboard.html` |
| `templates/accounts/dashboard_oic.html` | `templates/accounts/oic/dashboard.html` |
| `templates/accounts/dashboard_second_member.html` | `templates/accounts/second_member/dashboard.html` |
| `templates/accounts/dashboard_third_member.html` | `templates/accounts/third_member/dashboard.html` |
| `templates/accounts/dashboard_fourth_member.html` | `templates/accounts/fourth_member/dashboard.html` |
| `templates/accounts/dashboard_fifth_member.html` | `templates/accounts/fifth_member/dashboard.html` |

### Updated References

#### templates/accounts/dashboard.html
**Before:**
```django
{% if user.position == 'head' %}
    {% include 'accounts/dashboard_head.html' %}
{% elif user.position == 'oic' %}
    {% include 'accounts/dashboard_oic.html' %}
...
```

**After:**
```django
{% if user.position == 'head' %}
    {% include 'accounts/head/dashboard.html' %}
{% elif user.position == 'oic' %}
    {% include 'accounts/oic/dashboard.html' %}
...
```

## Files That Did NOT Need Changes

### accounts/urls.py
✅ No changes needed - URLs reference views, not templates directly:
```python
urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
]
```

### accounts/views.py
✅ No changes needed - View returns main template which handles includes:
```python
@login_required
def dashboard_view(request):
    # ... context logic ...
    return render(request, 'accounts/dashboard.html', context)
```

## Benefits

### Before
- All dashboard templates in one flat directory
- Hard to find specific position's dashboard
- Naming convention: `dashboard_<position>.html`
- Template paths were long and repetitive

### After
✅ **Organized by position** - Each position has its own folder  
✅ **Consistent naming** - All position dashboards are named `dashboard.html`  
✅ **Scalable** - Easy to add more position-specific templates (e.g., `widgets.html`, `reports.html`)  
✅ **Better IDE navigation** - Folder structure mirrors organizational hierarchy  
✅ **Cleaner includes** - Template paths follow Django best practices  

## Future Additions
Each position folder can now contain additional templates:
```
head/
├── dashboard.html
├── reports.html (future)
├── approvals.html (future)
└── widgets/ (future widget components)
```

## Testing
After reorganization, verify:
1. ✅ Login as each position
2. ✅ Dashboard loads correctly
3. ✅ Position-specific widgets display
4. ✅ No template errors in console

## Rollback (if needed)
To rollback, reverse the file moves:
```python
import os, shutil
base = 'c:/Users/jtcor/Documents/capstone/templates/accounts'
mappings = {
    'head/dashboard.html': 'dashboard_head.html',
    'oic/dashboard.html': 'dashboard_oic.html',
    'second_member/dashboard.html': 'dashboard_second_member.html',
    'third_member/dashboard.html': 'dashboard_third_member.html',
    'fourth_member/dashboard.html': 'dashboard_fourth_member.html',
    'fifth_member/dashboard.html': 'dashboard_fifth_member.html',
}
for new, old in mappings.items():
    shutil.move(os.path.join(base, new), os.path.join(base, old))
```

And revert `templates/accounts/dashboard.html` include paths.
