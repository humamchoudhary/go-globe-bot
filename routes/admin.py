import threading
from pprint import pprint
from services.usage_service import UsageService
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import requests
from .scrape import scrape_web
import re
import time
from flask import send_from_directory
import uuid
import os
from flask import render_template, session, request, jsonify, redirect, url_for, current_app, flash
from flask_socketio import join_room, leave_room, emit
import bcrypt
from functools import wraps
from . import admin_bp
from services.chat_service import ChatService
from services.user_service import UserService

from werkzeug.utils import secure_filename
import pdf2image



def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            # Store the original path in session
            session['next'] = request.path
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('admin/login.html')

    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    if username != current_app.config['ADMIN_USERNAME']:
        return jsonify({"error": "Invalid credentials"}), 401

    stored_hash = current_app.config['ADMIN_PASSWORD']
    if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
        return jsonify({"error": "Invalid credentials"}), 401

    session.clear()
    session['role'] = 'admin'

    # Redirect to the stored 'next' URL if available
    next_url = session.pop('next', None)
    if next_url:
        return jsonify({"status": "success", "redirect": next_url}), 200

    return jsonify({"status": "success"}), 200


@admin_bp.route('/chat/<room_id>', methods=['GET'])
@admin_required
def chat(room_id):

    chat_service = ChatService(current_app.db)

    chat = chat_service.get_chat_by_room_id(room_id)
    chats = chat_service.get_all_chats()

    chats_data = [c for c in chats if c.admin_required]
    if not chat:
        return redirect(url_for('admin.dashboard'))
    if request.headers.get('HX-Request'):
        return render_template('admin/fragments/chat_page.html', chat=chat, username="Anna")

    return render_template('admin/dashboard.html', chat=chat, chats=chats_data, username="Anna")


@admin_bp.route('/chat/min/<room_id>', methods=['GET'])
@admin_required
def chat_mini(room_id):

    chat_service = ChatService(current_app.db)

    chat = chat_service.get_chat_by_room_id(room_id)
    chats = chat_service.get_all_chats()

    # chats_data = [c for c in chats if c.admin_required]
    # if not chat:
    #     return redirect(url_for('admin.dashboard'))
    return render_template('admin/fragments/chat_mini.html', chat=chat, username="Anna")


@admin_bp.route('/user/<string:user_id>/details', methods=['GET'])
@admin_required
def get_user_details(user_id):

    user_service = UserService(current_app.db)
    user = user_service.get_user_by_id(user_id)

    return jsonify(user.to_dict())


@admin_bp.route('/chats/<string:filter>', methods=['GET'])
@admin_required
def filter_chats(filter):

    chat_service = ChatService(current_app.db)
    user_service = UserService(current_app.db)

    chats = chat_service.get_all_chats()

    if filter == "all":
        return render_template('admin/fragments/chat_list_container.html', chats=[{**chat.to_dict(), "username": user_service.get_user_by_id(chat.user_id).name} for chat in chats])
    elif filter == "active":
        return render_template('admin/fragments/chat_list_container.html', chats=[{**chat.to_dict(), "username": user_service.get_user_by_id(chat.user_id).name} for chat in chats if chat.admin_required])


@admin_bp.route('/chat/<room_id>/send_message', methods=['POST'])
@admin_required
def send_message(room_id):

    # if 'user_id' not in session:
    #     if request.headers.get('HX-Request'):
    #         return "Please log in first", 401
    #     return "<h1>Unauthorized</h1>", 401

    message = request.form.get('message')
    print(rf'{message}')
    print(f'{room_id}')
    if not message:
        return "", 302
    chat_service = ChatService(current_app.db)
    user_service = UserService(current_app.db)

    chat = chat_service.get_chat_by_room_id(room_id)
    if not chat:
        if request.headers.get('HX-Request'):
            return "Chat not found", 404
        return jsonify({"error": "Chat not found"}), 404

    new_message = chat_service.add_message(
        chat.room_id, "Anna", message)
    user = user_service.get_user_by_id(chat.user_id)
    if not user:
        return '<p>User Not Found</>'
    current_app.socketio.emit('new_message', {
        'sender': new_message.sender,
        'content': message,
        'timestamp': new_message.timestamp.isoformat()
    }, room=room_id)

    return render_template('admin/fragments/chat_message.html', message=new_message, username="Anna")


UPLOAD_FOLDER = os.path.join(os.getcwd(), 'files')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@admin_bp.route('/files/')
@admin_required
def files():
    return render_template('admin/files.html', files=sorted(os.listdir(UPLOAD_FOLDER)))


def is_readable_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None


@admin_bp.route('/files/<file_name>', methods=['GET'])
@admin_required
def file_page(file_name):
    file = {}
    file_readable = False
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if os.path.exists(file_path):
        file["filename"] = file_name
        # Get file extension
        file_ext = os.path.splitext(file_name)[1].lower()
        # Check if file is an image
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
            # If it's an image, we don't need to read its content
            # The template will display it as an image
            file_readable = False
        else:
            # Try to read the file content for non-image files
            file['content'] = is_readable_file(file_path)
            if file['content']:
                file_readable = True
    return render_template('admin/read_file.html', file=file, file_readable=file_readable)


@admin_bp.route('/files/delete/<file_name>', methods=['POST'])
@admin_required
def delete_file(file_name):
    try:
        file_path = os.path.join(UPLOAD_FOLDER, file_name)
        # Check if file exists before attempting to delete
        if os.path.exists(file_path):
            os.remove(file_path)
            flash('File deleted successfully', 'success')
        else:
            flash('File not found', 'error')
    except Exception as e:
        flash(f'Error deleting file: {str(e)}', 'error')

    # Redirect to the file list page
    # Assuming 'file_list' is your route for /file
    return redirect(url_for('admin.files'))


@admin_bp.route('/serve-file/<file_name>')
@admin_required
def serve_file(file_name):
    # Securely serve the file from the UPLOAD_FOLDER
    return send_from_directory(UPLOAD_FOLDER, file_name)


# @admin_bp.route('/add-admin', methods=['GET', 'POST'])
# @admin_required
# def add_admin():
#     if request.method == "GET":
#         return render_template('admin/add_admin.html')


@admin_bp.route("/upload", methods=["POST"])
@admin_required
def upload_file():
    if 'files' not in request.files:
        return jsonify({"error": "No files provided"}), 400

    uploaded_files = request.files.getlist("files")  # Get multiple files
    file_items = []

    for file in uploaded_files:
        if file.filename == '':
            continue

        original_filename = secure_filename(file.filename)
        base_filename = os.path.splitext(original_filename)[0]
        file_extension = os.path.splitext(original_filename)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

        if file_extension == '.pdf':
            try:
                temp_path = os.path.join(
                    UPLOAD_FOLDER, f"temp_{unique_filename}")
                file.save(temp_path)
                images = pdf2image.convert_from_path(temp_path)

                if images:
                    image_filenames = []
                    # Save each page as a separate image
                    for i, image in enumerate(images):
                        image_filename = f"{base_filename}_{i+1}.png"
                        image_path = os.path.join(
                            UPLOAD_FOLDER, image_filename)
                        image.save(image_path, 'PNG')
                        image_filenames.append(image_filename)
                        file_items.append(render_template(
                            "admin/fragments/file_item.html", file=image_filename))

                    os.remove(temp_path)
                else:
                    file.save(file_path)
                    file_items.append(render_template(
                        "admin/fragments/file_item.html", file=unique_filename))
            except Exception as e:
                file.seek(0)
                file.save(file_path)
                print(f"PDF conversion error: {e}")
                file_items.append(render_template(
                    "admin/fragments/file_item.html", file=unique_filename))
        else:
            file.save(file_path)
            file_items.append(render_template(
                "admin/fragments/file_item.html", file=unique_filename))

    return "".join(file_items), 200  # Return all file items as HTML


@admin_bp.route('/logout')
@admin_required
def logout():
    # session.pop('user', None)
    session.clear()
    return redirect(url_for('admin.login'))


@admin_bp.route('/')
@admin_required
def dashboard():

    chat_service = ChatService(current_app.db)
    chats = chat_service.get_all_chats()

    # Convert to dictionary representation
    chats_data = [chat for chat in chats if chat.admin_required]
    return render_template('admin/dashboard.html', chats=chats_data, username="Anna")


@admin_bp.route('/join/<room_id>')
@admin_required
def join_chat(room_id):
    chat_service = ChatService(current_app.db)
    chat = chat_service.get_chat_by_room_id(room_id)

    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    # Mark admin as present in this chat
    chat_service.set_admin_present(chat.chat_id, True)

    # Notify the room that admin has joined
    current_app.socketio.emit('admin_joined', {
        'message': 'Admin has joined the chat'
    }, room=room_id)

    return render_template('chat.html', room_id=room_id, is_admin=True)

# Socket.IO events for admin


@admin_bp.route('/settings', methods=['GET'])
@admin_required
def settings():

    config = dict(current_app.config)
    print(os.path.join(os.getcwd(),
          current_app.config['SETTINGS']['logo']['large'][1:]))
    config['SETTINGS']['logo']['large'] = current_app.config['SETTINGS']['logo']['large'] if os.path.exists(
        os.path.join(os.getcwd(), current_app.config['SETTINGS']['logo']['large'][1:])) else ''
    config['SETTINGS']['logo']['small'] = current_app.config['SETTINGS']['logo']['small'] if os.path.exists(
        os.path.join(os.getcwd(), current_app.config['SETTINGS']['logo']['small'][1:])) else ''
    print(config)
    return render_template('admin/settings.html', settings=config['SETTINGS'])


def save_settings(settings):
    session['settings'] = settings
    return True


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "txt", 'svg'}


def allowed_file(filename):
    """Check if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route('/update-logo/<file_name>', methods=['POST'])
@admin_required
def upload_logo(file_name):

    if "file" not in request.files:
        return "No file part", 400

    file = request.files["file"]
    if file.filename == "":
        return "No selected file", 400
    if file_name == 'logo.svg':
        f_type = 'large'
    elif file_name == 'logo-desktop-mini.svg':
        f_type = 'small'
    if file and allowed_file(file_name):
        # Prevent directory traversal attacks
        filename = secure_filename(file_name)
        file_path = os.path.join(current_app.config["LOGOS_FOLDER"], filename)
        file.save(file_path)
        current_app.config['SETTINGS']['logo'][f_type] = os.path.join(
            '/static', 'img', filename)
        # print(current_app.config)
        return f"File saved at {file_path}", 200

    return "Invalid file type", 400


@admin_bp.route('/settings/api/<api_type>', methods=['POST', 'DELETE'])
@admin_required
def api_key(api_type):
    if request.method == 'DELETE':
        current_app.config['SETTINGS']['apiKeys'][api_type] = ''

        print(current_app.config)
        return '', 200
    elif request.method == 'POST':
        # data = request.json
        current_app.config['SETTINGS']['apiKeys'][api_type] = request.form.get(
            "key")
        print(current_app.config)
        return '', 200
    return '', 500


@admin_bp.route('/settings/theme/<theme_type>', methods=['POST'])
@admin_required
def set_theme(theme_type):
    # data = request.json
    current_app.config['SETTINGS']['theme'] = theme_type
    return '', 200


@admin_bp.route('/settings/prompt', methods=['POST'])
@admin_required
def set_prompt():
    prpt = request.form.get('prompt')
    # ADD NEW SUBJECT
    current_app.config['SETTINGS']['prompt'] = prpt
    return '', 200


@admin_bp.route('/settings/subject', defaults={'subject': None}, methods=['POST'])
@admin_bp.route('/settings/subject/<string:subject>', methods=['DELETE'])
def subjects(subject):
    if request.method == 'POST':
        subject = request.form.get('subject')
        # ADD NEW SUBJECT
        current_app.config['SETTINGS']['subjects'].add(subject)
        return '', 200
    else:
        try:
            current_app.config['SETTINGS']['subjects'].remove(subject)
        except KeyError:
            pass
        return '', 200


def scrape_urls(urls):

    for url in urls:
        res = scrape_web(
            url,
            rotate_user_agents=True,
            random_delay=True
        )
        if res and 'text' in res:
            lines = str(res['text'])
            # print(lines)
            lines = re.sub(r"\s+", " ", lines).strip()
            # Create a filename from the URL
            if res['url'].endswith('/'):
                res['url'] = res['url'][:-1]
                print(res['url'])
            print(res['url'].endswith('/'))
            filename = '*'.join(res['url'].split('/')[2:])
            if not filename:
                # Use domain if path is empty
                filename = urlparse(res['url']).netloc
            filepath = f"{os.getcwd()}/files/{filename}.txt"
            with open(filepath, 'w') as f:
                # print(f"Saving content to {f.name}")
                # if len(lines) > 500:
                # print(lines)
                # print(filepath)
                f.write(lines)


@admin_bp.route('/scrape', methods=['POST'])
@admin_required
def scrape():
    urls = str(request.form.get('url')).rsplit()
    all_urls = []
    # Process each URL (could be a sitemap or regular page)
    for url in urls:
        # time.sleep(0.5)
        collected_urls = process_url(url)
        all_urls.extend(collected_urls)

    thread = threading.Thread(target=scrape_urls, args=(all_urls,))
    thread.start()
    # Now scrape all the collected URLs
    # pprint(all_urls)
    return '', 200


def process_url(url):
    """
    Process a URL which could be a sitemap or a regular page.
    Returns a list of URLs to scrape.
    """
    # First check if it's likely a sitemap based on URL pattern
    if is_likely_sitemap(url):
        return process_sitemap_url(url)
    return [url]  # Treat as regular URL if not a sitemap


def is_likely_sitemap(url):
    """
    Check if a URL is likely a sitemap without making a request.
    Returns True if URL ends with common sitemap extensions or contains 'sitemap' in path.
    """
    url_lower = url.lower()
    return (url_lower.endswith('.xml') or
            url_lower.endswith('.xml.gz') or
            'sitemap' in url_lower)


def process_sitemap_url(url):
    """
    Process a URL that's likely a sitemap.
    Returns a list of URLs found in the sitemap.
    """
    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            print(f"Failed to fetch {url}: Status code {response.status_code}")
            return [url]  # Return original URL if we can't process it

        content_type = response.headers.get('Content-Type', '').lower()
        content = response.text

        # Check if it's actually a sitemap (even if URL suggested it might be)
        if ('xml' in content_type or
            '<urlset' in content or
                '<sitemapindex' in content):
            return extract_urls_from_sitemap(content, url)

        # If URL suggested sitemap but content isn't, return original URL
        return [url]

    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
        return [url]  # Include the original URL if processing fails


def extract_urls_from_sitemap(sitemap_content, base_url):
    """
    Extract URLs from a sitemap, handling both regular sitemaps and sitemap indexes.
    Returns a list of URLs.
    """
    urls = []
    try:
        # Parse the XML
        root = ET.fromstring(sitemap_content)
        # Handle sitemap index (collection of sitemaps)
        if root.tag.endswith('sitemapindex'):
            # This is a sitemap index, we need to process each sitemap
            for sitemap in root.findall('.//{*}sitemap'):
                loc_elem = sitemap.find('.//{*}loc')
                if loc_elem is not None and loc_elem.text:
                    # Recursively process this sitemap
                    child_sitemap_url = loc_elem.text.strip()
                    print(f"Found child sitemap: {child_sitemap_url}")
                    child_urls = process_sitemap_url(child_sitemap_url)
                    urls.extend(child_urls)
        # Handle regular sitemap
        elif root.tag.endswith('urlset'):
            # This is a regular sitemap with URLs
            for url_elem in root.findall('.//{*}url'):
                loc_elem = url_elem.find('.//{*}loc')
                if loc_elem is not None and loc_elem.text:
                    page_url = loc_elem.text.strip()
                    urls.append(page_url)
    except Exception as e:
        print(f"Error parsing sitemap from {base_url}: {str(e)}")
        # Fall back to regex-based extraction if XML parsing fails
        urls.extend(re.findall(r'<loc>(.*?)</loc>', sitemap_content))
    # print(f"Extracted {len(urls)} URLs from sitemap")
    return urls


def get_latest_entry(period, collection):
    """Get the latest available entry for a given period (daily, monthly, yearly)."""
    latest = collection.find_one({"period": period}, sort=[("date", -1)])
    return latest["date"] if latest else None


def get_all_entry(period, collection):
    latest = collection.find({"period": period}, sort=[("date", -1)])
    return latest


@admin_bp.route('/usage/')
@admin_required
def usage():
    usage_service = UsageService(current_app.db)

    # Get all unique dates for each period
    daily_dates = list(usage_service.collection.distinct(
        "date", {"period": "daily"}))
    monthly_dates = list(usage_service.collection.distinct(
        "date", {"period": "monthly"}))
    yearly_dates = list(usage_service.collection.distinct(
        "date", {"period": "yearly"}))

    # Get the latest entries
    latest_daily = get_latest_entry("daily", usage_service.collection)
    latest_monthly = get_latest_entry("monthly", usage_service.collection)
    latest_yearly = get_latest_entry("yearly", usage_service.collection)

    return render_template("admin/usage.html",
                           latest_daily=latest_daily,
                           latest_monthly=latest_monthly,
                           latest_yearly=latest_yearly,
                           daily_dates=daily_dates,
                           monthly_dates=monthly_dates,
                           yearly_dates=yearly_dates)


@admin_bp.route('/api/usage/')
@admin_required
def api_usage():
    usage_service = UsageService(current_app.db)
    period = request.args.get("period", "daily")
    date = request.args.get("date", get_latest_entry(
        period, usage_service.collection))

    # Find the specific data point
    data = usage_service.collection.find_one({"period": period, "date": date})

    # If no data found, fall back to latest entry
    if not data:
        date = get_latest_entry(period, usage_service.collection)
        data = usage_service.collection.find_one(
            {"period": period, "date": date})

        if not data:
            return jsonify({"error": "No data found"}), 404

    return jsonify({
        "date": date,
        "cost": data["cost"],
        "input_tokens": data["input_tokens"],
        "output_tokens": data["output_tokens"]
    })

# @admin_bp.route('/chats')
# @admin_required
# def get_chats():
#     chat_service = ChatService(current_app.db)
#     chats = chat_service.get_all_chats()
#
#     # Convert to dictionary representation
#     chats_data = [chat.to_dict() for chat in chats if chat.admin_required]
#     return jsonify(chats_data)


@admin_bp.route('/chats', methods=['GET'])
# @admin_bp.route('/chats/<string:status>', methods=['GET'])
@admin_required
def get_all_chats():

    chat_service = ChatService(current_app.db)
    chats_objs = chat_service.get_all_chats()
    user_service = UserService(current_app.db)
    chats = []
    for c in chats_objs:
        chat = c.to_dict()
        chat['username'] = user_service.get_user_by_id(c.user_id).name
        chats.append(chat)

    # Convert to dictionary representation
    pprint(chats)
    # = [chat.to_dict() for chat in chats if chat.admin_required]
    return render_template('admin/chats.html', chats=chats)


def register_admin_socketio_events(socketio):
    @socketio.on('admin_join')
    def on_admin_join(data):
        if session.get('role') != 'admin':
            print('ret')
            return

        room = data.get('room')
        if not room:
            return

        join_room(room)
        join_room('admin')  # Join the admin room for broadcasts
        print('admin joined')
        emit('status', {'msg': 'Admin has joined the room.'}, room=room)
