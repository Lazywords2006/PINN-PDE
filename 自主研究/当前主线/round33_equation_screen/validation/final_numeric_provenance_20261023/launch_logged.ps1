param([Parameter(Mandatory=$true)][ValidateSet('full','heldout')][string]$Batch)
$ErrorActionPreference = 'Stop'
$runtimeDir = 'D:\CodexRuntime\runs\r33_final_numeric_provenance_20261023'
$pythonPath = 'D:\CodexRuntime\venvs\r33-torch214\Scripts\python.exe'
$scriptName = if ($Batch -eq 'full') { 'recompute_saved_models.py' } else { 'recompute_heldout.py' }
$scriptPath = Join-Path $PSScriptRoot $scriptName
$scriptArgs = @('-B', '-X', 'utf8', ('"' + $scriptPath + '"'), 'run')
if ($Batch -eq 'full') { $scriptArgs += @('--batch', 'full') }
$scriptArgs += @('--workers', '8')
$logDir = Join-Path $runtimeDir ('supervisor_' + $Batch)
New-Item -ItemType Directory -Path $logDir -ErrorAction Stop | Out-Null
$started = [DateTime]::UtcNow.ToString('o')
$stdoutPath = Join-Path $logDir 'stdout.log'
$stderrPath = Join-Path $logDir 'stderr.log'
$invocation = [ordered]@{ executable=$pythonPath; argument_list=$scriptArgs; cwd=$PSScriptRoot; started_utc=$started; launcher_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLower(); script_sha256=(Get-FileHash -LiteralPath $scriptPath -Algorithm SHA256).Hash.ToLower(); actual_returncode=$null }
$invocation | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $logDir 'invocation.json') -Encoding utf8
$auditProcess = Start-Process -FilePath $pythonPath -ArgumentList $scriptArgs -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru -Wait
$receipt = [ordered]@{ executable=$pythonPath; argument_list=$scriptArgs; started_utc=$started; finished_utc=[DateTime]::UtcNow.ToString('o'); process_id=$auditProcess.Id; actual_returncode=$auditProcess.ExitCode; stdout_sha256=(Get-FileHash -LiteralPath $stdoutPath -Algorithm SHA256).Hash.ToLower(); stderr_sha256=(Get-FileHash -LiteralPath $stderrPath -Algorithm SHA256).Hash.ToLower(); launcher_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLower(); script_sha256=(Get-FileHash -LiteralPath $scriptPath -Algorithm SHA256).Hash.ToLower() }
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $logDir 'execution.json') -Encoding utf8
$destination = Join-Path $PSScriptRoot ('supervisors\' + $Batch)
if (Test-Path -LiteralPath $destination) { throw 'Supervisor evidence destination already exists' }
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $destination 'launch_logged.ps1')
Get-ChildItem -LiteralPath $logDir -File | ForEach-Object {
    $target = Join-Path $destination $_.Name
    Copy-Item -LiteralPath $_.FullName -Destination $target
    if ((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash) { throw 'Supervisor evidence copy failed' }
}
$receipt | ConvertTo-Json -Depth 8 | Write-Output
exit $auditProcess.ExitCode
