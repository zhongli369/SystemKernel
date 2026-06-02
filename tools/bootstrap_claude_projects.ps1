param(
    [string]$Root = "F:\Claude\ClaudeCodeProject",
    [string]$SystemKernelPath = "F:\Claude\SystemKernel",
    [switch]$DryRun,
    [switch]$Apply,
    [string]$ReportPath = "v3\exports\global_claude_bootstrap_report.json"
)

$ErrorActionPreference = "Stop"

$SectionMarker = "## SystemKernel Governance"

$SectionContent = @"

## SystemKernel Governance

This project uses SystemKernel as a global governance and architecture reference.

SystemKernel path:
F:\Claude\SystemKernel

Rules for Claude Code / Codex agents:
- Treat external tool outputs as evidence, not truth.
- Do not introduce new truth sources without explicit approval.
- Keep integrations removable.
- Avoid ability +10%, complexity +300%.
- Prefer dry-run, report, adapter, and evidence before integration.
- Do not add heavy dependencies without architecture review.
- Do not integrate agent/memory/vector/LLM frameworks directly into project runtime without approval.
- Use SystemKernel CLI for complex architecture, provider, context, or evidence decisions.

Useful commands:
- python F:\Claude\SystemKernel\v3\cli\systemkernel.py v4 status
- python F:\Claude\SystemKernel\v3\cli\systemkernel.py v4 summary
- python F:\Claude\SystemKernel\v3\cli\systemkernel.py eval benefit
- python F:\Claude\SystemKernel\v3\cli\systemkernel.py capability summary
"@

$SkipDirs = @(".git", "node_modules", ".venv", "venv", "dist", "build", "target", ".next", "out")

# --- Validate inputs ---

if (-not (Test-Path $Root -PathType Container)) {
    Write-Host "ERROR: Root directory does not exist: $Root"
    exit 1
}

if ($DryRun -eq $Apply) {
    Write-Host "ERROR: Must pass exactly one of -DryRun or -Apply."
    exit 1
}

$Mode = if ($DryRun) { "DRY-RUN" } else { "APPLY" }
Write-Host "SystemKernel Global Bootstrap"
Write-Host "  Root:              $Root"
Write-Host "  SystemKernelPath:  $SystemKernelPath"
Write-Host "  Mode:              $Mode"
Write-Host ""

# --- Scan projects ---

$Projects = Get-ChildItem -Path $Root -Directory | Where-Object {
    $_.Name -notin $SkipDirs
}

if ($Projects.Count -eq 0) {
    Write-Host "No project directories found under $Root"
    exit 0
}

$Actions = @()
$Scanned = 0
$Created = 0
$Updated = 0
$Unchanged = 0
$Skipped = 0

foreach ($Proj in $Projects) {
    $ProjPath = $Proj.FullName
    $ProjName = $Proj.Name
    $ClaudeFile = Join-Path $ProjPath "CLAUDE.md"
    $Scanned++

    if ($Proj.Name -in $SkipDirs) {
        $Skipped++
        $Actions += @{
            project = $ProjName
            claude_file = $ClaudeFile
            action = "skip"
            reason = "Directory in skip list"
        }
        Write-Host "  SKIP   $ProjName (skip list)"
        continue
    }

    if (Test-Path $ClaudeFile -PathType Leaf) {
        $Content = Get-Content $ClaudeFile -Raw -Encoding UTF8

        if ($Content -match [regex]::Escape($SectionMarker)) {
            $Unchanged++
            $Actions += @{
                project = $ProjName
                claude_file = $ClaudeFile
                action = "unchanged"
                reason = "Section already present"
            }
            Write-Host "  OK     $ProjName (section already present)"
        } else {
            if ($Apply) {
                $NewContent = $Content.TrimEnd() + "`r`n" + $SectionContent
                [System.IO.File]::WriteAllText($ClaudeFile, $NewContent, [System.Text.UTF8Encoding]::new($false))
            }
            $Updated++
            $Actions += @{
                project = $ProjName
                claude_file = $ClaudeFile
                action = "update"
                reason = "Section appended to existing CLAUDE.md"
            }
            Write-Host "  UPDATE $ProjName (section appended)"
        }
    } else {
        if ($Apply) {
            [System.IO.File]::WriteAllText($ClaudeFile, $SectionContent, [System.Text.UTF8Encoding]::new($false))
        }
        $Created++
        $Actions += @{
            project = $ProjName
            claude_file = $ClaudeFile
            action = "create"
            reason = "CLAUDE.md created with governance section"
        }
        Write-Host "  CREATE $ProjName (CLAUDE.md created)"
    }
}

Write-Host ""
Write-Host "Summary: scanned=$Scanned created=$Created updated=$Updated unchanged=$Unchanged skipped=$Skipped"

# --- Write JSON report ---

$ReportDir = Split-Path $ReportPath -Parent
if ($ReportDir -and -not (Test-Path $ReportDir)) {
    New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
}

$Report = @{
    root = $Root
    systemkernel_path = $SystemKernelPath
    dry_run = $DryRun.IsPresent
    apply = $Apply.IsPresent
    scanned_count = $Scanned
    create_count = $Created
    update_count = $Updated
    unchanged_count = $Unchanged
    skipped_count = $Skipped
    actions = $Actions
}

$ReportJson = $Report | ConvertTo-Json -Depth 3
[System.IO.File]::WriteAllText($ReportPath, $ReportJson, [System.Text.UTF8Encoding]::new($false))
Write-Host "Report written to: $ReportPath"
