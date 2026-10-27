"""开箱脚本：创建初始家庭，并把创建者挂成 OWNER（02 §7、04 §3）。

实现已收敛到 `processor/familyService.bootstrapFamily`（S4）：脚本只负责解析参数、
选择环境、打印结果，业务与事务都在 service 层，避免两处逻辑漂移。

约定：
- 不创建本地账号与口令（账号由账号服务负责，本库 USER_BASIC 只做镜像）；
- 一个事务内写 mj_family + mj_family_member(OWNER) + mj_user_pref.lastFamilyID + 审计；
- 按 familyCode / (familyID, loginID) 先查后插，重复执行幂等。

用法（工作目录 = code/backend/src）：
    python tools/bootstrapFamily.py --owner 13800000000 --name "廉家" --code lianjia
    python tools/bootstrapFamily.py --owner 13800000000 --name "廉家" --code lianjia --test
"""

import argparse
import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)


def parseArgs(argv=None):
    parser = argparse.ArgumentParser(description="创建初始家庭并绑定 OWNER")
    parser.add_argument("--owner", required=True, help="家庭管理员 loginID")
    parser.add_argument("--name", default="廉家", help="家庭名称，默认 廉家")
    parser.add_argument("--code", default="lianjia", help="家庭编码（幂等键），默认 lianjia")
    parser.add_argument("--env", default="local", choices=["local", "test_server", "server_01"])
    parser.add_argument("--test", action="store_true", help="指向测试库 mahjong_test")
    return parser.parse_args(argv)


def bootstrapFamily(
    ownerLoginID,
    familyName,
    familyCode,
    defaultRuleFamilyCode="generic",
    defaultSkinCode="css-classic",
):
    """兼容旧签名的入口：直接转发到 processor.familyService。"""
    from processor import familyService

    return familyService.bootstrapFamily(
        ownerLoginID,
        familyName,
        familyCode,
        defaultRuleFamilyCode=defaultRuleFamilyCode,
        defaultSkinCode=defaultSkinCode,
    )


def main(argv=None):
    args = parseArgs(argv)

    os.environ["APP_ENV"] = args.env
    if args.test or args.env == "test_server":
        os.environ["MYSQL_WRITE_DB"] = "mahjong_test"
        os.environ["MYSQL_READ_DB"] = "mahjong_test"

    from config import mysqlSettings as mysqlSettings

    if mysqlSettings.dbW is None:
        print("[bootstrapFamily] 未建立数据库连接(MYSQL_SKIP_CONNECT=1)，已中止")
        return 1

    if not mysqlSettings.pingServer():
        print("[bootstrapFamily] 连不上数据库，已中止（请检查 .env 的 MYSQL_* 与实例状态）")
        return 1

    from common.bizCommon import BizError

    try:
        result = bootstrapFamily(args.owner, args.name, args.code)
    except BizError as error:
        print(f"[bootstrapFamily] 失败 code={error.code} message={error.message}")
        return 1

    print(
        "[bootstrapFamily] env:%s db:%s owner:%s code:%s -> familyID=%d, familyCreated=%s, memberCreated=%s, prefUpdated=%s"
        % (
            mysqlSettings.ENV_NAME,
            mysqlSettings.MYSQL_WRITE_DB,
            args.owner,
            args.code,
            result["familyID"],
            result["familyCreated"],
            result["memberCreated"],
            result["prefUpdated"],
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
