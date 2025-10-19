# DAIoT

Este documento describe cómo desplegar un sistema completo con **data_logger.py** (en Raspberry Pi Zero 2 W) y **MQTT_suscriber.py** (en equipo Linux). Ambos usan **MQTT sobre TLS**, **QoS=1** y **persistencia**, guardan datos en **MariaDB** (base `temperatura`, tabla `mediciones`) y se visualizan con **Grafana**.

---

## Arquitectura general

- **Raspberry Pi Zero 2 W:** ejecuta `data_logger.py`. Obtiene datos desde un socket local, los guarda en la base de datos y los publica al broker MQTT con TLS.
- **Equipo Linux (servidor):** ejecuta `MQTT_suscriber.py`. Recibe los datos publicados y los guarda en su propia base de datos.
- **Broker MQTT (Mosquitto):** servidor con TLS (puerto 8883), QoS=1 y persistencia habilitada.
- **Grafana:** visualiza los datos desde la tabla `mediciones` de la base de datos `temperatura`.

---

## 1. Conexión SSH a la Raspberry Pi

Habilitar SSH (si no está activo):

1. Colocar la tarjeta SD en otro equipo y crear un archivo vacío llamado `ssh` (sin extensión) dentro de la partición `boot`.
2. Insertar la SD en la Raspberry Pi y arrancarla.
3. Conectar por SSH desde el equipo Linux:
   ```bash
   ssh pi@<IP_DE_LA_PI>
   # Ejemplo
   ssh pi@10.0.1.19
   ```

---

## 2. Actualizar la Pi

Actualizar paquetes y firmware:
```bash
sudo apt update
sudo apt upgrade -y
sudo apt autoremove -y
```

---

## 3. Instalación de dependencias en la Raspberry Pi (data_logger)

Instalar Python y crear un entorno virtual:
```bash
sudo apt install -y python3 python3-venv python3-pip
python3 -m venv ~/venv_datalogger
source ~/venv_datalogger/bin/activate
pip install --upgrade pip
pip install paho-mqtt mariadb
```

Si `pip install mariadb` falla, instalar dependencias del sistema:
```bash
sudo apt install -y libmariadb-dev libmariadb-dev-compat build-essential
pip install mariadb
```

---

## 4. Instalación de dependencias en el equipo Linux (suscriptor)

Instalar Python y crear entorno virtual:
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
python3 -m venv ~/venv_mqttsub
source ~/venv_mqttsub/bin/activate
pip install --upgrade pip
pip install paho-mqtt mariadb
```

Si hay errores con MariaDB:
```bash
sudo apt install -y libmariadb-dev libmariadb-dev-compat build-essential
pip install mariadb
```

---

## 5. Instalación y configuración de MariaDB

Instalar MariaDB:
```bash
sudo apt install -y mariadb-server mariadb-client
sudo systemctl enable --now mariadb
sudo mysql_secure_installation
```

Crear base de datos, usuario y tabla:
```sql
CREATE DATABASE temperatura CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE USER 'user_name'@'localhost' IDENTIFIED BY 'TU_CONTRASENA_SEGURA';
GRANT ALL PRIVILEGES ON temperatura.* TO 'user_name'@'localhost';
FLUSH PRIVILEGES;
USE temperatura;

CREATE TABLE mediciones (
  id INT AUTO_INCREMENT PRIMARY KEY,
  id_estacion INT NOT NULL,
  temp1 DECIMAL(6,2) NOT NULL,
  temp2 DECIMAL(6,2) NOT NULL,
  temp3 DECIMAL(6,2) NOT NULL,
  ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. Instalación y configuración del broker MQTT (Mosquitto) con TLS

Instalar Mosquitto:
```bash
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

### 6.1 Generar certificados TLS

```bash
mkdir -p ~/mqtt_certs
cd ~/mqtt_certs

openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt -subj "/CN=MQTT-CA"

openssl genrsa -out server.key 4096
openssl req -new -key server.key -out server.csr -subj "/CN=192.168.80.185"
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 3650

openssl genrsa -out client.key 4096
openssl req -new -key client.key -out client.csr -subj "/CN=cliente-paisita"
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out client.crt -days 3650
```

Copiar certificados al broker:
```bash
sudo mkdir -p /etc/mosquitto/certs
sudo cp ca.crt server.crt server.key /etc/mosquitto/certs/
sudo chown -R mosquitto:mosquitto /etc/mosquitto/certs
sudo chmod 640 /etc/mosquitto/certs/server.key
```

### 6.2 Configurar Mosquitto

Crear `/etc/mosquitto/conf.d/tls.conf`:
```
listener 8883
protocol mqtt
cafile /etc/mosquitto/certs/ca.crt
certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key
persistence true
persistence_location /var/lib/mosquitto/
allow_anonymous true
```

Reiniciar:
```bash
sudo systemctl restart mosquitto
```

---

## 7. Configurar los scripts

Copiar `data_logger.py` y `MQTT_suscriber.py` a sus ubicaciones.  
Ajustar en ambos:
- `broker = "192.168.80.185"`
- `puerto = 8883`
- Rutas a certificados (`CA_CERT`, `CLIENT_CERT`, `CLIENT_KEY`)
- Datos de base (`DB_USER`, `DB_PASSWORD`, etc.)

Permisos:
```bash
chmod 600 client.key
chmod 644 client.crt ca.crt
```

---

## 8. QoS y persistencia

Publicar con QoS=1 y retain:
```python
cliente.publish(topico, mensaje, qos=1, retain=True)
```

Suscribir con QoS=1 y sesión persistente:
```python
client = mqtt.Client(client_id="mi_cliente_suscriptor", clean_session=False)
client.subscribe("sensors/Paisita/temps", qos=1)
```

---

## 9. Crear servicios systemd

### Raspberry Pi (`/etc/systemd/system/datalogger.service`)
```
[Unit]
Description=Data Logger MQTT TLS
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/datalogger
Environment=PATH=/home/pi/venv_datalogger/bin
ExecStart=/home/pi/venv_datalogger/bin/python /home/pi/datalogger/data_logger.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Linux (`/etc/systemd/system/mqtt_suscriber.service`)
```
[Unit]
Description=MQTT Suscriber TLS
After=network.target

[Service]
User=usuario
WorkingDirectory=/home/usuario/mqtt_sub
Environment=PATH=/home/usuario/venv_mqttsub/bin
ExecStart=/home/usuario/venv_mqttsub/bin/python /home/usuario/mqtt_sub/MQTT_suscriber.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Activar:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now datalogger.service
sudo systemctl enable --now mqtt_suscriber.service
```

---

## 10. Instalar Grafana

```bash
sudo apt install -y apt-transport-https software-properties-common wget
sudo mkdir -p /etc/apt/keyrings
sudo wget -q -O /etc/apt/keyrings/grafana.gpg https://apt.grafana.com/gpg.key
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt update
sudo apt install -y grafana
sudo systemctl enable --now grafana-server
```

---

## 11. Conectar Grafana con MariaDB

Abrir Grafana en `http://localhost:3000`  
Usuario: `admin`  
Contraseña: `admin`  

Ir a **Connections → Data sources → Add data source → MySQL** y configurar:
- Host: `localhost:3306`
- Database: `temperatura`
- User: `user_name`
- Password: contraseña configurada
- SSL Mode: `disable`

Guardar y probar conexión.

---

## 12. Crear dashboard en Grafana

1. Ir a **Dashboards → New → New Dashboard**
2. Click **Add a new panel**
3. Seleccionar la fuente de datos MySQL
4. Usar esta consulta:
```sql
SELECT
  UNIX_TIMESTAMP(ts) * 1000 AS time,
  temp1,
  temp2,
  temp3
FROM mediciones
ORDER BY ts DESC
LIMIT 200;
```
5. Tipo de gráfico: **Time Series**
6. Guardar panel y dashboard

---

## 13. Verificación

Publicar mensaje de prueba:
```bash
mosquitto_pub -h 192.168.80.185 -p 8883 --cafile ca.crt --cert client.crt --key client.key -t 'sensors/Paisita/temps' -m "25.4,26.1,24.8"
```

Ver mensajes:
```bash
mosquitto_sub -h 192.168.80.185 -p 8883 --cafile ca.crt -t 'sensors/Paisita/temps'
```

Ver registros:
```bash
mysql -u user_name -p -D temperatura -e "SELECT * FROM mediciones ORDER BY ts DESC LIMIT 10;"
```

---

## 14. Buenas prácticas

- Usar `chmod 600` en archivos `.key`
- No usar `allow_anonymous true` en producción
- Respaldar base de datos:
```bash
mysqldump -u user_name -p temperatura > backup_temperatura.sql
```
- Actualizar certificados y contraseñas periódicamente

---

## 15. Comandos útiles

```bash
ssh pi@10.0.1.19
sudo apt update && sudo apt upgrade -y
source ~/venv_datalogger/bin/activate
python /home/pi/datalogger/data_logger.py
sudo journalctl -u datalogger.service -f
sudo journalctl -u mqtt_suscriber.service -f
```

---

## 16. Resumen

| Componente | Función | Ubicación | Puerto |
|-------------|----------|------------|--------|
| data_logger.py | Publicador MQTT + DB | Raspberry Pi Zero 2 W | 8883 |
| MQTT_suscriber.py | Suscriptor MQTT + DB | Servidor Linux | 8883 |
| Mosquitto | Broker MQTT TLS | 192.168.80.185 | 8883 |
| MariaDB | Base de datos | Local o remoto | 3306 |
| Grafana | Visualización de datos | `http://localhost:3000` | 3000 |
