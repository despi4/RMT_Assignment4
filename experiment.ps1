param(
    [ValidateSet('help','setup','check','pilot','freeze','final','analyze','status','export')]
    [string]$Action = 'help',
    [string]$Python,
    [string]$RunId = 'cpu_smoke_verified',
    [int]$LimitFacts = 3,
    [string]$UploadedAt,
    [string]$Evidence,
    [string]$Protocol,
    [string]$Declarant,
    [string]$Output
)
$ErrorActionPreference = 'Stop'

function Invoke-ExperimentPython {
    & $script:ExperimentPython @args
    if ($LASTEXITCODE -ne 0) { throw "Python command failed with exit code $LASTEXITCODE. Read the message above." }
}

if ($Action -eq 'help') {
    Write-Output @'
Run from the repository folder in PowerShell:
  .\experiment.ps1 setup       Create .venv, install CPU dependencies, download locked model
  .\experiment.ps1 check       Validate environment, data, model cache; run software tests
  .\experiment.ps1 pilot       63 real dev calls; never uses final test facts
  .\experiment.ps1 status      Show current progress without loading model weights
  .\experiment.ps1 freeze -UploadedAt REAL_ISO_TIME -Evidence RECEIPT -Protocol APPENDIX_A -Declarant NAME
  .\experiment.ps1 final       Run/resume all 2520 final calls after a genuine freeze
  .\experiment.ps1 analyze     Validate completed final logs; compute tables and 4 SVG figures
  .\experiment.ps1 export -Output DESTINATION.zip

Use -Python C:\path\to\python.exe to reuse an installed environment, or set RMT_PYTHON.
HF_HOME may point to the existing model cache. Default cache is .cache\huggingface.
After an interruption, use the identical pilot/final command to resume.
See README.md for manual error review and independent reproduction commands.
'@
    exit 0
}

if ($Python) {
    $script:ExperimentPython = (Get-Command $Python -ErrorAction Stop).Source
} elseif ($env:RMT_PYTHON) {
    $script:ExperimentPython = (Get-Command $env:RMT_PYTHON -ErrorAction Stop).Source
} elseif (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.venv/Scripts/python.exe')) {
    $script:ExperimentPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
} else {
    $script:ExperimentPython = (Get-Command python -ErrorAction Stop).Source
}

Push-Location $PSScriptRoot
try {
    $env:PYTHONIOENCODING = 'utf-8'
    $env:OMP_NUM_THREADS = '2'
    $env:HF_HUB_DISABLE_XET = '1'
    if (-not $env:HF_HOME) { $env:HF_HOME = Join-Path $PSScriptRoot '.cache/huggingface' }
    switch ($Action) {
        'setup' {
            if (Test-Path -LiteralPath 'freeze/freeze.json') { throw 'Already frozen. Do not reinstall or overwrite this environment.' }
            if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
                Invoke-ExperimentPython -m venv .venv
            }
            $script:ExperimentPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
            Invoke-ExperimentPython -m pip install -r requirements-cpu.txt
            Invoke-ExperimentPython scripts/prepare.py --download
        }
        'check' {
            Invoke-ExperimentPython scripts/status.py
            Invoke-ExperimentPython -m unittest discover -s tests -v
        }
        'status' { Invoke-ExperimentPython scripts/status.py }
        'pilot' { Invoke-ExperimentPython scripts/run.py --phase pilot --limit-facts $LimitFacts --run-id $RunId }
        'freeze' {
            if (-not $UploadedAt -or -not $Evidence -or -not $Protocol -or -not $Declarant) {
                throw 'freeze requires -UploadedAt, -Evidence, -Protocol and -Declarant. Use real Moodle details.'
            }
            Invoke-ExperimentPython scripts/status.py
            Invoke-ExperimentPython scripts/freeze.py --uploaded-at $UploadedAt --evidence $Evidence --protocol $Protocol --declarant $Declarant
        }
        'final' {
            Invoke-ExperimentPython scripts/status.py --require-final-ready
            Invoke-ExperimentPython scripts/run.py --phase final
        }
        'analyze' { Invoke-ExperimentPython scripts/analyze.py }
        'export' {
            if (-not $Output) { throw 'export requires -Output C:\path\to\package.zip' }
            Invoke-ExperimentPython scripts/export_package.py --output $Output
        }
    }
} finally { Pop-Location }
