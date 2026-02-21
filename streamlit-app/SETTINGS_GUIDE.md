# Settings Page Implementation Guide

This document describes the Settings page implementation for the ZeroClaw Streamlit UI.

## Overview

The Settings page (`pages/settings.py`) provides a comprehensive configuration interface for the ZeroClaw Streamlit application, matching the functionality of the React version while adapting to Streamlit's component model.

## Features

### 1. Gateway Configuration

**Purpose:** Configure connection to the ZeroClaw gateway service.

**Components:**
- Gateway URL input field (text input)
- API Token input field (password-masked)
- Save Changes button
- Test Connection button

**Validation:**
- URL format validation (must start with `http://` or `https://`)
- Non-empty URL requirement
- Connection testing via `/health` endpoint

**State Management:**
- Updates `gateway_url` and `api_token` in session state
- Persists to `config.json` for app restart persistence
- Uses `update_settings()` from `lib/session_state.py`

**Error Handling:**
- Invalid URL format: Shows error message
- Connection timeout: Shows timeout error
- Connection refused: Shows connection error
- Successful connection: Shows success with version/uptime info

### 2. Appearance

**Purpose:** Customize visual appearance of the application.

**Components:**

#### Theme Selector
- Options: Matrix Green, Dark, Light
- Default: Matrix Green
- Status: Only Matrix Green currently enabled
- Future: Dark and Light themes coming soon

#### Font Size Selector
- Options: Small, Medium, Large
- Default: Medium
- Effect: Adjusts text size throughout the app

**State Management:**
- Updates `theme` and `font_size` in session state
- Auto-saves to `config.json` on selection change
- Real-time updates without manual save button

### 3. Preferences

**Purpose:** Configure application behavior.

**Components:**

#### Debug Mode Checkbox
- Default: False (disabled)
- When enabled:
  - Shows "Debug Information" section
  - Displays current settings as JSON
  - Shows full session state (with sensitive data hidden)

#### Auto-refresh Reports Checkbox
- Default: True (enabled)
- Effect: Controls automatic refresh of report listings

**State Management:**
- Updates `debug_mode` and `auto_refresh` in session state
- Auto-saves to `config.json` on toggle

### 4. Debug Information

**Purpose:** Display diagnostic information for troubleshooting.

**Visibility:** Only shown when Debug Mode is enabled.

**Information Displayed:**
- Gateway URL
- API token status (set/not set, not the actual token)
- Current theme
- Current font size
- Auto-refresh status
- Config file existence
- Config file path

**Expandable Section:**
- Full session state viewer
- Sensitive data (API token) automatically redacted as `***HIDDEN***`

## File Persistence

### Configuration File

**Location:** `streamlit-app/config.json`

**Format:**
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

### Load/Save Flow

**On Page Load:**
1. Check if `settings_loaded` flag exists in session state
2. If not, load `config.json` if it exists
3. Update session state with saved values
4. Set `settings_loaded` flag to prevent repeated loads

**On Save:**
1. Validate input (URL format, etc.)
2. Update session state via `update_settings()`
3. Write current settings to `config.json`
4. Show success/error message

## Integration with Existing Components

### API Client (`lib/api_client.py`)

The Settings page uses the existing `ZeroClawAPIClient` class:

```python
from lib.api_client import ZeroClawAPIClient

client = ZeroClawAPIClient(
    base_url=gateway_url,
    api_token=api_token
)
health = client.get_health()
```

**Health Check Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime": 3600.5
}
```

### Session State (`lib/session_state.py`)

Uses the centralized state management system:

```python
from lib.session_state import update_settings

update_settings(
    gateway_url="http://localhost:3000",
    api_token="secret_token",
    theme="matrix-green",
    font_size="medium",
    debug_mode=False,
    auto_refresh=True
)
```

## Testing

### Standalone Test

Run the settings page in isolation:

```bash
cd streamlit-app
streamlit run test_settings.py
```

This test script:
- Initializes session state
- Applies Matrix Green theme CSS
- Renders the settings page
- Shows footer information

### Integration Test

Test within the full application:

```bash
cd streamlit-app
streamlit run app.py
# Navigate to Settings page via sidebar
```

### Manual Test Scenarios

1. **URL Validation**
   - Enter invalid URL (no protocol) → Should show error
   - Enter valid URL → Should accept

2. **Connection Testing**
   - Test with running gateway → Should succeed
   - Test with stopped gateway → Should show connection error
   - Test with invalid URL → Should show timeout/error

3. **Settings Persistence**
   - Change settings and save
   - Restart app
   - Verify settings are restored from `config.json`

4. **Debug Mode**
   - Enable debug mode → Debug section appears
   - Verify session state display
   - Verify API token is hidden

5. **Theme/Font Selection**
   - Change theme → Should auto-save
   - Change font size → Should auto-save
   - Restart app → Verify selections persisted

## Architecture Decisions

### Why Streamlit Forms?

Used `st.form()` for gateway settings to:
- Batch input validation
- Prevent premature submissions
- Support both Save and Test actions
- Match Streamlit best practices

### Why Auto-save for Preferences?

Appearance and preference settings auto-save because:
- Single-value changes don't need explicit save
- Immediate feedback improves UX
- Matches modern app expectations
- Reduces user friction

### Why File Persistence?

Settings persist to `config.json` to:
- Survive app restarts
- Work across browser sessions
- Enable deployment configuration
- Support version control (when not containing secrets)

**Note:** The config file should be added to `.gitignore` if it contains API tokens.

### Why Separate Test Connection?

Test connection is separate from Save because:
- Users may want to test without saving
- Allows experimentation with different URLs
- Provides immediate feedback
- Follows principle of least surprise

## Error Handling

### URL Validation
- Empty URL → Error message
- Missing protocol → Error message
- Invalid format → Error message with details

### Connection Testing
- Timeout → User-friendly timeout message
- Connection refused → Clear "cannot connect" message
- HTTP errors → Status code and reason
- Success → Shows version and uptime if available

### File Operations
- Failed to save → Error message with exception details
- Failed to load → Warning message, continues with defaults
- File not found → Silent fallback to defaults

## Security Considerations

### API Token Handling
- Input field uses `type="password"` for masking
- Token never displayed in debug output
- Replaced with `***HIDDEN***` in session state viewer
- Stored in `config.json` (should be gitignored)

### URL Validation
- Protocol enforcement (http/https only)
- Format validation via `urllib.parse`
- No JavaScript injection possible (Streamlit sanitizes)

### File Permissions
- Config file written with default permissions
- Contains potentially sensitive data (API token)
- Should be added to `.gitignore`

## Future Enhancements

### Theme Support
- Implement Dark theme
- Implement Light theme
- Custom theme builder
- Theme preview

### Advanced Gateway Settings
- Connection timeout configuration
- Retry settings
- Custom headers
- Multiple gateway profiles

### Enhanced Preferences
- Refresh interval slider
- Notification settings
- Data retention policies
- Export/import settings

### Validation Improvements
- Async connection testing
- Gateway version compatibility check
- Certificate validation for HTTPS
- Auto-discovery of gateway endpoints

## Comparison with React Version

### Similarities
- Same three-section layout (Gateway, Appearance, Preferences)
- Same configuration options
- Similar validation logic
- Equivalent state management pattern

### Differences
- **Forms:** Streamlit uses `st.form()` instead of React form handlers
- **Auto-save:** Streamlit auto-saves appearance/preferences (React has single Save button)
- **File storage:** Streamlit uses `config.json` (React uses localStorage)
- **Debug info:** Streamlit has expandable session state viewer (React doesn't have this)
- **Theme switching:** Streamlit shows "coming soon" message (React disables buttons)

## Troubleshooting

### Settings not persisting
- Check if `config.json` is being created in app root
- Verify file permissions
- Check for errors in Streamlit console

### Connection test fails
- Verify gateway is running
- Check URL format
- Test URL in browser first
- Check for firewall/network issues

### Theme not applying
- Theme application requires main app integration
- Test page only applies basic CSS
- Full theme requires `app.py` integration

### Debug mode not showing data
- Ensure checkbox is actually checked
- Refresh page if needed
- Check browser console for errors

## Code Style

The implementation follows these conventions:
- Type hints on function signatures
- Docstrings for all functions
- Clear variable names
- Consistent error handling
- Comments for complex logic
- DRY principle (helper functions)

## Dependencies

Required packages (from `requirements.txt`):
- `streamlit>=1.32.0` - Core framework
- `requests>=2.31.0` - HTTP client for API calls

No additional dependencies needed for Settings page.
