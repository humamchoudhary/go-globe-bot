
## 📌 Prerequisites
Before setting up the project, ensure you have the following installed:
- Python (>= 3.8)
- virtualenv (recommended)
- Gunicorn (for production deployment)

---

## 🔧 Setup Guide
### 1️⃣ Clone the Repository
```bash
git clone https://github.com/your-repo/flask-app.git
cd flask-app
```

### 2️⃣ Create a Virtual Environment (Optional but Recommended)
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
venv\Scripts\activate    # On Windows
```

### 3️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```

### 4️⃣ Run Flask App (Development Mode)
```bash
python app.py
```
The application will start at: `http://127.0.0.1:5000`

---

## 🚀 Deploy with Gunicorn
### 5️⃣ Install Gunicorn
```bash
pip install gunicorn
```

### 6️⃣ Run the App with Gunicorn
```bash
gunicorn -k eventlet  -w 1 -b 0.0.0.0:8000 app:app
```
- `-b 0.0.0.0:8000` → Binds to port 8000 (change if required)

### 7️⃣ Run as a Background Service (Optional)
```bash
nohup gunicorn -k eventlet -w 1 -b 0.0.0.0:8000 app:app &
```

---

## 🛠 Troubleshooting
- If you get a `ModuleNotFoundError`, ensure you are in the correct virtual environment.
- Make sure no other process is running on port `8000`.

---

## 🎯 Next Steps
- Use **nginx** as a reverse proxy for production deployment.
- Configure **systemd** for automatic restarts.
- Set up **SSL** for secure communication.

---


