import uuid
import bcrypt
from models.admin import Admin
from datetime import datetime


class AdminService:
    def __init__(self, db):
        self.db = db
        self.admins_collection = db.admins

    def create_admin(self, username, password, role="admin", email=None, phone=None, created_by=None):
        """Create a new admin"""
        # Check if username already exists
        if self.get_admin_by_username(username):
            raise ValueError("Username already exists")

        admin_id = str(uuid.uuid4())
        password_hash = bcrypt.hashpw(password.encode(
            'utf-8'), bcrypt.gensalt()).decode('utf-8')

        admin = Admin(
            username=username,
            password_hash=password_hash,
            role=role,
            admin_id=admin_id,
            email=email,
            phone=phone,
            created_by=created_by
        )

        self.admins_collection.insert_one(admin.to_dict())
        return admin

    def get_admin_by_key(self, key):
        admin_data = self.admins_collection.find_one({"secret_key": key})
        if admin_data:
            return Admin.from_dict(admin_data)
        return None

    def get_admin_by_username(self, username):
        """Get admin by username"""
        admin_data = self.admins_collection.find_one({"username": username})
        if admin_data:
            return Admin.from_dict(admin_data)
        return None

    def get_admin_by_id(self, admin_id):
        """Get admin by ID"""
        admin_data = self.admins_collection.find_one({"admin_id": admin_id})
        if admin_data:
            return Admin.from_dict(admin_data)
        return None

    def authenticate_admin(self, username, password):
        """Authenticate admin credentials"""
        admin = self.get_admin_by_username(username)
        if admin and admin.status == "active":
            if bcrypt.checkpw(password.encode('utf-8'), admin.password_hash.encode('utf-8')):
                # Update last login
                self.update_last_login(admin.admin_id)
                return admin
        return None

    def get_admin_from_sec(self, secrect_key):
        return Admin.from_dict(self.admins_collection.find_one({'secret_key': secrect_key}))

    def get_all_admins(self):
        """Get all admins"""
        admins = self.admins_collection.find()
        return [Admin.from_dict(admin) for admin in admins]

    def get_admins_by_role(self, role):
        """Get admins by role"""
        admins = self.admins_collection.find({"role": role})
        return [Admin.from_dict(admin) for admin in admins]

    def update_admin_settings(self, admin_id, settings):
        """Update admin settings"""
        result = self.admins_collection.update_one(
            {"admin_id": admin_id},
            {"$set": {"settings": settings}}
        )
        return result.modified_count > 0

    def update_admin_password(self, admin_id, new_password):
        """Update admin password"""
        password_hash = bcrypt.hashpw(new_password.encode(
            'utf-8'), bcrypt.gensalt()).decode('utf-8')
        result = self.admins_collection.update_one(
            {"admin_id": admin_id},
            {"$set": {"password_hash": password_hash}}
        )
        return result.modified_count > 0

    def set_admin_onboarded(self, admin_id):
        result = self.admins_collection.update_one(
            {"admin_id": admin_id},
            {"$set": {"onboarding": False}}
        )
        return result.modified_count > 0

    def update_admin_login(self, admin_id, username, password, email, phone):
        self.update_admin_password(admin_id, password)
        result = self.admins_collection.update_one(
            {"admin_id": admin_id},
            {"$set": {"email": email, 'username': username,
                      'phone': phone, 'onboarding': False}}
        )
        return result.modified_count > 0

    def update_admin_status(self, admin_id, status):
        """Update admin status (active, inactive, suspended)"""
        result = self.admins_collection.update_one(
            {"admin_id": admin_id},
            {"$set": {"status": status}}
        )
        return result.modified_count > 0

    def update_admin_role(self, admin_id, role):
        """Update admin role"""
        result = self.admins_collection.update_one(
            {"admin_id": admin_id},
            {"$set": {"role": role}}
        )
        return result.modified_count > 0

    def update_last_login(self, admin_id):
        """Update last login timestamp"""
        self.admins_collection.update_one(
            {"admin_id": admin_id},
            {"$set": {"last_login": datetime.utcnow()}}
        )

    def delete_admin(self, admin_id):
        """Delete admin (only superadmin can do this)"""
        result = self.admins_collection.delete_one({"admin_id": admin_id})
        return result.deleted_count > 0

    def count_admins_by_role(self):
        """Count admins by role"""
        pipeline = [
            {"$group": {"_id": "$role", "count": {"$sum": 1}}}
        ]
        result = list(self.admins_collection.aggregate(pipeline))
        counts = {"admin": 0, "superadmin": 0}
        for item in result:
            counts[item["_id"]] = item["count"]
        return counts

    def get_admin_activity(self, days=30):
        """Get admin login activity for the last N days"""
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        pipeline = [
            {"$match": {"last_login": {"$gte": cutoff_date}}},
            {"$project": {
                "username": 1,
                "role": 1,
                "last_login": 1,
                "status": 1
            }},
            {"$sort": {"last_login": -1}}
        ]

        result = list(self.admins_collection.aggregate(pipeline))
        return result
