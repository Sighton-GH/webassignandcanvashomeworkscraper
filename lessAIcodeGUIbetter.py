"""
SFU Canvas Assignment Tracker (Final Compiled Version)

Features:
- Modern ttkbootstrap GUI
- SFU logo at the top with title and description
- Connects to SFU Canvas via a 3rd‑party integration access token
- Safe: token is read‑only (cannot write or change anything in Canvas)
- Top controls (token, fetch button, authenticated status) are static
- Notebook tab bar (days of week + "No Due Date") is static (does not scroll)
- Each tab's content (assignments list) is scrollable independently
- Mouse wheel scrolling inside each tab
- Persistent Progress Box (never clears)
- Determinate progress bar with percentage updates

Setup:
pip install requests ttkbootstrap pillow
"""

import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import ttkbootstrap as tb
from PIL import Image, ImageTk
import threading

BASE_URL = "https://canvas.sfu.ca/api/v1"

# -----------------------------
# Helper functions
# -----------------------------
def get_all_pages(url, headers, params=None):
    """Fetch all paginated results from a Canvas API endpoint."""
    results = []
    while url:
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        results.extend(r.json())
        if "next" in r.links:
            url = r.links["next"]["url"]
            params = None
        else:
            url = None
    return results

def parse_due_date(due_str):
    """Convert Canvas due_at string into datetime (UTC)."""
    return datetime.fromisoformat(due_str.replace("Z", "+00:00"))

def log_status(msg):
    """Append a message to the Progress Box (persistent)."""
    status_box.config(state="normal")
    status_box.insert(tk.END, msg + "\n")
    status_box.see(tk.END)
    status_box.config(state="disabled")
    app.update_idletasks()

def bind_mousewheel(widget, canvas):
    """Enable mouse wheel scrolling inside a tab's canvas."""
    def on_mousewheel(event):
        # Linux sends Button-4/5; Windows/macOS use delta
        if getattr(event, "num", None) == 4:      # Linux scroll up
            canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:    # Linux scroll down
            canvas.yview_scroll(1, "units")
        else:                                     # Windows/macOS
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    widget.bind("<Enter>", lambda e: widget.focus_set())
    widget.bind("<MouseWheel>", on_mousewheel)   # Windows/macOS
    widget.bind("<Button-4>", on_mousewheel)     # Linux
    widget.bind("<Button-5>", on_mousewheel)     # Linux

# -----------------------------
# Fetch assignments (background)
# -----------------------------
def fetch_assignments_thread():
    fetch_button.config(state="disabled")
    progress_bar["value"] = 0
    progress_label.config(text="Progress: 0%")

    try:
        token = token_entry.get().strip()
        if not token:
            messagebox.showerror("Error", "Please enter your Canvas access token.")
            return

        headers = {"Authorization": f"Bearer {token}"}

        # Clear existing assignment content in tabs
        for tab in all_tabs:
            for widget in tab_frames[tab].winfo_children():
                widget.destroy()

        log_status("----- New fetch started -----")
        log_status("Authenticating user...")
        user_resp = requests.get(f"{BASE_URL}/users/self", headers=headers)
        user_resp.raise_for_status()
        user = user_resp.json()
        user_id = user["id"]

        # Show both name and ID in UI
        status_label.config(text=f"Authenticated as: {user.get('name')} (ID: {user_id})")
        log_status(f"Authenticated as {user.get('name')} (User ID: {user_id})")

        log_status("Fetching active courses...")
        courses_url = f"{BASE_URL}/users/{user_id}/courses"
        courses = get_all_pages(courses_url, headers, params={"enrollment_state": "active"})
        log_status(f"Found {len(courses)} active courses.")

        total_courses = len(courses)
        progress_bar["maximum"] = max(total_courses, 1)  # avoid zero max

        log_status("Compiling assignments...")
        all_assignments = []
        for idx, course in enumerate(courses, start=1):
            course_id = course["id"]
            course_name = course.get("name", "Unnamed Course")
            log_status(f"  → Fetching assignments for {course_name}")
            assignments_url = f"{BASE_URL}/courses/{course_id}/assignments"
            assignments = get_all_pages(assignments_url, headers)
            for a in assignments:
                all_assignments.append({
                    "course_name": course_name,
                    "assignment_name": a["name"],
                    "due_at": a.get("due_at")
                })

            # Update progress bar
            progress_bar["value"] = idx
            percent = int((idx / max(total_courses, 1)) * 100)
            progress_label.config(text=f"Progress: {percent}%")
            app.update_idletasks()

        now = datetime.now(timezone.utc)
        try:
            local_tz = ZoneInfo("America/Los_Angeles")
        except Exception:
            local_tz = timezone.utc

        # Separate and sort
        upcoming_assignments = [
            a for a in all_assignments
            if a["due_at"] is not None and parse_due_date(a["due_at"]) >= now
        ]
        no_due_assignments = [a for a in all_assignments if a["due_at"] is None]
        upcoming_assignments.sort(key=lambda x: parse_due_date(x["due_at"]))

        log_status(f"Upcoming assignments: {len(upcoming_assignments)}")
        log_status(f"No due date: {len(no_due_assignments)}")

        # Group by weekday
        grouped = {day: [] for day in day_tabs}
        for item in upcoming_assignments:
            due_dt_utc = parse_due_date(item["due_at"])
            due_dt_local = due_dt_utc.astimezone(local_tz)
            weekday = due_dt_local.strftime("%A")
            delta = due_dt_local - datetime.now(local_tz)
            days_remaining = delta.days
            hours_remaining = max(0, delta.seconds // 3600)
            due_str = due_dt_local.strftime("%Y-%m-%d %H:%M %Z")
            grouped[weekday].append(
                f"[{item['course_name']}] {item['assignment_name']}\n"
                f"   Due: {due_str}\n"
                f"   In: {days_remaining} days {hours_remaining} hrs\n"
            )

        # Populate tabs
        for day in day_tabs:
            if grouped[day]:
                for text in grouped[day]:
                    ttk.Label(tab_frames[day], text=text, anchor="w", justify="left", wraplength=900)\
                        .pack(fill="x", padx=10, pady=5)
            else:
                ttk.Label(tab_frames[day], text="No assignments due.", foreground="gray").pack(pady=20)

        if no_due_assignments:
            for item in no_due_assignments:
                ttk.Label(tab_frames["No Due Date"],
                          text=f"[{item['course_name']}] {item['assignment_name']}",
                          anchor="w", justify="left", wraplength=900)\
                    .pack(fill="x", padx=10, pady=5)
        else:
            ttk.Label(tab_frames["No Due Date"], text="No assignments without due dates.", foreground="gray")\
                .pack(pady=20)

        log_status("✅ Everything is loaded.")
        progress_label.config(text="Progress: 100%")

    except requests.exceptions.HTTPError as e:
        messagebox.showerror("HTTP Error", str(e))
    except Exception as e:
        messagebox.showerror("Error", str(e))
    finally:
        fetch_button.config(state="normal")

def fetch_assignments():
    """Start background thread to keep the GUI responsive while fetching."""
    threading.Thread(target=fetch_assignments_thread, daemon=True).start()

# -----------------------------
# GUI Setup
# -----------------------------
app = tb.Window(themename="cosmo")
app.title("SFU Canvas Assignment Tracker")
app.geometry("1200x900")

# Header with logo + title + description
header_frame = ttk.Frame(app, padding=10)
header_frame.pack(fill=tk.X)

# SFU Logo at top-left
try:
    logo_img = Image.open("sfu_logo.png").resize((120, 60))
    logo_photo = ImageTk.PhotoImage(logo_img)
    logo_label = ttk.Label(header_frame, image=logo_photo)
    logo_label.pack(side="left", padx=(0, 10))
except Exception:
    logo_label = ttk.Label(header_frame, text="[SFU Logo]")
    logo_label.pack(side="left", padx=(0, 10))

# Title and description next to logo
title_frame = ttk.Frame(header_frame)
title_frame.pack(side="left", padx=10)

ttk.Label(title_frame, text="SFU Canvas Assignment Tracker",
          font=("TkDefaultFont", 18, "bold")).pack(anchor="w")

ttk.Label(
    title_frame,
    text=(
        "This program connects to your SFU Canvas account using a 3rd‑party integration access token. "
        "It is completely safe: the token only allows the program to READ your course and assignment "
        "information — it cannot make changes or write anything back to Canvas.\n\n"
        "Assignments are fetched from all your active courses and organized by weekday, with a dedicated "
        "'No Due Date' tab for items without deadlines. Use this tool to keep track of upcoming deadlines "
        "in a clear, scrollable view."
    ),
    wraplength=900,
    justify="left"
).pack(anchor="w", pady=(4, 0))

# Controls (token, fetch button, authenticated status)
top_frame = ttk.Frame(app, padding=10)
top_frame.pack(fill=tk.X)

ttk.Label(top_frame, text="Canvas Access Token:").pack(anchor="w")
token_entry = ttk.Entry(top_frame, width=100, show="*")
token_entry.pack(fill=tk.X, pady=5)

fetch_button = tb.Button(top_frame, text="Fetch Assignments", bootstyle="primary", command=fetch_assignments)
fetch_button.pack(pady=5)

# Shows "Authenticated as: Name (ID: 12345)" after login
status_label = ttk.Label(top_frame, text="Authenticated as: —", foreground="gray")
status_label.pack(anchor="w", pady=5)

# Notebook (tab bar is static; each tab has its own scrollable content)
assignments_frame = ttk.Frame(app)
assignments_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

notebook = ttk.Notebook(assignments_frame)
notebook.pack(fill=tk.BOTH, expand=True)

day_tabs = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
all_tabs = day_tabs + ["No Due Date"]
tab_frames = {}  # maps tab name -> inner scrollable frame

for tab in all_tabs:
    # Outer frame for the tab (static within the notebook)
    outer_frame = ttk.Frame(notebook)
    notebook.add(outer_frame, text=tab)

    # Scrollable area inside the tab
    tab_canvas = tk.Canvas(outer_frame, highlightthickness=0)
    tab_scrollbar = ttk.Scrollbar(outer_frame, orient="vertical", command=tab_canvas.yview)
    inner_frame = ttk.Frame(tab_canvas)

    # Update scrollregion whenever content grows/shrinks
    inner_frame.bind(
        "<Configure>",
        lambda e, c=tab_canvas: c.configure(scrollregion=c.bbox("all"))
    )

    tab_canvas.create_window((0, 0), window=inner_frame, anchor="nw")
    tab_canvas.configure(yscrollcommand=tab_scrollbar.set)

    tab_canvas.pack(side="left", fill="both", expand=True)
    tab_scrollbar.pack(side="right", fill="y")

    # Enable mouse wheel scrolling for this tab
    bind_mousewheel(inner_frame, tab_canvas)

    # Save inner_frame where assignment labels will be added
    tab_frames[tab] = inner_frame

# -----------------------------
# Progress Box (persistent, labeled)
# -----------------------------
progress_log_frame = ttk.Frame(app, padding=(10, 5))
progress_log_frame.pack(fill=tk.BOTH, expand=False)

ttk.Label(progress_log_frame, text="Progress Box", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
status_box = scrolledtext.ScrolledText(progress_log_frame, height=6, wrap=tk.WORD, state="disabled")
status_box.pack(fill=tk.BOTH, expand=True, pady=(2, 5))

# -----------------------------
# Progress bar + label
# -----------------------------
progress_frame = ttk.Frame(app)
progress_frame.pack(fill=tk.X, padx=10, pady=5)

progress_bar = ttk.Progressbar(progress_frame, mode="determinate")
progress_bar.pack(side="left", fill=tk.X, expand=True, padx=(0, 10))

progress_label = ttk.Label(progress_frame, text="Progress: 0%")
progress_label.pack(side="right")

# -----------------------------
# Run the app
# -----------------------------
app.mainloop()
