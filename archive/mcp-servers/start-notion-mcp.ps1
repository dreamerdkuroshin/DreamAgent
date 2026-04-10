# =====================================================
# Notion MCP Server — bridges stdio to HTTP on port 3010
# =====================================================
# SETUP: Add your Notion integration token below, OR set it in .env as NOTION_TOKEN
# Get a token at: https://www.notion.so/my-integrations
# =====================================================

param(
    [string]$Token = $env:NOTION_TOKEN,
    [int]$Port = 3010
)

if (-not $Token) {
    Write-Host "ERROR: NOTION_TOKEN is not set." -ForegroundColor Red
    Write-Host "  Run with: .\start-notion-mcp.ps1 -Token secret_xxx"
    Write-Host "  Or add NOTION_TOKEN=secret_xxx to your .env file"
    exit 1
}

Write-Host "Starting Notion MCP on http://localhost:$Port ..." -ForegroundColor Cyan

$env:OPENAPI_MCP_HEADERS = '{"Authorization": "Bearer ' + $Token + '"}'

& "$PSScriptRoot\..\\.venv\Scripts\mcp-proxy" `
    --port $Port `
    -- `
    npx -y @notionhq/notion-mcp-server
