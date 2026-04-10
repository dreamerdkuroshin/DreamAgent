# =====================================================
# DreamAgent — Launch ALL MCP Servers
# =====================================================
# Starts Notion, Stripe, and Figma MCP servers in
# separate PowerShell windows, each proxied to HTTP.
#
# BEFORE RUNNING: fill your tokens in .env or below
# =====================================================

# Load .env from parent directory
$envFile = "$PSScriptRoot\..\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
        }
    }
    Write-Host ".env loaded" -ForegroundColor Green
}

$venvProxy = "$PSScriptRoot\..\\.venv\Scripts\mcp-proxy"

function Start-MCPServer {
    param($Name, $Port, $EnvSetup, $Command)
    Write-Host "Starting $Name MCP on port $Port..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "$EnvSetup; & '$venvProxy' --port $Port -- $Command" -WindowStyle Normal
}

# ---- Notion ----
$notionToken = $env:NOTION_TOKEN
if ($notionToken) {
    Start-MCPServer `
        -Name "Notion" `
        -Port 3010 `
        -EnvSetup "`$env:OPENAPI_MCP_HEADERS='{""Authorization"": ""Bearer $notionToken""}'"`
        -Command "npx -y @notionhq/notion-mcp-server"
} else {
    Write-Host "SKIPPING Notion MCP — NOTION_TOKEN not set in .env" -ForegroundColor Yellow
}

# ---- Stripe ----
$stripeKey = $env:STRIPE_API_KEY
if ($stripeKey) {
    Start-MCPServer `
        -Name "Stripe" `
        -Port 3013 `
        -EnvSetup "`$env:STRIPE_API_KEY='$stripeKey'" `
        -Command "npx -y @stripe/mcp --tools=all"
} else {
    Write-Host "SKIPPING Stripe MCP — STRIPE_API_KEY not set in .env" -ForegroundColor Yellow
}

# ---- Figma ----
$figmaToken = $env:FIGMA_TOKEN
if ($figmaToken) {
    Start-MCPServer `
        -Name "Figma" `
        -Port 3012 `
        -EnvSetup "`$env:FIGMA_TOKEN='$figmaToken'" `
        -Command "npx -y figma-developer-mcp --figma-api-key=$figmaToken"
} else {
    Write-Host "SKIPPING Figma MCP — FIGMA_TOKEN not set in .env" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "MCP servers launched. Check individual windows for status." -ForegroundColor Green
Write-Host "Register URLs with DreamAgent by calling POST /api/connect/mcp once each server is running."
Write-Host ""
Write-Host "  Notion: http://localhost:3010"
Write-Host "  Figma:  http://localhost:3012"
Write-Host "  Stripe: http://localhost:3013"
