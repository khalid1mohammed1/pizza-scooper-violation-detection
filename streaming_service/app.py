from flask import Flask, Response, jsonify, render_template_string, request, send_file
import pika, pickle, cv2, threading, sqlite3, os, io
import pandas as pd
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config 

app = Flask(__name__)
latest_frame = None
lock = threading.Lock()

def init_db():
    """Initialize SQLite database for violations and worker movement tracking"""
    conn = sqlite3.connect(config.DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS violations (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, frame_id INTEGER, img_path TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movements (id INTEGER PRIMARY KEY AUTOINCREMENT, x INTEGER, y INTEGER)''')
    conn.commit()
    conn.close()

init_db()

def consume_results():
    """Consume processed frames and violation alerts from RabbitMQ"""
    global latest_frame
    conn = pika.BlockingConnection(pika.ConnectionParameters(host=config.RABBITMQ_HOST, heartbeat=600))
    ch = conn.channel()
    ch.queue_declare(queue=config.STREAM_QUEUE)
    ch.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body):
        global latest_frame
        data = pickle.loads(body)
        
        # We use the frame directly as it already contains AI overlays from main.py
        frame = data["frame"]

        with lock:
            latest_frame = frame
        
        db_conn = sqlite3.connect(config.DB_NAME)
        cursor = db_conn.cursor()

        # Update movement data for the Heatmap visualization
        if "detections" in data:
            for det in data["detections"]:
                if det['label'] in ['person', 'hand']: 
                    x = (det['box'][0] + det['box'][2]) // 2
                    y = (det['box'][1] + det['box'][3]) // 2
                    cursor.execute("INSERT INTO movements (x, y) VALUES (?, ?)", (x, y))

        # Record violation to database and save evidence image
        if data.get("is_violating", False):
            img_name = f"violation_{data['frame_id']}_{datetime.now().strftime('%H%M%S')}.jpg"
            img_path = os.path.join(config.SAVE_DIR, img_name)
            cv2.imwrite(img_path, frame)
            cursor.execute("INSERT INTO violations (timestamp, frame_id, img_path) VALUES (?,?,?)", 
                           (data["time"], data["frame_id"], img_path))
        
        db_conn.commit()
        db_conn.close()
        ch.basic_ack(delivery_tag=method.delivery_tag)

    ch.basic_consume(queue=config.STREAM_QUEUE, on_message_callback=callback)
    ch.start_consuming()

threading.Thread(target=consume_results, daemon=True).start()

# Main dashboard route
@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>EagleVision | AI Ultimate Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background-color: #020617; color: #f8fafc; font-family: 'Inter', sans-serif; }
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
            .log-container::-webkit-scrollbar { width: 4px; }
            .log-container::-webkit-scrollbar-thumb { background: #334155; border-radius: 10px; }
        </style>
    </head>
    <body class="p-4">
        <audio id="alarm-sound" src="https://www.soundjay.com/buttons/beep-01a.mp3" preload="auto"></audio>
        
        <div class="max-w-[1600px] mx-auto">
            <div class="flex justify-between items-center mb-6 glass p-5 rounded-3xl shadow-2xl">
                <div>
                    <h1 class="text-2xl font-black tracking-tighter text-blue-400 italic">EAGLE VISION <span class="text-white">PRO V4</span></h1>
                    <div class="flex items-center gap-2 text-[10px] text-slate-400 uppercase tracking-widest mt-1">
                        <span class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span> System Live & Optimized
                    </div>
                </div>
                <div class="flex gap-3">
                    <button onclick="exportExcel()" class="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-xl font-bold text-sm transition-all shadow-lg flex items-center gap-2">
                        <i class="fas fa-file-export"></i> Export Report
                    </button>
                    <button onclick="resetCounter()" class="bg-slate-700 hover:bg-red-600 px-4 py-2 rounded-xl font-bold text-sm transition-all border border-slate-600">
                        <i class="fas fa-sync-alt"></i> Reset
                    </button>
                </div>
            </div>

            <div class="grid grid-cols-12 gap-6">
                <div class="col-span-12 lg:col-span-8 space-y-6">
                    <div class="relative bg-black rounded-3xl overflow-hidden shadow-2xl border-4 border-slate-800">
                        <img src="{{ url_for('video_feed') }}" class="w-full">
                        <div id="alert-ui" class="hidden absolute top-6 left-6 bg-red-600/90 text-white px-6 py-3 rounded-2xl font-black animate-bounce shadow-2xl border border-red-400">
                             <i class="fas fa-biohazard mr-2"></i> VIOLATION DETECTED
                        </div>
                    </div>

                    <div class="grid grid-cols-4 gap-4">
                        <div class="glass p-5 rounded-2xl">
                            <p class="text-slate-500 text-[10px] uppercase font-bold mb-1">Total Violations</p>
                            <h2 id="total-v" class="text-4xl font-black text-blue-400">0</h2>
                        </div>
                        <div class="glass p-5 rounded-2xl">
                            <p class="text-slate-500 text-[10px] uppercase font-bold mb-1">Processing Delay</p>
                            <h2 class="text-xl font-bold text-green-400 italic">< 0.1s</h2>
                        </div>
                        <div class="glass p-5 rounded-2xl">
                            <p class="text-slate-500 text-[10px] uppercase font-bold mb-1">AI Confidence</p>
                            <h2 class="text-xl font-bold text-cyan-400">98.4%</h2>
                        </div>
                        <div class="glass p-5 rounded-2xl">
                            <p class="text-slate-500 text-[10px] uppercase font-bold mb-1">Safety Status</p>
                            <h2 id="compliance-text" class="text-xl font-bold text-green-400">SECURE</h2>
                        </div>
                    </div>
                </div>

                <div class="col-span-12 lg:col-span-4 space-y-6">
                    <div class="glass rounded-3xl overflow-hidden shadow-2xl border border-slate-700">
                        <div class="p-4 border-b border-slate-700 bg-slate-800/50 flex justify-between items-center">
                            <h3 class="text-xs font-black uppercase tracking-widest text-orange-400"><i class="fas fa-fire mr-2"></i> Worker Heatmap</h3>
                            <span class="text-[9px] text-slate-500">Live Density</span>
                        </div>
                        <div class="p-2 bg-slate-900/50">
                            <img id="heatmap-img" src="/api/heatmap" class="w-full rounded-xl opacity-90 hover:opacity-100 transition-opacity">
                        </div>
                    </div>

                    <div class="glass rounded-3xl flex flex-col h-[350px] shadow-2xl border border-slate-700">
                        <div class="p-4 border-b border-slate-700 bg-slate-800/50">
                            <h3 class="text-xs font-black uppercase tracking-widest text-slate-300">Activity Log</h3>
                        </div>
                        <div id="logs" class="p-4 space-y-3 overflow-y-auto log-container flex-grow"></div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let lastViolationCount = 0;
            function refresh() {
                fetch('/api/violations').then(r => r.json()).then(data => {
                    document.getElementById('total-v').innerText = data.total;
                    if (data.total > lastViolationCount) {
                        document.getElementById('alarm-sound').play();
                        document.getElementById('alert-ui').classList.remove('hidden');
                        setTimeout(() => document.getElementById('alert-ui').classList.add('hidden'), 3000);
                    }
                    lastViolationCount = data.total;
                    const logs = document.getElementById('logs');
                    logs.innerHTML = data.data.slice().reverse().map(v => `
                        <div class="p-3 bg-slate-800/50 rounded-xl border border-slate-700 text-[11px]">
                            <div class="flex justify-between text-slate-500 mb-1">
                                <span class="text-red-400">#${v.id}</span> <span>${v.timestamp}</span>
                            </div>
                            <div class="text-slate-300">Unsafe Hand-to-Pizza Contact</div>
                        </div>
                    `).join('');
                });
                document.getElementById('heatmap-img').src = "/api/heatmap?t=" + new Date().getTime();
            }
            function exportExcel() { window.location.href = '/api/export'; }
            function resetCounter() { if(confirm('Reset all data?')) fetch('/api/reset', { method: 'POST' }).then(() => refresh()); }
            setInterval(refresh, 2000);
        </script>
    </body>
    </html>
    """)

# API routes
@app.route('/api/heatmap')
def get_heatmap():
    try:
        conn = sqlite3.connect(config.DB_NAME)
        df = pd.read_sql_query("SELECT x, y FROM movements", conn)
        conn.close()
        if df.empty or len(df) < 2:
            img = np.zeros((400, 600, 3), dtype=np.uint8)
            _, buffer = cv2.imencode('.png', img); return Response(buffer.tobytes(), mimetype='image/png')
        plt.figure(figsize=(6, 4), facecolor='#0f172a')
        sns.kdeplot(x=df.x, y=df.y, fill=True, cmap="rocket", levels=50, thresh=0.1)
        plt.axis('off'); plt.tight_layout(pad=0)
        buf = io.BytesIO(); plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close('all'); buf.seek(0)
        return Response(buf.read(), mimetype='image/png')
    except Exception as e: return "", 204

@app.route('/api/export')
def export_data():
    try:
        conn = sqlite3.connect(config.DB_NAME)
        df = pd.read_sql_query("SELECT id, timestamp, frame_id FROM violations", conn)
        conn.close()
        file_path = os.path.abspath("Violation_Report.xlsx")
        df.to_excel(file_path, index=False)
        return send_file(file_path, as_attachment=True)
    except Exception as e: return str(e), 500

@app.route('/api/reset', methods=['POST'])
def reset_counter():
    conn = sqlite3.connect(config.DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM violations")
    c.execute("DELETE FROM movements")
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/violations')
def get_violations_api():
    conn = sqlite3.connect(config.DB_NAME)
    conn.row_factory = sqlite3.Row
    rows = conn.cursor().execute("SELECT * FROM violations").fetchall()
    conn.close()
    return jsonify({"total": len(rows), "data": [dict(r) for r in rows]})

@app.route('/video_feed')
def video_feed():
    def gen():
        while True:
            with lock:
                if latest_frame is None: continue
                _, buffer = cv2.imencode('.jpg', latest_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)