import pymysql
from app.config import settings

def create_db():
    # Parse connection string
    # mysql+pymysql://root:@localhost:3306/examinal
    url = settings.DATABASE_URL
    if not url.startswith("mysql"):
        print("Not a MySQL connection string.")
        return

    # Extract info (very simple parsing)
    # This assumes mysql+pymysql://user:pass@host:port/db
    parts = url.split("://")[1].split("/")
    base_url = parts[0]
    db_name = parts[1]

    auth_host = base_url.split("@")
    if len(auth_host) > 1:
        user_pass = auth_host[0].split(":")
        user = user_pass[0]
        password = user_pass[1] if len(user_pass) > 1 else ""
        host_port = auth_host[1].split(":")
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 3306
    else:
        user = "root"
        password = ""
        host_port = auth_host[0].split(":")
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 3306

    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        print(f"Database '{db_name}' ensured.")
        conn.close()
    except Exception as e:
        print(f"Error creating database: {e}")

if __name__ == "__main__":
    create_db()
