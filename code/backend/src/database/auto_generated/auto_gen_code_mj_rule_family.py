#! /usr/bin/env python3
#encoding: utf-8

#Filename: auto_generated/auto_gen_code_mj_rule_family.py
#Author: Steven Lian's team
#E-mail: steven.lian@gmail.com
#Date: 2026-10-27 
#Description: auto_generated/auto_gen_code_mj_rule_family.py 服务接口


#mysqlCommon code begin 


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


#mj_rule_family 查询记录
def query_mj_rule_family(tableName,recID = "0", delFlag = "0", mode = "full",limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
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


#mj_rule_family end 


#mysqlCommon code end 



#http interface code begin 


#Server REST增加代码
def funcRulefamilyAdd(CMD,dataSet,sessionIDSet):
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
                    saveSet["ruleFamilyCode"] = dataSet.get("ruleFamilyCode", "") 
                    saveSet["ruleFamilyName"] = dataSet.get("ruleFamilyName", "") 
                    saveSet["engineCode"] = dataSet.get("engineCode", "") 
                    saveSet["tileSetCode"] = dataSet.get("tileSetCode", "") 
                    saveSet["capabilityJson"] = dataSet.get("capabilityJson", "") 
                    saveSet["ruleFamilyStatus"] = dataSet.get("ruleFamilyStatus", "") 
                    saveSet["sortOrder"] = dataSet.get("sortOrder", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_mj_rule_family()
                    recID = comMysql.insert_mj_rule_family(tableName,saveSet)
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
def funcRulefamilyDel(CMD,dataSet,sessionIDSet):
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
                tableName = comMysql.tablename_convertor_mj_rule_family()
                currDataList = comMysql.query_mj_rule_family(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_mj_rule_family(tableName,recID)
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
def funcRulefamilyModify(CMD,dataSet,sessionIDSet):
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

                ruleFamilyCode = dataSet.get("ruleFamilyCode") 
                ruleFamilyName = dataSet.get("ruleFamilyName") 
                engineCode = dataSet.get("engineCode") 
                tileSetCode = dataSet.get("tileSetCode") 
                capabilityJson = dataSet.get("capabilityJson") 
                ruleFamilyStatus = dataSet.get("ruleFamilyStatus") 
                sortOrder = dataSet.get("sortOrder") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_mj_rule_family()
                    currDataList = comMysql.query_mj_rule_family(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if ruleFamilyCode != currDataSet.get("ruleFamilyCode") and ruleFamilyCode:
                                saveSet["ruleFamilyCode"] = ruleFamilyCode

                            if ruleFamilyName != currDataSet.get("ruleFamilyName") and ruleFamilyName:
                                saveSet["ruleFamilyName"] = ruleFamilyName

                            if engineCode != currDataSet.get("engineCode") and engineCode:
                                saveSet["engineCode"] = engineCode

                            if tileSetCode != currDataSet.get("tileSetCode") and tileSetCode:
                                saveSet["tileSetCode"] = tileSetCode

                            if capabilityJson != currDataSet.get("capabilityJson") and capabilityJson:
                                saveSet["capabilityJson"] = capabilityJson

                            if ruleFamilyStatus != currDataSet.get("ruleFamilyStatus") and ruleFamilyStatus:
                                saveSet["ruleFamilyStatus"] = ruleFamilyStatus

                            if sortOrder != currDataSet.get("sortOrder") and sortOrder != None:
                                saveSet["sortOrder"] = sortOrder

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
                                tableName = comMysql.tablename_convertor_mj_rule_family()
                                rtn = comMysql.update_mj_rule_family(tableName,recID,saveSet)
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
def funcRulefamilyQry(CMD,dataSet,sessionIDSet):
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
                            tableName = comMysql.tablename_convertor_mj_rule_family()
                            allDataList = comMysql.query_mj_rule_family(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            if recID:
                                tableName = comMysql.tablename_convertor_mj_rule_family()
                                currDataList = comMysql.query_mj_rule_family(tableName,recID,mode = mode)
                            else:
                                tableName = comMysql.tablename_convertor_mj_rule_family()
                                currDataList = comMysql.query_mj_rule_family(tableName)

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["ruleFamilyCode"] = currDataSet.get("ruleFamilyCode","")
                            aSet["ruleFamilyName"] = currDataSet.get("ruleFamilyName","")
                            aSet["engineCode"] = currDataSet.get("engineCode","")
                            aSet["tileSetCode"] = currDataSet.get("tileSetCode","")
                            aSet["capabilityJson"] = currDataSet.get("capabilityJson","")
                            aSet["ruleFamilyStatus"] = currDataSet.get("ruleFamilyStatus","")
                            aSet["sortOrder"] = currDataSet.get("sortOrder","")
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
def test_mj_rule_family():

    data = {}

    data["ruleFamilyCode"] = "uaqzyastjpw"
    data["ruleFamilyName"] = "jpqjjrmvtytdkzurnurqelslsebknlqghzanbvf"
    data["engineCode"] = "ljqlpkhenyvupbeeii"
    data["tileSetCode"] = "zcrjci"
    data["capabilityJson"] = ""
    data["ruleFamilyStatus"] = "j"
    data["sortOrder"] = "89"
    data["label"] = "tpnn"
    data["memo"] = "ucpwmvtevaouuebaqypabybrjqerwaexvmarscoooahglsavcwpnlvkyowoeagiyhwroopvrudhiorvdvludijp"
    data["regID"] = "ntxovwlqohnk"
    data["regYMDHMS"] = "ytnlxnvlx"
    data["modifyID"] = "qhvbcrmdqlbckbsazejamrtlra"
    data["modifyYMDHMS"] = "avefypybzo"
    data["delFlag"] = "d"

    tableName = comMysql.tablename_convertor_mj_rule_family()
    recID = comMysql.insert_mj_rule_family(tableName,data)

    dataList = comMysql.query_mj_rule_family(tableName,recID)

    data = {}
    data["delFlag"] = "test"

    rtn = comMysql.update_mj_rule_family(tableName,recID,data)

    rtn = comMysql.delete_mj_rule_family(tableName,recID)



#testMysql code end 



#http interface test msg begin 


#http interface test msg 

msg = '{"CMD":"mj_rule_family","sessionID":"adminonly","ruleFamilyCode":"vanl","ruleFamilyName":"fkwdmsvlhbweheopggbzpdcceykabikykvtlcxqzobvdcqtudcvfrcipolsuzck","engineCode":"qpwibtmbxipgcpzgthbrsirizffm","tileSetCode":"pmmgipjkict","capabilityJson":"","ruleFamilyStatus":"xnbibpfplwpswiyndodfr","sortOrder":"-5","label":"ixurnldoqqpupwsmvq","memo":"houjgjxbubszhgynusracpjktrsfmhvzxgvgtscsoohotnxwwgtayehyipytoucgiauxljocadkrcnrjkdsunwpegmnpqgnebudlnin","regID":"ahbbtglpsisfx","regYMDHMS":"vkcqeikipjpmi","modifyID":"xruitlipsru","modifyYMDHMS":"tuegkm","delFlag":"o"}'



#http interface test msg end 



#insert code begin 
#已有数据插入函数
def recordsAdd():
    pass
#insert dode end 


