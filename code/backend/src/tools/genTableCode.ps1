# 家庭麻将 · 表定义批量生成脚本 (Windows / PowerShell)
#
# 用途: 对 database/mj_*.txt 逐表执行 mysqlCodeGenerator.py, 产出
#       database/auto_generated/auto_gen_code_mj_*.py 与 word_table_mj_*.csv
#
# ★★ 表名陷阱(务必保留本段说明) ★★
#   mysqlCodeGenerator.readFromFile() 用 fileName.split(".")[0] 取表名, 而产物目录
#   AUTO_GENERATE_OUTPUT_DIR="auto_generated" 是相对路径。若在 src 下执行
#   `-i database/mj_room.txt`, 表名会变成 "database/mj_room", 建表名与产物名全部错误。
#   因此本脚本必须先 Set-Location 到 database 目录, 再传裸文件名(-i mj_room.txt)。
#   请勿改成带路径调用，也不要用 handleSQL()。
#
# 用法: powershell -File code/backend/src/tools/genTableCode.ps1

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$srcDir    = Split-Path -Parent $scriptDir
$dbDir     = Join-Path $srcDir "database"
$outDir    = Join-Path $dbDir "auto_generated"
$py        = if ($env:PY) { $env:PY } else { "python" }

Set-Location $dbDir
New-Item -ItemType Directory -Force $outDir | Out-Null

$okCount  = 0
$failList = @()
Get-ChildItem -Path (Join-Path $dbDir "mj_*.txt") | Sort-Object Name | ForEach-Object {
    $tableName = $_.BaseName                    # mj_room
    # cmdTitle = 去 mj_ 前缀 + 去全部下划线: mj_game_player -> gameplayer
    $title     = ($tableName -replace "^mj_", "") -replace "_", ""
    $product   = Join-Path $outDir ("auto_gen_code_{0}.py" -f $tableName)

    # 生成器内部 try/except 会吞掉异常并以 0 退出，故必须用「产物是否真的产出」判定
    if (Test-Path $product) { Remove-Item $product -Force }

    Write-Host ("[gen] {0} -t {1}" -f $_.Name, $title)
    & $py "mysqlCodeGenerator.py" -i $_.Name -t $title
    $exitCode = $LASTEXITCODE

    $created = (Test-Path $product) -and ((Get-Item $product).Length -gt 0)
    if ($exitCode -eq 0 -and $created) {
        $okCount++
    } else {
        $failList += $_.Name
        Write-Host ("[gen] FAIL {0} (exit={1}, product={2})" -f $_.Name, $exitCode, $created)
    }
}

Write-Host ("[gen] done: ok={0}, fail={1}" -f $okCount, $failList.Count)
if ($failList.Count -gt 0) {
    Write-Host ("[gen] failed files: {0}" -f ($failList -join ", "))
    exit 1
}
exit 0
