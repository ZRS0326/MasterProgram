"""
指令控制结构定义模块
定义串口指令常量和方法接口，基于底层串口数据参考源码
"""

import struct
from dataclasses import dataclass
from typing import Optional


@dataclass
class UartControl:
    """串口控制参数结构"""
    # 串口上传时间 (2字节)
    uart_upload_time: int = 0
    
    # 自动增益调整时间 (2字节)
    adj_time: int = 0
    
    # 舵机单运转时间 (2字节)
    fashion_time: int = 0
    
    # 舵机位置参数 - 低位 (2字节)
    pos_low: int = 0
    
    # 舵机位置参数 - 高位 (2字节)
    pos_high: int = 0
    
    # 舵机位置参数 - 分度值 (2字节)
    pos_div: int = 0
    
    # 舵机位置参数 - 设置值 (2字节)
    pos_set: int = 0
    
    # 工作模式标志 (2字节)
    flag_mask: int = 0
    
    # 激光器开启延时 (2字节)
    lidar_time: int = 0
    
    def to_bytes(self) -> bytes:
        """将控制参数转换为字节流"""
        # 总字节数: 2*9 = 18字节
        return struct.pack('>HHHHHHHHH',
                          self.uart_upload_time,
                          self.adj_time,
                          self.fashion_time,
                          self.pos_low,
                          self.pos_high,
                          self.pos_div,
                          self.pos_set,
                          self.flag_mask,
                          self.lidar_time)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'UartControl':
        """从字节流解析控制参数"""
        if len(data) != 18:
            raise ValueError(f"控制参数长度应为18字节，实际收到{len(data)}字节")
        
        values = struct.unpack('>HHHHHHHHH', data)
        return cls(*values)


class CommandConstants:
    """指令常量定义"""
    
    # 指令帧头
    CMD_HEADER = bytes([0xA0, 0xB3])
    
    # 指令类型
    CMD_READ = 0x01  # 读取指令
    CMD_BATCH_WRITE = 0x02  # 批量写入指令
    CMD_SET_UART_FREQ = 0x03  # 设置串口发送频率
    CMD_SET_ADJ_FREQ = 0x04  # 设置自动增益频率
    CMD_SET_SERVO_TIME = 0x05  # 设置舵机单运转时间
    CMD_SET_SERVO_POS = 0x06  # 设置舵机运转位置参数
    CMD_SET_WORK_MODE = 0x07  # 设置工作模式
    CMD_SET_LIDAR_DELAY = 0x08  # 设置激光器开启延时
    
    # 调试指令
    CMD_DEBUG_IIC_READ = 0x11  # 调试IIC读命令
    CMD_DEBUG_IIC_WRITE = 0x12  # 调试IIC写命令
    CMD_DEBUG_SERVO_ONLINE = 0x13  # 调试舵机是否在线
    CMD_DEBUG_SET_SERVO_ANGLE = 0x14  # 调试设置舵机角度
    CMD_DEBUG_READ_SERVO_ANGLE = 0x15  # 调试读取舵机角度
    CMD_DEBUG_READ_DATA = 0x16  # 调试读取数据
    CMD_DEBUG_MONITOR_DATA = 0x17  # 调试监控数据
    
    # 带参数启动指令
    CMD_START_DEBUG_WITH_PARAMS = 0x21  # 带参数启动debug模式
    CMD_START_CMODE_WITH_PARAMS = 0x22  # 带参数启动cMode
    CMD_START_DMODE_WITH_PARAMS = 0x23  # 带参数启动dMode


class CommandFrame:
    """指令帧结构"""
    
    def __init__(self, command_type: int, data: Optional[bytes] = None):
        self.command_type = command_type
        self.data = data or b''
    
    def to_bytes(self) -> bytes:
        """将指令帧转换为字节流"""
        frame = bytearray()
        
        # 添加帧头
        frame.extend(CommandConstants.CMD_HEADER)
        
        # 添加指令类型
        frame.append(self.command_type)
        
        # 添加数据
        frame.extend(self.data)
        
        return bytes(frame)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'CommandFrame':
        """从字节流解析指令帧"""
        if len(data) < 3:
            raise ValueError("指令帧长度过短")
        
        # 验证帧头
        if data[0:2] != CommandConstants.CMD_HEADER:
            raise ValueError("指令帧头校验失败")
        
        command_type = data[2]
        command_data = data[3:] if len(data) > 3 else b''
        
        return cls(command_type, command_data)


class CommandDriver:
    """指令驱动方法接口"""
    
    @staticmethod
    def create_read_command() -> CommandFrame:
        """创建读取指令"""
        return CommandFrame(CommandConstants.CMD_READ)
    
    @staticmethod
    def create_batch_write_command(control_params: UartControl) -> CommandFrame:
        """创建批量写入指令"""
        return CommandFrame(CommandConstants.CMD_BATCH_WRITE, control_params.to_bytes())
    
    @staticmethod
    def create_set_uart_freq_command(upload_time: int) -> CommandFrame:
        """创建设置串口发送频率指令"""
        data = struct.pack('>H', upload_time)
        return CommandFrame(CommandConstants.CMD_SET_UART_FREQ, data)
    
    @staticmethod
    def create_set_adj_freq_command(adj_time: int) -> CommandFrame:
        """创建设置自动增益频率指令"""
        data = struct.pack('>H', adj_time)
        return CommandFrame(CommandConstants.CMD_SET_ADJ_FREQ, data)
    
    @staticmethod
    def create_set_servo_time_command(fashion_time: int) -> CommandFrame:
        """创建设置舵机单运转时间指令"""
        data = struct.pack('>H', fashion_time)
        return CommandFrame(CommandConstants.CMD_SET_SERVO_TIME, data)
    
    @staticmethod
    def create_set_servo_pos_command(pos_low: int, pos_high: int, 
                                   pos_div: int, pos_set: int) -> CommandFrame:
        """创建设置舵机运转位置参数指令"""
        data = struct.pack('>HHHH', pos_low, pos_high, pos_div, pos_set)
        return CommandFrame(CommandConstants.CMD_SET_SERVO_POS, data)
    
    @staticmethod
    def create_set_work_mode_command(flag_mask: int) -> CommandFrame:
        """创建工作模式设置指令"""
        data = struct.pack('>H', flag_mask)
        return CommandFrame(CommandConstants.CMD_SET_WORK_MODE, data)
    
    @staticmethod
    def create_set_lidar_delay_command(lidar_time: int) -> CommandFrame:
        """创建设置激光器开启延时指令"""
        data = struct.pack('>H', lidar_time)
        return CommandFrame(CommandConstants.CMD_SET_LIDAR_DELAY, data)
    
    @staticmethod
    def create_debug_iic_read_command(addr_index: int) -> CommandFrame:
        """创建调试IIC读命令"""
        data = bytes([addr_index])
        return CommandFrame(CommandConstants.CMD_DEBUG_IIC_READ, data)
    
    @staticmethod
    def create_debug_iic_write_command(addr_index: int, data0: int, data1: int) -> CommandFrame:
        """创建调试IIC写命令"""
        data = bytes([addr_index, data0, data1])
        return CommandFrame(CommandConstants.CMD_DEBUG_IIC_WRITE, data)
    
    @staticmethod
    def create_debug_servo_online_command(servo_id: int) -> CommandFrame:
        """创建调试舵机在线检测命令"""
        data = bytes([servo_id])
        return CommandFrame(CommandConstants.CMD_DEBUG_SERVO_ONLINE, data)
    
    @staticmethod
    def create_debug_set_servo_angle_command(servo_id: int, angle: int, time: int) -> CommandFrame:
        """创建调试设置舵机角度命令"""
        data = struct.pack('>bHH', servo_id, angle, time)
        return CommandFrame(CommandConstants.CMD_DEBUG_SET_SERVO_ANGLE, data)
    
    @staticmethod
    def create_debug_read_servo_angle_command(servo_id: int) -> CommandFrame:
        """创建调试读取舵机角度命令"""
        data = bytes([servo_id])
        return CommandFrame(CommandConstants.CMD_DEBUG_READ_SERVO_ANGLE, data)
    
    @staticmethod
    def create_debug_read_data_command(servo_id: int, cmd_id: int) -> CommandFrame:
        """创建调试读取数据命令"""
        data = bytes([servo_id, cmd_id])
        return CommandFrame(CommandConstants.CMD_DEBUG_READ_DATA, data)
    
    @staticmethod
    def create_debug_monitor_data_command(servo_id: int, cmd_id: int) -> CommandFrame:
        """创建调试监控数据命令"""
        data = bytes([servo_id, cmd_id])
        return CommandFrame(CommandConstants.CMD_DEBUG_MONITOR_DATA, data)
    
    @staticmethod
    def create_start_debug_with_params_command(flag_mask: int, pos_set: int, fashion_time: int) -> CommandFrame:
        """创建带参数启动debug模式命令"""
        data = struct.pack('>HHH', flag_mask, pos_set, fashion_time)
        return CommandFrame(CommandConstants.CMD_START_DEBUG_WITH_PARAMS, data)
    
    @staticmethod
    def create_start_cmode_with_params_command(flag_mask: int, pos_low: int, pos_high: int,
                                              fashion_time: int, lidar_time: int) -> CommandFrame:
        """创建带参数启动cMode命令"""
        data = struct.pack('>HHHHH', flag_mask, pos_low, pos_high, fashion_time, lidar_time)
        return CommandFrame(CommandConstants.CMD_START_CMODE_WITH_PARAMS, data)


# 指令帧长度常量
CMD_FRAME_HEADER_LENGTH = 3  # 帧头2字节 + 指令类型1字节


if __name__ == "__main__":
    # 测试指令控制结构
    
    # 创建控制参数
    control_params = UartControl(
        uart_upload_time=100,
        adj_time=200,
        fashion_time=300,
        pos_low=400,
        pos_high=500,
        pos_div=600,
        pos_set=700,
        flag_mask=0x1234,
        lidar_time=800
    )
    
    print("控制参数结构:")
    print(f"串口上传时间: {control_params.uart_upload_time}")
    print(f"自动增益时间: {control_params.adj_time}")
    print(f"舵机运转时间: {control_params.fashion_time}")
    print(f"位置低位: {control_params.pos_low}")
    print(f"位置高位: {control_params.pos_high}")
    print(f"位置分度: {control_params.pos_div}")
    print(f"位置设置: {control_params.pos_set}")
    print(f"工作模式: 0x{control_params.flag_mask:04X}")
    print(f"激光器延时: {control_params.lidar_time}")
    
    # 测试批量写入指令
    cmd_frame = CommandDriver.create_batch_write_command(control_params)
    byte_data = cmd_frame.to_bytes()
    
    print(f"\n批量写入指令字节流: {byte_data.hex()}")
    print(f"指令长度: {len(byte_data)} 字节")
    
    # 解析指令帧
    parsed_cmd = CommandFrame.from_bytes(byte_data)
    print(f"解析后的指令类型: 0x{parsed_cmd.command_type:02X}")
    print(f"指令数据长度: {len(parsed_cmd.data)} 字节")
    
    # 测试其他指令
    read_cmd = CommandDriver.create_read_command()
    print(f"\n读取指令: {read_cmd.to_bytes().hex()}")
    
    servo_cmd = CommandDriver.create_debug_set_servo_angle_command(1, 90, 1000)
    print(f"舵机角度设置指令: {servo_cmd.to_bytes().hex()}")