# FuelIQ — Smart Fueling System

A Flask-based fuel station management system with number plate detection (YOLOv8 + EasyOCR), prepaid wallet billing, PDF bill generation, and email delivery.

---

## Features

- Live camera / image upload number plate detection
- Fuzzy plate matching against prepaid wallet database
- One-click bill generation with auto wallet deduction
- PDF bill download + email delivery to customer
- Admin dashboard with transaction analytics
- User portal with wallet recharge and bill history

---

## Local Setup

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/fueliq.git
cd fueliq

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables (copy and fill in)
copy .env.example .env       # Windows
# cp .env.example .env       # Mac/Linux

# 5. Run
python app.py
```

Open `http://localhost:5000` — login with `admin / admin123`.

---

## Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask session secret (change in production) |
| `EMAIL_USER` | Gmail address to send bills from |
| `EMAIL_PASSWORD` | Gmail App Password (not your account password) |
| `SMTP_SERVER` | Default: `smtp.gmail.com` |
| `SMTP_PORT` | Default: `587` |

> To get a Gmail App Password: Google Account → Security → 2-Step Verification → App passwords

---

## Deploy to Render (free)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app --workers 2 --timeout 120`
5. Add environment variables in the Render dashboard
6. Deploy

> Note: YOLOv8 model weights (`*.pt`) are excluded from git. Either commit them separately, use Git LFS, or upload via Render's persistent disk.

---

## Deploy to Heroku

```bash
heroku create fueliq-app
heroku config:set SECRET_KEY=your_secret
heroku config:set EMAIL_USER=your@gmail.com
heroku config:set EMAIL_PASSWORD=your_app_password
git push heroku main
```

---

## Project Structure

```
fueliq/
├── app.py                  # Flask app + all routes
├── utils/
│   ├── ocr.py              # EasyOCR + Tesseract plate reader
│   ├── yolo_detect.py      # YOLOv8 plate detection
│   ├── wallet.py           # Wallet CRUD (CSV-backed)
│   └── email_sender.py     # PDF generation + email
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS, JS, images
├── datasets/               # Wallet CSV database
├── requirements.txt
├── Procfile                # Gunicorn start command
└── .env.example            # Environment variable template
```
