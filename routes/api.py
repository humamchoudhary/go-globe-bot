from config import Config
from flask import request, make_response, session, jsonify, url_for, current_app, abort
from functools import wraps
from . import api_bp
from services.admin_service import AdminService


def success_json_response(data=None, code=200):
    return jsonify({"status": "success", **({"data": data} if data else {})}), code


def error_json_response(message="Error! Couldnot process this request", code=500):
    return jsonify({"status": "error", "message": message}), code


def redirect_json_response(redirect, code=302):
    return jsonify({"status": "redirect", "redirect": redirect}), code


def admin_required(_func=None, *, roles=None):
    if roles is None:
        roles = ["admin", "superadmin"]
    elif isinstance(roles, str):
        roles = [roles]

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("role") not in roles:
                return redirect_json_response(url_for('api.login'))
            if not session.get("admin_id"):
                session["next"] = request.path
                return redirect_json_response(url_for('api.login'))

            admin_service = AdminService(current_app.db)
            current_admin = admin_service.get_admin_by_id(session["admin_id"])

            if not current_admin or not current_admin.has_permission(roles):
                return redirect_json_response(url_for('api.login'))

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
            'X-SECRET-KEY') or request.headers.get('secret_key')
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


@api_bp.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == "GET":
        abort(405)
        return
    data = request.json
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


@api_bp.route('/')
def test():
    return success_json_response()
