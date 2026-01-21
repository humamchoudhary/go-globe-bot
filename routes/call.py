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
from services.call_service import CallService

@call_bp.route("/sheet-hook", methods=["POST", "GET"])
def sheet_hook():
    data = request.json
    print(data)
    row = data["rowNumber"]
    values = data["data"]
    call_service = CallService(current_app.db)
    extracted_data = call_service.extract_sheet_data(data)
    print("New row:", row, values)
    print(extracted_data)
    # Save to DB / file / process logic here

    # Save extracted_data to MongoDB 'calls' collection
    calls_collection = current_app.db.get_collection("calls")
    calls_collection.insert_one(extracted_data)

    return jsonify({"status": "Call Data received and processed"}), 200
