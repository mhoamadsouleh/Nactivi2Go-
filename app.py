from flask import Flask, request, render_template_string, redirect, url_for
import requests
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

DATA_FILE = 'djezzy_users.json'
CLIENT_ID = '6E6CwTkp8H1CyQxraPmcEJPQ7xka'
CLIENT_SECRET = 'MVpXHW_ImuMsxKIwrJpoVVMHjRsa'

def load_users():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

@app.route("/", methods=["GET", "POST"])
def index():
    error = ""
    if request.method == "POST":
        number = request.form.get("msisdn")
        if number and number.startswith("07") and len(number) == 10:
            msisdn = "213" + number[1:]
            users = load_users()

            # تحقق إذا الرقم مفعل من قبل خلال 7 أيام
            user = users.get(msisdn)
            if user:
                last_activation = datetime.fromisoformat(user['activated_at'])
                if datetime.now() - last_activation < timedelta(days=7):
                    return f"⏳ هذا الرقم مفعل بالفعل. يرجى الانتظار أسبوع. تم التفعيل يوم: {user['activated_at']}"

            # إرسال OTP
            success = send_otp(msisdn)
            if success:
                return redirect(url_for("verify", msisdn=msisdn))
            else:
                error = "❌ فشل في إرسال OTP."
        else:
            error = "⚠️ رقم غير صحيح. يرجى إدخال رقم يبدأ بـ 07 ويتكون من 10 أرقام."
    return render_template_string("""
        <h2>📲 أدخل رقمك لتفعيل Nactivi2Go:</h2>
        <form method="post">
            <input type="text" name="msisdn" placeholder="07XXXXXXXX" required>
            <button type="submit">💬 إرسال الرمز</button>
        </form>
        <p style="color: red;">{{ error }}</p>
        <a href="/users">📋 عرض قائمة الأرقام</a>
    """, error=error)

@app.route("/verify", methods=["GET", "POST"])
def verify():
    msisdn = request.args.get("msisdn")
    if not msisdn:
        return redirect(url_for("index"))

    if request.method == "POST":
        otp = request.form.get("otp")
        tokens = verify_otp(msisdn, otp)
        if tokens:
            users = load_users()
            now = datetime.now()
            users[msisdn] = {
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "activated_at": now.isoformat()
            }
            save_users(users)
            if activate_2go(msisdn, tokens["access_token"]):
                return f"✅ تم التفعيل لرقم {msisdn[-4:]} بنجاح!"
            else:
                return "⚠️ فشل التفعيل أو تم التفعيل مسبقاً."
        return "❌ رمز غير صحيح أو منتهي الصلاحية."
    
    return render_template_string("""
        <h2>💬 أدخل رمز Nactivi2Go:</h2>
        <form method="post">
            <input type="text" name="otp" placeholder="رمز التحقق" required>
            <button type="submit">✅ تحقق من الرمز</button>
        </form>
    """)

@app.route("/users")
def user_list():
    users = load_users()
    return render_template_string("""
        <h2>📋 قائمة الأرقام المسجلة</h2>
        <table border="1">
            <tr><th>رقم الهاتف</th><th>تاريخ التفعيل</th></tr>
            {% for msisdn, info in users.items() %}
            <tr>
                <td>{{ msisdn }}</td>
                <td>{{ info['activated_at'] }}</td>
            </tr>
            {% endfor %}
        </table>
        <a href="/">⬅️ رجوع</a>
    """, users=users)

def send_otp(msisdn):
    url = 'https://apim.djezzy.dz/oauth2/registration'
    data = f'msisdn={msisdn}&client_id={CLIENT_ID}&scope=smsotp'
    headers = {
        'User-Agent': 'Djezzy/2.6.7',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    res = requests.post(url, data=data, headers=headers)
    return res.status_code == 200

def verify_otp(msisdn, otp):
    url = 'https://apim.djezzy.dz/oauth2/token'
    data = f'otp={otp}&mobileNumber={msisdn}&scope=openid&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&grant_type=mobile'
    headers = {
        'User-Agent': 'Djezzy/2.6.7',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    res = requests.post(url, data=data, headers=headers)
    if res.status_code == 200:
        return res.json()
    return None

def activate_2go(msisdn, token):
    url = f"https://apim.djezzy.dz/djezzy-api/api/v1/subscribers/{msisdn}/subscription-product"
    payload = {
        "data": {
            "id": "GIFTWALKWIN",
            "type": "products",
            "meta": {
                "services": {
                    "steps": 10000,
                    "code": "GIFTWALKWIN2GO",
                    "id": "WALKWIN"
                }
            }
        }
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Djezzy/2.6.7",
        "Content-Type": "application/json"
    }
    res = requests.post(url, json=payload, headers=headers)
    return "successfully" in res.text

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
