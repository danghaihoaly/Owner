#!/usr/bin/env python3
"""
WWTP Integration Module - SCADA & PLC Systems
==============================================

Supports integration with:
- Modbus TCP/RTU (Most PLCs)
- OPC UA (Siemens, Allen-Bradley, etc.)
- MQTT (IoT sensors)
- HTTP/REST APIs
- SQL Databases
- File-based (CSV, JSON)

Installation:
pip install pymodbus opcua-client paho-mqtt sqlalchemy requests

Usage:
python scada_integration.py --config config.yaml
"""

import asyncio
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import threading
from queue import Queue

# SCADA/PLC Libraries
try:
    from pymodbus.client import ModbusTcpClient, ModbusSerialClient
    from pymodbus.constants import Endian
    from pymodbus.payload import BinaryPayloadDecoder
    HAS_MODBUS = True
except ImportError:
    HAS_MODBUS = False
    print("⚠️  pymodbus not installed. Run: pip install pymodbus")

try:
    from opcua import Client as OPCUAClient
    HAS_OPCUA = True
except ImportError:
    HAS_OPCUA = False
    print("⚠️  opcua not installed. Run: pip install opcua")

try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False
    print("⚠️  paho-mqtt not installed. Run: pip install paho-mqtt")

try:
    from sqlalchemy import create_engine, Column, Float, DateTime, Integer, String
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker
    HAS_SQLALCHEMY = True
    Base = declarative_base()
except ImportError:
    HAS_SQLALCHEMY = False
    print("⚠️  sqlalchemy not installed. Run: pip install sqlalchemy")

import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SensorData:
    """Standardized sensor data format"""
    sensor_id: str
    timestamp: datetime
    value: float
    unit: str
    quality: str = "GOOD"  # GOOD, BAD, UNCERTAIN
    source: str = "unknown"
    
    def to_dict(self):
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }


class ModbusAdapter:
    """Adapter for Modbus TCP/RTU communication"""
    
    def __init__(self, host: str = 'localhost', port: int = 502, 
                 serial_port: Optional[str] = None, baudrate: int = 9600):
        """
        Initialize Modbus adapter
        
        Args:
            host: Modbus TCP host IP
            port: Modbus TCP port (default 502)
            serial_port: Serial port for Modbus RTU (e.g., '/dev/ttyUSB0')
            baudrate: Baudrate for Modbus RTU
        """
        if not HAS_MODBUS:
            raise ImportError("pymodbus not installed")
        
        self.host = host
        self.port = port
        
        if serial_port:
            self.client = ModbusSerialClient(
                method='rtu',
                port=serial_port,
                baudrate=baudrate,
                timeout=3
            )
            logger.info(f"Modbus RTU adapter initialized on {serial_port}")
        else:
            self.client = ModbusTcpClient(host=host, port=port, timeout=3)
            logger.info(f"Modbus TCP adapter initialized for {host}:{port}")
        
        self.connected = False
    
    def connect(self) -> bool:
        """Establish connection"""
        try:
            self.connected = self.client.connect()
            if self.connected:
                logger.info("✓ Modbus connection established")
            return self.connected
        except Exception as e:
            logger.error(f"Modbus connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close connection"""
        if self.client:
            self.client.close()
            self.connected = False
            logger.info("Modbus connection closed")
    
    def read_holding_registers(self, address: int, count: int = 1, 
                               unit: int = 1) -> Optional[List[int]]:
        """
        Read holding registers
        
        Args:
            address: Starting register address
            count: Number of registers to read
            unit: Modbus unit ID (slave ID)
        
        Returns:
            List of register values or None if error
        """
        try:
            result = self.client.read_holding_registers(
                address=address,
                count=count,
                unit=unit
            )
            
            if result.isError():
                logger.error(f"Modbus read error: {result}")
                return None
            
            return result.registers
        except Exception as e:
            logger.error(f"Error reading Modbus registers: {e}")
            return None
    
    def read_float(self, address: int, unit: int = 1, 
                   byte_order: str = 'big', word_order: str = 'big') -> Optional[float]:
        """
        Read 32-bit float from two registers
        
        Args:
            address: Starting register address
            unit: Modbus unit ID
            byte_order: 'big' or 'little'
            word_order: 'big' or 'little'
        """
        registers = self.read_holding_registers(address, count=2, unit=unit)
        
        if registers is None:
            return None
        
        # Convert to float
        byte_order_map = {'big': Endian.Big, 'little': Endian.Little}
        word_order_map = {'big': Endian.Big, 'little': Endian.Little}
        
        decoder = BinaryPayloadDecoder.fromRegisters(
            registers,
            byteorder=byte_order_map[byte_order],
            wordorder=word_order_map[word_order]
        )
        
        return decoder.decode_32bit_float()
    
    def write_register(self, address: int, value: int, unit: int = 1) -> bool:
        """Write single register"""
        try:
            result = self.client.write_register(address, value, unit=unit)
            return not result.isError()
        except Exception as e:
            logger.error(f"Error writing Modbus register: {e}")
            return False
    
    def read_sensor_map(self, sensor_map: Dict[str, Dict]) -> List[SensorData]:
        """
        Read multiple sensors based on configuration
        
        Args:
            sensor_map: Dictionary mapping sensor IDs to config
                {
                    'flow_rate': {'address': 100, 'type': 'float', 'unit': 'm3/h'},
                    'do_level': {'address': 102, 'type': 'float', 'unit': 'mg/L'}
                }
        """
        sensors = []
        timestamp = datetime.now()
        
        for sensor_id, config in sensor_map.items():
            address = config['address']
            data_type = config.get('type', 'int')
            unit = config.get('unit', '')
            modbus_unit = config.get('modbus_unit', 1)
            
            if data_type == 'float':
                value = self.read_float(address, unit=modbus_unit)
            else:
                registers = self.read_holding_registers(address, count=1, unit=modbus_unit)
                value = registers[0] if registers else None
            
            if value is not None:
                sensors.append(SensorData(
                    sensor_id=sensor_id,
                    timestamp=timestamp,
                    value=float(value),
                    unit=unit,
                    quality='GOOD',
                    source='modbus'
                ))
        
        return sensors


class OPCUAAdapter:
    """Adapter for OPC UA communication (Siemens, Allen-Bradley, etc.)"""
    
    def __init__(self, server_url: str = "opc.tcp://localhost:4840"):
        """
        Initialize OPC UA adapter
        
        Args:
            server_url: OPC UA server URL
        """
        if not HAS_OPCUA:
            raise ImportError("opcua not installed")
        
        self.server_url = server_url
        self.client = OPCUAClient(server_url)
        self.connected = False
        logger.info(f"OPC UA adapter initialized for {server_url}")
    
    def connect(self, username: Optional[str] = None, 
                password: Optional[str] = None) -> bool:
        """Establish connection"""
        try:
            if username and password:
                self.client.set_user(username)
                self.client.set_password(password)
            
            self.client.connect()
            self.connected = True
            logger.info("✓ OPC UA connection established")
            return True
        except Exception as e:
            logger.error(f"OPC UA connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close connection"""
        if self.client:
            self.client.disconnect()
            self.connected = False
            logger.info("OPC UA connection closed")
    
    def read_node(self, node_id: str) -> Optional[Any]:
        """
        Read value from OPC UA node
        
        Args:
            node_id: Node identifier (e.g., 'ns=2;i=2')
        """
        try:
            node = self.client.get_node(node_id)
            value = node.get_value()
            return value
        except Exception as e:
            logger.error(f"Error reading OPC UA node {node_id}: {e}")
            return None
    
    def write_node(self, node_id: str, value: Any) -> bool:
        """Write value to OPC UA node"""
        try:
            node = self.client.get_node(node_id)
            node.set_value(value)
            return True
        except Exception as e:
            logger.error(f"Error writing OPC UA node {node_id}: {e}")
            return False
    
    def read_sensor_map(self, sensor_map: Dict[str, Dict]) -> List[SensorData]:
        """
        Read multiple sensors from OPC UA
        
        Args:
            sensor_map: Dictionary mapping sensor IDs to node IDs
                {
                    'flow_rate': {'node_id': 'ns=2;i=100', 'unit': 'm3/h'},
                    'do_level': {'node_id': 'ns=2;i=101', 'unit': 'mg/L'}
                }
        """
        sensors = []
        timestamp = datetime.now()
        
        for sensor_id, config in sensor_map.items():
            node_id = config['node_id']
            unit = config.get('unit', '')
            
            value = self.read_node(node_id)
            
            if value is not None:
                sensors.append(SensorData(
                    sensor_id=sensor_id,
                    timestamp=timestamp,
                    value=float(value),
                    unit=unit,
                    quality='GOOD',
                    source='opcua'
                ))
        
        return sensors


class MQTTAdapter:
    """Adapter for MQTT communication (IoT sensors)"""
    
    def __init__(self, broker: str = 'localhost', port: int = 1883,
                 username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize MQTT adapter
        
        Args:
            broker: MQTT broker hostname
            port: MQTT broker port
            username: Optional username
            password: Optional password
        """
        if not HAS_MQTT:
            raise ImportError("paho-mqtt not installed")
        
        self.broker = broker
        self.port = port
        self.client = mqtt.Client()
        self.connected = False
        self.data_queue = Queue()
        
        if username and password:
            self.client.username_pw_set(username, password)
        
        # Setup callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        logger.info(f"MQTT adapter initialized for {broker}:{port}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected"""
        if rc == 0:
            self.connected = True
            logger.info("✓ MQTT connection established")
        else:
            logger.error(f"MQTT connection failed with code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            payload = json.loads(msg.payload.decode())
            self.data_queue.put({
                'topic': msg.topic,
                'payload': payload,
                'timestamp': datetime.now()
            })
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected"""
        self.connected = False
        logger.warning(f"MQTT disconnected with code {rc}")
    
    def connect(self) -> bool:
        """Establish connection"""
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 5
            start = time.time()
            while not self.connected and time.time() - start < timeout:
                time.sleep(0.1)
            
            return self.connected
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close connection"""
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False
        logger.info("MQTT connection closed")
    
    def subscribe(self, topics: List[str]):
        """Subscribe to topics"""
        for topic in topics:
            self.client.subscribe(topic)
            logger.info(f"Subscribed to MQTT topic: {topic}")
    
    def publish(self, topic: str, payload: Dict):
        """Publish message"""
        self.client.publish(topic, json.dumps(payload))
    
    def get_messages(self, timeout: float = 0.1) -> List[Dict]:
        """Get received messages"""
        messages = []
        try:
            while True:
                msg = self.data_queue.get(timeout=timeout)
                messages.append(msg)
        except:
            pass
        return messages


class DatabaseAdapter:
    """Adapter for SQL database integration"""
    
    class SensorReading(Base):
        """Database model for sensor readings"""
        __tablename__ = 'sensor_readings'
        
        id = Column(Integer, primary_key=True)
        sensor_id = Column(String(100))
        timestamp = Column(DateTime)
        value = Column(Float)
        unit = Column(String(50))
        quality = Column(String(20))
        source = Column(String(50))
    
    def __init__(self, connection_string: str):
        """
        Initialize database adapter
        
        Args:
            connection_string: SQLAlchemy connection string
                Examples:
                - PostgreSQL: 'postgresql://user:pass@localhost/dbname'
                - MySQL: 'mysql://user:pass@localhost/dbname'
                - SQLite: 'sqlite:///path/to/database.db'
                - SQL Server: 'mssql+pyodbc://user:pass@server/database'
        """
        if not HAS_SQLALCHEMY:
            raise ImportError("sqlalchemy not installed")
        
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        logger.info(f"Database adapter initialized")
    
    def write_sensor_data(self, sensor_data: SensorData) -> bool:
        """Write sensor data to database"""
        try:
            reading = self.SensorReading(
                sensor_id=sensor_data.sensor_id,
                timestamp=sensor_data.timestamp,
                value=sensor_data.value,
                unit=sensor_data.unit,
                quality=sensor_data.quality,
                source=sensor_data.source
            )
            self.session.add(reading)
            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error writing to database: {e}")
            self.session.rollback()
            return False
    
    def write_batch(self, sensor_data_list: List[SensorData]) -> bool:
        """Write multiple sensor readings"""
        try:
            readings = [
                self.SensorReading(**data.to_dict())
                for data in sensor_data_list
            ]
            self.session.bulk_save_objects(readings)
            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error writing batch to database: {e}")
            self.session.rollback()
            return False
    
    def read_latest(self, sensor_id: str) -> Optional[SensorData]:
        """Read latest value for a sensor"""
        try:
            reading = self.session.query(self.SensorReading)\
                .filter_by(sensor_id=sensor_id)\
                .order_by(self.SensorReading.timestamp.desc())\
                .first()
            
            if reading:
                return SensorData(
                    sensor_id=reading.sensor_id,
                    timestamp=reading.timestamp,
                    value=reading.value,
                    unit=reading.unit,
                    quality=reading.quality,
                    source=reading.source
                )
            return None
        except Exception as e:
            logger.error(f"Error reading from database: {e}")
            return None
    
    def execute_query(self, query: str) -> List[Dict]:
        """Execute custom SQL query"""
        try:
            result = self.session.execute(query)
            return [dict(row) for row in result]
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return []


class HTTPAdapter:
    """Adapter for REST API integration"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize HTTP adapter
        
        Args:
            base_url: Base URL for API
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {'Content-Type': 'application/json'}
        
        if api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'
        
        logger.info(f"HTTP adapter initialized for {base_url}")
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """GET request"""
        try:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"HTTP GET error: {e}")
            return None
    
    def post(self, endpoint: str, data: Dict) -> Optional[Dict]:
        """POST request"""
        try:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"HTTP POST error: {e}")
            return None
    
    def read_sensors(self, endpoint: str = '/sensors') -> List[SensorData]:
        """Read sensors from REST API"""
        data = self.get(endpoint)
        
        if not data:
            return []
        
        sensors = []
        for item in data.get('sensors', []):
            sensors.append(SensorData(
                sensor_id=item.get('id'),
                timestamp=datetime.fromisoformat(item.get('timestamp')),
                value=float(item.get('value')),
                unit=item.get('unit', ''),
                quality=item.get('quality', 'GOOD'),
                source='http'
            ))
        
        return sensors


class IntegrationManager:
    """Central manager for all integrations"""
    
    def __init__(self, config: Dict):
        """
        Initialize integration manager
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.adapters = {}
        self.running = False
        self.data_callbacks = []
        
        logger.info("Integration Manager initialized")
    
    def add_modbus(self, name: str, **kwargs):
        """Add Modbus adapter"""
        adapter = ModbusAdapter(**kwargs)
        self.adapters[name] = adapter
        logger.info(f"Added Modbus adapter: {name}")
    
    def add_opcua(self, name: str, **kwargs):
        """Add OPC UA adapter"""
        adapter = OPCUAAdapter(**kwargs)
        self.adapters[name] = adapter
        logger.info(f"Added OPC UA adapter: {name}")
    
    def add_mqtt(self, name: str, **kwargs):
        """Add MQTT adapter"""
        adapter = MQTTAdapter(**kwargs)
        self.adapters[name] = adapter
        logger.info(f"Added MQTT adapter: {name}")
    
    def add_database(self, name: str, **kwargs):
        """Add database adapter"""
        adapter = DatabaseAdapter(**kwargs)
        self.adapters[name] = adapter
        logger.info(f"Added database adapter: {name}")
    
    def add_http(self, name: str, **kwargs):
        """Add HTTP adapter"""
        adapter = HTTPAdapter(**kwargs)
        self.adapters[name] = adapter
        logger.info(f"Added HTTP adapter: {name}")
    
    def connect_all(self) -> bool:
        """Connect all adapters"""
        success = True
        for name, adapter in self.adapters.items():
            if hasattr(adapter, 'connect'):
                if not adapter.connect():
                    logger.error(f"Failed to connect adapter: {name}")
                    success = False
        return success
    
    def disconnect_all(self):
        """Disconnect all adapters"""
        for name, adapter in self.adapters.items():
            if hasattr(adapter, 'disconnect'):
                adapter.disconnect()
    
    def register_callback(self, callback):
        """Register data callback function"""
        self.data_callbacks.append(callback)
    
    def poll_sensors(self, sensor_config: Dict) -> List[SensorData]:
        """Poll all configured sensors"""
        all_data = []
        
        for adapter_name, sensors in sensor_config.items():
            if adapter_name not in self.adapters:
                continue
            
            adapter = self.adapters[adapter_name]
            
            if hasattr(adapter, 'read_sensor_map'):
                data = adapter.read_sensor_map(sensors)
                all_data.extend(data)
        
        # Call callbacks
        for callback in self.data_callbacks:
            callback(all_data)
        
        return all_data
    
    def start_polling(self, sensor_config: Dict, interval: float = 1.0):
        """Start continuous polling"""
        self.running = True
        
        def poll_loop():
            while self.running:
                try:
                    self.poll_sensors(sensor_config)
                    time.sleep(interval)
                except Exception as e:
                    logger.error(f"Polling error: {e}")
        
        thread = threading.Thread(target=poll_loop, daemon=True)
        thread.start()
        logger.info(f"Started polling with {interval}s interval")
    
    def stop_polling(self):
        """Stop polling"""
        self.running = False
        logger.info("Stopped polling")


def main():
    """Example usage"""
    print("=" * 70)
    print(" " * 15 + "WWTP SCADA Integration Demo")
    print("=" * 70)
    
    # Example configuration
    config = {
        'modbus': {
            'host': '192.168.1.10',
            'port': 502
        },
        'opcua': {
            'server_url': 'opc.tcp://192.168.1.20:4840'
        },
        'mqtt': {
            'broker': 'localhost',
            'port': 1883
        },
        'database': {
            'connection_string': 'sqlite:///wwtp_data.db'
        }
    }
    
    # Sensor mapping
    sensor_config = {
        'modbus_plc1': {
            'flow_rate': {'address': 100, 'type': 'float', 'unit': 'm3/h'},
            'do_aerobic': {'address': 102, 'type': 'float', 'unit': 'mg/L'},
            'mlss': {'address': 104, 'type': 'float', 'unit': 'mg/L'}
        },
        'opcua_scada': {
            'eff_cod': {'node_id': 'ns=2;i=100', 'unit': 'mg/L'},
            'eff_nh4': {'node_id': 'ns=2;i=101', 'unit': 'mg/L'}
        }
    }
    
    # Create integration manager
    manager = IntegrationManager(config)
    
    # Add adapters (commented out - enable as needed)
    # manager.add_modbus('modbus_plc1', **config['modbus'])
    # manager.add_opcua('opcua_scada', **config['opcua'])
    # manager.add_mqtt('mqtt_sensors', **config['mqtt'])
    manager.add_database('db', **config['database'])
    
    # Register callback
    def data_callback(sensor_data: List[SensorData]):
        print(f"\n📊 Received {len(sensor_data)} sensor readings:")
        for data in sensor_data:
            print(f"  {data.sensor_id}: {data.value} {data.unit}")
            
            # Write to database
            if 'db' in manager.adapters:
                manager.adapters['db'].write_sensor_data(data)
    
    manager.register_callback(data_callback)
    
    # Connect all
    print("\n🔌 Connecting to systems...")
    manager.connect_all()
    
    print("\n✓ Integration demo ready!")
    print("  Check the code for configuration examples")
    print("  Uncomment adapters in main() to enable them")
    
    # Cleanup
    manager.disconnect_all()


if __name__ == '__main__':
    main()
