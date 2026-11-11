$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$PublishDir = Join-Path $RepoRoot 'assessment-public'
if (Test-Path -LiteralPath $PublishDir) {
  $publishItem = Get-Item -LiteralPath $PublishDir -Force
  if (($publishItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Refusing to stage the public site through a symlink or reparse point.' }
  Remove-Item -LiteralPath $PublishDir -Recurse -Force
}
$SourceFiles = @('index.html','awards.html','syllabus.html','hackathon.html','sample-papers.html','mock-test.html','faqs.html','contact.html','login.html','register.html','registration.js','team-prelaunch.html','admin.html','admin.js','exam.html','exam.js','styles.css','layout.css','site.js','sample-papers.js','mock-test.js','question-bank.js')
$AssetFiles = @('brand-home.svg','brand-home-pathways.svg','brand-home-learning.svg','brand-home-hackathon.svg','brand-home-recognition.svg','brand-registration.svg','brand-syllabus.svg','brand-syllabus-map.svg','brand-samples.svg','brand-sample-explanation.svg','brand-mock.svg','brand-awards.svg','brand-launchpad.svg','brand-hackathon.svg','brand-faq.svg','brand-contact.svg','brand-login.svg','brand-team.svg','brand-admin.svg','brand-exam.svg','brand-award-podium.svg','brand-hackathon-award.svg','favicon.svg','sutravya-logo.png','qualinova-logo.png','healthcare-talent-search-og.jpg')
$Allowed = @()
New-Item -ItemType Directory -Path $PublishDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PublishDir 'assets') -Force | Out-Null
foreach ($file in $SourceFiles) {
  $source = Join-Path $RepoRoot $file
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing required public file: $file" }
  Copy-Item -LiteralPath $source -Destination (Join-Path $PublishDir $file) -Force
  $Allowed += $file
}
foreach ($file in $AssetFiles) {
  $source = Join-Path (Join-Path $RepoRoot 'assets') $file
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing required public asset: assets/$file" }
  Copy-Item -LiteralPath $source -Destination (Join-Path (Join-Path $PublishDir 'assets') $file) -Force
  $Allowed += "assets/$file"
}
$Unexpected = @()
Get-ChildItem -LiteralPath $PublishDir -Recurse -File | ForEach-Object {
  $relative = $_.FullName.Substring($PublishDir.Length).TrimStart('\','/') -replace '\\','/'
  if ($Allowed -notcontains $relative) { $Unexpected += $relative }
}
if ($Unexpected.Count -gt 0) { throw "Unexpected public files: $($Unexpected -join ', ')" }
$Restricted = Get-ChildItem -LiteralPath $PublishDir -Recurse -File | Where-Object {
  $_.Name -eq '.env' -or $_.Extension -in @('.db','.sqlite','.xlsx') -or $_.Name -match 'answer.?key'
}
if ($Restricted) { throw 'A restricted file was found in the public bundle. Build aborted.' }
Write-Host "Assessment microsite staged successfully in $PublishDir" -ForegroundColor Green
Write-Host "Files staged: $((Get-ChildItem -LiteralPath $PublishDir -Recurse -File).Count)"
