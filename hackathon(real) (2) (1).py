import tkinter as tk
import json
import requests
from urllib.parse import unquote
from datetime import datetime

# Create the main window
root = tk.Tk()
root.title("WebAssign Homework Viewer")
root.geometry("600x400")
root.configure(bg="lightblue") 

# Output box to show results
output_box = tk.Text(root, height=15, width=70, bg="white", fg="black")
output_box.pack(pady=10)

def print_homework_assignments(assignments, label):
    output_box.insert(tk.END, f"\n{label} Homework Assignments:\n" + "-"*40 + "\n") #I couldn't get this to work, AI coded this line.
    for a in assignments:
        if a.get('category', '').lower() == 'homework': # if the data "category" is homework and not optional, continue. 
            due = a.get("due") # a field just like category that it can grab as data 
            try:
                due_dt = datetime.fromisoformat(due) # puts the data into time value 
                due_str = due_dt.strftime("%Y-%m-%d %H:%M") # puts the data into readable time value for user. 
                #these two lines were written with AI, as I couldn't figure out how to get it to work. 
            except:
                due_str = due # if missing, display unchanged string 
            output_box.insert(tk.END, f"{a['name']} | Due: {due_str}\n") 

def submit_cookie():
    cookie_input = entry_field.get() # whatever is inputted becomes the cookie variable 
    cookie_dict = dict(item.split("=", 1) for item in cookie_input.split("; ")) # because ; is a delimiter, we can break down the string

    cookies = {
        "seen_student_memo": cookie_dict.get("seen_student_memo"),
        "dtCookie": cookie_dict.get("dtCookie"),
        "cmp-session-id": cookie_dict.get("cmp-session-id"),
        "UserPass": cookie_dict.get("UserPass"),
        "scalcet9": cookie_dict.get("scalcet9"),
        "cmp-policy": cookie_dict.get("cmp-policy"),
        "AWSELB": cookie_dict.get("AWSELB"),
        "QSI_HistorySession": cookie_dict.get("QSI_HistorySession"),
    }

    url = "https://www.webassign.net/web/bff/section/1572455/assignments" #url of the class
    try:
        response = requests.get(url, cookies=cookies) # trying to pull data again, from the url, using the cookie data dictionary 
        data = response.json().get('data', {}) # grabs data from every assignment. AI told us how to use this function correctly. 
    except Exception as e:
        output_box.insert(tk.END, f"Error: {e}\n") # for any mistakes/accidents that happen
        return

    output_box.delete("1.0", tk.END)  # Clear previous output
    print_homework_assignments(data.get('currentAssignments', []), "Current") 
    print_homework_assignments(data.get('pastAssignments', []), "Past") # print the current and past assignments 

# Create a label
label = tk.Label(root, text="Enter your WebAssign session cookie:", bg="lightblue", fg="black")
label.pack(pady=5)

# Create an entry widget
entry_field = tk.Entry(root, width=60, bg="white", fg="black")
entry_field.pack(pady=5)

# Create a button to submit the cookie
submit_button = tk.Button(root, text="Submit", command=submit_cookie, bg="white", fg="black")
submit_button.pack(pady=5)

# Start the main event loop
root.mainloop()