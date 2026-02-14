#!/bin/bash
# WWTP Real-Time Dashboard - Complete Deployment Script
# This script sets up everything needed for the web dashboard

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       WWTP Real-Time Dashboard - Auto Deployment              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
PROJECT_NAME="wwtp-dashboard"
PORT=5000

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found${NC}"

# Create project directory
echo ""
echo "📁 Creating project structure..."
mkdir -p $PROJECT_NAME/{templates,static/{css,js},data,logs}
cd $PROJECT_NAME

echo -e "${GREEN}✓ Project structure created${NC}"

# Create virtual environment
echo ""
echo "🐍 Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate

echo -e "${GREEN}✓ Virtual environment created${NC}"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
cat > requirements.txt << 'EOF'
flask==3.0.0
flask-cors==4.0.0
flask-socketio==5.3.5
python-socketio==5.10.0
numpy==1.26.4
pandas==2.2.1
eventlet==0.34.3
gunicorn==21.2.0
python-dotenv==1.0.0
EOF

pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create .env file
echo ""
echo "⚙️  Creating configuration files..."
cat > .env << EOF
FLASK_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
FLASK_ENV=development
PORT=$PORT
DEBUG=True
MAX_HISTORY=1000
EOF

echo -e "${GREEN}✓ Configuration files created${NC}"

# Create Flask backend (save to file)
echo ""
echo "🔧 Creating Flask backend..."
cat > flask_backend.py << 'BACKEND_EOF'
#!/usr/bin/env python3
"""Flask Backend for WWTP Dashboard"""

from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import numpy as np
import pandas as pd
from datetime import datetime
import threading
import time
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-key')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Simple simulator state
class Simulator:
    def __init__(self):
        self.running = False
        self.time = 0.0
        self.srt = 10.0
        self.mlr = 3.0
        self.do_aerobic = 2.0
        self.flow = 100.0
        self.history = []
        
    def step(self):
        self.time += 1
        hour = self.time % 24
        
        # Simulate influent variation
        inf_cod = 400 + 100 * np.sin(2 * np.pi * hour / 24) + np.random.normal(0, 20)
        inf_nh4 = 40 + 10 * np.sin(2 * np.pi * hour / 24) + np.random.normal(0, 3)
        
        # Simulate treatment
        eff_cod = inf_cod * np.exp(-0.1 * self.srt) + 20 + np.random.normal(0, 3)
        eff_nh4 = inf_nh4 * (1 - min(1, self.srt / 15) * 0.95) + np.random.normal(0, 0.3)
        eff_no3 = (inf_nh4 - eff_nh4) * (1 - min(1, self.mlr / 4) * 0.8) + np.random.normal(0, 0.5)
        eff_tn = eff_nh4 + eff_no3
        
        mlss = 2000 + self.srt * 120 + np.random.normal(0, 100)
        energy = self.do_aerobic * 100 + self.mlr * 50 + np.random.normal(0, 10)
        
        state = {
            'time': self.time,
            'inf_cod': float(inf_cod),
            'inf_nh4': float(inf_nh4),
            'eff_cod': float(eff_cod),
            'eff_nh4': float(eff_nh4),
            'eff_no3': float(eff_no3),
            'eff_tn': float(eff_tn),
            'mlss': float(mlss),
            'energy': float(energy),
            'srt': self.srt,
            'mlr': self.mlr,
            'do_aerobic': self.do_aerobic
        }
        
        self.history.append(state)
        if len(self.history) > 1000:
            self.history.pop(0)
            
        return state

sim = Simulator()

def simulation_worker():
    while sim.running:
        state = sim.step()
        socketio.emit('update', state)
        time.sleep(1)

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/status')
def status():
    if sim.history:
        return jsonify(sim.history[-1])
    return jsonify({'message': 'No data yet'})

@app.route('/api/start', methods=['POST'])
def start():
    if not sim.running:
        sim.running = True
        threading.Thread(target=simulation_worker, daemon=True).start()
    return jsonify({'status': 'started'})

@app.route('/api/stop', methods=['POST'])
def stop():
    sim.running = False
    return jsonify({'status': 'stopped'})

@app.route('/api/parameters', methods=['POST'])
def update_params():
    data = request.json
    if 'srt' in data:
        sim.srt = float(data['srt'])
    if 'mlr' in data:
        sim.mlr = float(data['mlr'])
    if 'do_aerobic' in data:
        sim.do_aerobic = float(data['do_aerobic'])
    return jsonify({'status': 'updated'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=os.getenv('DEBUG', 'True') == 'True')
BACKEND_EOF

chmod +x flask_backend.py
echo -e "${GREEN}✓ Flask backend created${NC}"

# Copy dashboard HTML to templates
echo ""
echo "🎨 Setting up dashboard..."
echo "Please paste the dashboard HTML into templates/dashboard.html"
echo "Or the script will create a basic version..."

# Create basic dashboard if needed
cat > templates/dashboard.html << 'HTML_EOF'
<!DOCTYPE html>
<html>
<head>
    <title>WWTP Dashboard</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
    <style>
        body { font-family: Arial; margin: 20px; background: #f0f0f0; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }
        .metric { background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 2em; font-weight: bold; color: #007bff; }
        .metric-label { font-size: 0.9em; color: #666; margin-top: 5px; }
        .controls { margin: 20px 0; }
        button { padding: 10px 20px; margin: 5px; border: none; border-radius: 5px; cursor: pointer; }
        .btn-start { background: #28a745; color: white; }
        .btn-stop { background: #dc3545; color: white; }
        canvas { max-height: 300px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏭 WWTP Real-Time Dashboard</h1>
        
        <div class="controls">
            <button class="btn-start" onclick="startSim()">▶ Start</button>
            <button class="btn-stop" onclick="stopSim()">⏹ Stop</button>
        </div>
        
        <div class="metrics">
            <div class="metric">
                <div class="metric-value" id="cod">--</div>
                <div class="metric-label">Effluent COD (mg/L)</div>
            </div>
            <div class="metric">
                <div class="metric-value" id="nh4">--</div>
                <div class="metric-label">NH4-N (mg/L)</div>
            </div>
            <div class="metric">
                <div class="metric-value" id="mlss">--</div>
                <div class="metric-label">MLSS (mg/L)</div>
            </div>
            <div class="metric">
                <div class="metric-value" id="energy">--</div>
                <div class="metric-label">Energy (kWh)</div>
            </div>
        </div>
        
        <canvas id="chart"></canvas>
    </div>
    
    <script>
        const socket = io();
        const ctx = document.getElementById('chart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'COD',
                    data: [],
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
        
        socket.on('update', (data) => {
            document.getElementById('cod').textContent = data.eff_cod.toFixed(1);
            document.getElementById('nh4').textContent = data.eff_nh4.toFixed(2);
            document.getElementById('mlss').textContent = data.mlss.toFixed(0);
            document.getElementById('energy').textContent = data.energy.toFixed(0);
            
            chart.data.labels.push(data.time);
            chart.data.datasets[0].data.push(data.eff_cod);
            if (chart.data.labels.length > 50) {
                chart.data.labels.shift();
                chart.data.datasets[0].data.shift();
            }
            chart.update('none');
        });
        
        function startSim() {
            fetch('/api/start', {method: 'POST'});
        }
        
        function stopSim() {
            fetch('/api/stop', {method: 'POST'});
        }
    </script>
</body>
</html>
HTML_EOF

echo -e "${GREEN}✓ Dashboard created${NC}"

# Create Dockerfile
echo ""
echo "🐳 Creating Docker configuration..."
cat > Dockerfile << 'DOCKERFILE_EOF'
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "flask_backend.py"]
DOCKERFILE_EOF

# Create docker-compose.yml
cat > docker-compose.yml << 'COMPOSE_EOF'
version: '3.8'

services:
  dashboard:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - FLASK_ENV=production
      - DEBUG=False
    restart: unless-stopped
COMPOSE_EOF

echo -e "${GREEN}✓ Docker configuration created${NC}"

# Create systemd service
echo ""
echo "⚙️  Creating systemd service..."
cat > wwtp-dashboard.service << EOF
[Unit]
Description=WWTP Dashboard
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin"
ExecStart=$(pwd)/venv/bin/python flask_backend.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓ Systemd service file created${NC}"

# Create launch scripts
echo ""
echo "🚀 Creating launch scripts..."

cat > start.sh << 'START_EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python flask_backend.py
START_EOF
chmod +x start.sh

cat > start-production.sh << 'PROD_EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:5000 flask_backend:app
PROD_EOF
chmod +x start-production.sh

echo -e "${GREEN}✓ Launch scripts created${NC}"

# Create README
echo ""
echo "📄 Creating documentation..."
cat > README.md << 'README_EOF'
# WWTP Real-Time Dashboard

## Quick Start

### Development
```bash
./start.sh
```

### Production
```bash
./start-production.sh
```

### Docker
```bash
docker-compose up -d
```

## Access

Dashboard: http://localhost:5000

## Configuration

Edit `.env` file to change settings.

## Systemd Service

```bash
sudo cp wwtp-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wwtp-dashboard
sudo systemctl start wwtp-dashboard
```
README_EOF

echo -e "${GREEN}✓ Documentation created${NC}"

# Create .gitignore
cat > .gitignore << 'GITIGNORE_EOF'
venv/
__pycache__/
*.pyc
.env
data/
logs/
*.log
.DS_Store
GITIGNORE_EOF

# Final summary
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  ✅ DEPLOYMENT COMPLETE!                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📁 Project created in: $(pwd)"
echo ""
echo "🚀 To start the dashboard:"
echo ""
echo "   Option 1 - Development:"
echo "   ------------------------"
echo "   ./start.sh"
echo ""
echo "   Option 2 - Production:"
echo "   ------------------------"
echo "   ./start-production.sh"
echo ""
echo "   Option 3 - Docker:"
echo "   ------------------------"
echo "   docker-compose up -d"
echo ""
echo "   Option 4 - Systemd Service:"
echo "   ------------------------"
echo "   sudo cp wwtp-dashboard.service /etc/systemd/system/"
echo "   sudo systemctl start wwtp-dashboard"
echo ""
echo "🌐 Access dashboard at: http://localhost:$PORT"
echo ""
echo "📚 Next steps:"
echo "   1. Review and customize .env"
echo "   2. Update templates/dashboard.html with full version"
echo "   3. Configure firewall if needed"
echo "   4. Set up reverse proxy (nginx) for production"
echo ""
echo "✅ Happy monitoring!"
echo ""
