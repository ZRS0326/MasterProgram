"""
串口通信系统集成测试
整合测试：串口驱动 + 环形缓冲区 + 数据结构
"""
from UartSrc.simple_uart import SimpleUart, scan_available_ports
from DataParser.circular_buffer import CircularBuffer, BufferType
from DataStructures.data_frame import DataFrame, ChannelData, DataFramePublisher, DataFrameFileWriter
from DataStructures.command_frame import CommandDriver
import time
# 扫描并返回需要打开的串口
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
# 打开串口（，波特率，buffer_size）
if uart.open():
    print(f"串口状态: {'打开' if uart.is_open() else '关闭'}")
    display_buffer = CircularBuffer(buffer_type=BufferType.LIST)
    DataFramePublisher.subscribe(display_buffer)
    file_writer = DataFrameFileWriter(output_dir="./output", file_type="csv")
    # write_buffer = CircularBuffer(buffer_type=BufferType.LIST)
    print("\n串口通信控制台")
    print("输入要发送的数据（回车发送），输入 'quit' 退出：")
    cmd_frame =  CommandDriver.create_set_uart_freq_command(3)
    byte_data = cmd_frame.to_bytes()
    uart.send(byte_data)
    print(f"\n批量写入指令字节流: {byte_data.hex()}")
    print(f"指令长度: {len(byte_data)} 字节")

    time.sleep(0.001)  # 短暂休眠
    cmd_frame =  CommandDriver.create_set_work_mode_command(0x0000)
    byte_data = cmd_frame.to_bytes()
    uart.send(byte_data)
    print(f"\n批量写入指令字节流: {byte_data.hex()}")
    print(f"指令长度: {len(byte_data)} 字节")
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
    # 订阅数据帧
# 创建数据帧订阅缓冲区

# 订阅数据帧

# 指令控制逻辑


# 程序死循环运行

if __name__ == "__main__":
    # 运行集成测试
    print("\n所有测试完成！")