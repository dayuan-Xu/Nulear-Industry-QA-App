import logging

# 配置根 logger
# 过滤起点：这是日志消息的第一个过滤层
# 整体控制：控制整个 logger 系统接收哪些级别的日志消息
# 作用范围：影响所有通过此 logger 发出的消息
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# 统一配置：父 logger 的配置（级别、处理器）会被子 logger 继承
if not root_logger.handlers:
    # 输出过滤：这是第二个过滤层，决定特定输出目标接收哪些消息
    # 独立控制：可以为不同输出目标设置不同级别
    # 作用范围：只影响发送到特定输出设备的消息
    file_handler = logging.FileHandler("app.log")
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def get_logger(name):
    """直接获取已配置的 logger"""
    # 实际发出的日志消息 >= Logger 级别 （第一层过滤） >= Handler 级别 （第二层过滤）
    return logging.getLogger(name)