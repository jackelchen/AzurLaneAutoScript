from module.logger import logger
from module.ui.ui import UI


class Battery(UI):
    def run(self):
        """
        Monitor device battery level and wait until battery is above threshold.
        """
        # 确保当前在主页面
        logger.info('确保当前在主页面')
        self.ui_goto_main()

        threshold = self.config.Battery_Threshold
        interval = self.config.Battery_Interval
        wait_time = self.config.Battery_WaitTime

        level = self.get_battery_level()
        if level is None:
            logger.warning('获取电量失败，1分钟后重试')
            self.device.sleep(60)
            level = self.get_battery_level()

        if level is None:
            logger.warning('仍然无法获取电量，任务完成')
            self.config.task_delay(minute=interval)
            return

        # 关键内容发三遍
        logger.info(f'====当前电量: {level}%, 设定阈值: {threshold}%====')
        logger.info(f'====当前电量: {level}%, 设定阈值: {threshold}%====')
        logger.info(f'====当前电量: {level}%, 设定阈值: {threshold}%====')

        if level >= threshold:
            logger.info('电量充足，任务完成')
            self.config.task_delay(minute=interval)
        else:
            logger.info(f'电量低于阈值，等待 {wait_time} 分钟')
            # 如果等待时间超过5分钟，每隔5分钟点击屏幕中心保持手机不锁屏
            if wait_time > 5:
                cycles = wait_time // 5
                remaining = wait_time % 5
                for i in range(cycles):
                    logger.info(f'等待第 {i+1}/{cycles} 个5分钟周期')
                    self.device.sleep(5 * 60)
                    # 使用ADB命令点击屏幕中心，避免使用device.click()
                    # 屏幕分辨率为 1280*780，中心坐标为 (640, 390)
                    self.device.adb_shell(['input', 'tap', '640', '390'])
                    logger.info('点击屏幕中心保持唤醒')
                if remaining > 0:
                    logger.info(f'等待剩余 {remaining} 分钟')
                    self.device.sleep(remaining * 60)
            else:
                self.device.sleep(wait_time * 60)
            
            next_delay = max(0, interval - wait_time)
            logger.info(f'任务完成，下次运行在 {next_delay} 分钟后')
            self.config.task_delay(minute=next_delay)

    def get_battery_level(self):
        """
        Get device battery level using dumpsys battery command.

        Returns:
            int: Battery level percentage (0-100), or None if failed to get
        """
        try:
            output = self.device.adb_shell(['dumpsys', 'battery'])
            for line in output.split('\n'):
                line = line.strip()
                if line.startswith('level:'):
                    level_str = line.split(':')[1].strip()
                    level = int(level_str)
                    return level
            logger.warning(f'Battery level not found in output: {output}')
            return None
        except Exception as e:
            logger.warning(f'Failed to get battery level: {e}')
            return None