# MELOJI hardware guide

How to turn the printed enclosure (`cad/stl/`) into a working device. Sizes in the enclosure are
parameters at the top of `cad/meloji_enclosure.py`: measure your actual parts and adjust them before printing.

## Microcontroller: Seeed Studio XIAO ESP32S3 Sense

| Option | Fits MELOJI? | Why |
| --- | --- | --- |
| **ESP32-S3 (XIAO ESP32S3 Sense)** | **Yes, use this** | Bluetooth LE + Wi-Fi for the iOS app, 8 MB PSRAM for audio buffers and the screen, a built-in microphone, USB-C and LiPo charging, 21 x 17.8 mm |
| Arduino Uno / Nano (classic) | No | No Bluetooth or Wi-Fi, 2 KB RAM: can't hold audio or drive a color screen smoothly |
| BBC micro:bit | No | Has BLE, but its fixed board shape, LED grid and small RAM don't suit a custom audio device |
| Adafruit Circuit Playground | No | A round all-in-one board with LEDs and sensors built on; it won't fit this case or drive this screen well |

The iOS app talks to it over **Bluetooth Low Energy** (Apple's CoreBluetooth framework). iPhones don't allow
apps to use classic Bluetooth with hobby devices, so BLE is the right channel. Use Wi-Fi only if you need to
move long recordings quickly.

## Parts list

| Qty | Part | Used for | Notes |
| --- | --- | --- | --- |
| 1 | Seeed Studio XIAO ESP32S3 **Sense** | Brain, microphone, USB-C, battery charging | Its own USB-C port faces out through the bottom opening |
| 1 | 1.54" 240x240 IPS TFT, ST7789 driver, SPI | Waveform display | Window is 28.5 x 28.5 mm; front cavity fits a panel about 31.5 x 33.7 mm. Measure your module |
| 1 | MCP23017 I2C GPIO expander breakout | Reads the 8 front and side buttons | Frees the XIAO's few pins |
| 1 | MPR121 12-channel capacitive touch breakout | Senses pop-it presses (beat maker) | Center + inner ring = 7 pads; 5 spare |
| 1 | MAX98357A I2S amplifier breakout | Sound output | Mono, 3 W class D |
| 1 | Speaker, 20-28 mm, 8 ohm, 0.5-1 W | Playback | Not in the sketch: add a grille if you want playback without headphones |
| 9 | 6 x 6 mm tactile switch, ~5 mm tall | AI, D-pad x4, record, vol+, vol-, power | Gives the "click" under each printed cap |
| 1 | 10 k linear slide potentiometer, 15 mm travel (e.g. Bourns PTA15 series) | Slider | Check its lever size against the knob's 2.2 x 1.2 mm socket |
| 1 | 3.7 V LiPo, ~500 mAh (e.g. 503035, 5 x 30 x 35 mm) | Battery | Solder to the XIAO's BAT+/BAT- pads |
| 4 | M2 x 12 self-tapping screws | Close the shell | Driven from the back |
| - | Copper foil tape, perfboard, 30 AWG wire, hot glue | Touch pads, button boards, wiring | |
| - | PLA or PETG (shells, caps); **TPU 95A** (pop-it insert) | Printing | |

## Wiring (XIAO ESP32S3 pins)

| XIAO pin | GPIO | Connects to |
| --- | --- | --- |
| D0 | 1 | Slider pot wiper (analog in); pot ends to 3V3 and GND |
| D1 | 2 | TFT CS |
| D2 | 3 | TFT DC |
| D3 | 4 | Power button to GND (wakes from deep sleep) |
| D4 | 5 | I2C SDA: MCP23017 + MPR121 |
| D5 | 6 | I2C SCL: MCP23017 + MPR121 |
| D6 | 43 | MAX98357A BCLK |
| D7 | 44 | MAX98357A LRC |
| D8 | 7 | TFT SCK |
| D9 | 8 | MAX98357A DIN |
| D10 | 9 | TFT MOSI (SDA) |
| 3V3 / GND | | Everything's power; TFT RST to 3V3 through 10 k, TFT backlight to 3V3 |

- The microphone is built into the Sense board and uses no D pins.
- This plan uses D9 for audio, so the Sense board's microSD slot (which shares D8-D10) is unused. Store clips in
  flash and send them to the phone.
- Poll the MCP23017 and MPR121 over I2C (about 100 times a second) instead of wiring their interrupt pins.
- Check every pin against Seeed's current XIAO ESP32S3 pinout before soldering.

## How each feature works

- **Screen:** the panel sits behind the front window, held with foam tape or hot glue. Draw the waveform with
  the TFT_eSPI or LovyanGFX library.
- **Clicky buttons:** each printed cap has a flange inside the wall so it can't fall out. Solder tactile switches
  to small perfboards and glue them so each switch touches the back of its cap. The D-pad cap sits over 4 switches,
  one under each arm.
- **Power button:** a momentary switch acting as soft power. Hold for 2 s to sleep (ESP32 deep sleep), press to
  wake. Add an inline slide switch on the battery wire if you want a hard off for storage.
- **USB-C:** the XIAO's own port charges the battery and programs the board. Mount the XIAO at the bottom with
  the port flush with the opening.
- **Pop-it (beat maker):** print `popit_insert_TPU.stl` in TPU 95A and glue it behind the back holes, domes facing
  out. For sensing, put a copper-tape pad behind each of the 7 inner bubbles, wired to the MPR121; pressing a dome
  brings the finger close enough to trigger it. Tune the MPR121 thresholds by testing. The outer rings stay pure fidget.
- **Smooth slider:** the slide pot does the smoothing. Glue its body to the inside of the right wall with the
  lever through the slot, push the knob on, and add a dab of damping grease. Sand the slot edges: the back shell
  prints with the slot running up the layers.

## Printing

| Part | Material | Orientation | Notes |
| --- | --- | --- | --- |
| front_shell, back_shell | PLA or PETG | Outer face down | Supports for the rounded rim only; 0.2 mm layers, 3 walls |
| cap_* (6), slider_knob | PLA or PETG | As exported (flange on the bed) | No supports; test-fit in the holes and adjust `CLEAR` |
| popit_insert_TPU | TPU 95A | As exported (domes up) | Slow (20-25 mm/s); adjust `POP_WALL` (0.6 mm) for a softer or firmer pop |

The microphone needs a path for sound: once you know where the Sense board's mic sits, add a 1.5 mm hole there.
