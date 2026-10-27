"""房间注册表。

预留 RoomStore 接口：日后要多进程部署，把它换成 Redis 实现即可，其余代码不动。
"""

from common.loggingCommon import get_logger
from realtime.room import RoomActor
from schemas.rule import RuleConfig

logger = get_logger("mahjong.manager")


class RoomManager:
    def __init__(self) -> None:
        self._actors: dict[str, RoomActor] = {}

    def get(self, code: str) -> RoomActor | None:
        return self._actors.get(code)

    def get_or_create(
        self, code: str, room_id: int, name: str, host_id: int, rule: RuleConfig, rule_name: str
    ) -> RoomActor:
        actor = self._actors.get(code)
        if actor is not None:
            return actor
        actor = RoomActor(
            code=code,
            room_id=room_id,
            name=name,
            host_id=host_id,
            rule=rule,
            rule_name=rule_name,
            rule_snapshot=rule.model_dump(),
        )
        self._actors[code] = actor
        logger.info("房间演员创建 code=%s room=%s", code, room_id)
        return actor

    def remove(self, code: str) -> None:
        actor = self._actors.pop(code, None)
        if actor is not None:
            actor._clear_timers()
            logger.info("房间演员销毁 code=%s", code)

    def codes(self) -> list[str]:
        return list(self._actors.keys())


room_manager = RoomManager()
