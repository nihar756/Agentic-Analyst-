import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="projectX",
    user="postgres",
    password="database@123"
)

print("Connected Successfully")
conn.close()