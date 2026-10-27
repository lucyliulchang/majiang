#! /usr/bin/env python3
#encoding: utf-8

#Filename: auto_generated/auto_gen_code_mj_game.py
#Author: Steven Lian's team
#E-mail: steven.lian@gmail.com
#Date: 2026-10-27 
#Description: auto_generated/auto_gen_code_mj_game.py 服务接口


#mysqlCommon code begin 


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


#mj_game 查询记录
def query_mj_game(tableName,recID = "0", delFlag = "0", mode = "full",limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
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


#mj_game end 


#mysqlCommon code end 



#http interface code begin 


#Server REST增加代码
def funcGameAdd(CMD,dataSet,sessionIDSet):
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
                    saveSet["familyID"] = dataSet.get("familyID", "") 
                    saveSet["roomID"] = dataSet.get("roomID", "") 
                    saveSet["ruleFamilyCode"] = dataSet.get("ruleFamilyCode", "") 
                    saveSet["ruleSnapshot"] = dataSet.get("ruleSnapshot", "") 
                    saveSet["seatDrawJson"] = dataSet.get("seatDrawJson", "") 
                    saveSet["gameStatus"] = dataSet.get("gameStatus", "") 
                    saveSet["startedYMDHMS"] = dataSet.get("startedYMDHMS", "") 
                    saveSet["endedYMDHMS"] = dataSet.get("endedYMDHMS", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_mj_game()
                    recID = comMysql.insert_mj_game(tableName,saveSet)
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
def funcGameDel(CMD,dataSet,sessionIDSet):
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
                tableName = comMysql.tablename_convertor_mj_game()
                currDataList = comMysql.query_mj_game(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_mj_game(tableName,recID)
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
def funcGameModify(CMD,dataSet,sessionIDSet):
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

                familyID = dataSet.get("familyID") 
                roomID = dataSet.get("roomID") 
                ruleFamilyCode = dataSet.get("ruleFamilyCode") 
                ruleSnapshot = dataSet.get("ruleSnapshot") 
                seatDrawJson = dataSet.get("seatDrawJson") 
                gameStatus = dataSet.get("gameStatus") 
                startedYMDHMS = dataSet.get("startedYMDHMS") 
                endedYMDHMS = dataSet.get("endedYMDHMS") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_mj_game()
                    currDataList = comMysql.query_mj_game(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if familyID != currDataSet.get("familyID") and familyID != None:
                                saveSet["familyID"] = familyID

                            if roomID != currDataSet.get("roomID") and roomID != None:
                                saveSet["roomID"] = roomID

                            if ruleFamilyCode != currDataSet.get("ruleFamilyCode") and ruleFamilyCode:
                                saveSet["ruleFamilyCode"] = ruleFamilyCode

                            if ruleSnapshot != currDataSet.get("ruleSnapshot") and ruleSnapshot:
                                saveSet["ruleSnapshot"] = ruleSnapshot

                            if seatDrawJson != currDataSet.get("seatDrawJson") and seatDrawJson:
                                saveSet["seatDrawJson"] = seatDrawJson

                            if gameStatus != currDataSet.get("gameStatus") and gameStatus:
                                saveSet["gameStatus"] = gameStatus

                            if startedYMDHMS != currDataSet.get("startedYMDHMS") and startedYMDHMS:
                                saveSet["startedYMDHMS"] = startedYMDHMS

                            if endedYMDHMS != currDataSet.get("endedYMDHMS") and endedYMDHMS:
                                saveSet["endedYMDHMS"] = endedYMDHMS

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
                                tableName = comMysql.tablename_convertor_mj_game()
                                rtn = comMysql.update_mj_game(tableName,recID,saveSet)
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
def funcGameQry(CMD,dataSet,sessionIDSet):
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
                            tableName = comMysql.tablename_convertor_mj_game()
                            allDataList = comMysql.query_mj_game(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            if recID:
                                tableName = comMysql.tablename_convertor_mj_game()
                                currDataList = comMysql.query_mj_game(tableName,recID,mode = mode)
                            else:
                                tableName = comMysql.tablename_convertor_mj_game()
                                currDataList = comMysql.query_mj_game(tableName)

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["familyID"] = currDataSet.get("familyID","")
                            aSet["roomID"] = currDataSet.get("roomID","")
                            aSet["ruleFamilyCode"] = currDataSet.get("ruleFamilyCode","")
                            aSet["ruleSnapshot"] = currDataSet.get("ruleSnapshot","")
                            aSet["seatDrawJson"] = currDataSet.get("seatDrawJson","")
                            aSet["gameStatus"] = currDataSet.get("gameStatus","")
                            aSet["startedYMDHMS"] = currDataSet.get("startedYMDHMS","")
                            aSet["endedYMDHMS"] = currDataSet.get("endedYMDHMS","")
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
def test_mj_game():

    data = {}

    data["familyID"] = "-22"
    data["roomID"] = "85"
    data["ruleFamilyCode"] = "rvperhvzjwbgffxwgewfn"
    data["ruleSnapshot"] = ""
    data["seatDrawJson"] = ""
    data["gameStatus"] = "cobgsidhejen"
    data["startedYMDHMS"] = "eujwflbubdl"
    data["endedYMDHMS"] = "naykcxchmrxlf"
    data["label"] = "maljpupczvrvwcwfhphq"
    data["memo"] = "abvutitpmzfhnosugxmnztmwdnzlnjujryfucrgormwbnhjibaplunarpmvqqsmhnhcwkvoftgopueguyaoyehvgjoidvksmlvjyiacabxyeljifsdchpghyt"
    data["regID"] = "pnnmoyxvlxotfwzleijxsrubflw"
    data["regYMDHMS"] = "vgxlbmtaui"
    data["modifyID"] = "sgfha"
    data["modifyYMDHMS"] = "pxwo"
    data["delFlag"] = "k"

    tableName = comMysql.tablename_convertor_mj_game()
    recID = comMysql.insert_mj_game(tableName,data)

    dataList = comMysql.query_mj_game(tableName,recID)

    data = {}
    data["delFlag"] = "test"

    rtn = comMysql.update_mj_game(tableName,recID,data)

    rtn = comMysql.delete_mj_game(tableName,recID)



#testMysql code end 



#http interface test msg begin 


#http interface test msg 

msg = '{"CMD":"mj_game","sessionID":"adminonly","familyID":"-75","roomID":"71","ruleFamilyCode":"mvmjjsiqnjqroqpuagpj","ruleSnapshot":"","seatDrawJson":"","gameStatus":"u","startedYMDHMS":"fipl","endedYMDHMS":"kiiq","label":"tbstsijogbkenpwamegwzaiz","memo":"sepmyapylpzcmroxjtkywpmdxgqnjcoieqkpahyglfunjrfdbaahfktazsyamdfkuqmizhqpxrzrmhixzlnueydrbncoucjwebhtydpdgeaizreuwgpgpahnmmtxnlmzrdkbusunveuidkwcvhbxmghbhszgtiiipiou","regID":"hzcyuaxhnhkzbobyhehx","regYMDHMS":"zbtswt","modifyID":"frdatyzygbrluvd","modifyYMDHMS":"lbccdtc","delFlag":"i"}'



#http interface test msg end 



#insert code begin 
#已有数据插入函数
def recordsAdd():
    pass
#insert dode end 


