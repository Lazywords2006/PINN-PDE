param([ValidateSet('Gate','Run','Status','Plan')][string]$Action='Run')
$ErrorActionPreference='Stop'
$stage5Python='D:\CodexRuntime\venvs\r33-torch214\Scripts\python.exe'
$stage5Runtime='D:\CodexRuntime\runs\r33_stage5_20261022'
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
New-Item -ItemType Directory -Force -Path $stage5Runtime,$env:TEMP,$env:PYTHONPYCACHEPREFIX | Out-Null
Set-Location -LiteralPath $PSScriptRoot
$stage5Script=Join-Path $PSScriptRoot 'stage5_runner.py'
if ($Action -ne 'Run') {
    & $stage5Python -u $stage5Script "--$($Action.ToLowerInvariant())"
    exit $LASTEXITCODE
}
$stage5Status=Join-Path $stage5Runtime 'status.json'
if (Test-Path -LiteralPath $stage5Status) {
    $stage5Previous=Get-Content -LiteralPath $stage5Status -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($stage5KnownPid in @($stage5Previous.runner_pid,$stage5Previous.batch_pid)) {
        if ($stage5KnownPid -and (Get-Process -Id $stage5KnownPid -ErrorAction SilentlyContinue)) {
            throw "Previous runner/batch process still exists: $stage5KnownPid; inspect Status before restarting."
        }
    }
    if ($stage5Previous.phase -eq 'completed') { throw 'All 22 tasks already completed; do not rerun.' }
}
$stage5Process=Start-Process -FilePath $stage5Python -ArgumentList @('-u',('"{0}"' -f $stage5Script)) -WorkingDirectory $PSScriptRoot -RedirectStandardOutput (Join-Path $stage5Runtime 'runner.stdout.log') -RedirectStandardError (Join-Path $stage5Runtime 'runner.stderr.log') -WindowStyle Hidden -PassThru
[pscustomobject]@{RunnerPid=$stage5Process.Id;Runtime=$stage5Runtime;Status=$stage5Status;AuthorizedTasks=22;Phase2=$false} | ConvertTo-Json
