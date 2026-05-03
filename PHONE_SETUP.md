# iPhone → MacBook Video Stream Setup

## Recommended: Camo (USB — most reliable, no WiFi needed)

1. Install **Camo** on your iPhone: https://reincubate.com/camo/
2. Install **Camo for Mac** on your MacBook
3. Plug iPhone into MacBook via USB cable
4. Trust the computer on your iPhone when prompted
5. Open Camo on Mac — you should see your iPhone feed
6. In `cv/config.py`, set: `CAMERA_SOURCE = 1`
   (run `python -c "import cv2; [print(i, cv2.VideoCapture(i).isOpened()) for i in range(5)]"` to find the right index)

## Alternative: HTTP MJPEG stream over WiFi

Use any iPhone app that serves a MJPEG HTTP stream, e.g. **iVCam** or **EpocCam**.

1. Connect iPhone and MacBook to the **same WiFi network** (use iPhone hotspot)
2. Install the streaming app on iPhone, start the stream
3. Note the URL shown in the app (usually `http://<phone-ip>:8080/video` or similar)
4. In `cv/config.py`, set: `CAMERA_SOURCE = "http://192.168.x.x:8080/video"`

## Verify Stream Works

```bash
cd cv
python -c "
import cv2
import config
cap = cv2.VideoCapture(config.CAMERA_SOURCE)
ret, frame = cap.read()
print('SUCCESS' if ret else 'FAILED', frame.shape if ret else '')
cap.release()
"
```

## Hotspot Setup (for MacBook ↔ Pi connection)

The MacBook also needs to reach the Pi at `pi.local`.

**Option A — same router:**  Connect both MacBook and Pi to the same WiFi router.

**Option B — phone hotspot as bridge:**
1. iPhone: Settings → Personal Hotspot → on
2. MacBook: join iPhone hotspot WiFi
3. Pi: join iPhone hotspot WiFi (configure in Pi's wpa_supplicant.conf or via raspi-config)
4. Both MacBook and Pi are on the same subnet → `pi.local` should resolve

**Verify Pi is reachable:**
```bash
ping pi.local
# or if that fails, get the Pi's IP from Teammate 2:
curl http://192.168.x.x:5000/cv -d '{"test":1}' -H "Content-Type: application/json"
```
