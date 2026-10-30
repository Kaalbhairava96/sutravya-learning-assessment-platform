param(
    [ValidateSet("all", "team_prelaunch", "public_registration")]
    [string]$Source = "all",
    [string]$OutputPath = "",
    [string]$ApiBaseUrl = "https://sutravya-assessment-api-demo.onrender.com"
)

$ErrorActionPreference = "Stop"
$downloadFolder = Join-Path ([Environment]::GetFolderPath("UserProfile")) "Downloads"
if (-not $OutputPath) {
    $OutputPath = Join-Path $downloadFolder "sutravya-registrations.csv"
}
$apiUri = [Uri]$ApiBaseUrl.TrimEnd("/")
if ($apiUri.Scheme -ne "https") {
    throw "The registration export requires an HTTPS API URL."
}

$secureKey = Read-Host "Registration export key" -AsSecureString
$keyPointer = [IntPtr]::Zero
$plainKey = $null
try {
    $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    $encodedSource = [Uri]::EscapeDataString($Source)
    $exportUri = "{0}/api/admin/registrations/export?source={1}" -f $apiUri.AbsoluteUri.TrimEnd("/"), $encodedSource
    Invoke-WebRequest -Uri $exportUri -Method Get -Headers @{ "X-Registration-Export-Key" = $plainKey } -OutFile $OutputPath -UseBasicParsing | Out-Null
    Write-Host "Registration export saved to $([System.IO.Path]::GetFullPath($OutputPath))"
}
catch {
    throw "Registration export failed. Check the API URL, access key, and organiser permissions; no key or response details were displayed."
}
finally {
    $plainKey = $null
    if ($keyPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }
    if ($secureKey) { $secureKey.Dispose() }
}
