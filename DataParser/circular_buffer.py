"""
环形缓冲区模块 - 独立于串口驱动
提供高效的字节流存储和指针式操作
支持多种数据结构和可配置的缓冲区大小
"""

import threading
from typing import Optional, Union, TypeVar, Generic
from enum import Enum


class BufferType(Enum):
    """缓冲区数据类型枚举"""
    BYTEARRAY = "bytearray"  # 字节数组，适合字节流
    LIST = "list"           # 列表，适合对象存储
    BYTES = "bytes"         # 字节对象，只读模式


T = TypeVar('T')


class CircularBuffer(Generic[T]):
    """环形缓冲区类，支持多种数据结构和可配置大小"""
    
    def __init__(self, size: int = 8192, buffer_type: BufferType = BufferType.BYTEARRAY):
        """
        初始化环形缓冲区
        
        Args:
            size: 缓冲区大小，默认8KB
            buffer_type: 缓冲区数据类型，默认字节数组
        """
        self.size = size
        self.buffer_type = buffer_type
        self.read_pos = 0
        self.write_pos = 0
        self.available = 0
        self.lock = threading.RLock()
        
        # 根据类型初始化缓冲区
        if buffer_type == BufferType.BYTEARRAY:
            self.buffer = bytearray(size)
        elif buffer_type == BufferType.LIST:
            self.buffer = [None] * size
        elif buffer_type == BufferType.BYTES:
            self.buffer = bytearray(size)
        else:
            raise ValueError(f"不支持的缓冲区类型: {buffer_type}")
    
    def write(self, data: Union[bytes, list]) -> int:
        """
        写入数据到缓冲区
        
        Args:
            data: 要写入的数据，可以是bytes或list
            
        Returns:
            实际写入的数据量
        """
        with self.lock:
            if self.buffer_type == BufferType.BYTEARRAY or self.buffer_type == BufferType.BYTES:
                if not isinstance(data, (bytes, bytearray)):
                    raise TypeError("字节缓冲区只支持bytes或bytearray类型数据")
                data_len = len(data)
            else:
                if not isinstance(data, list):
                    raise TypeError("列表缓冲区只支持list类型数据")
                data_len = len(data)
            
            if data_len == 0:
                return 0
            
            # 计算可写入空间
            free_space = self.size - self.available
            if free_space < data_len:
                # 空间不足，只写入部分数据
                data_len = free_space
                data = data[:data_len]
            
            if data_len == 0:
                return 0
            
            # 写入数据
            remaining = data_len
            while remaining > 0:
                # 计算从write_pos到缓冲区末尾的空间
                space_to_end = self.size - self.write_pos
                chunk_size = min(remaining, space_to_end)
                
                # 复制数据
                start_idx = data_len - remaining
                if self.buffer_type == BufferType.BYTEARRAY or self.buffer_type == BufferType.BYTES:
                    self.buffer[self.write_pos:self.write_pos + chunk_size] = data[start_idx:start_idx + chunk_size]
                else:
                    for i in range(chunk_size):
                        self.buffer[self.write_pos + i] = data[start_idx + i]
                
                self.write_pos = (self.write_pos + chunk_size) % self.size
                remaining -= chunk_size
            
            self.available += data_len
            return data_len
    
    def read(self, size: Optional[int] = None) -> Union[bytes, list]:
        """
        从缓冲区读取数据（移动读指针）
        
        Args:
            size: 要读取的数据大小，None表示读取所有可用数据
            
        Returns:
            读取到的数据，类型取决于缓冲区类型
        """
        with self.lock:
            if self.available == 0:
                if self.buffer_type == BufferType.BYTEARRAY or self.buffer_type == BufferType.BYTES:
                    return b''
                else:
                    return []
            
            if size is None:
                size = self.available
            else:
                size = min(size, self.available)
            
            if size == 0:
                if self.buffer_type == BufferType.BYTEARRAY or self.buffer_type == BufferType.BYTES:
                    return b''
                else:
                    return []
            
            if self.buffer_type == BufferType.BYTEARRAY or self.buffer_type == BufferType.BYTES:
                result = bytearray()
            else:
                result = []
            
            remaining = size
            
            while remaining > 0:
                # 计算从read_pos到缓冲区末尾的数据量
                data_to_end = min(remaining, self.size - self.read_pos)
                
                # 复制数据
                if self.buffer_type == BufferType.BYTEARRAY or self.buffer_type == BufferType.BYTES:
                    result.extend(self.buffer[self.read_pos:self.read_pos + data_to_end])
                else:
                    result.extend(self.buffer[self.read_pos:self.read_pos + data_to_end])
                
                self.read_pos = (self.read_pos + data_to_end) % self.size
                remaining -= data_to_end
            
            self.available -= size
            
            if self.buffer_type == BufferType.BYTEARRAY:
                return bytes(result)
            elif self.buffer_type == BufferType.BYTES:
                return bytes(result)
            else:
                return result
    
    def peek(self, size: Optional[int] = None) -> Union[bytes, list]:
        """
        查看缓冲区数据但不移动读指针
        
        Args:
            size: 要查看的数据大小，None表示查看所有可用数据
            
        Returns:
            查看到的数据，类型取决于缓冲区类型
        """
        with self.lock:
            if self.available == 0:
                if self.buffer_type == BufferType.BYTEARRAY or self.buffer_type == BufferType.BYTES:
                    return b''
                else:
                    return []
            
            if size is None:
                size = self.available
            else:
                size = min(size, self.available)
            
            if size == 0:
                if self.buffer_type == BufferType.BYTEARRAY or self.buffer_type == BufferType.BYTES:
                    return b''
                else:
                    return []
            
            if self.buffer_type == BufferType.BYTEARRAY or self.buffer_type == BufferType.BYTES:
                result = bytearray()
            else:
                result = []
            
            remaining = size
            temp_read_pos = self.read_pos
            
            while remaining > 0:
                data_to_end = min(remaining, self.size - temp_read_pos)
                
                if self.buffer_type == BufferType.BYTEARRAY or self.buffer_type == BufferType.BYTES:
                    result.extend(self.buffer[temp_read_pos:temp_read_pos + data_to_end])
                else:
                    result.extend(self.buffer[temp_read_pos:temp_read_pos + data_to_end])
                
                temp_read_pos = (temp_read_pos + data_to_end) % self.size
                remaining -= data_to_end
            
            if self.buffer_type == BufferType.BYTEARRAY:
                return bytes(result)
            elif self.buffer_type == BufferType.BYTES:
                return bytes(result)
            else:
                return result
    
    def consume(self, size: int) -> bool:
        """
        消费指定大小的数据（移动读指针但不返回数据）
        
        Args:
            size: 要消费的数据大小
            
        Returns:
            是否成功消费
        """
        with self.lock:
            if size <= 0:
                return False
            
            if self.available < size:
                return False
            
            # 移动读指针
            self.read_pos = (self.read_pos + size) % self.size
            self.available -= size
            return True
    
    def get_available(self) -> int:
        """获取缓冲区中的可用数据量"""
        with self.lock:
            return self.available
    
    def get_free_space(self) -> int:
        """获取缓冲区的剩余空间"""
        with self.lock:
            return self.size - self.available
    
    def clear(self):
        """清空缓冲区"""
        with self.lock:
            self.read_pos = 0
            self.write_pos = 0
            self.available = 0
    
    def is_empty(self) -> bool:
        """检查缓冲区是否为空"""
        return self.available == 0
    
    def is_full(self) -> bool:
        """检查缓冲区是否已满"""
        return self.available == self.size
    
    def __str__(self) -> str:
        """字符串表示，显示缓冲区状态"""
        return f"CircularBuffer(size={self.size}, available={self.available}, free={self.get_free_space()})"
    
    def __repr__(self) -> str:
        """调试表示，显示详细缓冲区内容"""
        with self.lock:
            if self.available == 0:
                return f"CircularBuffer(size={self.size}, available=0, data=[])"
            
            # 获取当前数据用于显示
            data = self.peek()
            
            if self.buffer_type == BufferType.BYTEARRAY or self.buffer_type == BufferType.BYTES:
                # 字节数据显示为十六进制
                hex_data = ' '.join(f'{b:02x}' for b in data)
                return f"CircularBuffer(size={self.size}, available={self.available}, data=[{hex_data}])"
            else:
                # 列表数据直接显示
                return f"CircularBuffer(size={self.size}, available={self.available}, data={data})"


def test_circular_buffer():

    """测试环形缓冲区功能"""
    print("=== 环形缓冲区测试 ===")

    # 创建缓冲区
    buffer = CircularBuffer(10)
    # 测试写入
    written = buffer.write(b'Hello')
    print(f"写入数据: {written} 字节")
    print(f"可用数据: {buffer.get_available()} 字节")

    print(repr(buffer))
    # 测试查看
    peek_data = buffer.peek()
    print(f"查看数据: {peek_data}")
    
    # 测试消费
    consumed = buffer.consume(2)
    print(f"消费2字节: {'成功' if consumed else '失败'}")
    print(f"消费后可用数据: {buffer.get_available()} 字节")
    
    # 测试读取
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
    
    # 测试边界情况
    print(f"缓冲区是否为空: {buffer.is_empty()}")
    print(f"缓冲区是否已满: {buffer.is_full()}")
    
    print("=== 测试完成 ===")


if __name__ == "__main__":
    test_circular_buffer()