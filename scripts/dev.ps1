<#
.SYNOPSIS
  Windows equivalent of the Makefile.  Usage:  .\scripts\dev.ps1 <command>
  Commands: install | dev | api | web | warmup | test | lint | eval | eval-fast | up
#>
param([Parameter(Position = 0)][string]$Command = "help")

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

function In($dir, [scriptblock]$block) { Push-Location $dir; try { & $block } finally { Pop-Location } }

switch ($Command) {
  "install" {
    In $Backend { uv sync --extra vision }
    In $Frontend { npm install }
  }
  "api" { In $Backend { uv run uvicorn app.main:app --reload --port 8000 } }
  "web" { In $Frontend { npm run dev } }
  "dev" {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Backend'; uv run uvicorn app.main:app --reload --port 8000"
    In $Frontend { npm run dev }
  }
  "warmup" { In $Backend { uv run python scripts/warmup.py } }
  "test" {
    In $Backend { uv run pytest -q }
    In $Frontend { npm test }
  }
  "lint" {
    In $Backend { uv run ruff check .; uv run ruff format --check .; uv run mypy app }
    In $Frontend { npm run lint; npm run typecheck }
  }
  "eval" { In $Backend { uv run python ../eval/run_eval.py } }
  "eval-fast" { In $Backend { uv run python ../eval/run_eval.py --retrieval-only } }
  "up" { In $Root { docker compose up --build } }
  default { Get-Help $MyInvocation.MyCommand.Path -Detailed }
}
