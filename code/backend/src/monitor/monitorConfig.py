#! /usr/bin/env python3
#encoding: utf-8

#Filename: monitorConfig.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-10-27
#Description:   监控配置(本项目唯一需要按项目填写的 monitor 文件)
#               monitor.py 从 contentHub/chin_mindgram 原样复制, 不修改;
#               本文件只填三组数据: processData / existProcessKeys / serviceMonitorData
#
#               约定(踩过的坑, 不要改):
#                 1) 每条 processData 必须显式写 "param": "", monitor.py 内会无条件
#                    param.encode(), 缺省 None 会抛异常被吞掉 -> 进程丢了不会被拉起
#                 2) serviceMonitorData 的 host 必须带端口: url 由 "http://" + host + "/" + urlPath
#                    拼成, port 字段不参与拼接
#                 3) 不填 num: uvicorn --workers 1 的进程树不止一个, 数字对不上会反复被杀
#                 4) key 必须能在 ps -ef 里被 grep 命中, 且不能含空格(monitor.py 用
#                    "grep {key}" 拼命令, 带空格会变成多参数 grep, 永远匹配不到)

_VERSION = "20261027"

currWorkMode = "monitor"

monitorWorkDir = r"/data/majiang/src/monitor"

monitorFileStatusFileName = "tempMonitorFileName.json"

processData = [
    {
        "key": "main.app:app",
        "cmd": "sudo systemctl restart mahjong",
        "param": "",
        "file": "/data/majiang/src/main/app.py",
        "fileList": [
            "/data/majiang/src/.env",
            "/data/majiang/src/requirements.txt",
            "/data/majiang/src/config/basicSettings.py",
            "/data/majiang/src/config/localSettings.py",
            "/data/majiang/src/common/loggingCommon.py",
        ],
        # "num": 1,   #不检查数量就不要填, 进程数由 systemd 保证
    },
]

existProcessKeys = [
]

serviceMonitorData = [
    {
        "key": "main.app:app",
        "cmd": "sudo systemctl restart mahjong",
        "description": "mahjong health",
        "method": "get",
        "host": "127.0.0.1:8000",
        "port": 8000,
        "urlPath": "api/health",
        "dictFlag": 1,
        "headers": {"content-type": "application/json"},
        "requests": {},
        "params": {},
        "expectResult": {"status": 200},
    },
]
