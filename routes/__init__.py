"""
Routes package for FIRINGup
"""

from .admin_routes import admin_bp
from .employee_routes import employee_bp

__all__ = ['admin_bp', 'employee_bp']
