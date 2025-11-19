"""
串口驱动实现 - 使用环形缓冲区和独立线程实现收发
核心功能：扫描串口、连接、断开、发送、接收
暴露缓冲区接口便于数据解析
"""

import serial
import serial.tools.list_ports
import threading
import time
from typing import Optional, Callable, List
from DataParser.circular_buffer import CircularBuffer, BufferType
from DataStructures.data_frame import DataFrame, ChannelData, DataFramePublisher, DataFrameFileWriter


class SimpleUart:
    """串口驱动类 - 使用环形缓冲区和独立线程实现收发"""
    
    def __init__(self, port: str, baudrate: int = 115200, buffer_size: int = 8192):
        """
        初始化串口驱动
        
        Args:
            port: 串口名称，如 'COM3'
            baudrate: 波特率，默认9600
            buffer_size: 缓冲区大小，默认8KB
        """
        self.port = port
        self.baudrate = baudrate
        
        # 串口对象
        self.serial: Optional[serial.Serial] = None
        
        # 使用独立的环形缓冲区
        self.rx_buffer = CircularBuffer(buffer_size)
        self.tx_buffer = CircularBuffer(buffer_size)
        
        # 线程控制
        self.running = False
        self.rx_thread: Optional[threading.Thread] = None
        self.tx_thread: Optional[threading.Thread] = None
        self.parse_thread: Optional[threading.Thread] = None

        # 回调函数
        self.data_received_callback: Optional[Callable[[bytes], None]] = None
        self.error_callback: Optional[Callable[[str], None]] = None
        self.frame_parsed_callback: Optional[Callable[[DataFrame], None]] = None

        # 统计信息
        self.rx_bytes = 0
        self.tx_bytes = 0
        self.errors = 0
    
    def open(self) -> bool:
        """打开串口连接"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0,  # 增加超时时间，确保接收完整帧
                write_timeout=1.0,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            
            self.running = True
            
            # 启动接收线程
            self.rx_thread = threading.Thread(target=self._rx_worker, daemon=True)
            self.rx_thread.start()
            
            # 启动发送线程
            self.tx_thread = threading.Thread(target=self._tx_worker, daemon=True)
            self.tx_thread.start()
            
            # 启动解析线程
            self.parse_thread = threading.Thread(target=self._parse_worker, daemon=True)
            self.parse_thread.start()
            
            print(f"串口 {self.port} 打开成功")
            return True
            
        except Exception as e:
            print(f"打开串口 {self.port} 失败: {e}")
            self._handle_error(f"打开失败: {e}")
            return False
    
    def close(self):
        """关闭串口连接"""
        self.running = False
        
        # 等待线程结束
        if self.rx_thread and self.rx_thread.is_alive():
            self.rx_thread.join(timeout=1.0)
        
        if self.tx_thread and self.tx_thread.is_alive():
            self.tx_thread.join(timeout=1.0)
        
        if self.parse_thread and self.parse_thread.is_alive():
            self.parse_thread.join(timeout=1.0)
        
        # 关闭串口
        if self.serial and self.serial.is_open:
            self.serial.close()
        
        # 清空缓冲区
        self.rx_buffer.clear()
        self.tx_buffer.clear()
        
        print(f"串口 {self.port} 已关闭")
    
    def send(self, data: bytes) -> bool:
        """
        发送数据
        
        Args:
            data: 要发送的字节数据
            
        Returns:
            是否成功加入发送缓冲区
        """
        if not self.running or not self.serial or not self.serial.is_open:
            return False

        written = self.tx_buffer.write(data)
        if written > 0:
            self.tx_bytes += written
            return True
        return False

    def receive(self, size: Optional[int] = None, timeout: float = 0.0) -> bytes:
        """
        接收数据

        Args:
            size: 要接收的数据大小，None表示接收所有可用数据
            timeout: 超时时间，0表示立即返回

        Returns:
            接收到的字节数据
        """
        if timeout <= 0:
            # 立即返回
            return self.rx_buffer.read(size)

        # 等待数据到达
        start_time = time.time()
        while time.time() - start_time < timeout:
            available = self.rx_buffer.get_available()
            if available > 0:
                if size is None:
                    return self.rx_buffer.read()
                elif available >= size:
                    return self.rx_buffer.read(size)
            time.sleep(0.001)  # 短暂休眠

        return b''


    def get_available(self) -> int:
        """获取接收缓冲区中的可用数据量"""
        return self.rx_buffer.get_available()

    def set_data_received_callback(self, callback: Callable[[bytes], None]):
        """设置数据接收回调函数"""
        self.data_received_callback = callback

    def set_error_callback(self, callback: Callable[[str], None]):
        """设置错误回调函数"""
        self.error_callback = callback

    def set_frame_parsed_callback(self, callback: Callable[[DataFrame], None]):
        """设置数据帧解析回调函数"""
        self.frame_parsed_callback = callback

    def is_open(self) -> bool:
        """检查串口是否打开"""
        return self.running and self.serial is not None and self.serial.is_open

    # 缓冲区访问接口 - 便于数据解析
    def get_rx_buffer(self) -> CircularBuffer:
        """获取接收缓冲区对象"""
        return self.rx_buffer

    def get_tx_buffer(self) -> CircularBuffer:
        """获取发送缓冲区对象"""
        return self.tx_buffer

    def peek_rx_data(self, size: Optional[int] = None) -> bytes:
        """查看接收缓冲区数据而不消费"""
        return self.rx_buffer.peek(size)

    def consume_rx_data(self, size: int) -> bool:
        """消费接收缓冲区数据"""
        return self.rx_buffer.consume(size)

    def clear_rx_buffer(self):
        """清空接收缓冲区"""
        self.rx_buffer.clear()

    def clear_tx_buffer(self):
        """清空发送缓冲区"""
        self.tx_buffer.clear()

    def _rx_worker(self):
        """接收数据工作线程"""
        while self.running and self.serial and self.serial.is_open:
            try:
                # 使用非阻塞读取，提高实时性
                if self.serial.in_waiting > 0:
                    data = self.serial.read(self.serial.in_waiting)

                    if data:
                        # 写入缓冲区
                        written = self.rx_buffer.write(data)
                        self.rx_bytes += written

                        # 调用回调函数
                        if self.data_received_callback and written > 0:
                            try:
                                self.data_received_callback(data)
                            except Exception as e:
                                self._handle_error(f"数据接收回调错误: {e}")
                else:
                    # 没有数据时短暂休眠，避免过度占用CPU
                    time.sleep(0.001)

            except Exception as e:
                self._handle_error(f"接收数据错误: {e}")
                time.sleep(0.1)  # 错误后短暂休眠

    def _tx_worker(self):
        """发送数据工作线程"""
        while self.running and self.serial and self.serial.is_open:
            try:
                # 检查发送缓冲区是否有数据
                available = self.tx_buffer.get_available()
                if available > 0:
                    # 读取数据并发送
                    data = self.tx_buffer.read(min(available, 1024))  # 每次最多发送1KB
                    if data:
                        self.serial.write(data)
                        self.serial.flush()  # 确保数据完全发送
                else:
                    # 没有数据，短暂休眠
                    time.sleep(0.001)

            except Exception as e:
                self._handle_error(f"发送数据错误: {e}")
                time.sleep(0.1)  # 错误后短暂休眠


    def _parse_data_frame(self, frame_data: bytes):
        """解析数据帧 - 传入的是去掉帧头的38字节数据"""
        try:
            # 数据帧结构(去掉帧头A9B5后): ADC数据(8字节) + SDADC数据(16字节) + ADJ数据(8字节) + 主帧(2字节) + 子帧(2字节) + 激光器状态(1字节) + 帧尾(1字节)
            # ADC数据: 4通道，每通道2字节 = 8字节 (字节0-7)
            # SDADC数据: 8通道，每通道2字节 = 16字节 (字节8-23) 
            # ADJ数据: 8通道，每通道1字节 = 8字节 (字节24-31)
            # 主帧: 2字节 (字节32-33)
            # 子帧: 2字节 (字节34-35)
            # 激光器状态: 1字节 (字节36)
            # 帧尾: 1字节 (字节37)
            
            # 创建数据帧对象
            data_frame = DataFrame()

            # adc[2134]
            data_frame.channels[1].adc = int.from_bytes(frame_data[0:2], byteorder='little', signed=True)
            data_frame.channels[0].adc = int.from_bytes(frame_data[2:4], byteorder='little', signed=True)
            data_frame.channels[2].adc = int.from_bytes(frame_data[4:6], byteorder='little', signed=True)
            data_frame.channels[3].adc = int.from_bytes(frame_data[6:8], byteorder='little', signed=True)
            # sdadc[CH1A,CH2A,CH3A,CH1B,CH2B,CH4A,CH3B,CH4B]
            data_frame.channels[0].sdadc0 = int.from_bytes(frame_data[8:10], byteorder='little', signed=True)
            data_frame.channels[0].sdadc1 = int.from_bytes(frame_data[14:16], byteorder='little', signed=True)
            data_frame.channels[1].sdadc0 = int.from_bytes(frame_data[10:12], byteorder='little', signed=True)
            data_frame.channels[1].sdadc1 = int.from_bytes(frame_data[16:18], byteorder='little', signed=True)
            data_frame.channels[2].sdadc0 = int.from_bytes(frame_data[12:14], byteorder='little', signed=True)
            data_frame.channels[2].sdadc1 = int.from_bytes(frame_data[20:22], byteorder='little', signed=True)
            data_frame.channels[3].sdadc0 = int.from_bytes(frame_data[18:20], byteorder='little', signed=True)
            data_frame.channels[3].sdadc1 = int.from_bytes(frame_data[22:24], byteorder='little', signed=True)

            # 解析ADJ数据 (8通道，每通道1字节)
            # ADJ0: 通道0-3 (字节24-27)
            # ADJ1: 通道4-7 (字节28-31)
            adj_base_offset = 24  # SDADC数据结束位置
            
            for i in range(4):
                # ADJ0值 (前4个通道)
                data_frame.channels[i].adj0 = frame_data[adj_base_offset + i]
                
                # ADJ1值 (后4个通道，但只取前4个对应通道)
                data_frame.channels[i].adj1 = frame_data[adj_base_offset + 4 + i]
            
            # Current值暂时设为0，因为数据中没有包含
            for i in range(4):
                data_frame.channels[i].current = (1000 * (data_frame.channels[i].sdadc0 + 32767) * 3300 / 65535)/((256 - data_frame.channels[i].adj0) * 3.92)
            
            # 解析主帧数据 (2字节)
            data_frame.master_frame = int.from_bytes(frame_data[32:34], byteorder='little')
            
            # 解析子帧数据 (2字节)
            data_frame.slave_frame = int.from_bytes(frame_data[34:36], byteorder='little')
            
            # 解析激光器状态 (1字节)
            data_frame.lidar_state = frame_data[36]
            
            # 验证帧尾是否为0x33
            if frame_data[37] != 0x33:
                self._handle_error(f"帧尾错误: 期望0x33，实际{frame_data[37]:02X}")
                return
            
            # 发布数据帧到订阅者
            DataFramePublisher.publish(data_frame)
            
            # 调用回调函数
            if hasattr(self, 'frame_parsed_callback') and self.frame_parsed_callback:
                self.frame_parsed_callback(data_frame)
            
            print(f"数据帧解析成功: 主帧={data_frame.master_frame:04X}, 子帧={data_frame.slave_frame:04X}")
            
        except Exception as e:
            self._handle_error(f"解析数据帧错误: {e}")

    def _handle_error(self, error_msg: str):
        """处理错误"""
        self.errors += 1
        print(f"[错误] {error_msg}")
        
        if self.error_callback:
            try:
                self.error_callback(error_msg)
            except Exception:
                pass

    def _parse_worker(self):
        """数据解析工作线程 - 简单的逐字节读取解析"""
        frame_state = 0  # 0: 寻找帧头, 1: 找到A9等待B5, 2: 找到05等待1C
        
        while self.running:
            try:
                # 逐字节读取
                byte_data = self.rx_buffer.read(1)
                if not byte_data:
                    time.sleep(0.001)
                    continue
                
                current_byte = byte_data[0]
                
                match frame_state:
                    case 0:  # 寻找帧头
                        if current_byte == 0xA9:
                            frame_state = 1  # 找到A9，进入状态1寻找B5
                        elif current_byte == 0x05:
                            frame_state = 2  # 找到05，进入状态2寻找1C
                    
                    case 1:  # 寻找数据帧第二个帧头字节B5
                        if current_byte == 0xB5:  # 找到完整帧头A9 B5
                            # 等待剩余38字节数据
                            while self.running and self.rx_buffer.get_available() < 38:
                                time.sleep(0.0001)

                            # 读取剩余数据
                            remaining_data = self.rx_buffer.read(38)
                            # 验证帧尾解析数据帧
                            if remaining_data[-1] == 0x33:
                                self._parse_data_frame(remaining_data)
                            else:
                                print(f"数据帧帧尾错误: {remaining_data[-1]:02X}")
                            frame_state = 0  # 重置状态，寻找下一帧
                        elif current_byte == 0xA9:  # 又遇到A9，可能是新帧的开始
                            # 保持状态为1，继续寻找B5
                            pass
                        elif current_byte == 0x05:  # 遇到05，切换到指令帧状态
                            frame_state = 2
                        else:  # 不是B5也不是A9或05，重置状态
                            frame_state = 0
                    
                    case 2:  # 寻找指令帧第二个帧头字节1C
                        if current_byte == 0x1C:  # 找到完整帧头05 1C
                            # 等待cmd_id和length字节
                            while self.running and self.rx_buffer.get_available() < 2:
                                time.sleep(0.001)
                            
                            if self.rx_buffer.get_available() >= 2:
                                # 读取cmd_id和length
                                header_data = self.rx_buffer.read(2)
                                cmd_id = header_data[0]
                                length = header_data[1]
                                
                                # 等待content和checksum字节
                                total_needed = length + 1  # content + checksum
                                while self.running and self.rx_buffer.get_available() < total_needed:
                                    time.sleep(0.001)
                                
                                if self.rx_buffer.get_available() >= total_needed:
                                    # 读取content和checksum
                                    content_checksum = self.rx_buffer.read(total_needed)
                                    content = content_checksum[:-1]
                                    received_checksum = content_checksum[-1]
                                    
                                    # 计算校验和
                                    calculated_checksum = sum([0x05, 0x1C, cmd_id, length] + list(content)) % 256
                                    
                                    if calculated_checksum == received_checksum:
                                        print(f"指令帧接收成功: cmd_id=0x{cmd_id:02X}, length={length}, checksum=0x{received_checksum:02X}")
                                        # 这里可以添加具体的指令处理逻辑
                                    else:
                                        print(f"指令帧校验错误: 计算值=0x{calculated_checksum:02X}, 接收值=0x{received_checksum:02X}")
                                else:
                                    print("指令帧数据不足")
                                
                                frame_state = 0  # 重置状态，寻找下一帧
                            else:
                                print("指令帧头数据不足")
                                frame_state = 0  # 重置状态
                        elif current_byte == 0x05:  # 又遇到05，可能是新帧的开始
                            # 保持状态为2，继续寻找1C
                            pass
                        elif current_byte == 0xA9:  # 遇到A9，切换到数据帧状态
                            frame_state = 1
                        else:  # 不是1C也不是05或A9，重置状态
                            frame_state = 0
                
            except Exception as e:
                self._handle_error(f"数据解析错误: {e}")
                time.sleep(0.1)


    def _handle_error(self, error_msg: str):
        """处理错误"""
        self.errors += 1
        print(f"串口错误: {error_msg}")

        if self.error_callback:
            try:
                self.error_callback(error_msg)
            except Exception as e:
                print(f"错误回调函数执行错误: {e}")

    def __enter__(self):
        """上下文管理器入口"""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


def scan_available_ports() -> List[str]:
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


def test_simple_uart():
    """测试串口驱动"""
    print("=== 串口驱动测试 ===")
    
    # 扫描可用串口
    print("1. 扫描可用串口")
    available_ports = scan_available_ports()
    if available_ports:
        print(f"可用串口: {available_ports}")
        # 选择第一个可用串口进行测试
        test_port = available_ports[1]
        print(f"选择串口: {test_port}")
    else:
        print("未找到可用串口，使用模拟端口")
        test_port = "COM1"
    
    # 创建串口实例
    uart = SimpleUart(test_port, 115200, 8192)  # 使用2KB缓冲区
    
    # 测试基本功能
    print("2. 测试缓冲区功能")
    
    # 测试环形缓冲区
    buffer = CircularBuffer(10)
    
    # 写入数据
    written = buffer.write(b'Hello')
    print(f"写入数据: {written} 字节")
    
    # 查看数据
    peek_data = buffer.peek()
    print(f"查看数据: {peek_data}")
    
    # 消费数据
    consumed = buffer.consume(2)
    print(f"消费2字节: {'成功' if consumed else '失败'}")
    
    # 读取数据
    read_data = buffer.read()
    print(f"读取数据: {read_data}")
    
    # 测试指针式操作
    buffer.write(b'1234567890')
    
    # 先查看前3个字节
    peek1 = buffer.peek(3)
    print(f"查看前3字节: {peek1}")
    
    # 消费2个字节
    buffer.consume(2)
    
    # 再查看剩余数据
    peek2 = buffer.peek()
    print(f"消费2字节后查看: {peek2}")
    
    print("3. 测试串口驱动")
    # 测试数据帧结构
    frame = DataFrame()

    # 设置测试数据
    frame.channels[0] = ChannelData(1000, 2000, 3000, 50, 60, 1.234)
    frame.channels[1] = ChannelData(1100, 2100, 3100, 51, 61, 2.345)
    frame.channels[2] = ChannelData(1200, 2200, 3200, 52, 62, 3.456)
    frame.channels[3] = ChannelData(1300, 2300, 3300, 53, 63, 4.567)
    frame.master_frame = 0x1234
    frame.slave_frame = 0x5678
    frame.lidar_state = 1
    # 打开串口
    if uart.open():
        print(f"串口状态: {'打开' if uart.is_open() else '关闭'}")
        display_buffer = CircularBuffer(buffer_type=BufferType.LIST)
        # file_writer = DataFrameFileWriter(output_dir="./output", file_type="csv")
        # write_buffer = CircularBuffer(buffer_type=BufferType.LIST)

        # 订阅数据帧
        DataFramePublisher.subscribe(display_buffer)
        
        # 开启一个线程，监控display_buffer，有数据就读取出来并打印
        import threading
        import time
        
        def monitor_display_buffer():
            """监控display_buffer的线程函数"""
            while True:
                # 检查display_buffer是否有数据
                if not display_buffer.is_empty():
                    data = display_buffer.read()
                    if data:
                        print(f"\n[显示模块] 收到数据帧: {len(data)} 个数据帧")
                        for i, frame_data in enumerate(data):
                            print(f"  数据帧 {i+1}: {frame_data}")
                
                # 短暂休眠，避免过度占用CPU
                time.sleep(0.5)
        
        # 启动监控线程
        monitor_thread = threading.Thread(target=monitor_display_buffer, daemon=True)
        monitor_thread.start()
        print("启动display_buffer监控线程...")
        
        # 设置数据接收回调
        def on_data_received(data):
            # DataFramePublisher.publish(data)
            print(repr(uart.get_rx_buffer()))
            # uart.get_rx_buffer().consume(len(data))
        uart.set_data_received_callback(on_data_received)
        
        print("\n串口通信控制台")
        print("输入要发送的数据（回车发送），输入 'quit' 退出：")
        
        try:
            while True:
                # 检查是否有新数据（非回调方式，作为备份）
                available = uart.get_available()
                if available > 0:
                    data = uart.receive()
                    if data:
                        try:
                            decoded_data = data.decode('utf-8', errors='ignore')
                            print(f"\n[直接接收] {decoded_data}")
                        except:
                            hex_data = data.hex()
                            print(f"\n[直接接收] 十六进制: {hex_data}")
                
                # 获取用户输入（非阻塞方式）
                try:
                    user_input = input(">>> ").strip()
                    
                    if user_input.lower() == 'quit':
                        break
                    
                    # 发送用户输入的数据
                    if user_input:
                        send_success = uart.send(user_input.encode('utf-8'))
                        if send_success:
                            print(f"[发送] {user_input}")
                        else:
                            print("[发送失败]")
                except KeyboardInterrupt:
                    print("\n用户中断，关闭串口...")
                    break
                
        except KeyboardInterrupt:
            print("\n用户中断，关闭串口...")
        finally:
            uart.close()
    else:
        print("串口打开失败，跳过后续测试")
    
    print("=== 测试完成 ===")


if __name__ == "__main__":
    test_simple_uart()