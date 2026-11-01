<#
gearbase Windows 便携包构建脚本（PowerShell 5.1+ / 7+）。
不随包交二进制；嵌入式 Python 由本脚本在【用户机器上】下载，并强制校验 sha256。
用法（在 gearbase 包根或任意位置）：
  powershell -ExecutionPolicy Bypass -File packaging\windows\build_portable.ps1 -PythonVersion 3.12.x -PythonSha256 <由你核对的哈希>
也可离线：把已下载的 zip 放好后用 -EmbedZip <路径>（仍然校验哈希）。
#>
param(
    [Parameter(Mandatory = $true)][string]$PythonVersion,   # 例如 3.12.x：须由你在 python.org 确认真实存在的版本
    [Parameter(Mandatory = $true)][string]$PythonSha256,    # 须由你从 python.org 发布页核对后填入；不接受占位符
    [string]$EmbedZip = "",
    [string]$OutDir = "",
    [switch]$IncludePrivate                                  # 默认不拷 tr30/iso18265/kisssoft/registry（私有资料）
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $OutDir) { $OutDir = Join-Path $Root "dist\gearbase-portable" }

if ($PythonSha256 -match "CHECK|TODO|PLACEHOLDER|^\s*$" -or $PythonSha256 -notmatch "^[0-9a-fA-F]{64}$") {
    throw "PythonSha256 必须是你核对过的 64 位十六进制 sha256，不接受占位符。"
}
$Url = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"

if (Test-Path $OutDir) { Remove-Item -Recurse -Force $OutDir }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Zip = $EmbedZip
if (-not $Zip) {
    $Zip = Join-Path $OutDir "python-embed.zip"
    Write-Host "下载 $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Zip -UseBasicParsing
}
$Got = (Get-FileHash -Algorithm SHA256 -Path $Zip).Hash.ToLower()
if ($Got -ne $PythonSha256.ToLower()) {
    Remove-Item -Force $Zip -ErrorAction SilentlyContinue
    throw "sha256 不匹配：期望 $PythonSha256，实际 $Got。已中止。"
}
Expand-Archive -Path $Zip -DestinationPath (Join-Path $OutDir "python") -Force
if (-not $EmbedZip) { Remove-Item -Force $Zip }

# 拷入核心包（范围依据 docs/接续文档.md 与 MANIFEST；总包 00-包索引.md 不在本包内，范围以其为准时请核对）
$dirs = @("gearmath", "data", "docs", "tests", "bank", "vendor")
$files = @("mcp_server.py", "run_tests.py", "conftest.py", "demo.py", "README.md", "VERSION", "CHANGELOG.md", "MANIFEST.json", "PACKAGE-CONTENTS.sha256")
$private = @("tr30", "iso18265", "kisssoft", "registry")
$App = Join-Path $OutDir "gearbase"
New-Item -ItemType Directory -Force -Path $App | Out-Null
foreach ($d in $dirs) {
    $src = Join-Path $Root $d
    if (Test-Path $src) {
        $xd = @("__pycache__")
        if (-not $IncludePrivate -and $d -eq "data") { $xd += $private }
        robocopy $src (Join-Path $App $d) /E /XD $xd /XF *.pyc /NFL /NDL /NJH /NJS | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy 失败：$d" }
    }
}
foreach ($f in $files) { if (Test-Path (Join-Path $Root $f)) { Copy-Item (Join-Path $Root $f) $App } }
if ($IncludePrivate) {
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $App 'MANIFEST.json') | ConvertFrom-Json
    foreach ($row in $manifest.legacy) {
        $rel = $row.path
        if ($rel -notmatch '^legacy/' -or $rel -match '(^|/)\.\.(/|$)' -or $rel.Contains('\')) { throw "Invalid legacy path: $rel" }
        $dest = Join-Path $App $rel
        New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
        Copy-Item -LiteralPath (Join-Path $Root $rel) -Destination $dest
    }
    $code = 'import importlib.util,pathlib,sys; p=pathlib.Path(sys.argv[1]); s=importlib.util.spec_from_file_location("ph",p/"gearmath/tools/package_hashes.py"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); stale=m.update_manifest(p,write=False); assert not stale, stale; (p/m.CONTENTS).write_text(m.contents_text(p),encoding="utf-8",newline="\n")'
    $code | & (Join-Path $OutDir 'python\python.exe') -I - $App
    if ($LASTEXITCODE -ne 0) { throw 'Portable manifest verification failed' }
}

# 启动 bat：使用包内 python.exe 与 -I 隔离模式
$py = '%~dp0python\python.exe'
Set-Content -Encoding ASCII (Join-Path $OutDir "run_tests.bat") "@echo off`r`ncd /d %~dp0gearbase`r`n`"$py`" -I run_tests.py %*`r`n"
Set-Content -Encoding ASCII (Join-Path $OutDir "doctor.bat") "@echo off`r`ncd /d %~dp0gearbase`r`n`"$py`" -I gearmath\tools\doctor.py %*`r`n"
Set-Content -Encoding ASCII (Join-Path $OutDir "mcp_server.bat") "@echo off`r`n`"$py`" -I %~dp0gearbase\mcp_server.py --state-dir %~dp0state %*`r`n"
Write-Host "完成：$OutDir 。先运行 doctor.bat。"
