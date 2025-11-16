"""
数据帧结构定义模块
定义底层串口上传的数据帧结构，包含4个通道的ADC值、SDADC值、增益值等
支持数据帧的发送和订阅机制
"""

from dataclasses import dataclass
from typing import List, Set
from threading import Lock, Thread
import os
import time
from datetime import datetime
from DataParser.circular_buffer import CircularBuffer, BufferType

@dataclass
class ChannelData:
    """单个通道的数据结构"""
    adc: int  # ADC值 (2字节)
    sdadc0: int  # SDADC0值 (2字节)
    sdadc1: int  # SDADC1值 (2字节)
    adj0: int  # 增益值ADJ0 (1字节)
    adj1: int  # 增益值ADJ1 (1字节)
    current: float = 0.0  # 电流值 (4字节，浮点类型)


@dataclass
class DataFrame:
    """完整的数据帧结构"""
    # 帧头 (2字节)
    frame_header: bytes = b'\xA9\xB5'
    
    # 4个通道的数据 (每个通道: ADC+SDADC0+SDADC1+ADJ0+ADJ1 = 2+2+2+1+1 = 8字节)
    channels: List[ChannelData] = None
    
    # 主帧数据 (2字节)
    master_frame: int = 0
    
    # 子帧数据 (2字节)
    slave_frame: int = 0
    
    # 激光器状态 (1字节)
    lidar_state: int = 0
    
    # 帧尾 (1字节)
    frame_tail: bytes = b'\x33'
    
    def __post_init__(self):
        if self.channels is None:
            self.channels = [ChannelData(0, 0, 0, 0, 0, 0.0) for _ in range(4)]
    
    def __str__(self) -> str:
        """返回数据帧的字符串表示"""
        result = ["数据帧结构:"]
        result.append(f"帧头: {self.frame_header.hex()}")
        
        for i, channel in enumerate(self.channels):
            result.append(f"通道{i+1}: ADC={channel.adc}, SDADC0={channel.sdadc0}, "
                         f"SDADC1={channel.sdadc1}, ADJ0={channel.adj0}, ADJ1={channel.adj1}, "
                         f"Current={channel.current:.3f}")
        
        result.append(f"主帧: {self.master_frame}")
        result.append(f"子帧: {self.slave_frame}")
        result.append(f"激光器状态: {self.lidar_state}")
        result.append(f"帧尾: {self.frame_tail.hex()}")
        
        return "\n".join(result)
    



class DataFramePublisher:
    """数据帧发布管理器 - 处理数据帧的订阅和发布功能"""
    
    _instance = None
    _subscribers: Set = set()
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def subscribe(cls, buffer) -> bool:
        """
        订阅数据帧
        
        Args:
            buffer: 订阅者的环形缓冲区
            
        Returns:
            bool: 是否订阅成功
        """
        with cls._lock:
            if buffer in cls._subscribers:
                return False
            cls._subscribers.add(buffer)
            return True
    
    @classmethod
    def unsubscribe(cls, buffer) -> bool:
        """
        取消订阅数据帧
        
        Args:
            buffer: 要取消订阅的环形缓冲区
            
        Returns:
            bool: 是否取消订阅成功
        """
        with cls._lock:
            if buffer not in cls._subscribers:
                return False
            cls._subscribers.remove(buffer)
            return True
    
    @classmethod
    def publish(cls, frame: 'DataFrame') -> int:
        """
        发布数据帧到所有订阅者
        
        Args:
            frame: 要发布的数据帧
            
        Returns:
            int: 成功发布的订阅者数量
        """
        with cls._lock:
            success_count = 0
            for buffer in cls._subscribers:
                try:
                    # 使用环形缓冲区的write方法添加数据帧
                    # 注意：环形缓冲区的write方法期望bytes或list类型数据
                    # 这里我们使用list类型，包含单个数据帧
                    written = buffer.write([frame])
                    if written > 0:
                        success_count += 1
                except Exception:
                    # 单个订阅者失败不影响其他订阅者
                    continue
            return success_count
    
    @classmethod
    def get_subscriber_count(cls) -> int:
        """获取当前订阅者数量"""
        return len(cls._subscribers)


class DataFrameFileWriter:
    """数据帧文件写入器 - 将数据帧实时写入文件"""
    
    def __init__(self, output_dir: str, file_type: str = 'csv'):
        """
        初始化文件写入器
        
        Args:
            output_dir: 输出目录路径
            file_type: 文件类型 ('csv', 'xlsx', 'txt')
        """
        self.output_dir = output_dir
        self.file_type = file_type.lower()
        self.buffer = None
        self.running = False
        self.write_thread = None
        self.file_path = None
        
        # 验证文件类型
        if self.file_type not in ['csv', 'xlsx', 'txt']:
            raise ValueError(f"不支持的文件类型: {file_type}. 支持的类型: csv, xlsx, txt")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名（时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file_path = os.path.join(output_dir, f"data_frame_{timestamp}.{self.file_type}")
        
        # 初始化缓冲区并订阅
        self._init_buffer()
        
        # 启动写入线程
        self.start()
    
    def _init_buffer(self):
        
        # 创建写入模块的缓冲区
        self.buffer = CircularBuffer(buffer_type=BufferType.LIST)
        
        # 订阅数据帧
        DataFramePublisher.subscribe(self.buffer)
    
    def _write_to_file(self, frames: List['DataFrame']):
        """将数据帧写入文件"""
        if not frames:
            return
        
        try:
            if self.file_type == 'csv':
                self._write_csv(frames)
            elif self.file_type == 'xlsx':
                self._write_xlsx(frames)
            elif self.file_type == 'txt':
                self._write_txt(frames)
        except Exception as e:
            print(f"写入文件时出错: {e}")
    
    def _write_csv(self, frames: List['DataFrame']):
        """写入CSV文件"""
        import csv
        
        # 检查文件是否存在，如果不存在则写入表头
        file_exists = os.path.exists(self.file_path)
        
        with open(self.file_path, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # 如果文件不存在，写入表头
            if not file_exists:
                headers = ['timestamp', 'master_frame', 'slave_frame', 'lidar_state']
                for i in range(4):
                    headers.extend([f'ch{i+1}_adc', f'ch{i+1}_sdadc0', f'ch{i+1}_sdadc1', 
                                  f'ch{i+1}_adj0', f'ch{i+1}_adj1', f'ch{i+1}_current'])
                writer.writerow(headers)
            
            # 写入数据
            for frame in frames:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                row = [timestamp, frame.master_frame, frame.slave_frame, frame.lidar_state]
                
                for channel in frame.channels:
                    row.extend([channel.adc, channel.sdadc0, channel.sdadc1, 
                              channel.adj0, channel.adj1, channel.current])
                
                writer.writerow(row)
    
    def _write_xlsx(self, frames: List['DataFrame']):
        """写入Excel文件"""
        try:
            import openpyxl
        except ImportError:
            print("警告: openpyxl未安装，无法写入xlsx文件")
            return
        
        # 检查文件是否存在
        if os.path.exists(self.file_path):
            # 打开现有文件
            workbook = openpyxl.load_workbook(self.file_path)
            sheet = workbook.active
        else:
            # 创建新文件
            workbook = openpyxl.Workbook()
            sheet = workbook.active
            
            # 写入表头
            headers = ['timestamp', 'master_frame', 'slave_frame', 'lidar_state']
            for i in range(4):
                headers.extend([f'ch{i+1}_adc', f'ch{i+1}_sdadc0', f'ch{i+1}_sdadc1', 
                              f'ch{i+1}_adj0', f'ch{i+1}_adj1', f'ch{i+1}_current'])
            sheet.append(headers)
        
        # 写入数据
        for frame in frames:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            row = [timestamp, frame.master_frame, frame.slave_frame, frame.lidar_state]
            
            for channel in frame.channels:
                row.extend([channel.adc, channel.sdadc0, channel.sdadc1, 
                          channel.adj0, channel.adj1, channel.current])
            
            sheet.append(row)
        
        workbook.save(self.file_path)
    
    def _write_txt(self, frames: List['DataFrame']):
        """写入文本文件"""
        with open(self.file_path, 'a', encoding='utf-8') as txtfile:
            for frame in frames:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                txtfile.write(f"[{timestamp}] 数据帧:\n")
                txtfile.write(f"  主帧: {frame.master_frame}, 子帧: {frame.slave_frame}, 激光器状态: {frame.lidar_state}\n")
                
                for i, channel in enumerate(frame.channels):
                    txtfile.write(f"  通道{i+1}: ADC={channel.adc}, SDADC0={channel.sdadc0}, ")
                    txtfile.write(f"SDADC1={channel.sdadc1}, ADJ0={channel.adj0}, ADJ1={channel.adj1}, ")
                    txtfile.write(f"Current={channel.current:.3f}\n")
                
                txtfile.write("-" * 50 + "\n")
    
    def _write_loop(self):
        """写入线程的主循环"""
        while self.running:
            try:
                # 从缓冲区读取数据
                frames = self.buffer.read()
                if frames:
                    self._write_to_file(frames)
                
                # 短暂休眠，避免过度占用CPU
                time.sleep(0.1)
            except Exception as e:
                print(f"写入线程出错: {e}")
                time.sleep(1)  # 出错后等待更长时间
    
    def start(self):
        """启动写入线程"""
        if not self.running:
            self.running = True
            self.write_thread = Thread(target=self._write_loop, daemon=True)
            self.write_thread.start()
            print(f"文件写入器已启动，文件路径: {self.file_path}")
    
    def stop(self):
        """停止写入线程"""
        if self.running:
            self.running = False
            if self.write_thread:
                self.write_thread.join(timeout=5)
            
            # 取消订阅
            if self.buffer:
                DataFramePublisher.unsubscribe(self.buffer)
            
            print(f"文件写入器已停止，文件已保存到: {self.file_path}")
    
    def get_file_path(self) -> str:
        """获取当前文件路径"""
        return self.file_path


if __name__ == "__main__":
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
    
    print("原始数据帧:")
    print(frame)
    
    # 测试发送和订阅功能
    print("\n=== 测试发送和订阅功能 ===")
    
    # 创建两个环形缓冲区作为订阅者
    from DataParser.circular_buffer import CircularBuffer, BufferType
    
    # 创建显示模块的缓冲区
    display_buffer = CircularBuffer(buffer_type=BufferType.LIST)
    # 创建写入模块的缓冲区
    write_buffer = CircularBuffer(buffer_type=BufferType.LIST)
    
    # 测试新的文件写入功能
    print("\n=== 测试文件写入功能 ===")
    
    # 创建文件写入器
    file_writer = DataFrameFileWriter(output_dir="./output", file_type="csv")
    
    # 模拟发布一些数据帧
    for i in range(3):
        frame.master_frame = 0x1234 + i
        frame.slave_frame = 0x5678 + i
        frame.lidar_state = i % 2
        
        # 发布数据帧
        success_count = DataFramePublisher.publish(frame)
        print(f"发布第{i+1}个数据帧，成功发送到 {success_count} 个订阅者")
        
        # 等待一段时间让写入线程处理
        time.sleep(0.5)
    
    # 等待写入完成
    time.sleep(2)
    
    # 停止文件写入器
    file_writer.stop()
    
    print(f"文件写入测试完成，文件保存在: {file_writer.get_file_path()}")
    
    # 订阅数据帧
    DataFramePublisher.subscribe(display_buffer)
    DataFramePublisher.subscribe(write_buffer)
    
    print(f"订阅者数量: {DataFramePublisher.get_subscriber_count()}")
    
    # 发送数据帧
    success_count = DataFramePublisher.publish(frame)
    print(f"成功发送到 {success_count} 个订阅者")
    
    # 验证数据是否被正确添加到缓冲区
    print("\n验证显示模块缓冲区:")
    display_data = display_buffer.read()
    if display_data:
        print(f"显示模块收到数据帧: {len(display_data)} 个数据帧")
    else:
        print("显示模块未收到数据")
    
    print("\n验证写入模块缓冲区:")
    write_data = write_buffer.read()
    if write_data:
        print(f"写入模块收到数据帧: {len(write_data)} 个数据帧")
    else:
        print("写入模块未收到数据")
    
    # 取消订阅测试
    DataFramePublisher.unsubscribe(write_buffer)
    print(f"\n取消订阅后订阅者数量: {DataFramePublisher.get_subscriber_count()}")
    
    # 再次发送测试
    success_count = DataFramePublisher.publish(frame)
    print(f"第二次发送成功到 {success_count} 个订阅者")