@echo off
TITLE SmartLock Akilli Tahta Baslatici - Debug Modu
CHCP 65001 > nul
cls

:: Calisma dizinini ayarla
cd /d "%~dp0"

echo ======================================================
echo    SMARTLOCK GÜVENLİK SİSTEMİ BAŞLATILIYOR
echo ======================================================
echo.

:: Python kontrolü
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Python sistemde bulunamadi! 
    echo Lutfen Python'un yuklu oldugundan ve "Add to PATH" seceneginin 
    echo isaretli oldugundan emin olun.
    pause
    exit
)

:: Kütüphane kontrolü - Hata veren PIL burada 'Pillow' olarak yüklenir
echo [+] Kutuphaneler kontrol ediliyor...
python -m pip install --upgrade pip
python -m pip install Pillow qrcode pystray pyautogui keyboard

:: Dosya kontrolü
if not exist "server.py" (
    echo [HATA] 'server.py' dosyasi bulunamadi!
    pause
    exit
)

:: Programı Başlat
echo [+] Sistem baslatiliyor...
python server.py

if %errorlevel% neq 0 (
    echo.
    echo [UYARI] Program bir hata ile karsilasti.
    pause
)

exit