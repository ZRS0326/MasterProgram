"""
数据帧结构定义模块
定义底层串口上传的数据帧结构，包含4个通道的ADC值、SDADC值、增益值等
支持数据帧的发送和订阅机制
"""

from dataclasses import dataclass
from typing import List, Set
from threading import Lock


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
    success_count = frame.send()
    print(f"第二次发送成功到 {success_count} 个订阅者")