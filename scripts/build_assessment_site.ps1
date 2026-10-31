$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PublishDir = Join-Path $RepoRoot 'assessment-public'

if (Test-Path -LiteralPath $PublishDir) {
    $publishItem = Get-Item -LiteralPath $PublishDir -Force
    if (($publishItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Refusing to stage the public site through a symlink or reparse point.'
    }
}

$SourceFiles = @(
    'index.html', 'awards.html', 'syllabus.html', 'sample-papers.html',
    'faqs.html', 'contact.html', 'login.html', 'team-prelaunch.html', 'styles.css', 'site.js'
)
$AssetFiles = @(
    'awards-hero.svg'
    'contact-hero.svg'
    'faq-hero.svg'
    'favicon.svg'
    'handshake.svg'
    'nurse-tech.svg'
    'qualinova-logo.png'
    'sample-hero.svg'
    'sutravya-logo.png'
    'syllabus-hero.svg'
    'hero-registration.webp'
    'hero-free.webp'
    'hero-talent.webp'
    'healthcare-talent-search-og.jpg'
)
$AllowedPublicFiles = @($SourceFiles) + @($AssetFiles | ForEach-Object { "assets/$_" })

New-Item -ItemType Directory -Path $PublishDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PublishDir 'assets') -Force | Out-Null

foreach ($file in $SourceFiles) {
    $source = Join-Path $RepoRoot $file
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Missing required public file: $file"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $PublishDir $file) -Force
}
foreach ($file in $AssetFiles) {
    $source = Join-Path (Join-Path $RepoRoot 'assets') $file
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Missing required public asset: assets/$file"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path (Join-Path $PublishDir 'assets') $file) -Force
}

$Unexpected = @()
Get-ChildItem -LiteralPath $PublishDir -Recurse -File | ForEach-Object {
    $relative = $_.FullName.Substring($PublishDir.Length).TrimStart('\', '/') -replace '\\', '/'
    if ($AllowedPublicFiles -notcontains $relative) { $Unexpected += $relative }
}
if ($Unexpected.Count -gt 0) {
    throw "Unexpected file(s) in public bundle: $($Unexpected -join ', '). Remove or review them before building."
}

$Restricted = Get-ChildItem -LiteralPath $PublishDir -Recurse -File | Where-Object {
    $_.Name -eq '.env' -or $_.Extension -in @('.db', '.sqlite', '.xlsx') -or $_.Name -match 'answer.?key'
}
if ($Restricted) { throw 'A restricted file was found in the public bundle. Build aborted.' }

Write-Host "Assessment microsite staged successfully in $PublishDir" -ForegroundColor Green
Write-Host "Files staged: $((Get-ChildItem -LiteralPath $PublishDir -Recurse -File).Count)"
