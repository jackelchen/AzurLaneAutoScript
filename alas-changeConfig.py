#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Alas配置文件自动修改脚本
每天通过cron运行
功能：
1. 周三修改Daily和Hard任务下一次运行时间为12:00
2. 周五六修改SupplyLineDisruption和ModuleDevelopment为first（周四和其他时间改为skip）
3. 周五六修改CollectWeeklyMission为true（周四和其他时间改为false）

通过WebUI API控制程序启停，确保配置文件修改安全
"""

import json
import os
import shutil
import datetime
import glob
import sys
import requests
import time
import logging
import logging.handlers

def setup_logging():
    """配置日志系统"""
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(script_dir, "log", "alas-changeConfig.log")
    
    # 确保日志目录存在
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 创建logger
    logger = logging.getLogger('alas-changeConfig')
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

def check_alas_status(webui_url="http://192.168.1.100:28832", logger=None):
    """检查Alas程序运行状态"""
    try:
        response = requests.get(f"{webui_url}/api/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("running", False), data.get("state", "unknown")
        else:
            if logger:
                logger.warning(f"状态检查失败，HTTP状态码: {response.status_code}")
            return False, "unknown"
    except requests.exceptions.RequestException as e:
        if logger:
            logger.warning(f"无法连接到WebUI: {e}")
        return False, "unknown"

def stop_alas(webui_url="http://192.168.1.100:28832", logger=None):
    """停止Alas程序"""
    try:
        response = requests.post(f"{webui_url}/api/stop", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if logger:
                logger.info(f"{data.get('message', '程序已停止')}")
            return True
        else:
            if logger:
                logger.error(f"停止程序失败，HTTP状态码: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        if logger:
            logger.error(f"停止程序失败: {e}")
        return False

def start_alas(webui_url="http://192.168.1.100:28832", logger=None):
    """启动Alas程序"""
    try:
        response = requests.post(f"{webui_url}/api/start", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if logger:
                logger.info(f"{data.get('message', '程序已启动')}")
            return True
        else:
            if logger:
                logger.error(f"启动程序失败，HTTP状态码: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        if logger:
            logger.error(f"启动程序失败: {e}")
        return False

def main():
    # 初始化日志系统
    logger = setup_logging()
    
    logger.info("=" * 60)
    logger.info("开始执行Alas配置文件自动修改脚本")
    logger.info(f"执行时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    # WebUI地址
    webui_url = "http://192.168.1.100:28832"
    
    # 检查程序状态
    logger.info("检查Alas程序运行状态...")
    is_running, state = check_alas_status(webui_url, logger)
    logger.info(f"程序状态: {'运行中' if is_running else '未运行'} ({state})")
    
    # 如果程序正在运行，先停止程序
    was_running = is_running
    if is_running:
        logger.info("程序正在运行，先停止程序以确保配置文件修改安全...")
        if not stop_alas(webui_url, logger):
            logger.error("无法停止程序，脚本终止")
            sys.exit(1)
        
        # 等待程序完全停止
        logger.info("等待程序完全停止...")
        time.sleep(5)
    
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, "config", "alas.json")
    
    # 检查配置文件是否存在
    if not os.path.exists(config_file):
        logger.error(f"配置文件不存在: {config_file}")
        sys.exit(1)
    
    # 备份原配置文件
    backup_file = f"{config_file}.backup.{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        shutil.copy2(config_file, backup_file)
        logger.info(f"配置文件已备份到: {backup_file}")
    except Exception as e:
        logger.error(f"备份失败: {e}")
        sys.exit(1)
    
    # 读取配置文件
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        sys.exit(1)
    
    # 获取当前星期几 (1=周一, 2=周二, 3=周三, 4=周四, 5=周五, 6=周六, 7=周日)
    day_of_week = datetime.datetime.now().isoweekday()
    logger.info(f"当前星期: {day_of_week}")
    
    # 记录修改的字段
    modified_fields = []
    
    # 1. 如果是星期三(3)，修改 Daily 和 Hard 任务的 Scheduler.NextRun 的小时为 12
    # 注意：此功能已在 daily.py 和 hard.py 中自动实现，任务执行时会自动判断星期几设置下次执行时间
    # if day_of_week == 3:
    #     logger.info("今天是星期三，修改 Daily 和 Hard 任务的下一次运行时间为 12:00")
    #     
    #     # 修改Daily任务的NextRun
    #     if 'Daily' in config and 'Scheduler' in config['Daily']:
    #         old_time = config['Daily']['Scheduler']['NextRun']
    #         new_time = old_time.replace(' 00:', ' 12:')
    #         config['Daily']['Scheduler']['NextRun'] = new_time
    #         modified_fields.append(f"Daily.Scheduler.NextRun: {old_time} → {new_time}")
    #     
    #     # 修改Hard任务的NextRun
    #     if 'Hard' in config and 'Scheduler' in config['Hard']:
    #         old_time = config['Hard']['Scheduler']['NextRun']
    #         new_time = old_time.replace(' 00:', ' 12:')
    #         config['Hard']['Scheduler']['NextRun'] = new_time
    #         modified_fields.append(f"Hard.Scheduler.NextRun: {old_time} → {new_time}")
    #     
    #     logger.info("Daily.Scheduler.NextRun 和 Hard.Scheduler.NextRun 已修改为12:00")
    
    # 2. 修改 SupplyLineDisruption 破交作战（潜艇本） 和 ModuleDevelopment 兵装训练（兵装本）
    if day_of_week == 5 or day_of_week == 6:
        logger.info(f"今天是星期{day_of_week}，修改 SupplyLineDisruption 和 ModuleDevelopment 为first")
        
        # 修改SupplyLineDisruption
        if 'Daily' in config and 'Daily' in config['Daily']:
            old_value = config['Daily']['Daily'].get('SupplyLineDisruption', 'unknown')
            config['Daily']['Daily']['SupplyLineDisruption'] = 'first'
            modified_fields.append(f"Daily.SupplyLineDisruption: {old_value} → first")
        
        # 修改ModuleDevelopment
        if 'Daily' in config and 'Daily' in config['Daily']:
            old_value = config['Daily']['Daily'].get('ModuleDevelopment', 'unknown')
            config['Daily']['Daily']['ModuleDevelopment'] = 'first'
            modified_fields.append(f"Daily.ModuleDevelopment: {old_value} → first")
        
        logger.info("SupplyLineDisruption 和 ModuleDevelopment 已修改为first")
    else:
        logger.info(f"今天不是星期五、六，修改 SupplyLineDisruption 和 ModuleDevelopment 为skip")
        
        # 修改SupplyLineDisruption
        if 'Daily' in config and 'Daily' in config['Daily']:
            old_value = config['Daily']['Daily'].get('SupplyLineDisruption', 'unknown')
            config['Daily']['Daily']['SupplyLineDisruption'] = 'skip'
            modified_fields.append(f"Daily.SupplyLineDisruption: {old_value} → skip")
        
        # 修改ModuleDevelopment
        if 'Daily' in config and 'Daily' in config['Daily']:
            old_value = config['Daily']['Daily'].get('ModuleDevelopment', 'unknown')
            config['Daily']['Daily']['ModuleDevelopment'] = 'skip'
            modified_fields.append(f"Daily.ModuleDevelopment: {old_value} → skip")
        
        logger.info("SupplyLineDisruption 和 ModuleDevelopment 已修改为skip")
    
    # 3. 修改 CollectWeeklyMission 领取周任务奖励
    if day_of_week == 5 or day_of_week == 6:
        logger.info(f"今天是星期{day_of_week}，修改 Reward.CollectWeeklyMission 为 true")
        
        # 修改CollectWeeklyMission
        if 'Reward' in config and 'Reward' in config['Reward']:
            old_value = config['Reward']['Reward'].get('CollectWeeklyMission', 'unknown')
            config['Reward']['Reward']['CollectWeeklyMission'] = True
            modified_fields.append(f"Reward.CollectWeeklyMission: {old_value} → true")
        
        logger.info("CollectWeeklyMission 已修改为true")
    else:
        logger.info("今天不是星期五、六，修改CollectWeeklyMission为false")
        
        # 修改CollectWeeklyMission
        if 'Reward' in config and 'Reward' in config['Reward']:
            old_value = config['Reward']['Reward'].get('CollectWeeklyMission', 'unknown')
            config['Reward']['Reward']['CollectWeeklyMission'] = False
            modified_fields.append(f"Reward.CollectWeeklyMission: {old_value} → false")
        
        logger.info("CollectWeeklyMission 已修改为false")
    
    # 写回配置文件
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"写入配置文件失败: {e}")
        sys.exit(1)
    
    # 备份修改后的配置文件
    modified_backup_file = f"{config_file}.backup.{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.modified"
    try:
        shutil.copy2(config_file, modified_backup_file)
        logger.info(f"修改后的配置文件已备份到: {modified_backup_file}")
    except Exception as e:
        logger.error(f"备份修改后的配置文件失败: {e}")
    
    # 删除3天之前的备份文件（包括修改前和修改后的备份）
    logger.info("清理3天之前的备份文件...")
    backup_pattern = os.path.join(os.path.dirname(config_file), "alas.json.backup.*")
    deleted_count = 0
    
    for backup in glob.glob(backup_pattern):
        try:
            # 获取文件修改时间
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(backup))
            # 计算文件年龄
            file_age = datetime.datetime.now() - file_mtime
            
            if file_age.days > 3:
                os.remove(backup)
                deleted_count += 1
                logger.info(f"删除: {os.path.basename(backup)}")
        except Exception as e:
            logger.warning(f"删除备份文件失败 {backup}: {e}")
    
    if deleted_count > 0:
        logger.info(f"已清理 {deleted_count} 个3天之前的备份文件")
    else:
        logger.info("没有需要清理的备份文件")
    
    logger.info("配置文件修改完成！")
    
    # 如果之前程序在运行，重新启动程序
    if was_running:
        logger.info("重新启动Alas程序...")
        if not start_alas(webui_url, logger):
            logger.error("无法重新启动程序，请手动启动")
        else:
            logger.info("程序已重新启动")
    
    logger.info("-" * 60)
    logger.info("修改总结：")
    logger.info(f"- 当前星期: {day_of_week}")
    logger.info(f"- 程序状态: {'运行中 → 停止 → 修改 → 重新启动' if was_running else '未运行 → 直接修改'}")
    
    for field in modified_fields:
        logger.info(f"- {field}")
    
    logger.info("-" * 60)
    logger.info("脚本执行完成！")

if __name__ == "__main__":
    main()