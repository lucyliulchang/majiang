#! /usr/bin/env python3
#encoding: utf-8

#Filename: mysqlCommon.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Description:   家庭麻将全库读写唯一入口。手写区（本文件上半部）+ 生成区（下半部）。
#
#组成：
#  1) 手写区：公共件（通用增删改查、JSON 归一化、事务）+ USER_BASIC 8 个函数 +
#     02 §8 的 query_mj_* 扩展查询；
#  2) 生成区（#===== auto-generated sections 标记包裹）：database/mj_*.txt 经
#     database/mysqlCodeGenerator.py 产出、再由 tools/mergeMysqlCommon.py 合并进来。
#
#红线（01 §7.3）：
#  R1 本模块是业务层访问数据库的唯一入口，业务代码禁止裸 SQL；
#  R2 表结构唯一来源 database/*.txt；改表流程 = 改 txt → tools/genTableCode.ps1 →
#     tools/mergeMysqlCommon.py → tools/initTables.py；
#  R3 生成段禁止手改（重跑即覆盖）；手写段禁止被覆盖。
#
#生成器已知坑（02 §2.2）：
#  坑2 生成版 query_* 的 LIMIT 拼装被注释掉 → 本文件不使用生成版 query，列表查询由
#     手写 query_mj_* 提供；
#  坑3 insert_/update_ 对数值列强制 int()/float() 且异常置 0 → 可空数值列约定「0 = 未设置」。

_VERSION = "20261027"

import os
import re
import sys
import traceback
from contextlib import contextmanager

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

#common functions(log,time,string, json etc)
from common import miscCommon as misc
from common.loggingCommon import get_logger
from common.mysqlHandle import DBUnavailableError

#setting files
from config import mysqlSettings as mysqlSettings

_LOG = get_logger("mahjong.mysql")
_DEBUG = True

#分页默认值（02 §8 / 04 §1）：列表 20、上限 100；战绩与审计默认 30
_DEF_QUERY_LIMIT_NUM = 20
_DEF_QUERY_LIMIT_MAX = 100
_DEF_GAME_QUERY_LIMIT_NUM = 30
_DEF_CHAT_QUERY_LIMIT_NUM = 50

_CONST_YES = "1"
_CONST_NO = "0"

#写句柄：生成代码统一通过 mysqlDB.executeWrite/executeRead 访问数据库
mysqlDB = mysqlSettings.dbW
database_name = mysqlSettings.MYSQL_DATABASE_NAME

#查询条件运算符白名单（字段名另做正则校验，条件值一律走参数化占位符）
_DEF_QUERY_OPERATOR_LIST = ["=", "!=", ">", "<", ">=", "<=", "LIKE"]
#字段名合法性：只允许字母开头的字母/数字/下划线组合，避免拼接字段名引入注入
_DEF_QUERY_FIELD_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

#表名常量（业务层引用常量，禁止手写表名字面量）
MJ_FAMILY_TABLE = "mj_family"
MJ_FAMILY_MEMBER_TABLE = "mj_family_member"
MJ_USER_PREF_TABLE = "mj_user_pref"
MJ_RULE_FAMILY_TABLE = "mj_rule_family"
MJ_RULE_TEMPLATE_TABLE = "mj_rule_template"
MJ_ROOM_TABLE = "mj_room"
MJ_GAME_TABLE = "mj_game"
MJ_GAME_PLAYER_TABLE = "mj_game_player"
MJ_GAME_ROUND_TABLE = "mj_game_round"
MJ_ROOM_MESSAGE_TABLE = "mj_room_message"
MJ_TILE_SKIN_TABLE = "mj_tile_skin"
MJ_TILE_SKIN_ASSET_TABLE = "mj_tile_skin_asset"
MJ_AUDIT_LOG_TABLE = "mj_audit_log"
MJ_SCHEMA_VERSION_TABLE = "mj_schema_version"
USER_BASIC_TABLE = "USER_BASIC"

#建表/清理顺序（无外键，顺序只影响可读性）
TABLE_NAME_LIST = [
    MJ_FAMILY_TABLE,
    MJ_FAMILY_MEMBER_TABLE,
    MJ_USER_PREF_TABLE,
    MJ_RULE_FAMILY_TABLE,
    MJ_RULE_TEMPLATE_TABLE,
    MJ_ROOM_TABLE,
    MJ_GAME_TABLE,
    MJ_GAME_PLAYER_TABLE,
    MJ_GAME_ROUND_TABLE,
    MJ_ROOM_MESSAGE_TABLE,
    MJ_TILE_SKIN_TABLE,
    MJ_TILE_SKIN_ASSET_TABLE,
    MJ_AUDIT_LOG_TABLE,
    MJ_SCHEMA_VERSION_TABLE,
]
TABLE_NAME_SET = set(TABLE_NAME_LIST)


#common begin

def toIntSafe(value, default = 0):
    """数值安全转换：任意输入转 int，失败返回 default
       （与生成器「异常置 0」的口径一致，可空数值列统一约定 0 = 未设置）"""
    result = default
    try:
        result = int(value)
    except Exception:
        result = default
    return result


def clampLimit(limitNum, default = _DEF_QUERY_LIMIT_NUM, maxNum = _DEF_QUERY_LIMIT_MAX):
    """分页上限收敛：<=0 用默认值，超过 maxNum 截断，非数字回落到默认值。"""
    value = toIntSafe(limitNum, default)
    if value <= 0:
        value = default
    return min(value, maxNum)


#本工程所有 JSON 类型列的统一名单（源自 database/mj_*.txt 表定义），写库时据此做归一化
#新增 JSON 列时请在此追加，否则空串仍会被当成非法 JSON 报错（MySQL 错误 3140）
MYSQL_JSON_COLUMN_NAME_LIST = [
    "capabilityJson",   #mj_rule_family
    "configJson",       #mj_rule_template
    "ruleSnapshot",     #mj_room / mj_game
    "seatDrawJson",     #mj_game
    "fanItemsJson",     #mj_game_round
    "scoreDeltaJson",   #mj_game_round
    "payerJson",        #mj_game_round
    "detailJson",       #mj_audit_log
]
MYSQL_JSON_COLUMN_NAME_SET = set(MYSQL_JSON_COLUMN_NAME_LIST)


def normalizeJsonValue4DB(v):
    """JSON 列值写库前归一化（02 §5）：
       缺省/None/空串 -> None（落库为 SQL NULL，避免 '' 被 JSON 校验拒绝）
       dict/list     -> json.dumps 成 JSON 文本
       其它（已是合法 JSON 文本） -> 原样返回，由 MySQL 报错暴露问题"""
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        try:
            return misc.jsonDumps(v)
        except Exception:
            return None
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


def dataFormatConvert(dataList):
    """查询结果出参归一：数值转字符串（前端只认字符串），None 转空串，
       JSON 列文本转对象；解析失败按 misc.jsonLoads 的容错口径返回 {}。"""
    result = dataList
    for data in dataList:
        for k, v in list(data.items()):
            if isinstance(v, bool):
                data[k] = str(v)
            elif isinstance(v, int):
                data[k] = str(v)
            elif isinstance(v, float):
                data[k] = str(v)
            elif v is None:
                data[k] = ""
            if k in MYSQL_JSON_COLUMN_NAME_SET and data[k] != "":
                data[k] = misc.jsonLoads(data[k])
    return result


@contextmanager
def transaction():
    """写事务上下文：`with transaction() as tx:`，异常自动回滚。

    tx 即写句柄（mysqlDB），需要拿到底层连接可用 tx.dbW。
    事务内的 insert_*/update_* 不再各自提交，统一由本上下文 commit。
    """
    if mysqlDB is None:
        raise DBUnavailableError("MYSQL_SKIP_CONNECT=1，未建立数据库连接")
    mysqlDB.begin()
    try:
        yield mysqlDB
        mysqlDB.commit()
    except Exception:
        mysqlDB.rollback()
        raise


def chkTableExist(tableName):
    """表是否存在（建表脚本用于回报结果）"""
    result = False
    sqlStr = "SELECT table_name FROM information_schema.TABLES WHERE table_schema = %s and table_name = %s;"
    rtn = mysqlDB.executeRead(sqlStr, (database_name, tableName))
    if rtn > 0:
        result = True
    return result


def dropTableGeneral(tableName):
    """删除表（破坏性操作入口）
       ★★ 生成表/生产库禁止调用 ★★ 仅保留给测试库做建表演练；tools/initTables.py 不调用"""
    result = False
    try:
        sqlStr = "DROP TABLE %s;" % tableName
        mysqlDB.executeWrite(sqlStr)
        result = not chkTableExist(tableName)
    except Exception:
        result = False
    return result


def insertTableGeneral(tableName, dataSet, selfDefinedPrimaryKey = _CONST_NO):
    """通用插入：参数化拼装，JSON 列自动归一化，返回自增主键（失败返回 0）"""
    result = 0
    try:
        insertStr = "INSERT INTO %s (" % tableName
        fieldNameList = [insertStr]
        placeHolderList = []
        valuesList = []

        for k, v in dataSet.items():
            #JSON 列：空串为非法 JSON，归一为 NULL；dict/list 自动转 JSON 文本
            if k in MYSQL_JSON_COLUMN_NAME_SET:
                v = normalizeJsonValue4DB(v)
            fieldNameList.append(k)
            fieldNameList.append(",")
            valuesList.append(v)
            placeHolderList.append("%s")
            placeHolderList.append(",")

        fieldNameList = fieldNameList[0:-1]
        fieldNameList.append(")  VALUES (" )
        placeHolderList = placeHolderList[0:-1]
        fieldNameList.extend(placeHolderList)
        fieldNameList.append(")")
        sqlStr = "".join(fieldNameList)
        rtn = mysqlDB.executeWrite(sqlStr, tuple(valuesList))

        if rtn > 0:
            if selfDefinedPrimaryKey == _CONST_NO:
                result = mysqlDB.insertID()
            else:
                result = rtn

    except Exception as e:
        errMsg = "%s %s" % ("insertTableGeneral", str(e))
        if _DEBUG:
            _LOG.error(errMsg)

    return result


def updateTableGeneral(tableName, keySqlstr, keyValues, dataSet):
    """通用更新：keySqlstr 为 WHERE 条件片段（只含占位符），keyValues 为条件值列表"""
    result = 0
    try:
        tempStr = "UPDATE %s SET " % tableName
        fieldNameList = [tempStr]
        valuesList = []
        for k, v in dataSet.items():
            #JSON 列归一化，与 insertTableGeneral 保持一致
            if k in MYSQL_JSON_COLUMN_NAME_SET:
                v = normalizeJsonValue4DB(v)
            fieldNameList.append("%s = " % (k))
            fieldNameList.append("%s")
            fieldNameList.append(",")
            valuesList.append(v)

        fieldNameList = fieldNameList[0:-1]
        fieldNameList.append("  WHERE %s;" % (keySqlstr))
        valuesList.extend(keyValues)

        sqlStr = "".join(fieldNameList)
        result = mysqlDB.executeWrite(sqlStr, tuple(valuesList))

    except Exception as e:
        errMsg = "%s %s" % ("updateTableGeneral", str(e))
        if _DEBUG:
            _LOG.error(errMsg)

    return result


def queryTableGeneral(tableName, condList = None, likeOrList = None, keyword = "",
                      columns = "*", delFlag = "0", order = "create",
                      limitNum = _DEF_QUERY_LIMIT_NUM, beforeID = 0):
    """全部手写 query_* 的公共实现：
       - condList:   [[字段名, 运算符, 值], ...]，运算符取 _DEF_QUERY_OPERATOR_LIST 白名单
       - likeOrList: 关键词模糊匹配的字段清单，与 keyword 组成 (a LIKE %kw% OR b LIKE %kw%)
       - delFlag:    非空时叠加 (delFlag = 值 OR delFlag IS NULL)；传 "" 表示不过滤已删除
       - order:      modify -> modifyYMDHMS 降序；create -> recID 升序；其他 -> recID 降序
       - limitNum:   LIMIT 条数，<=0 回落默认值，最大 100，防止全表拉取
       - beforeID:   >0 时按 recID < beforeID 深翻页（避免 OFFSET）
    """
    result = []
    valuesList = []
    whereList = []
    sqlStr = "SELECT %s FROM %s " % (columns, tableName)

    try:
        for cond in (condList or []):
            try:
                fieldName = str(cond[0])
                operator = str(cond[1]).upper()
                fieldValue = cond[2]
            except Exception:
                continue
            if operator not in _DEF_QUERY_OPERATOR_LIST:
                continue
            if not _DEF_QUERY_FIELD_PATTERN.match(fieldName):
                continue
            if fieldValue in (None, ""):
                continue
            whereList.append(" %s %s %%s" % (fieldName, operator))
            valuesList.append(fieldValue)

        if keyword and likeOrList:
            orList = []
            for fieldName in likeOrList:
                if not _DEF_QUERY_FIELD_PATTERN.match(str(fieldName)):
                    continue
                orList.append(" %s LIKE %%s" % fieldName)
                valuesList.append("%" + str(keyword) + "%")
            if orList:
                whereList.append(" (" + " OR ".join(orList) + ")")

        if delFlag != "":
            whereList.append(" (delFlag = %s OR delFlag IS NULL)")
            valuesList.append(delFlag)

        beforeID = toIntSafe(beforeID, 0)
        if beforeID > 0:
            whereList.append(" recID < %s")
            valuesList.append(beforeID)

        if whereList:
            sqlStr += " WHERE " + " AND ".join(whereList)

        if order == "modify":
            sqlStr += " ORDER BY modifyYMDHMS DESC"
        elif order == "create":
            sqlStr += " ORDER BY recID ASC"
        else:
            sqlStr += " ORDER BY recID DESC"

        sqlStr += " LIMIT %s"
        valuesList.append(clampLimit(limitNum))

        rtn = mysqlDB.executeRead(sqlStr, tuple(valuesList))
        if rtn > 0:
            result = list(dataFormatConvert(mysqlDB.fetchAll()))

    except DBUnavailableError:
        raise
    except Exception as e:
        errMsg = "%s,%s" % (e, traceback.format_exc().strip(""))
        if _DEBUG:
            _LOG.error(f"{tableName},{errMsg}")

    return result


def getShortColumns(mode, tableName):
    """mode 语义：short -> 少量关键列；其余（含 full）-> 全列"""
    if mode == "short":
        return MJ_QUERY_SHORT_COLUMNS.get(tableName, "*")
    return "*"


#short 模式的关键列清单（只收敛列表接口的返回体积，不改变过滤条件；01 §7.3 禁 SELECT *）
MJ_QUERY_SHORT_COLUMNS = {
    MJ_FAMILY_TABLE: "recID,familyCode,familyName,ownerLoginID,defaultRuleFamilyCode,defaultSkinCode,familyStatus,sortOrder",
    MJ_FAMILY_MEMBER_TABLE: "recID,familyID,loginID,memberRole,memberStatus,joinedYMDHMS",
    MJ_USER_PREF_TABLE: "recID,loginID,lastFamilyID,skinCode,soundEnabledFlag,soundVolume,chatSoundFlag,showTenpaiFlag",
    MJ_RULE_FAMILY_TABLE: "recID,ruleFamilyCode,ruleFamilyName,engineCode,tileSetCode,ruleFamilyStatus,sortOrder",
    MJ_RULE_TEMPLATE_TABLE: "recID,templateCode,familyID,ruleFamilyCode,templateName,presetFlag,activeFlag,sortOrder",
    MJ_ROOM_TABLE: "recID,roomCode,familyID,roomName,hostLoginID,ruleFamilyCode,roomStatus,createdYMDHMS",
    MJ_GAME_TABLE: "recID,familyID,roomID,ruleFamilyCode,gameStatus,startedYMDHMS,endedYMDHMS",
    MJ_GAME_PLAYER_TABLE: "recID,gameID,familyID,seatNo,loginID,displayName,totalScore",
    MJ_GAME_ROUND_TABLE: "recID,gameID,roundNo,dealerSeat,winnerSeat,winType,fanTotal,finishedYMDHMS",
    MJ_ROOM_MESSAGE_TABLE: "recID,roomID,loginID,messageKind,content,createdYMDHMS",
    MJ_TILE_SKIN_TABLE: "recID,skinCode,skinName,familyID,previewFileID,tileAspect,defaultFlag,skinStatus,sortOrder",
    MJ_TILE_SKIN_ASSET_TABLE: "recID,skinID,tileKey,fileID,thumbFileID,width,height",
    MJ_AUDIT_LOG_TABLE: "recID,familyID,operatorLoginID,actionCode,targetType,targetID,createdYMDHMS",
    MJ_SCHEMA_VERSION_TABLE: "recID,versionCode,description,appliedYMDHMS",
}


#common end


#user family begin(USER_BASIC: 用户账号主表, 主键 loginID)

#genOrList: 生成 "( key = %s OR key = %s ... )" 条件串(移植自 museum common/mysqlCommon.py L265-277,
#USER_BASIC 的 queryUserBasic 依赖它; 与 contentHub 内 queryTableGeneral 的 likeOrList 实现互不影响)
def genOrList(IDList, keyName = ""):
    aList = []
    count = 0
    aList.append("( ")
    for ID in IDList:
        if count == 0:
            aList.append(f" {keyName} = %s ")
        else:
            aList.append(f" OR {keyName} = %s ")
        count += 1
    aList.append(") ")
    result = "".join(aList)
    return result


def createUserBasic():
    #列定义与 database/userBasic.txt 逐列一致（44 列，主键 loginID）；手写段不套 recID 规范
    tableName = "USER_BASIC"
    aList  = ["CREATE TABLE IF NOT EXISTS %s("
             "loginID VARCHAR(32) PRIMARY KEY COMMENT '用户登录号',"
             "passwd VARCHAR(80) COMMENT '用户密码 账号服务回包镜像 不参与本地校验',"
             "openID VARCHAR(40) COMMENT '微信openID',"
             "roleName VARCHAR(16) COMMENT '角色名称 账号服务角色',"
             "nickName VARCHAR(40) COMMENT '昵称',"
             "realName VARCHAR(40) COMMENT '用户真实姓名',"
             "gender CHAR(1) COMMENT '性别',"
             "avatarID VARCHAR(200) COMMENT '头像ID',"
             "mobilePhoneNo VARCHAR(32) COMMENT '手机号',"
             "masterID VARCHAR(32) COMMENT '用户主号',"
             "province VARCHAR(32) COMMENT '省',"
             "city VARCHAR(32) COMMENT '市',"
             "area VARCHAR(32) COMMENT '区县',"
             "address VARCHAR(200) COMMENT '地址',"
             "email VARCHAR(100) COMMENT '用户邮箱',"
             "PID VARCHAR(20) COMMENT '用户身份证号',"
             "photoIDFront VARCHAR(128) COMMENT '身份证头像侧',"
             "photoIDBack VARCHAR(128) COMMENT '身份证背面',"
             "photoID VARCHAR(128) COMMENT '用户照片',"
             "delFlag CHAR(1) COMMENT '删除标记',"
             "activeFlag CHAR(1) COMMENT '活动标记',"
             "regPosition VARCHAR(80) COMMENT '注册位置',"
             "regID VARCHAR(32) COMMENT '注册ID',"
             "regYMDHMS VARCHAR(16) COMMENT '注册年月日',"
             "updateYMDHMS VARCHAR(16) COMMENT '数据更新日期',"
             "lastOpenID VARCHAR(40) COMMENT '最后一次登录openID',"
             "lastLoginYMDHMS VARCHAR(16) COMMENT '最后一次登录年月日',"
             "modifyID VARCHAR(32) COMMENT '修改用户ID',"
             "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',"
             "passwdYMDHMS VARCHAR(16) COMMENT '密码修改年月日',"
             "extSessionID VARCHAR(48) COMMENT '扩展用户sessionID',"
             "extStartYMDHMS VARCHAR(16) COMMENT '扩展开始年月日',"
             "extLeaveYMDHMS VARCHAR(16) COMMENT '扩展停止年月日',"
             "extJobPosition VARCHAR(100) COMMENT '扩展职位',"
             "extDepartment VARCHAR(100) COMMENT '扩展部门',"
             "extOrgName VARCHAR(300) COMMENT '扩展组织名称',"
             "extOrgID INT COMMENT '扩展组织ID',"
             "extInService VARCHAR(1) COMMENT '扩展是否在职',"
             "extJobLabel VARCHAR(16) COMMENT '扩展职位身份标签',"
             "extJobDetail VARCHAR(64) COMMENT '扩展职位细节',"
             "extBrief VARCHAR(1000) COMMENT '扩展人员简介',"
             "extManualTagList VARCHAR(500) COMMENT '扩展标签列表',"
             "extManagementAreaList VARCHAR(500) COMMENT '扩展管理区域',"
             "extMemo VARCHAR(100) COMMENT '扩展备注'"
             ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;",
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    return result


def dropUserBasic():
    tableName = "USER_BASIC"
    result = dropTableGeneral(tableName)
    return result


#以后这个是标准写法,利用fetchMany来处理数据
#SELECT * FROM USER_BASIC WHERE loginID = "13910710766";
def queryUserBasic(loginID = "" , name = "", mobile = "", manualTag = "",jobLabel="",
                   searchOption = {},  roleName = "", roleNameList = [],  keyword="",
                   mode = "normal", beginYMD = "",endYMD = "", 
                   order="create", limitNum = _DEF_QUERY_LIMIT_MAX):
    result = []
    tableName = "USER_BASIC"

    if mode =="short":
        columns = "loginID,nickName,realName,roleName, gender,avatarID"
    elif mode =="normal":
        columns = "loginID,nickName,realName,roleName,gender,avatarID,openID,masterID,mobilePhoneNo,province,city,area, address, email, regYMDHMS, updateYMDHMS"
    else:
        columns = "*"
    valuesList = [] 
    sqlStr =   "SELECT %s FROM %s " % (columns, tableName )

    try:
        if loginID:
            sqlStr += " WHERE loginID = %s"
            valuesList = [loginID]
        else:
            valuesList = []
            #以下 searchOption,roleName,roleNameList是并列关系,只能选一个
            if searchOption:
                if valuesList:
                    whereStr = " AND "
                else:
                    whereStr = " WHERE "
                logic = searchOption.get("logic", "AND")
                optionList = searchOption.get("optionList", [])
                count = 0
                for optionSet in optionList:
                    if count > 0:
                        whereStr += " " + logic + " "
                    if "realName" in optionSet:
                        whereStr += " realName = %s" 
                        valuesList.append(optionSet["realName"])
                    if "nickName" in optionSet:
                        whereStr += " nickName = %s" 
                        valuesList.append(optionSet["nickName"])
                    if "loginID" in optionSet:
                        whereStr += " loginID = %s" 
                        valuesList.append(optionSet["loginID"])
                    if "roleName" in optionSet:
                        whereStr += " roleName = %s" 
                        valuesList.append(optionSet["roleName"])
                    if "province" in optionSet:
                        whereStr += " province = %s" 
                        valuesList.append(optionSet["province"])
                    count += 1
                sqlStr += whereStr 
                
            elif jobLabel:
                if valuesList:
                    whereStr = " AND extJobLabel = %s "
                else:
                    whereStr = " WHERE extJobLabel = %s "
                valuesList.append(jobLabel)
                sqlStr += whereStr 

            elif roleName:
                if valuesList:
                    whereStr = " AND roleName = %s "
                else:
                    whereStr = " WHERE roleName = %s "
                valuesList.append(roleName)
                sqlStr += whereStr 

            elif roleNameList:
                if valuesList:
                    whereStr = " AND " + genOrList(roleNameList, "roleName")
                else:
                    whereStr = " WHERE " + genOrList(roleNameList, "roleName")
                valuesList += roleNameList
                sqlStr += whereStr 
            
            if keyword:
                if valuesList:
                    sqlStr =  sqlStr + " AND (locate(%s,realName) OR locate(%s,nickName) OR locate(%s,extJobPosition) OR locate(%s,extJobDetail) OR locate(%s,extOrgName) OR locate(%s,loginID) )" 
                else:
                    sqlStr =  sqlStr + " WHERE (locate(%s,realName) OR locate(%s,nickName) OR locate(%s,extJobPosition) OR locate(%s,extJobDetail) OR locate(%s,extOrgName) OR locate(%s,loginID) )" 
                valuesList.append(keyword)
                valuesList.append(keyword)
                valuesList.append(keyword)
                valuesList.append(keyword)
                valuesList.append(keyword)
                valuesList.append(keyword)

            # beginYMD 和 endYMD可以和上面混用
            if beginYMD  and endYMD :
                beginYMDHMS = beginYMD + "000000"
                endYMDHMS = endYMD + "240000"
                if valuesList:
                    whereStr = " AND regYMDHMS >= %s and regYMDHMS <= %s "
                else:
                    whereStr = " WHERE regYMDHMS >= %s and regYMDHMS <= %s "
                sqlStr = sqlStr + " WHERE regYMDHMS >= %s and regYMDHMS <= %s " 
                valuesList += [beginYMDHMS, endYMDHMS] 
                                
        if order == "create":
            sqlStr += " ORDER BY regYMDHMS DESC"
        
        #其他过滤数据的在这里
        if name or mobile or manualTag:
            #分批次获取数据并挑选数据
            rtn = mysqlDB.executeRead(sqlStr, tuple(valuesList))
            if rtn:
                batchNum = 1000
                total = 0
                while True:
                    dataList = mysqlDB.fetchMany(batchNum)
                    dataList = dataFormatConvert(dataList)
                
                    for data in dataList:
                        matchFlag = False

                        if mobile:
                            keyword = mobile
                            keyList = ["mobilePhoneNo","loginID"]
                            for key in keyList:
                                currVal = data.get(key)
                                if currVal:
                                    if currVal.find(keyword) >= 0:
                                        matchFlag = True
                                        break
                        if name:
                            keyword = name
                            keyList = ["roleName","nickName","realName"]
                            for key in keyList:
                                currVal = data.get(key)
                                if currVal:
                                    if currVal.find(keyword) >= 0:
                                        matchFlag = True
                                        break

                        if matchFlag:
                            result.append(data)

                    #final
                    #如果取不到更多数据就退出
                    currDataLen = len(dataList)
                    if currDataLen < batchNum:
                        break
                    
                    #如果取到的数据满足要求也退出,limitNUm = 0 是提取全部满足条件数据
                    if limitNum > 0:
                        total = len(result)
                        if total >= limitNum:
                            result = result[0:limitNum]
                            break
        else:
            if limitNum > 0:
                sqlStr += " LIMIT {0}".format(limitNum)

            rtn = mysqlDB.executeRead(sqlStr, tuple(valuesList))
            if rtn > 0:
                dataList = mysqlDB.fetchAll()
                dataList = dataFormatConvert(dataList)

                result = dataList

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
#        if _DEBUG:
#            _LOG.error(f"{errMsg}")

    return result

    
#SELECT * FROM USER_BASIC WHERE loginID = "13910710766";
def deleteUserBasic(loginID):
    result = 0
    tableName = "USER_BASIC"
    try:
    
        sqlStr = "DELETE FROM %s WHERE loginID = %%s;" % (tableName)
        rtn = mysqlDB.executeWrite(sqlStr, (loginID,))
        result = rtn

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
#        if _DEBUG:
#            _LOG.error(f"{errMsg}")

    return result
    
    
def insertUserBasic(loginID, dataSet):
    result = 0
    tableName = "USER_BASIC"
    try:
        saveSet = {}
        saveSet["loginID"]  = loginID

        saveSet["passwd"] = dataSet.get("passwd", "") 

        saveSet["openID"] = dataSet.get("openID", "") 

        saveSet["roleName"] = dataSet.get("roleName", "") 

        saveSet["nickName"] = dataSet.get("nickName", "") 

        saveSet["realName"] = dataSet.get("realName", "") 

        saveSet["gender"] = dataSet.get("gender", "") 

        saveSet["avatarID"] = dataSet.get("avatarID", "") 

        saveSet["mobilePhoneNo"] = dataSet.get("mobilePhoneNo", "") 

        saveSet["masterID"] = dataSet.get("masterID", "") 

        saveSet["province"] = dataSet.get("province", "") 

        saveSet["city"] = dataSet.get("city", "") 

        saveSet["area"] = dataSet.get("area", "") 

        saveSet["address"] = dataSet.get("address", "") 

        saveSet["email"] = dataSet.get("email", "") 

        saveSet["PID"] = dataSet.get("PID", "") 

        saveSet["photoIDFront"] = dataSet.get("photoIDFront", "") 

        saveSet["photoIDBack"] = dataSet.get("photoIDBack", "") 

        saveSet["photoID"] = dataSet.get("photoID", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        saveSet["activeFlag"] = dataSet.get("activeFlag", _CONST_YES) 

        regPosition = dataSet.get("regPosition", {})
        if (regPosition != {}):
            #双引号的特殊处理
            saveSet["regPosition"]  = misc.jsonDumps(regPosition).replace("\"", "'")
        else:
            saveSet["regPosition"] = misc.jsonDumps({})

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["updateYMDHMS"] = dataSet.get("updateYMDHMS", "") 

        saveSet["lastOpenID"] = dataSet.get("lastOpenID", "") 

        saveSet["lastLoginYMDHMS"] = dataSet.get("lastLoginYMDHMS", "") 

        saveSet["passwdYMDHMS"] = dataSet.get("passwdYMDHMS", "") 

        # extend items begin, per project
        saveSet["extSessionID"] = dataSet.get("extSessionID", "") 

        saveSet["extStartYMDHMS"] = dataSet.get("extStartYMDHMS", "") 

        saveSet["extStartYMDHMS"] = dataSet.get("extStartYMDHMS", "") 

        saveSet["extLeaveYMDHMS"] = dataSet.get("extLeaveYMDHMS", "") 

        saveSet["extJobPosition"] = dataSet.get("extJobPosition", "") 

        saveSet["extDepartment"] = dataSet.get("extDepartment", "") 

        saveSet["extOrgName"] = dataSet.get("extOrgName", "") 

        try:
            extOrgID = int(dataSet.get("extOrgID")) 
        except:
            extOrgID = 0 
        saveSet["extOrgID"] = extOrgID

        saveSet["extInService"] = dataSet.get("extInService", "") 

        saveSet["extJobLabel"] = dataSet.get("extJobLabel", "") 

        saveSet["extJobDetail"] = dataSet.get("extJobDetail", "") 

        saveSet["extBrief"] = dataSet.get("extBrief", "") 

        saveSet["extManualTagList"] = dataSet.get("extManualTagList", "") 

        saveSet["extManagementAreaList"] = dataSet.get("extManagementAreaList", "") 

        saveSet["extMemo"] = dataSet.get("extMemo", "") 
        # extend items end, per project

        result = insertTableGeneral(tableName, saveSet, selfDefinedPrimaryKey = _CONST_YES)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
#        if _DEBUG:
#            _LOG.error(f"{errMsg}")

    return result
    
    
def updateUserBasic(loginID, dataSet):
    result = 0
    tableName = "USER_BASIC"
    try:
        saveSet = {}
        
        passwd = dataSet.get("passwd")
        if passwd != "" and passwd:
            saveSet["passwd"] = passwd
            
        openID = dataSet.get("openID", "")
        if openID != "":
            saveSet["openID"] = openID

        roleName = dataSet.get("roleName", "")
        if roleName != "":
            saveSet["roleName"] = roleName

        nickName = dataSet.get("nickName", "")
        if nickName != "":
            saveSet["nickName"] = nickName

        realName = dataSet.get("realName", "")
        if realName != "":
            saveSet["realName"] = realName

        gender = dataSet.get("gender", "")
        if gender != "":
            saveSet["gender"] = gender

        avatarID = dataSet.get("avatarID", "")
        if avatarID != "":
            saveSet["avatarID"] = avatarID

        mobilePhoneNo = dataSet.get("mobilePhoneNo", "")
        if mobilePhoneNo != "":
            saveSet["mobilePhoneNo"] = mobilePhoneNo

        province = dataSet.get("province", "")
        if province != "":
            saveSet["province"] = province
            
        masterID = dataSet.get("masterID", "")
        if masterID != "":
            saveSet["masterID"] = masterID
            
        city = dataSet.get("city", "")
        if city != "":
            saveSet["city"] = city
            
        area = dataSet.get("area", "")
        if area != "":
            saveSet["area"] = area
            
        address = dataSet.get("address", "")
        if address != "":
            saveSet["address"] = address
            
        email = dataSet.get("email", "")
        if email != "":
            saveSet["email"] = email
            
        PID = dataSet.get("PID", "")
        if PID != "":
            saveSet["PID"] = PID
            
        photoIDFront = dataSet.get("photoIDFront", "")
        if photoIDFront != "":
            saveSet["photoIDFront"] = photoIDFront
            
        photoIDBack = dataSet.get("photoIDBack", "")
        if photoIDBack != "":
            saveSet["photoIDBack"] = photoIDBack
            
        photoIDBack = dataSet.get("photoIDBack", "")
        if photoIDBack != "":
            saveSet["photoIDBack"] = photoIDBack
            
        photoID = dataSet.get("photoID", "")
        if photoID != "":
            saveSet["photoID"] = photoID

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            if delFlag != "1":
                delFlag = "0"
            saveSet["delFlag"] = delFlag

        activeFlag = dataSet.get("activeFlag")
        if activeFlag:
            saveSet["activeFlag"] = activeFlag

        regPosition = dataSet.get("regPosition", {})
        if (regPosition != {}):
            #双引号的特殊处理
            saveSet["regPosition"] = misc.jsonDumps(regPosition).replace("\"", "'")

        updateYMDHMS = dataSet.get("updateYMDHMS", "")
        if updateYMDHMS != "":
            saveSet["updateYMDHMS"] = updateYMDHMS
        lastOpenID = dataSet.get("lastOpenID", "")

        if lastOpenID != "":
            saveSet["lastOpenID"] = lastOpenID

        lastLoginYMDHMS = dataSet.get("lastLoginYMDHMS", "")
        if lastLoginYMDHMS != "":
            saveSet["lastLoginYMDHMS"] = lastLoginYMDHMS

        modifyID = dataSet.get("modifyID")
        if modifyID != "":
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS", "")
        if modifyYMDHMS != "":
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        passwdYMDHMS = dataSet.get("passwdYMDHMS", "")
        if passwdYMDHMS != "":
            saveSet["passwdYMDHMS"] = passwdYMDHMS
    
        # extend items begin, per project

        extSessionID = dataSet.get("extSessionID", "")
        if extSessionID != "":
            saveSet["extSessionID"] = extSessionID

        extStartYMDHMS = dataSet.get("extStartYMDHMS") 
        if extStartYMDHMS:
            saveSet["extStartYMDHMS"] = extStartYMDHMS

        extLeaveYMDHMS = dataSet.get("extLeaveYMDHMS") 
        if extLeaveYMDHMS:
            saveSet["extLeaveYMDHMS"] = extLeaveYMDHMS

        extJobPosition = dataSet.get("extJobPosition") 
        if extJobPosition:
            saveSet["extJobPosition"] = extJobPosition

        extDepartment = dataSet.get("extDepartment") 
        if extDepartment:
            saveSet["extDepartment"] = extDepartment

        extOrgName = dataSet.get("extOrgName") 
        if extOrgName:
            saveSet["extOrgName"] = extOrgName

        extOrgID = dataSet.get("extOrgID") 
        if extOrgID:
            try:
                extOrgID = int(dataSet.get("extOrgID")) 
                saveSet["extOrgID"] = extOrgID
            except:
                pass

        extInService = dataSet.get("extInService") 
        if extInService:
            saveSet["extInService"] = extInService

        extJobLabel = dataSet.get("extJobLabel") 
        if extJobLabel:
            saveSet["extJobLabel"] = extJobLabel

        extJobDetail = dataSet.get("extJobDetail") 
        if extJobDetail:
            saveSet["extJobDetail"] = extJobDetail

        extBrief = dataSet.get("extBrief") 
        if extBrief:
            saveSet["extBrief"] = extBrief

        extManualTagList = dataSet.get("extManualTagList") 
        if extManualTagList:
            saveSet["extManualTagList"] = extManualTagList

        extManagementAreaList = dataSet.get("extManagementAreaList") 
        if extManagementAreaList:
            saveSet["extManagementAreaList"] = extManagementAreaList

        extMemo = dataSet.get("extMemo") 
        if extMemo:
            saveSet["extMemo"] = extMemo

        # extend items end, per project

        keySqlstr = "loginID = %s" 
        keyValues = [loginID]
        
        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)
        
    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
#        if _DEBUG:
#            _LOG.error(f"{errMsg}")

    return result


#获取本地用户信息mysql
def getUserInfoMysql(loginID):
    result = {}
    try:
        mode = "full"
        currDataList = queryUserBasic(loginID,mode = mode)

        if currDataList:
            currDataSet = currDataList[0]

            aSet = {}

            aSet["loginID"] = currDataSet.get("loginID","")
            # aSet["openID"] = currDataSet.get("openID","")
            aSet["roleName"] = currDataSet.get("roleName","")
            aSet["nickName"] = currDataSet.get("nickName","")
            aSet["realName"] = currDataSet.get("realName","")
            aSet["gender"] = currDataSet.get("gender","")

            aSet["avatarID"] = currDataSet.get("avatarID","")

            aSet["mobilePhoneNo"] = currDataSet.get("mobilePhoneNo","")
            aSet["masterID"] = currDataSet.get("masterID","")
            aSet["province"] = currDataSet.get("province","")
            aSet["city"] = currDataSet.get("city","")
            aSet["area"] = currDataSet.get("area","")
            aSet["address"] = currDataSet.get("address","")
            aSet["email"] = currDataSet.get("email","")
            aSet["PID"] = currDataSet.get("PID","")
            aSet["activeFlag"] = currDataSet.get("activeFlag","")

            # photoIDFront = currDataSet.get("photoIDFront","")
            # if photoIDFront:
            #     photoIDFront = getTempLocation(photoIDFront, privateFlag = True)
            # aSet["photoIDFront"] = photoIDFront

            # photoIDBack = currDataSet.get("photoIDBack","")
            # if photoIDBack:
            #     photoIDBack = getTempLocation(photoIDBack, privateFlag = True)
            # aSet["photoIDBack"] = photoIDBack

            # photoID = currDataSet.get("photoID","")
            # if photoID:
            #     photoID = getTempLocation(photoID, privateFlag = True)
            # aSet["photoID"] = photoID

            # aSet["delFlag"] = currDataSet.get("delFlag","")
            aSet["regPosition"] = currDataSet.get("regPosition","")
            aSet["regID"] = currDataSet.get("regID","")
            aSet["regYMDHMS"] = currDataSet.get("regYMDHMS","")
            aSet["updateYMDHMS"] = currDataSet.get("updateYMDHMS","")
            # aSet["lastOpenID"] = currDataSet.get("lastOpenID","")
            aSet["lastLoginYMDHMS"] = currDataSet.get("lastLoginYMDHMS","")
            aSet["modifyID"] = currDataSet.get("modifyID","")
            aSet["modifyYMDHMS"] = currDataSet.get("modifyYMDHMS","")
            # aSet["passwdYMDHMS"] = currDataSet.get("passwdYMDHMS","")

            # extend items begin, per project
            aSet["extSessionID"] = currDataSet.get("extSessionID","")
            aSet["extStartYMDHMS"] = currDataSet.get("extStartYMDHMS","")
            aSet["extLeaveYMDHMS"] = currDataSet.get("extLeaveYMDHMS","")
            aSet["extJobPosition"] = currDataSet.get("extJobPosition","")
            aSet["extDepartment"] = currDataSet.get("extDepartment","")
            aSet["extOrgName"] = currDataSet.get("extOrgName","")
            aSet["extOrgID"] = currDataSet.get("extOrgID","")

            aSet["extInService"] = currDataSet.get("extInService","")
            # aSet["extInService"] = chkIsInService(aSet["extInService"],aSet["activeFlag"])

            aSet["extJobLabel"] = currDataSet.get("extJobLabel","")
            aSet["extJobDetail"] = currDataSet.get("extJobDetail","")
            aSet["extBrief"] = currDataSet.get("extBrief","")

            #list/dict处理
            extManualTagList = currDataSet.get("extManualTagList")
            try:
                extManualTagList = misc.jsonLoads(extManualTagList)
            except:
                extManualTagList = []
            aSet["extManualTagList"] = extManualTagList

            #list/dict处理
            extManagementAreaList = currDataSet.get("extManagementAreaList")
            try:
                extManagementAreaList = misc.jsonLoads(extManagementAreaList)
            except:
                extManagementAreaList = []
            aSet["extManagementAreaList"] = extManagementAreaList
            aSet["extMemo"] = currDataSet.get("extMemo","")
            # extend items end, per project

            result = aSet
    except:
        pass
    return result


#champion only 
def statUserBasic(statBy = "roleName", beginYMD = "",endYMD = ""):
    result = []
    tableName = "USER_BASIC"

    valuesList = []

    try:
        if statBy == "roleName":
            sqlStr = f"SELECT count(loginID) as total, roleName FROM {tableName} "

            if beginYMD:
                beginYMDHMS = beginYMD + "000000"
                if valuesList:
                    sqlStr += " AND regYMDHMS >= %s " 
                else:
                    sqlStr += " WHERE regYMDHMS >= %s " 
                valuesList.append(beginYMDHMS)

            if endYMD:
                endYMDHMS = endYMD + "240000"
                if valuesList:
                    sqlStr += " AND regYMDHMS <= %s " 
                else:
                    sqlStr += " WHERE regYMDHMS <= %s " 
                valuesList.append(endYMDHMS)
            
            sqlStr += " GROUP BY roleName"
        else:
            sqlStr = f"SELECT count(loginID) as total FROM {tableName}"

            if beginYMD:
                beginYMDHMS = beginYMD + "000000"
                if valuesList:
                    sqlStr += " AND regYMDHMS >= %s " 
                else:
                    sqlStr += " WHERE regYMDHMS >= %s " 
                valuesList.append(beginYMDHMS)

            if endYMD:
                endYMDHMS = endYMD + "240000"
                if valuesList:
                    sqlStr += " AND regYMDHMS <= %s " 
                else:
                    sqlStr += " WHERE regYMDHMS <= %s " 
                valuesList.append(endYMDHMS)
            
        rtn = mysqlDB.executeRead(sqlStr, tuple(valuesList))
        if rtn > 0:
            dataList = mysqlDB.fetchAll()
            dataList = dataFormatConvert(dataList)
            result = dataList

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
#        if _DEBUG:
#            _LOG.error(f"{errMsg}")

    return result


#user family end


#mj query begin（02 §8 手写区：业务层只调这里的函数，不写裸 SQL）

def query_mj_user_pref_by_login(loginID):
    """按 loginID 取偏好（单条，无记录返回 {}）"""
    result = {}
    dataList = queryTableGeneral(
        MJ_USER_PREF_TABLE,
        condList=[["loginID", "=", loginID]],
        order="create",
        limitNum=1,
    )
    if dataList:
        result = dataList[0]
    return result


def query_mj_room_by_code(roomCode):
    """按 6 位邀请码取房（单条，无记录返回 {}）；只认未删除行"""
    result = {}
    dataList = queryTableGeneral(
        MJ_ROOM_TABLE,
        condList=[["roomCode", "=", roomCode]],
        order="create",
        limitNum=1,
    )
    if dataList:
        result = dataList[0]
    return result


def query_mj_family_list_by_login(loginID):
    """我的家庭列表：join 成员表，只取 ACTIVE 成员关系"""
    result = []
    sqlStr = (
        "SELECT f.*, m.memberRole, m.memberStatus, m.joinedYMDHMS "
        "FROM %s m INNER JOIN %s f ON f.recID = m.familyID "
        "WHERE m.loginID = %%s AND m.memberStatus = 'ACTIVE' "
        "AND (m.delFlag = '0' OR m.delFlag IS NULL) "
        "AND (f.delFlag = '0' OR f.delFlag IS NULL) "
        "ORDER BY f.sortOrder ASC, f.recID ASC LIMIT %%s"
    ) % (MJ_FAMILY_MEMBER_TABLE, MJ_FAMILY_TABLE)
    try:
        rtn = mysqlDB.executeRead(sqlStr, (loginID, clampLimit(_DEF_QUERY_LIMIT_MAX, _DEF_QUERY_LIMIT_MAX)))
        if rtn > 0:
            result = list(dataFormatConvert(mysqlDB.fetchAll()))
    except DBUnavailableError:
        raise
    except Exception as e:
        if _DEBUG:
            _LOG.error("query_mj_family_list_by_login:%s", e)
    return result


def query_mj_room_list(familyID, limit = _DEF_QUERY_LIMIT_NUM, beforeID = 0):
    """家庭房间列表：只列 OPEN，按 recID 倒序分页"""
    return queryTableGeneral(
        MJ_ROOM_TABLE,
        condList=[
            ["familyID", "=", toIntSafe(familyID)],
            ["roomStatus", "=", "OPEN"],
        ],
        columns=getShortColumns("short", MJ_ROOM_TABLE),
        order="new",
        limitNum=clampLimit(limit),
        beforeID=beforeID,
    )


def query_mj_rule_template_list(familyID, ruleFamilyCode = ""):
    """模板列表：家庭自有 + 全局预置（familyID IN (0, ?)），只列启用项"""
    result = []
    sqlStr = (
        "SELECT recID, templateCode, familyID, ruleFamilyCode, templateName, description, "
        "configJson, presetFlag, ownerLoginID, activeFlag, sortOrder "
        "FROM %s WHERE familyID IN (0, %%s) AND activeFlag = '1' "
        "AND (delFlag = '0' OR delFlag IS NULL)"
    ) % MJ_RULE_TEMPLATE_TABLE
    valuesList = [toIntSafe(familyID)]
    if ruleFamilyCode:
        sqlStr += " AND ruleFamilyCode = %s"
        valuesList.append(ruleFamilyCode)
    sqlStr += " ORDER BY familyID ASC, sortOrder ASC, recID ASC LIMIT %s"
    valuesList.append(clampLimit(_DEF_QUERY_LIMIT_MAX, _DEF_QUERY_LIMIT_MAX))
    try:
        rtn = mysqlDB.executeRead(sqlStr, tuple(valuesList))
        if rtn > 0:
            result = list(dataFormatConvert(mysqlDB.fetchAll()))
    except DBUnavailableError:
        raise
    except Exception as e:
        if _DEBUG:
            _LOG.error("query_mj_rule_template_list:%s", e)
    return result


def query_mj_tile_skin_list(familyID):
    """皮肤清单：内置（0）+ 家庭自有，只列 ENABLED，按 sortOrder 升序"""
    result = []
    sqlStr = (
        "SELECT recID, skinCode, skinName, familyID, previewFileID, tileAspect, "
        "defaultFlag, skinStatus, sortOrder, ownerLoginID "
        "FROM %s WHERE familyID IN (0, %%s) AND skinStatus = 'ENABLED' "
        "AND (delFlag = '0' OR delFlag IS NULL) "
        "ORDER BY defaultFlag DESC, sortOrder ASC, recID ASC LIMIT %%s"
    ) % MJ_TILE_SKIN_TABLE
    try:
        rtn = mysqlDB.executeRead(
            sqlStr, (toIntSafe(familyID), clampLimit(_DEF_QUERY_LIMIT_MAX, _DEF_QUERY_LIMIT_MAX))
        )
        if rtn > 0:
            result = list(dataFormatConvert(mysqlDB.fetchAll()))
    except DBUnavailableError:
        raise
    except Exception as e:
        if _DEBUG:
            _LOG.error("query_mj_tile_skin_list:%s", e)
    return result


def query_mj_tile_skin_asset_list(skinID):
    """某皮肤的逐张资源，按 tileKey 排序（前端按 tileKey 建索引）"""
    return queryTableGeneral(
        MJ_TILE_SKIN_ASSET_TABLE,
        condList=[["skinID", "=", toIntSafe(skinID)]],
        order="create",
        limitNum=clampLimit(200, 200),
    )


def query_mj_room_message_list(roomID, limit = _DEF_CHAT_QUERY_LIMIT_NUM):
    """最近聊天：recID 倒序取 N 条（调用方需要按时间正序时自行 reverse）"""
    result = []
    sqlStr = (
        "SELECT recID, roomID, familyID, loginID, messageKind, content, createdYMDHMS "
        "FROM %s WHERE roomID = %%s AND (delFlag = '0' OR delFlag IS NULL) "
        "ORDER BY recID DESC LIMIT %%s"
    ) % MJ_ROOM_MESSAGE_TABLE
    try:
        rtn = mysqlDB.executeRead(
            sqlStr, (toIntSafe(roomID), clampLimit(limit, _DEF_CHAT_QUERY_LIMIT_NUM))
        )
        if rtn > 0:
            result = list(dataFormatConvert(mysqlDB.fetchAll()))
    except DBUnavailableError:
        raise
    except Exception as e:
        if _DEBUG:
            _LOG.error("query_mj_room_message_list:%s", e)
    return result


def query_mj_game_list(familyID, loginID = "", limit = _DEF_GAME_QUERY_LIMIT_NUM, beforeID = 0):
    """场次列表：按家庭；传 loginID 时只列其参与过的场次（参与者子查询）"""
    result = []
    sqlStr = (
        "SELECT g.recID, g.familyID, g.roomID, g.ruleFamilyCode, g.gameStatus, "
        "g.startedYMDHMS, g.endedYMDHMS FROM %s g "
        "WHERE g.familyID = %%s AND (g.delFlag = '0' OR g.delFlag IS NULL)"
    ) % MJ_GAME_TABLE
    valuesList = [toIntSafe(familyID)]
    if beforeID:
        sqlStr += " AND g.recID < %s"
        valuesList.append(toIntSafe(beforeID))
    if loginID:
        sqlStr += (
            " AND EXISTS (SELECT 1 FROM %s p WHERE p.gameID = g.recID AND p.loginID = %%s "
            "AND (p.delFlag = '0' OR p.delFlag IS NULL))"
        ) % MJ_GAME_PLAYER_TABLE
        valuesList.append(loginID)
    sqlStr += " ORDER BY g.recID DESC LIMIT %s"
    valuesList.append(clampLimit(limit, _DEF_GAME_QUERY_LIMIT_NUM))
    try:
        rtn = mysqlDB.executeRead(sqlStr, tuple(valuesList))
        if rtn > 0:
            result = list(dataFormatConvert(mysqlDB.fetchAll()))
    except DBUnavailableError:
        raise
    except Exception as e:
        if _DEBUG:
            _LOG.error("query_mj_game_list:%s", e)
    return result


def query_mj_game_detail(gameID):
    """场次详情：game + players + rounds（无记录时 game 为 {}）"""
    result = {"game": {}, "players": [], "rounds": []}
    gameID = toIntSafe(gameID)
    if gameID <= 0:
        return result
    gameList = queryTableGeneral(
        MJ_GAME_TABLE, condList=[["recID", "=", gameID]], order="create", limitNum=1
    )
    if gameList:
        result["game"] = gameList[0]
    result["players"] = queryTableGeneral(
        MJ_GAME_PLAYER_TABLE,
        condList=[["gameID", "=", gameID]],
        order="create",
        limitNum=8,
    )
    result["rounds"] = queryTableGeneral(
        MJ_GAME_ROUND_TABLE,
        condList=[["gameID", "=", gameID]],
        order="create",
        limitNum=clampLimit(200, 200),
    )
    return result


def update_mj_game_player_score(gameID, seatNo, delta):
    """更新某座位累计分：totalScore = totalScore + delta（返回受影响行数，失败 -1）"""
    result = 0
    sqlStr = (
        "UPDATE %s SET totalScore = totalScore + %%s, modifyYMDHMS = %%s "
        "WHERE gameID = %%s AND seatNo = %%s AND (delFlag = '0' OR delFlag IS NULL)"
    ) % MJ_GAME_PLAYER_TABLE
    try:
        result = mysqlDB.executeWrite(
            sqlStr, (toIntSafe(delta), misc.getTime(), toIntSafe(gameID), toIntSafe(seatNo))
        )
    except DBUnavailableError:
        raise
    except Exception as e:
        if _DEBUG:
            _LOG.error("update_mj_game_player_score:%s", e)
        result = -1
    return result


def delete_mj_soft(tableName, recID, modifyID = ""):
    """软删：SET delFlag='1'（不物理删除）；表名只接受 TABLE_NAME_SET 内的常量。

    生成版 delete_mj_*(tableName, recID) 是物理删除，业务层不得直接调用。
    """
    result = 0
    if tableName not in TABLE_NAME_SET:
        if _DEBUG:
            _LOG.error("delete_mj_soft: 非法表名 %s", tableName)
        return -1
    sqlStr = "UPDATE %s SET delFlag = '1', modifyID = %%s, modifyYMDHMS = %%s WHERE recID = %%s" % tableName
    try:
        result = mysqlDB.executeWrite(sqlStr, (modifyID, misc.getTime(), toIntSafe(recID)))
    except DBUnavailableError:
        raise
    except Exception as e:
        if _DEBUG:
            _LOG.error("delete_mj_soft:%s", e)
        result = -1
    return result


#mj query end


#===== auto-generated sections begin (由 tools/mergeMysqlCommon.py 生成, 请勿手改) =====

#mj_family begin 

def tablename_convertor_mj_family():
    tableName = "mj_family"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_family(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_family表
def create_mj_family(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "familyCode VARCHAR(32) NOT NULL UNIQUE COMMENT '家庭编码 幂等键',",
    "familyName VARCHAR(64) NOT NULL COMMENT '家庭名称',",
    "ownerLoginID VARCHAR(32) NOT NULL COMMENT '家庭管理员登录号',",
    "defaultRuleFamilyCode VARCHAR(32) NULL COMMENT '默认规则族编码',",
    "defaultSkinCode VARCHAR(32) NULL COMMENT '默认皮肤编码',",
    "familyStatus VARCHAR(24) NOT NULL DEFAULT 'ENABLED' COMMENT 'ENABLED或DISABLED',",
    "sortOrder INT NOT NULL DEFAULT 0 COMMENT '排序号',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_family表
def drop_mj_family(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_family 删除记录
def delete_mj_family(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_family 增加记录
def insert_mj_family(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["familyCode"] = dataSet.get("familyCode", "") 

        saveSet["familyName"] = dataSet.get("familyName", "") 

        saveSet["ownerLoginID"] = dataSet.get("ownerLoginID", "") 

        saveSet["defaultRuleFamilyCode"] = dataSet.get("defaultRuleFamilyCode", "") 

        saveSet["defaultSkinCode"] = dataSet.get("defaultSkinCode", "") 

        saveSet["familyStatus"] = dataSet.get("familyStatus", "") 

        try:
            sortOrder = int(dataSet.get("sortOrder")) 
        except:
            sortOrder = 0 
        saveSet["sortOrder"] = sortOrder

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_family 修改记录
def update_mj_family(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        familyCode = dataSet.get("familyCode") 
        if familyCode:
            saveSet["familyCode"] = familyCode

        familyName = dataSet.get("familyName") 
        if familyName:
            saveSet["familyName"] = familyName

        ownerLoginID = dataSet.get("ownerLoginID") 
        if ownerLoginID:
            saveSet["ownerLoginID"] = ownerLoginID

        defaultRuleFamilyCode = dataSet.get("defaultRuleFamilyCode") 
        if defaultRuleFamilyCode:
            saveSet["defaultRuleFamilyCode"] = defaultRuleFamilyCode

        defaultSkinCode = dataSet.get("defaultSkinCode") 
        if defaultSkinCode:
            saveSet["defaultSkinCode"] = defaultSkinCode

        familyStatus = dataSet.get("familyStatus") 
        if familyStatus:
            saveSet["familyStatus"] = familyStatus

        try:
            sortOrder = int(dataSet.get("sortOrder")) 
            saveSet["sortOrder"] = sortOrder
        except:
            pass

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_family end


#mj_family_member begin 

def tablename_convertor_mj_family_member():
    tableName = "mj_family_member"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_family_member(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_family_member表
def create_mj_family_member(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "familyMemberKey VARCHAR(80) NOT NULL UNIQUE COMMENT '成员幂等键 familyID_loginID',",
    "familyID INT NOT NULL COMMENT '家庭ID',",
    "loginID VARCHAR(32) NOT NULL COMMENT '成员登录号',",
    "memberRole VARCHAR(16) NOT NULL DEFAULT 'MEMBER' COMMENT 'OWNER或ADMIN或MEMBER',",
    "memberStatus VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' COMMENT 'ACTIVE或DISABLED或LEFT',",
    "joinedYMDHMS VARCHAR(16) NULL COMMENT '加入时间',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_family_member表
def drop_mj_family_member(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_family_member 删除记录
def delete_mj_family_member(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_family_member 增加记录
def insert_mj_family_member(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["familyMemberKey"] = dataSet.get("familyMemberKey", "") 

        try:
            familyID = int(dataSet.get("familyID")) 
        except:
            familyID = 0 
        saveSet["familyID"] = familyID

        saveSet["loginID"] = dataSet.get("loginID", "") 

        saveSet["memberRole"] = dataSet.get("memberRole", "") 

        saveSet["memberStatus"] = dataSet.get("memberStatus", "") 

        saveSet["joinedYMDHMS"] = dataSet.get("joinedYMDHMS", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_family_member 修改记录
def update_mj_family_member(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        familyMemberKey = dataSet.get("familyMemberKey") 
        if familyMemberKey:
            saveSet["familyMemberKey"] = familyMemberKey

        try:
            familyID = int(dataSet.get("familyID")) 
            saveSet["familyID"] = familyID
        except:
            pass

        loginID = dataSet.get("loginID") 
        if loginID:
            saveSet["loginID"] = loginID

        memberRole = dataSet.get("memberRole") 
        if memberRole:
            saveSet["memberRole"] = memberRole

        memberStatus = dataSet.get("memberStatus") 
        if memberStatus:
            saveSet["memberStatus"] = memberStatus

        joinedYMDHMS = dataSet.get("joinedYMDHMS") 
        if joinedYMDHMS:
            saveSet["joinedYMDHMS"] = joinedYMDHMS

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_family_member end


#mj_user_pref begin 

def tablename_convertor_mj_user_pref():
    tableName = "mj_user_pref"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_user_pref(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_user_pref表
def create_mj_user_pref(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "loginID VARCHAR(32) NOT NULL UNIQUE COMMENT '用户登录号',",
    "lastFamilyID INT NULL COMMENT '当前家庭ID',",
    "skinCode VARCHAR(32) NULL COMMENT '偏好皮肤编码 NULL为默认',",
    "soundEnabledFlag CHAR(1) NOT NULL DEFAULT '1' COMMENT '音效总开关 1开 0关',",
    "soundVolume INT NOT NULL DEFAULT 70 COMMENT '音效音量 0-100',",
    "chatSoundFlag CHAR(1) NOT NULL DEFAULT '1' COMMENT '聊天音效开关',",
    "showTenpaiFlag CHAR(1) NOT NULL DEFAULT '1' COMMENT '听牌提示开关',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_user_pref表
def drop_mj_user_pref(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_user_pref 删除记录
def delete_mj_user_pref(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_user_pref 增加记录
def insert_mj_user_pref(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["loginID"] = dataSet.get("loginID", "") 

        try:
            lastFamilyID = int(dataSet.get("lastFamilyID")) 
        except:
            lastFamilyID = 0 
        saveSet["lastFamilyID"] = lastFamilyID

        saveSet["skinCode"] = dataSet.get("skinCode", "") 

        saveSet["soundEnabledFlag"] = dataSet.get("soundEnabledFlag", "") 

        try:
            soundVolume = int(dataSet.get("soundVolume")) 
        except:
            soundVolume = 0 
        saveSet["soundVolume"] = soundVolume

        saveSet["chatSoundFlag"] = dataSet.get("chatSoundFlag", "") 

        saveSet["showTenpaiFlag"] = dataSet.get("showTenpaiFlag", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_user_pref 修改记录
def update_mj_user_pref(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        loginID = dataSet.get("loginID") 
        if loginID:
            saveSet["loginID"] = loginID

        try:
            lastFamilyID = int(dataSet.get("lastFamilyID")) 
            saveSet["lastFamilyID"] = lastFamilyID
        except:
            pass

        skinCode = dataSet.get("skinCode") 
        if skinCode:
            saveSet["skinCode"] = skinCode

        soundEnabledFlag = dataSet.get("soundEnabledFlag") 
        if soundEnabledFlag:
            saveSet["soundEnabledFlag"] = soundEnabledFlag

        try:
            soundVolume = int(dataSet.get("soundVolume")) 
            saveSet["soundVolume"] = soundVolume
        except:
            pass

        chatSoundFlag = dataSet.get("chatSoundFlag") 
        if chatSoundFlag:
            saveSet["chatSoundFlag"] = chatSoundFlag

        showTenpaiFlag = dataSet.get("showTenpaiFlag") 
        if showTenpaiFlag:
            saveSet["showTenpaiFlag"] = showTenpaiFlag

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_user_pref end


#mj_rule_family begin 

def tablename_convertor_mj_rule_family():
    tableName = "mj_rule_family"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_rule_family(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_rule_family表
def create_mj_rule_family(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "ruleFamilyCode VARCHAR(32) NOT NULL UNIQUE COMMENT '规则族编码 幂等键',",
    "ruleFamilyName VARCHAR(64) NOT NULL COMMENT '规则族名称',",
    "engineCode VARCHAR(32) NOT NULL COMMENT '引擎插件标识',",
    "tileSetCode VARCHAR(16) NOT NULL DEFAULT '136' COMMENT '牌张集合 136或108',",
    "capabilityJson JSON NULL COMMENT '能力声明 可用开关与番种上限',",
    "ruleFamilyStatus VARCHAR(24) NOT NULL DEFAULT 'ENABLED' COMMENT 'ENABLED或DISABLED',",
    "sortOrder INT NOT NULL DEFAULT 0 COMMENT '排序号',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_rule_family表
def drop_mj_rule_family(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_rule_family 删除记录
def delete_mj_rule_family(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_rule_family 增加记录
def insert_mj_rule_family(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["ruleFamilyCode"] = dataSet.get("ruleFamilyCode", "") 

        saveSet["ruleFamilyName"] = dataSet.get("ruleFamilyName", "") 

        saveSet["engineCode"] = dataSet.get("engineCode", "") 

        saveSet["tileSetCode"] = dataSet.get("tileSetCode", "") 

        saveSet["capabilityJson"] = dataSet.get("capabilityJson", "") 

        saveSet["ruleFamilyStatus"] = dataSet.get("ruleFamilyStatus", "") 

        try:
            sortOrder = int(dataSet.get("sortOrder")) 
        except:
            sortOrder = 0 
        saveSet["sortOrder"] = sortOrder

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_rule_family 修改记录
def update_mj_rule_family(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        ruleFamilyCode = dataSet.get("ruleFamilyCode") 
        if ruleFamilyCode:
            saveSet["ruleFamilyCode"] = ruleFamilyCode

        ruleFamilyName = dataSet.get("ruleFamilyName") 
        if ruleFamilyName:
            saveSet["ruleFamilyName"] = ruleFamilyName

        engineCode = dataSet.get("engineCode") 
        if engineCode:
            saveSet["engineCode"] = engineCode

        tileSetCode = dataSet.get("tileSetCode") 
        if tileSetCode:
            saveSet["tileSetCode"] = tileSetCode

        capabilityJson = dataSet.get("capabilityJson") 
        if capabilityJson:
            saveSet["capabilityJson"] = capabilityJson

        ruleFamilyStatus = dataSet.get("ruleFamilyStatus") 
        if ruleFamilyStatus:
            saveSet["ruleFamilyStatus"] = ruleFamilyStatus

        try:
            sortOrder = int(dataSet.get("sortOrder")) 
            saveSet["sortOrder"] = sortOrder
        except:
            pass

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_rule_family end


#mj_rule_template begin 

def tablename_convertor_mj_rule_template():
    tableName = "mj_rule_template"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_rule_template(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_rule_template表
def create_mj_rule_template(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "templateCode VARCHAR(32) NOT NULL UNIQUE COMMENT '模板编码 幂等键',",
    "familyID INT NOT NULL DEFAULT 0 COMMENT '家庭ID 0为全局预置',",
    "ruleFamilyCode VARCHAR(32) NOT NULL COMMENT '所属规则族编码',",
    "templateName VARCHAR(64) NOT NULL COMMENT '模板名称',",
    "`description` VARCHAR(400) NULL COMMENT '模板说明',",
    "configJson JSON NULL COMMENT '规则参数',",
    "presetFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否预置',",
    "ownerLoginID VARCHAR(32) NULL COMMENT '创建者登录号',",
    "activeFlag CHAR(1) NOT NULL DEFAULT '1' COMMENT '是否启用',",
    "sortOrder INT NOT NULL DEFAULT 0 COMMENT '排序号',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_rule_template表
def drop_mj_rule_template(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_rule_template 删除记录
def delete_mj_rule_template(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_rule_template 增加记录
def insert_mj_rule_template(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["templateCode"] = dataSet.get("templateCode", "") 

        try:
            familyID = int(dataSet.get("familyID")) 
        except:
            familyID = 0 
        saveSet["familyID"] = familyID

        saveSet["ruleFamilyCode"] = dataSet.get("ruleFamilyCode", "") 

        saveSet["templateName"] = dataSet.get("templateName", "") 

        saveSet["description"] = dataSet.get("description", "") 

        saveSet["configJson"] = dataSet.get("configJson", "") 

        saveSet["presetFlag"] = dataSet.get("presetFlag", "") 

        saveSet["ownerLoginID"] = dataSet.get("ownerLoginID", "") 

        saveSet["activeFlag"] = dataSet.get("activeFlag", "") 

        try:
            sortOrder = int(dataSet.get("sortOrder")) 
        except:
            sortOrder = 0 
        saveSet["sortOrder"] = sortOrder

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_rule_template 修改记录
def update_mj_rule_template(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        templateCode = dataSet.get("templateCode") 
        if templateCode:
            saveSet["templateCode"] = templateCode

        try:
            familyID = int(dataSet.get("familyID")) 
            saveSet["familyID"] = familyID
        except:
            pass

        ruleFamilyCode = dataSet.get("ruleFamilyCode") 
        if ruleFamilyCode:
            saveSet["ruleFamilyCode"] = ruleFamilyCode

        templateName = dataSet.get("templateName") 
        if templateName:
            saveSet["templateName"] = templateName

        description = dataSet.get("description") 
        if description:
            saveSet["description"] = description

        configJson = dataSet.get("configJson") 
        if configJson:
            saveSet["configJson"] = configJson

        presetFlag = dataSet.get("presetFlag") 
        if presetFlag:
            saveSet["presetFlag"] = presetFlag

        ownerLoginID = dataSet.get("ownerLoginID") 
        if ownerLoginID:
            saveSet["ownerLoginID"] = ownerLoginID

        activeFlag = dataSet.get("activeFlag") 
        if activeFlag:
            saveSet["activeFlag"] = activeFlag

        try:
            sortOrder = int(dataSet.get("sortOrder")) 
            saveSet["sortOrder"] = sortOrder
        except:
            pass

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_rule_template end


#mj_room begin 

def tablename_convertor_mj_room():
    tableName = "mj_room"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_room(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_room表
def create_mj_room(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "roomCode CHAR(6) NOT NULL UNIQUE COMMENT '6位数字邀请码',",
    "familyID INT NOT NULL COMMENT '家庭ID',",
    "roomName VARCHAR(64) NOT NULL COMMENT '房间名称',",
    "hostLoginID VARCHAR(32) NOT NULL COMMENT '房主登录号',",
    "templateID INT NULL COMMENT '规则模板ID',",
    "ruleFamilyCode VARCHAR(32) NOT NULL COMMENT '规则族编码',",
    "ruleSnapshot JSON NULL COMMENT '开桌时规则快照',",
    "roomStatus VARCHAR(16) NOT NULL DEFAULT 'OPEN' COMMENT 'OPEN或CLOSED',",
    "createdYMDHMS VARCHAR(16) NOT NULL COMMENT '创建时间',",
    "closedYMDHMS VARCHAR(16) NULL COMMENT '关闭时间',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_room表
def drop_mj_room(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_room 删除记录
def delete_mj_room(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_room 增加记录
def insert_mj_room(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["roomCode"] = dataSet.get("roomCode", "") 

        try:
            familyID = int(dataSet.get("familyID")) 
        except:
            familyID = 0 
        saveSet["familyID"] = familyID

        saveSet["roomName"] = dataSet.get("roomName", "") 

        saveSet["hostLoginID"] = dataSet.get("hostLoginID", "") 

        try:
            templateID = int(dataSet.get("templateID")) 
        except:
            templateID = 0 
        saveSet["templateID"] = templateID

        saveSet["ruleFamilyCode"] = dataSet.get("ruleFamilyCode", "") 

        saveSet["ruleSnapshot"] = dataSet.get("ruleSnapshot", "") 

        saveSet["roomStatus"] = dataSet.get("roomStatus", "") 

        saveSet["createdYMDHMS"] = dataSet.get("createdYMDHMS", "") 

        saveSet["closedYMDHMS"] = dataSet.get("closedYMDHMS", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_room 修改记录
def update_mj_room(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        roomCode = dataSet.get("roomCode") 
        if roomCode:
            saveSet["roomCode"] = roomCode

        try:
            familyID = int(dataSet.get("familyID")) 
            saveSet["familyID"] = familyID
        except:
            pass

        roomName = dataSet.get("roomName") 
        if roomName:
            saveSet["roomName"] = roomName

        hostLoginID = dataSet.get("hostLoginID") 
        if hostLoginID:
            saveSet["hostLoginID"] = hostLoginID

        try:
            templateID = int(dataSet.get("templateID")) 
            saveSet["templateID"] = templateID
        except:
            pass

        ruleFamilyCode = dataSet.get("ruleFamilyCode") 
        if ruleFamilyCode:
            saveSet["ruleFamilyCode"] = ruleFamilyCode

        ruleSnapshot = dataSet.get("ruleSnapshot") 
        if ruleSnapshot:
            saveSet["ruleSnapshot"] = ruleSnapshot

        roomStatus = dataSet.get("roomStatus") 
        if roomStatus:
            saveSet["roomStatus"] = roomStatus

        createdYMDHMS = dataSet.get("createdYMDHMS") 
        if createdYMDHMS:
            saveSet["createdYMDHMS"] = createdYMDHMS

        closedYMDHMS = dataSet.get("closedYMDHMS") 
        if closedYMDHMS:
            saveSet["closedYMDHMS"] = closedYMDHMS

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_room end


#mj_game begin 

def tablename_convertor_mj_game():
    tableName = "mj_game"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_game(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_game表
def create_mj_game(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "familyID INT NOT NULL COMMENT '家庭ID',",
    "roomID INT NOT NULL COMMENT '房间ID',",
    "ruleFamilyCode VARCHAR(32) NOT NULL COMMENT '规则族编码',",
    "ruleSnapshot JSON NULL COMMENT '开局时规则快照',",
    "seatDrawJson JSON NULL COMMENT '抽座与掷骰记录 各座位点数与庄家',",
    "gameStatus VARCHAR(16) NOT NULL DEFAULT 'PLAYING' COMMENT 'PLAYING或FINISHED或ABORTED',",
    "startedYMDHMS VARCHAR(16) NOT NULL COMMENT '开始时间',",
    "endedYMDHMS VARCHAR(16) NULL COMMENT '结束时间',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_game表
def drop_mj_game(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_game 删除记录
def delete_mj_game(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_game 增加记录
def insert_mj_game(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        try:
            familyID = int(dataSet.get("familyID")) 
        except:
            familyID = 0 
        saveSet["familyID"] = familyID

        try:
            roomID = int(dataSet.get("roomID")) 
        except:
            roomID = 0 
        saveSet["roomID"] = roomID

        saveSet["ruleFamilyCode"] = dataSet.get("ruleFamilyCode", "") 

        saveSet["ruleSnapshot"] = dataSet.get("ruleSnapshot", "") 

        saveSet["seatDrawJson"] = dataSet.get("seatDrawJson", "") 

        saveSet["gameStatus"] = dataSet.get("gameStatus", "") 

        saveSet["startedYMDHMS"] = dataSet.get("startedYMDHMS", "") 

        saveSet["endedYMDHMS"] = dataSet.get("endedYMDHMS", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_game 修改记录
def update_mj_game(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        try:
            familyID = int(dataSet.get("familyID")) 
            saveSet["familyID"] = familyID
        except:
            pass

        try:
            roomID = int(dataSet.get("roomID")) 
            saveSet["roomID"] = roomID
        except:
            pass

        ruleFamilyCode = dataSet.get("ruleFamilyCode") 
        if ruleFamilyCode:
            saveSet["ruleFamilyCode"] = ruleFamilyCode

        ruleSnapshot = dataSet.get("ruleSnapshot") 
        if ruleSnapshot:
            saveSet["ruleSnapshot"] = ruleSnapshot

        seatDrawJson = dataSet.get("seatDrawJson") 
        if seatDrawJson:
            saveSet["seatDrawJson"] = seatDrawJson

        gameStatus = dataSet.get("gameStatus") 
        if gameStatus:
            saveSet["gameStatus"] = gameStatus

        startedYMDHMS = dataSet.get("startedYMDHMS") 
        if startedYMDHMS:
            saveSet["startedYMDHMS"] = startedYMDHMS

        endedYMDHMS = dataSet.get("endedYMDHMS") 
        if endedYMDHMS:
            saveSet["endedYMDHMS"] = endedYMDHMS

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_game end


#mj_game_player begin 

def tablename_convertor_mj_game_player():
    tableName = "mj_game_player"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_game_player(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_game_player表
def create_mj_game_player(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "gameSeatKey VARCHAR(40) NOT NULL UNIQUE COMMENT '座位幂等键 gameID_seatNo',",
    "gameID INT NOT NULL COMMENT '场次ID',",
    "familyID INT NOT NULL COMMENT '家庭ID',",
    "seatNo TINYINT NOT NULL COMMENT '座位号 0到3',",
    "loginID VARCHAR(32) NOT NULL COMMENT '玩家登录号',",
    "displayName VARCHAR(40) NULL COMMENT '结算时昵称快照',",
    "totalScore INT NOT NULL DEFAULT 0 COMMENT '本场累计分',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_game_player表
def drop_mj_game_player(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_game_player 删除记录
def delete_mj_game_player(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_game_player 增加记录
def insert_mj_game_player(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["gameSeatKey"] = dataSet.get("gameSeatKey", "") 

        try:
            gameID = int(dataSet.get("gameID")) 
        except:
            gameID = 0 
        saveSet["gameID"] = gameID

        try:
            familyID = int(dataSet.get("familyID")) 
        except:
            familyID = 0 
        saveSet["familyID"] = familyID

        try:
            seatNo = int(dataSet.get("seatNo")) 
        except:
            seatNo = 0 
        saveSet["seatNo"] = seatNo

        saveSet["loginID"] = dataSet.get("loginID", "") 

        saveSet["displayName"] = dataSet.get("displayName", "") 

        try:
            totalScore = int(dataSet.get("totalScore")) 
        except:
            totalScore = 0 
        saveSet["totalScore"] = totalScore

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_game_player 修改记录
def update_mj_game_player(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        gameSeatKey = dataSet.get("gameSeatKey") 
        if gameSeatKey:
            saveSet["gameSeatKey"] = gameSeatKey

        try:
            gameID = int(dataSet.get("gameID")) 
            saveSet["gameID"] = gameID
        except:
            pass

        try:
            familyID = int(dataSet.get("familyID")) 
            saveSet["familyID"] = familyID
        except:
            pass

        try:
            seatNo = int(dataSet.get("seatNo")) 
            saveSet["seatNo"] = seatNo
        except:
            pass

        loginID = dataSet.get("loginID") 
        if loginID:
            saveSet["loginID"] = loginID

        displayName = dataSet.get("displayName") 
        if displayName:
            saveSet["displayName"] = displayName

        try:
            totalScore = int(dataSet.get("totalScore")) 
            saveSet["totalScore"] = totalScore
        except:
            pass

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_game_player end


#mj_game_round begin 

def tablename_convertor_mj_game_round():
    tableName = "mj_game_round"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_game_round(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_game_round表
def create_mj_game_round(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "gameID INT NOT NULL COMMENT '场次ID',",
    "familyID INT NOT NULL COMMENT '家庭ID',",
    "roundNo SMALLINT NOT NULL COMMENT '局号 从1开始',",
    "dealerSeat TINYINT NOT NULL COMMENT '庄家座位',",
    "roundWind TINYINT NOT NULL DEFAULT 0 COMMENT '本局局风 0东1南2西3北',",
    "winnerSeat TINYINT NULL COMMENT '赢家座位 NULL为荒庄',",
    "winType VARCHAR(16) NOT NULL DEFAULT 'none' COMMENT 'self_draw或discard或rob_kong或none',",
    "winningTile TINYINT NULL COMMENT '胡牌牌编码 0到33',",
    "patternID VARCHAR(32) NULL COMMENT '牌型标识',",
    "fanItemsJson JSON NULL COMMENT '番种明细 含倍数与封顶信息',",
    "fanRaw INT NOT NULL DEFAULT 0 COMMENT '封顶前番数 不封顶时等于fanTotal',",
    "fanTotal INT NOT NULL DEFAULT 0 COMMENT '总番 封顶后',",
    "scoreDeltaJson JSON NULL COMMENT '四家分差 顺序为座位0到3',",
    "payerJson JSON NULL COMMENT '付款方明细 含包牌者与被包家 见03规则族设计',",
    "finishedYMDHMS VARCHAR(16) NOT NULL COMMENT '结算时间',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_game_round表
def drop_mj_game_round(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_game_round 删除记录
def delete_mj_game_round(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_game_round 增加记录
def insert_mj_game_round(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        try:
            gameID = int(dataSet.get("gameID")) 
        except:
            gameID = 0 
        saveSet["gameID"] = gameID

        try:
            familyID = int(dataSet.get("familyID")) 
        except:
            familyID = 0 
        saveSet["familyID"] = familyID

        try:
            roundNo = int(dataSet.get("roundNo")) 
        except:
            roundNo = 0 
        saveSet["roundNo"] = roundNo

        try:
            dealerSeat = int(dataSet.get("dealerSeat")) 
        except:
            dealerSeat = 0 
        saveSet["dealerSeat"] = dealerSeat

        try:
            roundWind = int(dataSet.get("roundWind")) 
        except:
            roundWind = 0 
        saveSet["roundWind"] = roundWind

        try:
            winnerSeat = int(dataSet.get("winnerSeat")) 
        except:
            winnerSeat = 0 
        saveSet["winnerSeat"] = winnerSeat

        saveSet["winType"] = dataSet.get("winType", "") 

        try:
            winningTile = int(dataSet.get("winningTile")) 
        except:
            winningTile = 0 
        saveSet["winningTile"] = winningTile

        saveSet["patternID"] = dataSet.get("patternID", "") 

        saveSet["fanItemsJson"] = dataSet.get("fanItemsJson", "") 

        try:
            fanRaw = int(dataSet.get("fanRaw")) 
        except:
            fanRaw = 0 
        saveSet["fanRaw"] = fanRaw

        try:
            fanTotal = int(dataSet.get("fanTotal")) 
        except:
            fanTotal = 0 
        saveSet["fanTotal"] = fanTotal

        saveSet["scoreDeltaJson"] = dataSet.get("scoreDeltaJson", "") 

        saveSet["payerJson"] = dataSet.get("payerJson", "") 

        saveSet["finishedYMDHMS"] = dataSet.get("finishedYMDHMS", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_game_round 修改记录
def update_mj_game_round(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        try:
            gameID = int(dataSet.get("gameID")) 
            saveSet["gameID"] = gameID
        except:
            pass

        try:
            familyID = int(dataSet.get("familyID")) 
            saveSet["familyID"] = familyID
        except:
            pass

        try:
            roundNo = int(dataSet.get("roundNo")) 
            saveSet["roundNo"] = roundNo
        except:
            pass

        try:
            dealerSeat = int(dataSet.get("dealerSeat")) 
            saveSet["dealerSeat"] = dealerSeat
        except:
            pass

        try:
            roundWind = int(dataSet.get("roundWind")) 
            saveSet["roundWind"] = roundWind
        except:
            pass

        try:
            winnerSeat = int(dataSet.get("winnerSeat")) 
            saveSet["winnerSeat"] = winnerSeat
        except:
            pass

        winType = dataSet.get("winType") 
        if winType:
            saveSet["winType"] = winType

        try:
            winningTile = int(dataSet.get("winningTile")) 
            saveSet["winningTile"] = winningTile
        except:
            pass

        patternID = dataSet.get("patternID") 
        if patternID:
            saveSet["patternID"] = patternID

        fanItemsJson = dataSet.get("fanItemsJson") 
        if fanItemsJson:
            saveSet["fanItemsJson"] = fanItemsJson

        try:
            fanRaw = int(dataSet.get("fanRaw")) 
            saveSet["fanRaw"] = fanRaw
        except:
            pass

        try:
            fanTotal = int(dataSet.get("fanTotal")) 
            saveSet["fanTotal"] = fanTotal
        except:
            pass

        scoreDeltaJson = dataSet.get("scoreDeltaJson") 
        if scoreDeltaJson:
            saveSet["scoreDeltaJson"] = scoreDeltaJson

        payerJson = dataSet.get("payerJson") 
        if payerJson:
            saveSet["payerJson"] = payerJson

        finishedYMDHMS = dataSet.get("finishedYMDHMS") 
        if finishedYMDHMS:
            saveSet["finishedYMDHMS"] = finishedYMDHMS

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_game_round end


#mj_room_message begin 

def tablename_convertor_mj_room_message():
    tableName = "mj_room_message"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_room_message(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_room_message表
def create_mj_room_message(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "roomID INT NOT NULL COMMENT '房间ID',",
    "familyID INT NOT NULL COMMENT '家庭ID',",
    "loginID VARCHAR(32) NULL COMMENT '发送者 NULL为系统播报',",
    "messageKind VARCHAR(16) NOT NULL DEFAULT 'chat' COMMENT 'chat或system',",
    "content VARCHAR(500) NOT NULL COMMENT '消息内容',",
    "createdYMDHMS VARCHAR(16) NOT NULL COMMENT '发送时间',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_room_message表
def drop_mj_room_message(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_room_message 删除记录
def delete_mj_room_message(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_room_message 增加记录
def insert_mj_room_message(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        try:
            roomID = int(dataSet.get("roomID")) 
        except:
            roomID = 0 
        saveSet["roomID"] = roomID

        try:
            familyID = int(dataSet.get("familyID")) 
        except:
            familyID = 0 
        saveSet["familyID"] = familyID

        saveSet["loginID"] = dataSet.get("loginID", "") 

        saveSet["messageKind"] = dataSet.get("messageKind", "") 

        saveSet["content"] = dataSet.get("content", "") 

        saveSet["createdYMDHMS"] = dataSet.get("createdYMDHMS", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_room_message 修改记录
def update_mj_room_message(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        try:
            roomID = int(dataSet.get("roomID")) 
            saveSet["roomID"] = roomID
        except:
            pass

        try:
            familyID = int(dataSet.get("familyID")) 
            saveSet["familyID"] = familyID
        except:
            pass

        loginID = dataSet.get("loginID") 
        if loginID:
            saveSet["loginID"] = loginID

        messageKind = dataSet.get("messageKind") 
        if messageKind:
            saveSet["messageKind"] = messageKind

        content = dataSet.get("content") 
        if content:
            saveSet["content"] = content

        createdYMDHMS = dataSet.get("createdYMDHMS") 
        if createdYMDHMS:
            saveSet["createdYMDHMS"] = createdYMDHMS

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_room_message end


#mj_tile_skin begin 

def tablename_convertor_mj_tile_skin():
    tableName = "mj_tile_skin"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_tile_skin(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_tile_skin表
def create_mj_tile_skin(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "skinCode VARCHAR(32) NOT NULL UNIQUE COMMENT '皮肤编码 幂等键',",
    "skinName VARCHAR(64) NOT NULL COMMENT '皮肤名称',",
    "familyID INT NOT NULL DEFAULT 0 COMMENT '家庭ID 0为全局内置',",
    "previewFileID VARCHAR(200) NULL COMMENT '预览图相对路径',",
    "tileAspect DECIMAL(6,4) NOT NULL DEFAULT 0.6667 COMMENT '牌面宽高比 宽除以高',",
    "defaultFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否默认皮肤',",
    "skinStatus VARCHAR(24) NOT NULL DEFAULT 'ENABLED' COMMENT 'ENABLED或DISABLED',",
    "sortOrder INT NOT NULL DEFAULT 0 COMMENT '排序号',",
    "ownerLoginID VARCHAR(32) NULL COMMENT '上传者登录号',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_tile_skin表
def drop_mj_tile_skin(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_tile_skin 删除记录
def delete_mj_tile_skin(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_tile_skin 增加记录
def insert_mj_tile_skin(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["skinCode"] = dataSet.get("skinCode", "") 

        saveSet["skinName"] = dataSet.get("skinName", "") 

        try:
            familyID = int(dataSet.get("familyID")) 
        except:
            familyID = 0 
        saveSet["familyID"] = familyID

        saveSet["previewFileID"] = dataSet.get("previewFileID", "") 

        try:
            tileAspect = float(dataSet.get("tileAspect")) 
        except:
            tileAspect = 0 
        saveSet["tileAspect"] = tileAspect

        saveSet["defaultFlag"] = dataSet.get("defaultFlag", "") 

        saveSet["skinStatus"] = dataSet.get("skinStatus", "") 

        try:
            sortOrder = int(dataSet.get("sortOrder")) 
        except:
            sortOrder = 0 
        saveSet["sortOrder"] = sortOrder

        saveSet["ownerLoginID"] = dataSet.get("ownerLoginID", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_tile_skin 修改记录
def update_mj_tile_skin(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        skinCode = dataSet.get("skinCode") 
        if skinCode:
            saveSet["skinCode"] = skinCode

        skinName = dataSet.get("skinName") 
        if skinName:
            saveSet["skinName"] = skinName

        try:
            familyID = int(dataSet.get("familyID")) 
            saveSet["familyID"] = familyID
        except:
            pass

        previewFileID = dataSet.get("previewFileID") 
        if previewFileID:
            saveSet["previewFileID"] = previewFileID

        try:
            tileAspect = float(dataSet.get("tileAspect")) 
            saveSet["tileAspect"] = tileAspect
        except:
            pass

        defaultFlag = dataSet.get("defaultFlag") 
        if defaultFlag:
            saveSet["defaultFlag"] = defaultFlag

        skinStatus = dataSet.get("skinStatus") 
        if skinStatus:
            saveSet["skinStatus"] = skinStatus

        try:
            sortOrder = int(dataSet.get("sortOrder")) 
            saveSet["sortOrder"] = sortOrder
        except:
            pass

        ownerLoginID = dataSet.get("ownerLoginID") 
        if ownerLoginID:
            saveSet["ownerLoginID"] = ownerLoginID

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_tile_skin end


#mj_tile_skin_asset begin 

def tablename_convertor_mj_tile_skin_asset():
    tableName = "mj_tile_skin_asset"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_tile_skin_asset(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_tile_skin_asset表
def create_mj_tile_skin_asset(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "skinTileKey VARCHAR(80) NOT NULL UNIQUE COMMENT '资源幂等键 skinCode_tileKey',",
    "skinID INT NOT NULL COMMENT '皮肤ID',",
    "familyID INT NOT NULL DEFAULT 0 COMMENT '家庭ID 0为全局内置',",
    "tileKey VARCHAR(16) NOT NULL COMMENT '牌键 如1m或back',",
    "fileID VARCHAR(200) NOT NULL COMMENT '图片相对路径',",
    "thumbFileID VARCHAR(200) NULL COMMENT '缩略图相对路径',",
    "width SMALLINT NOT NULL DEFAULT 0 COMMENT '像素宽',",
    "height SMALLINT NOT NULL DEFAULT 0 COMMENT '像素高',",
    "fileSize INT NOT NULL DEFAULT 0 COMMENT '字节数',",
    "sortOrder INT NOT NULL DEFAULT 0 COMMENT '排序号',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_tile_skin_asset表
def drop_mj_tile_skin_asset(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_tile_skin_asset 删除记录
def delete_mj_tile_skin_asset(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_tile_skin_asset 增加记录
def insert_mj_tile_skin_asset(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["skinTileKey"] = dataSet.get("skinTileKey", "") 

        try:
            skinID = int(dataSet.get("skinID")) 
        except:
            skinID = 0 
        saveSet["skinID"] = skinID

        try:
            familyID = int(dataSet.get("familyID")) 
        except:
            familyID = 0 
        saveSet["familyID"] = familyID

        saveSet["tileKey"] = dataSet.get("tileKey", "") 

        saveSet["fileID"] = dataSet.get("fileID", "") 

        saveSet["thumbFileID"] = dataSet.get("thumbFileID", "") 

        try:
            width = int(dataSet.get("width")) 
        except:
            width = 0 
        saveSet["width"] = width

        try:
            height = int(dataSet.get("height")) 
        except:
            height = 0 
        saveSet["height"] = height

        try:
            fileSize = int(dataSet.get("fileSize")) 
        except:
            fileSize = 0 
        saveSet["fileSize"] = fileSize

        try:
            sortOrder = int(dataSet.get("sortOrder")) 
        except:
            sortOrder = 0 
        saveSet["sortOrder"] = sortOrder

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_tile_skin_asset 修改记录
def update_mj_tile_skin_asset(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        skinTileKey = dataSet.get("skinTileKey") 
        if skinTileKey:
            saveSet["skinTileKey"] = skinTileKey

        try:
            skinID = int(dataSet.get("skinID")) 
            saveSet["skinID"] = skinID
        except:
            pass

        try:
            familyID = int(dataSet.get("familyID")) 
            saveSet["familyID"] = familyID
        except:
            pass

        tileKey = dataSet.get("tileKey") 
        if tileKey:
            saveSet["tileKey"] = tileKey

        fileID = dataSet.get("fileID") 
        if fileID:
            saveSet["fileID"] = fileID

        thumbFileID = dataSet.get("thumbFileID") 
        if thumbFileID:
            saveSet["thumbFileID"] = thumbFileID

        try:
            width = int(dataSet.get("width")) 
            saveSet["width"] = width
        except:
            pass

        try:
            height = int(dataSet.get("height")) 
            saveSet["height"] = height
        except:
            pass

        try:
            fileSize = int(dataSet.get("fileSize")) 
            saveSet["fileSize"] = fileSize
        except:
            pass

        try:
            sortOrder = int(dataSet.get("sortOrder")) 
            saveSet["sortOrder"] = sortOrder
        except:
            pass

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_tile_skin_asset end


#mj_audit_log begin 

def tablename_convertor_mj_audit_log():
    tableName = "mj_audit_log"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_audit_log(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_audit_log表
def create_mj_audit_log(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "familyID INT NOT NULL DEFAULT 0 COMMENT '家庭ID 0为系统级',",
    "operatorLoginID VARCHAR(32) NOT NULL COMMENT '操作者登录号',",
    "actionCode VARCHAR(32) NOT NULL COMMENT '动作编码',",
    "targetType VARCHAR(24) NOT NULL COMMENT '对象类型',",
    "targetID VARCHAR(64) NULL COMMENT '对象标识',",
    "detailJson JSON NULL COMMENT '动作详情',",
    "clientIP VARCHAR(64) NULL COMMENT '客户端IP',",
    "createdYMDHMS VARCHAR(16) NOT NULL COMMENT '操作时间',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_audit_log表
def drop_mj_audit_log(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_audit_log 删除记录
def delete_mj_audit_log(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_audit_log 增加记录
def insert_mj_audit_log(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        try:
            familyID = int(dataSet.get("familyID")) 
        except:
            familyID = 0 
        saveSet["familyID"] = familyID

        saveSet["operatorLoginID"] = dataSet.get("operatorLoginID", "") 

        saveSet["actionCode"] = dataSet.get("actionCode", "") 

        saveSet["targetType"] = dataSet.get("targetType", "") 

        saveSet["targetID"] = dataSet.get("targetID", "") 

        saveSet["detailJson"] = dataSet.get("detailJson", "") 

        saveSet["clientIP"] = dataSet.get("clientIP", "") 

        saveSet["createdYMDHMS"] = dataSet.get("createdYMDHMS", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_audit_log 修改记录
def update_mj_audit_log(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        try:
            familyID = int(dataSet.get("familyID")) 
            saveSet["familyID"] = familyID
        except:
            pass

        operatorLoginID = dataSet.get("operatorLoginID") 
        if operatorLoginID:
            saveSet["operatorLoginID"] = operatorLoginID

        actionCode = dataSet.get("actionCode") 
        if actionCode:
            saveSet["actionCode"] = actionCode

        targetType = dataSet.get("targetType") 
        if targetType:
            saveSet["targetType"] = targetType

        targetID = dataSet.get("targetID") 
        if targetID:
            saveSet["targetID"] = targetID

        detailJson = dataSet.get("detailJson") 
        if detailJson:
            saveSet["detailJson"] = detailJson

        clientIP = dataSet.get("clientIP") 
        if clientIP:
            saveSet["clientIP"] = clientIP

        createdYMDHMS = dataSet.get("createdYMDHMS") 
        if createdYMDHMS:
            saveSet["createdYMDHMS"] = createdYMDHMS

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_audit_log end


#mj_schema_version begin 

def tablename_convertor_mj_schema_version():
    tableName = "mj_schema_version"
    tableName = tableName.lower()
    return tableName


def decode_tablename_mj_schema_version(tableName):
    result = {}
    aList = tableName.split("_")
    
    return result


#创建mj_schema_version表
def create_mj_schema_version(tableName):
    aList = ["CREATE TABLE IF NOT EXISTS %s("
    "recID INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',",
    "versionCode VARCHAR(32) NOT NULL UNIQUE COMMENT '结构版本号',",
    "`description` VARCHAR(200) NULL COMMENT '变更说明',",
    "appliedYMDHMS VARCHAR(16) NOT NULL COMMENT '执行时间',",
    "label VARCHAR(32) COMMENT 'label',",
    "memo VARCHAR(200) COMMENT 'memo',",
    "regID VARCHAR(32) COMMENT '注册ID',",
    "regYMDHMS VARCHAR(16) COMMENT '注册年月日',",
    "modifyID VARCHAR(32) COMMENT '修改用户ID',",
    "modifyYMDHMS VARCHAR(16) COMMENT '修改年月日',",
    "delFlag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标记'"
    ")  ENGINE=INNODB DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    tempStr = "".join(aList)
    sqlStr = tempStr % (tableName)
    rtn = mysqlDB.executeWrite(sqlStr)
    result = chkTableExist(tableName)
    if result:
        pass
        #sqlStr = "CREATE INDEX {1} ON {0}({1}) ".format(tableName, "indexKey")
        #rtn = mysqlDB.executeWrite(sqlStr)
        #sqlStr = "ALTER TABLE {0} auto_increment = {1} ".format(tableName,auto_increment_default_value)
        #rtn = mysqlDB.executeWrite(sqlStr)

    return result


#删除mj_schema_version表
def drop_mj_schema_version(tableName):
    result = dropTableGeneral(tableName)
    return result


#mj_schema_version 删除记录
def delete_mj_schema_version(tableName,recID):
    result = 0
    sqlStr = f"DELETE FROM {tableName}"
    try:

        sqlStr += " WHERE recID = %s"
        valuesList = [recID] 
        result = mysqlDB.executeWrite(sqlStr,tuple(valuesList))

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_schema_version 增加记录
def insert_mj_schema_version(tableName,dataSet):
    result = 0
    try:

        saveSet = {}

        saveSet["versionCode"] = dataSet.get("versionCode", "") 

        saveSet["description"] = dataSet.get("description", "") 

        saveSet["appliedYMDHMS"] = dataSet.get("appliedYMDHMS", "") 

        saveSet["label"] = dataSet.get("label", "") 

        saveSet["memo"] = dataSet.get("memo", "") 

        saveSet["regID"] = dataSet.get("regID", "") 

        saveSet["regYMDHMS"] = dataSet.get("regYMDHMS", "") 

        saveSet["delFlag"] = dataSet.get("delFlag", "0") 

        result = insertTableGeneral(tableName, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_schema_version 修改记录
def update_mj_schema_version(tableName,recID,dataSet):
    result = -2
    try:
        saveSet = {}

        versionCode = dataSet.get("versionCode") 
        if versionCode:
            saveSet["versionCode"] = versionCode

        description = dataSet.get("description") 
        if description:
            saveSet["description"] = description

        appliedYMDHMS = dataSet.get("appliedYMDHMS") 
        if appliedYMDHMS:
            saveSet["appliedYMDHMS"] = appliedYMDHMS

        label = dataSet.get("label") 
        if label:
            saveSet["label"] = label

        memo = dataSet.get("memo") 
        if memo:
            saveSet["memo"] = memo

        modifyID = dataSet.get("modifyID") 
        if modifyID:
            saveSet["modifyID"] = modifyID

        modifyYMDHMS = dataSet.get("modifyYMDHMS") 
        if modifyYMDHMS:
            saveSet["modifyYMDHMS"] = modifyYMDHMS

        delFlag = dataSet.get("delFlag") 
        if delFlag:
            saveSet["delFlag"] = delFlag

        keySqlstr = "recID = %s"
        keyValues = [recID]

        result = updateTableGeneral(tableName, keySqlstr,  keyValues, saveSet)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_schema_version end

#===== auto-generated sections end =====
