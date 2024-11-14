import socket
import tkinter as tk
from tkinter import simpledialog, messagebox, colorchooser
import threading
from datetime import datetime

# Kết nối tới server
def connect_to_server():
    try:
        client_socket.connect(("192.168.1.3", 12345))
        print("Connected to server.")
    except:
        print("Unable to connect to server.")
        return

# Xử lý đăng ký
def register():
    username = simpledialog.askstring("Register", "Enter Username:")
    password = simpledialog.askstring("Register", "Enter Password:", show="*")
    if username and password:
        client_socket.send(f"REGISTER {username} {password}".encode('utf-8'))
        response = client_socket.recv(1024).decode('utf-8')
        if response == "REGISTER_SUCCESS":
            messagebox.showinfo("Register", "Registration successful!")
        else:
            messagebox.showwarning("Register", "Username already exists.")

# Xử lý đăng nhập và nhận chế độ sáng/tối từ server
def login():
    global logged_in
    username = simpledialog.askstring("Login", "Enter Username:")
    password = simpledialog.askstring("Login", "Enter Password:", show="*")
    if username and password:
        client_socket.send(f"LOGIN {username} {password}".encode('utf-8'))
        response = client_socket.recv(1024).decode('utf-8')
        if response.startswith("LOGIN_SUCCESS"):
            messagebox.showinfo("Login", "Login successful!")
            logged_in = True
            theme = response.split()[1]
            apply_theme(theme)
            receive_thread.start()
        else:
            messagebox.showwarning("Login", "Invalid username or password.")

# Gửi yêu cầu chuyển đổi chế độ sáng/tối tới server và áp dụng trên giao diện
def toggle_theme():
    new_theme = "dark" if current_theme.get() == "light" else "light"
    client_socket.send(f"THEME {new_theme}".encode('utf-8'))
    current_theme.set(new_theme)
    apply_theme(new_theme)

# Áp dụng chế độ sáng/tối hoặc màu nền tùy chỉnh cho giao diện
def apply_theme(theme):
    if theme == "custom":
        color_code = colorchooser.askcolor(title="Choose background color")[1]  # Hộp thoại chọn màu
        if color_code:  # Nếu người dùng chọn một màu
            bg_color = color_code
            fg_color = "#fff" if current_theme.get() == "dark" else "#000"
        else:
            return  # Nếu không chọn màu nào, thoát khỏi hàm mà không làm gì
    else:
        current_theme.set(theme)
        bg_color = "#333" if theme == "dark" else "#fff"
        fg_color = "#fff" if theme == "dark" else "#000"

    root.config(bg=bg_color)
    chat_log.config(bg=bg_color, fg=fg_color)
    message_entry.config(bg=bg_color, fg=fg_color, insertbackground=fg_color)

# Yêu cầu lịch sử chat từ server
def view_history():
    recipient = recipient_var.get()
    if recipient and logged_in:
        client_socket.send(f"HISTORY {recipient}".encode('utf-8'))
        chat_log.insert(tk.END, f"Chat history with {recipient}:\n")

# Gửi tin nhắn đến người nhận và hiển thị thời gian
def send_message():
    message = message_entry.get()
    recipient = recipient_var.get()
    if message and recipient and logged_in:
        client_socket.send(f"MESSAGE {recipient} {message}".encode('utf-8'))
        message_entry.delete(0, tk.END)
        current_time = datetime.now().strftime("%H:%M:%S")
        chat_log.insert(tk.END, f"You ({current_time}): {message}\n")
        chat_log.see(tk.END)

# Nhận tin nhắn từ server và hiển thị thời gian
def receive_messages():
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if message.startswith("USER_LIST"):
                update_user_list(message)
            elif "Chat history with" in message or message.startswith("No chat history available"):
                chat_log.insert(tk.END, f"{message}\n")
            elif message.startswith("THEME_UPDATED"):
                new_theme = message.split()[1]
                apply_theme(new_theme)
            else:
                current_time = datetime.now().strftime("%H:%M:%S")
                chat_log.insert(tk.END, f"{message} ({current_time})\n")
                chat_log.see(tk.END)
        except:
            print("Error receiving message.")
            break

# Cập nhật danh sách người dùng online/offline
def update_user_list(message):
    users = message.split()[1:]
    recipient_menu['menu'].delete(0, 'end')
    for user in users:
        user_info = user.split("(")
        username = user_info[0]
        status = user_info[1][:-1]  # Remove the closing ')'
        recipient_menu['menu'].add_command(label=f"{username} - {status}", command=tk._setit(recipient_var, username))
    recipient_var.set(users[0].split("(")[0] if users else "")

# Giao diện GUI
root = tk.Tk()
root.title("Chat Client")

top_frame = tk.Frame(root)
top_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

chat_log = tk.Text(top_frame, height=15, width=50)
chat_log.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

recipient_label = tk.Label(top_frame, text="Select recipient:")
recipient_label.pack(side=tk.LEFT, padx=5)

recipient_var = tk.StringVar(root)
recipient_menu = tk.OptionMenu(top_frame, recipient_var, "")
recipient_menu.pack(side=tk.LEFT, padx=5)

message_entry = tk.Entry(top_frame, width=40)
message_entry.pack(side=tk.LEFT, padx=5)

send_button = tk.Button(top_frame, text="Send", command=send_message)
send_button.pack(side=tk.LEFT, padx=5)

# Nút xem lịch sử chat
view_history_button = tk.Button(top_frame, text="View History", command=view_history)
view_history_button.pack(side=tk.LEFT, padx=5)

leave_button = tk.Button(top_frame, text="Leave", command=root.quit)
leave_button.pack(side=tk.RIGHT, padx=5)

# Nút chuyển đổi chế độ sáng/tối
theme_button = tk.Button(top_frame, text="Toggle Theme", command=toggle_theme)
theme_button.pack(side=tk.LEFT, padx=5)

# Nút để chọn màu nền tùy chỉnh
custom_color_button = tk.Button(top_frame, text="Custom Background", command=lambda: apply_theme("custom"))
custom_color_button.pack(side=tk.LEFT, padx=5)

# Kết nối đến server và khởi tạo thread nhận tin nhắn
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
connect_to_server()

receive_thread = threading.Thread(target=receive_messages, daemon=True)

logged_in = False
current_theme = tk.StringVar(value="light")  # Lưu chế độ sáng/tối hiện tại

login_button = tk.Button(root, text="Login", command=login)
login_button.pack(side=tk.LEFT, padx=5, pady=5)

register_button = tk.Button(root, text="Register", command=register)
register_button.pack(side=tk.LEFT, padx=5, pady=5)

root.mainloop()


