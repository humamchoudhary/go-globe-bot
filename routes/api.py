import requests
import os
import json
from config import Config
from flask import request, make_response, session, jsonify, url_for, current_app, abort, redirect
from functools import wraps
from . import api_bp
from services.admin_service import AdminService
from services.chat_service import ChatService
from services.user_service import UserService
from services.usage_service import UsageService
from datetime import datetime
from services.timezone import UTCZoneManager
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from werkzeug.utils import secure_filename

CREDENTIALS_FILE = "credentials.json"

UPLOAD_FOLDER = os.path.join(os.getcwd(), "user_data")
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]


def success_json_response(data=None, code=200):
    return jsonify({"success": True, "status": "success", **({"data": data} if data else {})}), code


def error_json_response(message="Error! Couldnot process this request", code=500):
    return jsonify({"success": False, "status": "error", "message": message}), code


def admin_required(_func=None, *, roles=None):
    if roles is None:
        roles = ["admin", "superadmin"]
    elif isinstance(roles, str):
        roles = [roles]

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):

            if session.get("role") not in roles:
                return error_json_response("Not Authorized", 401)
            if not session.get("admin_id"):
                session["next"] = request.path
                return error_json_response("Not Authorized", 401)

            admin_service = AdminService(current_app.db)
            current_admin = admin_service.get_admin_by_id(session["admin_id"])

            if not current_admin or not current_admin.has_permission(roles):
                return error_json_response("UAuthorized", 401)

            from flask import g

            g.current_admin = current_admin

            return f(*args, **kwargs)

        return decorated_function

    if _func:
        return decorator(_func)

    return decorator


API_KEY = Config.SECRET_KEY


@api_bp.errorhandler(400)
def bad_request(error):
    return error_json_response(
        message="Bad Request: " + str(error.description),
        code=400
    )


@api_bp.errorhandler(401)
def unauthorized(error):
    return error_json_response(
        message="Unauthorized",
        code=401
    )


@api_bp.errorhandler(403)
def forbidden(error):
    return error_json_response(
        message="Forbidden ",
        code=403
    )


@api_bp.errorhandler(404)
def not_found(error):
    return error_json_response(
        message="Resource not found",
        code=404
    )


@api_bp.errorhandler(405)
def method_not_allowed(error):
    return error_json_response(
        message="Method Not Allowed",
        code=405
    )


@api_bp.errorhandler(500)
def server_error(error):
    return error_json_response(
        message="Internal Server Error: " + str(error.description),
        code=500
    )


@api_bp.before_request
def require_api_key():
    if request.endpoint != 'public_route':  # Exclude public routes
        # print(dict(request.headers))
        api_key = request.headers.get(
            'X-Secret-Key') or request.headers.get('secret_key')
        # print(api_key)
        if not api_key or api_key != API_KEY:
            return error_json_response('UnAuthorized', 403)


def complete_admin_login(admin):
    """Common login completion logic"""
    # Clear session and set admin session
    # next_url = session.pop("next", None)
    session.clear()
    session["admin_id"] = admin.admin_id
    session["role"] = admin.role
    session["username"] = admin.username

    # if next_url:
    # return jsonify({"status": "success", "redirect": next_url}), 200
    # return redirect_json_response(url_for(""))
    return success_json_response()
    # return jsonify({"status": "success", "redirect": url_for("admin.index")}), 200


@api_bp.route('/auth/login', methods=['POST', 'GET'])
def login():
    # print(session.sid)
    if request.method == "GET":
        abort(405)
        return
    data = request.json
    # print(data)
    username = data.get("username")
    password = data.get("password")
    ip_address = request.headers.get(
        "X_Real-IP", request.remote_addr).split(",")[0]

    if not username or not password:
        return error_json_response('Username and Password are required', 400)

    admin_service = AdminService(current_app.db)
    admin = admin_service.authenticate_admin(username, password)

    if not admin:
        return error_json_response('Invalid Credentials')

    if not admin.two_fa:
        # No 2FA required, complete login
        return complete_admin_login(admin)
    # Check if IP is trusted (completed 2FA within last 30 mins)
    if admin_service.is_ip_trusted(admin.admin_id, ip_address, current_app.config['SETTINGS'].get('2fa')):
        # IP is trusted, proceed with login
        return complete_admin_login(admin)

    # IP not trusted, require 2FA
    token_info = admin_service.create_2fa_token(
        admin.admin_id, ip_address, current_app.config['SETTINGS'].get('2fa'))
    if not token_info:
        return error_json_response('Failed to create 2FA token', 500)

    return ip_address


@api_bp.route('/auth/me')
@admin_required
def me():
    print(session.sid)
    # print(request.get_json())
    admin_service = AdminService(current_app.db)
    admin = admin_service.get_admin_by_id(session.get("admin_id")).to_dict()
    del admin['password_hash']
    print(admin)
    return success_json_response({"user": admin})


@api_bp.route("/chats/list")
@admin_required
def get_chat_list():

    page = request.args.get('page', 0, type=int)
    limit = request.args.get('limit', 10, type=int)
    filter_type = request.args.get('filter', 'all')

    chat_service = ChatService(current_app.db)
    user_service = UserService(current_app.db)

    # Get chats based on filter with pagination
    chats = chat_service.get_filtered_chats_paginated(
        admin_id=session.get("admin_id"),
        filter_type=filter_type,
        limit=limit,
        skip=page * limit
    )

    chats_data = []
    for c in chats:
        data = c.to_dict()
        data["username"] = user_service.get_user_by_id(c.user_id).name
        chats_data.append(data)
    chats_data.sort(key=lambda x: x["updated_at"], reverse=True)
    # print(len(chats_data))
    return success_json_response({"chats": chats_data, "has_more": len(chats_data) == limit})


@api_bp.route("/client/<user_id>", methods=["GET"])
@admin_required
def user(user_id):
    user_service = UserService(current_app.db)
    user = user_service.get_user_by_id(user_id)
    return success_json_response(
        user.to_dict()
    )


@api_bp.route("/chat/<room_id>", methods=["GET"])
@admin_required
def chat(room_id):
    chat_service = ChatService(current_app.db)
    user_service = UserService(current_app.db)
    chat = chat_service.get_chat_by_room_id(room_id)
    # print(chat)
    if not chat:
        return error_json_response("Chat not found"), 500
    # Get initial chats with pagination
    user = user_service.get_user_by_id(chat.user_id)
    chat_service.set_chat_viewed(chat.room_id)
    return success_json_response(
        {"user": user.to_dict(), "chat": chat.to_dict(), "username": "Ana"}
    )


def get_country_id(file_path, target_country):
    with open(file_path, 'r') as f:
        data = json.load(f)
    for entry in data:
        # print(entry.get('short_name'))
        if entry.get('short_name', "").lower() == target_country.lower():
            return entry.get('country_id')
    return None


@api_bp.route("/chat/<room_id>/send_message", methods=["POST"])
@admin_required
def send_message(room_id):
    try:
        message = request.json.get("message")
        if not message:
            return success_json_response("", 302)
        chat_service = ChatService(current_app.db)
        user_service = UserService(current_app.db)

        chat = chat_service.get_chat_by_room_id(room_id)
        if not chat:
            return error_json_response("Chat not found", 404)

        new_message = chat_service.add_message(chat.room_id, "Ana", message)
        user = user_service.get_user_by_id(chat.user_id)
        if not user:
            return error_json_response("User Not Found", 500)
        current_app.socketio.emit(
            "new_message",
            {

                'room_id': chat.room_id,
                "sender": new_message.sender,
                "content": message,
                "timestamp": new_message.timestamp.isoformat(),
            },
            room=room_id,
        )

        # return render_template('admin/fragments/chat_message.html', message=new_message, username="Ana")
        return success_json_response(None, 200)
    except Exception as e:
        return error_json_response(f"{e}", 500)


@api_bp.route('/chat/<string:room_id>/export', methods=['POST'])
@admin_required
def export_chat(room_id):
    chat_service = ChatService(current_app.db)
    chat = chat_service.get_chat_by_room_id(room_id)

    if chat:
        user_service = UserService(current_app.db)
        user = user_service.get_user_by_id(chat.user_id)
        # try:
        # erp_url = os.environ.get("ERP_URL")
        # headers = {
        #     "Content-Type": "application/x-www-form-urlencoded",
        #     "authtoken": f"{os.environ.get('ERP_TOKEN')}",
        # }
        # data = {
        #     "name": user.name,
        #     "company": user.company,
        #     "title": user.desg,
        #     "phonenumber": user.phone,
        #     "email": f"{user.email}",
        #     # "address": f"{user.city},{user.country}",
        #     "city": str(user.city),
        #     "state": str(user.city),
        #     "country": int(get_country_id('tblcountries.json', user.country)),
        #     "description": "\n".join([f"{message.sender}: {message.content}" for message in chat.messages])
        # }
        #
        # r = requests.post(erp_url, headers=headers, data=data)
        # # print(f"DATA: {data}")
        # if r.status_code == 200:
        #
        #     data = r.json()
        # print(r)
        # print(r.content)
        # TAB
        if not chat_service.export_chat(room_id, None
                                        # data.get("lead_id", None)
                                        ):
            return error_json_response("Error in exporting: Chat not found", 500)
        else:
            # print(r.json())
            pass

            # return error_json_response(f"Error in exporting: {r.status_code}, {r.json().get('message', 'Internal Server error').replace('<p>', "").replace('</p>', "")}", 500)
        return success_json_response(None, 200)

    return error_json_response("Chat not found", 500)


@api_bp.route("/chat/<room_id>/archive", methods=["POST"])
@admin_required
def archive_chat(room_id):
    chat_service = ChatService(current_app.db)
    chat = chat_service.get_chat_by_room_id(room_id)

    if chat:
        if not chat_service.archive_chat(room_id):
            return error_json_response("Error in exporting: Chat not found", 500)

        return success_json_response(None, 200)

    return error_json_response("Chat not found", 500)


@api_bp.route("/chat/<string:room_id>/delete", methods=["POST"])
@admin_required
def delete_chat(room_id):
    chat_service = ChatService(current_app.db)
    print(f"Deleted: {chat_service.delete([room_id])}")
    return success_json_response(None, 200)


@api_bp.route("/chats/latest")
@admin_required
def latest_chats():
    chat_service = ChatService(current_app.db)
    user_service = UserService(current_app.db)
    chats = chat_service.get_all_chats(admin_id=session.get("admin_id"))

    if not chats:
        return success_json_response(data={"chats": [], "stats": {"total": 0, "today": 0, "this_month": 0}})

    # Pre-calculate time boundaries once
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Single pass: get latest 5 chats + calculate stats
    chats_data = []
    today_count = this_month_count = 0

    for i, chat in enumerate(chats):
        # Get latest 5 chats data
        if i < 5:
            data = chat.to_dict()
            data["username"] = user_service.get_user_by_id(chat.user_id).name
            chats_data.append(data)

        # Calculate stats for all chats
        if chat.created_at >= today_start:
            today_count += 1
        if chat.created_at >= month_start:
            this_month_count += 1

    # Sort only the 5 chats (not all)
    chats_data.sort(key=lambda x: x["updated_at"], reverse=True)

    stats = {
        "total": len(chats),
        "today": today_count,
        "this_month": this_month_count
    }

    return success_json_response(data={"chats": chats_data, "stats": stats})


def get_latest_entry(period, collection):
    """Get the latest available entry for a given period (daily, monthly, yearly)."""
    latest = collection.find_one({"period": period}, sort=[("date", -1)])
    return latest["date"] if latest else None


def get_all_entry(period, collection):
    latest = collection.find({"period": period}, sort=[("date", -1)])
    return latest


#####################################################   GOOGLE     ###############################


@api_bp.route("/google-login")
@admin_required
def google_connect():
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE, scopes=SCOPES)
        flow.redirect_uri = url_for("api.oauth2callback", _external=True)
        auth_url, state = flow.authorization_url(
            access_type="offline", prompt="consent", include_granted_scopes="true"
        )
        session["google_auth_state"] = state

        return success_json_response(data={"auth_url": auth_url})
    except Exception as e:
        current_app.logger.error(f"Google login error: {str(e)}")
        return error_json_response("Failed to initiate Google login")


@api_bp.route("/load-folders", methods=["POST"])
@admin_required
def load_folders():
    try:
        data = request.get_json()
        selected_folders = data.get("selected_folders", [])

        admin_service = AdminService(current_app.db)
        current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

        # Update admin settings with selected folders
        current_admin.settings["selected_folders"] = selected_folders

        # Update in database
        admin_service.admins_collection.update_one(
            {"admin_id": current_admin.admin_id},
            {"$set": {"settings.selected_folders": selected_folders}},
        )

        return success_json_response(data={"message": "Folders updated successfully"})
    except Exception as e:
        current_app.logger.error(f"Load folders error: {str(e)}")
        return error_json_response("Failed to update folders")


@api_bp.route("/google-files/")
@admin_required
def google_files():
    try:
        admin_service = AdminService(current_app.db)
        current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

        if not current_admin.settings.get("google_token"):
            return success_json_response(data={
                "files": {},
                "selected_folders": [],
                "connected": False
            })

        creds = Credentials.from_authorized_user_info(
            json.loads(current_admin.settings["google_token"]), SCOPES
        )
        service = build("drive", "v3", credentials=creds)

        files_by_folder = {}
        errors = []

        for folder_id in current_admin.settings.get("selected_folders", []):
            try:
                # Get folder name
                folder_info = (
                    service.files().get(fileId=folder_id, fields="name").execute()
                )
                folder_name = folder_info.get("name", f"Folder ({folder_id})")

                # Get files in folder
                results = (
                    service.files()
                    .list(
                        q=f"'{
                            folder_id}' in parents and trashed = false and mimeType != 'application/vnd.google-apps.folder'",
                        pageSize=1000,
                        fields="files(id, name, mimeType, webViewLink, thumbnailLink)",
                    )
                    .execute()
                )

                files_by_folder[folder_name] = {
                    "id": folder_id,
                    "files": results.get("files", []),
                }
            except Exception as e:
                current_app.logger.error(f"Error accessing folder {
                                         folder_id}: {str(e)}")
                errors.append(f"Error accessing folder {folder_id}")
                continue

        return success_json_response(data={
            "files": files_by_folder,
            "selected_folders": current_admin.settings.get("selected_folders", []),
            "connected": True,
            "errors": errors if errors else None
        })

    except Exception as e:
        current_app.logger.error(f"Failed to access Google Drive: {str(e)}")
        return error_json_response("Failed to access Google Drive files")


@api_bp.route("/google-files/view/<file_id>")
@admin_required
def view_google_file(file_id):
    try:
        admin_service = AdminService(current_app.db)
        current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

        if not current_admin.settings.get("google_token"):
            return error_json_response("Google Drive not connected")

        creds = Credentials.from_authorized_user_info(
            json.loads(current_admin.settings["google_token"]), SCOPES
        )
        service = build("drive", "v3", credentials=creds)
        file = service.files().get(fileId=file_id, fields="webViewLink").execute()

        return success_json_response(data={
            "file_id": file_id,
            "view_url": file.get("webViewLink")
        })
    except Exception as e:
        current_app.logger.error(f"View file error: {str(e)}")
        return error_json_response("Failed to get file view URL")


@api_bp.route("/google-files/download", methods=["POST"])
@admin_required
def download_google_files():
    try:
        admin_service = AdminService(current_app.db)
        current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

        if not current_admin.settings.get("google_token"):
            return error_json_response("Google Drive not connected")

        data = request.get_json()
        file_ids = data.get("file_ids", [])

        if not file_ids:
            return error_json_response("No files selected for download")

        # Get the download path from config
        admin_id = session.get("admin_id")
        download_path = os.path.join(UPLOAD_FOLDER, f"{admin_id}", "files")
        os.makedirs(download_path, exist_ok=True)

        creds = Credentials.from_authorized_user_info(
            json.loads(current_admin.settings["google_token"]), SCOPES
        )
        service = build("drive", "v3", credentials=creds)

        downloaded_files = []
        failed_files = []

        for file_id in file_ids:
            try:
                # Get file metadata
                file_meta = (
                    service.files()
                    .get(fileId=file_id, fields="name, mimeType")
                    .execute()
                )

                # Create safe filename
                original_name = file_meta["name"]
                safe_name = secure_filename(original_name)
                file_path = os.path.join(download_path, safe_name)

                # Handle duplicate filenames
                counter = 1
                while os.path.exists(file_path):
                    name, ext = os.path.splitext(original_name)
                    safe_name = f"{secure_filename(name)}_{counter}{ext}"
                    file_path = os.path.join(download_path, safe_name)
                    counter += 1

                # Download file content
                request_download = service.files().get_media(fileId=file_id)
                file_content = request_download.execute()

                # Save to server
                with open(file_path, "wb") as f:
                    f.write(file_content)

                downloaded_files.append({
                    "id": file_id,
                    "original_name": original_name,
                    "saved_name": safe_name
                })

            except Exception as e:
                current_app.logger.error(
                    f"Error downloading file {file_id}: {str(e)}")
                failed_files.append({"id": file_id, "error": str(e)})
                continue

        return success_json_response(data={
            "downloaded_files": downloaded_files,
            "failed_files": failed_files,
            "total_downloaded": len(downloaded_files),
            "total_failed": len(failed_files)
        })

    except Exception as e:
        current_app.logger.error(f"Failed to download files: {str(e)}")
        return error_json_response("Failed to download files")


@api_bp.route('/google/logout', methods=['POST'])
@admin_required
def google_logout():
    try:
        admin_service = AdminService(current_app.db)
        admin_service.admins_collection.update_one(
            {"admin_id": session.get('admin_id')},
            {"$unset": {"settings.google_token": "", "settings.selected_folders": ""}},
        )

        return success_json_response(data={"message": "Successfully logged out from Google Drive"})
    except Exception as e:
        current_app.logger.error(f"Google logout error: {str(e)}")
        return error_json_response("Failed to logout from Google Drive")


@api_bp.route("/google-thumbnail/<file_id>")
@admin_required
def google_thumbnail(file_id):
    try:
        admin_service = AdminService(current_app.db)
        current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

        if not current_admin.settings.get("google_token"):
            return error_json_response("Google Drive not connected")

        creds = Credentials.from_authorized_user_info(
            json.loads(current_admin.settings["google_token"]), SCOPES
        )
        service = build("drive", "v3", credentials=creds)

        # Get file info first
        file_info = service.files().get(fileId=file_id, fields="thumbnailLink").execute()
        thumbnail_link = file_info.get("thumbnailLink")

        if thumbnail_link:
            return success_json_response(data={
                "file_id": file_id,
                "thumbnail_url": thumbnail_link
            })
        else:
            # If no thumbnail available, download the actual file
            request_download = service.files().get_media(fileId=file_id)
            from googleapiclient.http import MediaIoBaseDownload
            import io
            import base64

            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request_download)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)

            # Convert to base64 for JSON response
            file_data = base64.b64encode(fh.read()).decode('utf-8')

            return success_json_response(data={
                "file_id": file_id,
                "file_data": file_data,
                "mime_type": "image/jpeg"
            })

    except Exception as e:
        current_app.logger.error(f"Thumbnail error: {str(e)}")
        return error_json_response("Failed to get file thumbnail")


@api_bp.route("/oauth2callback")
@admin_required
def oauth2callback():
    try:
        state = session.get("google_auth_state")
        if not state:
            return error_json_response("Invalid authentication state")

        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE, scopes=SCOPES, state=state
        )
        flow.redirect_uri = url_for("api.oauth2callback", _external=True)
        flow.fetch_token(authorization_response=request.url)

        # Store credentials in the admin's settings
        admin_service = AdminService(current_app.db)
        current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

        # Update admin settings with the new token
        current_admin.settings["google_token"] = flow.credentials.to_json()
        admin_service.admins_collection.update_one(
            {"admin_id": current_admin.admin_id},
            {"$set": {"settings.google_token": flow.credentials.to_json()}},
        )

        return redirect("gobotadmin://oauth-callback?success=true")
    except Exception as e:
        current_app.logger.error(f"OAuth callback error: {str(e)}")
        return error_json_response("Failed to complete Google Drive authentication")


@api_bp.route("/google/save-tokens", methods=["POST"])
@admin_required
def save_google_tokens():
    try:
        data = request.get_json()
        # Get authorization code from frontend
        auth_code = data.get("auth_code")

        if not auth_code:
            return error_json_response("Authorization code is required")

        # Create flow instance
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES
        )
        flow.redirect_uri = url_for("api.oauth2callback", _external=True)

        # Exchange authorization code for tokens
        flow.fetch_token(code=auth_code)

        # The flow now contains complete credentials with refresh token
        credentials = flow.credentials

        # Save to admin settings
        admin_service = AdminService(current_app.db)
        current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

        current_admin.settings["google_token"] = credentials.to_json()
        admin_service.admins_collection.update_one(
            {"admin_id": current_admin.admin_id},
            {"$set": {"settings.google_token": credentials.to_json()}},
        )

        return success_json_response(data={
            "message": "Tokens saved successfully",
            "has_refresh_token": credentials.refresh_token is not None
        })

    except FileNotFoundError:
        return error_json_response("Credentials file not found")
    except json.JSONDecodeError:
        return error_json_response("Invalid credentials file format")
    except Exception as e:
        current_app.logger.error(f"Save tokens error: {str(e)}")
        return error_json_response(f"Failed to save Google tokens: {str(e)}")


#####################################################   SETTINGS     ###############################

@api_bp.route("/settings", methods=["GET"])
@admin_required
def settings():
    try:
        admin_service = AdminService(current_app.db)
        current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

        # Initialize settings data based on role
        if current_admin.role == "superadmin":
            settings_data = {
                **current_app.config["SETTINGS"], **current_admin.settings}
        else:
            settings_data = current_admin.settings

        # Validate logo paths for superadmin
        if current_admin.role == "superadmin":
            settings_data["logo"]["large"] = (
                current_app.config["SETTINGS"]["logo"]["large"]
                if os.path.exists(
                    os.path.join(
                        os.getcwd(),
                        current_app.config["SETTINGS"]["logo"]["large"][1:]
                    )
                )
                else ""
            )
            settings_data["logo"]["small"] = (
                current_app.config["SETTINGS"]["logo"]["small"]
                if os.path.exists(
                    os.path.join(
                        os.getcwd(),
                        current_app.config["SETTINGS"]["logo"]["small"][1:]
                    )
                )
                else ""
            )

        # Sort timings by day order if they exist
        day_order = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
        }
        if settings_data.get("timings"):
            settings_data["timings"] = sorted(
                settings_data["timings"],
                key=lambda time: day_order[time["day"]]
            )

        # Handle Google Drive connection for all admins
        folders = []
        selected_folders = []
        if current_admin.settings.get("google_token"):
            try:
                creds = Credentials.from_authorized_user_info(
                    json.loads(current_admin.settings["google_token"]), SCOPES
                )
                if creds:
                    service = build("drive", "v3", credentials=creds)
                    results = (
                        service.files()
                        .list(
                            q="mimeType='application/vnd.google-apps.folder'",
                            fields="files(id, name)",
                        )
                        .execute()
                    )
                    folders = results.get("files", [])
                    selected_folders = current_admin.settings.get(
                        "selected_folders", [])
            except Exception as e:
                current_app.logger.error(
                    f"Failed to load Google Drive for admin {
                        current_admin.admin_id}: {str(e)}"
                )

        # Update config for superadmin
        if current_admin.role == 'superadmin':
            current_app.db.config.update_one(
                {"id": "settings"},
                {"$set": current_app.config['SETTINGS']}
            )

        # Prepare response data
        response_data = {
            "settings": settings_data,
            "timezones": UTCZoneManager.get_timezones(),
            "folders": folders,
            "selected_folders": selected_folders,
            "audio_file": "/static/sounds/message.wav"
        }

        return success_json_response(data=response_data)

    except Exception as e:
        current_app.logger.error(f"Settings endpoint error: {str(e)}")
        return error_json_response("Failed to load settings")


@api_bp.route("/settings/subject", defaults={"subject": None}, methods=["POST"])
@api_bp.route("/settings/subject/<string:subject>", methods=["DELETE"])
@admin_required
def subjects(subject):
    admin_service = AdminService(current_app.db)
    current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

    if request.method == "POST":
        subject = request.json.get("subject")
        if not subject:
            return error_json_response("Subject is required", 400)

        try:
            if current_admin.role == "superadmin":
                current_app.config["SETTINGS"]["subjects"] = set(
                    current_app.config["SETTINGS"].get("subjects", [])
                )
                current_app.config["SETTINGS"]["subjects"].add(subject)
                return success_json_response({"subject": subject}, 201)
            else:
                current_admin.settings["subjects"] = set(
                    current_admin.settings.get("subjects", [])
                )
                current_admin.settings["subjects"].add(subject)
                admin_service.admins_collection.update_one(
                    {"admin_id": current_admin.admin_id},
                    {"$addToSet": {"settings.subjects": subject}},
                )
                return success_json_response({"subject": subject}, 201)

        except Exception as e:
            return error_json_response(f"Failed to add subject: {str(e)}", 500)

    else:  # DELETE method
        try:
            if current_admin.role == "superadmin":
                if subject in current_app.config["SETTINGS"].get("subjects", []):
                    current_app.config["SETTINGS"]["subjects"].remove(subject)
                    return success_json_response({"message": f"Subject '{subject}' deleted successfully"})
                else:
                    return error_json_response("Subject not found", 404)
            else:
                if subject in current_admin.settings.get("subjects", []):
                    current_admin.settings["subjects"].remove(subject)
                    admin_service.admins_collection.update_one(
                        {"admin_id": current_admin.admin_id},
                        {"$pull": {"settings.subjects": subject}},
                    )
                    return success_json_response({"message": f"Subject '{subject}' deleted successfully"})
                else:
                    return error_json_response("Subject not found", 404)

        except KeyError:
            return error_json_response("Subject not found", 404)
        except Exception as e:
            return error_json_response(f"Failed to delete subject: {str(e)}", 500)


@api_bp.route("/settings/language", methods=["POST"])
@admin_required
def add_language():
    language = request.json.get("language")
    if not language:
        return error_json_response("Language is required", 400)

    admin_service = AdminService(current_app.db)
    current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

    try:
        if current_admin.role == "superadmin":
            # Update global settings
            languages = set(
                current_app.config["SETTINGS"].get("languages", ["English"])
            )
            languages.add(language)
            current_app.config["SETTINGS"]["languages"] = list(languages)
            return success_json_response({"language": language}, 201)
        else:
            # Update admin-specific settings
            languages = set(current_admin.settings.get(
                "languages", ["English"]))
            languages.add(language)
            current_admin.settings["languages"] = list(languages)

            # Update in database
            admin_service.admins_collection.update_one(
                {"admin_id": current_admin.admin_id},
                {"$addToSet": {"settings.languages": language}},
            )
            return success_json_response({"language": language}, 201)

    except Exception as e:
        current_app.logger.error(f"Error adding language: {str(e)}")
        return error_json_response("Failed to add language", 500)


@api_bp.route("/settings/language/<string:language>", methods=["DELETE"])
@admin_required
def remove_language(language):
    if not language:
        return error_json_response("Language is required", 400)

    admin_service = AdminService(current_app.db)
    current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

    try:
        if current_admin.role == "superadmin":
            # Update global settings
            languages = set(
                current_app.config["SETTINGS"].get("languages", ["English"])
            )
            if language not in languages:
                return error_json_response("Language not found", 404)
            languages.discard(language)
            current_app.config["SETTINGS"]["languages"] = list(languages)
            return success_json_response({"message": f"Language '{language}' removed successfully"})
        else:
            # Update admin-specific settings
            languages = set(current_admin.settings.get(
                "languages", ["English"]))
            if language not in languages:
                return error_json_response("Language not found", 404)
            languages.discard(language)
            current_admin.settings["languages"] = list(languages)

            # Update in database
            admin_service.admins_collection.update_one(
                {"admin_id": current_admin.admin_id},
                {"$pull": {"settings.languages": language}},
            )
            return success_json_response({"message": f"Language '{language}' removed successfully"})

    except Exception as e:
        current_app.logger.error(f"Error removing language: {str(e)}")
        return error_json_response("Failed to remove language", 500)


@api_bp.route("/settings/timezone", methods=["POST"])
@admin_required
def set_timezone():
    data = request.get_json()
    if not data or 'timezone' not in data:
        return error_json_response("Timezone is required", 400)

    tz = data.get("timezone")
    admin_service = AdminService(current_app.db)
    current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

    try:
        if current_admin.role == "superadmin":
            current_app.config["SETTINGS"]["timezone"] = tz
            return success_json_response({"timezone": tz}, 200)
        else:
            current_admin.settings["timezone"] = tz
            admin_service.admins_collection.update_one(
                {"admin_id": current_admin.admin_id}, {
                    "$set": {"settings.timezone": tz}}
            )
            return success_json_response({"timezone": tz}, 200)
    except Exception as e:
        current_app.logger.error(f"Error setting timezone: {str(e)}")
        return error_json_response("Failed to set timezone", 500)


@api_bp.route("/settings/timing", methods=["POST"])
@admin_required
def add_timing():
    data = request.get_json()
    if not data:
        return error_json_response("Request data is required", 400)

    day = data.get("meetingDay")
    start_time = data.get("startTime")
    end_time = data.get("endTime")

    # Validate required fields
    if not all([day, start_time, end_time]):
        return error_json_response("Day, start time, and end time are required", 400)

    admin_service = AdminService(current_app.db)
    current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

    try:
        if current_admin.role == "superadmin":
            timings = current_app.config["SETTINGS"].get("timings", [])
        else:
            timings = current_admin.settings.get("timings", [])

        # Remove existing entry for that day
        timings = [t for t in timings if t["day"] != day]

        # Add new timing entry
        timings.append(
            {"day": day, "startTime": start_time, "endTime": end_time})

        # Sort by weekday
        day_order = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        timings.sort(key=lambda t: day_order[t["day"]])

        if current_admin.role == "superadmin":
            current_app.config["SETTINGS"]["timings"] = timings
        else:
            current_admin.settings["timings"] = timings
            admin_service.admins_collection.update_one(
                {"admin_id": current_admin.admin_id},
                {"$set": {"settings.timings": timings}},
            )

        return success_json_response({"timings": timings}, 200)

    except Exception as e:
        current_app.logger.error(f"Error adding timing: {str(e)}")
        return error_json_response("Failed to add timing", 500)


@api_bp.route("/settings/prompt", methods=["POST"])
@admin_required
def set_prompt():
    data = request.get_json()
    if not data or 'prompt' not in data:
        return error_json_response("Prompt is required", 400)

    prpt = data.get("prompt")
    admin_service = AdminService(current_app.db)
    current_admin = admin_service.get_admin_by_id(session.get("admin_id"))

    try:
        if current_admin.role == "superadmin":
            current_app.config["SETTINGS"]["prompt"] = prpt
            return success_json_response({"prompt": prpt}, 200)
        else:
            current_admin.settings["prompt"] = prpt
            admin_service.admins_collection.update_one(
                {"admin_id": current_admin.admin_id}, {
                    "$set": {"settings.prompt": prpt}}
            )
            return success_json_response({"prompt": prpt}, 200)
    except Exception as e:
        current_app.logger.error(f"Error setting prompt: {str(e)}")
        return error_json_response("Failed to set prompt", 500)


