# ZeroClaw Streamlit UI

Real-time monitoring and analytics interface for the ZeroClaw agent runtime.

## Features

- **Dashboard**: Real-time agent status and performance metrics
- **Analytics**: Historical performance trends and token usage tracking
- **Reports**: Conversation logs and activity reports
- **Analyze**: Deep conversation analysis and diagnostics
- **Settings**: API configuration and preferences

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### Running the App

```bash
# Run the Streamlit app
streamlit run app.py
```

The app will be available at `http://localhost:8501`

## Project Structure

```
streamlit-app/
├── app.py                  # Main application entry point
├── components/             # Reusable UI components
│   └── sidebar.py         # Navigation sidebar
├── pages/                  # Page implementations
│   ├── dashboard.py       # Dashboard page
│   ├── analytics.py       # Analytics page
│   ├── reports.py         # Reports page
│   ├── analyze.py         # Analyze page
│   └── settings.py        # Settings page
├── lib/                    # Shared utilities
│   ├── api_client.py      # API client for ZeroClaw backend
│   ├── session_state.py   # Session state management
│   └── mock_data.py       # Mock data generators
└── requirements.txt        # Python dependencies
```

## Architecture

### Routing

The app uses a simple routing system based on sidebar selection:
- `app.py` handles page configuration and routing
- `components/sidebar.py` renders navigation and returns selected page
- Individual page modules in `pages/` contain render functions

### Theming

The app uses a **Matrix Green** theme inspired by terminal aesthetics:
- Background: Pure black (#000000)
- Primary: Mint green (#5FAF87)
- Secondary: Sea green (#87D7AF)
- All CSS is defined in `app.py` for centralized management

### Session State

Session state is managed through `lib/session_state.py`:
- API connection status
- User preferences
- Navigation state
- Cache management

## Development

### Adding a New Page

1. Create a new file in `pages/` (e.g., `pages/my_page.py`)
2. Implement a `render()` function
3. Import in `app.py`
4. Add routing logic in the main routing section

### Adding a Component

1. Create a new file in `components/` (e.g., `components/my_component.py`)
2. Implement component functions
3. Import where needed

## Configuration

Configuration is handled through:
- Environment variables (see `.env.example`)
- Session state for runtime settings
- Settings page for user preferences

## Testing

Run the test suite:

```bash
# Test individual modules
python test_modules.py

# Test API client
python test_api_client.py

# Test sidebar
python test_sidebar.py
```

## Matrix Green Theme

The app features a custom Matrix Green theme with:
- Black background for reduced eye strain
- Green accents for cyberpunk aesthetic
- Monospace fonts for code-like appearance
- Consistent styling across all components

## Agent Integration

This UI connects to the ZeroClaw Rust runtime via HTTP API:
- Real-time metrics streaming
- Agent control and monitoring
- Log aggregation and analysis
- Performance analytics

## License

This project is part of the ZeroClaw ecosystem. See main repository for license details.
