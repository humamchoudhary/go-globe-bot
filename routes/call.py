from flask import (
    session,
    redirect,
    url_for,
)
from functools import wraps
from . import call_bp
from flask import (
    render_template,
    session,
    request,
    jsonify,
    redirect,
    url_for,
    current_app,
    flash,
)
from . import call_bp
from services.call_service import CallService
from services.logs_service import LogsService
from models.log import LogLevel, LogTag
from services.call_service import CallService
from services.logs_service import LogsService
from models.log import LogLevel, LogTag
from datetime import datetime
import pytz
import os
import requests
import time

def _save_recording(recording_url: str, call_id: str) -> str:
    if not recording_url or not call_id:
        return None
    base_dir = "recordings"  # Now relative to the project root
    os.makedirs(base_dir, exist_ok=True)
    rel_path = f"/recordings/call_{call_id}.wav"
    abs_path = os.path.join(base_dir, f"call_{call_id}.wav")
    tmp_path = f"{abs_path}.tmp"

    for attempt in range(3):
        try:
            with requests.get(recording_url, stream=True, timeout=20) as resp:
                resp.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            f.write(chunk)
            if os.path.getsize(tmp_path) > 0:
                os.replace(tmp_path, abs_path)
                return rel_path
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if attempt < 2:
                time.sleep(2)
            continue
    return None

@call_bp.route("/sheet-hook", methods=["POST", "GET"])
def sheet_hook():

    data = request.json or {}
    logs_service = LogsService(current_app.db)

    row = data.get("rowNumber")
    call_service = CallService(current_app.db)
    extracted_data = call_service.extract_sheet_data(data)

    # Parse and convert date/time to ISO 8601 with timezone
    date_str = (extracted_data or {}).get("date")
    time_str = (extracted_data or {}).get("time")
    call_at = None
    if date_str and time_str:
        try:
            # Example: "Jan 6, 2026 UTC", "3:28 PM UTC"
            dt_str = f"{date_str} {time_str}"
            # Remove redundant 'UTC' from time if present
            dt_str = dt_str.replace(" UTC", "")
            dt = datetime.strptime(dt_str, "%b %d, %Y %I:%M %p")
            # Set timezone to UTC
            dt = pytz.utc.localize(dt)
            # Format as ISO 8601 with milliseconds and timezone
            call_at = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+00:00"
            extracted_data["call_at"] = call_at
        except Exception as e:
            logs_service.create_log(
                level=LogLevel.DEBUG,
                tag=LogTag.ACCESS,
                message="Failed to parse date/time",
                data={"row": row, "date": date_str, "time": time_str, "error": str(e)}
            )

    name = (extracted_data or {}).get("name")
    email = (extracted_data or {}).get("email")
    if not name or not email:
        logs_service.create_log(
            level=LogLevel.DEBUG,
            tag=LogTag.ACCESS,
            message="Sheet hook missing required fields",
            data={"row": row, "missing_name": not bool(name), "missing_email": not bool(email)}
        )
        # Still return processed 200 even if fields are missing
        return jsonify({"status": "Call Data received and processed"}), 200

    call_collection = current_app.db.get_collection("calls")
    formatted_call = call_service.build_call_document(extracted_data)
    saved_path = _save_recording(extracted_data.get("recording_url"), formatted_call.get("call_id"))
    if saved_path:
        formatted_call["audio"] = saved_path
    call_collection.insert_one(formatted_call)
    logs_service.create_log(
        level=LogLevel.INFO,
        tag=LogTag.ACCESS,
        message="Sheet hook data saved",
        data={"row": row}
    )

    return jsonify({"status": "Call Data received and processed"}), 200

