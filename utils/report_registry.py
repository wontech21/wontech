"""Report Registry — central catalog of all available reports."""

_registry = {}


def register_report(key, name, category, description, data_fn, columns, chart_type=None):
    """Register a report in the central catalog."""
    _registry[key] = {
        'key': key,
        'name': name,
        'category': category,
        'description': description,
        'data_fn': data_fn,
        'columns': columns,
        'chart_type': chart_type,
    }


def get_report(key):
    """Retrieve a single report definition by key."""
    return _registry.get(key)


def list_reports(category=None):
    """List all reports, optionally filtered by category."""
    reports = list(_registry.values())
    if category:
        reports = [r for r in reports if r['category'] == category]
    return reports


def get_categories():
    """Return sorted list of all distinct report categories."""
    return sorted(set(r['category'] for r in _registry.values()))
