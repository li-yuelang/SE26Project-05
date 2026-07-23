# check_runs.ps1 - 查看论文解析运行状态
[CmdletBinding()]
param()

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPaths = @(
    "C:\Users\27017\AppData\Local\Programs\Python\Python313\python.exe",
    "python3",
    "python"
)

$python = $null
foreach ($p in $pythonPaths) {
    $result = & { try { & $p -c "print('ok')" 2>$null; $true } catch { $false } } 2>$null
    if ($result) { $python = $p; break }
}

if (-not $python) {
    Write-Error "Python not found"
    exit 1
}

$pyScript = Join-Path $scriptDir "check_runs.py"
& $python $pyScript
