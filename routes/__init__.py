"""
Routes package for WONTECH
"""

from .admin_routes import admin_bp
from .employee_routes import employee_bp
from .pos_routes import pos_bp
from .auth_routes import auth_bp
from .portal_routes import portal_bp
from .attendance_routes import attendance_bp
from .employee_mgmt_routes import employee_mgmt_bp
from .inventory_app_routes import inventory_app_bp
from .analytics_app_routes import analytics_app_bp
from .storefront_routes import storefront_bp
from .menu_admin_routes import menu_admin_bp
from .voice_routes import voice_bp

__all__ = [
    'admin_bp', 'employee_bp', 'pos_bp',
    'auth_bp', 'portal_bp', 'attendance_bp',
    'employee_mgmt_bp', 'inventory_app_bp', 'analytics_app_bp',
    'storefront_bp', 'menu_admin_bp', 'voice_bp',
]
