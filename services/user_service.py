import uuid
from models.user import User
import requests


class UserService:
    def __init__(self, db):
        self.db = db
        self.users_collection = db.users

    def create_user(self, name, ip=None, email=None, phone=None, role="user"):
        user_id = str(uuid.uuid4())

        geo = requests.get(f"https://ipapi.co/{ip}/json/")
        print(geo)
        geo = geo.json()
        country = geo.get("country_name", None)
        city = geo.get("city")
        if not country:

            geo = requests.get(f"https://ipwhois.app/json/{ip}")
            print(geo)
            geo = geo.json()
            country = geo.get("country", None)
            city = geo.get("city")
        user = User(name=name, email=email, phone=phone,
                    user_id=user_id, ip=ip, role=role, loc=f"{city},{country}")
        self.users_collection.insert_one(user.to_dict())
        return user

    def get_user(self, name, email, phone):
        user_data = self.users_collection.find_one(
            {"name": name, 'email': email, 'phone': phone})
        if user_data:
            return User.from_dict(user_data)
        return None

    def get_user_by_id(self, user_id):
        user_data = self.users_collection.find_one({"user_id": user_id})
        if user_data:
            return User.from_dict(user_data)
        return None

    def add_chat_to_user(self, user_id, chat_id):
        self.users_collection.update_one(
            {"user_id": user_id},
            {"$addToSet": {"chat_ids": chat_id}}
        )

    def update_last_active(self, user_id):
        from datetime import datetime
        self.users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"last_active": datetime.utcnow()}}
        )
