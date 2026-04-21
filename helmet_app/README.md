# helmet_app

Flutter client for the helmet safety system.

## Run on Android over Wi-Fi

1. Start the backend so it is reachable from the phone:

```powershell
cd ..\backend
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

2. Find the computer Wi-Fi IP:

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
  $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown"
} | Select-Object IPAddress, InterfaceAlias
```

3. Pair/connect the phone with Wireless debugging:

```powershell
adb pair PHONE_IP:PAIR_PORT
adb connect PHONE_IP:ADB_PORT
flutter devices
```

4. Run the app with the backend URL:

```powershell
flutter pub get
flutter run -d DEVICE_ID --dart-define=API_BASE_URL=http://COMPUTER_WIFI_IP:8000
```

Example:

```powershell
flutter run -d 192.168.1.35:5555 --dart-define=API_BASE_URL=http://192.168.1.10:8000
```

For the YOLO detector, point it to the same backend:

```powershell
$env:HELMET_SERVER_URL="http://COMPUTER_WIFI_IP:8000"
python ..\yolo\main.py
```

Use the same `HELMET_SERVER_URL` value when running `face_worker.py`.

If the phone cannot load data, check that both devices are on the same Wi-Fi network and Windows Firewall allows inbound TCP port `8000` for Python.

## Helper scripts

From the repository root:

```powershell
.\scripts\start_backend.ps1
.\scripts\run_flutter_wifi.ps1 -ComputerIp COMPUTER_WIFI_IP -DeviceId DEVICE_ID
.\scripts\run_yolo.ps1 -ComputerIp COMPUTER_WIFI_IP
.\scripts\run_face_worker.ps1 -ComputerIp COMPUTER_WIFI_IP
```
