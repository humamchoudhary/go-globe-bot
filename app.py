from datetime import timedelta
from flask import Flask, session, url_for, jsonify, Response

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


def get_font_data():
    # Path to your font directory
    font_dir = os.path.join(
        app.static_folder, 'font/Proxima Nova Complete Collection')

    # Find all font files
    font_files = []
    for ext in ['ttf', 'otf', 'woff', 'woff2']:
        font_files.extend(glob.glob(os.path.join(font_dir, f'*.{ext}')))

    # Extract just the filenames
    font_files = [os.path.basename(f) for f in font_files]

    return font_files


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

    app.config['SESSION_TYPE'] = 'mongodb'
    app.config['LOGOS_FOLDER'] = os.path.join(os.getcwd(), 'static/img/')

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

    @app.before_request
    def test():
        print(request.headers.get("X-Real-IP"))

    conf = db.config.find_one({"id": "settings"})
    if conf:
        app.config['SETTINGS'] = conf
        app.config['SETTINGS']["apiKeys"] = {
            'claude': os.environ.get('CLAUDE_KEY', ''),
            'openAi': os.environ.get('OPENAI_KEY', ''),
            'gemini': os.environ.get('GEMINI_KEY', '')}
    else:
        app.config['SETTINGS'] = {
            'logo': {
                'large': '/static/img/logo.svg',
                'small':
                '/static/img/logo-desktop-mini.svg',
            },
            'subjects': set({'Services', 'Products', 'Enquire', 'Others'}),
            'apiKeys': {
                'claude': os.environ.get('CLAUDE_KEY', ''),
                'openAi': os.environ.get('OPENAI_KEY', ''),
                'gemini': os.environ.get('GEMINI_KEY', '')},
            'theme': 'system',
            'model': 'gemini', 'backend_url': os.environ.get('BACKEND_URL'), "prompt": f"""
       you are a customer service assistant. Your role is to provide information and assistance based solely on the data provided. Do not generate information from external sources. If the user asks about something not covered in the provided data, respond with: 'I cannot assist with that. Please click the "Request Assistance" button for human assistance.'
                Incorporate information from any attached images into your responses where relevant. Give concise answers
                When referencing specific files or pages, include a link at the end of your response. Construct the link by replacing any '*' characters in the filename with '/', and removing the '.txt' extension. The link text should be the generated link itself.
                Example: If the filename is 'www.example.com*details.php.txt', the link should be 'https://www.example.com/details.php' ie just removin the .txt from the end and the link text should also be 'product/details'.
                USE VALID MARKUP TEXT, Have proper Formating for links
DON'T HALLUCINATE AND GIVE SMALL RESPONSES DONT EXPLAIN EVERYTHING ONLY THE THING USER ASKS TO EXPLAIN
                """
        }

    @app.context_processor
    def settings():
        app.config['SETTINGS']['subjects'] = list(
            app.config['SETTINGS']['subjects'])

        db.config.replace_one({"id": "settings"},
                              {"id": "settings", **app.config['SETTINGS'], "apiKeys": "removed"}, upsert=True)
        app.config['SETTINGS']['subjects'] = sorted(
            app.config['SETTINGS']['subjects'], key=len, reverse=True)
        return {'settings': app.config['SETTINGS']}
    app.bot = Bot(Config.BOT_NAME, app=app)

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
        print(f"Using default admin password: {default_pwd}")

    def has_no_empty_params(rule):
        defaults = rule.defaults if rule.defaults is not None else ()
        arguments = rule.arguments if rule.arguments is not None else ()
        return len(defaults) >= len(arguments)

    @app.context_processor
    def inject_font_data():
        print('fonts called')
        return {'font_files': get_font_data()}

    @app.route('/init-bot')
    def init_chatbot():

        return Response(render_template('js/init_chatbox.js', backend_url=app.config['SETTINGS']['backend_url']), mimetype='application/javascript')

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
    socketio.run(app, port=5000, host='0.0.0.0',
                 debug=True,
                 ssl_context='adhoc'
                 )
