import socket
import threading
import sqlite3


# Khởi tạo database và tạo bảng người dùng với cột theme và status nếu chưa có
def init_db():
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                      username TEXT PRIMARY KEY,
                      password TEXT NOT NULL,
                      theme TEXT DEFAULT 'light',
                      status TEXT DEFAULT 'offline')''')  # Add status column
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
                      sender TEXT,
                      recipient TEXT,
                      message TEXT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()


clients = {}


# Hàm lưu tin nhắn vào cơ sở dữ liệu
def save_message(sender, recipient, message):
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (sender, recipient, message) VALUES (?, ?, ?)",
                   (sender, recipient, message))
    conn.commit()
    conn.close()


# Xử lý yêu cầu lịch sử chat từ client
def handle_history_request(username, recipient, client_socket):
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender, message, timestamp FROM messages WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?) ORDER BY timestamp",
        (username, recipient, recipient, username))
    messages = cursor.fetchall()
    conn.close()
    if messages:
        for msg in messages:
            client_socket.send(f"{msg[0]} ({msg[2]}): {msg[1]}".encode('utf-8'))
    else:
        client_socket.send(f"No chat history available with {recipient}".encode('utf-8'))


# Hàm cập nhật chế độ sáng/tối cho người dùng
def update_theme(username, theme):
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET theme = ? WHERE username = ?", (theme, username))
    conn.commit()
    conn.close()


# Hàm cập nhật trạng thái người dùng
def update_user_status(username, status):
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE username = ?", (status, username))
    conn.commit()
    conn.close()


# Hàm đăng nhập và gửi chế độ sáng/tối hiện tại
def login_user(username, password, client_socket):
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()
    if user:
        cursor.execute("UPDATE users SET status = 'online' WHERE username = ?", (username,))
        conn.commit()
        theme = user[2]  # Get theme column
        client_socket.send(f"LOGIN_SUCCESS {theme}".encode('utf-8'))  # Send current theme
        conn.close()
        return True
    conn.close()
    return False


# Hàm xử lý mỗi client
def handle_client(client_socket, addr):
    print(f"Client {addr} connected.")
    username = None
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if message:
                command, *args = message.split()
                if command == "REGISTER":
                    username, password = args
                    if register_user(username, password):
                        client_socket.send("REGISTER_SUCCESS".encode('utf-8'))
                    else:
                        client_socket.send("REGISTER_FAIL".encode('utf-8'))
                elif command == "LOGIN":
                    username, password = args
                    if login_user(username, password, client_socket):
                        clients[username] = client_socket
                        broadcast_user_list()
                    else:
                        client_socket.send("LOGIN_FAIL".encode('utf-8'))
                elif command == "MESSAGE" and username:
                    recipient = args[0]
                    message_content = " ".join(args[1:])
                    send_to_user(username, recipient, message_content)
                    save_message(username, recipient, message_content)
                    if message_content.lower() == "hi":
                        auto_reply = (
                            "Chúc bạn một ngày, nhiều niềm vui\n"
                            "Công việc thuận lợi, ước mơ thành hiện\n"
                            "Sức khỏe dồi dào, tâm hồn tươi vui\n"
                            "Hạnh phúc luôn ngập tràn, cuộc sống viên mãn"
                        )
                        send_to_user("Auto-reply bot", username, auto_reply)
                        save_message("Auto-reply bot", username, auto_reply)
                elif command == "HISTORY" and username:
                    recipient = args[0]
                    handle_history_request(username, recipient, client_socket)
                elif command == "THEME" and username:  # Thay đổi chế độ sáng/tối
                    theme = args[0]
                    update_theme(username, theme)
                    client_socket.send(f"THEME_UPDATED {theme}".encode('utf-8'))
                elif command == "LEAVE" and username:
                    broadcast(f"{username} đã rời cuộc họp.", client_socket)
                    clients.pop(username, None)
                    update_user_status(username, "offline")
                    broadcast_user_list()
                    client_socket.close()
                    break
        except:
            print(f"Client {addr} disconnected.")
            if username in clients:
                clients.pop(username, None)
                update_user_status(username, "offline")
            broadcast_user_list()
            break


# Chức năng đăng ký người dùng
def register_user(username, password):
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


# Phát danh sách người dùng online/offline
def broadcast_user_list():
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, status FROM users")
    users = cursor.fetchall()
    conn.close()

    user_list = "USER_LIST " + " ".join([f"{user[0]}({user[1]})" for user in users])
    for client_socket in clients.values():
        client_socket.send(user_list.encode('utf-8'))


# Gửi tin nhắn đến người nhận
def send_to_user(sender, recipient, message):
    if recipient in clients:
        try:
            clients[recipient].send(f"{sender} (private): {message}".encode('utf-8'))
        except:
            clients[recipient].close()
            clients.pop(recipient, None)


# Khởi động server
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("192.168.1.3", 12345))
server.listen(5)
print("Server started on port 12345...")

init_db()

while True:
    client_socket, addr = server.accept()
    client_thread = threading.Thread(target=handle_client, args=(client_socket, addr))
    client_thread.start()



