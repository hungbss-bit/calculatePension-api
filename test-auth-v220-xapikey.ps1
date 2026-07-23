# test-auth-v220-xapikey.ps1
# Kiem tra chinh xac khoa runtime tren Render ma khong hien thi khoa bi mat.
# Yeu cau tren Render:
#   REQUIRE_API_KEY=true
#   AUTH_DIAGNOSTICS_ENABLED=true
# Sau khi chuan doan xong, dat AUTH_DIAGNOSTICS_ENABLED=false va deploy lai.

$ErrorActionPreference = "Stop"
$BaseUrl = "https://calculatepension-api.onrender.com"

function Read-SecretText {
    param([string]$Prompt)
    $secure = Read-Host $Prompt -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function Get-Sha256Prefix([string]$Text) {
    $normalized = $Text.Trim()
    if (
        $normalized.Length -ge 2 -and
        (($normalized.StartsWith('"') -and $normalized.EndsWith('"')) -or
         ($normalized.StartsWith("'") -and $normalized.EndsWith("'")))
    ) {
        $normalized = $normalized.Substring(1, $normalized.Length - 2).Trim()
    }

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized)
        $hash = $sha.ComputeHash($bytes)
        return (-join ($hash | ForEach-Object { $_.ToString("x2") })).Substring(0, 12)
    }
    finally {
        $sha.Dispose()
    }
}

Write-Host "1. Kiem tra /health..." -ForegroundColor Cyan
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get -TimeoutSec 60
$health | ConvertTo-Json -Depth 10

if ($health.version -ne "2.2.0") {
    Write-Host "CANH BAO: Render khong chay dung phien ban 2.2.0." -ForegroundColor Yellow
}

$key = Read-SecretText "Nhap dung API_KEY dang dat tren Render"
$localFingerprint = Get-Sha256Prefix $key

Write-Host "`nDau van tay khoa nhap tren may: $localFingerprint" -ForegroundColor Cyan
Write-Host "Dang goi /v1/authDiagnostics bang header X-API-Key..." -ForegroundColor Cyan

try {
    $diagnostics = Invoke-RestMethod `
        -Uri "$BaseUrl/v1/authDiagnostics" `
        -Method Get `
        -Headers @{"X-API-Key" = $key} `
        -TimeoutSec 60

    $diagnostics | ConvertTo-Json -Depth 10

    Write-Host "`n================ KET LUAN ================" -ForegroundColor Cyan

    if (-not $diagnostics.configured) {
        Write-Host "Render runtime khong doc duoc API_KEY." -ForegroundColor Red
        Write-Host "Kiem tra dung service va Environment Variables."
    }
    elseif (-not $diagnostics.received_present) {
        Write-Host "Request khong gui header X-API-Key." -ForegroundColor Red
    }
    elseif ($diagnostics.normalized_match) {
        Write-Host "X-API-Key KHOP CHINH XAC." -ForegroundColor Green
        Write-Host "Endpoint /v1/capabilities phai hoat dong voi cung khoa nay."
    }
    else {
        Write-Host "X-API-Key KHONG KHOP." -ForegroundColor Red
        Write-Host "Fingerprint local:   $localFingerprint"
        Write-Host "Fingerprint runtime: $($diagnostics.expected_fingerprint_sha256_12)"
        Write-Host "Fingerprint received:$($diagnostics.received_fingerprint_sha256_12)"
        Write-Host "Do dai runtime:       $($diagnostics.expected_length)"
        Write-Host "Do dai received:      $($diagnostics.received_length_normalized)"
        Write-Host "Bien runtime dang doc:$($diagnostics.configured_env_name)"
    }
}
catch {
    Write-Host "Chuan doan THAT BAI: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
        Write-Host $_.ErrorDetails.Message
    }
    Write-Host "Bao dam AUTH_DIAGNOSTICS_ENABLED=true va da Save and deploy."
}
