from flask import Flask, render_template, request, redirect, session
from datetime import datetime
import json
import requests
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY


# ---------------- HELPERS ----------------

def today():
    return str(datetime.now().date())


def load_data():
    try:
        with open("attendance.json", "r") as f:
            return json.load(f)
    except:
        return {}


def save_data(data):
    with open("attendance.json", "w") as f:
        json.dump(data, f, indent=4)


def convert_to_12hour(time_str):
    if not time_str:
        return "--:--"
    
    try:
        # Parse time string (format: HH:MM:SS)
        dt = datetime.strptime(time_str, "%H:%M:%S")
        
        # Convert to 12-hour format
        hour = dt.hour
        minute = dt.minute
        
        # Determine AM/PM
        period = "AM" if hour < 12 else "PM"
        
        # Convert to 12-hour format
        hour_12 = hour % 12
        if hour_12 == 0:
            hour_12 = 12
        
        return f"{hour_12:02d}:{minute:02d} {period}"
    except:
        return "--:--"


def calculate_working_hours(in_time, out_time):
    if not in_time or not out_time:
        return "--:--"
    
    try:
        # Parse time strings (format: HH:MM:SS)
        in_dt = datetime.strptime(in_time, "%H:%M:%S")
        out_dt = datetime.strptime(out_time, "%H:%M:%S")
        
        # Calculate difference
        diff = out_dt - in_dt
        
        # Convert to total seconds
        total_seconds = diff.total_seconds()
        
        # Calculate hours and minutes
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        
        return f"{hours:02d}:{minutes:02d}"
    except:
        return "--:--"


# -------- PUBLIC IP CHECK (OFFICE WIFI LOCK) --------

def get_public_ip():
    try:
        return requests.get("https://api.ipify.org").text
    except:
        return "0.0.0.0"


def office_only():
    return get_public_ip() == config.OFFICE_IP


# -------- GOOGLE SHEET SAVE --------

def send_to_google_sheet(user, action, ip):
    data = {
        "name": user,
        "action": action,
        "ip": ip,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    print(f"=== GOOGLE SHEET DEBUG ===")
    print(f"Sending data: {data}")
    print(f"URL: {config.GOOGLE_SCRIPT_URL}")

    try:
        # Try with different content types
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'text/plain'
        }
        
        response = requests.post(
            config.GOOGLE_SCRIPT_URL, 
            json=data,
            timeout=20,
            headers=headers
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200 and "Success" in response.text:
            print("Google Sheet Success!")
            return True
        else:
            print(f"Google Sheet Issue - Status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Google Sheet Error: {e}")
        return False


def doPost():
    print("doPost function called")


@app.route("/test-google-sheet")
def test_google_sheet():
    """Test route to debug Google Sheets integration"""
    if "user" not in session:
        return redirect("/")
    
    user = session["user"]
    ip = get_public_ip()
    
    print("=== Testing Google Sheet Integration ===")
    result = send_to_google_sheet(user, "TEST", ip)
    print(f"Test Result: {result}")
    
    # Try direct URL test
    try:
        response = requests.get(config.GOOGLE_SCRIPT_URL, timeout=5)
        get_result = f"GET Test: {response.status_code} - {response.text}"
        print(get_result)
    except Exception as e:
        get_result = f"GET Test Error: {e}"
        print(get_result)
    
    return f"""
    <h2>Google Sheet Test Result</h2>
    <p><strong>Main Test:</strong> {'SUCCESS' if result else 'FAILED'}</p>
    <p><strong>URL Test:</strong> {get_result}</p>
    <p><strong>URL:</strong> {config.GOOGLE_SCRIPT_URL}</p>
    <p><strong>User:</strong> {user}</p>
    <p><strong>IP:</strong> {ip}</p>
    <p><br>Check console for detailed logs</p>
    <p><a href='/dashboard'>Back to Dashboard</a></p>
    """


@app.route("/simple-test")
def simple_test():
    """Simple test without login"""
    print("=== Simple Test ===")
    result = send_to_google_sheet("TestUser", "TEST", "127.0.0.1")
    return f"Simple Test Result: {'SUCCESS' if result else 'FAILED'}"


# ---------------- LOGIN ----------------

@app.route("/", methods=["GET", "POST"])
def login():


    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        
        print(f"Login attempt: {username}")

        if username in config.USERS and config.USERS[username] == password:
            session["user"] = username
            print(f"Login successful for: {username}")
            return redirect("/dashboard")
        else:
            print(f"Login failed for: {username}")
            return render_template("login.html", error="Invalid Username or Password")

    return render_template("login.html", error=None)


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/")

    user = session["user"]
    data = load_data()

    today_data = data.get(user, {}).get(today(), {})

    # Calculate working hours and convert times to 12-hour format
    intime = today_data.get("last_in")
    outtime = today_data.get("last_out")
    working_hours = calculate_working_hours(intime, outtime)
    
    # Convert times to 12-hour format for display
    intime_12hr = convert_to_12hour(intime)
    outtime_12hr = convert_to_12hour(outtime)
    
    return render_template(
        "dashboard.html",
        user=user,
        today_date=today(),
        intime=intime_12hr,
        outtime=outtime_12hr,
        working_hours=working_hours,
        in_times=today_data.get("in_times", []),
        out_times=today_data.get("out_times", [])
    )


# ---------------- IN TIME ----------------

@app.route("/in")
def mark_in():

    if "user" not in session:
        return redirect("/")

    user = session["user"]
    ip = get_public_ip()
    current_time = datetime.now().strftime("%H:%M:%S")

    data = load_data()

    data.setdefault(user, {})
    data[user].setdefault(today(), {})
    
    # Allow multiple IN entries - store as list
    if "in_times" not in data[user][today()]:
        data[user][today()]["in_times"] = []
    
    data[user][today()]["in_times"].append(current_time)
    data[user][today()]["last_in"] = current_time

    send_to_google_sheet(user, "IN", ip)

    save_data(data)

    return redirect("/dashboard")


# ---------------- OUT TIME ----------------

@app.route("/out")
def mark_out():

    if "user" not in session:
        return redirect("/")

    user = session["user"]
    ip = get_public_ip()
    current_time = datetime.now().strftime("%H:%M:%S")

    data = load_data()

    data.setdefault(user, {})
    data[user].setdefault(today(), {})
    
    # Allow multiple OUT entries - store as list
    if "out_times" not in data[user][today()]:
        data[user][today()]["out_times"] = []
    
    data[user][today()]["out_times"].append(current_time)
    data[user][today()]["last_out"] = current_time

    send_to_google_sheet(user, "OUT", ip)

    save_data(data)

    return redirect("/dashboard")


# ---------------- LOGOUT ----------------

@app.route("/logout", methods=["GET", "POST"])
def logout():
    print("=== LOGOUT DEBUG ===")
    print(f"Before logout - Session data: {dict(session)}")
    
    session.clear()
    
    print(f"After logout - Session cleared: {dict(session)}")
    print("Redirecting to login page...")
    
    return redirect("/")


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)