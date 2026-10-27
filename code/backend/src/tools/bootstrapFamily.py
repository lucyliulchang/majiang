"""开箱脚本：创建初始家庭，并把创建者挂成 OWNER（02 §7）。

由旧的 scripts/bootstrap_family.py（SQLAlchemy 版）改写为 mysqlCommon 版：
- 不再创建本地账号与口令（账号由账号服务负责，本库 USER_BASIC 只做镜像）；
- 一个事务内写 mj_family + mj_family_member(OWNER) + mj_user_pref.lastFamilyID；
- 按 familyCode / familyMemberKey / loginID 先查后插，重复执行幂等。

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


def bootstrapFamily(ownerLoginID, familyName, familyCode, defaultRuleFamilyCode="generic", defaultSkinCode="css-classic"):
    """事务内确保：家庭存在、owner 是 OWNER、owner 的 lastFamilyID 指向该家庭。"""
    from common import miscCommon as misc
    from common import mysqlCommon as comMysql

    result = {"familyID": 0, "familyCreated": False, "memberCreated": False, "prefUpdated": False}

    with comMysql.transaction():
        # 1) 家庭主档：familyCode 唯一
        familyRows = comMysql.queryTableGeneral(
            comMysql.MJ_FAMILY_TABLE,
            condList=[["familyCode", "=", familyCode]],
            order="create",
            limitNum=1,
        )
        if familyRows:
            familyID = int(familyRows[0]["recID"])
        else:
            familyID = comMysql.insert_mj_family(
                comMysql.MJ_FAMILY_TABLE,
                {
                    "familyCode": familyCode,
                    "familyName": familyName,
                    "ownerLoginID": ownerLoginID,
                    "defaultRuleFamilyCode": defaultRuleFamilyCode,
                    "defaultSkinCode": defaultSkinCode,
                    "familyStatus": "ENABLED",
                    "sortOrder": 0,
                    "regID": ownerLoginID,
                    "regYMDHMS": misc.getTime(),
                },
            )
            if familyID <= 0:
                raise RuntimeError("mj_family 写入失败")
            result["familyCreated"] = True
        result["familyID"] = familyID

        # 2) 成员关系：familyMemberKey = familyID_loginID（02 §2.1 的组合键约定）
        memberKey = f"{familyID}_{ownerLoginID}"
        memberRows = comMysql.queryTableGeneral(
            comMysql.MJ_FAMILY_MEMBER_TABLE,
            condList=[["familyMemberKey", "=", memberKey]],
            order="create",
            limitNum=1,
        )
        if memberRows:
            if memberRows[0].get("memberRole") != "OWNER":
                comMysql.update_mj_family_member(
                    comMysql.MJ_FAMILY_MEMBER_TABLE,
                    int(memberRows[0]["recID"]),
                    {"memberRole": "OWNER", "modifyID": ownerLoginID, "modifyYMDHMS": misc.getTime()},
                )
        else:
            memberRecID = comMysql.insert_mj_family_member(
                comMysql.MJ_FAMILY_MEMBER_TABLE,
                {
                    "familyMemberKey": memberKey,
                    "familyID": familyID,
                    "loginID": ownerLoginID,
                    "memberRole": "OWNER",
                    "memberStatus": "ACTIVE",
                    "joinedYMDHMS": misc.getTime(),
                    "regID": ownerLoginID,
                    "regYMDHMS": misc.getTime(),
                },
            )
            if memberRecID <= 0:
                raise RuntimeError("mj_family_member 写入失败")
            result["memberCreated"] = True

        # 3) 用户偏好：当前家庭指向新家庭；无记录则建一条（开关用默认值，不用空串）
        prefRows = comMysql.queryTableGeneral(
            comMysql.MJ_USER_PREF_TABLE,
            condList=[["loginID", "=", ownerLoginID]],
            order="create",
            limitNum=1,
        )
        if prefRows:
            if int(prefRows[0].get("lastFamilyID") or 0) != familyID:
                comMysql.update_mj_user_pref(
                    comMysql.MJ_USER_PREF_TABLE,
                    int(prefRows[0]["recID"]),
                    {"lastFamilyID": familyID, "modifyID": ownerLoginID, "modifyYMDHMS": misc.getTime()},
                )
                result["prefUpdated"] = True
        else:
            prefRecID = comMysql.insert_mj_user_pref(
                comMysql.MJ_USER_PREF_TABLE,
                {
                    "loginID": ownerLoginID,
                    "lastFamilyID": familyID,
                    "skinCode": None,
                    "soundEnabledFlag": "1",
                    "soundVolume": 70,
                    "chatSoundFlag": "1",
                    "showTenpaiFlag": "1",
                    "regID": ownerLoginID,
                    "regYMDHMS": misc.getTime(),
                },
            )
            if prefRecID <= 0:
                raise RuntimeError("mj_user_pref 写入失败")
            result["prefUpdated"] = True

    return result


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

    result = bootstrapFamily(args.owner, args.name, args.code)
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
