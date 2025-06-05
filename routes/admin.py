from datetime import datetime, timedelta
from collections import defaultdict, Counter
from services.timezone import UTCZoneManager
import threading
from pprint import pprint
from services.usage_service import UsageService
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import requests
from .scrape import scrape_web
import re
from flask import send_from_directory
import uuid
import os
from flask import render_template, session, request, jsonify, redirect, url_for, current_app, flash
from flask_socketio import join_room,  emit
import bcrypt
from functools import wraps
from . import admin_bp
from services.chat_service import ChatService
from services.user_service import UserService
from werkzeug.utils import secure_filename
import pdf2image
from services.logs_service import LogsService

from datetime import datetime
from models.log import LogLevel, LogTag


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            # Store the original path in session
            session['next'] = request.path
            print(request.path)
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/pricing/')
@admin_required
def pricing_page():
    return render_template('admin/pricing.html')


@admin_bp.route('/faq/')
@admin_required
def faq_page():
    return render_template('admin/faq.html')


@admin_bp.route('/change-logs')
@admin_required
def changelogs_page():
    return render_template('admin/change-logs.html')


@admin_bp.route('/logs/')
@admin_required
def view_logs():
    """Main logs page"""
    logs_service = LogsService(current_app.db)
    logs = logs_service.get_recent_logs(10000)
    return render_template('admin/logs.html', logs=logs, selected_log=None)


@admin_bp.route('/logs/filter')
@admin_required
def filter_logs():
    """Filter logs with HTMX"""
    logs_service = LogsService(current_app.db)

    # Get filter parameters
    levels = request.args.getlist('level')  # Multiple levels
    tags = request.args.getlist('tag')      # Multiple tags
    user_id = request.args.get('user_id', '').strip()
    admin_id = request.args.get('admin_id', '').strip()
    message_search = request.args.get(
        'message_search', '').strip()  # New message filter
    sort_order = request.args.get('sort', 'timestamp_desc')
    limit = request.args.get('limit', None)

    # Parse dates
    start_date = None
    end_date = None
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()

    try:
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str)
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str)
    except ValueError:
        pass  # Invalid date format, ignore

    # Convert levels and tags to enums if provided
    level_enums = []
    tag_enums = []

    for level in levels:
        try:
            if level:
                level_enums.append(LogLevel(level))
        except ValueError:
            pass

    for tag in tags:
        try:
            if tag:
                tag_enums.append(LogTag(tag))
        except ValueError:
            pass

    # Search with filters
    logs = logs_service.search_logs_advanced(
        levels=level_enums if level_enums else None,
        tags=tag_enums if tag_enums else None,
        user_id=user_id if user_id else None,
        admin_id=admin_id if admin_id else None,
        message_search=message_search if message_search else None,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )

    # Apply sorting
    if sort_order == 'timestamp_asc':
        logs.sort(key=lambda x: x.timestamp)
    elif sort_order == 'level_desc':
        level_priority = {'CRITICAL': 5, 'ERROR': 4,
                          'WARNING': 3, 'INFO': 2, 'DEBUG': 1}
        logs.sort(key=lambda x: level_priority.get(
            x.level.value, 0), reverse=True)
    elif sort_order == 'level_asc':
        level_priority = {'CRITICAL': 5, 'ERROR': 4,
                          'WARNING': 3, 'INFO': 2, 'DEBUG': 1}
        logs.sort(key=lambda x: level_priority.get(x.level.value, 0))
    # timestamp_desc is default (already sorted by service)

    return render_template('admin/logs_table.html', logs=logs)


@admin_bp.route('/log/<string:log_id>')
@admin_required
def view_log_detail(log_id):
    """View individual log details"""
    logs_service = LogsService(current_app.db)
    log = logs_service.get_log_by_id(log_id)

    if not log:
        if request.headers.get('HX-Request') == 'true':
            return '<div class="p-4 text-red-500">Log not found</div>', 404
        else:
            return "Log not found", 404

    # Check if it's an HTMX request
    if request.headers.get('HX-Request') == 'true':
        return render_template('admin/log_detail.html', log=log)
    else:
        # Full page load - redirect to logs page with detail
        logs_service = LogsService(current_app.db)
        logs = logs_service.get_recent_logs(limit=100)
        return render_template('admin/logs.html', logs=logs, selected_log=log)


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

    # Redirect to the stored 'next' URL if available

    next_url = session.pop('next', None)
    print(f"NEXT: {next_url}")
    session.clear()
    session['role'] = 'admin'
    if next_url:
        # return redirect(next_url)
        return jsonify({"status": "success", "redirect": next_url}), 200

    return jsonify({"status": "success"}), 200


@admin_bp.route('/chat/<room_id>', methods=['GET'])
@admin_required
def chat(room_id):

    chat_service = ChatService(current_app.db)

    user_service = UserService(current_app.db)
    chat = chat_service.get_chat_by_room_id(room_id)
    if not chat:
        return redirect(url_for('admin.get_all_chats'))
    chats = chat_service.get_all_chats()

    # chats_data = [c for c in chats]
    chats_data = []
    for c in chats:
        data = c.to_dict()
        data['username'] = user_service.get_user_by_id(c.user_id).name
        chats_data.append(data)
    user = user_service.get_user_by_id(chat.user_id)
    if not chat:
        return redirect(url_for('admin.index'))
    if request.headers.get('HX-Request'):
        return render_template('components/chat-area.html', chat=chat, user=user, username="Ana")

    return render_template('admin/chats.html', chat=chat, chats=chats_data, user=user, username="Ana")


@admin_bp.route('/search/', methods=["POST"])
@admin_required
def search():
    search = request.form.get('search-q')

    chat_service = ChatService(current_app.db)
    chats = chat_service.get_all_chats()

    user_service = UserService(current_app.db)
    search_chats = set()
    for chat in chats:
        user = user_service.get_user_by_id(chat.user_id)
        chat.username = user.name

        if search in user.name or (user.country and search in user.country) or (user.city and search in user.city):
            search_chats.add(chat)
            continue
        for message in chat.messages:
            if search in message.content:
                search_chats.add(chat)
                break

    return render_template('components/search-results.html', search_chats=list(search_chats))


@admin_bp.route('/chat/<room_id>/user')
def chat_user(room_id):
    chat_service = ChatService(current_app.db)

    user_service = UserService(current_app.db)
    user = user_service.get_user_by_id(
        chat_service.get_chat_by_room_id(room_id).user_id)

    return render_template("admin/user.html", user=user.to_dict())
    # with current_app.test_client() as client:
    #     response = client.get('/internal-data')
    #     data = response.get_json()
    #     pass


@admin_bp.route('/chat/min/<room_id>', methods=['GET'])
@admin_required
def chat_mini(room_id):

    chat_service = ChatService(current_app.db)

    chat = chat_service.get_chat_by_room_id(room_id)
    chats = chat_service.get_all_chats()

    # chats_data = [c for c in chats if c.admin_required]
    # if not chat:
    #     return redirect(url_for('admin.index'))
    return render_template('admin/fragments/chat_mini.html', chat=chat, username="Ana")


@admin_bp.route('/user/<string:user_id>/details', methods=['GET'])
@admin_required
def get_user_details(user_id):

    user_service = UserService(current_app.db)
    user = user_service.get_user_by_id(user_id)
    if request.headers.get('HX-Request'):
        return render_template('components/chat-user-info.html', user=user)

    return jsonify(user.to_dict())


@admin_bp.route('/chats/<string:filter>', methods=['GET'])
@admin_required
def filter_chats(filter):

    chat_service = ChatService(current_app.db)
    user_service = UserService(current_app.db)

    chats = chat_service.get_all_chats()

    if filter == "all":
        return render_template('components/chat-list.html', chats=[{**chat.to_dict(), "username": user_service.get_user_by_id(chat.user_id).name} for chat in chats])
    elif filter == "active":
        return render_template('components/chat-list.html', chats=[{**chat.to_dict(), "username": user_service.get_user_by_id(chat.user_id).name} for chat in chats if chat.admin_required])


@admin_bp.route('/chat/<room_id>/send_message', methods=['POST'])
@admin_required
def send_message(room_id):
    try:
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
            chat.room_id, "Ana", message)
        user = user_service.get_user_by_id(chat.user_id)
        if not user:
            return '<p>User Not Found</>'
        current_app.socketio.emit('new_message', {
            'sender': new_message.sender,
            'content': message,
            'timestamp': new_message.timestamp.isoformat()
        }, room=room_id)

        # return render_template('admin/fragments/chat_message.html', message=new_message, username="Ana")
        return "", 200
    except Exception as e:
        print(e)


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


def generate_stats(chat_list):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    year_start = now.replace(month=1, day=1, hour=0,
                             minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0,
                              second=0, microsecond=0)  # <-- this-month start

    # Containers
    today_hourly = Counter()
    today_admin_hourly = Counter()

    week_daily = Counter()
    week_admin_daily = Counter()

    month_daily = Counter()          # <-- this-month counters
    month_admin_daily = Counter()

    year_monthly = Counter()
    year_admin_monthly = Counter()

    all_time_yearly = Counter()
    all_time_admin_yearly = Counter()

    for chat in chat_list:
        created = chat.created_at

        # === TODAY (hourly) ===
        if created >= today_start:
            hour_label = created.strftime("%H:00")
            today_hourly[hour_label] += 1
            if chat.admin_required:
                today_admin_hourly[hour_label] += 1

        # === THIS WEEK (daily) ===
        if created >= week_start:
            day_label = created.strftime("%A")
            week_daily[day_label] += 1
            if chat.admin_required:
                week_admin_daily[day_label] += 1

        # === THIS MONTH (daily) ===
        if created >= month_start:
            day_label = created.day  # integer day of month
            month_daily[day_label] += 1
            if chat.admin_required:
                month_admin_daily[day_label] += 1

        # === THIS YEAR (monthly) ===
        if created >= year_start:
            month_label = created.strftime("%b")
            year_monthly[month_label] += 1
            if chat.admin_required:
                year_admin_monthly[month_label] += 1

        # === ALL TIME (yearly) ===
        year_label = created.strftime("%Y")
        all_time_yearly[year_label] += 1
        if chat.admin_required:
            all_time_admin_yearly[year_label] += 1

    # Fill missing labels for consistency
    full_hours = [f"{str(h).zfill(2)}:00" for h in range(24)]
    full_days = ['Monday', 'Tuesday', 'Wednesday',
                 'Thursday', 'Friday', 'Saturday', 'Sunday']
    full_months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # Get number of days in current month (handles month length)
    import calendar
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    full_days_in_month = list(range(1, days_in_month + 1))

    return {
        'today': {
            'labels': full_hours,
            'totalChats': [today_hourly[h] for h in full_hours],
            'adminRequired': [today_admin_hourly[h] for h in full_hours]
        },
        'this-week': {
            'labels': full_days,
            'totalChats': [week_daily[d] for d in full_days],
            'adminRequired': [week_admin_daily[d] for d in full_days]
        },
        'this-month': {                                   # <-- added this-month
            'labels': full_days_in_month,
            'totalChats': [month_daily[d] for d in full_days_in_month],
            'adminRequired': [month_admin_daily[d] for d in full_days_in_month]
        },
        'this-year': {
            'labels': full_months,
            'totalChats': [year_monthly[m] for m in full_months],
            'adminRequired': [year_admin_monthly[m] for m in full_months]
        },
        'all-time': {
            'labels': sorted(all_time_yearly.keys()),
            'totalChats': [all_time_yearly[y] for y in sorted(all_time_yearly.keys())],
            'adminRequired': [all_time_admin_yearly[y] for y in sorted(all_time_admin_yearly.keys())]
        }
    }


@admin_bp.route('/')
@admin_required
def index():

    chat_service = ChatService(current_app.db)

    user_service = UserService(current_app.db)
    all_users = user_service.get_all_users()
    chats = chat_service.get_all_chats()

    chats_ary = []
    x = 0
    for c in chats:
        print(x)
        x += 1
        print(c)
        chat = c.to_dict()
        chat['username'] = user_service.get_user_by_id(c.user_id).name
        chats_ary.append(chat)

    data = generate_stats(chats)
    pprint(chats_ary)

    return render_template('admin/index.html', chats=chats_ary, data=data, username="Ana", online_users=current_app.config['ONLINE_USERS'], all_users=len(all_users))


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

    # Validate logo paths
    config['SETTINGS']['logo']['large'] = (
        current_app.config['SETTINGS']['logo']['large']
        if os.path.exists(os.path.join(os.getcwd(), current_app.config['SETTINGS']['logo']['large'][1:]))
        else ''
    )
    config['SETTINGS']['logo']['small'] = (
        current_app.config['SETTINGS']['logo']['small']
        if os.path.exists(os.path.join(os.getcwd(), current_app.config['SETTINGS']['logo']['small'][1:]))
        else ''
    )

    # Define day order and sort timings without converting timezones
    day_order = {'monday': 0, 'tuesday': 1, 'wednesday': 2,
                 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}

    if current_app.config['SETTINGS'].get('timings'):
        config['SETTINGS']['timings'] = sorted(
            current_app.config['SETTINGS']['timings'],
            key=lambda time: day_order[time['day']]
        )

    return render_template('admin/settings.html', settings=config['SETTINGS'], tzs=UTCZoneManager.get_timezones())


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


@admin_bp.route('/settings/timing', methods=['POST'])
def add_timing():
    day = request.form.get('meetingDay')
    start_time = request.form.get('startTime')  # Expected format: "HH:MM"
    end_time = request.form.get('endTime')
    timezone = request.form.get('timezone')

    # Just store the received times directly
    timings = current_app.config['SETTINGS'].get('timings', [])

    # Remove existing entry for that day
    timings = [t for t in timings if t['day'] != day]

    # Add new timing entry as-is
    timings.append({
        "day": day,
        "startTime": start_time,
        "endTime": end_time
    })

    # Sort by weekday
    current_app.config['SETTINGS']['timezone'] = timezone
    day_order = {'monday': 0, 'tuesday': 1, 'wednesday': 2,
                 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
    timings.sort(key=lambda t: day_order[t['day']])

    current_app.config['SETTINGS']['timings'] = timings

    return "added", 200


@admin_bp.route('/settings/timing/<int:id>', methods=['DELETE'])
def delete_timing(id):
    print(id)
    timings = current_app.config['SETTINGS'].get('timings', [])
    day_order = {'monday': 0, 'tuesday': 1, 'wednesday': 2,
                 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
    timings = sorted(timings, key=lambda time: day_order[time["day"]])
    timings.pop(id)

    current_app.config['SETTINGS']['timings'] = timings
    return "delete", 200


@admin_bp.route('/settings/model/', methods=['POST'])
def update_model():
    model = request.form.get('model')
    current_app.config['SETTINGS']['model'] = model

    current_app.bot._set_bot(model)
    return "", 200


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
        print("SUBJECT")
        print(current_app.config['SETTINGS']['subjects'])
        subject = request.form.get('subject')
        # ADD NEW SUBJECT
        current_app.config['SETTINGS']['subjects'] = set(
            current_app.config['SETTINGS']['subjects'])

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


@admin_bp.route('/chats/', methods=['GET'])
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


@admin_bp.route("/chat/<string:room_id>/delete", methods=["POST"])
def delete_chat(room_id):

    try:
        chat_service = ChatService(current_app.db)
        chat_service.delete([room_id])
        return "", 200
    except Exception as e:
        print(e)
        return "Error"
    # for i in chats:
    #     print(i)


@admin_bp.route("/chats/delete", methods=["POST"])
def delete_chats():

    data = request.get_json()
    if not data.get("chat_ids"):
        return "", 200
    chats = data["chat_ids"]
    print(chats)
    try:
        chat_service = ChatService(current_app.db)
        chat_service.delete(chats)
        return "", 200
    except Exception as e:
        print(e)
        return "Error"
    # for i in chats:
    #     print(i)


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
