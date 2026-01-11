from flask import Flask, request, jsonify, render_template_string
import sqlite3
import os
from datetime import datetime
import json
import requests   # 👈 NUEVO

app = Flask(__name__)

estado_alerta = {
    "alta": False,
    "baja": False
}


# ================= TELEGRAM =================
TELEGRAM_TOKEN = "8166291867:AAHIp2Q7E-44xe1a8ovHi27LGYQiTo_BEFM"
CHAT_ID = "5427827337"

def enviar_alerta(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensaje
    }

    try:
        r = requests.post(url, json=payload, timeout=5)
        print("📤 Telegram status:", r.status_code)
        print("📨 Telegram response:", r.text)
    except Exception as e:
        print("⚠️ Error enviando alerta Telegram:", e)


# ================= BASE DE DATOS =================
def conectar_db():
    return sqlite3.connect("datos.db")

def crear_tabla():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mediciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            temperatura REAL,
            humedad REAL,
            fecha TEXT
        )
    """)
    conn.commit()
    conn.close()

crear_tabla()

# ================= RUTAS =================
@app.route("/")
def inicio():
    return "Sistema AgroTech funcionando"

@app.route("/api/datos", methods=["POST"])
def recibir_datos():
    global estado_alerta

    data = request.get_json()
    print("📡 Datos recibidos desde ESP32:", data)

    temperatura = data["temperatura"]
    humedad = data["humedad"]
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO mediciones (temperatura, humedad, fecha) VALUES (?, ?, ?)",
        (temperatura, humedad, fecha)
    )
    conn.commit()
    conn.close()

    # ================= ALERTAS TELEGRAM =================
    if temperatura > 35 and not estado_alerta["alta"]:
        enviar_alerta(
            f"🚨 ALERTA AGROTECH\n"
            f"🌡️ Temperatura ALTA\n"
            f"Valor: {temperatura} °C\n"
            f"Hora: {fecha}"
        )
        estado_alerta["alta"] = True

    elif temperatura < 15 and not estado_alerta["baja"]:
        enviar_alerta(
            f"🚨 ALERTA AGROTECH\n"
            f"❄️ Temperatura BAJA\n"
            f"Valor: {temperatura} °C\n"
            f"Hora: {fecha}"
        )
        estado_alerta["baja"] = True

    # Reset cuando vuelve a rango normal
    if 15 <= temperatura <= 35:
        estado_alerta["alta"] = False
        estado_alerta["baja"] = False

    return jsonify({"status": "ok"})

# ================= API TIEMPO REAL =================
@app.route("/api/ultimo")
def api_ultimo():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT temperatura, humedad, fecha 
        FROM mediciones 
        ORDER BY id DESC 
        LIMIT 1
    """)
    dato = cursor.fetchone()
    conn.close()

    if not dato:
        return jsonify({})

    return jsonify({
        "temperatura": dato[0],
        "humedad": dato[1],
        "fecha": dato[2]
    })


@app.route("/test_telegram")
def test_telegram():
    enviar_alerta("✅ Mensaje de prueba AgroTech")
    return "Mensaje enviado"



# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT temperatura, humedad, fecha 
        FROM mediciones 
        ORDER BY id DESC 
        LIMIT 1
    """)
    ultimo = cursor.fetchone()

    cursor.execute("SELECT temperatura, humedad, fecha FROM mediciones")
    datos = cursor.fetchall()
    conn.close()

    if not ultimo:
        return "<h2>No hay datos aún</h2>"

    temperatura, humedad, fecha = ultimo

    temperaturas = [d[0] for d in datos]
    humedades = [d[1] for d in datos]
    fechas = [d[2] for d in datos]

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard AgroTech</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f4f6f8;
                padding: 20px;
            }
            .cards {
                display: flex;
                gap: 20px;
                margin-bottom: 20px;
            }
            .card {
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 10px rgba(0,0,0,0.1);
                flex: 1;
            }
            .value {
                font-size: 32px;
                font-weight: bold;
            }
        </style>
    </head>
    <body>

        <h1>🌱 Dashboard AgroTech</h1>
        <p><b>Última medición:</b> <span id="fecha">{{ fecha }}</span></p>

        <div class="cards">
            <div class="card">
                <h3>🌡️ Temperatura</h3>
                <div class="value" id="temp">{{ temperatura }} °C</div>
            </div>
            <div class="card">
                <h3>💧 Humedad</h3>
                <div class="value" id="hum">{{ humedad }} %</div>
            </div>
        </div>

        <canvas id="grafica"></canvas>

        <script>
            const ctx = document.getElementById('grafica').getContext('2d');
            const grafica = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: {{ fechas | safe }},
                    datasets: [
                        {
                            label: 'Temperatura (°C)',
                            data: {{ temperaturas | safe }},
                            borderWidth: 2
                        },
                        {
                            label: 'Humedad (%)',
                            data: {{ humedades | safe }},
                            borderWidth: 2
                        }
                    ]
                }
            });

            function actualizarDashboard() {
                fetch("/api/ultimo")
                    .then(res => res.json())
                    .then(data => {
                        if (!data.temperatura) return;

                        document.getElementById("temp").innerText = data.temperatura + " °C";
                        document.getElementById("hum").innerText = data.humedad + " %";
                        document.getElementById("fecha").innerText = data.fecha;

                        grafica.data.labels.push(data.fecha);
                        grafica.data.datasets[0].data.push(data.temperatura);
                        grafica.data.datasets[1].data.push(data.humedad);

                        if (grafica.data.labels.length > 20) {
                            grafica.data.labels.shift();
                            grafica.data.datasets[0].data.shift();
                            grafica.data.datasets[1].data.shift();
                        }

                        grafica.update();
                    });
            }

            setInterval(actualizarDashboard, 5000);
        </script>

    </body>
    </html>
    """

    return render_template_string(
        html,
        fecha=fecha,
        temperatura=temperatura,
        humedad=humedad,
        fechas=fechas,
        temperaturas=temperaturas,
        humedades=humedades
    )

# ================= EJECUCIÓN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

