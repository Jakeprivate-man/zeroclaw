# Analytics Components

Interactive chart components for analytics visualization using Plotly and Matrix Green theme.

## Components

### RequestVolumeChart

Displays request volume over time with successful vs failed request breakdown.

### ResponseTimeChart

Displays response time metrics over time with percentile breakdown (avg, p50, p95, p99).

### RequestDistributionChart

Displays request distribution by category/type using an interactive pie/donut chart.

## Component Details

### RequestVolumeChart

#### Usage

```python
import streamlit as st
from components.analytics import request_volume_chart

# Initialize session state
from lib.session_state import initialize_session_state
initialize_session_state()

# Set time range (optional, defaults to '7d')
st.session_state.time_range = '7d'

# Render the chart
request_volume_chart()
```

#### Features

- **Two data series**: Successful requests (green) and failed requests (red)
- **Interactive tooltips**: Hover over points to see detailed information
- **Time range support**: 24h, 7d, 30d, 90d, 1y
- **Matrix Green theme**: Uses #5FAF87 (primary) and #87D7AF (secondary)
- **Responsive**: Automatically adjusts to container width
- **Legend**: Interactive legend to toggle series visibility

#### Time Range Options

- `'24h'` - Last 24 hours (24 data points)
- `'7d'` - Last 7 days (7 data points)
- `'30d'` - Last 30 days (30 data points)
- `'90d'` - Last 90 days (30 data points, sampled)
- `'1y'` - Last year (12 data points, monthly)

#### Color Scheme

- **Successful requests**: #5FAF87 (Matrix Green primary)
- **Failed requests**: #FF5555 (Preserved red for errors)
- **Background**: #000000 (Pure black)
- **Text/labels**: #87D7AF (Matrix Green secondary)
- **Grid lines**: #1a1a1a (Dark gray)

#### Dependencies

- `streamlit` - UI framework
- `plotly` - Charting library
- `lib.session_state` - Session state management
- `lib.mock_data` - Mock data generation

### ResponseTimeChart

Displays response time percentiles over time with average, p50, p95, and p99 metrics.

#### Usage

```python
import streamlit as st
from components.analytics import response_time_chart

# Initialize session state
from lib.session_state import initialize_session_state
initialize_session_state()

# Set time range (optional, defaults to '7d')
st.session_state.time_range = '7d'

# Render the chart
response_time_chart()
```

#### Features

- **Four data series**: Average (green), p50 (sea green), p95 (yellow), p99 (red)
- **Interactive tooltips**: Hover over points to see detailed response time data
- **Time range support**: 24h, 7d, 30d, 90d, 1y
- **Matrix Green theme**: Primary colors with preserved yellow/red for warning thresholds
- **Responsive**: Automatically adjusts to container width

### RequestDistributionChart

Displays request distribution by category/type using an interactive pie/donut chart.

#### Usage

```python
import streamlit as st
from components.analytics import request_distribution_chart

# Initialize session state
from lib.session_state import initialize_session_state
initialize_session_state()

# Set time range (optional, defaults to '7d')
st.session_state.time_range = '7d'

# Render the chart
request_distribution_chart()
```

#### Features

- **Pie/Donut chart**: Visual distribution of request categories
- **Interactive tooltips**: Hover over slices to see count and percentage
- **Multiple categories**: API Requests, Agent Tasks, Report Generation, Data Analysis, etc.
- **Time range support**: 24h, 7d, 30d, 90d, 1y (affects total volume, not distribution)
- **Matrix Green theme**: Various shades of green/turquoise for different categories
- **Legend**: Category labels with color coding
- **Responsive**: Automatically adjusts to container width

#### Color Scheme

- **Category 1**: #5FAF87 (Mint green - primary)
- **Category 2**: #87D7AF (Sea green - secondary)
- **Category 3**: #87D787 (Light green)
- **Category 4**: #5FD7AF (Turquoise green)
- **Category 5**: #5FD7D7 (Cyan)
- **Category 6**: #87AFAF (Muted green-gray)
- **Category 7**: #5FAFAF (Teal)
- **Category 8**: #87D7D7 (Light cyan)
- **Background**: #000000 (Pure black)
- **Text/labels**: #87D7AF (Matrix Green secondary)

#### Data Structure

The component expects data in the following format:

```python
[
    {'category': 'API Requests', 'count': 183, 'percentage': 24.4},
    {'category': 'Agent Tasks', 'count': 168, 'percentage': 22.4},
    # ... more categories
]
```

## Development

### Adding New Charts

1. Create a new Python file in this directory (e.g., `response_time_chart.py`)
2. Implement a `render()` function that:
   - Gets time range from session state
   - Generates or fetches data
   - Creates Plotly figure with Matrix Green theme
   - Displays using `st.plotly_chart()`
3. Add import to `__init__.py`
4. Update this README

### Testing

```python
# Import test
from components.analytics import request_volume_chart
assert callable(request_volume_chart)

# Render test (requires Streamlit context)
import streamlit as st
from lib.session_state import initialize_session_state

initialize_session_state()
request_volume_chart()
```
