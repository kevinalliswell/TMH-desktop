#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# PROJECT MADE WITH: Qt Designer and PySide6/Pycharm
"""
PROJECT MADE WITH: Qt Designer and PySide6/Pycharm
@Created on:        2024/5/8 11:46
@Author:            By Kevin/USTB
@Filename:          mfcCMQProtocol.py
@Projectname:       ProgrammingReduction
@Contact:           shijinpeng06@126.com
"""
"""
# 硬件设备型号：测试机型：CQM-V，测试设备：电源模块24v，测试接口：USB-RS485；正式设备型号：MQV0020BS/MQV0005BS
# @Description: 
# 1. 设备地址：01
# 2. 通信协议：Modbus-CPL
# 3. 接口类型：串口，波特率：19200，数据位：8，停止位：1，校验位：偶校验E
# 4. 读命令：0100XRS,1001W,29A\r\n
# 5. 写命令：0100XWS,1001W,2,65FE\r\n

# 数据地址：
1401~1408：SP0~SP7
1206-1207：分别对应SP和PV值
"""


def CPLSum(input_str):
    """
    计算给定字符串的校验和(Checksum)。

    这个函数首先将输入字符串编码为 UTF-8 字节序列,然后对所有字节求和。
    接着,它对求和结果执行按位取反、加 1 和截断到 8 位无符号整数的操作,
    以获得校验码。最后,将校验码转换为两个字符的十六进制字符串并返回。

    Args:
        input_str (str): 需要计算校验和的输入字符串。

    Returns:
        str: 一个长度为 2 的十六进制字符串,表示输入字符串的校验和。
    """
    byte_str = input_str.encode('utf-8')  # 将输入字符串编码为 UTF-8 字节序列
    sum_value = sum(byte_str)  # 对所有字节求和
    sum_value = (-(sum_value & 0xFF) & 0xFF)  # 按位取反、加 1 和截断到 8 位无符号整数
    hex_str = f"{sum_value:02X}"  # 将校验码转换为两个字符的十六进制字符串
    return hex_str


def create_read_command(device_add, data_add, num_bytes):
    """
    创建十进制格式的读命令
    """
    # 转换设备地址、数据存储地址和读数据长度为十进制字符串，并拼接命令
    device_add_str = f"{device_add:02X}"
    data_add_str = str(data_add).upper()
    num_bytes_str = str(num_bytes).upper()

    # 控制字为十六进制字符串，固定为0x03
    start_control_str = chr(0x02)
    end_control_str = chr(0x03)

    # 读命令示例："0100XRS,1001W,29A\r\n"
    rs_command_str = f"{start_control_str}{device_add_str:02}00XRS,{data_add_str}W,{num_bytes_str}{end_control_str}"

    # 计算校验和
    checksum = CPLSum(rs_command_str)

    # 完成命令电文，添加校验和、CR和LF
    command = f"{rs_command_str}{checksum:02}" + "\r\n"

    return command.encode()


def create_write_command(device_add, data_add, data_list):
    """
    创建十进制格式的写命令
    """
    # 转换地址为十进制字符串，并将数据列表转换为十进制字符串，用逗号分隔
    device_add_str = f"{device_add:02X}"
    data_add_str = str(data_add).upper()
    data_str = ','.join(str(d).upper() for d in data_list)

    # 控制字为十六进制字符串，固定为0x03
    start_control_str = chr(0x02)
    end_control_str = chr(0x03)

    # 写命令示例："0100XWS,1001W,2,65FE\r\n"
    ws_command_str = f"{start_control_str}{device_add_str:02}00XWS,{data_add_str}W,{data_str}{end_control_str}"

    # 计算校验和
    checksum = CPLSum(ws_command_str)

    # 完成命令电文，添加校验和、CR和LF
    command = f"{ws_command_str}{checksum:02}" + "\r\n"

    return command.encode()


def parse_response(response):
    """
    解析响应数据。

    Args:
        response (bytes): 接收到的响应数据

    Returns:
        float: 解析后的数值或 None 如果解析失败
    """
    try:
        # 移除起始和结束字符及换行符
        cleaned_data = response.strip(b'\x02\x03\r').decode('utf-8')

        # 分割数据
        parts = cleaned_data.split(',')

        if len(parts) >= 2:
            # 提取数据部分并转换为浮点数
            data_part = parts[1]
            value = float(data_part) / 10  # 假设协议要求数值缩小10倍
            return value

        return None

    except Exception as e:
        print(f"解析数据时出错: {e}")
        return None


def test_read_command():
    # 读数据测试示例
    device_id = 1  # 设备地址
    address_to_read = 1206  # 要读取的地址
    num_bytes_to_read = 2  # 要读取的字节数，这里读取2个字节，对应SP0设定流量值和PV瞬时流量值
    read_command = create_read_command(device_id, address_to_read, num_bytes_to_read)
    print("Decimal Read Command:", read_command)
    return read_command


def test_write_command():
    # 写数据测试示例
    device_id = 1  # 设备地址
    address_to_write = 1401  # 要写入的地址
    data_to_write = [12, 60]  # 要写入的数据，对应的SP0设定流量值为1.2L/min，SP1设定流量值为6L/min
    write_command = create_write_command(device_id, address_to_write, data_to_write)
    print("Decimal Write Command:", write_command)
    return write_command


def test_parse_response():
    """
    测试 parse_response 函数的各种场景
    """
    test_cases = [
        # 正常响应数据
        {
            "input": b'\x020100X20,30\x03F3\r\n',
            "expected_output": 3.0,
            "description": "正常响应，解析成功"
        },
        {
            "input": b'\x020500X00,52\x03EB\r\n',
            "expected_output": 5.2,
            "description": "正常响应，解析成功"
        },
        # 异常响应数据，数据格式不正确
        {
            "input": b'\x02\x19F',
            "expected_output": "异常响应: 响应格式错误 - b'\\x02\\x19F'",
            "description": "异常响应，数据格式不正确"
        },
        # 异常响应数据，缺少\x03
        {
            "input": b'\x020200X00,18',
            "expected_output": "异常响应: 响应格式错误 - b'\\x020200X00,18'",
            "description": "异常响应，缺少\x03"
        },
        # 正常响应，但解析数据不是浮点数
        {
            "input": b'\x020401X00,ABC\x03F2\r\n',
            "expected_output": "异常响应: 无法解析数据为数字 - b'\\x020401X00,ABC\\x03F2\\r\\n'",
            "description": "正常响应，但无法解析为浮点数"
        },
        # 缺少\x02和\x03
        {
            "input": b'Invalid data',
            "expected_output": "异常响应: 响应格式错误 - b'Invalid data'",
            "description": "无\x02和\x03的异常数据"
        }
    ]

    for case in test_cases:
        result = parse_response(case["input"])
        if result == case["expected_output"]:
            print(f"测试通过: {case['description']}")
        else:
            print(f"测试失败: {case['description']}\n  预期输出: {case['expected_output']}\n  实际输出: {result}")


if __name__ == '__main__':
    # test_read_command()
    # test_write_command()
    # 调用测试函数
    test_parse_response()
