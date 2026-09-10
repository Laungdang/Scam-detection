# Closed pilot: Q&A-only + Cloudflare quick tunnel (ได้ URL ชั่วคราว *.trycloudflare.com)
# ก่อนรัน: ตั้ง APP_ACCESS_CODE ใน .env เสมอ — ไม่งั้นใครก็ยิง Claude API ผ่าน URL ได้
# ใช้: powershell -File scripts\run_pilot.ps1
param([int]$Port = 8000)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot

$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile) -or -not (Select-String -Path $envFile -Pattern "^APP_ACCESS_CODE=.+" -Quiet)) {
    Write-Host "คำเตือน: ยังไม่ได้ตั้ง APP_ACCESS_CODE ใน .env — ทุกคนที่มี URL จะใช้ได้ (เสียเครดิต Claude)" -ForegroundColor Yellow
    Write-Host "พิมพ์ Ctrl+C เพื่อยกเลิก หรือรอ 10 วินาทีเพื่อรันต่อแบบไม่มีรหัส..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
}

# ดาวน์โหลด cloudflared ครั้งแรกครั้งเดียว (quick tunnel ไม่ต้องมี Cloudflare account)
$bin = Join-Path $PSScriptRoot "bin"
New-Item -ItemType Directory -Force $bin | Out-Null
$cf = Join-Path $bin "cloudflared.exe"
if (-not (Test-Path $cf)) {
    Write-Host "กำลังดาวน์โหลด cloudflared..."
    Invoke-WebRequest "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile $cf
}

Write-Host "เริ่ม API (Q&A-only) ที่ port $Port — bge-m3 โหลด ~30 วิ ตอน start"
$api = Start-Process python -ArgumentList "-m", "uvicorn", "app.api.main:app", "--host", "127.0.0.1", "--port", "$Port" -PassThru -WorkingDirectory $root

try {
    Write-Host "เปิด tunnel... URL จะโผล่ในบรรทัด https://xxxx.trycloudflare.com (Ctrl+C เพื่อปิดทั้งคู่)"
    & $cf tunnel --url "http://127.0.0.1:$Port"
} finally {
    if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force }
}
