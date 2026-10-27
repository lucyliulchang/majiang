"""预置规则模板：开箱即用的四套，家人不用从零配规则。

刻意覆盖了「三组开关」的三种组合，方便家人理解开关的作用：
- 家庭标准：全开
- 带十三不靠：特殊牌型打开
- 休闲不限时：出牌不限时 + 杠不计分
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import RuleTemplate
from app.schemas.rule import (
    KongScore,
    PatternSwitches,
    RuleConfig,
    ThirteenUnrelatedOptions,
    ToggleValue,
    TurnTimeout,
)

logger = get_logger("mahjong.seeds")


def preset_configs() -> list[tuple[str, str, RuleConfig]]:
    standard = RuleConfig(
        base_score=1,
        fan_mode="exponential",
        fan_cap=8,
        allow_chow=True,
        turn_timeout=TurnTimeout(enabled=True, seconds=15),
        kong_score=KongScore(enabled=True, exposed=1, hidden=2, added=1),
        ting_hint=ToggleValue(enabled=True),
        rounds_per_game=4,
    )
    no_chow = RuleConfig(
        base_score=1,
        fan_mode="linear",
        fan_cap=12,
        allow_chow=False,
        turn_timeout=TurnTimeout(enabled=True, seconds=20),
        kong_score=KongScore(enabled=True, exposed=2, hidden=4, added=2),
        ting_hint=ToggleValue(enabled=True),
        rounds_per_game=4,
    )
    with_unrelated = RuleConfig(
        base_score=1,
        fan_mode="exponential",
        fan_cap=10,
        allow_chow=True,
        patterns=PatternSwitches(
            standard=True,
            seven_pairs=True,
            thirteen_orphans=True,
            thirteen_unrelated=ThirteenUnrelatedOptions(
                enabled=True, require_all_honors=False, allow_pair=True, min_gap=3
            ),
        ),
        turn_timeout=TurnTimeout(enabled=True, seconds=18),
        kong_score=KongScore(enabled=True, exposed=1, hidden=2, added=1),
        ting_hint=ToggleValue(enabled=True),
        rounds_per_game=4,
    )
    relaxed = RuleConfig(
        base_score=1,
        fan_mode="linear",
        fan_cap=15,
        allow_chow=True,
        turn_timeout=TurnTimeout(enabled=False, seconds=15),
        kong_score=KongScore(enabled=False, exposed=1, hidden=2, added=1),
        ting_hint=ToggleValue(enabled=False),
        draw_penalty=ToggleValue(enabled=False, value=0),
        rounds_per_game=8,
    )
    return [
        ("家庭标准", "底分 1，2 的 N 次方封顶 8 番，可以吃，限时 15 秒，杠分 1-2-1", standard),
        ("宽松无吃", "不能吃只能碰，线性累加封顶 12 番，适合新手慢慢打", no_chow),
        ("带十三不靠", "在家庭标准基础上开放十三不靠，需要 4 张牌间隔至少 3 位", with_unrelated),
        ("休闲不限时", "出牌不限时、杠不计分、无听牌提示，纯粹图个乐", relaxed),
    ]


def install_presets(session: Session) -> int:
    """幂等：按名字比对，已存在就不重复插入。"""
    created = 0
    existing = {
        row.name
        for row in session.scalars(
            select(RuleTemplate).where(RuleTemplate.is_preset.is_(True))
        ).all()
    }
    for name, description, config in preset_configs():
        if name in existing:
            continue
        session.add(
            RuleTemplate(
                owner_id=None,
                name=name,
                description=description,
                config=config.model_dump(),
                is_preset=True,
                is_active=True,
            )
        )
        created += 1
    if created:
        session.commit()
        logger.info("已写入 %s 套预置规则模板", created)
    return created
