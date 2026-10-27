"""用户偏好路由（04 §4）：GET / PUT /api/user/pref。

偏好按 `loginID` 维度（`mj_user_pref`），不属于家庭域；但 `last_family_code` 与
`skin_code` 的取值都要过家庭可见性校验（由 familyService 统一处理）。
"""

from fastapi import APIRouter, Depends

from main.deps import CurrentUser, current_user
from processor import familyService
from schemas.user import PrefOut, PrefUpdateRequest

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/pref", response_model=PrefOut)
def get_pref(user: CurrentUser = Depends(current_user)) -> PrefOut:
    """当前偏好：无记录时返回默认值（不写库）。"""
    return PrefOut(**familyService.getPref(user.login_id))


@router.put("/pref", response_model=PrefOut)
def put_pref(
    payload: PrefUpdateRequest, user: CurrentUser = Depends(current_user)
) -> PrefOut:
    """局部更新偏好：只改请求里出现的字段（`exclude_unset`）。"""
    patch = payload.model_dump(exclude_unset=True)
    return PrefOut(**familyService.updatePref(user.login_id, patch))
