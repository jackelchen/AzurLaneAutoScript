from module.base.base import ModuleBase
from module.logger import logger


class Battery(ModuleBase):
    def run(self):
        """
        Monitor device battery level and wait until battery is above threshold.
        """
        threshold = self.config.Battery_Threshold
        interval = self.config.Battery_Interval

        while True:
            level = self.get_battery_level()
            if level is None:
                logger.warning('Failed to get battery level, retry in 1 minute')
                self.device.sleep(60)
                continue

            logger.info(f'Battery level: {level}%, threshold: {threshold}%')

            if level >= threshold:
                logger.info('Battery level is sufficient, task completed')
                self.config.task_delay(minute=interval)
                return
            else:
                logger.info(f'Battery level is below threshold, waiting {interval} minutes')
                self.device.sleep(interval * 60)

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