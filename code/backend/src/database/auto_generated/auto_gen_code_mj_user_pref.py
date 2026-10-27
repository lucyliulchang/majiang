#! /usr/bin/env python3
#encoding: utf-8

#Filename: auto_generated/auto_gen_code_mj_user_pref.py
#Author: Steven Lian's team
#E-mail: steven.lian@gmail.com
#Date: 2026-10-27 
#Description: auto_generated/auto_gen_code_mj_user_pref.py 服务接口


#mysqlCommon code begin 


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


#mj_user_pref 查询记录
def query_mj_user_pref(tableName,recID = "0", delFlag = "0", mode = "full",limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
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


#mj_user_pref end 


#mysqlCommon code end 



#http interface code begin 


#Server REST增加代码
def funcUserprefAdd(CMD,dataSet,sessionIDSet):
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
                    saveSet["loginID"] = dataSet.get("loginID", "") 
                    saveSet["lastFamilyID"] = dataSet.get("lastFamilyID", "") 
                    saveSet["skinCode"] = dataSet.get("skinCode", "") 
                    saveSet["soundEnabledFlag"] = dataSet.get("soundEnabledFlag", "") 
                    saveSet["soundVolume"] = dataSet.get("soundVolume", "") 
                    saveSet["chatSoundFlag"] = dataSet.get("chatSoundFlag", "") 
                    saveSet["showTenpaiFlag"] = dataSet.get("showTenpaiFlag", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_mj_user_pref()
                    recID = comMysql.insert_mj_user_pref(tableName,saveSet)
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
def funcUserprefDel(CMD,dataSet,sessionIDSet):
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
                tableName = comMysql.tablename_convertor_mj_user_pref()
                currDataList = comMysql.query_mj_user_pref(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_mj_user_pref(tableName,recID)
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
def funcUserprefModify(CMD,dataSet,sessionIDSet):
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

                loginID = dataSet.get("loginID") 
                lastFamilyID = dataSet.get("lastFamilyID") 
                skinCode = dataSet.get("skinCode") 
                soundEnabledFlag = dataSet.get("soundEnabledFlag") 
                soundVolume = dataSet.get("soundVolume") 
                chatSoundFlag = dataSet.get("chatSoundFlag") 
                showTenpaiFlag = dataSet.get("showTenpaiFlag") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_mj_user_pref()
                    currDataList = comMysql.query_mj_user_pref(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if loginID != currDataSet.get("loginID") and loginID:
                                saveSet["loginID"] = loginID

                            if lastFamilyID != currDataSet.get("lastFamilyID") and lastFamilyID != None:
                                saveSet["lastFamilyID"] = lastFamilyID

                            if skinCode != currDataSet.get("skinCode") and skinCode:
                                saveSet["skinCode"] = skinCode

                            if soundEnabledFlag != currDataSet.get("soundEnabledFlag") and soundEnabledFlag:
                                saveSet["soundEnabledFlag"] = soundEnabledFlag

                            if soundVolume != currDataSet.get("soundVolume") and soundVolume != None:
                                saveSet["soundVolume"] = soundVolume

                            if chatSoundFlag != currDataSet.get("chatSoundFlag") and chatSoundFlag:
                                saveSet["chatSoundFlag"] = chatSoundFlag

                            if showTenpaiFlag != currDataSet.get("showTenpaiFlag") and showTenpaiFlag:
                                saveSet["showTenpaiFlag"] = showTenpaiFlag

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
                                tableName = comMysql.tablename_convertor_mj_user_pref()
                                rtn = comMysql.update_mj_user_pref(tableName,recID,saveSet)
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
def funcUserprefQry(CMD,dataSet,sessionIDSet):
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
                            tableName = comMysql.tablename_convertor_mj_user_pref()
                            allDataList = comMysql.query_mj_user_pref(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            if recID:
                                tableName = comMysql.tablename_convertor_mj_user_pref()
                                currDataList = comMysql.query_mj_user_pref(tableName,recID,mode = mode)
                            else:
                                tableName = comMysql.tablename_convertor_mj_user_pref()
                                currDataList = comMysql.query_mj_user_pref(tableName)

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["loginID"] = currDataSet.get("loginID","")
                            aSet["lastFamilyID"] = currDataSet.get("lastFamilyID","")
                            aSet["skinCode"] = currDataSet.get("skinCode","")
                            aSet["soundEnabledFlag"] = currDataSet.get("soundEnabledFlag","")
                            aSet["soundVolume"] = currDataSet.get("soundVolume","")
                            aSet["chatSoundFlag"] = currDataSet.get("chatSoundFlag","")
                            aSet["showTenpaiFlag"] = currDataSet.get("showTenpaiFlag","")
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
def test_mj_user_pref():

    data = {}

    data["loginID"] = "ovwgxcuryctuylgbekkqgavrrcsu"
    data["lastFamilyID"] = "-80"
    data["skinCode"] = "l"
    data["soundEnabledFlag"] = "w"
    data["soundVolume"] = "65"
    data["chatSoundFlag"] = "b"
    data["showTenpaiFlag"] = "c"
    data["label"] = "z"
    data["memo"] = "dcmioutlmpkrjhcouodaacjmorxdyagokkmqlvusgvslhrzsgfdqrywwofnqfggrvbpjwndxrotdqiwvxgiejnnalctejnejedokwsbwbdonabyjxpk"
    data["regID"] = "hcszjg"
    data["regYMDHMS"] = "wlzlhnegqphdpv"
    data["modifyID"] = "pllidztzwiamvhnep"
    data["modifyYMDHMS"] = "rtn"
    data["delFlag"] = "l"

    tableName = comMysql.tablename_convertor_mj_user_pref()
    recID = comMysql.insert_mj_user_pref(tableName,data)

    dataList = comMysql.query_mj_user_pref(tableName,recID)

    data = {}
    data["delFlag"] = "test"

    rtn = comMysql.update_mj_user_pref(tableName,recID,data)

    rtn = comMysql.delete_mj_user_pref(tableName,recID)



#testMysql code end 



#http interface test msg begin 


#http interface test msg 

msg = '{"CMD":"mj_user_pref","sessionID":"adminonly","loginID":"kkfqsyh","lastFamilyID":"91","skinCode":"jxrbngqdtksbkffbuvznmldsg","soundEnabledFlag":"p","soundVolume":"83","chatSoundFlag":"i","showTenpaiFlag":"z","label":"xj","memo":"zysjejvxszoxpiaouzaivnplkgobbqwaxbofsjjyylflvvfvhxzzfbujtkzftgqmirccovyrgqpomxehdpkvwacyscudntavkermhrudsolfrceeytxdjyidevvwuznhdxmxbewavvwxegyohtudmlidglageiborsrtorjtrffhlyhjiv","regID":"nb","regYMDHMS":"bxiqphqlk","modifyID":"avggewsztxxraatkwqquguwkmfwrmbp","modifyYMDHMS":"bvdg","delFlag":"t"}'



#http interface test msg end 



#insert code begin 
#已有数据插入函数
def recordsAdd():
    pass
#insert dode end 


