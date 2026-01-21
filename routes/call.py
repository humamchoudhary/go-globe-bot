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

@call_bp.route("/sheet-hook", methods=["POST", "GET"])
def sheet_hook():
    data = request.json or {}
    logs_service = LogsService(current_app.db)

    row = data.get("rowNumber")
    values = data.get("data")
    call_service = CallService(current_app.db)
    extracted_data = call_service.extract_sheet_data(data)

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

    calls_collection = current_app.db.get_collection("calls")
    calls_collection.insert_one(extracted_data)
    logs_service.create_log(
        level=LogLevel.INFO,
        tag=LogTag.ACCESS,
        message="Sheet hook data saved",
        data={"row": row}
    )

    return jsonify({"status": "Call Data received and processed"}), 200

