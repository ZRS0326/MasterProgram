"""
数据结构定义模块
定义下位机数据帧和上位机指令帧的数据结构
"""

__version__ = "1.0.0"
__author__ = "MasterProgram"

from .circular_buffer import CircularBuffer, BufferType

__all__ = ['CircularBuffer', 'BufferType']