from datetime import datetime
from winsound import Beep

import os
import sys
import time
import ctypes
import subprocess
import json
import atexit

RULE_PREFIX = "LunarBypass_"
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "log_path": r"%USERPROFILE%\.lunarclient\logs\launcher\main.log",
    "pattern_first": "[Launch] Spawning JVM process with following configuration...",
    "pattern_second": "[Launch] Starting log file polling",
    "lunar_path": r"%LOCALAPPDATA%\Programs\Lunar Client\Lunar Client.exe",
    "lunar_jre_base": r"%USERPROFILE%\.lunarclient\jre"
}


def expand_path(path):
    return os.path.normpath(os.path.expandvars(path))


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    else:
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def relaunch_as_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{sys.argv[0]}"', None, 1)
    sys.exit(0)


def print_firewall_log(action, rule_name, status="success"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{action}]: {rule_name} | {status}")


def firewall_rule_exists(rule_name):
    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"],
            capture_output=True, text=True
        )
        return "Rule Name:" in result.stdout
    except:
        return False


def manage_firewall_rule(app_path, action):
    if not app_path or not os.path.exists(app_path):
        print_firewall_log("ERROR", "N/A", "invalid path")
        return False

    app_name = os.path.basename(app_path)
    rule_name = f"{RULE_PREFIX}{app_name}"

    existed_before = firewall_rule_exists(rule_name)

    if action == "unblock" or existed_before:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print_firewall_log("DELETE", rule_name)
        else:
            print_firewall_log("DELETE", rule_name, f"error: {result.stderr.strip()}")

    if action == "block":
        cmd = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={rule_name}",
            "dir=out",
            "action=block",
            f"program={app_path}",
            "enable=yes",
            "profile=any"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print_firewall_log("CREATE", rule_name)
            return True
        else:
            print_firewall_log("CREATE", rule_name, f"error: {result.stderr.strip()}")
            return False
    return True


def cleanup_firewall_rules():
    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
            capture_output=True, text=True
        )

        rules = []
        for line in result.stdout.splitlines():
            if RULE_PREFIX in line and "Rule Name:" in line:
                rule_name = line.split(":")[1].strip()
                rules.append(rule_name)

        for rule_name in rules:
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print_firewall_log("CLEANUP", rule_name)
            else:
                print_firewall_log("CLEANUP", rule_name, f"error: {result.stderr.strip()}")

    except Exception as e:
        print_firewall_log("CLEANUP", "ALL", f"exception: {str(e)}")


def find_java_in_lunar(jre_base):
    jre_path = expand_path(jre_base)
    if not os.path.exists(jre_path):
        return None

    for root, _, files in os.walk(jre_path):
        if "javaw.exe" in files:
            return os.path.join(root, "javaw.exe")
    return None


def monitor_log(file_path, trigger):
    file_path = expand_path(file_path)
    while not os.path.exists(file_path):
        time.sleep(0.5)

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line and trigger in line:
                return True
            time.sleep(0.1)


def main():
    atexit.register(cleanup_firewall_rules)
    try:
        print("Lunar-Bypass | dev: empathy (https://github.com/lxngren)")
        print("Version: 1.2, Language: English")

        if not is_admin():
            relaunch_as_admin()

        config = load_config()

        log_path = config["log_path"]
        pattern_first = config["pattern_first"]
        pattern_second = config["pattern_second"]
        lunar_path = expand_path(config["lunar_path"])
        lunar_jre_base = config["lunar_jre_base"]

        java_path = find_java_in_lunar(lunar_jre_base)

        if not os.path.exists(lunar_path):
            print(f"[WARN] Lunar Client not found: {lunar_path}")
            return

        if not java_path:
            java_path = input("[WARN] Java not found. Enter the path to [lunar] javaw.exe: ").strip('"')
            if not os.path.exists(java_path):
                print(f"[ERROR]: Path doesn't exist: {java_path}")
                return

        print(f"[INFO] Configuration loaded successfully:")
        print(f"  - Log path: {expand_path(log_path)}")
        print(f"  - Lunar path: {lunar_path}")
        print(f"  - Java path: {java_path}")
        print(f"  - Pattern 1: {pattern_first}")
        print(f"  - Pattern 2: {pattern_second}")

        print(f"[1/4] Waiting for a first pattern")
        monitor_log(log_path, pattern_first)

        print("[2/4] Blocking Lunar Client...")
        manage_firewall_rule(lunar_path, "block")
        manage_firewall_rule(java_path, "block")

        print(f"[3/4] Waiting for a second pattern")
        monitor_log(log_path, pattern_second)

        print("[4/4] Unblocking...")
        manage_firewall_rule(lunar_path, "unblock")
        manage_firewall_rule(java_path, "unblock")

        print("[INFO] Bypass completed!")

        Beep(659, 175)
        Beep(659, 175)
        time.sleep(0.2)
        Beep(659, 175)
        time.sleep(0.2)
        Beep(523, 175)
        Beep(659, 175)
        time.sleep(0.2)
        Beep(784, 200)
        time.sleep(0.4)
        Beep(392, 200)
        time.sleep(0.4)
    except Exception as e:
        print(f"[FATAL]: {str(e)}")
    finally:
        print("Huyaka!")



if __name__ == "__main__":
    main()