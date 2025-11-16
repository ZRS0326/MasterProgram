"""
串口通信系统集成测试
整合测试：串口驱动 + 环形缓冲区 + 数据结构
"""

import time
import threading
from UartSrc.simple_uart import SimpleUart
from DataParser.circular_buffer import CircularBuffer, BufferType
from DataStructures.data_frame import DataFrame, ChannelData
from DataStructures.command_frame import CommandDriver, UartControl, CommandFrame

# 扫描并返回需要打开的串口

# 打开串口（，波特率，buffer_size）

# 创建数据帧订阅缓冲区

# 订阅数据帧

# 指令控制逻辑


# 程序死循环运行

if __name__ == "__main__":
    # 运行集成测试
    print("\n所有测试完成！")