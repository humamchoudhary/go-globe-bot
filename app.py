from datetime import timedelta
from flask import Flask, session, url_for, jsonify, Response, g
import uuid
from flask import render_template,  request, redirect, current_app
from flask_socketio import SocketIO
from flask_session import Session
from pymongo import MongoClient
import bcrypt
import os
from config import Config
from routes import chat_bp, admin_bp, auth_bp, min_bp
from routes.chat import register_socketio_events
from routes.admin import register_admin_socketio_events
import routes.auth
import routes.min
from routes.min import register_min_socketio_events
import glob
from models.bot import Bot
from flask_cors import CORS
from services.logs_service import LogsService
from models.log import LogLevel, LogTag, LogEntry
import traceback
from datetime import datetime
import json
from services.admin_service import AdminService
from urllib.parse import urlparse
from flask_mail import Mail, Message


def get_font_data():
    # Path to your font directory
    # font_dir = os.path.join(
    #     app.static_folder, 'font/Proxima Nova Complete Collection')

    font_dir = os.path.join(
        app.static_folder, 'font/NeueHaas')

    # Find all font files
    font_files = []
    for ext in ['ttf', 'otf', 'woff', 'woff2']:
        font_files.extend(glob.glob(os.path.join(font_dir, f'*.{ext}')))

    # Extract just the filenames
    font_files = [os.path.basename(f) for f in font_files]

    return font_files

import time
def create_app(config_class=Config):
    app = Flask(__name__)
    CORS(app, origins=["*"],
         supports_credentials=True,
         allow_headers=["*"],
         expose_headers=["Content-Disposition"],
         methods=["GET", "POST", "OPTIONS"])
    app.config.from_object(config_class)

    # Setup MongoDB
    client = MongoClient(app.config['MONGODB_URI'])
    db = client.get_database()
    app.db = db
    app.config['SESSION_MONGODB'] = client
    app.config['ONLINE_USERS'] = 0
    app.config['NOTIFICATIONS'] = []
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    app.config['SESSION_TYPE'] = 'mongodb'
    app.config['LOGOS_FOLDER'] = os.path.join(os.getcwd(), 'static/img/')
    app.config['SOUND_FOLDER'] = os.path.join(os.getcwd(), 'static/sounds/')

    def is_mobile(user_agent):
        mobile_keywords = ['mobile', 'android',
                           'iphone', 'ipad', 'blackberry', 'iemobile']
        # # print(user_agent.__dict__)
        user_agent_lower = user_agent.string.lower()
        return any(keyword in user_agent_lower for keyword in mobile_keywords)

    @app.before_request
    def start_timer():
        g.start_time = time.time()


    @app.after_request
    def log_request_time(response):
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            endpoint = request.endpoint or 'unknown'
            method = request.method
            path = request.path
            print(f"[{method}] {path} (endpoint: {endpoint}) took {duration:.4f} seconds")
        return response


    app.jinja_env.tests['mobile'] = is_mobile

    app.jinja_env.globals['bots'] = Bot.get_bots

    # app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Or 'None' if using HTTPS
    # # Must be True if using 'None' for SameSite
    # app.config['SESSION_COOKIE_SECURE'] = True

    app.config.update(
        SESSION_COOKIE_SECURE=True,  # Required for cross-origin iframes with HTTPS
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='None'
    )

    app.config.update(
        SESSION_TYPE='mongodb',
        SESSION_MONGODB=client,  # Ensure this is set
        SESSION_PERMANENT=True,
        SESSION_USE_SIGNER=True,  # Helps prevent tampering
        SESSION_KEY_PREFIX='session:',
    )

    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3)
    IGNORE_PATHS = {'static',
                    'socket.io',
                    'favicon.ico',
                    'healthcheck',
                    'robots.txt'}

    SENSITIVE_HEADERS = {
        'Authorization',
        'Cookie',
        'X-Api-Key',
        'X-CSRFToken', 'password'
    }
    logs_service = LogsService(app.db)

    app.config['MAIL_SERVER'] = os.environ.get('SMTP_SERVER')
    app.config['MAIL_PORT'] = int(os.environ.get('SMTP_PORT', 465))
    app.config['MAIL_USE_TLS'] = False  # Set to False if using SSL on port 465
    app.config['MAIL_USE_SSL'] = True  # Set to True if using SSL on port 465
    app.config['MAIL_USERNAME'] = os.environ.get('SMTP_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('SMTP_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('SMTP_USERNAME')

    from urllib.parse import urlparse

    #####################  GO BACK TO THIS CODE ONCE THE HEADER IS ADDED #########################
    # @app.before_request
    # def set_admin_id():
    #     origin = request.headers.get('Origin')
    #     referer = request.headers.get('Referer')
    #     print('\n\n\n\n')
    #     print(f"[BEFORE_REQUEST] Incoming request - Path: {request.path}")
    #     print(f"[HEADERS] Referer: {referer}")
    #     print(f"[HEADERS] Origin: {origin}")
    #
    #     # Skip domain check for exempted paths
    #     exempt_paths = ['static', 'socket.io',
    #                     'favicon.ico', 'healthcheck', 'robots.txt']
    #     if any(request.path.startswith(f'/{path}') for path in exempt_paths):
    #         print(f"[SKIP] Path '{
    #               request.path}' is exempted from domain check.")
    #         return
    #
    #     admin_id = None
    #     if origin or referer:
    #         admin_id = session.get('admin_id')
    #         print(f"[SESSION] Found admin_id in session: {admin_id}")
    #     else:
    #         admin_id = os.environ.get('DEFAULT_ADMIN_ID')
    #         print(
    #             f"[ENV] No Origin/Referer. Using DEFAULT_ADMIN_ID from env: {admin_id}")
    #
    #     admin = None
    #     sec_key = None
    #
    #     if not admin_id and referer and Config.BACKEND_URL in referer:
    #         admin_id = os.environ.get('DEFAULT_ADMIN_ID')
    #         print(
    #             f"[FALLBACK] Referer matches BACKEND_URL. Using DEFAULT_ADMIN_ID: {admin_id}")
    #
    #     if admin_id:
    #         print(f"[DB] Fetching admin by ID: {admin_id}")
    #         admin = AdminService(app.db).get_admin_by_id(admin_id)
    #         print(f"[DB] Admin fetched: {admin}")
    #     else:
    #         sec_key = request.headers.get('SECRET_KEY')
    #         print(
    #             f"[SECURITY] No admin_id found. Checking for SECRET_KEY in headers: {sec_key}")
    #         if sec_key:
    #             admin = AdminService(app.db).get_admin_by_key(sec_key)
    #             print(f"[DB] Admin fetched using SECRET_KEY: {admin}")
    #         else:
    #             print("[ERROR] No admin_id or SECRET_KEY provided. Returning 403.")
    #             return "No Secret Key", 403
    #
    #     if admin:
    #         session['admin_id'] = admin.admin_id
    #         print(f"[SESSION] Set session admin_id: {admin.admin_id}")
    #         # print(f"[SESSION] Set session role: {admin.role}")  # Uncomment if needed
    #
    #     # Domain checking for non-superadmin admins
    #     if admin and 'domains' in admin.settings and admin.settings['domains']:
    #         print(f"[SECURITY] Admin has domain restrictions: {
    #               admin.settings['domains']}")
    #         if referer:
    #             domain = urlparse(referer).netloc
    #             print(f"[DOMAIN] Parsed referer domain: {domain}")
    #             if domain not in admin.settings['domains'] and domain not in Config.BACKEND_URL:
    #                 print(f"[ACCESS DENIED] Domain '{
    #                       domain}' not allowed for this admin.")
    #                 return "Access denied", 403
    #         else:
    #             print("[WARNING] No referer provided to validate domain.")

    @app.before_request
    def set_admin_id():

        if not request.path.startswith('/min/'):
            return
        origin = request.headers.get('Origin')
        referer = request.headers.get('Referer')
        # print(f"[BEFORE_REQUEST] Incoming request - Path: {request.path}")
        # print(f"[HEADERS] Referer: {referer}")
        # print(f"[HEADERS] Origin: {origin}")

        exempt_paths = ['static', 'socket.io',
                        'favicon.ico', 'healthcheck', 'robots.txt']
        if any(request.path.startswith(f'/{path}') for path in exempt_paths):
            # print(f"[SKIP] Path '{
            # request.path}' is exempted from domain check.")
            return

        admin_id = None
        if origin or referer:
            admin_id = session.get('admin_id')
            # print(f"[SESSION] Found admin_id in session: {admin_id}")
        else:
            # print("[INFO] No Origin or Referer in headers.")
            pass

        if not admin_id and referer and Config.BACKEND_URL in referer:
            admin_id = os.environ.get('DEFAULT_ADMIN_ID')
            # print(
            # f"[FALLBACK] Referer matches BACKEND_URL. Using DEFAULT_ADMIN_ID: {admin_id}")

        admin = None
        sec_key = request.headers.get('SECRET_KEY')
        # print(f"[SECURITY] SECRET_KEY from headers: {sec_key}")

        # Attempt admin fetch by ID
        if admin_id:
            # print(f"[DB] Fetching admin by ID: {admin_id}")
            admin = AdminService(app.db).get_admin_by_id(admin_id)

        # If no admin yet, try SECRET_KEY
        if not admin and sec_key:
            # print(f"[DB] Fetching admin by SECRET_KEY: {sec_key}")
            admin = AdminService(app.db).get_admin_by_key(sec_key)

        # If still no admin, use default fallback
        if not admin:
            fallback_admin_id = os.environ.get('DEFAULT_ADMIN_ID')
            # print(f"[FALLBACK] No valid admin_id or SECRET_KEY. Using DEFAULT_ADMIN_ID: {
            # fallback_admin_id}")
            admin = AdminService(app.db).get_admin_by_id(fallback_admin_id)

        # Final check
        if not admin:
            # print("[ERROR] Admin could not be determined. Returning 403.")
            return "Access denied", 403

        # Set admin_id in session
        session['admin_id'] = admin.admin_id
        # print(f"[SESSION] Set session admin_id: {admin.admin_id}")

        # Check domain access if required
        if 'domains' in admin.settings and admin.settings['domains']:
            # print(f"[SECURITY] Admin has domain restrictions: {
            # admin.settings['domains']}")
            if referer:
                domain = urlparse(referer).netloc
                # print(f"[DOMAIN] Parsed referer domain: {domain}")
                if domain not in admin.settings['domains'] and domain not in Config.BACKEND_URL:
                    # print(f"[ACCESS DENIED] Domain '{
                    # domain}' not allowed for this admin.")
                    return "Access denied", 403
            else:
                # print("[WARNING] No referer provided to validate domain.")
                pass

    @app.before_request
    def log_request():
        """Comprehensive request logging middleware"""
        try:
            path = request.path.strip(
                '/').split('/')[0] if request.path else 'root'

            # Skip ignored paths
            if path in IGNORE_PATHS:
                return

            # Prepare request data
            request_id = str(uuid.uuid4())
            g.request_id = request_id  # Store in Flask's g for later use

            # Redact sensitive headers
            headers = dict(request.headers)
            for header in SENSITIVE_HEADERS:
                if header in headers:
                    headers[header] = '[REDACTED]'

            # Get user/agent information
            user_id = session.get('user_id')
            admin_id = session.get('admin_id')
            ip_address = request.headers.get(
                'X-Forwarded-For', request.remote_addr)
            user_agent = request.headers.get('User-Agent')

            # Determine log level based on path
            if path.startswith('admin'):
                log_level = LogLevel.INFO
                log_tag = LogTag.ADMIN
            elif path.startswith('api'):
                log_level = LogLevel.DEBUG
                log_tag = LogTag.ACCESS
            else:
                log_level = LogLevel.INFO
                log_tag = LogTag.ACCESS

            # Create request data payload
            request_data = {
                'request_id': request_id,
                'method': request.method,
                'path': request.path,
                'endpoint': request.endpoint,
                'args': dict(request.args),
                'headers': headers,
                'ip': ip_address,
                'user_agent': user_agent,
                'content_type': request.content_type,
                'content_length': request.content_length
            }

            # For form data
            if request.form:
                request_data['form_data'] = dict(request.form)

            # For JSON data
            if request.is_json:
                try:
                    request_data['json_data'] = request.get_json()
                except Exception as e:
                    request_data['json_data_error'] = f'Invalid JSON payload: {
                        str(e)}'

            # Create the log entry
            log_entry = logs_service.create_log(
                level=log_level,
                tag=log_tag,
                message=f"{request.method} {request.path}",
                user_id=user_id,
                admin_id=admin_id,
                data={
                    'request': request_data,
                    'session': {
                        'session_id': session.get('_id'),
                        'session_data': {k: v for k, v in session.items()
                                         if not k.startswith('_')}
                    }
                }
            )

            # Store log ID for potential error correlation
            g.log_id = log_entry.log_id

        except Exception as e:
            app.logger.error(f"Failed to log request: {
                             str(e)}\n{traceback.format_exc()}")

    @app.after_request
    def log_response(response):
        """Log response information"""

        # admin_id = session.get('admin_id')
        try:
            if hasattr(g, 'log_id') and hasattr(g, 'request_id'):
                logs_service.logs_collection.update_one(
                    {'log_id': g.log_id},
                    {'$set': {
                        'response': {
                            'status_code': response.status_code,
                            'content_length': response.content_length,
                            'content_type': response.content_type,
                            'headers': dict(response.headers)
                        },
                        'completed_at': datetime.utcnow(),
                        'duration': (datetime.utcnow() - g.get('request_start_time', datetime.utcnow())).total_seconds()
                    }}
                )
        except Exception as e:
            app.logger.error(f"Failed to log response: {
                             str(e)}\n{traceback.format_exc()}")
        return response

    @app.errorhandler(Exception)
    def log_exception(error):
        """Log exceptions with correlation to original request"""

        admin_id = session.get('admin_id')
        try:
            if hasattr(g, 'log_id'):
                logs_service.create_log(
                    level=LogLevel.ERROR,
                    tag=LogTag.SYSTEM,
                    message=f"Request failed: {str(error)}",
                    admin_id=admin_id,
                    data={
                        'error': str(error),
                        'type': error.__class__.__name__,
                        'related_request': g.log_id,
                        'traceback': traceback.format_exc() if app.debug else None
                    }
                )
        except Exception as e:
            app.logger.error(f"Failed to log exception: {
                             str(e)}\n{traceback.format_exc()}")
        return error


# Add request start time tracking

    @app.before_request
    def start_timer():
        g.request_start_time = datetime.utcnow()

    # @app.context_processor
    # def settings():
    #     admin_id = session.get('admin_id')
    #     # Start with global settings
    #     settings_data = current_app.config['SETTINGS'].copy()
    #
    #     if admin_id:
    #         admin_service = AdminService(current_app.db)
    #         admin = admin_service.get_admin_by_id(admin_id)
    #         if admin and admin.settings:
    #             # Merge admin settings with global settings
    #             settings_data.update(admin.settings)
    #
    #     # Process subjects and languages
    #     settings_data['subjects'] = list(settings_data.get('subjects', []))
    #     settings_data['languages'] = list(
    #         settings_data.get('languages', ['English']))
    #
    #     # Save to database (only global settings)
    #     if not admin_id:  # Only superadmin can update global settings
    #         db.config.replace_one(
    #             {"id": "settings"},
    #             {"id": "settings", **settings_data, "apiKeys": "removed"},
    #             upsert=True
    #         )
    #
    #     # Sort for display
    #     settings_data['subjects'] = sorted(
    #         settings_data['subjects'], key=len, reverse=True)
    #     settings_data['languages'] = sorted(
    #         settings_data['languages'], key=len, reverse=True)
    #
    #     return {'settings': settings_data}

    conf = db.config.find_one({"id": "settings"})
    if conf:
        app.config['SETTINGS'] = conf
    else:
        # Initialize default superadmin settings
        app.config['SETTINGS'] = {
            'id': 'settings',
            'logo': {
                'large': '/static/img/logo.svg',
                'small': '/static/img/logo-desktop-mini.svg',
            },
            'apiKeys': {
                'claude': Config.CLAUDE_KEY,
                'openAi': Config.OPENAI_KEY,
                'deepseek': Config.DEEPSEEK_KEY,
                'gemini': Config.GEMINI_KEY
            },
            'model': 'gemini_2.0_flash',
            'theme': 'system',
            'sound': '/static/sounds/notification.wav',
            'backend_url': Config.BACKEND_URL,
            'prompt': """you are a customer service assistant..."""
        }
        db.config.insert_one(app.config['SETTINGS'])
    if not app.config['SETTINGS'].get('2fa'):

        app.config['SETTINGS']['2fa'] = {
            "duration": 1, "unit": 'days'}

    @app.context_processor
    def inject_settings():
        """Inject settings into templates, combining superadmin settings with admin-specific settings"""
        settings_data = app.config['SETTINGS'].copy()

        admin_id = session.get('admin_id')
        if admin_id:
            admin_service = AdminService(app.db)
            admin = admin_service.get_admin_by_id(admin_id)
            if admin:
                # Merge admin-specific settings with superadmin settings
                # Admin settings take precedence for overlapping keys
                if admin.settings:
                    settings_data.update(admin.settings)

                # Special handling for languages and subjects
                if 'languages' in admin.settings:
                    settings_data['languages'] = admin.settings['languages']
                if 'subjects' in admin.settings:
                    settings_data['subjects'] = admin.settings['subjects']

        return {'settings': settings_data}

    app.bot = Bot(Config.BOT_NAME, app=app)

    # app.config['SETTINGS']['backend_url'] = 'https://192.168.22.249:5000'

    # Setup Flask-Session
    Session(app)

    # Setup SocketIO
    socketio = SocketIO(app,  async_mode="threading",
                        manage_session=False, cors_allowed_origins="*")
    app.socketio = socketio

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(min_bp)

    # Register Socket.IO event handlers
    register_socketio_events(socketio)
    register_min_socketio_events(socketio)
    register_admin_socketio_events(socketio)

    # Create admin user if it doesn't exist
    if not app.config.get('ADMIN_PASSWORD'):
        # For development, create a default admin password if not set
        default_pwd = "4z39oNoZv85btdBj"
        hashed = bcrypt.hashpw(default_pwd.encode('utf-8'), bcrypt.gensalt())
        app.config['ADMIN_PASSWORD'] = hashed.decode('utf-8')
        # print(f"Using default admin password: {default_pwd}")

    def has_no_empty_params(rule):
        defaults = rule.defaults if rule.defaults is not None else ()
        arguments = rule.arguments if rule.arguments is not None else ()
        return len(defaults) >= len(arguments)

    @app.context_processor
    def inject_font_data():

        # print(app.config['SETTINGS']['backend_url'])
        # print('fonts called')
        return {'font_files': get_font_data()}

    @app.route('/render-bot')
    def render_chatbot():

        return Response(render_template('js/init_chat.js', backend_url=app.config['SETTINGS']['backend_url']), mimetype='application/javascript')

    @app.route("/site-map")
    def site_map():
        links = []
        for rule in app.url_map.iter_rules():
            if "GET" in rule.methods and has_no_empty_params(rule):
                url = url_for(rule.endpoint, **(rule.defaults or {}))
                links.append((url, rule.endpoint))
        return jsonify(links)

    @app.route('/privacy')
    def privacy():
        return render_template('privacy.html')

    @app.route('/terms')
    def terms():
        return render_template('terms.html')

    # @app.route('/test-page')
    # def testpage():
    #     chat_names = ['chat1 name', 'chat2 name', 'chat2 name']
    #     chats = [{'sender': "bot", 'message': "Hello! How can I help you today?", 'timestamp': "10-10-2024"},
    #              {'sender': "user", 'message': "Temp user message", 'timestamp': "10-10-2024"}]
    #     return render_template('test.html', chats=chat_names, messages=chats)

    return app, socketio


app, socketio = create_app()
if __name__ == '__main__':
    socketio.run(app, port=Config.PORT, host='0.0.0.0',
                 debug=True,
                 # ssl_context='adhoc'

                 ssl_context=('cert.pem', 'key.pem'))
