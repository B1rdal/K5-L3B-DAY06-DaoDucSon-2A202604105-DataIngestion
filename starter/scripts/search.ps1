param(
    [string]$Question,
    [string]$Section,
    [switch]$Details,
    [switch]$Json,
    [switch]$NoColor
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$starterRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $starterRoot '.venv\Scripts\python.exe'
try {
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Run Setup Day6.cmd first.' }
    if (-not $Question) { $Question = Read-Host 'Enter your question' }
    if (-not $Question.Trim()) { exit 0 }
    Push-Location -LiteralPath $starterRoot
    try {
        $oldErrorAction = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $dockerOutput = & docker compose -p day6_student_starter up -d --wait 2>&1
        $dockerExit = $LASTEXITCODE
        $ErrorActionPreference = $oldErrorAction
        if ($dockerExit -ne 0) {
            $dockerOutput | Out-Host
            throw 'Could not start the database. Check that Docker Desktop is running.'
        }
        $searchArgs = @('-B', '-m', 'src.run', 'search', $Question)
        if ($Section) { $searchArgs += @('--section', $Section) }
        if ($Details) { $searchArgs += '--details' }
        if ($Json) { $searchArgs += '--json' }
        if ($NoColor) { $searchArgs += '--no-color' }
        & $pythonExe @searchArgs
        $searchExit = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    exit $searchExit
} catch {
    Write-Host "Search failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
