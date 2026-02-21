# ZeroClaw Streamlit UI - Pages

This directory contains all page modules for the ZeroClaw Streamlit application.

## Available Pages

### Settings (`settings.py`)

Configuration page for the ZeroClaw application.

**Features:**
- Gateway Configuration
  - Gateway URL input with validation
  - API token input (password-masked)
  - Test connection functionality
  - Save settings to JSON file
- Appearance
  - Theme selector (Matrix Green default, Dark/Light coming soon)
  - Font size selector (Small/Medium/Large)
- Preferences
  - Debug mode toggle
  - Auto-refresh reports toggle
- Debug Information (when debug mode enabled)
  - Current settings display
  - Full session state viewer (with sensitive data hidden)

**State Management:**
- Uses `lib/session_state.py` for session state management
- Persists settings to `config.json` in app root
- Automatically loads saved settings on page load

**API Integration:**
- Uses `lib/api_client.py` for gateway communication
- Tests connection via `/health` endpoint
- Validates gateway URL format before connection

**Usage:**
```python
from pages import settings
settings.render()
```

## Page Structure

Each page module follows this pattern:

1. Imports and dependencies
2. Helper functions (if needed)
3. `render()` function - main entry point
4. Optional `if __name__ == "__main__"` block for standalone testing

## Testing Pages

Each page can be tested standalone using the test scripts:

```bash
# Test settings page
streamlit run streamlit-app/test_settings.py
```

## Adding New Pages

To add a new page:

1. Create `pages/<page_name>.py`
2. Implement a `render()` function
3. Update `pages/__init__.py` to include the new page
4. Create a test script `test_<page_name>.py`
5. Update this README

Example template:

```python
"""<Page Name> page for ZeroClaw Streamlit UI."""

import streamlit as st
from lib.session_state import initialize_session_state

def render() -> None:
    """Render the <Page Name> page."""
    st.title("<Page Name>")
    # Page implementation here
    pass

if __name__ == "__main__":
    initialize_session_state()
    render()
```

## State Management

All pages should use the centralized state management from `lib/session_state.py`:

```python
from lib.session_state import (
    initialize_session_state,
    update_settings,
    update_gateway_state,
    add_activity
)

# Initialize on app start
initialize_session_state()

# Update settings
update_settings(
    gateway_url="http://localhost:3000",
    theme="matrix-green"
)

# Access state
gateway_url = st.session_state.get('gateway_url')
```

## Configuration Persistence

Settings are saved to `config.json` in the app root directory:

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

This file is automatically created/updated when settings are saved.
