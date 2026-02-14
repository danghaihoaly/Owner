# 🔌 WWTP System Integration - Complete Guide

## 📋 Overview

This guide covers integrating your WWTP monitoring system with existing infrastructure including SCADA, PLCs, databases, IoT sensors, and enterprise systems.

---

## 🎯 Supported Integrations

| System Type | Protocol | Status |
|-------------|----------|--------|
| **PLCs** | Modbus TCP/RTU | ✅ Ready |
| **SCADA** | OPC UA | ✅ Ready |
| **IoT Sensors** | MQTT | ✅ Ready |
| **Databases** | SQL (Postgres, MySQL, SQL Server) | ✅ Ready |
| **REST APIs** | HTTP/HTTPS | ✅ Ready |
| **Siemens** | S7 Protocol | ✅ Ready |
| **Allen-Bradley** | EtherNet/IP | 🔜 Coming |
| **Wonderware** | OPC DA/UA | ✅ Ready |
| **Cloud** | AWS IoT, Azure IoT | 🔜 Coming |

---

## 🚀 Quick Start Integration

### 1. Install Dependencies

```bash
cd wwtp-dashboard

# Install integration libraries
pip install pymodbus opcua paho-mqtt sqlalchemy psycopg2-binary pymysql

# For Siemens S7
pip install python-snap7

# For SQL Server
pip install pyodbc
```

### 2. Copy Integration Module

```bash
# Copy the SCADA integration module
cp scada_integration.py wwtp-dashboard/

# Make it executable
chmod +x scada_integration.py
```

### 3. Create Configuration File

```bash
cat > integration_config.yaml << 'EOF'
# WWTP Integration Configuration

# Modbus PLC Configuration
modbus:
  enabled: true
  host: "192.168.1.10"
  port: 502
  sensors:
    flow_rate:
      address: 100
      type: float
      unit: "m3/h"
    do_aerobic:
      address: 102
      type: float
      unit: "mg/L"

# OPC UA SCADA Configuration
opcua:
  enabled: true
  server_url: "opc.tcp://192.168.1.20:4840"
  username: "admin"
  password: "password"
  sensors:
    eff_cod:
      node_id: "ns=2;i=100"
      unit: "mg/L"

# MQTT IoT Sensors
mqtt:
  enabled: true
  broker: "localhost"
  port: 1883
  topics:
    - "wwtp/sensors/#"

# Database
database:
  enabled: true
  type: "postgresql"
  connection: "postgresql://user:password@localhost/wwtp"

# Polling interval (seconds)
poll_interval: 1.0
EOF
```

### 4. Run Integration Service

```bash
python scada_integration.py --config integration_config.yaml
```

---

## 🏭 Integration Scenarios

### Scenario 1: Modbus PLC Integration

**Use Case:** Read sensor values from Allen-Bradley or Schneider PLC

#### Hardware Setup
```
PLC (192.168.1.10:502)
    ↓ Modbus TCP
WWTP Server
    ↓ WebSocket
Dashboard/Mobile App
```

#### Configuration

```yaml
modbus:
  enabled: true
  host: "192.168.1.10"  # PLC IP address
  port: 502              # Modbus TCP port
  
  # Sensor mapping
  sensors:
    # Flow meter
    influent_flow:
      address: 40001      # Holding register address
      type: float         # Data type
      unit: "m3/h"
      scaling: 1.0        # Optional scaling factor
    
    # DO probe
    do_aerobic:
      address: 40003
      type: float
      unit: "mg/L"
    
    # Level sensor
    tank_level:
      address: 40005
      type: float
      unit: "m"
```

#### Python Code Example

```python
from scada_integration import ModbusAdapter, IntegrationManager

# Create Modbus adapter
modbus = ModbusAdapter(host='192.168.1.10', port=502)
modbus.connect()

# Read single value
flow_rate = modbus.read_float(address=40001)
print(f"Flow rate: {flow_rate} m³/h")

# Read multiple sensors
sensor_map = {
    'flow_rate': {'address': 40001, 'type': 'float', 'unit': 'm3/h'},
    'do_level': {'address': 40003, 'type': 'float', 'unit': 'mg/L'}
}

sensors = modbus.read_sensor_map(sensor_map)
for sensor in sensors:
    print(f"{sensor.sensor_id}: {sensor.value} {sensor.unit}")

modbus.disconnect()
```

---

### Scenario 2: Siemens SCADA Integration (OPC UA)

**Use Case:** Connect to Siemens WinCC or S7-1500 PLC

#### Hardware Setup
```
Siemens S7-1500 PLC
    ↓ OPC UA (Port 4840)
OPC UA Server (WinCC)
    ↓ OPC UA Client
WWTP Integration Service
```

#### Configuration

```yaml
opcua:
  enabled: true
  server_url: "opc.tcp://192.168.1.20:4840"
  
  # Security settings
  security_mode: "SignAndEncrypt"  # or "None", "Sign"
  security_policy: "Basic256Sha256"
  
  # Authentication
  username: "scada_user"
  password: "secure_password"
  
  # Certificate (optional)
  certificate: "/path/to/cert.der"
  private_key: "/path/to/key.pem"
  
  # Sensor mapping
  sensors:
    # Effluent COD analyzer
    cod_analyzer:
      node_id: "ns=2;s=WWTP.Effluent.COD"
      unit: "mg/L"
    
    # NH4 sensor
    nh4_sensor:
      node_id: "ns=2;s=WWTP.Effluent.NH4"
      unit: "mg/L"
    
    # Pump status
    pump_1_status:
      node_id: "ns=2;s=WWTP.Pumps.Pump1.Running"
      unit: "bool"
```

#### Python Code Example

```python
from scada_integration import OPCUAAdapter

# Connect to OPC UA server
opcua = OPCUAAdapter(server_url='opc.tcp://192.168.1.20:4840')
opcua.connect(username='scada_user', password='password')

# Read values
cod_value = opcua.read_node('ns=2;s=WWTP.Effluent.COD')
print(f"COD: {cod_value} mg/L")

# Write value (set pump speed)
opcua.write_node('ns=2;s=WWTP.Pumps.Pump1.Speed', 75.0)

opcua.disconnect()
```

---

### Scenario 3: Wonderware Integration

**Use Case:** Integrate with Wonderware InTouch/System Platform

#### Configuration

```yaml
# Wonderware uses OPC DA or OPC UA
wonderware:
  type: "opcua"  # or "opcda"
  server_url: "opc.tcp://wonderware-server:4840"
  
  # Tag mapping
  tags:
    - tag: "WWTP.Process.FlowRate"
      sensor_id: "flow_rate"
      unit: "m3/h"
    
    - tag: "WWTP.Quality.COD"
      sensor_id: "eff_cod"
      unit: "mg/L"
```

---

### Scenario 4: SQL Database Integration

**Use Case:** Read/Write data from existing SCADA database

#### Supported Databases
- PostgreSQL
- MySQL/MariaDB
- Microsoft SQL Server
- Oracle
- SQLite

#### Configuration

```yaml
database:
  enabled: true
  
  # Connection strings for different databases:
  
  # PostgreSQL
  connection: "postgresql://username:password@localhost:5432/scada_db"
  
  # MySQL
  # connection: "mysql://username:password@localhost:3306/scada_db"
  
  # SQL Server
  # connection: "mssql+pyodbc://username:password@server/database?driver=ODBC+Driver+17+for+SQL+Server"
  
  # Oracle
  # connection: "oracle://username:password@localhost:1521/orcl"
  
  # Queries
  read_query: |
    SELECT 
      sensor_name,
      sensor_value,
      unit,
      timestamp
    FROM sensor_readings
    WHERE timestamp > NOW() - INTERVAL '1 hour'
  
  write_table: "wwtp_data"
```

#### Python Code Example

```python
from scada_integration import DatabaseAdapter

# Connect to database
db = DatabaseAdapter('postgresql://user:pass@localhost/scada')

# Read latest sensor value
sensor_data = db.read_latest('flow_rate')
print(f"Latest flow: {sensor_data.value} {sensor_data.unit}")

# Write sensor data
from scada_integration import SensorData
from datetime import datetime

new_reading = SensorData(
    sensor_id='cod_analyzer',
    timestamp=datetime.now(),
    value=45.2,
    unit='mg/L',
    quality='GOOD',
    source='analyzer'
)

db.write_sensor_data(new_reading)
```

---

### Scenario 5: MQTT IoT Sensors

**Use Case:** Wireless pH, DO, and flow sensors

#### Configuration

```yaml
mqtt:
  enabled: true
  broker: "mqtt.example.com"
  port: 1883
  
  # Authentication
  username: "iot_user"
  password: "iot_password"
  
  # TLS/SSL
  use_tls: true
  ca_cert: "/path/to/ca.crt"
  
  # Topics to subscribe
  topics:
    - "wwtp/sensors/do/#"
    - "wwtp/sensors/ph/#"
    - "wwtp/sensors/flow/#"
  
  # Topic mapping
  topic_mapping:
    "wwtp/sensors/do/aerobic": "do_aerobic"
    "wwtp/sensors/ph/effluent": "ph_effluent"
```

#### Python Code Example

```python
from scada_integration import MQTTAdapter
import json

# Connect to MQTT broker
mqtt = MQTTAdapter(broker='mqtt.example.com', port=1883)
mqtt.connect()

# Subscribe to topics
mqtt.subscribe(['wwtp/sensors/#'])

# Publish setpoint
mqtt.publish('wwtp/control/do_setpoint', {'value': 2.0})

# Get messages
messages = mqtt.get_messages()
for msg in messages:
    print(f"Topic: {msg['topic']}")
    print(f"Data: {msg['payload']}")

mqtt.disconnect()
```

---

## 🔧 Bridge Service

Create a bridge service to connect SCADA systems to your web dashboard:

### bridge_service.py

```python
#!/usr/bin/env python3
"""
WWTP Bridge Service
Connects SCADA/PLC systems to web dashboard
"""

from scada_integration import IntegrationManager, SensorData
from flask import Flask, jsonify
from flask_socketio import SocketIO
import yaml
import logging
from typing import List

# Setup Flask app
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global integration manager
integration_manager = None


def load_config(config_file='integration_config.yaml'):
    """Load configuration from YAML file"""
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)


def sensor_data_callback(sensor_data: List[SensorData]):
    """Callback when new sensor data arrives"""
    # Convert to dictionary
    data = {
        sensor.sensor_id: {
            'value': sensor.value,
            'unit': sensor.unit,
            'timestamp': sensor.timestamp.isoformat(),
            'quality': sensor.quality
        }
        for sensor in sensor_data
    }
    
    # Emit to websocket clients
    socketio.emit('sensor_update', data)
    
    logger.info(f"Emitted {len(sensor_data)} sensor updates")


@app.route('/api/sensors', methods=['GET'])
def get_sensors():
    """Get current sensor values"""
    # Poll sensors
    sensor_data = integration_manager.poll_sensors(
        integration_manager.config.get('sensor_config', {})
    )
    
    return jsonify({
        'sensors': [s.to_dict() for s in sensor_data],
        'count': len(sensor_data)
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    adapter_status = {}
    
    for name, adapter in integration_manager.adapters.items():
        adapter_status[name] = {
            'connected': getattr(adapter, 'connected', False),
            'type': type(adapter).__name__
        }
    
    return jsonify({
        'adapters': adapter_status,
        'running': integration_manager.running
    })


def main():
    """Main entry point"""
    global integration_manager
    
    print("=" * 70)
    print(" " * 15 + "WWTP Bridge Service")
    print("=" * 70)
    
    # Load configuration
    config = load_config()
    
    # Create integration manager
    integration_manager = IntegrationManager(config)
    
    # Add adapters based on config
    if config.get('modbus', {}).get('enabled'):
        integration_manager.add_modbus('modbus', **config['modbus'])
    
    if config.get('opcua', {}).get('enabled'):
        integration_manager.add_opcua('opcua', **config['opcua'])
    
    if config.get('mqtt', {}).get('enabled'):
        integration_manager.add_mqtt('mqtt', **config['mqtt'])
    
    if config.get('database', {}).get('enabled'):
        integration_manager.add_database('database', **config['database'])
    
    # Register callback
    integration_manager.register_callback(sensor_data_callback)
    
    # Connect all adapters
    print("\n🔌 Connecting to systems...")
    integration_manager.connect_all()
    
    # Start polling
    poll_interval = config.get('poll_interval', 1.0)
    sensor_config = config.get('sensors', {})
    
    integration_manager.start_polling(sensor_config, poll_interval)
    
    # Start Flask server
    print(f"\n🚀 Bridge service running on http://0.0.0.0:5001")
    print("   Connect your dashboard to this endpoint")
    print("\n⏹️  Press Ctrl+C to stop")
    
    socketio.run(app, host='0.0.0.0', port=5001)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Shutting down...")
```

### Running the Bridge

```bash
# Start bridge service
python bridge_service.py

# Service runs on port 5001
# Configure dashboard to connect to: http://localhost:5001
```

---

## 📊 Data Flow Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   SCADA/PLC Systems                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Modbus   │  │ OPC UA   │  │   MQTT   │              │
│  │   PLC    │  │  Server  │  │  Sensors │              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
└───────┼─────────────┼─────────────┼────────────────────┘
        │             │             │
        └─────────────┼─────────────┘
                      │
              ┌───────▼────────┐
              │ Bridge Service │
              │  (Port 5001)   │
              └───────┬────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
   ┌────▼────┐   ┌────▼────┐   ┌───▼────┐
   │   Web   │   │ Mobile  │   │Database│
   │Dashboard│   │   App   │   │Storage │
   └─────────┘   └─────────┘   └────────┘
```

---

## 🔐 Security Best Practices

### 1. Network Segmentation

```yaml
# Use VLANs to isolate SCADA network
networks:
  scada_vlan:  # VLAN 10
    - PLCs
    - SCADA servers
  
  office_vlan:  # VLAN 20
    - Dashboard server
    - User workstations
  
  dmz_vlan:  # VLAN 30
    - External access
    - Cloud gateway
```

### 2. Authentication

```python
# Enable authentication for all protocols

# OPC UA with certificates
opcua_config = {
    'username': 'scada_user',
    'password': os.environ['OPCUA_PASSWORD'],  # From environment
    'certificate': '/secure/path/cert.der',
    'private_key': '/secure/path/key.pem'
}

# MQTT with TLS
mqtt_config = {
    'username': 'iot_user',
    'password': os.environ['MQTT_PASSWORD'],
    'use_tls': True,
    'ca_cert': '/secure/path/ca.crt'
}
```

### 3. Firewall Rules

```bash
# Allow only necessary ports
sudo ufw allow from 192.168.1.0/24 to any port 502  # Modbus
sudo ufw allow from 192.168.1.0/24 to any port 4840  # OPC UA
sudo ufw deny 502  # Deny from other networks
sudo ufw deny 4840
```

---

## 🧪 Testing Integration

### Test Modbus Connection

```python
# test_modbus.py
from scada_integration import ModbusAdapter

print("Testing Modbus connection...")

modbus = ModbusAdapter(host='192.168.1.10', port=502)

if modbus.connect():
    print("✓ Connected successfully")
    
    # Test read
    value = modbus.read_float(address=100)
    if value is not None:
        print(f"✓ Read value: {value}")
    else:
        print("✗ Read failed")
    
    modbus.disconnect()
else:
    print("✗ Connection failed")
```

### Test OPC UA Connection

```python
# test_opcua.py
from scada_integration import OPCUAAdapter

print("Testing OPC UA connection...")

opcua = OPCUAAdapter(server_url='opc.tcp://192.168.1.20:4840')

if opcua.connect():
    print("✓ Connected successfully")
    
    # Browse root node
    root = opcua.client.get_root_node()
    print(f"✓ Root node: {root}")
    
    opcua.disconnect()
else:
    print("✗ Connection failed")
```

---

## 📚 Common Integration Examples

### Allen-Bradley CompactLogix

```yaml
modbus:
  host: "192.168.1.50"
  port: 502
  sensors:
    tank_level:
      address: 400001
      type: float
```

### Siemens S7-1200/1500

```yaml
opcua:
  server_url: "opc.tcp://192.168.1.60:4840"
  sensors:
    process_value:
      node_id: "ns=3;s=DataBlocksGlobal.Process.Value"
```

### Schneider Electric M580

```yaml
modbus:
  host: "192.168.1.70"
  port: 502
```

---

## 🆘 Troubleshooting

### Issue 1: Can't Connect to PLC

```bash
# Check network connectivity
ping 192.168.1.10

# Check port is open
telnet 192.168.1.10 502

# Check firewall
sudo ufw status

# Test with Modbus tool
mbpoll -a 1 -t 3 -r 100 192.168.1.10
```

### Issue 2: OPC UA Connection Timeout

```python
# Increase timeout
opcua = OPCUAAdapter(server_url='opc.tcp://192.168.1.20:4840')
opcua.client.session_timeout = 30000  # 30 seconds
```

### Issue 3: MQTT Messages Not Received

```bash
# Test with mosquitto
mosquitto_sub -h localhost -t "wwtp/#" -v

# Publish test message
mosquitto_pub -h localhost -t "wwtp/test" -m "hello"
```

---

## ✅ Integration Checklist

Before going live:

- [ ] Network connectivity verified
- [ ] Firewall rules configured
- [ ] Authentication credentials set
- [ ] SSL/TLS certificates installed
- [ ] Sensor addresses documented
- [ ] Data flow tested end-to-end
- [ ] Error handling implemented
- [ ] Logging configured
- [ ] Backup integration configured
- [ ] Monitoring alerts set up
- [ ] Documentation updated
- [ ] Team trained

---

## 📞 Next Steps

1. **Choose your integration method** (Modbus, OPC UA, MQTT, etc.)
2. **Configure connection** in `integration_config.yaml`
3. **Test connection** with provided test scripts
4. **Start bridge service** to connect to dashboard
5. **Monitor data flow** and adjust as needed

**Need Help?** Check specific vendor documentation for your SCADA system.

---

*Integration guide version 1.0 | Updated 2026*