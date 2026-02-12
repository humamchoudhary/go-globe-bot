from dotenv import load_dotenv
from flask import (
    session,
    redirect,
    url_for,
)
from functools import wraps

from flask_mail import Mail

from routes.admin import chat
from services.admin_service import AdminService
from services.notification_service import NotificationService
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
from services.email_service import send_email
from models.log import LogLevel, LogTag
from services.call_service import CallService
from services.logs_service import LogsService
from models.log import LogLevel, LogTag
from datetime import datetime
import pytz
import os
import requests
import time

load_dotenv()

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
    # Check for password in payload
    expected_password = os.environ.get("SHEET_HOOK_PASSWORD")
    req_password = (request.json or {}).get("password") if request.is_json else None

    if not expected_password or req_password != expected_password:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json or []
    if isinstance(data, dict):
        data = [data]

    logs_service = LogsService(current_app.db)
    call_service = CallService(current_app.db)
    call_collection = current_app.db.get_collection("calls")
    admin_service = AdminService(current_app.db)
    current_admin = admin_service.get_admin_by_id(session.get('admin_id'))
    mail = Mail(current_app)

    for item in data:
        row = (item or {}).get("rowNumber")
        extracted_data = call_service.extract_sheet_data(item)

        # Parse and convert date/time to ISO 8601 with timezone
        date_str = (extracted_data or {}).get("date")
        time_str = (extracted_data or {}).get("time")
        call_at = None
        if date_str and time_str:
            try:
                dt_str = f"{date_str} {time_str}"
                dt_str = dt_str.replace(" UTC", "")
                dt = datetime.strptime(dt_str, "%b %d, %Y %I:%M %p")
                dt = pytz.utc.localize(dt)
                call_at = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+00:00"
                extracted_data["call_at"] = call_at
            except Exception as e:
                logs_service.create_log(
                    level=LogLevel.DEBUG,
                    tag=LogTag.ACCESS,
                    message="Failed to parse date/time",
                    data={"row": row, "date": date_str, "time": time_str, "error": str(e)}
                )

        formatted_call = call_service.build_call_document(extracted_data)
        saved_path = _save_recording(extracted_data.get("recording_url"), formatted_call.get("call_id"))
        if saved_path:
            formatted_call["audio"] = saved_path
        call_collection.insert_one(formatted_call)
        
        # email notification
        SEND_USER = os.environ.get("SMTP_TO")
        admin_email = current_admin.email if current_admin else None

        recipient = admin_email or SEND_USER
        if recipient:
            send_email(
                recipient,
                "New Call Received by Ana",
                "A new call record has been added",
                mail=mail,
                html_message=render_template(
                    "email/new_call.html",
                    call=formatted_call
                )
            )
        # push notification
        current_app.socketio.emit('new_call', {
            'username': extracted_data.get("name", "Unknown"),
        })
        admin_id = session.get('admin_id') or os.environ.get("DEFAULT_ADMIN_ID")
        # UI dropdown notification
        # send mongodb notification
        noti_service = NotificationService(current_app.db)
        noti_service.create_notification(admin_id, "New call Received", f'{extracted_data.get("name", "Unknown")} Made a new call to Ana', "new_call", "call_" + formatted_call.get("call_id"))
        # create log
        logs_service.create_log(
            level=LogLevel.INFO,
            tag=LogTag.ACCESS,
            message="Sheet hook data saved",
            data={"row": row}
        )
    return jsonify({"status": "Call Data received and processed"}), 200

