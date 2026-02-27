"""
Feature Gating Middleware

Provides decorator and helper to gate routes/templates by org-level feature flags.
Features are stored as a JSON array in organizations.features (master.db).
"""

from functools import wraps
from flask import g, jsonify
import json


def _get_org_features():
    """Parse the features JSON array from g.organization."""
    if not hasattr(g, 'organization') or not g.organization:
        return []
    raw = g.organization.get('features') or '[]'
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def has_feature(feature_key):
    """Check if the current org has a feature enabled.

    Usable in templates:  {% if has_feature('reports') %}
    Usable in Python:     if has_feature('reports'): ...
    """
    # Super admin bypasses feature gates
    if hasattr(g, 'is_super_admin') and g.is_super_admin:
        return True
    return feature_key in _get_org_features()


def feature_required(feature_key):
    """Decorator that returns 403 if the org doesn't have the feature enabled."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not has_feature(feature_key):
                return jsonify({
                    'error': f'Feature not enabled: {feature_key}',
                    'feature': feature_key
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
