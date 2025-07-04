import logging
import uuid
from models.chat import Chat, Message
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

logger = logging.getLogger(__name__)
# class ChatService:
#     def __init__(self, db):
#         self.db = db
#         self.chats_collection = db.chats
#
#     def create_chat(self, user_id, subject, admin_id):
#         chat_id = str(uuid.uuid4())
#         # if not room_id:
#         #     room_id = f"{user_id}-{chat_id[:8]}"
#
#         # Add default bot message
#         initial_messages = [Message("bot", "How may I help you")]
#
#         chat = Chat(
#             chat_id=chat_id,
#             # room_id=room_id,
#             user_id=user_id,
#             admin_id=admin_id,
#             messages=initial_messages,
#             subject=subject,
#         )
#
#         self.chats_collection.insert_one(chat.to_dict())
#         return chat
#
#     def count_chats(self,room_id=None):
#         if room_id:
#             return self.chats_collection.count_documents({"room_id":room_id})
#         return self.chats_collection.count_documents({})
#
#
#     def get_chat_by_id(self, chat_id):
#         chat_data = self.chats_collection.find_one({"chat_id": chat_id})
#         if chat_data:
#             return Chat.from_dict(chat_data)
#         return None
#
#     def delete(self, room_ids):
#         self.chats_collection.delete_many({"room_id": {"$in": room_ids}})
#         for id in room_ids:
#             # print(id)
#             os.remove(f"./bin/chat/{id}.chatpl")
#
#     def get_chat_by_room_id(self, room_id):
#         chat_data = self.chats_collection.find_one({"room_id": room_id})
#         if chat_data:
#             return Chat.from_dict(chat_data)
#         return None
#
#     def export_chat(self, room_id, lead_id):
#         chat = self.get_chat_by_room_id(room_id)
#         if not chat:
#             return False
#         self.chats_collection.update_one(
#             {"room_id": room_id}, {"$set": {"exported": True, "lead_id": lead_id}}
#         )
#         return True
#
#     def add_message(self, room_id, sender, content):
#         chat = self.get_chat_by_room_id(room_id)
#         if not chat:
#             return None
#
#         message = Message(sender, content)
#
#         self.chats_collection.update_one(
#             {"room_id": room_id},
#             {
#                 "$push": {"messages": message.to_dict()},
#                 "$set": {"updated_at": message.timestamp, 'viewed': False},
#             },
#         )
#
#         return message
#
#     def set_admin_required(self, room_id, required=True):
#         self.chats_collection.update_one(
#             {"room_id": room_id}, {
#                 "$set": {"admin_required": required, "viewed": False}}
#         )
#
#     def set_chat_viewed(self, room_id):
#         self.chats_collection.update_one(
#             {"room_id": room_id}, {
#                 "$set": {"viewed": True}}
#         )
#
#     def set_admin_present(self, room_id, present=True):
#         self.chats_collection.update_one(
#             {"room_id": room_id}, {"$set": {"admin_present": present}}
#         )
#
#     def close_chat(self, room_id):
#         self.chats_collection.update_one(
#             {"room_id": room_id}, {"$set": {"open": False}}
#         )
#
#     def get_all_chats(self, admin_id=None, limit=100, skip=0):
#         chats_data = list(
#             self.chats_collection.find({"admin_id": admin_id})
#             .sort("updated_at", -1)
#             .skip(skip)
#             .limit(limit)
#         )
#         return [Chat.from_dict(chat_data) for chat_data in chats_data]


class ChatService:
    def __init__(self, db):
        self.db = db
        self.chats_collection = db.chats
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Ensure proper database indexes for performance."""
        try:
            # Create compound indexes for common queries
            self.chats_collection.create_index([
                ("admin_id", 1),
                ("updated_at", -1)
            ])

            # Index for filtering
            self.chats_collection.create_index([
                ("admin_id", 1),
                ("admin_required", 1),
                ("updated_at", -1)
            ])

            self.chats_collection.create_index([
                ("admin_id", 1),
                ("exported", 1),
                ("updated_at", -1)
            ])

            # Index for message existence check
            self.chats_collection.create_index([
                ("admin_id", 1),
                ("subject", 1),
                ("messages.1", 1),
                ("updated_at", -1)
            ])

            # Basic indexes
            self.chats_collection.create_index("chat_id")
            self.chats_collection.create_index("room_id")
            self.chats_collection.create_index("user_id")

        except Exception as e:
            logger.warning(f"Index creation failed: {e}")

    def create_chat(self, user_id: str, subject: str, admin_id: str) -> Chat:
        """Create a new chat with optimized initial message."""
        chat_id = str(uuid.uuid4())

        # Create initial messages using the Message model
        initial_messages = [Message("bot", "How may I help you")]

        # Create the chat object using the Chat model
        chat = Chat(
            chat_id=chat_id,
            user_id=user_id,
            admin_id=admin_id,
            messages=initial_messages,
            subject=subject,
        )

        # Insert the chat document
        self.chats_collection.insert_one(chat.to_dict())
        return chat

    def count_chats(self, room_id: Optional[str] = None) -> int:
        """Count chats with optional room_id filter."""
        filter_query = {"room_id": room_id} if room_id else {}
        return self.chats_collection.count_documents(filter_query)

    @lru_cache(maxsize=128)
    def get_chat_by_id(self, chat_id: str) -> Optional[Chat]:
        """Get chat by ID with caching."""
        chat_data = self.chats_collection.find_one(
            {"chat_id": chat_id},
            {"_id": 0}  # Exclude MongoDB's _id field
        )
        return Chat.from_dict(chat_data) if chat_data else None

    def delete_chats_batch(self, room_ids: List[str]) -> int:
        """Optimized batch deletion with parallel file removal."""
        if not room_ids:
            return 0

        # Delete from database first
        result = self.chats_collection.delete_many(
            {"room_id": {"$in": room_ids}})
        deleted_count = result.deleted_count

        # Remove files in parallel
        self._remove_chat_files_parallel(room_ids)

        return deleted_count

    def _remove_chat_files_parallel(self, room_ids: List[str]):
        """Remove chat files in parallel for better performance."""
        def remove_file(room_id: str):
            try:
                file_path = f"./bin/chat/{room_id}.chatpl"
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(
                    f"Failed to remove file for room {room_id}: {e}")

        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(remove_file, room_ids)

    # Keep the old method for backward compatibility
    def delete(self, room_ids: List[str]):
        """Legacy method - use delete_chats_batch instead."""
        return self.delete_chats_batch(room_ids)

    @lru_cache(maxsize=128)
    def get_chat_by_room_id(self, room_id: str) -> Optional[Chat]:
        """Get chat by room ID with caching."""
        chat_data = self.chats_collection.find_one(
            {"room_id": room_id},
            {"_id": 0}
        )
        return Chat.from_dict(chat_data) if chat_data else None

    def export_chat(self, room_id: str, lead_id: str) -> bool:
        """Export chat with optimized existence check."""
        result = self.chats_collection.update_one(
            {"room_id": room_id},
            {"$set": {"exported": True, "lead_id": lead_id}}
        )
        return result.modified_count > 0

    def get_chats_with_full_messages(self, admin_id: Optional[str] = None, limit: int = 100, skip: int = 0) -> List[Chat]:
        """Get chats with all messages - use only when needed."""
        filter_query = {"admin_id": admin_id} if admin_id else {}

        cursor = self.chats_collection.find(
            filter_query,
            {"_id": 0}
        ).sort("updated_at", -1).skip(skip).limit(limit)

        return [Chat.from_dict(chat_data) for chat_data in cursor]

    def add_message(self, room_id: str, sender: str, content: str) -> Optional[Message]:
        """Add message with optimized update operation."""
        chat = self.get_chat_by_room_id(room_id)
        if not chat:
            return None

        message = Message(sender, content)

        result = self.chats_collection.update_one(
            {"room_id": room_id},
            {
                "$push": {"messages": message.to_dict()},
                "$set": {"updated_at": message.timestamp, "viewed": False}
            }
        )

        if result.modified_count > 0:
            return message
        return None

    def bulk_update_chats(self, updates: List[Dict[str, Any]]) -> int:
        """Perform bulk updates for better performance."""
        if not updates:
            return 0

        operations = []
        for update in updates:
            filter_query = update.get("filter", {})
            update_doc = update.get("update", {})
            operations.append({
                "updateOne": {
                    "filter": filter_query,
                    "update": update_doc
                }
            })

        if operations:
            result = self.chats_collection.bulk_write(operations)
            return result.modified_count
        return 0

    def set_admin_required(self, room_id: str, required: bool = True):
        """Set admin required status."""
        self.chats_collection.update_one(
            {"room_id": room_id},
            {"$set": {"admin_required": required, "viewed": False}}
        )

    def set_chat_viewed(self, room_id: str):
        """Set chat as viewed."""
        self.chats_collection.update_one(
            {"room_id": room_id},
            {"$set": {"viewed": True}}
        )

    def set_admin_present(self, room_id: str, present: bool = True):
        """Set admin presence status."""
        self.chats_collection.update_one(
            {"room_id": room_id},
            {"$set": {"admin_present": present}}
        )

    def close_chat(self, room_id: str):
        """Close chat."""
        self.chats_collection.update_one(
            {"room_id": room_id},
            {"$set": {"open": False}}
        )

    def get_all_chats(self, admin_id: Optional[str] = None, limit: int = 100, skip: int = 0) -> List[Chat]:
        """Get all chats with optimized query and projection."""
        filter_query = {"admin_id": admin_id, "subject": {
            "$nin": ["Job"]}, "messages.1": {'$exists': True}} if admin_id else {}

        # For better performance, you can optionally limit messages
        # But let's keep it simple and load all for now
        cursor = self.chats_collection.find(
            filter_query,
            {"_id": 0}  # Exclude MongoDB's _id field
        ).sort("updated_at", -1).skip(skip).limit(limit)

        return [Chat.from_dict(chat_data) for chat_data in cursor]

    def get_chats_with_limited_messages(self, admin_id: Optional[str] = None, limit: int = 100, skip: int = 0, message_limit: int = 1) -> List[Chat]:
        """Get chats with limited number of messages per chat for list views."""
        filter_query = {"admin_id": admin_id, "subject": {
            "$nin": ["Job"]}, "messages.1": {'$exists': True}} if admin_id else {}

        # Use projection to limit messages (e.g., only last message for list view)
        projection = {
            "_id": 0,
            "messages": {"$slice": -message_limit}  # Get last N messages
        }

        cursor = self.chats_collection.find(
            filter_query,
            projection
        ).sort("updated_at", -1).skip(skip).limit(limit)

        return [Chat.from_dict(chat_data) for chat_data in cursor]

    def get_chat_stats(self, admin_id: Optional[str] = None) -> Dict[str, Any]:
        """Get chat statistics using aggregation pipeline."""
        match_stage = {"$match": {"admin_id": admin_id}
                       } if admin_id else {"$match": {}}

        pipeline = [
            match_stage,
            {
                "$group": {
                    "_id": None,
                    "total_chats": {"$sum": 1},
                    "admin_required_chats": {
                        "$sum": {"$cond": [{"$eq": ["$admin_required", True]}, 1, 0]}
                    },
                    "open_chats": {
                        "$sum": {"$cond": [{"$eq": ["$open", True]}, 1, 0]}
                    },
                    "unviewed_chats": {
                        "$sum": {"$cond": [{"$eq": ["$viewed", False]}, 1, 0]}
                    }
                }
            }
        ]

        result = list(self.chats_collection.aggregate(pipeline))
        return result[0] if result else {
            "total_chats": 0,
            "admin_required_chats": 0,
            "open_chats": 0,
            "unviewed_chats": 0
        }

    def clear_cache(self):
        """Clear LRU caches."""
        self.get_chat_by_id.cache_clear()
        self.get_chat_by_room_id.cache_clear()

    def get_filtered_chats_paginated(
        self,
        admin_id: Optional[str] = None,
        filter_type: str = 'all',
        limit: int = 20,
        skip: int = 0
    ) -> List[Chat]:
        """Get filtered chats with pagination support."""

        # Base filter query
        base_filter = {
            "admin_id": admin_id,
            "subject": {"$nin": ["Job"]},
            "messages.1": {"$exists": True}
        } if admin_id else {}

        # Apply specific filters
        if filter_type == "active":
            base_filter["admin_required"] = True
        elif filter_type == "exported":
            base_filter["exported"] = True

        # Optimized projection - only get necessary fields for list view
        # projection = {
        #     "_id": 0,
        #     "room_id": 1,
        #     "user_id": 1,
        #     "subject": 1,
        #     "updated_at": 1,
        #     "viewed": 1,
        #     "admin_required": 1,
        #     "exported": 1,
        #     "messages": {"$slice": -1}  # Only get the last message
        # }

        # try:
        cursor = self.chats_collection.find(
            base_filter,
            {"messages": {"$slice": -1}, '_id': 0}  # Only get the last message
        ).sort("updated_at", -1).skip(skip).limit(limit)
        return [Chat.from_dict(chat_data) for chat_data in cursor]
        # except Exception as e:
        #     logger.error(f"Error getting filtered chats: {e}")
        #     return []

    def get_chat_counts_by_filter(self, admin_id: Optional[str] = None) -> Dict[str, int]:
        """Get chat counts for all filter types using aggregation."""

        base_match = {
            "admin_id": admin_id,
            "subject": {"$nin": ["Job"]},
            "messages.1": {"$exists": True}
        } if admin_id else {}

        pipeline = [
            {"$match": base_match},
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "active": {
                        "$sum": {"$cond": [{"$eq": ["$admin_required", True]}, 1, 0]}
                    },
                    "exported": {
                        "$sum": {"$cond": [{"$eq": ["$exported", True]}, 1, 0]}
                    }
                }
            }
        ]

        try:
            result = list(self.chats_collection.aggregate(pipeline))
            if result:
                return {
                    "all": result[0]["total"],
                    "active": result[0]["active"],
                    "exported": result[0]["exported"]
                }
            return {"all": 0, "active": 0, "exported": 0}
        except Exception as e:
            logger.error(f"Error getting chat counts: {e}")
            return {"all": 0, "active": 0, "exported": 0}

    def get_chat_counts_for_header(self, admin_id: Optional[str] = None) -> Dict[str, int]:
        """Get chat counts for header display with caching."""

        # Use a simple cache key based on admin_id
        cache_key = f"chat_counts_{admin_id}"

        # You can implement simple in-memory caching here if needed
        # For now, we'll call the database each time but it's optimized
        return self.get_chat_counts_by_filter(admin_id)
