"""皮肤路由（04 §8：#35–#41，7 个端点）。

分层（01 §2）：
  - 路由只做「读参数 → 家庭上下文 → 调 skinService → 套响应模型」；
  - 家庭管理员/系统管理员判定在 skinService（写操作按皮肤归属的家庭校验），
    路由不重复写 if；
  - `GET /api/skins` 自带 ETag/304：清单按「家庭 + updated_at」计算指纹（04 §8）。
"""

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from config.localSettings import settings
from main.deps import CurrentUser, FamilyContext, current_active_family, current_user, familyContextOf
from processor import familyService, skinService
from schemas.family import OkOut
from schemas.skin import SkinAssetOut, SkinCreateRequest, SkinOut, SkinUpdateRequest

router = APIRouter(prefix="/skins", tags=["skins"])

# 清单必须每次回源校验（带 ETag 协商）；不设 no-cache 会让浏览器本地缓存盖住更新
_ETAG_CACHE_CONTROL = "private, no-cache"


def _clientIP(request: Request) -> str:
    return request.client.host if request.client else ""


def _requireSkinEnabled() -> None:
    """回滚开关（06 §8.3）：SKIN_ENABLED=false 时皮肤写操作一律 403。"""
    if not settings.skin_enabled:
        raise skinService.SkinServiceError("SKIN_DISABLED", "皮肤功能已关闭", 403)


@router.get("", response_model=list[SkinOut])
def list_skins(
    request: Request,
    include_disabled: bool = False,
    context: FamilyContext = Depends(current_active_family),
    user: CurrentUser = Depends(current_user),
) -> Response:
    """04 §8 #35：当前家庭可见皮肤清单（含 assets），支持 `If-None-Match` → 304。

    `include_disabled=1` 只给管理页（家庭管理员/系统管理员）：带上本家庭自有的草稿皮肤，
    否则刷新页面后未发布的皮肤就再也点不进去。内置皮肤恒只给 ENABLED。
    """
    headers = {"Cache-Control": _ETAG_CACHE_CONTROL}
    if not settings.skin_enabled:
        headers["ETag"] = '"skin-disabled"'
        return JSONResponse(content=[], headers=headers)

    if include_disabled and not user.is_admin:
        context.require_admin()

    rows, etag, notModified = skinService.listSkins(
        context.family_id,
        context.family_code,
        request.headers.get("if-none-match", ""),
        includeDisabled=include_disabled,
    )
    headers["ETag"] = etag
    if notModified:
        return Response(status_code=304, headers=headers)
    payload = [SkinOut(**row).model_dump() for row in rows]
    return JSONResponse(content=payload, headers=headers)


@router.get("/{skin_code}", response_model=SkinOut)
def get_skin(
    skin_code: str,
    context: FamilyContext = Depends(current_active_family),
    user: CurrentUser = Depends(current_user),
) -> SkinOut:
    """04 §8 #36：单皮肤详情；跨家庭皮肤一律 403 NOT_FAMILY_MEMBER。"""
    _requireSkinEnabled()
    return SkinOut(
        **skinService.getSkin(
            user.login_id, skin_code, context.family_id, context.family_code
        )
    )


@router.post("", response_model=SkinOut)
def create_skin(
    payload: SkinCreateRequest,
    request: Request,
    user: CurrentUser = Depends(current_user),
) -> SkinOut:
    """04 §8 #37：新建皮肤（初始 DISABLED，资源齐全后 publish）。

    `family_code` 缺省取当前家庭；显式传入时按该家庭校验成员与管理员身份。
    """
    _requireSkinEnabled()
    familyCode = (payload.family_code or "").strip()
    if not familyCode:
        familyCode = _currentFamilyCode(user.login_id)
    context = familyContextOf(user.login_id, familyCode, requireEnabled=True)
    return SkinOut(
        **skinService.createSkin(
            user.login_id,
            context.family_code,
            payload.skin_name,
            payload.skin_code,
            clientIP=_clientIP(request),
            operatorIsSystemAdmin=user.is_admin,
        )
    )


@router.put("/{skin_code}/{tile_key}", response_model=SkinAssetOut)
def upload_asset(
    skin_code: str,
    tile_key: str,
    request: Request,
    file: UploadFile = File(..., description="PNG / WebP，≤512 KB"),
    user: CurrentUser = Depends(current_user),
) -> SkinAssetOut:
    """04 §8 #38：上传/替换单张资源（multipart `file`）。

    只读 `MAX_UPLOAD_BYTES + 1` 字节：超限立刻拒绝，不把大文件读进内存；
    其余校验（magic number、尺寸、总容量）在 skinService 内完成。
    """
    _requireSkinEnabled()
    limit = int(settings.max_upload_bytes or skinService.MAX_UPLOAD_BYTES)
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise skinService.SkinServiceError("UPLOAD_TOO_LARGE", "图片超过 512 KB")

    result = skinService.uploadAsset(
        user.login_id,
        skin_code,
        tile_key,
        data,
        file.filename or "",
        clientIP=_clientIP(request),
        operatorIsSystemAdmin=user.is_admin,
    )
    return SkinAssetOut(**result)


@router.delete("/{skin_code}/{tile_key}", response_model=OkOut)
def delete_asset(
    skin_code: str,
    tile_key: str,
    request: Request,
    user: CurrentUser = Depends(current_user),
) -> OkOut:
    """04 §8 #39：删除单张资源（软删；该张由前端回退 CSS，文件延迟清理）。"""
    _requireSkinEnabled()
    skinService.deleteAsset(
        user.login_id,
        skin_code,
        tile_key,
        clientIP=_clientIP(request),
        operatorIsSystemAdmin=user.is_admin,
    )
    return OkOut(ok=True)


@router.patch("/{skin_code}", response_model=SkinOut)
def patch_skin(
    skin_code: str,
    payload: SkinUpdateRequest,
    request: Request,
    user: CurrentUser = Depends(current_user),
) -> SkinOut:
    """04 §8 #40：改名 / 发布（status=ENABLED）/ 停用 / 排序 / 设默认。"""
    _requireSkinEnabled()
    return SkinOut(
        **skinService.patchSkin(
            user.login_id,
            skin_code,
            skinName=payload.skin_name,
            status=payload.status,
            sortOrder=payload.sort_order,
            isDefault=payload.is_default,
            clientIP=_clientIP(request),
            operatorIsSystemAdmin=user.is_admin,
        )
    )


@router.delete("/{skin_code}", response_model=OkOut)
def delete_skin(
    skin_code: str,
    request: Request,
    user: CurrentUser = Depends(current_user),
) -> OkOut:
    """04 §8 #41：软删皮肤（delFlag=1，文件保留）。"""
    _requireSkinEnabled()
    skinService.softDelete(
        user.login_id,
        skin_code,
        clientIP=_clientIP(request),
        operatorIsSystemAdmin=user.is_admin,
    )
    return OkOut(ok=True)


def _currentFamilyCode(loginID: str) -> str:
    """缺省家庭：`mj_user_pref.lastFamilyID` → 第一个 ACTIVE 家庭（04 §11）。"""
    code = familyService.currentFamilyCode(loginID) or ""
    if not code:
        raise familyService.FamilyServiceError(
            "NOT_FAMILY_MEMBER", "无权访问该家庭资源", 403
        )
    return code
