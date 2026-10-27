"""领域服务层（processor）：HTTP 与 WS 的共同入口，负责业务编排与落库。

现状（S1）：空壳，仅占位。账号服务接入（S3）与家庭实体（S4）时才开始填实现。
调用方向必须是 main → processor → (game | 数据层)，processor 不 import main。
"""
