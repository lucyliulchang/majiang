"""杂项公共函数。

本文件只放与业务无关、上下游都能用的零碎工具：时间格式化、目录推算、字符串处理。
不放任何麻将规则、数据库访问与 HTTP 相关代码。

现状（S1）：空壳。时间函数（getTime/get_rfc3339_time 等）按 S2 的库表口径补齐，
落地后 processor 与 realtime 统一从这里取，禁止各自写 datetime.now()。
"""

__all__: list[str] = []
