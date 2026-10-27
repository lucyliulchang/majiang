"""规则族与模板路由（04 §5，8 个端点）。

分层（01 §2）：本文件只做「解析参数 → 家庭上下文 → 调 ruleService → 套响应模型」。
权限、族能力校验、事务与错误码都在 `processor/ruleService.py`。
"""

from fastapi import APIRouter, Depends

from main.deps import (
    CurrentUser,
    FamilyContext,
    current_active_family,
    current_family,
    current_user,
    familyContextOf,
)
from processor import ruleService
from schemas.rule import (
    RuleFamilyOut,
    RuleTemplateCreateRequest,
    RuleTemplateDuplicateRequest,
    RuleTemplateOut,
    RuleTemplateUpdateRequest,
    RuleValidateRequest,
    RuleValidateResponse,
)

router = APIRouter(prefix="/rules", tags=["rules"])
family_router = APIRouter(prefix="/rule-families", tags=["rules"])


def _familyOf(
    user: CurrentUser, familyCode: str, fallback: FamilyContext
) -> FamilyContext:
    """请求体里的 family_code 优先；缺省用当前家庭（04 §1 的解析顺序）。"""
    code = (familyCode or "").strip()
    if not code or code == fallback.family_code:
        return fallback
    return familyContextOf(user.login_id, code, requireEnabled=True)


@family_router.get("", response_model=list[RuleFamilyOut])
def list_rule_families(user: CurrentUser = Depends(current_user)) -> list[RuleFamilyOut]:
    """规则族清单（登录即可读）；`ready=false` 的族可列模板但不可开桌。"""
    return [RuleFamilyOut(**row) for row in ruleService.listRuleFamilies(user.login_id)]


@router.get("", response_model=list[RuleTemplateOut])
def list_rules(
    rule_family_code: str = "",
    context: FamilyContext = Depends(current_active_family),
) -> list[RuleTemplateOut]:
    """模板列表：本家庭自有 + 全局预置，只列启用项（04 §5 #18）。"""
    rows = ruleService.listTemplates(
        context.login_id,
        context.family_id,
        context.family_code,
        ruleFamilyCode=rule_family_code,
    )
    return [RuleTemplateOut(**row) for row in rows]


@router.post("", response_model=RuleTemplateOut)
def create_rule(
    payload: RuleTemplateCreateRequest,
    user: CurrentUser = Depends(current_user),
    context: FamilyContext = Depends(current_active_family),
) -> RuleTemplateOut:
    """新建家庭模板（04 §5 #19）。"""
    family = _familyOf(user, payload.family_code, context)
    return RuleTemplateOut(
        **ruleService.createTemplate(
            user.login_id,
            family.family_id,
            family.family_code,
            payload.rule_family_code,
            payload.template_name,
            payload.description,
            payload.config,
        )
    )


@router.post("/validate", response_model=RuleValidateResponse)
def validate_rule(
    payload: RuleValidateRequest,
    _: CurrentUser = Depends(current_user),
) -> RuleValidateResponse:
    """校验规则参数，不落库（04 §5 #24）。

    校验失败按协议返回 `ok=false + code`（不是 4xx）：这是「试算」接口，
    前端要在表单里就地展示原因，而不是弹全局错误。
    """
    try:
        config = ruleService.validateConfig(payload.rule_family_code, payload.config)
    except ruleService.RuleServiceError as error:
        return RuleValidateResponse(ok=False, code=error.code, message=error.message)
    return RuleValidateResponse(
        ok=True,
        code="OK",
        message="规则合法",
        summary=ruleService.summaryText(config),
    )


@router.get("/{template_id}", response_model=RuleTemplateOut)
def get_rule(
    template_id: int,
    user: CurrentUser = Depends(current_user),
) -> RuleTemplateOut:
    """模板详情：家庭成员或全局预置（04 §5 #20）。"""
    return RuleTemplateOut(**ruleService.getTemplate(user.login_id, template_id))


@router.put("/{template_id}", response_model=RuleTemplateOut)
def update_rule(
    template_id: int,
    payload: RuleTemplateUpdateRequest,
    user: CurrentUser = Depends(current_user),
) -> RuleTemplateOut:
    """改模板：创建者/家庭管理员；预置模板 400（04 §5 #21）。"""
    return RuleTemplateOut(
        **ruleService.updateTemplate(
            user.login_id,
            template_id,
            templateName=payload.template_name,
            description=payload.description,
            rawConfig=payload.config,
            activeFlag=payload.active_flag,
        )
    )


@router.post("/{template_id}/duplicate", response_model=RuleTemplateOut)
def duplicate_rule(
    template_id: int,
    payload: RuleTemplateDuplicateRequest,
    user: CurrentUser = Depends(current_user),
    context: FamilyContext = Depends(current_active_family),
) -> RuleTemplateOut:
    """复制模板到本家庭（04 §5 #22）：预置模板只能复制后编辑。"""
    family = _familyOf(user, payload.family_code, context)
    return RuleTemplateOut(
        **ruleService.duplicateTemplate(
            user.login_id,
            template_id,
            family.family_id,
            family.family_code,
            payload.template_name,
        )
    )


@router.delete("/{template_id}", response_model=RuleTemplateOut)
def deactivate_rule(
    template_id: int,
    user: CurrentUser = Depends(current_user),
) -> RuleTemplateOut:
    """停用模板（04 §5 #23）：`active_flag=0`，已开桌的快照不受影响。"""
    return RuleTemplateOut(**ruleService.deactivateTemplate(user.login_id, template_id))
