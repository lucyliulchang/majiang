#! /usr/bin/env python3
#encoding: utf-8

#Filename: auto_generated/auto_gen_code_mj_game_round.py
#Author: Steven Lian's team
#E-mail: steven.lian@gmail.com
#Date: 2026-10-27 
#Description: auto_generated/auto_gen_code_mj_game_round.py 服务接口


#mysqlCommon code begin 


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
    "finalHandsJson JSON NULL COMMENT '终局四家手牌与副露 含胡张 用于结算回放核对',",
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

        saveSet["finalHandsJson"] = dataSet.get("finalHandsJson", "") 

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

        finalHandsJson = dataSet.get("finalHandsJson") 
        if finalHandsJson:
            saveSet["finalHandsJson"] = finalHandsJson

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


#mj_game_round 查询记录
def query_mj_game_round(tableName,recID = "0", delFlag = "0", mode = "full",limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
    result = []
    columns = "*"
    valuesList = []
    sqlStr = f"SELECT {columns} FROM {tableName}"

    try:

        try:
            recID = int(recID)
        except:
            recID = 0

        if recID > 0:
            sqlStr =  sqlStr + " WHERE recID = %s" 
            valuesList = [recID]  

        #if limitNum > 0:
            #sqlStr += " LIMIT {0}".format(limitNum)

        rtn = mysqlDB.executeRead(sqlStr, tuple(valuesList))
        if rtn > 0:
            dataList = mysqlDB.fetchAll()
            dataList = dataFormatConvert(dataList)
            result = list(dataList)

    except Exception as e:
        traceMsg = traceback.format_exc().strip("")
        errMsg = f"{e},{traceMsg}"
        # if _DEBUG:
            # _LOG.error(f"{errMsg}")

    return result


#mj_game_round end 


#mysqlCommon code end 



#http interface code begin 


#Server REST增加代码
def funcGameroundAdd(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:
        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True
                if dataValidFlag:
                    saveSet = {}
                    saveSet["gameID"] = dataSet.get("gameID", "") 
                    saveSet["familyID"] = dataSet.get("familyID", "") 
                    saveSet["roundNo"] = dataSet.get("roundNo", "") 
                    saveSet["dealerSeat"] = dataSet.get("dealerSeat", "") 
                    saveSet["roundWind"] = dataSet.get("roundWind", "") 
                    saveSet["winnerSeat"] = dataSet.get("winnerSeat", "") 
                    saveSet["winType"] = dataSet.get("winType", "") 
                    saveSet["winningTile"] = dataSet.get("winningTile", "") 
                    saveSet["patternID"] = dataSet.get("patternID", "") 
                    saveSet["fanItemsJson"] = dataSet.get("fanItemsJson", "") 
                    saveSet["fanRaw"] = dataSet.get("fanRaw", "") 
                    saveSet["fanTotal"] = dataSet.get("fanTotal", "") 
                    saveSet["scoreDeltaJson"] = dataSet.get("scoreDeltaJson", "") 
                    saveSet["payerJson"] = dataSet.get("payerJson", "") 
                    saveSet["finishedYMDHMS"] = dataSet.get("finishedYMDHMS", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_mj_game_round()
                    recID = comMysql.insert_mj_game_round(tableName,saveSet)
                    rtnData["recID"] = str(recID)

                    if recID <= 0:
                        #记录添加失败
                        errCode = "CG"
                        _LOG.warning(f"rtn:{recID},saveSet:{saveSet}")
                    else:
                        if _DEBUG:
                            pass
                            _LOG.info(f"D: recID:{recID}")

                    result = rtnData

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST删除代码
def funcGameroundDel(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID
            #权限检查

            if errCode == "B0": #
                recID = dataSet.get("recID", "")
                tableName = comMysql.tablename_convertor_mj_game_round()
                currDataList = comMysql.query_mj_game_round(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_mj_game_round(tableName,recID)
                    rtnData["rtn"] = str(rtn)

                    if _DEBUG:
                        _LOG.info(f"D: rtn:{rtn}")

                    result = rtnData

                else:
                    errCode = "CB"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST修改代码
def funcGameroundModify(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查/功能检测

            if errCode == "B0": #
                #data validation check
                dataValidFlag = True

                gameID = dataSet.get("gameID") 
                familyID = dataSet.get("familyID") 
                roundNo = dataSet.get("roundNo") 
                dealerSeat = dataSet.get("dealerSeat") 
                roundWind = dataSet.get("roundWind") 
                winnerSeat = dataSet.get("winnerSeat") 
                winType = dataSet.get("winType") 
                winningTile = dataSet.get("winningTile") 
                patternID = dataSet.get("patternID") 
                fanItemsJson = dataSet.get("fanItemsJson") 
                fanRaw = dataSet.get("fanRaw") 
                fanTotal = dataSet.get("fanTotal") 
                scoreDeltaJson = dataSet.get("scoreDeltaJson") 
                payerJson = dataSet.get("payerJson") 
                finishedYMDHMS = dataSet.get("finishedYMDHMS") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_mj_game_round()
                    currDataList = comMysql.query_mj_game_round(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if gameID != currDataSet.get("gameID") and gameID != None:
                                saveSet["gameID"] = gameID

                            if familyID != currDataSet.get("familyID") and familyID != None:
                                saveSet["familyID"] = familyID

                            if roundNo != currDataSet.get("roundNo") and roundNo != None:
                                saveSet["roundNo"] = roundNo

                            if dealerSeat != currDataSet.get("dealerSeat") and dealerSeat != None:
                                saveSet["dealerSeat"] = dealerSeat

                            if roundWind != currDataSet.get("roundWind") and roundWind != None:
                                saveSet["roundWind"] = roundWind

                            if winnerSeat != currDataSet.get("winnerSeat") and winnerSeat != None:
                                saveSet["winnerSeat"] = winnerSeat

                            if winType != currDataSet.get("winType") and winType:
                                saveSet["winType"] = winType

                            if winningTile != currDataSet.get("winningTile") and winningTile != None:
                                saveSet["winningTile"] = winningTile

                            if patternID != currDataSet.get("patternID") and patternID:
                                saveSet["patternID"] = patternID

                            if fanItemsJson != currDataSet.get("fanItemsJson") and fanItemsJson:
                                saveSet["fanItemsJson"] = fanItemsJson

                            if fanRaw != currDataSet.get("fanRaw") and fanRaw != None:
                                saveSet["fanRaw"] = fanRaw

                            if fanTotal != currDataSet.get("fanTotal") and fanTotal != None:
                                saveSet["fanTotal"] = fanTotal

                            if scoreDeltaJson != currDataSet.get("scoreDeltaJson") and scoreDeltaJson:
                                saveSet["scoreDeltaJson"] = scoreDeltaJson

                            if payerJson != currDataSet.get("payerJson") and payerJson:
                                saveSet["payerJson"] = payerJson

                            if finishedYMDHMS != currDataSet.get("finishedYMDHMS") and finishedYMDHMS:
                                saveSet["finishedYMDHMS"] = finishedYMDHMS

                            if label != currDataSet.get("label") and label:
                                saveSet["label"] = label

                            if memo != currDataSet.get("memo") and memo:
                                saveSet["memo"] = memo

                            if delFlag != currDataSet.get("delFlag") and delFlag:
                                saveSet["delFlag"] = delFlag

                            if saveSet:
                                #saveSet["delFlag"] = "0"
                                saveSet["modifyID"] = loginID
                                saveSet["modifyYMDHMS"] = misc.getTime()

                                #保存数据
                                tableName = comMysql.tablename_convertor_mj_game_round()
                                rtn = comMysql.update_mj_game_round(tableName,recID,saveSet)
                                rtnData["rtn"] = str(rtn)

                                if rtn < 0:
                                    _LOG.warning(f"D: rtn:{rtn},saveSet:{saveSet}")
                                else:
                                    if _DEBUG:
                                        pass
                                        _LOG.info(f"D: rtn:{rtn}")

                                result = rtnData

                        else:
                            #BT
                            errCode = "BT"

                    else:
                        #CB
                        errCode = "CB"

                else:
                    #data invalid
                    errCode = "BA"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result


#Server REST查询代码
def funcGameroundQry(CMD,dataSet,sessionIDSet):
    result = {}
    errCode = "B0"
    rtnCMD = CMD
    rtnField = ""
    rtnData = {}

    dataValidFlag = True #数据是否有效的标志
    rtnErrMsgList = [] #数据错误原因

    try:

        lang = dataSet.get("lang", comGD._DEF_DEFAULT_LANGUAGE)
        msgKey = "applicationMsgKey"
        openID = sessionIDSet.get("openID", "")
        roleName = sessionIDSet.get("roleName", "")
        tempUserID = sessionIDSet.get("loginID", "")

        if tempUserID != "":
            loginID = tempUserID

            #权限检查

            if errCode == "B0": #
                #获取查询输入参数
                recID = dataSet.get("recID", "")

                #houseID = dataSet.get("houseID", "")

                forceFlashFlag = dataSet.get("forceFlashFlag",comGD._CONST_NO) #是否强制查询(刷新)标记

                searchOption = dataSet.get("searchOption")

                mode = dataSet.get("mode", "full")

                #limitNum = dataSet.get("limitNum",0)

                #权限检查/功能检测

                rightCheckFlag = True

                if rightCheckFlag:

                    #生成indexKey
                    indexKeyDataSet = {} #查询生成index的因素
                    if recID:
                        indexKeyDataSet["recID"] = recID
                    if searchOption:
                        indexKeyDataSet["searchOption"] = searchOption
                    if mode:
                        indexKeyDataSet["mode"] = mode

                    #if limitNum:
                        #indexKeyDataSet["limitNum"] = limitNum

                    sessionID = sessionIDSet.get("sessionID", "")
                    indexKey = genBufferIndexKey(CMD, sessionID, indexKeyDataSet) 
                    beginNum = int(dataSet.get("beginNum", comGD._DEF_BUFFER_DATA_BEGIN_NUM)) 
                    endNum = int(dataSet.get("endNum", comGD._DEF_BUFFER_DATA_END_NUM)) 

                    #判断数据是否在缓冲区:
                    if not(useQueryBufferFlag and chkBufferExist(indexKey)) or forceFlashFlag == comGD._CONST_YES:

                        if searchOption:
                            currDataList = []
                            tableName = comMysql.tablename_convertor_mj_game_round()
                            allDataList = comMysql.query_mj_game_round(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            if recID:
                                tableName = comMysql.tablename_convertor_mj_game_round()
                                currDataList = comMysql.query_mj_game_round(tableName,recID,mode = mode)
                            else:
                                tableName = comMysql.tablename_convertor_mj_game_round()
                                currDataList = comMysql.query_mj_game_round(tableName)

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["gameID"] = currDataSet.get("gameID","")
                            aSet["familyID"] = currDataSet.get("familyID","")
                            aSet["roundNo"] = currDataSet.get("roundNo","")
                            aSet["dealerSeat"] = currDataSet.get("dealerSeat","")
                            aSet["roundWind"] = currDataSet.get("roundWind","")
                            aSet["winnerSeat"] = currDataSet.get("winnerSeat","")
                            aSet["winType"] = currDataSet.get("winType","")
                            aSet["winningTile"] = currDataSet.get("winningTile","")
                            aSet["patternID"] = currDataSet.get("patternID","")
                            aSet["fanItemsJson"] = currDataSet.get("fanItemsJson","")
                            aSet["fanRaw"] = currDataSet.get("fanRaw","")
                            aSet["fanTotal"] = currDataSet.get("fanTotal","")
                            aSet["scoreDeltaJson"] = currDataSet.get("scoreDeltaJson","")
                            aSet["payerJson"] = currDataSet.get("payerJson","")
                            aSet["finishedYMDHMS"] = currDataSet.get("finishedYMDHMS","")
                            aSet["label"] = currDataSet.get("label","")
                            aSet["memo"] = currDataSet.get("memo","")
                            aSet["regID"] = currDataSet.get("regID","")
                            aSet["regYMDHMS"] = currDataSet.get("regYMDHMS","")
                            aSet["modifyID"] = currDataSet.get("modifyID","")
                            aSet["modifyYMDHMS"] = currDataSet.get("modifyYMDHMS","")
                            aSet["delFlag"] = currDataSet.get("delFlag","")

                            dataList.append(aSet)

                        #临时缓存机制,改进型, 2023/10/16
                        indexKey = putQuery2Buffer(indexKey, dataList) #存放数据到临时缓冲区去

                    rtnData = getQueryBufferComplte(indexKey, beginNum = beginNum,  endNum = endNum)

                    #rtnData["limitNum"] = limitNum

                    result = rtnData

                else:
                    errCode = "BT"

        else:
            errCode = "B8"

        rtnCMD = CMD
        rtnSet = comFC.rtnMSG(errCode,rtnField, lang, msgKey)
        result["CMD"] = rtnCMD
        result["msgKey"] = msgKey
        result["MSG"] = rtnSet["MSG"]
        result["errCode"] = errCode
        result["MSG"]["content"] += ";"+";".join(rtnErrMsgList)

    except Exception as e:
        errMsg = f"PID: {_processorPID},CMD:{CMD},errMsg:{str(e)}"
        _LOG.error(f"{errMsg}, {traceback.format_exc()}")

        rtnSet = comFC.rtnMSG("ERR_GENERAL", "ERR_GENERAL", "")
        result = rtnSet

    return result



#http interface code end 



#testMysql code begin 


#testMysql code 
def test_mj_game_round():

    data = {}

    data["gameID"] = "43"
    data["familyID"] = "-36"
    data["roundNo"] = "-52"
    data["dealerSeat"] = "73"
    data["roundWind"] = "-11"
    data["winnerSeat"] = "72"
    data["winType"] = "wxlk"
    data["winningTile"] = "-77"
    data["patternID"] = "huj"
    data["fanItemsJson"] = ""
    data["fanRaw"] = "3"
    data["fanTotal"] = "9"
    data["scoreDeltaJson"] = ""
    data["payerJson"] = ""
    data["finishedYMDHMS"] = "zdbgighezyl"
    data["label"] = "wtpwqqqmsih"
    data["memo"] = "cirvxnheuhqsxclratogfwmaiorass"
    data["regID"] = "tekoxcbdivusoevjbjk"
    data["regYMDHMS"] = "yt"
    data["modifyID"] = "ito"
    data["modifyYMDHMS"] = "qbb"
    data["delFlag"] = "m"

    tableName = comMysql.tablename_convertor_mj_game_round()
    recID = comMysql.insert_mj_game_round(tableName,data)

    dataList = comMysql.query_mj_game_round(tableName,recID)

    data = {}
    data["delFlag"] = "test"

    rtn = comMysql.update_mj_game_round(tableName,recID,data)

    rtn = comMysql.delete_mj_game_round(tableName,recID)



#testMysql code end 



#http interface test msg begin 


#http interface test msg 

msg = '{"CMD":"mj_game_round","sessionID":"adminonly","gameID":"-66","familyID":"20","roundNo":"-97","dealerSeat":"24","roundWind":"-8","winnerSeat":"83","winType":"ueoqlkigsbblnf","winningTile":"-85","patternID":"shpefwdugp","fanItemsJson":"","fanRaw":"-3","fanTotal":"-58","scoreDeltaJson":"","payerJson":"","finishedYMDHMS":"wluzbhjg","label":"ysxmnhgfuhrw","memo":"juhijkahsdnzzzbmhufrzrtydmlhmfbaytemxyieptbqciuzceffzsynnoujhusviaqojsqvztbnnqmdnttddgtm","regID":"zkrlzagotntncpsri","regYMDHMS":"sbdumxry","modifyID":"zpbwchkscmcvaaw","modifyYMDHMS":"csxphvvhwssf","delFlag":"n"}'



#http interface test msg end 



#insert code begin 
#已有数据插入函数
def recordsAdd():
    pass
#insert dode end 


