param([Parameter(Mandatory=$true)][string]$ProjectRoot)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$r33WrapperNames=@('run_preflight.ps1','run_stage5.ps1','run_stage6.ps1')
$r33Expected=@{
    'run_preflight.ps1'=@('Workers')
    'run_stage5.ps1'=@('Action')
    'run_stage6.ps1'=@('Action','Workers')
}
$r33Rows=@()
foreach($r33Name in $r33WrapperNames){
    $r33Source=Join-Path $ProjectRoot $r33Name
    $r33Tokens=$null
    $r33Errors=$null
    $r33Ast=[System.Management.Automation.Language.Parser]::ParseFile($r33Source,[ref]$r33Tokens,[ref]$r33Errors)
    if($r33Errors.Count -ne 0){throw "Parser failed: $r33Name"}
    $r33Actual=@($r33Ast.ParamBlock.Parameters | ForEach-Object {$_.Name.VariablePath.UserPath})
    if(($r33Actual -join ',') -ne ($r33Expected[$r33Name] -join ',')){throw "Parameter mismatch: $r33Name"}
    $r33Rows+=@{
        source=$r33Source
        source_sha256=(Get-FileHash -LiteralPath $r33Source -Algorithm SHA256).Hash.ToLowerInvariant()
        parser_errors=0
        parameters=@($r33Ast.ParamBlock.Parameters | ForEach-Object {
            @{name=$_.Name.VariablePath.UserPath;default=$_.DefaultValue.Extent.Text;attributes=@($_.Attributes.Extent.Text)}
        })
    }
}
$r33Document=Join-Path $PSScriptRoot 'REPRODUCIBILITY_CN.md'
$r33Text=Get-Content -LiteralPath $r33Document -Raw -Encoding UTF8
$r33Matches=[regex]::Matches($r33Text,'(?s)```powershell\r?\n(.*?)```')
$r33Blocks=@()
$r33Index=0
foreach($r33Match in $r33Matches){
    $r33Index++
    $r33Tokens=$null
    $r33Errors=$null
    $r33Ast=[System.Management.Automation.Language.Parser]::ParseInput($r33Match.Groups[1].Value,[ref]$r33Tokens,[ref]$r33Errors)
    if($r33Errors.Count -ne 0){throw "Document command block parser failed: $r33Index"}
    $r33Blocks+=@{index=$r33Index;parser_errors=0;executed=$false}
}
if($r33Blocks.Count -ne 4){throw 'Expected four PowerShell documentation blocks.'}
@{scope='Static AST parsing only; wrappers and documented training/final commands were not executed.';wrappers=$r33Rows;documentation_blocks=$r33Blocks} | ConvertTo-Json -Depth 9
