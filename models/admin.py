from datetime import datetime
import os
import secrets


class Admin:
    def __init__(self, username, password_hash, role="admin", admin_id=None, email=None, secret_key=None,
                 phone=None, created_by=None, settings=None, last_login=None, status="active", onboarding=False):
        self.admin_id = admin_id
        self.username = username
        self.password_hash = password_hash
        self.role = role  # 'admin' or 'superadmin'
        self.email = email
        self.phone = phone
        self.created_by = created_by  # admin_id of who created this admin
        self.created_at = datetime.utcnow()
        self.last_login = last_login
        self.status = status  # 'active', 'inactive', 'suspended'
        self.secret_key = secret_key or secrets.token_hex(32)
        self.onboarding = onboarding

        # Default settings for each admin
        default_admin_settings = {
            'languages': ['English'],
            'subjects': [],
            'model': 'gm_2_0_f',
            'prompt': """you are a customer service assistant...""",
            'domains': [],
            'google_token': None,  # Store serialized Google credentials
            'selected_folders': []  # Store folder IDs selected by this admin
        }

        default_superadmin_settings = {
            'logo': {
                'large': '/static/img/logo.svg',
                'small': '/static/img/logo-desktop-mini.svg',
            },
            'apiKeys': {
                'claude': None,
                'openAi': None,
                'deepseek': None,
                'gemini': None
            },
            'theme': 'system',
            'sound': '/static/sounds/notification.wav',
            'backend_url': '',
            'prompt': """you are a customer service assistant..."""
        }

        if self.role == 'superadmin':
            self.settings = settings or default_superadmin_settings
        else:
            self.settings = settings or default_admin_settings

    def to_dict(self):
        return {
            "admin_id": self.admin_id,
            "username": self.username,
            "password_hash": self.password_hash,
            "role": self.role,
            "email": self.email,
            "phone": self.phone,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "status": self.status,
            "settings": self.settings,
            "secret_key": self.secret_key,
            "onboarding": self.onboarding
        }

    @classmethod
    def from_dict(cls, data):
        admin = cls(
            username=data.get("username"),
            password_hash=data.get("password_hash"),
            role=data.get("role", "admin"),
            admin_id=data.get("admin_id"),
            email=data.get("email"),
            phone=data.get("phone"),
            created_by=data.get("created_by"),
            settings=data.get("settings"),
            last_login=data.get("last_login"),
            status=data.get("status", "active"),
            secret_key=data.get('secret_key'),
            onboarding=data.get('onboarding', False)
        )
        admin.created_at = data.get("created_at", datetime.utcnow())
        return admin

    def has_permission(self, required_roles):
        """Check if admin has required permission"""
        if isinstance(required_roles, str):
            required_roles = [required_roles]
        return self.role in required_roles and self.status == "active"

    def can_manage_admins(self):
        """Only superadmins can manage other admins"""
        return self.role == "superadmin" or self.status == "active"

    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
