$BaseUrl = "https://calculatepension-api.onrender.com"
$SecureKey = Read-Host "Nhap API_KEY (ky tu se duoc an)" -AsSecureString
$BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
try {
    $Key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($BSTR)

    Write-Host "`n1. Kiem tra /health..." -ForegroundColor Cyan
    Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get | ConvertTo-Json -Depth 10

    Write-Host "`n2. Kiem tra X-API-Key..." -ForegroundColor Cyan
    try {
        Invoke-RestMethod -Uri "$BaseUrl/v1/capabilities" -Method Get -Headers @{"X-API-Key" = $Key} | ConvertTo-Json -Depth 10
        Write-Host "X-API-Key: THANH CONG" -ForegroundColor Green
    }
    catch {
        Write-Host "X-API-Key: THAT BAI - $($_.Exception.Message)" -ForegroundColor Red
    }

    Write-Host "`n3. Kiem tra Authorization Bearer..." -ForegroundColor Cyan
    try {
        Invoke-RestMethod -Uri "$BaseUrl/v1/capabilities" -Method Get -Headers @{"Authorization" = "Bearer $Key"} | ConvertTo-Json -Depth 10
        Write-Host "Bearer: THANH CONG" -ForegroundColor Green
    }
    catch {
        Write-Host "Bearer: THAT BAI - $($_.Exception.Message)" -ForegroundColor Red
    }
}
finally {
    if ($BSTR -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    }
    Remove-Variable Key -ErrorAction SilentlyContinue
}
