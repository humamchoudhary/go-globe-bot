import uuid
from models.chat import Chat, Message
import os


class ChatService:
    def __init__(self, db):
        self.db = db
        self.chats_collection = db.chats

    def create_chat(self, user_id, subject):
        chat_id = str(uuid.uuid4())
        # if not room_id:
        #     room_id = f"{user_id}-{chat_id[:8]}"

        # Add default bot message
        initial_messages = [
            Message("bot", "How may I help you")
        ]

        chat = Chat(
            chat_id=chat_id,
            # room_id=room_id,
            user_id=user_id,
            messages=initial_messages, subject=subject
        )

        self.chats_collection.insert_one(chat.to_dict())
        return chat

    def get_chat_by_id(self, chat_id):
        chat_data = self.chats_collection.find_one({"chat_id": chat_id})
        if chat_data:
            return Chat.from_dict(chat_data)
        return None

    def delete(self, room_ids):
        self.chats_collection.delete_many({"room_id": {'$in': room_ids}})
        for id in room_ids:
            print(id)
            os.remove(f"./bin/chat/{id}.chatpl")

    def get_chat_by_room_id(self, room_id):
        chat_data = self.chats_collection.find_one({"room_id": room_id})
        if chat_data:
            return Chat.from_dict(chat_data)
        return None

    def export_chat(self, room_id):
        chat = self.get_chat_by_room_id(room_id)
        if not chat:
            return False
        self.chats_collection.update_one(
            {'room_id': room_id}, {"$set": {"exported": True}})
        return True

    def add_message(self, room_id, sender, content):
        chat = self.get_chat_by_room_id(room_id)
        if not chat:
            return None

        message = Message(sender, content)

        self.chats_collection.update_one(
            {"room_id": room_id},
            {
                "$push": {"messages": message.to_dict()},
                "$set": {"updated_at": message.timestamp}
            }
        )

        return message

    def set_admin_required(self, room_id, required=True):
        self.chats_collection.update_one(
            {"room_id": room_id},
            {"$set": {"admin_required": required}}
        )

    def set_admin_present(self, room_id, present=True):
        self.chats_collection.update_one(
            {"room_id": room_id},
            {"$set": {"admin_present": present}}
        )

    def close_chat(self, room_id):
        self.chats_collection.update_one(
            {'room_id': room_id}, {"$set": {'open': False}})

    def get_all_chats(self, limit=100, skip=0):
        chats_data = list(self.chats_collection.find().sort(
            "updated_at", -1).skip(skip).limit(limit))
        return [Chat.from_dict(chat_data) for chat_data in chats_data]
