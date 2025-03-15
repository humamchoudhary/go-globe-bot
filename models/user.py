from datetime import datetime


class User:
    def __init__(self, name, ip=None, phone=None, email=None, user_id=None, role="user", chat_ids=None):
        self.user_id = user_id
        self.name = name
        self.role = role
        self.chat_ids = chat_ids or []
        self.created_at = datetime.utcnow()
        self.last_active = datetime.utcnow()
        self.email = email
        self.phone = phone
        self.ip = ip

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "name": self.name,
            "role": self.role,
            "chat_ids": self.chat_ids,
            "created_at": self.created_at,
            "last_active": self.last_active,
            'email': self.email,
            'phone': self.phone, 'ip': self.ip

        }

    @classmethod
    def from_dict(cls, data):
        user = cls(
            name=data.get("name"),
            user_id=data.get("user_id"),
            role=data.get("role", "user"),
            chat_ids=data.get("chat_ids", []),
            ip=data.get('ip'),
            email=data.get('email'), phone=data.get('phone')
        )
        user.created_at = data.get("created_at", datetime.utcnow())
        user.last_active = data.get("last_active", datetime.utcnow())
        return user
