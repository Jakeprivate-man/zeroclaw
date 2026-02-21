# Settings Page - Quick Start Guide

## Test the Settings Page

```bash
cd /Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app
streamlit run test_settings.py
```

## Files Created

### Implementation
- `pages/settings.py` (294 lines) - Main settings page
- `test_settings.py` (124 lines) - Standalone test

### Documentation
- `pages/README.md` - Pages module guide
- `SETTINGS_GUIDE.md` - Comprehensive implementation guide
- `IMPLEMENTATION_SUMMARY.md` - Summary and checklist
- `SETTINGS_FILES.txt` - File structure overview
- `QUICK_START.md` - This file

## Features

### Gateway Configuration
- Gateway URL input (validated)
- API Token input (password-masked)
- Test Connection button
- Save Changes button

### Appearance
- Theme: Matrix Green (default), Dark/Light (coming soon)
- Font Size: Small, Medium, Large

### Preferences
- Debug Mode toggle
- Auto-refresh Reports toggle

### Debug Information
- Settings JSON viewer
- Full session state viewer (API token hidden)

## Quick Test Checklist

- [ ] Run `streamlit run test_settings.py`
- [ ] Enter gateway URL: `http://localhost:3000`
- [ ] Click "Test Connection" (will fail if gateway not running)
- [ ] Click "Save Changes"
- [ ] Verify `config.json` created in app root
- [ ] Change theme/font size (auto-saves)
- [ ] Enable debug mode
- [ ] Verify debug section appears
- [ ] Verify API token is hidden in session state
- [ ] Restart app and verify settings restored

## Integration with Main App

```python
# In main app (e.g., app.py)
from pages import settings

# In page router
if selected_page == "Settings":
    settings.render()
```

## Configuration File

Created at: `/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/config.json`

```json
{
  "gateway_url": "http://localhost:3000",
  "api_token": "",
  "theme": "matrix-green",
  "font_size": "medium",
  "debug_mode": false,
  "auto_refresh": true
}
```

**Important:** Add `config.json` to `.gitignore` if it contains API tokens!

## Dependencies

All dependencies already in `requirements.txt`:
- streamlit>=1.32.0
- requests>=2.31.0

## Next Steps

1. Test standalone: `streamlit run test_settings.py`
2. Integrate into main app
3. Test in full app context
4. Add `config.json` to `.gitignore`
5. Implement Dark/Light themes (future)

## Need Help?

See detailed documentation:
- `SETTINGS_GUIDE.md` - Full implementation guide
- `IMPLEMENTATION_SUMMARY.md` - Complete feature list
- `pages/README.md` - Pages module overview
