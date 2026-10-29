"""皮肤域服务：主档、逐张资源、发布与默认皮肤（04 §8、05 §6、01 §10）。

职责：
  1) `mj_tile_skin` / `mj_tile_skin_asset` 的读写，及图片文件落盘（唯一写入口）；
  2) 上传校验：扩展名 + magic number 双白名单（png/webp）、≤512 KB、尺寸/宽高比、
     单皮肤总量 ≤8 MB（01 §10）；
  3) 清单组装：`assets` map（35 个 tile_key）、`preview_url`、`fallback=css-classic`，
     以及按「家庭 + updated_at」计算的 ETag（04 §8）；
  4) 发布/设默认/停用/软删的权限（家庭管理员或系统管理员）与审计
     （SKIN_CREATE / SKIN_UPLOAD / SKIN_PUBLISH / SKIN_DEFAULT / SKIN_DELETE）；
  5) 权限一律经 `familyService.assertMember` 判定，不在这里另写一套。

硬约束（01 §10、05 §6.2）：
  - 文件名完全由服务端生成：`{tileKey}.{hash8}.{ext}`，用户文件名只用于取扩展名；
  - 拒绝 SVG（脚本注入风险）：magic number 与扩展名都只认 png/webp；
  - 上传目录固定 `settings.public_dir/tiles`（本地 code/backend/data/webserver/majiangapp，
    生产 /data/webserver/majiangapp），只经 `/majiangapp/tiles/` 暴露；
  - 软删不删文件（延迟清理，见 schedule/dataClean.py 的孤儿文件清理）。
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import struct
from dataclasses import dataclass
from pathlib import Path

from common import miscCommon as misc
from common import mysqlCommon
from common.bizCommon import BizError
from common.loggingCommon import get_logger
from config.basicSettings import (
    PUBLIC_IMAGE_URL,
    UPLOAD_ALLOWED_SUFFIXES,
    UPLOAD_MAX_BYTES,
    UPLOAD_MAX_SKIN_BYTES,
)
from config.localSettings import settings
from processor import familyService

logger = get_logger("mahjong.skin")

# ---------------------------------------------------------------- 枚举与常量

SKIN_ENABLED = "ENABLED"
SKIN_DISABLED = "DISABLED"
SKIN_STATUS_LIST = (SKIN_ENABLED, SKIN_DISABLED)

# 05 §6.1：34 张牌 + 牌背 = 35 个必填 tile_key（顺序即发布校验的报错顺序）
TILE_KEYS: tuple[str, ...] = (
    "1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
    "1p", "2p", "3p", "4p", "5p", "6p", "7p", "8p", "9p",
    "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s",
    "east", "south", "west", "north", "red", "green", "white",
    "back",
)
TILE_KEY_SET = frozenset(TILE_KEYS)

# 预览图不是 tile_key（05 §6.1），单独存 mj_tile_skin.previewFileID
PREVIEW_KEY = "preview"
UPLOADABLE_KEY_SET = TILE_KEY_SET | {PREVIEW_KEY}

# 内置兜底皮肤（无资源，纯 CSS 渲染）
FALLBACK_SKIN_CODE = "css-classic"
TILE_ASPECT = 0.6667

# 上传限制（01 §10 / 11 配置）：单文件与单皮肤上限来自 config，测试与运维都只改一处
MAX_UPLOAD_BYTES = UPLOAD_MAX_BYTES
MAX_SKIN_BYTES = UPLOAD_MAX_SKIN_BYTES
MAX_TILE_DIMENSION = 2048
MIN_TILE_WIDTH = 32
MIN_TILE_HEIGHT = 48
MIN_PREVIEW_WIDTH = 96

ALLOWED_SUFFIXES = UPLOAD_ALLOWED_SUFFIXES
# 牌面 2:3；预览 3:2。给 ±10% 宽容，避免设计切图差几个像素就传不上
_TILE_RATIO = 2 / 3
_TILE_RATIO_TOLERANCE = 0.1
_PREVIEW_RATIO = 3 / 2
_PREVIEW_RATIO_TOLERANCE = 0.1

# 04 §3 口径的编码风格（小写字母开头，允许数字、下划线、连字符）
SKIN_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_SKIN_NAME_MAX_LEN = 64

# 审计动作码（S8）
ACTION_SKIN_CREATE = "SKIN_CREATE"
ACTION_SKIN_UPLOAD = "SKIN_UPLOAD"
ACTION_SKIN_PUBLISH = "SKIN_PUBLISH"
ACTION_SKIN_DEFAULT = "SKIN_DEFAULT"
ACTION_SKIN_DELETE = "SKIN_DELETE"
ACTION_SKIN_UPDATE = "SKIN_UPDATE"

_MAGIC_PNG = b"\x89PNG\r\n\x1a\n"


class SkinServiceError(BizError):
    """皮肤域业务异常（HTTP 状态 + 错误码 + 中文提示）。"""


# ---------------------------------------------------------------- 小工具


def _err(code: str, message: str, httpStatus: int = 400) -> SkinServiceError:
    return SkinServiceError(code, message, httpStatus)


def _text(row: dict, key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value)


def _int(row: dict, key: str) -> int:
    try:
        return int(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _flag(value) -> bool:
    return str(value or "").strip() in ("1", "true", "True")


def _iso(ymdhms: str) -> str:
    return misc.ymdhmsToIso(ymdhms)


def publicRoot() -> Path:
    """静态站点根（= settings.public_dir）。测试里替换此函数即可改上传根目录。"""
    return Path(settings.public_dir)


def tilesRoot() -> Path:
    return publicRoot() / "tiles"


def _ensureTilesRoot() -> Path:
    root = tilesRoot()
    root.mkdir(parents=True, exist_ok=True)
    return root


def publicURL(relativePath: str) -> str:
    """相对路径（tiles/{skinCode}/{file}）→ 对外 URL（/majiangapp/tiles/...）。"""
    path = (relativePath or "").strip().replace("\\", "/").lstrip("/")
    if not path:
        return ""
    return f"{PUBLIC_IMAGE_URL}/{path}"


def _filePath(relativePath: str) -> Path:
    return publicRoot() / (relativePath or "").replace("\\", "/").lstrip("/")


def _audit(
    familyID: int,
    operatorLoginID: str,
    actionCode: str,
    targetID: str,
    detail: dict,
    clientIP: str,
) -> None:
    """写审计：调用方必须已在事务内（与业务写入同生共死，01 §7.4）。"""
    recID = mysqlCommon.write_mj_audit_log(
        familyID=familyID,
        operatorLoginID=operatorLoginID,
        actionCode=actionCode,
        targetType="SKIN",
        targetID=targetID,
        detail=detail,
        clientIP=clientIP,
    )
    if recID <= 0:
        raise SkinServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)


# ---------------------------------------------------------------- 图片校验


@dataclass(frozen=True)
class ImageInfo:
    ext: str
    mime: str
    width: int
    height: int


def _badType(message: str = "只支持 PNG 或 WebP 图片") -> SkinServiceError:
    return _err("UPLOAD_BAD_TYPE", message)


def sniffImage(data: bytes) -> ImageInfo:
    """按 magic number 识别 png/webp 并读出像素尺寸（不引入 Pillow 依赖）。

    尺寸来自文件头：PNG 的 IHDR；WebP 的 VP8（有损）/ VP8L（无损）/ VP8X（扩展）。
    头损坏或无法识别一律按 UPLOAD_BAD_TYPE 拒绝，绝不影响后续落盘。
    """
    if data[:8] == _MAGIC_PNG:
        if len(data) < 24 or data[12:16] != b"IHDR":
            raise _badType("PNG 文件头不完整")
        width, height = struct.unpack(">II", data[16:24])
        return ImageInfo("png", "image/png", int(width), int(height))

    if len(data) >= 16 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8 ":
            if len(data) < 30:
                raise _badType("WebP 文件头不完整")
            width = int.from_bytes(data[26:28], "little") & 0x3FFF
            height = int.from_bytes(data[28:30], "little") & 0x3FFF
            return ImageInfo("webp", "image/webp", width, height)
        if chunk == b"VP8L":
            if len(data) < 25 or data[20] != 0x2F:
                raise _badType("WebP 文件头不完整")
            bits = int.from_bytes(data[21:25], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return ImageInfo("webp", "image/webp", width, height)
        if chunk == b"VP8X":
            if len(data) < 30:
                raise _badType("WebP 文件头不完整")
            width = int.from_bytes(data[24:27], "little") + 1
            height = int.from_bytes(data[27:30], "little") + 1
            return ImageInfo("webp", "image/webp", width, height)
        raise _badType("WebP 编码格式不受支持")

    raise _badType()


def _validateDimensions(info: ImageInfo, tileKey: str) -> None:
    """尺寸校验：牌面 2:3（建议 192×288），预览 3:2（建议 480×320）。"""
    if tileKey == PREVIEW_KEY:
        ratio, tolerance = _PREVIEW_RATIO, _PREVIEW_RATIO_TOLERANCE
        minWidth, minHeight = MIN_PREVIEW_WIDTH, 0
    else:
        ratio, tolerance = _TILE_RATIO, _TILE_RATIO_TOLERANCE
        minWidth, minHeight = MIN_TILE_WIDTH, MIN_TILE_HEIGHT
    ratioLow = ratio * (1 - tolerance)
    ratioHigh = ratio * (1 + tolerance)

    if info.width <= 0 or info.height <= 0:
        raise _badType("图片尺寸无法识别")
    if info.width < minWidth or info.height < minHeight:
        raise _err(
            "UPLOAD_BAD_DIMENSION",
            f"图片尺寸过小：{info.width}×{info.height}（牌面最小 {MIN_TILE_WIDTH}×{MIN_TILE_HEIGHT}）",
        )
    if max(info.width, info.height) > MAX_TILE_DIMENSION:
        raise _err(
            "UPLOAD_BAD_DIMENSION",
            f"图片尺寸过大：{info.width}×{info.height}（最大边 {MAX_TILE_DIMENSION}px）",
        )
    actual = info.width / info.height
    if actual < ratioLow or actual > ratioHigh:
        expected = "2:3（建议 192×288）" if tileKey != PREVIEW_KEY else "3:2（建议 480×320）"
        raise _err(
            "UPLOAD_BAD_DIMENSION",
            f"图片宽高比应为 {expected}，当前 {info.width}×{info.height}",
        )


def validateUpload(tileKey: str, fileName: str, data: bytes) -> ImageInfo:
    """上传前校验：key 白名单 → 扩展名 → 体积 → magic number → 尺寸。

    顺序有意为之：体积检查放最前（也算在 magic 之前），免得超大文件先做字节解析。
    """
    if tileKey not in UPLOADABLE_KEY_SET:
        raise _err("SKIN_TILE_KEY_INVALID", f"不支持的 tile_key：{tileKey}")

    suffix = os.path.splitext((fileName or "").strip())[1].lower()
    if suffix not in ALLOWED_SUFFIXES:
        # 含 .svg：明确拒绝，不进入任何图片解析分支
        raise _badType("只支持 PNG 或 WebP 图片")

    if not data:
        raise _badType("图片内容为空")
    limit = int(settings.max_upload_bytes or MAX_UPLOAD_BYTES)
    if len(data) > limit:
        raise _err("UPLOAD_TOO_LARGE", f"图片超过 {limit // 1024} KB")

    info = sniffImage(data)
    if f".{info.ext}" != suffix:
        # 扩展名与真实内容不一致：可能是改了后缀的 svg/其他格式
        raise _badType("图片内容与扩展名不一致")

    _validateDimensions(info, tileKey)
    return info


# ---------------------------------------------------------------- 行 → 协议


def _assetsBySkin(assetRows: list[dict]) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    for row in assetRows:
        grouped.setdefault(_int(row, "skinID"), []).append(row)
    return grouped


def _skinOut(
    row: dict,
    assetRows: list[dict],
    familyID: int,
    familyHasDefault: bool,
) -> dict:
    """04 §8 的 skin 结构（含 assets map / preview_url / fallback）。"""
    tileAssetMap: dict[str, str] = {}
    for asset in assetRows:
        tileKey = _text(asset, "tileKey")
        fileID = _text(asset, "fileID")
        if tileKey in TILE_KEY_SET and fileID:
            tileAssetMap[tileKey] = publicURL(fileID)

    isBuiltin = _int(row, "familyID") == 0
    # 有效默认：家庭自有皮肤一旦有 default，全局内置的 defaultFlag 让位（避免清单里两个 is_default）
    isDefault = _flag(row.get("defaultFlag")) and (not familyHasDefault or not isBuiltin)

    return {
        "skin_code": _text(row, "skinCode"),
        "skin_name": _text(row, "skinName"),
        "family_code": None if isBuiltin else _text(row, "familyCode") or None,
        "is_default": isDefault,
        "status": _text(row, "skinStatus") or SKIN_ENABLED,
        "tile_aspect": float(row.get("tileAspect") or TILE_ASPECT),
        "asset_count": len(tileAssetMap),
        "preview_url": publicURL(_text(row, "previewFileID")) or None,
        "assets": tileAssetMap,
        "fallback": FALLBACK_SKIN_CODE,
        "updated_at": _iso(_text(row, "modifyYMDHMS") or _text(row, "regYMDHMS")),
    }


def buildETag(familyID: int, skinRows: list[dict], assetRows: list[dict]) -> str:
    """ETag = 家庭 + 主档（含 DISABLED/软删）+ 资源行的指纹；任何可见变更都会换 ETag。"""
    parts = [f"f{int(familyID or 0)}"]
    for row in skinRows:
        parts.append(
            "s:%s:%s:%s:%s:%s:%s"
            % (
                _int(row, "recID"),
                _text(row, "skinStatus"),
                _text(row, "defaultFlag"),
                _text(row, "previewFileID"),
                _text(row, "sortOrder"),
                _text(row, "modifyYMDHMS") or _text(row, "regYMDHMS"),
            )
        )
    for row in assetRows:
        parts.append(
            "a:%s:%s:%s:%s"
            % (
                _int(row, "recID"),
                _int(row, "skinID"),
                _text(row, "fileID"),
                _text(row, "modifyYMDHMS") or _text(row, "regYMDHMS"),
            )
        )
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f'"{digest}"'


def etagMatches(ifNoneMatch: str, etag: str) -> bool:
    """If-None-Match 匹配（弱比较）：支持 `*`、逗号分隔、W/ 前缀。"""
    header = (ifNoneMatch or "").strip()
    if not header or not etag:
        return False
    if header == "*":
        return True
    target = etag.strip().lstrip("W/").strip('"')
    for item in header.split(","):
        if item.strip().lstrip("W/").strip('"') == target:
            return True
    return False


# ---------------------------------------------------------------- 权限与读取


def _loadSkin(skinCode: str) -> dict:
    """按编码取皮肤；软删（delFlag=1）与不存在同样返回 404，不泄露内部状态。"""
    code = (skinCode or "").strip()
    if not code:
        raise _err("SKIN_NOT_FOUND", "皮肤不存在", 404)
    row = mysqlCommon.query_mj_tile_skin_by_code(code)
    if not row:
        raise _err("SKIN_NOT_FOUND", "皮肤不存在", 404)
    return row


def _adminContext(
    loginID: str, familyID: int, operatorIsSystemAdmin: bool
) -> dict | None:
    """皮肤写操作权限：家庭管理员（OWNER/ADMIN）或系统管理员；全局皮肤只允许系统管理员。"""
    if int(familyID or 0) <= 0:
        if not operatorIsSystemAdmin:
            raise familyService.FamilyServiceError(
                "NOT_FAMILY_ADMIN", "只有系统管理员可以修改内置皮肤", 403
            )
        return None
    context = familyService.assertMemberOfFamilyID(loginID, familyID, requireEnabled=True)
    if operatorIsSystemAdmin:
        return context
    if context["memberRole"] not in (familyService.ROLE_OWNER, familyService.ROLE_ADMIN):
        raise familyService.FamilyServiceError(
            "NOT_FAMILY_ADMIN", "只有家庭管理员可以操作", 403
        )
    return context


def _assetRowsOf(skinID: int) -> list[dict]:
    return mysqlCommon.query_mj_tile_skin_asset_list(skinID)


def _skinTotalBytes(assetRows: list[dict], excludeTileKey: str = "") -> int:
    total = 0
    for row in assetRows:
        if excludeTileKey and _text(row, "tileKey") == excludeTileKey:
            continue
        total += _int(row, "fileSize")
    return total


def _resolveVisibleSkin(loginID: str, skinCode: str, familyID: int) -> dict:
    """详情读取：全局皮肤对所有家庭可见；家庭皮肤只对本家庭成员可见。"""
    row = _loadSkin(skinCode)
    rowFamilyID = _int(row, "familyID")
    if rowFamilyID > 0 and rowFamilyID != int(familyID or 0):
        # 跨家庭：与 familyService 同一文案，不泄露皮肤是否存在
        raise familyService.FamilyServiceError(
            "NOT_FAMILY_MEMBER", "无权访问该家庭资源", 403
        )
    return row


# ---------------------------------------------------------------- 清单 / 详情


def listSkins(
    familyID: int,
    familyCode: str = "",
    ifNoneMatch: str = "",
    includeDisabled: bool = False,
) -> tuple[list[dict], str, bool]:
    """04 §8 #35：家庭可见皮肤清单（含 assets map）。

    出参: (skins, etag, notModified)。`notModified=True` 时调用方回 304，不要读 skins。
    默认仅返回 ENABLED；ETag 的指纹却包含 DISABLED/软删行，保证下架也能让缓存失效。

    `includeDisabled=True` 只给家庭管理员/系统管理员的管理页用（S10）：返回本家庭自有的
    DISABLED 草稿，否则「新建 → 上传 35 张 → 发布」在刷新页面后就再也找不到那套皮肤。
    内置（familyID=0）行始终只给 ENABLED，避免把平台下架的皮肤暴露给普通成员。
    """
    familyID = int(familyID or 0)
    allRows = mysqlCommon.query_mj_tile_skin_list_all(familyID)
    assetRows = mysqlCommon.query_mj_tile_skin_asset_list_by_family(familyID)

    etag = buildETag(familyID, allRows, assetRows)
    if etagMatches(ifNoneMatch, etag):
        return [], etag, True

    if includeDisabled:
        visibleRows = [
            row
            for row in allRows
            if _int(row, "familyID") == familyID or _text(row, "skinStatus") == SKIN_ENABLED
        ]
    else:
        visibleRows = [row for row in allRows if _text(row, "skinStatus") == SKIN_ENABLED]

    # 家庭编码由家庭主档给出，避免每条皮肤再查一次家庭表
    code = (familyCode or "").strip()
    grouped = _assetsBySkin(assetRows)
    familyHasDefault = any(
        _int(row, "familyID") == familyID and _flag(row.get("defaultFlag"))
        for row in allRows
    )

    skins: list[dict] = []
    for row in visibleRows:
        skinID = _int(row, "recID")
        row["familyCode"] = code if _int(row, "familyID") == familyID else ""
        skins.append(_skinOut(row, grouped.get(skinID, []), familyID, familyHasDefault))
    return skins, etag, False


def getSkin(loginID: str, skinCode: str, familyID: int, familyCode: str = "") -> dict:
    """04 §8 #36：单皮肤详情（含 assets / preview_url）。"""
    row = _resolveVisibleSkin(loginID, skinCode, familyID)
    if _int(row, "familyID") > 0:
        code = (familyCode or "").strip()
        if not code:
            family = mysqlCommon.query_mj_family_by_id(_int(row, "familyID"))
            code = _text(family, "familyCode")
        row["familyCode"] = code
    allRows = mysqlCommon.query_mj_tile_skin_list_all(familyID)
    familyHasDefault = any(
        _int(item, "familyID") == familyID and _flag(item.get("defaultFlag"))
        for item in allRows
    )
    return _skinOut(row, _assetRowsOf(_int(row, "recID")), familyID, familyHasDefault)


# ---------------------------------------------------------------- 主档写操作


def _generateSkinCode(familyCode: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (familyCode or "").strip().lower()).strip("-")[:24]
    if not base or not base[0].isalpha():
        base = "skin"
    return f"{base}-{secrets.token_hex(2)}"


def _validateSkinCode(skinCode: str) -> str:
    code = (skinCode or "").strip().lower()
    if not SKIN_CODE_PATTERN.match(code):
        raise _err(
            "SKIN_CODE_INVALID",
            "皮肤编码需以小写字母开头，只含小写字母、数字、下划线与连字符，长度 2-32",
        )
    return code


def _validateSkinName(skinName: str) -> str:
    name = (skinName or "").strip()
    if not name:
        raise _err("SKIN_NAME_REQUIRED", "请填写皮肤名称")
    if len(name) > _SKIN_NAME_MAX_LEN:
        raise _err("SKIN_NAME_TOO_LONG", "皮肤名称最多 64 字")
    return name


def createSkin(
    loginID: str,
    familyCode: str,
    skinName: str,
    skinCode: str = "",
    clientIP: str = "",
    operatorIsSystemAdmin: bool = False,
) -> dict:
    """04 §8 #37：新建皮肤（初始 DISABLED，资源齐全后 publish 才可见）。

    幂等：同家庭内重复提交同一 skinCode 返回既有资源（04 §1），跨家庭占用给 409。
    """
    context = familyService.assertMember(loginID, familyCode, requireEnabled=True)
    familyID = context["familyID"]
    if not operatorIsSystemAdmin and context["memberRole"] not in (
        familyService.ROLE_OWNER,
        familyService.ROLE_ADMIN,
    ):
        raise familyService.FamilyServiceError(
            "NOT_FAMILY_ADMIN", "只有家庭管理员可以操作", 403
        )

    name = _validateSkinName(skinName)
    existing = mysqlCommon.query_mj_tile_skin_by_code(skinCode) if skinCode else {}
    if existing:
        if _int(existing, "familyID") != familyID:
            raise _err("SKIN_CODE_EXISTS", "皮肤编码已被占用", 409)
        return getSkin(loginID, _text(existing, "skinCode"), familyID, familyCode)

    code = _validateSkinCode(skinCode) if skinCode else _generateSkinCode(familyCode)
    for _ in range(3):
        if not mysqlCommon.query_mj_tile_skin_by_code(code):
            break
        code = _generateSkinCode(familyCode)
    else:
        raise _err("SKIN_CODE_EXHAUSTED", "皮肤编码生成失败，请重试", 500)

    now = misc.getTime()
    with mysqlCommon.transaction():
        recID = mysqlCommon.insert_mj_tile_skin(
            mysqlCommon.MJ_TILE_SKIN_TABLE,
            {
                "skinCode": code,
                "skinName": name,
                "familyID": familyID,
                "previewFileID": None,
                "tileAspect": TILE_ASPECT,
                # 初始不可见：没有资源的皮肤出现在清单里只会让前端整片回退 CSS
                "defaultFlag": "0",
                "skinStatus": SKIN_DISABLED,
                "sortOrder": 0,
                "ownerLoginID": loginID,
                "regID": loginID,
                "regYMDHMS": now,
                "delFlag": "0",
            },
        )
        if recID <= 0:
            if mysqlCommon.query_mj_tile_skin_by_code(code):
                raise _err("SKIN_CODE_EXISTS", "皮肤编码已被占用", 409)
            raise SkinServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
        _audit(
            familyID,
            loginID,
            ACTION_SKIN_CREATE,
            code,
            {"skin_name": name, "skin_code": code},
            clientIP,
        )

    return getSkin(loginID, code, familyID, familyCode)


def _updateSkin(
    loginID: str,
    skin: dict,
    dataSet: dict,
    clientIP: str,
    actionCode: str = ACTION_SKIN_UPDATE,
    detail: dict | None = None,
) -> None:
    """单次事务内更新皮肤主档 + 审计（dataSet 允许为空，此时只写审计）。"""
    skinCode = _text(skin, "skinCode")
    if dataSet:
        dataSet = dict(dataSet)
        dataSet["modifyID"] = loginID
        dataSet["modifyYMDHMS"] = misc.getTime()
    with mysqlCommon.transaction():
        if dataSet:
            affected = mysqlCommon.update_mj_tile_skin_fields(_int(skin, "recID"), dataSet)
            if affected < 0:
                raise SkinServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
        _audit(
            _int(skin, "familyID"),
            loginID,
            actionCode,
            skinCode,
            detail or dataSet,
            clientIP,
        )


def setDefault(
    loginID: str,
    skinCode: str,
    clientIP: str = "",
    operatorIsSystemAdmin: bool = False,
) -> dict:
    """04 §8：设为家庭默认皮肤；同事务清掉同家庭旧的 default，保证唯一。"""
    skin = _loadSkin(skinCode)
    familyID = _int(skin, "familyID")
    _adminContext(loginID, familyID, operatorIsSystemAdmin)

    if _text(skin, "skinStatus") != SKIN_ENABLED:
        raise _err("SKIN_NOT_PUBLISHED", "皮肤尚未发布，不能设为默认")

    friends = mysqlCommon.query_mj_tile_skin_list(familyID)
    previous = [row for row in friends if _flag(row.get("defaultFlag")) and _int(row, "recID") != _int(skin, "recID")]

    with mysqlCommon.transaction():
        # 只清「同一归属」的 default：全局皮肤的 defaultFlag 由种子维护，
        # 家庭 A 设默认不能把其他家庭看到的内置默认也清掉。
        mysqlCommon.clear_mj_tile_skin_default(familyID, _int(skin, "recID"), loginID)
        affected = mysqlCommon.update_mj_tile_skin_fields(
            _int(skin, "recID"),
            {
                "defaultFlag": "1",
                "modifyID": loginID,
                "modifyYMDHMS": misc.getTime(),
            },
        )
        if affected < 0:
            raise SkinServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
        _audit(
            familyID,
            loginID,
            ACTION_SKIN_DEFAULT,
            _text(skin, "skinCode"),
            {
                "skin_code": _text(skin, "skinCode"),
                "previous": [_text(row, "skinCode") for row in previous],
            },
            clientIP,
        )

    return getSkin(loginID, _text(skin, "skinCode"), familyID)


def publish(
    loginID: str,
    skinCode: str,
    clientIP: str = "",
    operatorIsSystemAdmin: bool = False,
) -> dict:
    """04 §8：发布 = 校验 34 张牌 + back 齐全后置 ENABLED；缺项列键并 400。"""
    skin = _loadSkin(skinCode)
    familyID = _int(skin, "familyID")
    _adminContext(loginID, familyID, operatorIsSystemAdmin)

    missing = _missingTileKeys(skin)
    if missing:
        raise _err(
            "SKIN_ASSET_INCOMPLETE",
            "皮肤资源不完整，缺少：" + "、".join(missing),
        )

    _updateSkin(
        loginID,
        skin,
        {"skinStatus": SKIN_ENABLED},
        clientIP,
        actionCode=ACTION_SKIN_PUBLISH,
        detail={
            "skin_code": _text(skin, "skinCode"),
            "status": SKIN_ENABLED,
            "asset_count": len(TILE_KEYS),
        },
    )
    return getSkin(loginID, _text(skin, "skinCode"), familyID)


def _missingTileKeys(skin: dict) -> list[str]:
    """缺失的 tile_key（按 05 §6.1 顺序）；DB 有行但文件被外部删掉也算缺。"""
    present = set()
    for row in _assetRowsOf(_int(skin, "recID")):
        tileKey = _text(row, "tileKey")
        if tileKey in TILE_KEY_SET and _text(row, "fileID") and _filePath(_text(row, "fileID")).is_file():
            present.add(tileKey)
    return [tileKey for tileKey in TILE_KEYS if tileKey not in present]


def disable(
    loginID: str,
    skinCode: str,
    clientIP: str = "",
    operatorIsSystemAdmin: bool = False,
) -> dict:
    """停用（status=DISABLED）：清单不再返回，但资源与文件保留。"""
    skin = _loadSkin(skinCode)
    familyID = _int(skin, "familyID")
    _adminContext(loginID, familyID, operatorIsSystemAdmin)
    _updateSkin(
        loginID,
        skin,
        {"skinStatus": SKIN_DISABLED, "defaultFlag": "0"},
        clientIP,
        detail={"skin_code": _text(skin, "skinCode"), "status": SKIN_DISABLED},
    )
    return getSkin(loginID, _text(skin, "skinCode"), familyID)


def softDelete(
    loginID: str,
    skinCode: str,
    clientIP: str = "",
    operatorIsSystemAdmin: bool = False,
) -> dict:
    """04 §8 #41：软删皮肤与资源行；物理文件延迟清理（schedule/dataClean.py）。"""
    skin = _loadSkin(skinCode)
    familyID = _int(skin, "familyID")
    _adminContext(loginID, familyID, operatorIsSystemAdmin)

    if familyID <= 0:
        raise _err("SKIN_BUILTIN_PROTECTED", "内置皮肤不能删除")

    assetRows = _assetRowsOf(_int(skin, "recID"))
    skinID = _int(skin, "recID")
    now = misc.getTime()
    with mysqlCommon.transaction():
        for row in assetRows:
            affected = mysqlCommon.update_mj_tile_skin_asset(
                mysqlCommon.MJ_TILE_SKIN_ASSET_TABLE,
                _int(row, "recID"),
                {"delFlag": "1", "modifyID": loginID, "modifyYMDHMS": now},
            )
            if affected < 0:
                raise SkinServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
        affected = mysqlCommon.update_mj_tile_skin_fields(
            skinID,
            {
                "delFlag": "1",
                "defaultFlag": "0",
                "skinStatus": SKIN_DISABLED,
                "modifyID": loginID,
                "modifyYMDHMS": now,
            },
        )
        if affected < 0:
            raise SkinServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
        # 家庭默认皮肤若指向它，一并清空，避免家庭主档悬空引用
        mysqlCommon.clear_mj_family_default_skin(familyID, _text(skin, "skinCode"))
        _audit(
            familyID,
            loginID,
            ACTION_SKIN_DELETE,
            _text(skin, "skinCode"),
            {
                "skin_code": _text(skin, "skinCode"),
                "asset_count": len(assetRows),
                "files_kept": True,
            },
            clientIP,
        )
    return {"ok": True}


# ---------------------------------------------------------------- 资源写操作


def _writeFile(skinCode: str, tileKey: str, data: bytes, ext: str) -> tuple[str, bool]:
    """落盘：`{tileKey}.{sha256[:8]}.{ext}`；返回 (relativePath, created)。

    文件名只由服务端生成；写完前确认目标路径仍在 tiles 根下（纵深防御）。
    同内容重复上传命中同名文件（内容哈希），不重复写盘。
    """
    root = _ensureTilesRoot().resolve()
    dirPath = (root / skinCode).resolve()
    if root != dirPath and root not in dirPath.parents:
        raise _err("SKIN_CODE_INVALID", "皮肤编码不合法")

    fileName = f"{tileKey}.{hashlib.sha256(data).hexdigest()[:8]}.{ext}"
    target = (dirPath / fileName).resolve()
    if dirPath not in target.parents:
        raise _err("SKIN_TILE_KEY_INVALID", "资源路径不合法")

    relativePath = f"tiles/{skinCode}/{fileName}"
    if target.is_file() and target.stat().st_size == len(data):
        return relativePath, False

    dirPath.mkdir(parents=True, exist_ok=True)
    tmpPath = dirPath / f".{fileName}.tmp"
    tmpPath.write_bytes(data)
    os.replace(tmpPath, target)
    return relativePath, True


def uploadAsset(
    loginID: str,
    skinCode: str,
    tileKey: str,
    data: bytes,
    fileName: str,
    clientIP: str = "",
    operatorIsSystemAdmin: bool = False,
) -> dict:
    """04 §8 #38：上传/替换单张资源（multipart）。返回 {tile_key, file_id, width, height}。"""
    skin = _loadSkin(skinCode)
    familyID = _int(skin, "familyID")
    _adminContext(loginID, familyID, operatorIsSystemAdmin)

    tileKey = (tileKey or "").strip()
    info = validateUpload(tileKey, fileName, data)

    skinID = _int(skin, "recID")
    assetRows = _assetRowsOf(skinID)
    if tileKey != PREVIEW_KEY:
        used = _skinTotalBytes(assetRows, excludeTileKey=tileKey)
        if used + len(data) > MAX_SKIN_BYTES:
            raise _err(
                "UPLOAD_TOO_LARGE",
                "单个皮肤总容量不能超过 8 MB，请先删除或压缩部分图片",
            )

    createdFile = False
    fileID = ""
    try:
        fileID, createdFile = _writeFile(_text(skin, "skinCode"), tileKey, data, info.ext)
    except OSError as error:
        logger.error("皮肤资源落盘失败 skin:%s tile:%s err:%s", skinCode, tileKey, error)
        raise SkinServiceError("DB_WRITE_FAILED", "图片保存失败，请重试", 500)

    now = misc.getTime()
    replaced = False
    try:
        with mysqlCommon.transaction():
            if tileKey == PREVIEW_KEY:
                # 预览图不入资源表（05 §6.1），只写皮肤主档
                affected = mysqlCommon.update_mj_tile_skin_fields(
                    skinID,
                    {
                        "previewFileID": fileID,
                        "modifyID": loginID,
                        "modifyYMDHMS": now,
                    },
                )
                if affected < 0:
                    raise SkinServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
            else:
                existing = mysqlCommon.query_mj_tile_skin_asset_by_key(
                    _text(skin, "skinCode"), tileKey
                )
                payload = {
                    "skinTileKey": "%s_%s" % (_text(skin, "skinCode"), tileKey),
                    "skinID": skinID,
                    "familyID": familyID,
                    "tileKey": tileKey,
                    "fileID": fileID,
                    "thumbFileID": None,
                    "width": info.width,
                    "height": info.height,
                    "fileSize": len(data),
                    "regID": loginID,
                    "regYMDHMS": now,
                    "modifyID": loginID,
                    "modifyYMDHMS": now,
                    "delFlag": "0",
                }
                if existing:
                    # 唯一键是 skinTileKey（软删行仍占位）：复用原行，不插新行
                    replaced = bool(_text(existing, "fileID"))
                    affected = mysqlCommon.update_mj_tile_skin_asset(
                        mysqlCommon.MJ_TILE_SKIN_ASSET_TABLE,
                        _int(existing, "recID"),
                        payload,
                    )
                    if affected < 0:
                        raise SkinServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
                else:
                    recID = mysqlCommon.insert_mj_tile_skin_asset(
                        mysqlCommon.MJ_TILE_SKIN_ASSET_TABLE, payload
                    )
                    if recID <= 0:
                        raise SkinServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)

            _audit(
                familyID,
                loginID,
                ACTION_SKIN_UPLOAD,
                _text(skin, "skinCode"),
                {
                    "skin_code": _text(skin, "skinCode"),
                    "tile_key": tileKey,
                    "file_id": fileID,
                    "width": info.width,
                    "height": info.height,
                    "bytes": len(data),
                    "replaced": replaced,
                },
                clientIP,
            )
    except Exception:
        # 数据库没写成 → 刚写的文件成为孤儿；删掉（同名文件可能是别人刚传的，故只在本次新建时删）
        if createdFile:
            try:
                _filePath(fileID).unlink(missing_ok=True)
            except OSError:
                pass
        raise

    return {
        "tile_key": tileKey,
        "file_id": fileID,
        "width": info.width,
        "height": info.height,
    }


def deleteAsset(
    loginID: str,
    skinCode: str,
    tileKey: str,
    clientIP: str = "",
    operatorIsSystemAdmin: bool = False,
) -> dict:
    """04 §8 #39：删除单张资源（软删；文件延迟清理，该张由前端回退 CSS）。"""
    skin = _loadSkin(skinCode)
    familyID = _int(skin, "familyID")
    _adminContext(loginID, familyID, operatorIsSystemAdmin)

    tileKey = (tileKey or "").strip()
    if tileKey not in UPLOADABLE_KEY_SET:
        raise _err("SKIN_TILE_KEY_INVALID", f"不支持的 tile_key：{tileKey}")

    skinID = _int(skin, "recID")
    now = misc.getTime()

    if tileKey == PREVIEW_KEY:
        if not _text(skin, "previewFileID"):
            raise _err("SKIN_ASSET_NOT_FOUND", "该皮肤没有预览图", 404)
        with mysqlCommon.transaction():
            affected = mysqlCommon.update_mj_tile_skin_fields(
                skinID,
                {"previewFileID": None, "modifyID": loginID, "modifyYMDHMS": now},
            )
            if affected < 0:
                raise SkinServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
            _audit(
                familyID,
                loginID,
                ACTION_SKIN_DELETE,
                _text(skin, "skinCode"),
                {"skin_code": _text(skin, "skinCode"), "tile_key": tileKey, "removed": True},
                clientIP,
            )
        return {"ok": True}

    existing = mysqlCommon.query_mj_tile_skin_asset_by_key(_text(skin, "skinCode"), tileKey)
    if not existing:
        raise _err("SKIN_ASSET_NOT_FOUND", "该皮肤没有这张牌的资源", 404)

    with mysqlCommon.transaction():
        affected = mysqlCommon.update_mj_tile_skin_asset(
            mysqlCommon.MJ_TILE_SKIN_ASSET_TABLE,
            _int(existing, "recID"),
            {"delFlag": "1", "modifyID": loginID, "modifyYMDHMS": now},
        )
        if affected < 0:
            raise SkinServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
        _audit(
            familyID,
            loginID,
            ACTION_SKIN_DELETE,
            _text(skin, "skinCode"),
            {
                "skin_code": _text(skin, "skinCode"),
                "tile_key": tileKey,
                "file_id": _text(existing, "fileID"),
                "removed": True,
            },
            clientIP,
        )
    return {"ok": True}


# ---------------------------------------------------------------- 主档补丁


def patchSkin(
    loginID: str,
    skinCode: str,
    skinName: str | None = None,
    status: str | None = None,
    sortOrder: int | None = None,
    isDefault: bool | None = None,
    clientIP: str = "",
    operatorIsSystemAdmin: bool = False,
) -> dict:
    """04 §8 #40：改名 / 改状态 / 改排序 / 设默认（一次请求只写一次审计）。"""
    skin = _loadSkin(skinCode)
    familyID = _int(skin, "familyID")
    _adminContext(loginID, familyID, operatorIsSystemAdmin)

    dataSet: dict = {}
    detail: dict = {}

    if skinName is not None:
        newName = _validateSkinName(skinName)
        if newName != _text(skin, "skinName"):
            dataSet["skinName"] = newName
            detail["skin_name"] = {"before": _text(skin, "skinName"), "after": newName}

    if sortOrder is not None:
        try:
            order = int(sortOrder)
        except (TypeError, ValueError):
            raise _err("SKIN_SORT_INVALID", "排序号必须是整数")
        dataSet["sortOrder"] = order
        detail["sort_order"] = {"before": _int(skin, "sortOrder"), "after": order}

    if status is not None:
        newStatus = (status or "").strip().upper()
        if newStatus not in SKIN_STATUS_LIST:
            raise _err("SKIN_STATUS_INVALID", "皮肤状态只支持 ENABLED / DISABLED")
        if newStatus == SKIN_ENABLED and _text(skin, "skinStatus") != SKIN_ENABLED:
            missing = _missingTileKeys(skin)
            if missing:
                raise _err(
                    "SKIN_ASSET_INCOMPLETE",
                    "皮肤资源不完整，缺少：" + "、".join(missing),
                )
        dataSet["skinStatus"] = newStatus
        detail["status"] = {"before": _text(skin, "skinStatus"), "after": newStatus}
        if newStatus == SKIN_DISABLED:
            dataSet["defaultFlag"] = "0"
            detail["is_default"] = {"before": _flag(skin.get("defaultFlag")), "after": False}

    if isDefault is not None and bool(isDefault):
        # 设默认有自己的唯一性约束与审计动作，交给 setDefault。
        # 顺序：先启用（若要），再设默认，最后改名/排序——任何一步失败都不会留下半成品。
        if dataSet.get("skinStatus") == SKIN_ENABLED:
            _updateSkin(
                loginID, skin, dataSet, clientIP, actionCode=ACTION_SKIN_PUBLISH, detail=detail
            )
            dataSet = {}
            skin = _loadSkin(skinCode)
        result = setDefault(
            loginID,
            skinCode,
            clientIP=clientIP,
            operatorIsSystemAdmin=operatorIsSystemAdmin,
        )
        if dataSet:
            _updateSkin(loginID, skin, dataSet, clientIP, detail=detail)
            return getSkin(loginID, skinCode, familyID)
        return result

    actionCode = ACTION_SKIN_UPDATE
    if detail.get("status", {}).get("after") == SKIN_ENABLED:
        actionCode = ACTION_SKIN_PUBLISH

    if dataSet:
        _updateSkin(loginID, skin, dataSet, clientIP, actionCode=actionCode, detail=detail)
    return getSkin(loginID, skinCode, familyID)


__all__ = [
    "ACTION_SKIN_CREATE",
    "ACTION_SKIN_DEFAULT",
    "ACTION_SKIN_DELETE",
    "ACTION_SKIN_PUBLISH",
    "ACTION_SKIN_UPLOAD",
    "FALLBACK_SKIN_CODE",
    "MAX_SKIN_BYTES",
    "MAX_UPLOAD_BYTES",
    "PREVIEW_KEY",
    "SKIN_DISABLED",
    "SKIN_ENABLED",
    "SkinServiceError",
    "TILE_KEYS",
    "TILE_KEY_SET",
    "buildETag",
    "createSkin",
    "deleteAsset",
    "disable",
    "etagMatches",
    "getSkin",
    "listSkins",
    "patchSkin",
    "publicURL",
    "publish",
    "setDefault",
    "sniffImage",
    "softDelete",
    "tilesRoot",
    "uploadAsset",
    "validateUpload",
]
