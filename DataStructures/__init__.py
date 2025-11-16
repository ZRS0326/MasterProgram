"""
数据结构模块包
包含数据帧结构和指令控制结构定义
"""

from .data_frame import DataFrame, ChannelData
from .command_frame import (
    UartControl,
    CommandConstants,
    CommandFrame,
    CommandDriver,
    CMD_FRAME_HEADER_LENGTH
)

__all__ = [
    # 数据帧结构
    'DataFrame',
    'ChannelData',
    # 'DataFramePublisher',
    
    # 指令控制结构
    'UartControl',
    'CommandConstants',
    'CommandFrame',
    'CommandDriver',
    'CMD_FRAME_HEADER_LENGTH'
]

__version__ = '1.0.0'
__author__ = 'MasterProgram'

# 模块描述
__doc__ = """
MasterProgram 数据结构模块

该模块提供了底层串口通信所需的数据结构定义：

1. 数据帧结构 (DataFrame):
   - 包含4个通道的ADC、SDADC、增益值
   - 主帧/子帧数据
   - 激光器状态
   - 支持字节流转换和解析

2. 指令控制结构 (CommandFrame):
   - 定义所有串口指令常量
   - 提供指令创建和解析方法
   - 支持批量参数设置和调试指令

使用示例:
    from DataStructures import DataFrame, CommandDriver
    
    # 创建数据帧
    frame = DataFrame()
    frame.channels[0].adc = 1000
    
    # 创建指令
    cmd = CommandDriver.create_read_command()
"""