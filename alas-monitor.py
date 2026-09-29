#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Alas程序监控脚本
每天通过cron运行（建议设置为每天凌晨1:00）
功能：
1. 检查Alas程序是否正在运行
2. 如果未运行，则通过WebUI API启动程序

通过WebUI API控制程序启停，确保操作安全
"""

import os
import sys
import requests
import datetime
import logging
import logging.handlers
import argparse


def setup_logging(log_dir=None):
    """配置日志系统，支持每周轮转"""
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 日志目录
    if log_dir is None:
        log_dir = os.path.join(script_dir, "log")
    
    # 确保日志目录存在
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, "alas-monitor.log")
    
    # 创建logger
    logger = logging.getLogger('alas-monitor')
    logger.setLevel(logging.INFO)
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    # 创建formatter
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-5s [%(process)d/%(threadName)s] %(filename)s:%(lineno)d %(funcName)s() - %(message)s"
    )
    
    # 文件handler - 每周轮转，保留4周
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when='W0', interval=1, backupCount=4, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # 控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 添加handler
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def check_alas_status(webui_url, logger=None):
    """检查Alas程序运行状态"""
    try:
        response = requests.get(f"{webui_url}/api/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if logger:
                logger.debug(f"API响应: {data}")
            return data.get("running", False), data.get("state", "unknown")
        else:
            if logger:
                logger.warning(f"状态检查失败，HTTP状态码: {response.status_code}")
            return False, "unknown"
    except requests.exceptions.RequestException as e:
        if logger:
            logger.warning(f"无法连接到WebUI: {e}")
        return False, "unknown"


def start_alas(webui_url, logger=None):
    """启动Alas程序"""
    try:
        response = requests.post(f"{webui_url}/api/start", timeout=30)
        if response.status_code == 200:
            data = response.json()
            if logger:
                logger.info(f"启动成功: {data.get('message', '程序已启动')}")
            return True
        else:
            if logger:
                logger.error(f"启动失败，HTTP状态码: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        if logger:
            logger.error(f"启动失败: {e}")
        return False


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Alas程序监控脚本")
    parser.add_argument(
        '-u', '--url',
        default="http://192.168.1.100:28832",
        help="WebUI地址，默认: http://192.168.1.100:28832"
    )
    parser.add_argument(
        '-l', '--log-dir',
        default=None,
        help="日志目录，默认: ./log"
    )
    
    args = parser.parse_args()
    
    # 初始化日志系统
    logger = setup_logging(args.log_dir)
    
    logger.info("=" * 60)
    logger.info("开始执行Alas程序监控脚本")
    logger.info(f"执行时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"WebUI地址: {args.url}")
    logger.info("=" * 60)
    
    # 检查程序状态
    logger.info("检查Alas程序运行状态...")
    is_running, state = check_alas_status(args.url, logger)
    logger.info(f"程序状态: {'运行中' if is_running else '未运行'} ({state})")
    
    if is_running:
        logger.info("Alas程序正在运行，无需操作")
        logger.info("-" * 60)
        logger.info("脚本执行完成！")
        return
    
    # 程序未运行，尝试启动
    logger.warning("Alas程序未运行，尝试启动...")
    if start_alas(args.url, logger):
        logger.info("Alas程序启动成功！")
    else:
        logger.error("Alas程序启动失败，请检查WebUI服务是否正常")
        sys.exit(1)
    
    logger.info("-" * 60)
    logger.info("脚本执行完成！")


if __name__ == "__main__":
    main()
