# Raspberry detector

Raspberry Pi runs only helmet detection and sends events to the laptop backend.
Backend, database, Firebase, Flutter app, and face worker stay on the laptop.

## Copy to Raspberry Pi

Copy these files/folders to the Raspberry Pi:

```text
yolo/pi_detector.py
yolo/best.pt
yolo/requirements_pi.txt
scripts/raspberry_setup.sh
scripts/raspberry_run.sh
```

Keep the same structure on Raspberry:

```text
helmet_syst/
  yolo/
    pi_detector.py
    best.pt
    requirements_pi.txt
  scripts/
    raspberry_setup.sh
    raspberry_run.sh
```

## Laptop

Start backend on the laptop:

```powershell
cd C:\Users\user\Desktop\helmet_syst
.\scripts\start_backend.ps1
```

The laptop IP must be reachable from Raspberry Pi. Current IP:

```text
172.20.10.8
```

## Raspberry setup

On Raspberry:

```bash
cd ~/helmet_syst
chmod +x scripts/raspberry_setup.sh scripts/raspberry_run.sh
./scripts/raspberry_setup.sh
```

## Run with USB camera

```bash
cd ~/helmet_syst
./scripts/raspberry_run.sh http://172.20.10.8:8000 opencv
```

## Run with Raspberry Camera Module

Install Picamera2 first if needed:

```bash
sudo apt update
sudo apt install -y python3-picamera2
```

Then run:

```bash
cd ~/helmet_syst
./scripts/raspberry_run.sh http://172.20.10.8:8000 picamera2
```

## Buzzer

The active buzzer is on GPIO17.

Default behavior:

- short beep pattern, not one long tone
- siren lasts 3 seconds
- siren starts after the same 15 second no-helmet delay as the event logic
- while no-helmet people are visible, siren repeats once per minute
- one shared siren is used, so several people do not start several buzzers

Run with buzzer enabled:

```bash
./scripts/raspberry_run.sh http://172.20.10.8:8000 opencv
```

Run at home without buzzer:

```bash
./scripts/raspberry_run.sh http://172.20.10.8:8000 opencv --no-buzzer
```

If the buzzer is not physically connected, the script can still run. GPIO17 will switch, but nothing will sound.

Default sound is already set to a quiet short-pulse pattern. To make it even softer, use shorter on-time and longer pause:

```bash
./scripts/raspberry_run.sh http://172.20.10.8:8000 opencv --buzzer-on-time 0.03 --buzzer-off-time 0.45
```

## Check connection

From Raspberry:

```bash
curl http://172.20.10.8:8000/events
```

If this does not return JSON, check Wi-Fi, laptop IP, backend, and Windows Firewall port `8000`.
