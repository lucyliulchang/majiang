"""规则模板的增删改查、复制派生与校验。"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import db_session, get_current_user
from app.db.models import RuleTemplate, User
from app.schemas.rule import (
    RuleConfig,
    RuleTemplateCreate,
    RuleTemplateOut,
    RuleTemplateUpdate,
    RuleValidateRequest,
    RuleValidateResponse,
)

router = APIRouter(prefix="/rules", tags=["rules"])


def summary_text(config: RuleConfig) -> str:
    parts = [
        f"底分 {config.base_score}",
        "2 的 N 次方" if config.fan_mode == "exponential" else "线性累加",
    ]
    if config.fan_cap is not None:
        parts.append(f"封顶 {config.fan_cap} 番")
    parts.append("可以吃" if config.allow_chow else "不能吃")
    if config.turn_timeout.enabled:
        parts.append(f"限时 {config.turn_timeout.seconds} 秒")
    else:
        parts.append("不限时")
    if config.kong_score.enabled:
        parts.append(
            f"杠分 明{config.kong_score.exposed}/暗{config.kong_score.hidden}/补{config.kong_score.added}"
        )
    else:
        parts.append("杠不计分")
    parts.append("听牌提示开" if config.ting_hint.enabled else "无听牌提示")
    return " · ".join(parts)


def to_out(row: RuleTemplate) -> RuleTemplateOut:
    return RuleTemplateOut(
        id=row.id,
        owner_id=row.owner_id,
        name=row.name,
        description=row.description or "",
        config=RuleConfig.model_validate(row.config or {}),
        is_preset=row.is_preset,
        is_active=row.is_active,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def load_visible(session: Session, user: User, template_id: int) -> RuleTemplate:
    row = session.get(RuleTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="规则模板不存在")
    if not row.is_preset and row.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="这套规则不是你的")
    return row


def load_editable(session: Session, user: User, template_id: int) -> RuleTemplate:
    row = load_visible(session, user, template_id)
    if row.is_preset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="预置模板不能直接改，请先复制一份",
        )
    if row.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="这套规则不是你的")
    return row


@router.get("", response_model=list[RuleTemplateOut])
def list_rules(
    user: User = Depends(get_current_user), session: Session = Depends(db_session)
) -> list[RuleTemplateOut]:
    rows = session.scalars(
        select(RuleTemplate)
        .where(
            RuleTemplate.is_active.is_(True),
            or_(RuleTemplate.is_preset.is_(True), RuleTemplate.owner_id == user.id),
        )
        .order_by(RuleTemplate.is_preset.desc(), RuleTemplate.id)
    ).all()
    return [to_out(row) for row in rows]


@router.post("", response_model=RuleTemplateOut)
def create_rule(
    payload: RuleTemplateCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(db_session),
) -> RuleTemplateOut:
    row = RuleTemplate(
        owner_id=user.id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        config=payload.config.model_dump(),
        is_preset=False,
    )
    session.add(row)
    session.commit()
    return to_out(row)


@router.post("/validate", response_model=RuleValidateResponse)
def validate_rule(payload: RuleValidateRequest) -> RuleValidateResponse:
    return RuleValidateResponse(
        ok=True, message="规则合法", summary=summary_text(payload.config)
    )


@router.get("/{template_id}", response_model=RuleTemplateOut)
def get_rule(
    template_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(db_session),
) -> RuleTemplateOut:
    return to_out(load_visible(session, user, template_id))


@router.put("/{template_id}", response_model=RuleTemplateOut)
def update_rule(
    template_id: int,
    payload: RuleTemplateUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(db_session),
) -> RuleTemplateOut:
    row = load_editable(session, user, template_id)
    if payload.name is not None:
        row.name = payload.name.strip()
    if payload.description is not None:
        row.description = payload.description.strip()
    if payload.config is not None:
        row.config = payload.config.model_dump()
    if payload.is_active is not None:
        row.is_active = payload.is_active
    session.commit()
    return to_out(row)


@router.post("/{template_id}/duplicate", response_model=RuleTemplateOut)
def duplicate_rule(
    template_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(db_session),
) -> RuleTemplateOut:
    source = load_visible(session, user, template_id)
    row = RuleTemplate(
        owner_id=user.id,
        name=f"{source.name} 副本"[:64],
        description=source.description or "",
        config=dict(source.config or {}),
        is_preset=False,
    )
    session.add(row)
    session.commit()
    return to_out(row)


@router.delete("/{template_id}", response_model=RuleTemplateOut)
def deactivate_rule(
    template_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(db_session),
) -> RuleTemplateOut:
    row = load_editable(session, user, template_id)
    row.is_active = False
    session.commit()
    return to_out(row)


def validate_or_error(raw: dict) -> RuleConfig:
    try:
        return RuleConfig.model_validate(raw)
    except ValidationError as error:
        first = error.errors()[0]
        message = first.get("msg", "规则不合法").replace("Value error, ", "")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from error
