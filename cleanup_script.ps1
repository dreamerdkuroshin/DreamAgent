$ErrorActionPreference = "SilentlyContinue"

$root = $PSScriptRoot

# 1. Structure the frontend properly
Move-Item -Path "$root\frontend of dreamAgent\DreamAgent-v1.00-UI\artifacts\dream-agent" -Destination "$root\frontend" -Force
Remove-Item -Path "$root\frontend of dreamAgent" -Recurse -Force

# 2. Setup standard folders
New-Item -Path "$root\docs" -ItemType Directory -Force
New-Item -Path "$root\archive" -ItemType Directory -Force

# 3. Move documentations
Move-Item -Path "$root\DreamAgent_Analysis.docx" -Destination "$root\docs\" -Force
Move-Item -Path "$root\agent_memory.md" -Destination "$root\docs\" -Force

# 4. Move bloated redundant / deprecated folders out of root
$to_archive = @(
    "builder_output", 
    "ecommerce_app",
    "sandbox",
    "tests",
    "safety",
    "plugins",
    "self_improvement",
    "mcp-servers",
    "tools",
    "DreamAgent",
    "Interface",
    "Modes",
    "antigravity",
    "monitoring"
)

foreach ($dir in $to_archive) {
    if (Test-Path "$root\$dir") {
        Move-Item -Path "$root\$dir" -Destination "$root\archive\" -Force
    }
}
