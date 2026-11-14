param(
    [string]$PdfPath,
    [switch]$SkipInstall,
    [switch]$SkipIndex,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$repoRoot = $PSScriptRoot
$starterRoot = Join-Path $repoRoot 'starter'
$pythonExe = Join-Path $starterRoot '.venv\Scripts\python.exe'
$envPath = Join-Path $starterRoot '.env'

if ($CheckOnly) {
    Write-Output "Repository: $repoRoot"
    Write-Output "Python environment: $pythonExe"
    Write-Output "Default model cache: $(Join-Path $starterRoot '.cache')"
    Write-Output "Docker Compose: $(Join-Path $starterRoot 'docker-compose.yml')"
    exit 0
}

function Invoke-Day6 {
    param([string]$Program, [string[]]$Arguments)
    $ErrorActionPreference = 'Continue'
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Program" }
}

try {
    if ($PdfPath) { $PdfPath = (Resolve-Path -LiteralPath $PdfPath -ErrorAction Stop).Path }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Install Docker Desktop and start it before running setup.'
    }
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            Invoke-Day6 -Program 'py' -Arguments @('-3.13', '-m', 'venv', (Join-Path $starterRoot '.venv'))
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            Invoke-Day6 -Program 'python' -Arguments @('-m', 'venv', (Join-Path $starterRoot '.venv'))
        } else {
            throw 'Install Python 3.13 before running setup.'
        }
    }
    Push-Location -LiteralPath $starterRoot
    try {
        if (-not $SkipInstall) {
            $pythonVersion = & $pythonExe -c 'import sys; print(sys.version_info[0], sys.version_info[1], sep=chr(46))'
            if ($LASTEXITCODE -ne 0) { throw 'The Python environment could not start.' }
            $requirements = if ($pythonVersion -eq '3.13') { 'requirements-lock.txt' } else { 'requirements.txt' }
            Invoke-Day6 -Program $pythonExe -Arguments @('-m', 'pip', 'install', '-r', $requirements)
        }
        if (-not (Test-Path -LiteralPath $envPath)) {
            Copy-Item -LiteralPath (Join-Path $starterRoot '.env.example') -Destination $envPath
        }
        Write-Output 'Starting PostgreSQL + pgvector...'
        Invoke-Day6 -Program 'docker' -Arguments @('compose', '-p', 'day6_student_starter', 'up', '-d', '--wait')
        Invoke-Day6 -Program $pythonExe -Arguments @('-B', 'scripts/check_setup.py')

        if (-not $SkipIndex) {
            $pack = Get-Content -LiteralPath (Join-Path $repoRoot 'data\artifact_references.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            $missing = @($pack.artifacts | Where-Object { -not (Test-Path -LiteralPath (Join-Path $repoRoot $_.path)) })
            if ($missing.Count -gt 0) {
                if (-not $PdfPath) { $PdfPath = Read-Host 'Path to the matching source PDF (any folder)' }
                if (-not $PdfPath) { throw 'A matching source PDF is needed to restore the evidence files.' }
                $PdfPath = (Resolve-Path -LiteralPath $PdfPath -ErrorAction Stop).Path
                Invoke-Day6 -Program $pythonExe -Arguments @('-B', 'scripts/submission.py', 'restore', '--pdf', $PdfPath)
            }
            Invoke-Day6 -Program $pythonExe -Arguments @('-B', 'scripts/prepare_database.py')
        }
        Write-Output ''
        Write-Output 'Setup complete. Open Search Day6.cmd in the repository to search.'
    } finally {
        Pop-Location
    }
} catch {
    Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
