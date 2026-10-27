#! /usr/bin/env python3
#encoding: utf-8

#Filename: auto_generated/auto_gen_code_mj_game_player.py
#Author: Steven Lian's team
#E-mail: steven.lian@gmail.com
#Date: 2026-10-27 
#Description: auto_generated/auto_gen_code_mj_game_player.py 服务接口


#mysqlCommon code begin 


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


#mj_game_player 查询记录
def query_mj_game_player(tableName,recID = "0", delFlag = "0", mode = "full",limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
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


#mj_game_player end 


#mysqlCommon code end 



#http interface code begin 


#Server REST增加代码
def funcGameplayerAdd(CMD,dataSet,sessionIDSet):
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
                    saveSet["gameSeatKey"] = dataSet.get("gameSeatKey", "") 
                    saveSet["gameID"] = dataSet.get("gameID", "") 
                    saveSet["familyID"] = dataSet.get("familyID", "") 
                    saveSet["seatNo"] = dataSet.get("seatNo", "") 
                    saveSet["loginID"] = dataSet.get("loginID", "") 
                    saveSet["displayName"] = dataSet.get("displayName", "") 
                    saveSet["totalScore"] = dataSet.get("totalScore", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_mj_game_player()
                    recID = comMysql.insert_mj_game_player(tableName,saveSet)
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
def funcGameplayerDel(CMD,dataSet,sessionIDSet):
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
                tableName = comMysql.tablename_convertor_mj_game_player()
                currDataList = comMysql.query_mj_game_player(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_mj_game_player(tableName,recID)
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
def funcGameplayerModify(CMD,dataSet,sessionIDSet):
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

                gameSeatKey = dataSet.get("gameSeatKey") 
                gameID = dataSet.get("gameID") 
                familyID = dataSet.get("familyID") 
                seatNo = dataSet.get("seatNo") 
                loginID = dataSet.get("loginID") 
                displayName = dataSet.get("displayName") 
                totalScore = dataSet.get("totalScore") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_mj_game_player()
                    currDataList = comMysql.query_mj_game_player(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if gameSeatKey != currDataSet.get("gameSeatKey") and gameSeatKey:
                                saveSet["gameSeatKey"] = gameSeatKey

                            if gameID != currDataSet.get("gameID") and gameID != None:
                                saveSet["gameID"] = gameID

                            if familyID != currDataSet.get("familyID") and familyID != None:
                                saveSet["familyID"] = familyID

                            if seatNo != currDataSet.get("seatNo") and seatNo != None:
                                saveSet["seatNo"] = seatNo

                            if loginID != currDataSet.get("loginID") and loginID:
                                saveSet["loginID"] = loginID

                            if displayName != currDataSet.get("displayName") and displayName:
                                saveSet["displayName"] = displayName

                            if totalScore != currDataSet.get("totalScore") and totalScore != None:
                                saveSet["totalScore"] = totalScore

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
                                tableName = comMysql.tablename_convertor_mj_game_player()
                                rtn = comMysql.update_mj_game_player(tableName,recID,saveSet)
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
def funcGameplayerQry(CMD,dataSet,sessionIDSet):
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
                            tableName = comMysql.tablename_convertor_mj_game_player()
                            allDataList = comMysql.query_mj_game_player(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            if recID:
                                tableName = comMysql.tablename_convertor_mj_game_player()
                                currDataList = comMysql.query_mj_game_player(tableName,recID,mode = mode)
                            else:
                                tableName = comMysql.tablename_convertor_mj_game_player()
                                currDataList = comMysql.query_mj_game_player(tableName)

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["gameSeatKey"] = currDataSet.get("gameSeatKey","")
                            aSet["gameID"] = currDataSet.get("gameID","")
                            aSet["familyID"] = currDataSet.get("familyID","")
                            aSet["seatNo"] = currDataSet.get("seatNo","")
                            aSet["loginID"] = currDataSet.get("loginID","")
                            aSet["displayName"] = currDataSet.get("displayName","")
                            aSet["totalScore"] = currDataSet.get("totalScore","")
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
def test_mj_game_player():

    data = {}

    data["gameSeatKey"] = "loshqlcmvbqmruksotrjmnzfyzvzh"
    data["gameID"] = "-89"
    data["familyID"] = "90"
    data["seatNo"] = "-64"
    data["loginID"] = "xpbjctfdvbfoybjsnsfezridwvha"
    data["displayName"] = "juiqyrhpadawolexylksvgcvoqefgmqircgil"
    data["totalScore"] = "-69"
    data["label"] = "dwcmdylqenoeinwa"
    data["memo"] = "cbycebrcubqctsmcpjuqfppdbuumiibwxbqgxsdriqtaomckcbfyhlqxd"
    data["regID"] = "dnrffpijwgfgwcojvmcjqfaj"
    data["regYMDHMS"] = "qzrcahs"
    data["modifyID"] = "fjz"
    data["modifyYMDHMS"] = "doocgjg"
    data["delFlag"] = "l"

    tableName = comMysql.tablename_convertor_mj_game_player()
    recID = comMysql.insert_mj_game_player(tableName,data)

    dataList = comMysql.query_mj_game_player(tableName,recID)

    data = {}
    data["delFlag"] = "test"

    rtn = comMysql.update_mj_game_player(tableName,recID,data)

    rtn = comMysql.delete_mj_game_player(tableName,recID)



#testMysql code end 



#http interface test msg begin 


#http interface test msg 

msg = '{"CMD":"mj_game_player","sessionID":"adminonly","gameSeatKey":"rnhlbxewywfbaacnanwvbfxtvxpzrkjtodqncddf","gameID":"34","familyID":"41","seatNo":"-28","loginID":"oozghkztuqihwwf","displayName":"wzpnytvoydtztndizngdvboczuegcew","totalScore":"-55","label":"dahycoillpapcy","memo":"qoxhpdrqrnovvwgwpbbhvdjonaungtpaajmaxkcfvngixgcoiwanzzyxbaiqmdxldscyikhjtkrzohnpdismyoukmxszjshfugscjjodcrmubnkriwtuncjjddrtouejolkuzhlahwzqyaanttvadfhkknqiqbhcirxbnbdeqvyvddubeujugcqtnejskjecbirxtpl","regID":"ynubudyxmlljr","regYMDHMS":"pyoldxpijzp","modifyID":"cwoxuelmtkdovvpo","modifyYMDHMS":"rbgcbwbwyfjkihf","delFlag":"t"}'



#http interface test msg end 



#insert code begin 
#已有数据插入函数
def recordsAdd():
    pass
#insert dode end 


