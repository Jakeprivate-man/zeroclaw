# Streamlit Official API Reference for ZeroClaw Migration

**Purpose:** This document contains official Streamlit documentation excerpts for all APIs used in the ZeroClaw migration.
**Source:** https://docs.streamlit.io/
**Last Updated:** February 21, 2026

---

# Layout & Containers

## st.columns

### Function Signature

```python
st.columns(spec, *, gap="small", vertical_alignment="top", border=False, width="stretch")
```

### Parameters

- **`spec`** (int or Iterable of numbers): Controls the number and width of columns
  - Integer: Creates that many equal-width columns
  - Iterable: Specifies relative widths (e.g., `[0.7, 0.3]` or `[1, 2, 3]`)

- **`gap`** (string or None): Spacing between columns
  - Options: `"xxsmall"` (0.25rem) through `"xxlarge"` (8rem)
  - Default: `"small"` (1rem)
  - `None` removes gaps

- **`vertical_alignment`** (string): Vertical content alignment
  - Options: `"top"` (default), `"center"`, `"bottom"`

- **`border`** (bool): Show borders around columns (default: `False`)

- **`width`** (string or int): Column group width
  - `"stretch"` (default): matches parent container
  - Integer: fixed pixel width (capped by parent)

### Usage Examples

```python
# Context manager (preferred)
col1, col2, col3 = st.columns(3)
with col1:
    st.header("Column 1")
    st.image("image1.jpg")

# Direct method calls
col1, col2 = st.columns([3, 1])
col1.line_chart(df)
col2.write(df)

# Vertical alignment
left, middle, right = st.columns(3, vertical_alignment="bottom")
left.text_input("Input")
middle.button("Click", use_container_width=True)
right.checkbox("Check")
```

### Best Practices

- **Limit nesting**: Don't nest columns more than once
- **Use `with` statements**: Context manager syntax is clearer
- **Leverage vertical alignment**: Consistent widget heights without nested containers

---

## st.container

### Function Signature

```python
st.container(*, border=None, key=None, width="stretch", height="content",
             horizontal=False, horizontal_alignment="left",
             vertical_alignment="top", gap="small")
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `border` | bool or None | None | Show border; auto-displays if fixed height set |
| `key` | str or None | None | Stable identity and CSS class prefix |
| `width` | "stretch"/"content"/int | "stretch" | Container width |
| `height` | "content"/"stretch"/int | "content" | Container height; int = scrollable |
| `horizontal` | bool | False | Horizontal flexbox layout |
| `horizontal_alignment` | str | "left" | "left", "center", "right", "distribute" |
| `vertical_alignment` | str | "top" | "top", "center", "bottom", "distribute" |
| `gap` | str or None | "small" | Gap between elements |

### Scrolling Behavior

- Fixed integer height: container becomes scrollable if content exceeds
- **Important**: "Avoid heights exceeding 500 pixels" on mobile

### Examples

```python
# Basic container
with st.container():
    st.write("Content")
    st.bar_chart(data)

# Fixed-height scrollable
with st.container(height=300):
    st.markdown(long_text)

# Horizontal layout
flex = st.container(horizontal=True, horizontal_alignment="right")
for i in range(3):
    flex.button(f"Button {i+1}")
```

---

## st.sidebar

### Overview

Organizes widgets into a left sidebar, helping users focus on main content.

### Usage Patterns

```python
# Object notation
selectbox = st.sidebar.selectbox("Question", ("A", "B", "C"))

# Context manager (preferred)
with st.sidebar:
    radio = st.radio("Method", ("Standard", "Express"))
```

### Limitations

**Unsupported with object notation** (use `with` instead):
- `st.echo`
- `st.spinner`
- `st.toast`

### Features

- Resizable: Users can drag right border
- Organization: Keeps widgets accessible
- Flexible: Supports most Streamlit elements

---

## st.tabs

### Function Signature

```python
st.tabs(tabs, *, width="stretch", default=None)
```

### Parameters

- **`tabs`** (list of str): One tab per string. First tab displays by default. Supports GitHub-flavored Markdown.
- **`width`** (str or int): Container width (`"stretch"` or pixel integer)
- **`default`** (str or None): Initially selected tab (must match label exactly)

### Key Limitation

"All content within every tab is computed and sent to the frontend, regardless of which tab is selected." No conditional rendering.

### Usage

```python
# Context manager (preferred)
tab1, tab2, tab3 = st.tabs(["Cat", "Dog", "Owl"])
with tab1:
    st.header("A cat")
    st.image("cat.jpg")

# Direct method calls
tab1, tab2 = st.tabs(["📈 Chart", "🗃 Data"])
tab1.line_chart(df)
tab2.write(df)
```

---

# State Management

## st.session_state

### Overview

Maintains variables across script reruns within individual user sessions. Persists across pages in multipage apps.

### Initialization

```python
# Dictionary-style
if 'key' not in st.session_state:
    st.session_state['key'] = 'value'

# Attribute-style
if 'key' not in st.session_state:
    st.session_state.key = 'value'
```

### Reading and Updating

```python
# Retrieve
st.write(st.session_state.key)
st.write(st.session_state)  # All state

# Modify
st.session_state.key = 'new_value'  # Attribute
st.session_state['key'] = 'new_value'  # Dictionary
```

### Deleting Items

```python
del st.session_state[key]  # Single key

# Clear all
for key in st.session_state.keys():
    del st.session_state[key]
```

### Widget Integration

"Every widget with a key is automatically added to Session State."

```python
st.text_input("Name", key="name")
# st.session_state.name now exists
```

### Callbacks

Callbacks execute upon widget changes. Execution order: callback first, then script top-to-bottom.

**Supported parameters:**
- `on_change` or `on_click`: callback function
- `args`: positional arguments tuple
- `kwargs`: keyword arguments dictionary

**Compatible widgets:**
- **on_change**: checkbox, color_picker, date_input, data_editor, file_uploader, multiselect, number_input, radio, select_slider, selectbox, slider, text_area, text_input, time_input, toggle
- **on_click**: button, download_button, form_submit_button

### Forms and Callbacks

"The callback gets executed upon clicking on the submit button."

```python
def form_callback():
    st.write(st.session_state.my_slider)

with st.form(key='my_form'):
    st.slider('My slider', 0, 10, 5, key='my_slider')
    st.form_submit_button(label='Submit', on_click=form_callback)
```

### Key Limitations

- State resets when users reload browser tabs or follow Markdown links
- Only `st.form_submit_button` supports callbacks within forms
- Modifying widget values via Session State after widget instantiation raises exceptions
- Button-type widgets cannot have state set via API
- Setting both Session State and widget `value` parameters simultaneously produces warnings

---

# Widgets

## st.selectbox

### Function Signature

```python
st.selectbox(label, options, index=0, format_func=special_internal_function,
             key=None, help=None, on_change=None, args=None, kwargs=None,
             *, placeholder=None, disabled=False, label_visibility="visible",
             accept_new_options=False, width="stretch")
```

### Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `label` | str | Widget description |
| `options` | Iterable | Select options |
| `index` | int or None | Preselected index (0 = first, None = empty) |
| `placeholder` | str or None | Text when nothing selected |
| `accept_new_options` | bool | Allow user-entered values |

### Examples

```python
# Basic (auto-selects first)
option = st.selectbox("Contact method", ("Email", "Phone", "Mobile"))

# Empty initialization
option = st.selectbox("Contact", ("Email", "Phone"),
                      index=None, placeholder="Select...")

# User-defined options
option = st.selectbox("Email", ["foo@example.com", "bar@example.com"],
                      index=None, placeholder="Select or enter new",
                      accept_new_options=True)
```

---

## st.checkbox

### Function Signature

```python
st.checkbox(label, value=False, key=None, help=None, on_change=None,
            args=None, kwargs=None, *, disabled=False,
            label_visibility="visible", width="content")
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `label` | str | Checkbox purpose (supports Markdown) |
| `value` | bool | Initial state (default: False) |
| `disabled` | bool | Disable interaction (default: False) |
| `label_visibility` | str | "visible", "hidden", "collapsed" |

### Returns

**bool** — Whether checkbox is checked

### Example

```python
agree = st.checkbox("I agree")
if agree:
    st.write("Great!")
```

---

## st.text_input

### Function Signature

```python
st.text_input(label, value="", max_chars=None, key=None, type="default",
              help=None, autocomplete=None, on_change=None, args=None,
              kwargs=None, *, placeholder=None, disabled=False,
              label_visibility="visible", icon=None, width="stretch")
```

### Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `label` | str | Input purpose (supports Markdown) |
| `value` | object or None | Initial text value |
| `max_chars` | int or None | Maximum character limit |
| `type` | "default" or "password" | "password" masks input |
| `placeholder` | str or None | Text when empty |
| `icon` | str or None | Emoji or Material icon |

### Returns

**(str or None)**: Current input value or None

### Examples

```python
# Basic
title = st.text_input("Movie title", "Life of Brian")

# Password
password = st.text_input("Password", type="password")

# With icon
email = st.text_input("Email", icon="📧")
```

---

## st.button

### Function Signature

```python
st.button(label, key=None, help=None, on_click=None, args=None, kwargs=None,
          *, type="secondary", icon=None, disabled=False,
          use_container_width=False, width="content")
```

### Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `label` | str | Button text |
| `on_click` | callable | Callback function |
| `type` | str | "primary", "secondary", "tertiary" |
| `use_container_width` | bool | Expand to container width |

### Returns

**bool**: True if clicked on last run

### Example

```python
if st.button("Submit"):
    st.write("Submitted!")

# With callback
def on_submit():
    st.session_state.submitted = True

st.button("Submit", on_click=on_submit)
```

---

## st.download_button

### Function Signature

```python
st.download_button(label, data, file_name=None, mime=None, key=None,
                   help=None, on_click="rerun", args=None, kwargs=None,
                   *, type="secondary", icon=None, disabled=False,
                   use_container_width=None, width="content")
```

### Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `label` | str | Button text |
| `data` | str/bytes/file/callable | File contents or generator |
| `file_name` | str | Downloaded filename |
| `mime` | str or None | MIME type (auto-detected if None) |
| `on_click` | str/callable | "rerun", "ignore", callable, or None |

### MIME Behavior

- String/text: "text/plain"
- Binary/bytes: "application/octet-stream"

### Examples

```python
# CSV download
csv = df.to_csv().encode("utf-8")
st.download_button("Download CSV", csv, "data.csv", "text/csv")

# Text file
message = st.text_area("Message")
st.download_button("Download text", message, "message.txt")

# Deferred generation
def make_report():
    return "col1,col2\n1,2".encode("utf-8")

st.download_button("Download report", make_report, "report.csv", "text/csv")
```

---

# Forms

## st.form

### Function Signature

```python
st.form(key, clear_on_submit=False, *, enter_to_submit=True, border=True,
        width="stretch", height="content")
```

### Overview

"Create a form that batches elements together with a 'Submit' button." All widget values sent in a batch when submitted.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key` | str | Required | Unique form identifier |
| `clear_on_submit` | bool | False | Reset all widgets after submission |
| `enter_to_submit` | bool | True | Allow Enter key to submit |
| `border` | bool | True | Display border |

### Constraints

- **Required**: "Every form must contain a st.form_submit_button"
- **Forbidden**: st.button and st.download_button cannot be in forms
- **No embedding**: Forms cannot be inside other forms
- **Callbacks**: Only st.form_submit_button can have callbacks

### Usage

```python
with st.form("my_form"):
    st.write("Inside the form")
    slider_val = st.slider("Form slider")
    checkbox_val = st.checkbox("Form checkbox")

    submitted = st.form_submit_button("Submit")
    if submitted:
        st.write("slider", slider_val, "checkbox", checkbox_val)
```

---

# Charts

## Simple Chart Types

### st.line_chart

Display a line chart for time-series data and trends.

```python
st.line_chart(df)
```

### st.bar_chart

Display a bar chart for categorical comparisons.

```python
st.bar_chart(df)
```

### st.area_chart

Display an area chart for cumulative trends.

```python
st.area_chart(df)
```

## Advanced Charts

### st.plotly_chart

Display an interactive Plotly chart with extensive customization.

```python
import plotly.graph_objects as go

fig = go.Figure()
fig.add_trace(go.Scatter(x=data['date'], y=data['value'],
                         name='Series', line=dict(color='#5FAF87')))
st.plotly_chart(fig, use_container_width=True)
```

**Other options**: st.altair_chart, st.vega_lite_chart, st.pyplot, st.pydeck_chart

---

# Text & Markdown

## st.markdown

### Function Signature

```python
st.markdown(body, unsafe_allow_html=False, *, help=None)
```

### Parameters

- **`body`** (str): Markdown content
- **`unsafe_allow_html`** (bool): Allow raw HTML (default: False)
- **`help`** (str or None): Tooltip text

### Usage

```python
st.markdown("**Bold text** and *italic*")

# With HTML
st.markdown("""
<div style="background: #0a0a0a; padding: 1rem;">
    Custom styled content
</div>
""", unsafe_allow_html=True)
```

---

# Dialogs

## st.dialog

### Function Signature

```python
@st.dialog(title, *, width="small", dismissible=True, icon=None, on_dismiss="ignore")
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `title` | str | Dialog heading (supports Markdown) |
| `width` | str | "small" (500px), "medium" (750px), "large" (1280px) |
| `dismissible` | bool | Can close via click outside/ESC (default: True) |
| `icon` | str or None | Emoji or Material icon |
| `on_dismiss` | str or callable | "ignore", "rerun", or function |

### Key Behaviors

- "Dialog functions inherit fragment behavior"
- Use Session State for wider app access
- `st.sidebar` not supported in dialogs
- Only one dialog may be called per script run

### Example

```python
@st.dialog("Cast your vote")
def vote(item):
    st.write(f"Why is {item} your favorite?")
    reason = st.text_input("Because...")
    if st.button("Submit"):
        st.session_state.vote = {"item": item, "reason": reason}
        st.rerun()

if "vote" not in st.session_state:
    if st.button("A"):
        vote("A")
    if st.button("B"):
        vote("B")
else:
    st.write(f"Voted: {st.session_state.vote['item']}")
```

---

# Configuration

## st.set_page_config

### Function Signature

```python
st.set_page_config(page_title=None, page_icon=None, layout=None,
                   initial_sidebar_state=None, menu_items=None)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `page_title` | str or None | Browser tab title |
| `page_icon` | str or None | Emoji, `:shortcode:`, "random", or `:material/icon:` |
| `layout` | str or None | "centered" (default) or "wide" |
| `initial_sidebar_state` | str or int | "auto", "expanded", "collapsed", or pixel width |
| `menu_items` | dict | "Get Help", "Report a Bug", "About" |

### Important Notes

- "This command can be called multiple times in a script run"
- Each call overrides only specified parameters
- "Material icons display in black regardless of browser theme"

### Example

```python
st.set_page_config(
    page_title="ZeroClaw UI",
    page_icon="🦀",
    layout="wide",
    initial_sidebar_state="expanded"
)
```

---

# Best Practices for ZeroClaw Migration

## Real-Time Updates

Use `time.sleep()` loop or external autorefresh component:

```python
import time

placeholder = st.empty()
while True:
    with placeholder.container():
        render_dashboard()
    time.sleep(2)
```

## Session State Organization

Namespace your state to avoid collisions:

```python
# Initialize all state at top of app
if 'dashboard' not in st.session_state:
    st.session_state.dashboard = {
        'stats': None,
        'agents': [],
        'last_update': None
    }
```

## Custom CSS

Inject via st.markdown:

```python
st.markdown("""
<style>
.metric-card {
    background: #0a0a0a;
    border: 1px solid #2d5f4f;
    border-radius: 0.5rem;
    padding: 1rem;
}
</style>
""", unsafe_allow_html=True)
```

## Plotly Charts (Matrix Green Theme)

```python
import plotly.graph_objects as go

fig = go.Figure()
fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="#000000",
    plot_bgcolor="#000000",
    font=dict(color="#87D7AF")
)
fig.add_trace(go.Scatter(
    x=data['date'],
    y=data['value'],
    line=dict(color='#5FAF87', width=2)
))
st.plotly_chart(fig, use_container_width=True)
```

---

# Additional Resources

- **Official Docs**: https://docs.streamlit.io/
- **API Reference**: https://docs.streamlit.io/develop/api-reference
- **Cheat Sheet**: https://docs.streamlit.io/develop/quick-reference/cheat-sheet
- **Component Gallery**: https://streamlit.io/components

---

**End of Streamlit API Reference**
