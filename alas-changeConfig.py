#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Alas配置文件自动修改脚本
每天通过cron运行
功能：
1. 周五六修改 SupplyLineDisruption 和 ModuleDevelopment 为 first（周四和其他时间改为 skip）
2. 周五六修改 CollectWeeklyMission 为 true（周四和其他时间改为 false）

优先通过 WebUI /api/config 接口修改（无需停止程序），WebUI 不可达时回退直接写文件。
"""

import json
import os
import shutil
import datetime
import glob
import sys
import requests
import logging
import logging.handlers


def setup_logging():
    """配置日志系统"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(script_dir, "log", "alas-changeConfig.log")

    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger('alas-changeConfig')
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-5s [%(process)d/%(threadName)s] "
        "%(filename)s:%(lineno)d %(funcName)s() - %(message)s"
    )

    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when='W0', interval=1, backupCount=2, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def webui_available(webui_url, logger=None):
    """检查 WebUI /api/status 是否可达"""
    try:
        resp = requests.get(f"{webui_url}/api/status", timeout=5)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        if logger:
            logger.info("WebUI 不可达，将直接修改配置文件")
        return False


def set_config_via_api(webui_url, key, value, logger=None):
    """调用 /api/config 修改单个字段，返回 (success, old_value, new_value)"""
    try:
        resp = requests.post(
            f"{webui_url}/api/config",
            json={"key": key, "value": value},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                if logger:
                    logger.info(data.get("message", f"{key}: 已设置为 {value!r}"))
                return True, data.get("old_value"), data.get("new_value")
            else:
                if logger:
                    logger.error(f"接口返回失败: {data}")
                return False, None, None
        else:
            if logger:
                logger.error(f"接口 HTTP {resp.status_code}: {resp.text[:200]}")
            return False, None, None
    except requests.exceptions.RequestException as e:
        if logger:
            logger.error(f"接口请求异常: {e}")
        return False, None, None


def deep_set_in_file(config, keys, value):
    """在嵌套字典里设置值（点分路径，例如 'Daily.Daily.SupplyLineDisruption'）"""
    parts = keys.split('.')
    d = config
    for k in parts[:-1]:
        if k not in d or not isinstance(d[k], dict):
            d[k] = {}
        d = d[k]
    old = d.get(parts[-1], None)
    d[parts[-1]] = value
    return old, value


def modify_via_file(config_file, modifications, logger=None):
    """直接读文件修改，modifications 是 [(key_str, new_value), ...]"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        if logger:
            logger.error(f"读取配置文件失败: {e}")
        return False, []

    results = []
    for key, value in modifications:
        old, new = deep_set_in_file(config, key, value)
        if logger:
            logger.info(f"{key}: {old!r} → {new!r}")
        results.append((key, old, new))

    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True, results
    except Exception as e:
        if logger:
            logger.error(f"写入配置文件失败: {e}")
        return False, results


def backup_config(config_file, backup_dir, suffix, logger=None):
    """备份配置文件到指定目录，suffix 如 'before' 或 'modified'"""
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    filename = f"alas.json.{suffix}.{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_path = os.path.join(backup_dir, filename)
    try:
        shutil.copy2(config_file, backup_path)
        if logger:
            logger.info(f"配置文件已备份: {backup_path}")
        return True
    except Exception as e:
        if logger:
            logger.error(f"备份失败: {e}")
        return False


def cleanup_old_backups(backup_dir, logger=None):
    """删除备份目录中 3 天之前的备份文件"""
    if not os.path.exists(backup_dir):
        return
    deleted = 0
    for backup in glob.glob(os.path.join(backup_dir, "alas.json.*")):
        try:
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(backup))
            if (datetime.datetime.now() - mtime) > datetime.timedelta(days=3):
                os.remove(backup)
                deleted += 1
                if logger:
                    logger.info(f"清理旧备份: {os.path.basename(backup)}")
        except Exception as e:
            if logger:
                logger.warning(f"清理备份失败 {backup}: {e}")

    if logger:
        logger.info(f"共清理 {deleted} 个过期备份")


def main():
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("开始执行 Alas 配置文件自动修改脚本")
    logger.info(f"执行时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    webui_url = "http://192.168.1.100:28832"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, "config", "alas.json")
    backup_dir = os.path.join(os.path.dirname(config_file), "alas.json.backup")

    if not os.path.exists(config_file):
        logger.error(f"配置文件不存在: {config_file}")
        sys.exit(1)

    # ====== 1. 备份（修改前） ======
    if not backup_config(config_file, backup_dir, "before", logger):
        sys.exit(1)

    # ====== 2. 根据星期决定要改哪些字段 ======
    dow = datetime.datetime.now().isoweekday()  # 1=周一 .. 7=周日
    is_weekend = dow in (5, 6)

    if is_weekend:
        logger.info(f"今天是星期{dow}（周末），启用 first 模式")
        modifications = [
            ("Daily.Daily.SupplyLineDisruption", "first"),
            ("Daily.Daily.ModuleDevelopment", "first"),
            ("Reward.Reward.CollectWeeklyMission", True),
        ]
    else:
        logger.info(f"今天是星期{dow}（工作日），启用 skip 模式")
        modifications = [
            ("Daily.Daily.SupplyLineDisruption", "skip"),
            ("Daily.Daily.ModuleDevelopment", "skip"),
            ("Reward.Reward.CollectWeeklyMission", False),
        ]

    # ====== 3. 优先调用 WebUI /api/config ======
    use_api = webui_available(webui_url, logger)
    success_count = 0
    failed_fields = []

    if use_api:
        logger.info("WebUI 可达，使用 /api/config 接口修改（无需停止程序）")
        for key, value in modifications:
            ok, old, new = set_config_via_api(webui_url, key, value, logger)
            if ok:
                success_count += 1
            else:
                failed_fields.append((key, value))

        if failed_fields:
            logger.warning(f"接口修改失败 {len(failed_fields)} 项，回退到直接修改文件")
            file_ok, file_results = modify_via_file(config_file, failed_fields, logger)
            if file_ok:
                success_count += len(file_results)
    else:
        logger.info("直接修改配置文件")
        file_ok, file_results = modify_via_file(config_file, modifications, logger)
        if file_ok:
            success_count += len(file_results)

    # ====== 4. 备份（修改后） ======
    backup_config(config_file, backup_dir, "modified", logger)

    # ====== 5. 清理旧备份 ======
    cleanup_old_backups(backup_dir, logger)

    # ====== 6. 总结 ======
    logger.info("-" * 60)
    logger.info("修改总结：")
    logger.info(f"- 当前星期: {dow} {'（周末 first 模式）' if is_weekend else '（工作日 skip 模式）'}")
    logger.info(f"- 修改方式: {'WebUI /api/config' if use_api else '直接修改文件'}")
    logger.info(f"- 成功字段: {success_count}/{len(modifications)}")
    logger.info(f"- 备份目录: {backup_dir}")
    logger.info("-" * 60)
    logger.info("脚本执行完成！")


if __name__ == "__main__":
    main()
