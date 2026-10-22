param(
    [ValidateSet('Gate','Run','Status','Plan')][string]$Action='Status',
    [ValidateRange(1,24)][int]$Workers=24
)
$ErrorActionPreference='Stop'
$stage6Python='D:\CodexRuntime\venvs\r33-torch214\Scripts\python.exe'
$stage6Runtime='D:\CodexRuntime\runs\r33_stage6_20261022'
$env:TEMP='D:\CodexRuntime\temp'
$env:TMP=$env:TEMP
$env:PIP_CACHE_DIR='D:\CodexRuntime\cache\pip'
$env:UV_CACHE_DIR='D:\CodexRuntime\cache\uv'
$env:XDG_CACHE_HOME='D:\CodexRuntime\cache\xdg'
$env:PYTHONPYCACHEPREFIX='D:\CodexRuntime\cache\pycache'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
if (-not (Test-Path -LiteralPath 'D:\CodexRuntime')) { throw 'D:\CodexRuntime 不可用。' }
New-Item -ItemType Directory -Force -Path $stage6Runtime,$env:TEMP,$env:PYTHONPYCACHEPREFIX | Out-Null
Set-Location -LiteralPath $PSScriptRoot
$stage6Script=Join-Path $PSScriptRoot 'stage6_runner.py'
if ($Action -ne 'Run') {
    & $stage6Python -u $stage6Script "--$($Action.ToLowerInvariant())"
    exit $LASTEXITCODE
}
# Python's OS locks are authoritative. The unique log names avoid truncating an
# earlier launch's logs even when a duplicate launch is rejected by the lock.
$stage6Stamp=Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$stage6Process=Start-Process -FilePath $stage6Python -ArgumentList @('-u',('"{0}"' -f $stage6Script),'--run','--workers',"$Workers") -WorkingDirectory $PSScriptRoot -RedirectStandardOutput (Join-Path $stage6Runtime "runner_$stage6Stamp.stdout.log") -RedirectStandardError (Join-Path $stage6Runtime "runner_$stage6Stamp.stderr.log") -WindowStyle Hidden -PassThru
try { $stage6Process.PriorityClass='Normal' } catch { if (-not $stage6Process.HasExited) { throw } }
[pscustomobject]@{RunnerPid=$stage6Process.Id;Runtime=$stage6Runtime;Status=(Join-Path $stage6Runtime 'status.json');AuthorizedTasks=30;MaxWorkers=$Workers;Priority='Normal';Prerequisite='已通过修订 6 Gate'} | ConvertTo-Json
