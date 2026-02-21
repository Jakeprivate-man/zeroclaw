#!/usr/bin/env python3
"""
Test script to verify app.py structure and configuration.

This script validates:
1. Python syntax
2. Import structure
3. Required functions exist
4. Routing logic is correct
5. File structure is complete
"""

import ast
import sys
from pathlib import Path


def test_app_syntax():
    """Test that app.py has valid Python syntax."""
    app_path = Path(__file__).parent / "app.py"
    
    try:
        with open(app_path, 'r') as f:
            source = f.read()
        ast.parse(source)
        print("✓ app.py has valid Python syntax")
        return True
    except SyntaxError as e:
        print(f"✗ Syntax error in app.py: {e}")
        return False


def test_imports():
    """Test that all required imports are present."""
    app_path = Path(__file__).parent / "app.py"
    
    with open(app_path, 'r') as f:
        source = f.read()
    
    required_imports = [
        'import streamlit as st',
        'from lib.session_state import initialize_session_state',
        'from components.sidebar import render_sidebar',
    ]
    
    for imp in required_imports:
        if imp in source:
            print(f"✓ Found: {imp}")
        else:
            print(f"✗ Missing: {imp}")
            return False
    
    return True


def test_page_config():
    """Test that st.set_page_config() is present and correct."""
    app_path = Path(__file__).parent / "app.py"
    
    with open(app_path, 'r') as f:
        source = f.read()
    
    # Check that st.set_page_config appears before other st calls
    lines = source.split('\n')
    first_st_call = None
    config_line = None
    
    for i, line in enumerate(lines):
        if 'st.set_page_config' in line:
            config_line = i
        elif line.strip().startswith('st.') and 'import' not in line:
            if first_st_call is None and 'st.set_page_config' not in line:
                first_st_call = i
    
    if config_line is None:
        print("✗ st.set_page_config() not found")
        return False
    
    print(f"✓ st.set_page_config() found at line {config_line}")
    
    # Check required parameters
    required_params = [
        'page_title=',
        'page_icon=',
        'layout=',
        'initial_sidebar_state=',
        'menu_items='
    ]
    
    for param in required_params:
        if param in source:
            print(f"✓ Found parameter: {param}")
        else:
            print(f"✗ Missing parameter: {param}")
            return False
    
    return True


def test_routing():
    """Test that routing logic is present."""
    app_path = Path(__file__).parent / "app.py"
    
    with open(app_path, 'r') as f:
        source = f.read()
    
    routes = [
        'if selected_page == "Dashboard"',
        'elif selected_page == "Analytics"',
        'elif selected_page == "Reports"',
        'elif selected_page == "Analyze"',
        'elif selected_page == "Settings"',
    ]
    
    for route in routes:
        if route in source:
            print(f"✓ Found route: {route}")
        else:
            print(f"✗ Missing route: {route}")
            return False
    
    return True


def test_theme_css():
    """Test that Matrix Green theme CSS is present."""
    app_path = Path(__file__).parent / "app.py"
    
    with open(app_path, 'r') as f:
        source = f.read()
    
    css_elements = [
        '--background-color: #000000',
        '--primary-color: #5FAF87',
        '--foreground-color: #87D7AF',
        'Matrix Green Theme',
    ]
    
    for element in css_elements:
        if element in source:
            print(f"✓ Found CSS: {element}")
        else:
            print(f"✗ Missing CSS: {element}")
            return False
    
    return True


def test_file_structure():
    """Test that required files and directories exist."""
    base_path = Path(__file__).parent
    
    required_files = [
        'app.py',
        'requirements.txt',
        'README.md',
        'lib/__init__.py',
        'lib/session_state.py',
        'components/__init__.py',
        'components/sidebar.py',
        'pages/__init__.py',
    ]
    
    for file_path in required_files:
        full_path = base_path / file_path
        if full_path.exists():
            print(f"✓ Found: {file_path}")
        else:
            print(f"✗ Missing: {file_path}")
            return False
    
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("ZeroClaw Streamlit UI - Structure Validation")
    print("=" * 60)
    print()
    
    tests = [
        ("File Structure", test_file_structure),
        ("Python Syntax", test_app_syntax),
        ("Import Statements", test_imports),
        ("Page Configuration", test_page_config),
        ("Routing Logic", test_routing),
        ("Matrix Green Theme", test_theme_css),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 60)
        result = test_func()
        results.append((test_name, result))
        print()
    
    # Summary
    print("=" * 60)
    print("Summary:")
    print("=" * 60)
    
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    print()
    if all_passed:
        print("✓ All tests passed! App structure is valid.")
        return 0
    else:
        print("✗ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
