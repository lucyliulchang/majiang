"""战绩路由（04 §7，3 个端点）。

分层（01 §2）：只解析参数（`family_code` / `limit` / `before_id`）→ 调 historyService。
分页：`limit` 默认 30、最大 100；`before_id` 为 recID 游标（不用 OFFSET 深翻页）。
"""

from fastapi import APIRouter, Depends, Query

from main.deps import CurrentUser, FamilyContext, current_family, current_user
from processor import historyService

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/games")
def list_games(
    limit: int = Query(default=30, ge=1, le=100),
    before_id: int = 0,
    context: FamilyContext = Depends(current_family),
) -> list[dict]:
    """我的场次列表（04 §7 #31）：只列自己参与过的场次，倒序游标分页。"""
    return historyService.listGames(
        context.login_id, context.family_id, limit=limit, beforeID=before_id
    )


@router.get("/games/{game_id}")
def game_detail(
    game_id: int,
    user: CurrentUser = Depends(current_user),
) -> dict:
    """场次明细（04 §7 #32）：参与者/家庭管理员/系统管理员可读。"""
    return historyService.gameDetail(user.login_id, game_id, operatorIsSystemAdmin=user.is_admin)


@router.get("/stats")
def my_stats(context: FamilyContext = Depends(current_family)) -> dict:
    """个人统计（04 §7 #33）。"""
    return historyService.myStats(context.login_id, context.family_id)
