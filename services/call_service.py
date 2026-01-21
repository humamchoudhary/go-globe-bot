import logging
from flask import Blueprint, request, jsonify, current_app

logger = logging.getLogger(__name__)


class CallService:
    def __init__(self, db):
        self.db = db
        self.calls_collection = db.get_collection("calls")
        self._ensure_indexes()

    def _ensure_indexes(self):
        try:
            self.calls_collection.create_index("row_number")
            self.calls_collection.create_index("date")
            self.calls_collection.create_index("phone_number")
            self.calls_collection.create_index("email")
        except Exception as e:
            logger.warning(f"Index creation failed: {e}")

    def save_call(self, extracted_data: dict) -> None:
        self.calls_collection.insert_one(extracted_data)



    def extract_sheet_data(self, data):
        # Example extraction logic
        row_number = data.get("rowNumber")
        row_data = data.get("data") or []
        # Unpack the row_data list into variables
        date_, time_, name, country, phone_number, email, product_discussed, success_evaluation_numeric, product_interest_level, success_evaluation_pass_fail, nps_score, customer_sentiment, descriptive_scale, call_summary, transcript_whole_conversation = (row_data + [None] * 15)[:15]
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
        }
        return extracted_data

