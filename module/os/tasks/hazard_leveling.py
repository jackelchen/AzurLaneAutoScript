from module.config.utils import get_os_reset_remain
from module.logger import logger
from module.os.map import OSMap
from module.os_handler.action_point import ActionPointLimit


class OpsiHazard1Leveling(OSMap):
    def os_hazard1_leveling(self):
        logger.hr('OS hazard 1 leveling', level=1)
        # Without these enabled, CL1 gains 0 profits
        self.config.override(
            OpsiGeneral_DoRandomMapEvent=True,
            OpsiGeneral_AkashiShopFilter='ActionPoint > PurpleCoins',
        )
        # 月末7天内（距大世界重置不足7天）才连带开启短猫相接，平时需手动开启
        if get_os_reset_remain() <= 6 \
                and not self.config.is_task_enabled('OpsiMeowfficerFarming'):
            self.config.cross_set(keys='OpsiMeowfficerFarming.Scheduler.Enable', value=True)
        # 平时保留600点行动力, 并遵循 get_action_point_limit()
        preserve = min(self.get_action_point_limit(), 600)
        while True:
            # 侵蚀1练级保留600点行动力
            self.config.OS_ACTION_POINT_PRESERVE = preserve
            if self.config.is_task_enabled('OpsiAshBeacon') \
                    and not self._ash_fully_collected \
                    and self.config.cross_get("OpsiAshBeacon.OpsiAshBeacon.EnsureFullyCollected", True):
                logger.info('Ash beacon not fully collected, ignore action point limit temporarily')
                self.config.OS_ACTION_POINT_PRESERVE = 0
            logger.attr('OS_ACTION_POINT_PRESERVE', self.config.OS_ACTION_POINT_PRESERVE)

            if self.get_yellow_coins() < self.yellow_coins_preserve:
                logger.info(f'Reach the limit of yellow coins, preserve={self.yellow_coins_preserve}')
                with self.config.multi_set():
                    self.config.task_delay(minute=60, server_update=True)
                    if not self.is_in_opsi_explore():
                        cd = self.nearest_task_cooling_down
                        if cd is None:
                            for task in ['OpsiAbyssal', 'OpsiStronghold', 'OpsiObscure']:
                                if self.config.is_task_enabled(task):
                                    self.config.task_call(task)
                        self.config.task_call('OpsiMeowfficerFarming', force_call=False)
                self.config.task_stop()

            self.get_current_zone()

            # Preset action point to 70
            # When running CL1 oil is for running CL1, not meowfficer farming
            keep_current_ap = True
            if self.config.OpsiGeneral_BuyActionPointLimit > 0:
                keep_current_ap = False
            try:
                self.action_point_set(cost=70, keep_current_ap=keep_current_ap, check_rest_ap=True)
            except ActionPointLimit:
                # 行动力已低于保底, 无法继续练级, 但仍需按规则处理短猫开关
                self.meowfficer_switch_by_action_point()
                raise

            self.meowfficer_switch_by_action_point()
            if self._action_point_total >= 3000:
                with self.config.multi_set():
                    self.config.task_delay(minute=60, server_update=True)
                    if not self.is_in_opsi_explore():
                        cd = self.nearest_task_cooling_down
                        if cd is None:
                            for task in ['OpsiAbyssal', 'OpsiStronghold', 'OpsiObscure']:
                                if self.config.is_task_enabled(task):
                                    self.config.task_call(task)
                        self.config.task_call('OpsiMeowfficerFarming', force_call=False)
                self.config.task_stop()

            if self.config.OpsiHazard1Leveling_TargetZone != 0:
                zone = self.config.OpsiHazard1Leveling_TargetZone
            else:
                zone = 22
            logger.hr(f'OS hazard 1 leveling, zone_id={zone}', level=1)
            if self.zone.zone_id != zone or not self.is_zone_name_hidden:
                self.globe_goto(self.name_to_zone(zone), types='SAFE', refresh=True)
            self.fleet_set(self.config.OpsiFleet_Fleet)
            self.run_strategic_search()

            self.handle_after_auto_search()
            self.config.check_task_switch()

    def meowfficer_switch_by_action_point(self):
        """
        按总行动力(当前行动力 + 箱子行动力)决定短猫相接的开关

        - 月末7天内: 不处理, 由月末规则保证开启
        - 总行动力 >= 3000: 开启
        - 总行动力 < 1000: 关闭
        - 1000 ~ 3000: 保持当前状态
        """
        if get_os_reset_remain() <= 6:
            return

        total = self._action_point_total
        enabled = self.config.is_task_enabled('OpsiMeowfficerFarming')

        if total >= 3000 and not enabled:
            logger.info(f'总行动力 {total} >= 3000, 开启短猫相接')
            self.config.cross_set(keys='OpsiMeowfficerFarming.Scheduler.Enable', value=True)
        elif total < 1000 and enabled:
            logger.info(f'总行动力 {total} < 1000, 关闭短猫相接')
            self.config.cross_set(keys='OpsiMeowfficerFarming.Scheduler.Enable', value=False)
