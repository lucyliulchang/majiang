"""皮肤协议模型（04 §8、05 §6.4）。

`assets` 的键只能是 05 §6.1 的 35 个 tile_key；`fallback` 固定 `css-classic`，
前端据此在整皮肤不可用时回退 CSS（05 §6.3）。
"""

from pydantic import BaseModel, Field


class SkinOut(BaseModel):
    """04 §8 的 skin；`family_code` 为 null 表示全局内置皮肤。"""

    skin_code: str
    skin_name: str
    family_code: str | None = None
    is_default: bool = False
    status: str = "ENABLED"
    tile_aspect: float = 0.6667
    asset_count: int = 0
    preview_url: str | None = None
    assets: dict[str, str] = Field(default_factory=dict)
    fallback: str = "css-classic"
    updated_at: str = ""


class SkinCreateRequest(BaseModel):
    """POST /api/skins（04 §8 #37）；`skin_code` 不传则由服务端生成。"""

    family_code: str = ""
    skin_code: str = ""
    skin_name: str = Field(min_length=1, max_length=64)


class SkinUpdateRequest(BaseModel):
    """PATCH /api/skins/{skin_code}（04 §8 #40）。"""

    skin_name: str | None = Field(default=None, min_length=1, max_length=64)
    status: str | None = None
    sort_order: int | None = None
    is_default: bool | None = None


class SkinAssetOut(BaseModel):
    """PUT /api/skins/{skin_code}/{tile_key} 的响应（04 §8 #38）。

    `file_id` 是库内相对路径 `tiles/{skinCode}/{file}`；前端拼 `/majiangapp/` 前缀。
    """

    tile_key: str
    file_id: str
    width: int = 0
    height: int = 0


__all__ = [
    "SkinAssetOut",
    "SkinCreateRequest",
    "SkinOut",
    "SkinUpdateRequest",
]
