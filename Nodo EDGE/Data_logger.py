import socket
import mariadb
import paho.mqtt.client as paho

HOST = "10.0.1.19"
PORT = 7000

DB_USER = "andavaro"
DB_PASSWORD = “***********”
DB_HOST = "localhost"
DB_PORT = 3306
DB_NAME = "temperatura"

broker = "192.168.80.185"
puerto = 8883
topico = "sensors/Paisita/temps"
ID_ESTACION = 1

CA_CERT = "ca.crt"
CLIENT_CERT = "client.crt"
CLIENT_KEY = "client.key"

def parsear_datos(datos_recibidos):
    partes = datos_recibidos.strip().split('+')[1:]
    return [float(p) for p in partes]

def guardar_en_db(valores):
    if not valores:
        return
    conn = None
    cur = None
    try:
        conn = mariadb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME
        )
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO mediciones (id_estacion, temp1, temp2, temp3) VALUES (?, ?, ?, ?)",
            (ID_ESTACION, valores[0], valores[1], valores[2])
        )
        conn.commit()
        print(f"Datos insertados en la DB: {valores}")
    except mariadb.Error as e:
        print(f"Error al interactuar con MariaDB: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    cliente = paho.Client(client_id="Paisita", clean_session=False)
    cliente.tls_set(ca_certs=CA_CERT, certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
    cliente.tls_insecure_set(False)

    try:
        cliente.connect(broker, puerto)
        print(f"Conectado al broker TLS en {broker}:{puerto}")
    except Exception as e:
        print(f"Error al conectar al broker: {e}")
        exit()

    mensaje = f"{valores[0]}, {valores[1]}, {valores[2]}"
    cliente.publish(topico, mensaje, qos=1, retain=True)
    print(f"Mensaje '{mensaje}' publicado en '{topico}' con QoS=1 y retain=True")
    cliente.disconnect()

def iniciar_cliente():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print(f"Intentando conectar a {HOST}:{PORT}...")
            s.connect((HOST, PORT))
            print("Conexión exitosa con el servidor.")
            while True:
                data = s.recv(1024)
                if not data:
                    print("El servidor cerró la conexión.")
                    break
                datos_recibidos = data.decode('utf-8').strip()
                print(f"Recibido del servidor: {datos_recibidos}")
                valores = parsear_datos(datos_recibidos)
                if valores:
                    guardar_en_db(valores)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    iniciar_cliente()