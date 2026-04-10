# =====================================================
# Stripe MCP Server — bridges stdio to HTTP on port 3013
# =====================================================
# SETUP: Add your Stripe secret key below, OR set it in .env as STRIPE_API_KEY
# Get your key at: https://dashboard.stripe.com/apikeys
# =====================================================

param(
    [string]$ApiKey = $env:STRIPE_API_KEY,
    [int]$Port = 3013
)

if (-not $ApiKey) {
    Write-Host "ERROR: STRIPE_API_KEY is not set." -ForegroundColor Red
    Write-Host "  Run with: .\start-stripe-mcp.ps1 -ApiKey sk_test_xxx"
    Write-Host "  Or add STRIPE_API_KEY=sk_test_xxx to your .env file"
    exit 1
}

Write-Host "Starting Stripe MCP on http://localhost:$Port ..." -ForegroundColor Cyan

$env:STRIPE_API_KEY = $ApiKey

& "$PSScriptRoot\..\\.venv\Scripts\mcp-proxy" `
    --port $Port `
    -- `
    npx -y @stripe/mcp --tools=all
