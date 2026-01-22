from datetime import datetime
import logging
from flask import Blueprint, request, jsonify, current_app
from uuid import uuid4

logger = logging.getLogger(__name__)


class CallService:
    def __init__(self, db):
        self.db = db
        self.call_collection = db.get_collection("calls")
        self._ensure_indexes()

    def _ensure_indexes(self):
        try:
            self.call_collection.create_index("row_number")
            self.call_collection.create_index("date")
            self.call_collection.create_index("phone_number")
            self.call_collection.create_index("email")
        except Exception as e:
            logger.warning(f"Index creation failed: {e}")

    def save_call(self, extracted_data: dict) -> None:
        self.call_collection.insert_one(extracted_data)

    def _parse_transcript(self, transcript_text: str):
        if not transcript_text or not isinstance(transcript_text, str):
            return []

        lines = [line.strip() for line in transcript_text.splitlines() if line.strip()]
        result = []
        current_speaker = None
        current_text = []

        def flush():
            if current_speaker and current_text:
                result.append({
                    "speaker": current_speaker,
                    "transcription": " ".join(current_text).strip()
                })

        for line in lines:
            if line.lower().startswith("ai:"):
                flush()
                current_speaker = "BOT"
                current_text = [line[3:].strip()]
            elif line.lower().startswith("user:"):
                flush()
                current_speaker = "USER"
                current_text = [line[5:].strip()]
            else:
                # continuation of previous line
                if current_speaker:
                    current_text.append(line)
                else:
                    # no speaker yet; treat as USER by default
                    current_speaker = "USER"
                    current_text = [line]

        flush()
        return result

    def build_call_document(self, extracted_data: dict) -> dict:
        call_at = (extracted_data or {}).get("call_at")
        started_at = None
        if isinstance(call_at, str):
            try:
                started_at = datetime.fromisoformat(call_at.replace("Z", "+00:00"))
            except Exception:
                started_at = None

        transcript_text = (extracted_data or {}).get("transcript_whole_conversation")
        transcription = self._parse_transcript(transcript_text)

        return {
            "call_id": str(uuid4()),
            "status": "ended",
            "started_at": started_at,
            "ended_at": None,
            "audio": (extracted_data or {}).get("audio"),
            "recording_url": (extracted_data or {}).get("recording_url"),
            "transcription": transcription,
            "userdata": {
                "From": (extracted_data or {}).get("from") or "sheet",
                "phone_number": (extracted_data or {}).get("phone_number"),
                "name": (extracted_data or {}).get("name"),
                "email": (extracted_data or {}).get("email"),
            },
        }

    def extract_sheet_data(self, data):
        # Example extraction logic
        row_number = data.get("rowNumber")
        row_data = data.get("data") or []
        # Unpack the row_data list into variables
        date_, time_, name, country, phone_number, email, product_discussed, success_evaluation_numeric, product_interest_level, success_evaluation_pass_fail, nps_score, customer_sentiment, descriptive_scale, call_summary, transcript_whole_conversation, recording_url = (row_data + [None] * 16)[:16]
        # Convert to dictionary
        extracted_data = {
            "row_number": row_number,
            "date": date_,
            "time": time_,
            "name": name,
            "country": country,
            "phone_number": phone_number,
            "email": email,
            "product_discussed": product_discussed,
            "success_evaluation_numeric": success_evaluation_numeric,
            "product_interest_level": product_interest_level,
            "success_evaluation_pass_fail": success_evaluation_pass_fail,
            "nps_score": nps_score,
            "customer_sentiment": customer_sentiment,
            "descriptive_scale": descriptive_scale,
            "call_summary": call_summary,
            "transcript_whole_conversation": transcript_whole_conversation,
            "recording_url": recording_url,
            "audio": None,
        }
        return extracted_data
    
    def get_calls_with_limited_data(self, admin_id=None, limit=20, skip=0, filter_type='all'):
        """
        Get calls with only the data needed for list display.
        Excludes heavy transcription field.
        """
        query = {}

        # Projection - only fetch required fields (exclude transcription content)
        projection = {
            'started_at': 1,
            'customer_sentiment': 1,
            'product_discussed': 1,
            'userdata': 1,
            'call_id': 1,
            'transcription': 1,
            '_id': 0  # Exclude MongoDB's _id field
        }

        calls = list(
            self.call_collection.find(query, projection)
            .sort("started_at", -1)
            .skip(skip)
            .limit(limit)
        )

        # Add transcription length (count) without sending full transcription
        for call in calls:
            if 'started_at' in call and isinstance(call['started_at'], str):
                call['started_at'] = datetime.fromisoformat(call['started_at'].replace('Z', '+00:00'))
            call['transcription_length'] = len(call.get('transcription', []))

        return calls
    
    def get_call_counts_by_filter(self, admin_id=None):
        """Get counts for all call filters."""
        base_query = {}
        
        return {
            'all': self.call_collection.count_documents(base_query)
        }
    
    def get_full_call(self, call_id):
        """Get complete call data including transcription for detail view."""
        call = self.call_collection.find_one({"call_id": call_id})
        
        # MongoDB returns datetime objects natively - no conversion needed
        # Verify they are datetime objects
        if call:
            if isinstance(call['started_at'], str):
                call['started_at'] = datetime.fromisoformat(call['started_at'].replace('Z', '+00:00'))
            
            # Convert ended_at to datetime if it exists and is a string
            if call.get('ended_at') and isinstance(call['ended_at'], str):
                call['ended_at'] = datetime.fromisoformat(call['ended_at'].replace('Z', '+00:00'))
        
        return call
    
    def delete_call(self, call_id):
        """Delete a call record."""
        result = self.call_collection.delete_one({"call_id": call_id})
        return result.deleted_count > 0