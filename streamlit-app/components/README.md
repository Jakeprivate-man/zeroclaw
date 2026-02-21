# ZeroClaw Streamlit Components

This directory contains reusable Streamlit components for the ZeroClaw UI.

## Available Components

### Sidebar Navigation (`sidebar.py`)

The main navigation sidebar for the application.

**Usage:**

```python
from components import render_sidebar

# Render sidebar and get selected page
selected_page = render_sidebar()
# Returns: "Dashboard", "Analytics", "Reports", "Analyze", or "Settings"
```

**Features:**

- Matrix green theme styling (black background, green accents)
- Navigation menu with 5 pages:
  - Dashboard (📊)
  - Analytics (📈)
  - Reports (📄)
  - Analyze (🔍)
  - Settings (⚙️)
- Gateway connection status display
- Online/offline indicator (dynamic based on `gateway_health` session state)
- Responsive design (collapsible on mobile)

**Session State Dependencies:**

- `gateway_url` (optional, default: `localhost:3000`) - Gateway URL to display
- `gateway_health` (optional, default: `True`) - Gateway online status

**Return Value:**

Returns the selected page name as a clean string without emoji prefix:
- "Dashboard"
- "Analytics"
- "Reports"
- "Analyze"
- "Settings"

**Example:**

```python
import streamlit as st
from components import render_sidebar

# Initialize session state
if 'gateway_url' not in st.session_state:
    st.session_state.gateway_url = 'localhost:3000'

if 'gateway_health' not in st.session_state:
    st.session_state.gateway_health = True

# Render sidebar
page = render_sidebar()

# Route to appropriate page
if page == "Dashboard":
    st.title("Dashboard")
    # Dashboard content...
elif page == "Analytics":
    st.title("Analytics")
    # Analytics content...
# etc.
```

## Testing

Run the test script to verify the sidebar component:

```bash
streamlit run streamlit-app/test_sidebar.py
```

The test script includes:
- Live sidebar preview
- Session state display
- Gateway URL and status controls
