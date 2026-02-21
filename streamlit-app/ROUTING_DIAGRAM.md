# ZeroClaw Streamlit UI - Routing Architecture

## Application Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         app.py                                   │
│                   (Main Entry Point)                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              st.set_page_config()                                │
│         (MUST BE FIRST STREAMLIT COMMAND)                        │
│                                                                   │
│  • Page title: "ZeroClaw UI"                                    │
│  • Page icon: 🦀                                                │
│  • Layout: wide                                                  │
│  • Sidebar: expanded                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│           initialize_session_state()                             │
│              (lib/session_state.py)                              │
│                                                                   │
│  • Initialize app state                                          │
│  • Setup user preferences                                        │
│  • Configure API connection                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Matrix Green Theme CSS                              │
│                                                                   │
│  • Background: #000000 (black)                                   │
│  • Primary: #5FAF87 (mint green)                                │
│  • Secondary: #87D7AF (sea green)                               │
│  • Style all components                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│            render_sidebar()                                      │
│          (components/sidebar.py)                                 │
│                                                                   │
│  • Display navigation menu                                       │
│  • Show status indicators                                        │
│  • Return selected page                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                      selected_page
                              │
        ┌─────────────────────┼──────────────────────┐
        │                     │                      │
        ▼                     ▼                      ▼
┌───────────────┐    ┌───────────────┐     ┌───────────────┐
│  Dashboard    │    │   Analytics   │     │    Reports    │
│  (Agent 17)   │    │   (Agent 18)  │     │   (Agent 13)  │
│               │    │               │     │               │
│  📊 Metrics   │    │  📈 Charts    │     │  📄 Logs      │
│  Status       │    │  Trends       │     │  Export       │
│  Actions      │    │  Usage        │     │  Search       │
└───────────────┘    └───────────────┘     └───────────────┘
        │                     │                      │
        ▼                     ▼                      ▼
┌───────────────┐    ┌───────────────┐
│   Analyze     │    │   Settings    │
│  (Agent 19)   │    │  (Agent 21)   │
│               │    │               │
│  🔍 Deep      │    │  ⚙️ Config    │
│  Analysis     │    │  Preferences  │
│  Diagnostics  │    │  API Setup    │
└───────────────┘    └───────────────┘
        │                     │
        └──────────┬──────────┘
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Footer                                    │
│                                                                   │
│  ZeroClaw Web UI | Built with Streamlit | Matrix Green Theme   │
└─────────────────────────────────────────────────────────────────┘
```

## Routing Logic

```python
selected_page = render_sidebar()

if selected_page == "Dashboard":
    dashboard.render()

elif selected_page == "Analytics":
    analytics.render()

elif selected_page == "Reports":
    reports.render()

elif selected_page == "Analyze":
    analyze.render()

elif selected_page == "Settings":
    settings.render()

else:
    # Fallback for unknown pages
    st.error(f"Unknown page: {selected_page}")
```

## Page Module Interface

Each page module must implement a `render()` function:

```python
# pages/example.py
import streamlit as st

def render():
    """
    Render the page content.
    
    This function is called by app.py when the page is selected.
    It should contain all the UI logic for the page.
    """
    st.title("Page Title")
    # Page implementation here
```

## Component Integration

### Sidebar Component

```python
# components/sidebar.py
import streamlit as st

def render_sidebar() -> str:
    """
    Render the navigation sidebar.
    
    Returns:
        str: The name of the selected page
    """
    with st.sidebar:
        # Sidebar implementation
        page = st.radio("Navigation", ["Dashboard", "Analytics", ...])
    return page
```

### Session State

```python
# lib/session_state.py
import streamlit as st

def initialize_session_state():
    """
    Initialize all session state variables.
    
    This function is called once at app startup.
    """
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        # Initialize other state variables
```

## Data Flow

```
User Input
    │
    ▼
Sidebar Selection
    │
    ▼
app.py Routing
    │
    ▼
Page render()
    │
    ├─► API Client (lib/api_client.py)
    │       │
    │       ▼
    │   ZeroClaw Backend
    │
    ├─► Mock Data (lib/mock_data.py)
    │
    └─► Session State (lib/session_state.py)
```

## Error Handling

```
Import Error (missing page module)
    │
    ▼
Graceful Degradation
    │
    ▼
Display Placeholder UI
    │
    └─► "Page under construction by Agent X"
```

## Theme Application

```
app.py loads
    │
    ▼
st.markdown() with CSS
    │
    ▼
All components inherit theme
    │
    ├─► Sidebar: black bg, green borders
    ├─► Headers: mint green
    ├─► Buttons: green hover
    ├─► Inputs: green focus
    ├─► Metrics: green accents
    └─► Tables: green borders
```

## Dependencies

```
app.py
    │
    ├─► lib/session_state.py (Agent 24)
    ├─► components/sidebar.py (Agent 20)
    │
    └─► pages/
            ├─► dashboard.py (Agent 17)
            ├─► analytics.py (Agent 18)
            ├─► reports.py (Agent 13)
            ├─► analyze.py (Agent 19)
            └─► settings.py (Agent 21)
```

## Page Loading Sequence

```
1. Import attempt
   │
   ├─► Success: Page module available
   │   └─► Call page.render()
   │
   └─► Failure: ImportError
       └─► Display placeholder
           └─► Show construction message
```

## URL Parameters (Future Enhancement)

Currently, the app uses sidebar-based navigation. URL parameters could be added:

```
http://localhost:8501?page=dashboard
http://localhost:8501?page=analytics&timerange=7d
http://localhost:8501?page=reports&filter=error
```

This would be implemented by:
1. Reading query parameters in app.py
2. Overriding sidebar selection if URL param exists
3. Updating URL on sidebar selection

## State Management

```
Session State Variables:
    │
    ├─► initialized: bool
    ├─► current_page: str
    ├─► api_connected: bool
    ├─► theme: str
    │
    └─► user_preferences: dict
            ├─► auto_refresh: bool
            ├─► refresh_interval: int
            └─► notifications_enabled: bool
```

## Performance Considerations

1. **CSS Loaded Once**: Theme CSS is loaded on app startup, not on every page change
2. **Lazy Imports**: Pages only imported when needed (try/except pattern)
3. **Session State**: Minimal state stored, cleared on app restart
4. **Sidebar Caching**: Could use `@st.cache_data` for static sidebar content

## Security Considerations

1. **No User Input in Routing**: Page selection via radio buttons only
2. **No Dynamic Imports**: All imports are static and known
3. **No eval/exec**: No dynamic code execution
4. **Sanitized Inputs**: All user inputs in forms will be sanitized by page modules
