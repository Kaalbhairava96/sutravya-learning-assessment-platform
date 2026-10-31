$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PublishDir = Join-Path $RepoRoot 'assessment-public'

$SourceFiles = @(
    'index.html', 'awards.html', 'syllabus.html',
    'sample-papers.html', 'faqs.html', 'contact.html',
    'login.html', 'styles.css', 'site.js'
)

$AssetFiles = @(
    'awards-hero.svg', 'contact-hero.svg', 'faq-hero.svg',
    'favicon.svg', 'handshake.svg', 'nurse-tech.svg',
    'qualinova-logo.png', 'sample-hero.svg',
    'sutravya-logo.png', 'syllabus-hero.svg'
)

New-Item -ItemType Directory -Path $PublishDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PublishDir 'assets') -Force | Out-Null

foreach ($file in $SourceFiles) {
    $src = Join-Path $RepoRoot $file
    if (!(Test-Path -LiteralPath $src -PathType Leaf)) {
        throw "Missing source file: $file"
    }
    Copy-Item -LiteralPath $src -Destination $PublishDir -Force
}

foreach ($file in $AssetFiles) {
    $src = Join-Path (Join-Path $RepoRoot 'assets') $file
    if (!(Test-Path -LiteralPath $src -PathType Leaf)) {
        throw "Missing asset: assets/$file"
    }
    Copy-Item -LiteralPath $src -Destination (Join-Path $PublishDir 'assets') -Force
}

$Allowed = @($SourceFiles) + @($AssetFiles | ForEach-Object { "assets/$_" })

$Unexpected = @(
    Get-ChildItem -LiteralPath $PublishDir -Recurse -File |
    ForEach-Object {
        $relative = $_.FullName.Substring($PublishDir.Length).TrimStart('\','/') -replace '\\','/'
        if ($Allowed -notcontains $relative) { $relative }
    }
)

if ($Unexpected.Count -gt 0) {
    throw "Unexpected files in public bundle: $($Unexpected -join ', ')"
}

Write-Host "Assessment microsite staged successfully!" -ForegroundColor Green
Write-Host "Files staged: $((Get-ChildItem $PublishDir -Recurse -File).Count)"
