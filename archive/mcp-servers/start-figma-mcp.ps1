# =====================================================
# Figma MCP Server — bridges stdio to HTTP on port 3012
# =====================================================
# SETUP: Add your Figma personal access token below, OR set it in .env as FIGMA_TOKEN
# Get a token at: https://www.figma.com/settings (under "Personal access tokens")
# =====================================================

param(
    [string]$Token = $env:FIGMA_TOKEN,
    [int]$Port = 3012
)

if (-not $Token) {
    Write-Host "ERROR: FIGMA_TOKEN is not set." -ForegroundColor Red
    Write-Host "  Run with: .\start-figma-mcp.ps1 -Token figd_xxx"
    Write-Host "  Or add FIGMA_TOKEN=figd_xxx to your .env file"
    exit 1
}

Write-Host "Starting Figma MCP on http://localhost:$Port ..." -ForegroundColor Cyan

& "$PSScriptRoot\..\\.venv\Scripts\mcp-proxy" `
    --port $Port `
    -- `
    npx -y figma-developer-mcp --figma-api-key=$Token
