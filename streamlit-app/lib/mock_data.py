"""Mock data generators for testing and development.

This module provides realistic mock data generation functions for all major
data types used in the application, including time series, agents, activities,
reports, and analytics.
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Callable


def generate_time_series_data(
    time_range: str,
    base_value: int,
    variance: int,
    value_key: str = 'value'
) -> List[Dict[str, Any]]:
    """Generate time-series data points for a given time range.

    Args:
        time_range: Time range ('24h', '7d', '30d', '90d', '1y')
        base_value: Base value around which to generate data
        variance: Maximum variance from base value (+/-)
        value_key: Key name for the value field in output

    Returns:
        List of data points with timestamp, date, and value
    """
    intervals: Dict[str, Tuple[int, Callable[[int], datetime]]] = {
        '24h': (24, lambda i: datetime.now() - timedelta(hours=24-i)),
        '7d': (7, lambda i: datetime.now() - timedelta(days=7-i)),
        '30d': (30, lambda i: datetime.now() - timedelta(days=30-i)),
        '90d': (30, lambda i: datetime.now() - timedelta(days=(90-i)*3)),
        '1y': (12, lambda i: datetime.now() - timedelta(days=(365-i)*30))
    }

    count, date_fn = intervals.get(
        time_range,
        (7, lambda i: datetime.now() - timedelta(days=7-i))
    )

    data = []
    for i in range(count):
        value = max(0, base_value + random.randint(-variance, variance))
        timestamp = date_fn(i)
        data.append({
            'timestamp': int(timestamp.timestamp()),
            'date': timestamp.strftime('%Y-%m-%d %H:%M'),
            value_key: value
        })
    return data


def generate_request_volume_data(time_range: str) -> List[Dict[str, Any]]:
    """Generate mock request volume data with success/failure breakdown.

    Args:
        time_range: Time range ('24h', '7d', '30d', '90d', '1y')

    Returns:
        List of data points with total, successful, and failed requests
    """
    data = generate_time_series_data(time_range, 1500, 300, 'total')

    for point in data:
        total = point['total']
        # Failure rate between 1-5%
        failed = random.randint(int(total * 0.01), int(total * 0.05))
        point['successful'] = total - failed
        point['failed'] = failed

    return data


def generate_response_time_data(time_range: str) -> List[Dict[str, Any]]:
    """Generate mock response time data in milliseconds.

    Args:
        time_range: Time range ('24h', '7d', '30d', '90d', '1y')

    Returns:
        List of data points with average response time, p50, p95, p99
    """
    data = generate_time_series_data(time_range, 250, 100, 'avg')

    for point in data:
        avg = point['avg']
        point['p50'] = max(50, avg - random.randint(50, 100))
        point['p95'] = avg + random.randint(100, 200)
        point['p99'] = avg + random.randint(200, 400)

    return data


def generate_error_rate_data(time_range: str) -> List[Dict[str, Any]]:
    """Generate mock error rate data as percentages.

    Args:
        time_range: Time range ('24h', '7d', '30d', '90d', '1y')

    Returns:
        List of data points with error rate percentage
    """
    # Error rate around 2-5%
    data = generate_time_series_data(time_range, 3, 2, 'error_rate')

    for point in data:
        # Ensure error rate is between 0 and 10%
        point['error_rate'] = max(0, min(10, point['error_rate']))

    return data


def generate_user_activity_data(time_range: str) -> List[Dict[str, Any]]:
    """Generate mock user activity data.

    Args:
        time_range: Time range ('24h', '7d', '30d', '90d', '1y')

    Returns:
        List of data points with active users count
    """
    return generate_time_series_data(time_range, 150, 50, 'active_users')


def generate_agent_statuses() -> List[Dict[str, Any]]:
    """Generate mock agent status data.

    Returns:
        List of agent objects with status, health, and metrics
    """
    agent_names = [
        ("Agent Analysis-1", "🔍"),
        ("Agent Report-1", "📊"),
        ("Agent Monitor-1", "👁️"),
        ("Agent Process-1", "⚙️"),
        ("Agent Gateway-1", "🌐"),
        ("Agent Search-1", "🔎"),
        ("Agent Transform-1", "🔄"),
        ("Agent Validate-1", "✓")
    ]

    statuses = ['active', 'idle', 'error', 'stopped']
    healths = ['healthy', 'warning', 'critical']

    agents = []
    for i, (name, icon) in enumerate(agent_names):
        # Most agents should be active or idle
        status = random.choices(
            statuses,
            weights=[50, 40, 5, 5],
            k=1
        )[0]

        # Health correlates with status
        if status == 'error':
            health = random.choice(['warning', 'critical'])
        elif status == 'stopped':
            health = 'critical'
        else:
            health = random.choices(
                healths,
                weights=[80, 15, 5],
                k=1
            )[0]

        agents.append({
            'id': f"agent-{i+1}",
            'name': name,
            'icon': icon,
            'status': status,
            'health': health,
            'cpu_usage': random.uniform(10, 80) if status == 'active' else random.uniform(0, 10),
            'memory_usage': random.randint(100_000_000, 500_000_000),
            'uptime': random.randint(3600, 86400) if status != 'stopped' else 0,
            'last_activity': int(datetime.now().timestamp()) - random.randint(0, 300),
            'tasks_completed': random.randint(10, 100),
            'tasks_in_progress': random.randint(0, 5) if status == 'active' else 0,
            'error_count': random.randint(0, 3) if health != 'healthy' else 0
        })

    return agents


def generate_mock_activity() -> Dict[str, Any]:
    """Generate a single mock activity event.

    Returns:
        Activity object with type, icon, message, and timestamp
    """
    activity_types = {
        'agent_started': ("🟢", "Agent {name} initialized successfully"),
        'agent_stopped': ("🔴", "Agent {name} stopped gracefully"),
        'analysis_complete': ("✅", "Analysis completed: {detail}"),
        'report_generated': ("📄", "Report generated: {detail}"),
        'task_started': ("▶️", "Task started: {detail}"),
        'task_completed': ("✓", "Task completed: {detail}"),
        'error': ("❌", "Error: {detail}"),
        'warning': ("⚠️", "Warning: {detail}"),
        'info': ("ℹ️", "Info: {detail}"),
        'debug': ("🐛", "Debug: {detail}")
    }

    activity_type = random.choice(list(activity_types.keys()))
    icon, template = activity_types[activity_type]

    agent_names = ["Analysis-1", "Report-1", "Monitor-1", "Process-1", "Gateway-1"]
    task_names = [
        "Data extraction",
        "Report compilation",
        "Metric aggregation",
        "Health check",
        "Cache refresh"
    ]

    details = {
        'name': random.choice(agent_names),
        'detail': random.choice(task_names)
    }

    return {
        'id': f"activity-{random.randint(10000, 99999)}",
        'type': activity_type,
        'icon': icon,
        'message': template.format(**details),
        'timestamp': int(datetime.now().timestamp()),
        'time_ago': 'Just now'
    }


def generate_multiple_activities(count: int = 20) -> List[Dict[str, Any]]:
    """Generate multiple mock activity events with realistic timestamps.

    Args:
        count: Number of activities to generate

    Returns:
        List of activity objects sorted by timestamp (newest first)
    """
    activities = []
    now = datetime.now()

    for i in range(count):
        activity = generate_mock_activity()
        # Spread activities over the last hour
        timestamp = now - timedelta(minutes=random.randint(0, 60))
        activity['timestamp'] = int(timestamp.timestamp())

        # Calculate time ago
        minutes_ago = (now - timestamp).total_seconds() / 60
        if minutes_ago < 1:
            activity['time_ago'] = 'Just now'
        elif minutes_ago < 60:
            activity['time_ago'] = f"{int(minutes_ago)}m ago"
        else:
            activity['time_ago'] = f"{int(minutes_ago / 60)}h ago"

        activities.append(activity)

    # Sort by timestamp, newest first
    activities.sort(key=lambda x: x['timestamp'], reverse=True)

    return activities


def generate_gateway_health() -> Dict[str, Any]:
    """Generate mock gateway health status.

    Returns:
        Gateway health object with status and metrics
    """
    is_healthy = random.random() > 0.1  # 90% chance of being healthy

    return {
        'status': 'healthy' if is_healthy else 'degraded',
        'uptime': random.randint(86400, 2592000),  # 1-30 days
        'version': '1.0.0',
        'timestamp': int(datetime.now().timestamp()),
        'checks': {
            'database': random.choice(['pass', 'pass', 'pass', 'fail']),
            'redis': random.choice(['pass', 'pass', 'pass', 'fail']),
            'external_api': random.choice(['pass', 'pass', 'pass', 'fail'])
        }
    }


def generate_gateway_stats() -> Dict[str, Any]:
    """Generate mock gateway statistics.

    Returns:
        Gateway stats object with various metrics
    """
    total_requests = random.randint(50000, 100000)
    failed_requests = random.randint(100, 1000)

    return {
        'cpu_usage': random.uniform(20, 75),
        'memory_usage': random.randint(500_000_000, 2_000_000_000),
        'active_agents': random.randint(5, 12),
        'requests_today': random.randint(1000, 5000),
        'reports_generated': random.randint(50, 200),
        'total_requests': total_requests,
        'successful_requests': total_requests - failed_requests,
        'failed_requests': failed_requests,
        'avg_response_time': random.uniform(150, 350),
        'uptime_percentage': random.uniform(99.5, 100.0)
    }


def generate_mock_reports(count: int = 10) -> List[Dict[str, Any]]:
    """Generate mock report metadata.

    Args:
        count: Number of reports to generate

    Returns:
        List of report objects with metadata
    """
    report_types = [
        'Performance Analysis',
        'Security Audit',
        'Usage Summary',
        'Error Analysis',
        'Agent Health Report',
        'Capacity Planning',
        'Cost Analysis'
    ]

    statuses = ['completed', 'in_progress', 'failed', 'scheduled']

    reports = []
    for i in range(count):
        created = datetime.now() - timedelta(days=random.randint(0, 30))
        status = random.choices(
            statuses,
            weights=[70, 15, 10, 5],
            k=1
        )[0]

        reports.append({
            'id': f"report-{i+1:04d}",
            'title': f"{random.choice(report_types)} - {created.strftime('%Y-%m-%d')}",
            'type': random.choice(report_types),
            'status': status,
            'created_at': int(created.timestamp()),
            'created_by': random.choice(['admin', 'system', 'agent-monitor']),
            'size': random.randint(10000, 500000),  # bytes
            'format': random.choice(['pdf', 'html', 'json']),
            'tags': random.sample(['monthly', 'quarterly', 'automated', 'manual', 'critical'], k=2)
        })

    # Sort by created date, newest first
    reports.sort(key=lambda x: x['created_at'], reverse=True)

    return reports


def generate_mock_report_content(report_id: str) -> Dict[str, Any]:
    """Generate mock report content for a specific report.

    Args:
        report_id: ID of the report

    Returns:
        Report content object with sections and data
    """
    return {
        'id': report_id,
        'title': 'Performance Analysis Report',
        'generated_at': int(datetime.now().timestamp()),
        'summary': 'System performance analysis covering the last 7 days.',
        'sections': [
            {
                'title': 'Executive Summary',
                'content': 'Overall system health is good with 99.8% uptime.',
                'type': 'text'
            },
            {
                'title': 'Key Metrics',
                'content': {
                    'total_requests': 125430,
                    'avg_response_time': 245,
                    'error_rate': 1.2,
                    'active_agents': 8
                },
                'type': 'metrics'
            },
            {
                'title': 'Recommendations',
                'content': [
                    'Consider scaling Agent Process-1 during peak hours',
                    'Investigate intermittent errors in Analysis pipeline',
                    'Update cache configuration for improved performance'
                ],
                'type': 'list'
            }
        ],
        'metadata': {
            'version': '1.0',
            'author': 'System',
            'pages': random.randint(5, 25)
        }
    }


def generate_request_distribution_data(time_range: str) -> List[Dict[str, Any]]:
    """Generate mock request distribution data by category/type.

    Args:
        time_range: Time range ('24h', '7d', '30d', '90d', '1y')

    Returns:
        List of category objects with name, count, and percentage
    """
    # Define request categories/types
    categories = [
        'API Requests',
        'Agent Tasks',
        'Report Generation',
        'Data Analysis',
        'Health Checks',
        'Cache Operations',
        'Database Queries',
        'External API Calls'
    ]

    # Generate realistic distribution with some categories more common than others
    weights = [25, 20, 15, 12, 10, 8, 6, 4]  # Percentage weights

    # Scale based on time range
    scale_factors = {
        '24h': 100,
        '7d': 700,
        '30d': 3000,
        '90d': 9000,
        '1y': 36500
    }
    scale = scale_factors.get(time_range, 700)

    # Generate counts with some randomness
    data = []
    total_count = 0

    for category, weight in zip(categories, weights):
        # Base count from weight, with some variance
        base_count = int((weight / 100) * scale)
        count = max(1, base_count + random.randint(-int(base_count * 0.2), int(base_count * 0.2)))
        total_count += count

        data.append({
            'category': category,
            'count': count
        })

    # Calculate actual percentages
    for item in data:
        item['percentage'] = round((item['count'] / total_count) * 100, 1)

    # Sort by count descending
    data.sort(key=lambda x: x['count'], reverse=True)

    return data


def generate_metrics_history(days: int = 7) -> Dict[str, List[Dict[str, Any]]]:
    """Generate historical metrics data for dashboard charts.

    Args:
        days: Number of days of history to generate

    Returns:
        Dictionary with different metric time series
    """
    return {
        'active_agents': generate_time_series_data(f'{days}d', 8, 2, 'count'),
        'requests_today': generate_time_series_data(f'{days}d', 3500, 500, 'count'),
        'reports_generated': generate_time_series_data(f'{days}d', 15, 5, 'count'),
        'cpu_usage': generate_time_series_data(f'{days}d', 45, 15, 'percentage')
    }


def generate_error_types_data(time_range: str) -> List[Dict[str, Any]]:
    """Generate mock error types data by HTTP status code and error category.

    Args:
        time_range: Time range ('24h', '7d', '30d', '90d', '1y')

    Returns:
        List of error type objects with name, count, status code, and percentage
    """
    # Define error types with HTTP status codes
    error_types = [
        ('404 Not Found', 404),
        ('500 Internal Server Error', 500),
        ('503 Service Unavailable', 503),
        ('401 Unauthorized', 401),
        ('400 Bad Request', 400),
        ('408 Request Timeout', 408),
        ('422 Validation Error', 422),
        ('429 Rate Limit Exceeded', 429)
    ]

    # Weight distribution (more common errors get higher weights)
    weights = [30, 25, 15, 10, 8, 5, 4, 3]

    # Scale based on time range
    scale_factors = {
        '24h': 50,
        '7d': 350,
        '30d': 1500,
        '90d': 4500,
        '1y': 18000
    }
    scale = scale_factors.get(time_range, 350)

    # Generate counts with some randomness
    data = []
    total_count = 0

    for (error_name, status_code), weight in zip(error_types, weights):
        # Base count from weight, with some variance
        base_count = int((weight / 100) * scale)
        count = max(1, base_count + random.randint(-int(base_count * 0.3), int(base_count * 0.3)))
        total_count += count

        data.append({
            'error_type': error_name,
            'status_code': status_code,
            'count': count
        })

    # Calculate actual percentages
    for item in data:
        item['percentage'] = round((item['count'] / total_count) * 100, 1)

    # Sort by count descending
    data.sort(key=lambda x: x['count'], reverse=True)

    return data


def generate_feature_usage_data(time_range: str) -> List[Dict[str, Any]]:
    """Generate mock feature usage data for horizontal bar chart.

    Args:
        time_range: Time range ('24h', '7d', '30d', '90d', '1y')

    Returns:
        List of feature objects with name, usage count, and percentage
    """
    # Define feature categories
    features = [
        'Agent Orchestration',
        'Report Generation',
        'Data Analysis',
        'API Requests',
        'Cache Management',
        'Task Scheduling',
        'Health Monitoring',
        'Error Tracking',
        'User Management',
        'System Configuration'
    ]

    # Weight distribution (more commonly used features get higher weights)
    weights = [28, 22, 18, 12, 8, 5, 3, 2, 1, 1]

    # Scale based on time range
    scale_factors = {
        '24h': 100,
        '7d': 700,
        '30d': 3000,
        '90d': 9000,
        '1y': 36500
    }
    scale = scale_factors.get(time_range, 700)

    # Generate counts with some randomness
    data = []
    total_usage = 0

    for feature, weight in zip(features, weights):
        # Base count from weight, with some variance
        base_count = int((weight / 100) * scale)
        count = max(1, base_count + random.randint(-int(base_count * 0.2), int(base_count * 0.2)))
        total_usage += count

        data.append({
            'feature': feature,
            'usage_count': count
        })

    # Calculate actual percentages
    for item in data:
        item['percentage'] = round((item['usage_count'] / total_usage) * 100, 1)

    # Sort by usage count descending
    data.sort(key=lambda x: x['usage_count'], reverse=True)

    return data


def generate_performance_metrics_data(time_range: str) -> List[Dict[str, Any]]:
    """Generate mock performance metrics data for grouped bar chart (latency percentiles).

    Args:
        time_range: Time range ('24h', '7d', '30d', '90d', '1y')

    Returns:
        List of metric groups with p50, p95, p99 latency percentiles
    """
    # Define metric categories (endpoints/services)
    categories = [
        'Agent API',
        'Report Service',
        'Analytics Engine',
        'Gateway Service',
        'Database Queries',
        'Cache Operations',
        'External API Calls',
        'Background Jobs'
    ]

    # Generate data for each category
    data = []

    for category in categories:
        # Base latency varies by service type
        if 'Cache' in category:
            base_p50 = random.randint(5, 15)
        elif 'Database' in category:
            base_p50 = random.randint(20, 50)
        elif 'External' in category:
            base_p50 = random.randint(100, 250)
        else:
            base_p50 = random.randint(30, 120)

        # Calculate percentiles with realistic distribution
        p50 = base_p50
        p95 = p50 + random.randint(int(p50 * 1.5), int(p50 * 3))
        p99 = p95 + random.randint(int(p95 * 0.5), int(p95 * 1.5))

        data.append({
            'category': category,
            'p50': p50,
            'p95': p95,
            'p99': p99
        })

    return data
