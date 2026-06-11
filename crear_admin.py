import mysql.connector
import bcrypt
from config import Config

password_plano = "admin123"
password_hash = bcrypt.hashpw(password_plano.encode("utf-8"), bcrypt.gensalt())

conn = mysql.connector.connect(
    host=Config.MYSQL_HOST,
    user=Config.MYSQL_USER,
    password=Config.MYSQL_PASSWORD,
    database=Config.MYSQL_DB
)

cursor = conn.cursor()

cursor.execute("""
    INSERT INTO usuarios (
        nombres,
        apellidos,
        usuario,
        correo,
        password,
        rol_id,
        estado
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s)
""", (
    "Administrador",
    "General",
    "admin",
    "admin@inamhi.gob.ec",
    password_hash.decode("utf-8"),
    1,
    "ACTIVO"
))

conn.commit()
cursor.close()
conn.close()

print("Usuario administrador creado correctamente")
print("Usuario: admin")
print("Contraseña: admin123")