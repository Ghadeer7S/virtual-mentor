#!/bin/bash
set -e

echo "Waiting for MySQL..."

python3 - <<'EOF'
import os
import sys
import time
import pymysql

host = os.environ.get("DB_HOST", "db")
port = int(os.environ.get("DB_PORT", 3306))
user = os.environ.get("DB_USER", "root")
password = os.environ.get("DB_PASSWORD", "")
database = os.environ.get("DB_NAME", "")

start_time = time.time()
while True:
    try:
        connection = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=database if database else None, connect_timeout=3
        )
        connection.close()
        print("MySQL is fully up and reachable.")
        break
    except Exception as e:
        if time.time() - start_time > 60:
            print(f"ERROR: MySQL connection timed out: {e}")
            sys.exit(1)
        print("MySQL is unavailable - sleeping...")
        time.sleep(2)
EOF

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn WSGI server..."
exec gunicorn --bind 0.0.0.0:8000 --workers 3 --threads 2 --timeout 60 virtual_mentor.wsgi:application