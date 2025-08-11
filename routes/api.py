import requests
import os
import json
from config import Config
from flask import request, make_response, session, jsonify, url_for, current_app, abort
from functools import wraps
from . import api_bp
from services.admin_service import AdminService
from services.chat_service import ChatService
from services.user_service import UserService


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
            print(dict(session))
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
        print(dict(request.headers))
        api_key = request.headers.get(
            'X-Secret-Key') or request.headers.get('secret_key')
        print(api_key)
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
    return jsonify({"status": "success", "redirect": url_for("admin.index")}), 200


@api_bp.route('/auth/login', methods=['POST', 'GET'])
def login():
    if request.method == "GET":
        abort(405)
        return
    data = request.json
    print(data)
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
    admin_service = AdminService(current_app.db)
    admin = admin_service.get_admin_by_id(session.get("admin_id")).to_dict()
    del admin['password_hash']
    return success_json_response({"user": admin})


@api_bp.route("/chats/list")
@admin_required
def get_chat_list():

    page = request.args.get('page', 0, type=int)
    limit = request.args.get('limit', 20, type=int)
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
    print(len(chats_data))
    return success_json_response({"chats": chats_data, "has_more": len(chats_data) == limit})


def get_country_id(file_path, target_country):
    with open(file_path, 'r') as f:
        data = json.load(f)
    for entry in data:
        print(entry.get('short_name'))
        if entry.get('short_name', "").lower() == target_country.lower():
            return entry.get('country_id')
    return None


@api_bp.route('/chat/<string:room_id>/export',methods=['POST'])
@admin_required
def export_chat(room_id):
    chat_service = ChatService(current_app.db)
    chat = chat_service.get_chat_by_room_id(room_id)

    if chat:
        user_service = UserService(current_app.db)
        user = user_service.get_user_by_id(chat.user_id)
        # try:
        erp_url = os.environ.get("ERP_URL")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "authtoken": f"{os.environ.get('ERP_TOKEN')}",
        }
        data = {
            "name": user.name,
            "company": user.company,
            "title": user.desg,
            "phonenumber": user.phone,
            "email": f"{user.email}",
            # "address": f"{user.city},{user.country}",
            "city": str(user.city),
            "state": str(user.city),
            "country": int(get_country_id('tblcountries.json', user.country)),
            "description": "\n".join([f"{message.sender}: {message.content}" for message in chat.messages])
        }

        r = requests.post(erp_url, headers=headers, data=data)
        print(f"DATA: {data}")
        if r.status_code == 200:

            data = r.json()
            print(r)
            print(r.content)
            if not chat_service.export_chat(room_id, data.get("lead_id", None)):
                return error_json_response("Error in exporting: Chat not found", 500)
        else:
            print(r.json())

            return error_json_response(f"Error in exporting: {r.status_code}, {r.json().get('message', 'Internal Server error').replace('<p>', "").replace('</p>', "")}", 500)
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

