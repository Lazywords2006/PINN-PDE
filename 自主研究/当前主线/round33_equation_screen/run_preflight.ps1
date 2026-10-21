param([ValidateRange(1,10)][int]$Workers=8)
$ErrorActionPreference='Stop'
$r33Python='D:\CodexRuntime\venvs\r33-torch214\Scripts\python.exe'
$r33RunDir='D:\CodexRuntime\runs\r33_resolution_20261021'
$env:TEMP='D:\CodexRuntime\temp'
$env:TMP='D:\CodexRuntime\temp'
$env:PIP_CACHE_DIR='D:\CodexRuntime\cache\pip'
$env:UV_CACHE_DIR='D:\CodexRuntime\cache\uv'
$env:XDG_CACHE_HOME='D:\CodexRuntime\cache\xdg'
$env:PYTHONPYCACHEPREFIX='D:\CodexRuntime\cache\pycache'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:R33_CKPT_DIR=Join-Path $r33RunDir 'pilot_checkpoints'
Set-Location -LiteralPath $PSScriptRoot
$r33Common=@('run','--eqs','E1_heat,E3_fisher','--methods','vanilla,hardic,hardic+layer','--seeds','100,101','--workers',"$Workers",'--set','width=64','--set','depth=4','--set','adam_steps=4000','--set','lbfgs_iters=500','--set','nf=2048','--set','nb=128','--set','n0=256','--set','nf_fixed=4096','--set','nb_fixed=256','--set','n0_fixed=512','--set','lr0=0.001','--set','lr1=0.00001','--set','tau=0.1','--set','t_refine=0','--set','w_ic=1','--set','soap_beta=0.95','--set','soap_freq=10')
foreach ($r33Optimizer in @('adam','soap_official64')) {
    $r33Tag=if ($r33Optimizer -eq 'adam') {'preflight4_adam'} else {'preflight4_soap64'}
    & $r33Python -u 'screen.py' @r33Common '--tag' $r33Tag '--set' "optimizer=$r33Optimizer" 2>&1 | Tee-Object -FilePath (Join-Path $r33RunDir "$r33Tag.log")
    if ($LASTEXITCODE -ne 0) { throw "Preflight failed: $r33Tag" }
}
