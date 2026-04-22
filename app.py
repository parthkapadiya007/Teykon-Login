from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timedelta
import json
import os
import requests
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY


# ---------------- HELPERS ----------------

def get_ist_time():
    """Get current IST time (UTC + 5:30)"""
    utc_now = datetime.utcnow()
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    return ist_now

def today():
    return str(get_ist_time().date())


def load_data():
    try:
        # Get absolute path for PythonAnywhere
        base_dir = os.path.dirname(os.path.abspath(__file__))
        attendance_path = os.path.join(base_dir, "attendance.json")
        
        with open(attendance_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading attendance data: {e}")
        return {}


def save_data(data):
    try:
        # Get absolute path for PythonAnywhere
        base_dir = os.path.dirname(os.path.abspath(__file__))
        attendance_path = os.path.join(base_dir, "attendance.json")
        
        with open(attendance_path, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving attendance data: {e}")


def convert_to_12hour(time_str):
    if not time_str:
        return "--:--"
    
    try:
        # Parse time string (format: HH:MM:SS)
        dt = datetime.strptime(time_str, "%H:%M:%S")
        
        # Convert to 12-hour format
        hour = dt.hour
        minute = dt.minute
        second = dt.second
        
        # Determine AM/PM
        period = "AM" if hour < 12 else "PM"
        
        # Convert to 12-hour format
        hour_12 = hour % 12
        if hour_12 == 0:
            hour_12 = 12
        
        return f"{hour_12:02d}:{minute:02d}:{second:02d} {period}"
    except Exception as e:
        print(f"Time conversion error: {e} for time_str: {time_str}")
        return time_str  # Return original if conversion fails


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
    # Try multiple IP services for better reliability
    ip_services = [
        "https://api.ipify.org",
        "https://ipinfo.io/ip",
        "https://icanhazip.com",
        "https://checkip.amazonaws.com"
    ]
    
    for service in ip_services:
        try:
            response = requests.get(service, timeout=5)
            if response.status_code == 200:
                ip = response.text.strip()
                # Validate IP format
                parts = ip.split('.')
                if len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts):
                    print(f"Successfully got IP: {ip} from {service}")
                    return ip
        except Exception as e:
            print(f"Failed to get IP from {service}: {e}")
            continue
    
    print("All IP services failed, using fallback")
    return "0.0.0.0"


def office_only():
    return get_public_ip() == config.OFFICE_IP


# -------- GOOGLE SHEET SAVE --------

def send_to_google_sheet(user, action, ip):
    data = {
        "name": user,
        "action": action,
        "ip": ip,
        "timestamp": get_ist_time().strftime("%Y-%m-%d %H:%M:%S")
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


@app.route("/test-all")
def test_all():
    """Comprehensive test of all functionality"""
    print("=== COMPREHENSIVE TEST ===")
    
    test_results = {
        "time_conversion": {},
        "ip_fetching": {},
        "file_operations": {},
        "config_loading": {},
        "google_sheets": {}
    }
    
    # Test time conversion with multiple examples
    test_times = ["14:57:19", "09:30:00", "23:45:30", "12:00:00", "01:15:45"]
    time_results = []
    
    for test_time in test_times:
        converted = convert_to_12hour(test_time)
        time_results.append({
            "input": test_time,
            "output": converted,
            "success": converted != "--:--" and converted != test_time
        })
    
    test_results["time_conversion"] = {
        "tests": time_results,
        "all_success": all(t["success"] for t in time_results)
    }
    
    # Test IP fetching
    print("=== DEBUG CONFIG ===")
    
    debug_info = {
        "config_loaded": bool(hasattr(config, 'USERS')),
        "users_dict": getattr(config, 'USERS', 'NOT FOUND'),
        "secret_key": getattr(config, 'SECRET_KEY', 'NOT FOUND'),
        "office_ip": getattr(config, 'OFFICE_IP', 'NOT FOUND'),
        "google_url": getattr(config, 'GOOGLE_SCRIPT_URL', 'NOT FOUND'),
        "file_paths": {
            "attendance_exists": False,
            "attendance_readable": False,
            "config_exists": False
        }
    }
    
    # Check file paths with absolute paths
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        attendance_path = os.path.join(base_dir, "attendance.json")
        config_path = os.path.join(base_dir, "config.py")
        
        debug_info["file_paths"]["base_dir"] = base_dir
        debug_info["file_paths"]["attendance_path"] = attendance_path
        debug_info["file_paths"]["config_path"] = config_path
        debug_info["file_paths"]["attendance_exists"] = os.path.exists(attendance_path)
        debug_info["file_paths"]["attendance_readable"] = os.access(attendance_path, os.R_OK) if os.path.exists(attendance_path) else False
        debug_info["file_paths"]["config_exists"] = os.path.exists(config_path)
    except Exception as e:
        debug_info["file_paths"]["error"] = str(e)
    
    # Test user validation
    test_username = "Neha"
    test_password = "123"
    debug_info["test_login"] = {
        "username": test_username,
        "password": test_password,
        "user_exists": test_username in getattr(config, 'USERS', {}),
        "password_match": getattr(config, 'USERS', {}).get(test_username) == test_password
    }
    
    return f"""
    <h2>Debug Information</h2>
    <pre>{json.dumps(debug_info, indent=2)}</pre>
    <br>
    <a href='/'>Back to Login</a>
    """


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
    current_time = get_ist_time().strftime("%H:%M:%S")

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
    current_time = get_ist_time().strftime("%H:%M:%S")

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


# ---------------- DEBUG CURRENT TIME ----------------

@app.route("/debug-current-time")
def debug_current_time():
    """Debug current time and timezone issues"""
    print("=== DEBUG CURRENT TIME ===")
    
    import time
    
    # Get various time formats
    now_utc = datetime.utcnow()
    now_local = datetime.now()
    
    # Current time in different formats
    current_24hr = now_local.strftime("%H:%M:%S")
    current_12hr = convert_to_12hour(current_24hr)
    
    debug_info = {
        "server_info": {
            "utc_time": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "local_time": now_local.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": str(now_local.astimezone().tzinfo),
            "timestamp": time.time()
        },
        "time_display": {
            "24hr_format": current_24hr,
            "12hr_format": current_12hr,
            "date": now_local.strftime("%Y-%m-%d"),
            "hour": now_local.hour,
            "minute": now_local.minute,
            "second": now_local.second
        },
        "conversion_test": {
            "input": current_24hr,
            "output": current_12hr,
            "success": current_12hr != "--:--" and current_12hr != current_24hr
        }
    }
    
    # Test with attendance data
    data = load_data()
    sample_data = {}
    for user, user_data in data.items():
        for date, date_data in user_data.items():
            if "last_in" in date_data:
                sample_data[user] = {
                    "date": date,
                    "last_in": date_data["last_in"],
                    "last_in_converted": convert_to_12hour(date_data["last_in"]),
                    "last_out": date_data.get("last_out", "N/A"),
                    "last_out_converted": convert_to_12hour(date_data.get("last_out")) if date_data.get("last_out") else "N/A"
                }
            break
        if sample_data:
            break
    
    debug_info["attendance_data"] = sample_data
    
    return f"""
    <h2>Current Time Debug Information</h2>
    <h3>Server Time Information</h3>
    <pre>{json.dumps(debug_info["server_info"], indent=2)}</pre>
    
    <h3>Time Display</h3>
    <pre>{json.dumps(debug_info["time_display"], indent=2)}</pre>
    
    <h3>Conversion Test</h3>
    <pre>{json.dumps(debug_info["conversion_test"], indent=2)}</pre>
    
    <h3>Sample Attendance Data</h3>
    <pre>{json.dumps(debug_info["attendance_data"], indent=2)}</pre>
    
    <br><br>
    <a href='/'>Back to Login</a> | 
    <a href='/dashboard'>Dashboard</a>
    """


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)