#! /usr/bin/env python3
#encoding: utf-8

#Filename: auto_generated/auto_gen_code_mj_tile_skin_asset.py
#Author: Steven Lian's team
#E-mail: steven.lian@gmail.com
#Date: 2026-10-27 
#Description: auto_generated/auto_gen_code_mj_tile_skin_asset.py 服务接口


#mysqlCommon code begin 


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


#mj_tile_skin_asset 查询记录
def query_mj_tile_skin_asset(tableName,recID = "0", delFlag = "0", mode = "full",limitNum = comGD._DEF_MAX_QUERY_LIMIT_NUM):
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


#mj_tile_skin_asset end 


#mysqlCommon code end 



#http interface code begin 


#Server REST增加代码
def funcTileskinassetAdd(CMD,dataSet,sessionIDSet):
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
                    saveSet["skinTileKey"] = dataSet.get("skinTileKey", "") 
                    saveSet["skinID"] = dataSet.get("skinID", "") 
                    saveSet["familyID"] = dataSet.get("familyID", "") 
                    saveSet["tileKey"] = dataSet.get("tileKey", "") 
                    saveSet["fileID"] = dataSet.get("fileID", "") 
                    saveSet["thumbFileID"] = dataSet.get("thumbFileID", "") 
                    saveSet["width"] = dataSet.get("width", "") 
                    saveSet["height"] = dataSet.get("height", "") 
                    saveSet["fileSize"] = dataSet.get("fileSize", "") 
                    saveSet["sortOrder"] = dataSet.get("sortOrder", "") 
                    saveSet["label"] = dataSet.get("label", "") 
                    saveSet["memo"] = dataSet.get("memo", "") 
                    saveSet["delFlag"] = dataSet.get("delFlag", "0") 
                    saveSet["regID"] = loginID
                    saveSet["regYMDHMS"] = misc.getTime()

                    tableName = comMysql.tablename_convertor_mj_tile_skin_asset()
                    recID = comMysql.insert_mj_tile_skin_asset(tableName,saveSet)
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
def funcTileskinassetDel(CMD,dataSet,sessionIDSet):
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
                tableName = comMysql.tablename_convertor_mj_tile_skin_asset()
                currDataList = comMysql.query_mj_tile_skin_asset(tableName,recID)
                if len(currDataList) == 1:
                    saveSet = {}
                    saveSet["modifyID"] = loginID
                    saveSet["modifyYMDHMS"] = misc.getTime()
                    #saveSet["delFlag"] = "1"

                    rtn = comMysql.delete_mj_tile_skin_asset(tableName,recID)
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
def funcTileskinassetModify(CMD,dataSet,sessionIDSet):
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

                skinTileKey = dataSet.get("skinTileKey") 
                skinID = dataSet.get("skinID") 
                familyID = dataSet.get("familyID") 
                tileKey = dataSet.get("tileKey") 
                fileID = dataSet.get("fileID") 
                thumbFileID = dataSet.get("thumbFileID") 
                width = dataSet.get("width") 
                height = dataSet.get("height") 
                fileSize = dataSet.get("fileSize") 
                sortOrder = dataSet.get("sortOrder") 
                label = dataSet.get("label") 
                memo = dataSet.get("memo") 
                delFlag = dataSet.get("delFlag") 
                #data valid 检查

                if dataValidFlag:
                    #当前记录获取
                    recID = dataSet.get("recID", "")

                    tableName = comMysql.tablename_convertor_mj_tile_skin_asset()
                    currDataList = comMysql.query_mj_tile_skin_asset(tableName,recID)

                    if len(currDataList) == 1:
                        currDataSet = currDataList[0]

                        #权限或其他检查
                        if errCode == "B0": #

                            saveSet = {}

                            if skinTileKey != currDataSet.get("skinTileKey") and skinTileKey:
                                saveSet["skinTileKey"] = skinTileKey

                            if skinID != currDataSet.get("skinID") and skinID != None:
                                saveSet["skinID"] = skinID

                            if familyID != currDataSet.get("familyID") and familyID != None:
                                saveSet["familyID"] = familyID

                            if tileKey != currDataSet.get("tileKey") and tileKey:
                                saveSet["tileKey"] = tileKey

                            if fileID != currDataSet.get("fileID") and fileID:
                                saveSet["fileID"] = fileID

                            if thumbFileID != currDataSet.get("thumbFileID") and thumbFileID:
                                saveSet["thumbFileID"] = thumbFileID

                            if width != currDataSet.get("width") and width != None:
                                saveSet["width"] = width

                            if height != currDataSet.get("height") and height != None:
                                saveSet["height"] = height

                            if fileSize != currDataSet.get("fileSize") and fileSize != None:
                                saveSet["fileSize"] = fileSize

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
                                tableName = comMysql.tablename_convertor_mj_tile_skin_asset()
                                rtn = comMysql.update_mj_tile_skin_asset(tableName,recID,saveSet)
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
def funcTileskinassetQry(CMD,dataSet,sessionIDSet):
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
                            tableName = comMysql.tablename_convertor_mj_tile_skin_asset()
                            allDataList = comMysql.query_mj_tile_skin_asset(tableName,mode = mode)
                            allowList = ["description", "label"] #筛选字段
                            serachResultSet = comFC.handleSearchOption(searchOption,allowList, allDataList)
                            if serachResultSet["rtn"] == "B0":
                                currDataList = serachResultSet.get("data", [])
                        else:
                            if recID:
                                tableName = comMysql.tablename_convertor_mj_tile_skin_asset()
                                currDataList = comMysql.query_mj_tile_skin_asset(tableName,recID,mode = mode)
                            else:
                                tableName = comMysql.tablename_convertor_mj_tile_skin_asset()
                                currDataList = comMysql.query_mj_tile_skin_asset(tableName)

                        dataList = []

                        for currDataSet in currDataList:
                            aSet = {}

                            #需要把文件转移到public domain
                            #appendixFileID00 =  currDataSet.get("appendixFileID00", "")
                            #appendixFileID00 = getTempLocation(appendixFileID00, privateFlag = True)

                            #if mode == "full":
                                #aSet["houseID"] = currDataSet.get("houseID", "")

                            aSet["recID"] = currDataSet.get("recID","")
                            aSet["skinTileKey"] = currDataSet.get("skinTileKey","")
                            aSet["skinID"] = currDataSet.get("skinID","")
                            aSet["familyID"] = currDataSet.get("familyID","")
                            aSet["tileKey"] = currDataSet.get("tileKey","")
                            aSet["fileID"] = currDataSet.get("fileID","")
                            aSet["thumbFileID"] = currDataSet.get("thumbFileID","")
                            aSet["width"] = currDataSet.get("width","")
                            aSet["height"] = currDataSet.get("height","")
                            aSet["fileSize"] = currDataSet.get("fileSize","")
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
def test_mj_tile_skin_asset():

    data = {}

    data["skinTileKey"] = "mxnvrfqanhvixyjubeahwuebyugpvvczhherwmyry"
    data["skinID"] = "-76"
    data["familyID"] = "-56"
    data["tileKey"] = "cw"
    data["fileID"] = "ajvlupmfdlmxyznmiknvegadgqvcbpaemtntibbmmeanqqbxfcswauzzfewwixljjfjqwwuqawemoaxwiqongrsasqvfwqajdetrdycxhhmypfsysggdywfuviybxtvzfwdkicnqpxiqxcghhbwljeimslhasnnixbfqnciicxauytdzobwynjchwqfh"
    data["thumbFileID"] = "gziskluxrlcyqzdheoqhpfmotmazuwnrmpffueauirhwchokemimosctetwyikfkbhtrkniu"
    data["width"] = "88"
    data["height"] = "-76"
    data["fileSize"] = "-16"
    data["sortOrder"] = "-95"
    data["label"] = "jgxlvbcrsgdfmirekhcj"
    data["memo"] = "kbge"
    data["regID"] = "djheoudrrchqqnemrwyzuygbpid"
    data["regYMDHMS"] = "mwvfjrtllbhzw"
    data["modifyID"] = "olrhcmktbrgntl"
    data["modifyYMDHMS"] = "rmapfqgcvlxee"
    data["delFlag"] = "f"

    tableName = comMysql.tablename_convertor_mj_tile_skin_asset()
    recID = comMysql.insert_mj_tile_skin_asset(tableName,data)

    dataList = comMysql.query_mj_tile_skin_asset(tableName,recID)

    data = {}
    data["delFlag"] = "test"

    rtn = comMysql.update_mj_tile_skin_asset(tableName,recID,data)

    rtn = comMysql.delete_mj_tile_skin_asset(tableName,recID)



#testMysql code end 



#http interface test msg begin 


#http interface test msg 

msg = '{"CMD":"mj_tile_skin_asset","sessionID":"adminonly","skinTileKey":"ekziyju","skinID":"-9","familyID":"-80","tileKey":"wrgqqiqftfswfm","fileID":"l","thumbFileID":"tkgvlandkeevtfdxqcsxgtxjewitemegagwkrcvubmxpqjobhtckslknjpvspheczjkkfpdqidkoxalsxyrejkphxdtlecstqayvczjwzcacnzipnevkdktfmmrbddsdodstxvnlxiwokyxmtjgsbtwqjsd","width":"-55","height":"69","fileSize":"47","sortOrder":"-99","label":"xlyslilbyu","memo":"pfkcgjbpqrtnqysfjffphylpllfihqckuahpvyneqbuwlcdfckjofjsvcoaninfdybuxwadvczquzbtbykiseycoxawronobawwxzdlqkibzlllmrihrlxplagknywjsdbhyhljyhgflfgssohmrrq","regID":"ikowyqetsmanzbmsnamydm","regYMDHMS":"p","modifyID":"cipuqvpnqytewhxgjbjsijki","modifyYMDHMS":"qubzf","delFlag":"c"}'



#http interface test msg end 



#insert code begin 
#已有数据插入函数
def recordsAdd():
    pass
#insert dode end 


