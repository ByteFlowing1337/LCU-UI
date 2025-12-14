import logging
import sys

def setup_logger(name="LCU-UI"):
    """
    配置并返回一个 logger 实例
    """
    logger = logging.getLogger(name)
    
    # 如果 logger 已经有 handlers，说明已经配置过，直接返回
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # 创建控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # 创建 formatter
    # 格式: [时间] [级别] [模块]: 消息
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d]: %(message)s',
        datefmt='%H:%M:%S'
    )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

# 创建一个默认的 logger 实例供其他模块直接使用
logger = setup_logger()
