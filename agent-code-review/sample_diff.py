SAMPLE_DIFF = """diff --git a/auth/login.py b/auth/login.py
new file mode 100644
index 0000000..1a2b3c4
--- /dev/null
+++ b/auth/login.py
@@ -0,0 +1,52 @@
+import hashlib
+import sqlite3
+import logging
+
+DB_PATH = "/var/app/users.db"
+SECRET_KEY = "my_super_secret_key_12345"
+
+def authenticate(username,password):
+    conn = sqlite3.connect(DB_PATH)
+    cursor = conn.cursor()
+    query = f"SELECT id, role FROM users WHERE username = '{username}' AND password = '{password}'"
+    cursor.execute(query)
+    row = cursor.fetchone()
+    if row != None:
+        logging.info(f"Login success for {username}, password: {password}")
+        return {"user_id": row[0], "role": row[1]}
+    else:
+        return None
+
+def hashPassword(password):
+    return hashlib.md5(password.encode()).hexdigest()
+
+def reset_password(user_id,new_password):
+    conn = sqlite3.connect(DB_PATH)
+    cursor = conn.cursor()
+    hashed = hashPassword(new_password)
+    query = "UPDATE users SET password='" + hashed + "' WHERE id=" + str(user_id)
+    cursor.execute(query)
+    conn.commit()
+
+def get_permissions(user_id):
+    conn = sqlite3.connect(DB_PATH)
+    cursor = conn.cursor()
+    perms = []
+    for row in cursor.execute("SELECT perm FROM user_perms WHERE uid=" + str(user_id)):
+        perms.append(row[0])
+    return perms
+
+def is_admin(user):
+    return user["role"] == "admin" or user["role"] == "superadmin" or user["role"] == "root"
+
+def update_profile(user_id, data):
+    conn = sqlite3.connect(DB_PATH)
+    cursor = conn.cursor()
+    for key in data:
+        cursor.execute(f"UPDATE users SET {key} = '{data[key]}' WHERE id = {user_id}")
+    conn.commit()
"""
