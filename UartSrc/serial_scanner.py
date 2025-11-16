"""
串口扫描器 - 自动检测可用串口
"""

import serial.tools.list_ports
from typing import List


class SerialScanner:
    """串口扫描器类"""
    
    def scan_ports(self) -> List[str]:
        """
        扫描所有可用串口
        
        Returns:
            可用串口名称列表
        """
        try:
            ports = serial.tools.list_ports.comports()
            port_names = []
            
            for port in ports:
                # 过滤掉一些虚拟串口和无效端口
                if port.device and not port.device.startswith('ttyS'):
                    port_names.append(port.device)
            
            return port_names
            
        except Exception as e:
            print(f"扫描串口时发生错误: {e}")
            return []