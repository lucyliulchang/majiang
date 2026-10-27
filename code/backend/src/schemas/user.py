"""用户偏好的请求/响应模型（04 §4）。

约定：
  - `PUT` 是局部更新：只处理 `exclude_unset` 里出现的字段；
  - `last_family_code` / `skin_code` 传**空串**表示清空（回到默认），传 `null`/不传表示不改；
  - 没有任何 BGM 字段（音效纯前端播放，见 08-音效设计）。
"""

from pydantic import BaseModel


class PrefOut(BaseModel):
    last_family_code: str | None = None
    skin_code: str | None = None
    sound_enabled: bool = True
    sound_volume: int = 70
    chat_sound: bool = True
    show_tenpai: bool = True


class PrefUpdateRequest(BaseModel):
    last_family_code: str | None = None
    skin_code: str | None = None
    sound_enabled: bool | None = None
    sound_volume: int | None = None
    chat_sound: bool | None = None
    show_tenpai: bool | None = None
