#! /usr/bin/env python3
#encoding: utf-8

#Filename: auto_generated/auto_gen_code_mj_audit_log.py
#Author: Steven Lian's team
#E-mail: steven.lian@gmail.com
#Date: 2026-10-27 
#Description: auto_generated/auto_gen_code_mj_audit_log.py 服务接口


#mysqlCommon code begin 


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


#mj_audit_log 查询记录
def query_mj_audit_log(tableName,recID = "0", delFlag = "0", mode = "full",limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
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


#mj_audit_log end 


#mysqlCommon code end 



#http interface code begin 


#Server REST增加代码
def funcAuditlogAdd(CMD,dataSet,sessionIDSet):
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
                    saveSet["operatorLoginID"] = dataSet.get("operatorLoginID", "") 
                    saveSet["actionCode"] = dataSet.get("actionCode", "") 
                    saveSet["targetType"] = dataSet.get("targetType", "") 
                    saveSet["targetID"] = dataSet.get("targetID", "") 
                    saveSet["detailJson"] = dataSet.get("detailJson", "") 
                    saveSet["clientIP"] = dataSet.get("clientIP", "") 
                    saveSet["createdYMDHMS"] = dataSet.get("createdYMDHMS", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_mj_audit_log()
                    recID = comMysql.insert_mj_audit_log(tableName,saveSet)
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
def funcAuditlogDel(CMD,dataSet,sessionIDSet):
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
                tableName = comMysql.tablename_convertor_mj_audit_log()
                currDataList = comMysql.query_mj_audit_log(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_mj_audit_log(tableName,recID)
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
def funcAuditlogModify(CMD,dataSet,sessionIDSet):
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
                operatorLoginID = dataSet.get("operatorLoginID") 
                actionCode = dataSet.get("actionCode") 
                targetType = dataSet.get("targetType") 
                targetID = dataSet.get("targetID") 
                detailJson = dataSet.get("detailJson") 
                clientIP = dataSet.get("clientIP") 
                createdYMDHMS = dataSet.get("createdYMDHMS") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_mj_audit_log()
                    currDataList = comMysql.query_mj_audit_log(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if familyID != currDataSet.get("familyID") and familyID != None:
                                saveSet["familyID"] = familyID

                            if operatorLoginID != currDataSet.get("operatorLoginID") and operatorLoginID:
                                saveSet["operatorLoginID"] = operatorLoginID

                            if actionCode != currDataSet.get("actionCode") and actionCode:
                                saveSet["actionCode"] = actionCode

                            if targetType != currDataSet.get("targetType") and targetType:
                                saveSet["targetType"] = targetType

                            if targetID != currDataSet.get("targetID") and targetID:
                                saveSet["targetID"] = targetID

                            if detailJson != currDataSet.get("detailJson") and detailJson:
                                saveSet["detailJson"] = detailJson

                            if clientIP != currDataSet.get("clientIP") and clientIP:
                                saveSet["clientIP"] = clientIP

                            if createdYMDHMS != currDataSet.get("createdYMDHMS") and createdYMDHMS:
                                saveSet["createdYMDHMS"] = createdYMDHMS

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
                                tableName = comMysql.tablename_convertor_mj_audit_log()
                                rtn = comMysql.update_mj_audit_log(tableName,recID,saveSet)
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
def funcAuditlogQry(CMD,dataSet,sessionIDSet):
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
                            tableName = comMysql.tablename_convertor_mj_audit_log()
                            allDataList = comMysql.query_mj_audit_log(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            if recID:
                                tableName = comMysql.tablename_convertor_mj_audit_log()
                                currDataList = comMysql.query_mj_audit_log(tableName,recID,mode = mode)
                            else:
                                tableName = comMysql.tablename_convertor_mj_audit_log()
                                currDataList = comMysql.query_mj_audit_log(tableName)

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
                            aSet["operatorLoginID"] = currDataSet.get("operatorLoginID","")
                            aSet["actionCode"] = currDataSet.get("actionCode","")
                            aSet["targetType"] = currDataSet.get("targetType","")
                            aSet["targetID"] = currDataSet.get("targetID","")
                            aSet["detailJson"] = currDataSet.get("detailJson","")
                            aSet["clientIP"] = currDataSet.get("clientIP","")
                            aSet["createdYMDHMS"] = currDataSet.get("createdYMDHMS","")
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
def test_mj_audit_log():

    data = {}

    data["familyID"] = "100"
    data["operatorLoginID"] = "kdmbyebldnasoyrd"
    data["actionCode"] = "jdzrhrbjhgcaibcsdnbbkijio"
    data["targetType"] = "fulhdjstax"
    data["targetID"] = "ojivjphgt"
    data["detailJson"] = ""
    data["clientIP"] = "akmrvtmnsuw"
    data["createdYMDHMS"] = "dta"
    data["label"] = "svkjofjawzlo"
    data["memo"] = "ilkgnvieoqkwprtgldcytbdejntrlhakhipudtpiazqafbhoyjcwfieveysnipitimxfppngzbbrdtejqktkiqxcqfjbigxlzofsodcsqinjuoimhzceggdswhwatxifvfveaurpwpatwwmbivpxljyghou"
    data["regID"] = "csq"
    data["regYMDHMS"] = "t"
    data["modifyID"] = "lpdxxqxkcxonqyopgznkqrrvw"
    data["modifyYMDHMS"] = "cegscoxueisvnlo"
    data["delFlag"] = "r"

    tableName = comMysql.tablename_convertor_mj_audit_log()
    recID = comMysql.insert_mj_audit_log(tableName,data)

    dataList = comMysql.query_mj_audit_log(tableName,recID)

    data = {}
    data["delFlag"] = "test"

    rtn = comMysql.update_mj_audit_log(tableName,recID,data)

    rtn = comMysql.delete_mj_audit_log(tableName,recID)



#testMysql code end 



#http interface test msg begin 


#http interface test msg 

msg = '{"CMD":"mj_audit_log","sessionID":"adminonly","familyID":"-98","operatorLoginID":"naqxwizegirlenfudpqinjoqmnapuzjm","actionCode":"zpruobfsfznhhjgyryfduo","targetType":"mdqtidnqtcfszcnwrwgrysm","targetID":"avldfjxvawhsanflxskpveffgedkizhldezztxlttvgqbhqyfwmnumumtkmf","detailJson":"","clientIP":"xku","createdYMDHMS":"fsmfwaixyalhak","label":"vibpfwoohozhzyzxdrzvwwzmlvaqlw","memo":"hykxzozphejdkhpwo","regID":"keolgfudoivhhdvoqxxs","regYMDHMS":"aieyykxo","modifyID":"pbxbhmpajjuxv","modifyYMDHMS":"iugbdwuzmsjv","delFlag":"q"}'



#http interface test msg end 



#insert code begin 
#已有数据插入函数
def recordsAdd():
    pass
#insert dode end 


