# zFileAnal v3 — Photo Labeler + File & Folder Toolkit
#
# v3.0 - New tkinter GUI. The photo-labelling workflow is front and centre:
#          * open a folder, see thumbnails (columns adjustable → thumbnail size)
#          * tick "quick labels" (family names, places, things) to build a file name
#            like  20260627_Elliot_Alice_butterfly_IMG_135135.JPG
#          * the date prefix is suggested automatically from EXIF (photos) or the
#            movie header (videos) or a date already embedded in the file name
#          * every edit is only STAGED — nothing touches the disk until you press
#            "Apply renames" and confirm the full old → new list
#          * "Undo last apply" reverses the last batch
#          * Metadata tab: prints every EXIF / PNG / MP4 field it can find, and lets
#            you edit the common EXIF text fields (dates, description, keywords…)
#        All ten v2.1.1 tools are still here under the Tools menu, driven by dialogs
#        instead of console prompts (same file-selection syntax: .jpg  !.txt  1,3,5-8  *name*).
#        Thumbnails: pure-Python baseline-JPEG decoder for the EXIF thumbnail (instant),
#        plus — on Windows — a background PowerShell/WIC helper that renders proper
#        thumbnails and previews (also handles progressive JPEG, HEIC, WEBP, TIFF, BMP).
#        Standard library only. Run:  py -3 zFileAnal_v3.py   (or START_zFileAnal_v3.cmd)

import os
import re
import sys
import json
import math
import time
import queue
import struct
import fnmatch
import hashlib
import shutil
import datetime
import tempfile
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

APP_VERSION = "3.0"
APP_NAME = f"zFileAnal v{APP_VERSION} — Photo Labeler"

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".heif"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".wmv"}
JPEG_EXT = {".jpg", ".jpeg"}
TK_NATIVE_EXT = {".png", ".gif"}

SETTINGS_DIR = os.path.join(os.path.expanduser("~"), ".zFileAnal")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings_v3.json")
CACHE_DIR = os.path.join(tempfile.gettempdir(), "zFileAnal_thumbs")
THUMB_PX = 384       # longest side of cached thumbnails
PREVIEW_PX = 1200    # longest side of cached previews

DEFAULT_SETTINGS = {
    "columns": 5,
    "last_folder": "",
    "auto_date": True,
    "sort": "Name",
    "include_videos": True,
    "write_exif_keywords": False,
    "label_groups": [
        {"name": "People", "labels": ["Elliot", "Alice"]},
        {"name": "Places", "labels": ["Home", "Park", "Beach", "School"]},
        {"name": "Things", "labels": ["Birthday", "Christmas", "Holiday", "Trip", "Sport", "Butterfly"]},
    ],
}


def load_settings():
    s = json.loads(json.dumps(DEFAULT_SETTINGS))
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
            s.update(json.load(fh))
    except Exception:
        pass
    return s


def save_settings(s):
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(s, fh, indent=2)
    except Exception:
        pass


def fmt_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.2f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    return f"{size / (1024 * 1024 * 1024):.2f} GB"


# ─────────────────────────────────────────────
# EXIF / TIFF PARSING
# ─────────────────────────────────────────────
EXIF_TAGS = {
    0x0100: "ImageWidth", 0x0101: "ImageLength", 0x0102: "BitsPerSample", 0x0103: "Compression",
    0x0106: "PhotometricInterpretation", 0x010E: "ImageDescription", 0x010F: "Make", 0x0110: "Model",
    0x0112: "Orientation", 0x011A: "XResolution", 0x011B: "YResolution", 0x0128: "ResolutionUnit",
    0x0131: "Software", 0x0132: "DateTime", 0x013B: "Artist", 0x013E: "WhitePoint",
    0x0201: "JPEGInterchangeFormat", 0x0202: "JPEGInterchangeFormatLength", 0x0213: "YCbCrPositioning",
    0x4746: "Rating", 0x4749: "RatingPercent", 0x8298: "Copyright", 0x829A: "ExposureTime",
    0x829D: "FNumber", 0x8769: "ExifIFDPointer", 0x8822: "ExposureProgram", 0x8825: "GPSInfoIFDPointer",
    0x8827: "ISOSpeedRatings", 0x9000: "ExifVersion", 0x9003: "DateTimeOriginal", 0x9004: "DateTimeDigitized",
    0x9010: "OffsetTime", 0x9011: "OffsetTimeOriginal", 0x9012: "OffsetTimeDigitized",
    0x9101: "ComponentsConfiguration", 0x9102: "CompressedBitsPerPixel", 0x9201: "ShutterSpeedValue",
    0x9202: "ApertureValue", 0x9203: "BrightnessValue", 0x9204: "ExposureBiasValue", 0x9205: "MaxApertureValue",
    0x9206: "SubjectDistance", 0x9207: "MeteringMode", 0x9208: "LightSource", 0x9209: "Flash",
    0x920A: "FocalLength", 0x9214: "SubjectArea", 0x927C: "MakerNote", 0x9286: "UserComment",
    0x9290: "SubSecTime", 0x9291: "SubSecTimeOriginal", 0x9292: "SubSecTimeDigitized",
    0x9C9B: "XPTitle", 0x9C9C: "XPComment", 0x9C9D: "XPAuthor", 0x9C9E: "XPKeywords", 0x9C9F: "XPSubject",
    0xA000: "FlashpixVersion", 0xA001: "ColorSpace", 0xA002: "PixelXDimension", 0xA003: "PixelYDimension",
    0xA005: "InteropIFDPointer", 0xA20E: "FocalPlaneXResolution", 0xA20F: "FocalPlaneYResolution",
    0xA210: "FocalPlaneResolutionUnit", 0xA217: "SensingMethod", 0xA300: "FileSource", 0xA301: "SceneType",
    0xA401: "CustomRendered", 0xA402: "ExposureMode", 0xA403: "WhiteBalance", 0xA404: "DigitalZoomRatio",
    0xA405: "FocalLengthIn35mmFilm", 0xA406: "SceneCaptureType", 0xA408: "Contrast", 0xA409: "Saturation",
    0xA40A: "Sharpness", 0xA420: "ImageUniqueID", 0xA430: "CameraOwnerName", 0xA431: "BodySerialNumber",
    0xA432: "LensSpecification", 0xA433: "LensMake", 0xA434: "LensModel", 0xEA1C: "Padding",
}
GPS_TAGS = {
    0: "GPSVersionID", 1: "GPSLatitudeRef", 2: "GPSLatitude", 3: "GPSLongitudeRef", 4: "GPSLongitude",
    5: "GPSAltitudeRef", 6: "GPSAltitude", 7: "GPSTimeStamp", 8: "GPSSatellites", 9: "GPSStatus",
    10: "GPSMeasureMode", 11: "GPSDOP", 12: "GPSSpeedRef", 13: "GPSSpeed", 14: "GPSTrackRef", 15: "GPSTrack",
    16: "GPSImgDirectionRef", 17: "GPSImgDirection", 18: "GPSMapDatum", 27: "GPSProcessingMethod",
    29: "GPSDateStamp", 31: "GPSHPositioningError",
}
INTEROP_TAGS = {1: "InteroperabilityIndex", 2: "InteroperabilityVersion"}
TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}
TYPE_NAME = {1: "BYTE", 2: "ASCII", 3: "SHORT", 4: "LONG", 5: "RATIONAL", 6: "SBYTE", 7: "UNDEFINED",
             8: "SSHORT", 9: "SLONG", 10: "SRATIONAL", 11: "FLOAT", 12: "DOUBLE"}
POINTER_TAGS = {0x8769: ("ExifIFD", EXIF_TAGS), 0x8825: ("GPS", GPS_TAGS), 0xA005: ("Interop", INTEROP_TAGS)}

ENUMS = {
    "Orientation": {1: "Normal", 2: "Mirror horizontal", 3: "Rotate 180", 4: "Mirror vertical",
                    5: "Mirror horizontal + rotate 270 CW", 6: "Rotate 90 CW",
                    7: "Mirror horizontal + rotate 90 CW", 8: "Rotate 270 CW"},
    "ResolutionUnit": {1: "None", 2: "inch", 3: "cm"},
    "ColorSpace": {1: "sRGB", 2: "Adobe RGB", 65535: "Uncalibrated"},
    "ExposureProgram": {0: "Not defined", 1: "Manual", 2: "Program", 3: "Aperture priority",
                        4: "Shutter priority", 5: "Creative", 6: "Action", 7: "Portrait", 8: "Landscape"},
    "MeteringMode": {0: "Unknown", 1: "Average", 2: "Center weighted", 3: "Spot", 4: "Multi-spot",
                     5: "Pattern", 6: "Partial", 255: "Other"},
    "WhiteBalance": {0: "Auto", 1: "Manual"},
    "ExposureMode": {0: "Auto", 1: "Manual", 2: "Auto bracket"},
    "SceneCaptureType": {0: "Standard", 1: "Landscape", 2: "Portrait", 3: "Night"},
    "Contrast": {0: "Normal", 1: "Soft", 2: "Hard"}, "Saturation": {0: "Normal", 1: "Low", 2: "High"},
    "Sharpness": {0: "Normal", 1: "Soft", 2: "Hard"}, "CustomRendered": {0: "Normal", 1: "Custom"},
    "SensingMethod": {1: "Not defined", 2: "One-chip color area", 3: "Two-chip", 4: "Three-chip",
                      5: "Color sequential area", 7: "Trilinear", 8: "Color sequential linear"},
    "LightSource": {0: "Unknown", 1: "Daylight", 2: "Fluorescent", 3: "Tungsten", 4: "Flash",
                    9: "Fine weather", 10: "Cloudy", 11: "Shade", 255: "Other"},
    "YCbCrPositioning": {1: "Centered", 2: "Co-sited"},
    "Compression": {1: "Uncompressed", 6: "JPEG (old-style)", 7: "JPEG"},
    "GPSAltitudeRef": {0: "Above sea level", 1: "Below sea level"},
}


class JpegError(Exception):
    pass


def jpeg_segments(data):
    """[(marker, seg_start, seg_end), ...] for the header segments of a JPEG, up to and including SOS."""
    if data[:2] != b"\xff\xd8":
        raise JpegError("Not a JPEG (no SOI marker)")
    segs = []
    i, n = 2, len(data)
    while i + 4 <= n:
        if data[i] != 0xFF:
            break
        m = data[i + 1]
        if m == 0xFF:
            i += 1
            continue
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            i += 2
            continue
        if m == 0xD9:
            break
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        segs.append((m, i, i + 2 + seg_len))
        if m == 0xDA:
            break
        i += 2 + seg_len
    return segs


def read_jpeg_header(path):
    """Read only the header segments (not the scan data) of a JPEG file. Returns (bytes, segments)."""
    with open(path, "rb") as fh:
        head = fh.read(4)
        if head[:2] != b"\xff\xd8":
            raise JpegError("Not a JPEG")
        buf = bytearray(head)
        pos = 2
        while True:
            while len(buf) < pos + 4:
                chunk = fh.read(4096)
                if not chunk:
                    return bytes(buf), jpeg_segments(bytes(buf))
                buf += chunk
            if buf[pos] != 0xFF:
                break
            m = buf[pos + 1]
            if m == 0xFF:
                pos += 1
                continue
            if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                pos += 2
                continue
            if m == 0xD9:
                break
            seg_len = struct.unpack(">H", buf[pos + 2:pos + 4])[0]
            need = pos + 2 + seg_len
            while len(buf) < need:
                chunk = fh.read(max(4096, need - len(buf)))
                if not chunk:
                    break
                buf += chunk
            if m == 0xDA:
                pos = need
                break
            pos = need
        return bytes(buf[:pos]), jpeg_segments(bytes(buf[:pos]))


class ExifData:
    def __init__(self):
        self.tiff = b""
        self.endian = ">"
        self.entries = []      # dicts: ifd, tag, name, type, count, value, raw, entry_off, value_off
        self.thumb = None      # embedded JPEG thumbnail bytes
        self.error = None

    def get(self, name, default=None):
        for e in self.entries:
            if e["name"] == name:
                return e["value"]
        return default

    def entry(self, name, ifd=None):
        for e in self.entries:
            if e["name"] == name and (ifd is None or e["ifd"] == ifd):
                return e
        return None


def _decode_value(typ, cnt, raw, e, name):
    try:
        if typ == 2:
            return raw.split(b"\0")[0].decode("utf-8", "replace").strip()
        if typ in (1, 7):
            if name.startswith("XP"):
                return raw.decode("utf-16-le", "replace").rstrip("\0")
            if name == "UserComment" and len(raw) >= 8:
                pfx, body = raw[:8], raw[8:]
                if pfx.startswith(b"ASCII"):
                    return body.decode("ascii", "replace").rstrip("\0 ")
                if pfx.startswith(b"UNICODE"):
                    enc = "utf-16-le" if e == "<" else "utf-16-be"
                    return body.decode(enc, "replace").rstrip("\0")
                return body.decode("utf-8", "replace").rstrip("\0 ")
            if name in ("ExifVersion", "FlashpixVersion", "InteroperabilityVersion"):
                return raw.decode("ascii", "replace")
            if name in ("MakerNote",) or cnt > 32:
                return f"<{cnt} bytes>"
            if all(32 <= b < 127 for b in raw.rstrip(b"\0")) and raw.strip(b"\0"):
                return raw.rstrip(b"\0").decode("ascii")
            vals = list(raw)
            return vals[0] if cnt == 1 else tuple(vals)
        if typ in (3, 4, 6, 8, 9, 11, 12):
            fmt = {3: "H", 4: "I", 6: "b", 8: "h", 9: "i", 11: "f", 12: "d"}[typ]
            vals = struct.unpack(e + fmt * cnt, raw[:TYPE_SIZE[typ] * cnt])
            return vals[0] if cnt == 1 else tuple(vals)
        if typ in (5, 10):
            fmt = "II" if typ == 5 else "ii"
            vals = []
            for k in range(cnt):
                num, den = struct.unpack(e + fmt, raw[k * 8:k * 8 + 8])
                vals.append((num, den))
            return vals[0] if cnt == 1 else tuple(vals)
    except Exception:
        return f"<unreadable {TYPE_NAME.get(typ, typ)} x{cnt}>"
    return f"<{cnt} bytes>"


def parse_exif_tiff(tiff):
    ex = ExifData()
    ex.tiff = tiff
    if tiff[:2] == b"II":
        e = "<"
    elif tiff[:2] == b"MM":
        e = ">"
    else:
        ex.error = "Bad TIFF header"
        return ex
    ex.endian = e
    try:
        if struct.unpack(e + "H", tiff[2:4])[0] != 42:
            ex.error = "Bad TIFF magic"
            return ex
        ifd0 = struct.unpack(e + "I", tiff[4:8])[0]
    except struct.error:
        ex.error = "Truncated TIFF header"
        return ex

    visited = set()

    def read_ifd(off, ifdname, tagmap):
        if off <= 0 or off + 2 > len(tiff) or off in visited:
            return 0
        visited.add(off)
        n = struct.unpack(e + "H", tiff[off:off + 2])[0]
        pointers = []
        for k in range(n):
            p = off + 2 + k * 12
            if p + 12 > len(tiff):
                break
            tag, typ, cnt = struct.unpack(e + "HHI", tiff[p:p + 8])
            size = TYPE_SIZE.get(typ, 1) * cnt
            voff = p + 8 if size <= 4 else struct.unpack(e + "I", tiff[p + 8:p + 12])[0]
            raw = tiff[voff:voff + size] if voff + size <= len(tiff) else b""
            name = tagmap.get(tag, f"Tag0x{tag:04X}")
            value = _decode_value(typ, cnt, raw, e, name)
            ex.entries.append(dict(ifd=ifdname, tag=tag, name=name, type=typ, count=cnt,
                                   value=value, raw=raw, entry_off=p, value_off=voff))
            if tag in POINTER_TAGS and typ in (3, 4) and raw:
                pointers.append((tag, value))
        nxt_pos = off + 2 + n * 12
        nxt = struct.unpack(e + "I", tiff[nxt_pos:nxt_pos + 4])[0] if nxt_pos + 4 <= len(tiff) else 0
        for tag, target in pointers:
            sub_name, sub_map = POINTER_TAGS[tag]
            if isinstance(target, int):
                read_ifd(target, sub_name, sub_map)
        return nxt

    nxt = read_ifd(ifd0, "IFD0", EXIF_TAGS)
    if nxt:
        read_ifd(nxt, "IFD1", EXIF_TAGS)
        toff = ex.get("JPEGInterchangeFormat")
        tlen = ex.get("JPEGInterchangeFormatLength")
        if isinstance(toff, int) and isinstance(tlen, int) and 0 < tlen and toff + tlen <= len(tiff):
            ex.thumb = tiff[toff:toff + tlen]
    return ex


def find_exif_segment(data, segs):
    for m, s, en in segs:
        if m == 0xE1 and data[s + 4:s + 10] == b"Exif\0\0":
            return s, en
    return None


def exif_from_jpeg_header(data, segs):
    seg = find_exif_segment(data, segs)
    if not seg:
        return None
    s, en = seg
    return parse_exif_tiff(data[s + 10:en])


def pretty_exif(name, value):
    """Human-friendly rendering of an EXIF value (keeps the raw value visible when it helps)."""
    def rat(v):
        if isinstance(v, tuple) and len(v) == 2 and all(isinstance(x, int) for x in v):
            return v[0] / v[1] if v[1] else float("inf")
        return None

    if name in ENUMS and isinstance(value, int):
        return f"{ENUMS[name].get(value, '?')} ({value})"
    if name == "Flash" and isinstance(value, int):
        return f"{'Fired' if value & 1 else 'Did not fire'}{', auto' if value & 0x18 == 0x18 else ''} ({value})"
    r = rat(value)
    if r is not None:
        if name == "ExposureTime":
            return f"1/{round(1 / r)} s" if 0 < r < 1 else f"{r:g} s"
        if name in ("FNumber", "MaxApertureValue"):
            return f"f/{r:.1f}"
        if name in ("FocalLength",):
            return f"{r:g} mm"
        if name == "ExposureBiasValue":
            return f"{r:+.1f} EV"
        if name == "GPSAltitude":
            return f"{r:.1f} m"
        return f"{r:g}  ({value[0]}/{value[1]})"
    if name in ("GPSLatitude", "GPSLongitude") and isinstance(value, tuple) and len(value) == 3:
        try:
            d, m, s = [v[0] / v[1] if v[1] else 0 for v in value]
            return f"{d + m / 60 + s / 3600:.6f}°  ({d:g}° {m:g}' {s:g}\")"
        except Exception:
            pass
    if name == "GPSTimeStamp" and isinstance(value, tuple) and len(value) == 3:
        try:
            h, m, s = [v[0] / v[1] if v[1] else 0 for v in value]
            return f"{int(h):02d}:{int(m):02d}:{s:05.2f} UTC"
        except Exception:
            pass
    if name == "LensSpecification" and isinstance(value, tuple):
        try:
            return ", ".join(f"{v[0] / v[1]:g}" if v[1] else "?" for v in value)
        except Exception:
            pass
    if isinstance(value, tuple) and len(value) > 24:
        return f"<{len(value)} values>"
    return str(value)


def exif_datetime(ex):
    """(datetime, source_field) from an ExifData, or (None, None)."""
    if ex is None:
        return None, None
    for field in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
        v = ex.get(field)
        if isinstance(v, str):
            m = re.match(r"(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", v)
            if m:
                try:
                    return datetime.datetime(*map(int, m.groups())), field
                except ValueError:
                    continue
            m = re.match(r"(\d{4}):(\d{2}):(\d{2})", v)
            if m:
                try:
                    return datetime.datetime(*map(int, m.groups())), field
                except ValueError:
                    continue
    return None, None


# ── PNG / MP4 metadata ──────────────────────────
def png_info(path):
    """dims + text chunks of a PNG."""
    info = {"width": None, "height": None, "text": []}
    with open(path, "rb") as fh:
        if fh.read(8) != b"\x89PNG\r\n\x1a\n":
            return info
        while True:
            hdr = fh.read(8)
            if len(hdr) < 8:
                break
            length, ctype = struct.unpack(">I4s", hdr)
            if ctype == b"IHDR":
                d = fh.read(length)
                info["width"], info["height"] = struct.unpack(">II", d[:8])
                info["bit_depth"], info["color_type"] = d[8], d[9]
            elif ctype in (b"tEXt", b"zTXt", b"iTXt") and length < 1_000_000:
                d = fh.read(length)
                try:
                    if ctype == b"tEXt":
                        k, v = d.split(b"\0", 1)
                        info["text"].append((k.decode("latin-1"), v.decode("latin-1", "replace")))
                    elif ctype == b"zTXt":
                        import zlib
                        k, rest = d.split(b"\0", 1)
                        info["text"].append((k.decode("latin-1"), zlib.decompress(rest[1:]).decode("latin-1", "replace")))
                    else:
                        k, rest = d.split(b"\0", 1)
                        comp, _, rest2 = rest[0], rest[1], rest[2:]
                        _, _, txt = rest2.split(b"\0", 2)
                        if comp:
                            import zlib
                            txt = zlib.decompress(txt)
                        info["text"].append((k.decode("latin-1"), txt.decode("utf-8", "replace")))
                except Exception:
                    pass
            elif ctype == b"IDAT" or ctype == b"IEND":
                if ctype == b"IEND":
                    break
                fh.seek(length, 1)
            else:
                fh.seek(length, 1)
            fh.read(4)  # crc
    return info


def mp4_info(path):
    """Creation time + dims from an MP4/MOV 'moov' box. Returns dict."""
    info = {"created": None, "duration": None, "width": None, "height": None, "boxes": []}
    size_total = os.path.getsize(path)

    def walk(fh, start, end, depth, want):
        pos = start
        while pos + 8 <= end:
            fh.seek(pos)
            hdr = fh.read(8)
            if len(hdr) < 8:
                break
            size, typ = struct.unpack(">I4s", hdr)
            hlen = 8
            if size == 1:
                size = struct.unpack(">Q", fh.read(8))[0]
                hlen = 16
            elif size == 0:
                size = end - pos
            if size < hlen:
                break
            name = typ.decode("latin-1", "replace")
            if depth == 0:
                info["boxes"].append(f"{name} ({fmt_size(size)})")
            if name in ("moov", "trak", "mdia", "minf", "stbl", "udta"):
                walk(fh, pos + hlen, min(pos + size, end), depth + 1, want)
            elif name == "mvhd":
                d = fh.read(min(size - hlen, 120))
                ver = d[0]
                if ver == 1:
                    ctime, _, scale, dur = struct.unpack(">QQIQ", d[4:32])
                else:
                    ctime, _, scale, dur = struct.unpack(">IIII", d[4:20])
                if ctime:
                    try:
                        info["created"] = datetime.datetime.fromtimestamp(ctime - 2082844800)
                    except (OverflowError, OSError, ValueError):
                        pass
                if scale:
                    info["duration"] = dur / scale
            elif name == "tkhd":
                d = fh.read(min(size - hlen, 100))
                ver = d[0]
                base = 4 + (32 if ver == 1 else 20) + 8 + 8 + 2 + 2 + 2 + 2 + 36
                if len(d) >= base + 8:
                    w, h = struct.unpack(">II", d[base:base + 8])
                    w, h = w >> 16, h >> 16
                    if w and h and not info["width"]:
                        info["width"], info["height"] = w, h
            elif name == "\xa9day" or name == "©day":
                d = fh.read(min(size - hlen, 64))
                m = re.search(rb"(\d{4})-(\d{2})-(\d{2})", d)
                if m and not info["created"]:
                    try:
                        info["created"] = datetime.datetime(*map(int, m.groups()))
                    except ValueError:
                        pass
            pos += size

    with open(path, "rb") as fh:
        walk(fh, 0, size_total, 0, None)
    return info


def date_from_filename(stem):
    m = re.search(r"(?<!\d)(20\d{2}|19\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])(?!\d)", stem)
    if m:
        try:
            return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


# ─────────────────────────────────────────────
# EXIF WRITING  (append-only strategy: existing offsets are never moved)
# ─────────────────────────────────────────────
# A tag's new value is written in place when it fits, otherwise appended at the
# end of the TIFF block and the entry re-pointed. A brand-new tag rebuilds just
# its IFD at the end of the block and re-points the single pointer to it, so
# MakerNotes and every other offset-based blob stay exactly where they were.

EDITABLE_TAGS = {  # name: (ifd, tag, type)
    "DateTimeOriginal": ("ExifIFD", 0x9003, 2),
    "DateTimeDigitized": ("ExifIFD", 0x9004, 2),
    "DateTime": ("IFD0", 0x0132, 2),
    "ImageDescription": ("IFD0", 0x010E, 2),
    "Artist": ("IFD0", 0x013B, 2),
    "Copyright": ("IFD0", 0x8298, 2),
    "Make": ("IFD0", 0x010F, 2),
    "Model": ("IFD0", 0x0110, 2),
    "Software": ("IFD0", 0x0131, 2),
    "UserComment": ("ExifIFD", 0x9286, 7),
    "XPTitle": ("IFD0", 0x9C9B, 1),
    "XPComment": ("IFD0", 0x9C9C, 1),
    "XPAuthor": ("IFD0", 0x9C9D, 1),
    "XPKeywords": ("IFD0", 0x9C9E, 1),
    "XPSubject": ("IFD0", 0x9C9F, 1),
    "Orientation": ("IFD0", 0x0112, 3),
    "Rating": ("IFD0", 0x4746, 3),
}
IFD_POINTER_TAG = {"ExifIFD": 0x8769, "GPS": 0x8825}


class TiffEditor:
    def __init__(self, tiff=None):
        if tiff is None or len(tiff) < 8:
            tiff = b"II*\0" + struct.pack("<I", 8) + struct.pack("<H", 0) + struct.pack("<I", 0)
        self.b = bytearray(tiff)
        self.e = "<" if self.b[:2] == b"II" else ">"
        if self.b[:2] not in (b"II", b"MM"):
            raise ValueError("Bad TIFF header")

    def u16(self, off):
        return struct.unpack(self.e + "H", self.b[off:off + 2])[0]

    def u32(self, off):
        return struct.unpack(self.e + "I", self.b[off:off + 4])[0]

    def w16(self, off, v):
        self.b[off:off + 2] = struct.pack(self.e + "H", v)

    def w32(self, off, v):
        self.b[off:off + 4] = struct.pack(self.e + "I", v)

    def append(self, data):
        if len(self.b) % 2:
            self.b += b"\0"
        off = len(self.b)
        self.b += data
        return off

    def entries(self, ifd_off):
        n = self.u16(ifd_off)
        out = []
        for k in range(n):
            p = ifd_off + 2 + k * 12
            if p + 12 > len(self.b):
                break
            tag, typ, cnt = struct.unpack(self.e + "HHI", self.b[p:p + 8])
            out.append((p, tag, typ, cnt))
        nxt_pos = ifd_off + 2 + n * 12
        nxt = self.u32(nxt_pos) if nxt_pos + 4 <= len(self.b) else 0
        return out, nxt

    def find_ifd(self, name):
        ifd0 = self.u32(4)
        if name == "IFD0":
            return ifd0 if ifd0 and ifd0 + 2 <= len(self.b) else 0
        if ifd0 == 0 or ifd0 + 2 > len(self.b):
            return 0
        ptag = IFD_POINTER_TAG[name]
        for p, tag, typ, cnt in self.entries(ifd0)[0]:
            if tag == ptag:
                return self.u32(p + 8)
        return 0

    def ensure_ifd(self, name):
        off = self.find_ifd(name)
        if off:
            return off
        empty = struct.pack(self.e + "H", 0) + struct.pack(self.e + "I", 0)
        if name == "IFD0":
            off = self.append(empty)
            self.w32(4, off)
            return off
        self.ensure_ifd("IFD0")
        off = self.append(empty)
        self.set_tag("IFD0", IFD_POINTER_TAG[name], 4, struct.pack(self.e + "I", off), 1)
        return off

    def set_tag(self, ifdname, tag, typ, data, count):
        ifd_off = self.ensure_ifd(ifdname)
        ents, nxt = self.entries(ifd_off)
        for p, otag, otyp, ocnt in ents:
            if otag != tag:
                continue
            old_size = TYPE_SIZE.get(otyp, 1) * ocnt
            if len(data) <= 4:
                self.b[p + 8:p + 12] = data.ljust(4, b"\0")
            elif old_size > 4 and len(data) <= old_size:
                voff = self.u32(p + 8)
                self.b[voff:voff + old_size] = data.ljust(old_size, b"\0")
            else:
                self.w32(p + 8, self.append(data))
            self.w16(p + 2, typ)
            self.w32(p + 4, count)
            return
        # tag not present → rebuild this IFD at the end of the block with the new entry
        if len(data) <= 4:
            valfield = data.ljust(4, b"\0")
        else:
            valfield = struct.pack(self.e + "I", self.append(data))
        new_entry = struct.pack(self.e + "HHI", tag, typ, count) + valfield
        raw_entries = [(t, bytes(self.b[p:p + 12])) for p, t, _, _ in ents] + [(tag, new_entry)]
        raw_entries.sort(key=lambda x: x[0])
        ifd_bytes = struct.pack(self.e + "H", len(raw_entries)) + b"".join(r for _, r in raw_entries) \
            + struct.pack(self.e + "I", nxt)
        new_off = self.append(ifd_bytes)
        if ifdname == "IFD0":
            self.w32(4, new_off)
        else:
            self.set_tag("IFD0", IFD_POINTER_TAG[ifdname], 4, struct.pack(self.e + "I", new_off), 1)

    def remove_tag(self, ifdname, tag):
        ifd_off = self.find_ifd(ifdname)
        if not ifd_off:
            return False
        ents, nxt = self.entries(ifd_off)
        keep = [(t, bytes(self.b[p:p + 12])) for p, t, _, _ in ents if t != tag]
        if len(keep) == len(ents):
            return False
        ifd_bytes = struct.pack(self.e + "H", len(keep)) + b"".join(r for _, r in keep) \
            + struct.pack(self.e + "I", nxt)
        new_off = self.append(ifd_bytes)
        if ifdname == "IFD0":
            self.w32(4, new_off)
        else:
            self.set_tag("IFD0", IFD_POINTER_TAG[ifdname], 4, struct.pack(self.e + "I", new_off), 1)
        return True


def encode_exif_value(name, value, endian):
    """→ (type, count, bytes) for an editable tag."""
    ifd, tag, typ = EDITABLE_TAGS[name]
    if typ == 2:
        data = str(value).encode("utf-8", "replace") + b"\0"
        return 2, len(data), data
    if typ == 1:  # XP* fields: UTF-16LE with terminator, stored as BYTE array
        data = str(value).encode("utf-16-le") + b"\0\0"
        return 1, len(data), data
    if typ == 7:  # UserComment
        s = str(value)
        try:
            data = b"ASCII\0\0\0" + s.encode("ascii")
        except UnicodeEncodeError:
            data = b"UNICODE\0" + s.encode("utf-16-le" if endian == "<" else "utf-16-be")
        return 7, len(data), data
    if typ == 3:
        v = int(value)
        return 3, 1, struct.pack(endian + "H", v)
    raise ValueError(f"Unsupported type for {name}")


def write_exif_fields(path, fields, remove=()):
    """Write {tag_name: value} into a JPEG's EXIF. Creates the APP1 block if missing.
    Verifies the result re-parses before replacing the file. Keeps the file's mtime."""
    with open(path, "rb") as fh:
        data = fh.read()
    segs = jpeg_segments(data)
    seg = find_exif_segment(data, segs)
    tiff = data[seg[0] + 10:seg[1]] if seg else None
    ed = TiffEditor(tiff)
    for name in remove:
        ifd, tag, typ = EDITABLE_TAGS[name]
        ed.remove_tag(ifd, tag)
    for name, value in fields.items():
        ifd, tag, _ = EDITABLE_TAGS[name]
        typ, cnt, raw = encode_exif_value(name, value, ed.e)
        ed.set_tag(ifd, tag, typ, raw, cnt)
    new_tiff = bytes(ed.b)
    payload = b"Exif\0\0" + new_tiff
    if len(payload) + 2 > 65533:
        raise ValueError("EXIF block would exceed the 64 KB segment limit")
    check = parse_exif_tiff(new_tiff)
    if check.error:
        raise ValueError("Internal error: rebuilt EXIF does not parse (" + check.error + ")")
    for name, value in fields.items():
        if EDITABLE_TAGS[name][2] in (1, 2) and str(check.get(name)) != str(value):
            raise ValueError(f"Internal error: verification of {name} failed")
    new_seg = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    if seg:
        out = data[:seg[0]] + new_seg + data[seg[1]:]
    else:
        insert_at = segs[0][2] if segs and segs[0][0] == 0xE0 else 2
        out = data[:insert_at] + new_seg + data[insert_at:]
    st = os.stat(path)
    tmp = path + ".zfa_tmp"
    with open(tmp, "wb") as fh:
        fh.write(out)
    os.replace(tmp, path)
    try:
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    except OSError:
        pass


# ─────────────────────────────────────────────
# BASELINE JPEG DECODER (pure Python) → PPM
# ─────────────────────────────────────────────
# Used for the small EXIF thumbnails (instant grid paint) and, when the Windows
# helper is unavailable, for a 1/8-scale "DC only" render of the full image.

_ZZ = [0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5, 12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14,
       21, 28, 35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51, 58, 59, 52, 45, 38, 31, 39, 46, 53,
       60, 61, 54, 47, 55, 62, 63]
_A = [[(math.sqrt(0.5) if u == 0 else 1.0) * 0.5 * math.cos((2 * x + 1) * u * math.pi / 16)
       for u in range(8)] for x in range(8)]
_CLAMP = bytes(max(0, min(255, i - 512)) for i in range(1280))
_CR_R = [round(1.402 * (i - 128)) for i in range(256)]
_CB_B = [round(1.772 * (i - 128)) for i in range(256)]
_CB_G = [0.344136 * (i - 128) for i in range(256)]
_CR_G = [0.714136 * (i - 128) for i in range(256)]


class _Bits:
    __slots__ = ("d", "n", "pos", "buf", "cnt")

    def __init__(self, data):
        self.d, self.n, self.pos, self.buf, self.cnt = data, len(data), 0, 0, 0

    def bit(self):
        if self.cnt == 0:
            if self.pos < self.n:
                self.buf = self.d[self.pos]
                self.pos += 1
            else:
                self.buf = 0
            self.cnt = 8
        self.cnt -= 1
        return (self.buf >> self.cnt) & 1

    def bits(self, k):
        while self.cnt < k:
            nb = self.d[self.pos] if self.pos < self.n else 0
            self.pos += 1
            self.buf = ((self.buf & ((1 << self.cnt) - 1)) << 8) | nb
            self.cnt += 8
        self.cnt -= k
        return (self.buf >> self.cnt) & ((1 << k) - 1)


def _build_huff(counts, symbols):
    maxcode, mincode, valptr = [-1] * 18, [0] * 18, [0] * 18
    code = k = 0
    for l in range(1, 17):
        n = counts[l - 1]
        if n:
            valptr[l], mincode[l] = k, code
            code += n
            k += n
            maxcode[l] = code - 1
        code <<= 1
    return maxcode, mincode, valptr, symbols


def _idct_block(c):
    rows = []
    for v in range(8):
        base = v * 8
        nz = [(u, c[base + u]) for u in range(8) if c[base + u]]
        if nz:
            rows.append((v, [sum(val * Ax[u] for u, val in nz) for Ax in _A]))
    if not rows:
        return None
    out = [0] * 64
    for y in range(8):
        Ay = _A[y]
        o = y * 8
        for x in range(8):
            s = 0.0
            for v, r in rows:
                s += Ay[v] * r[x]
            out[o + x] = s
    return out


def decode_jpeg(data, dc_only=False, max_pixels=40_000_000):
    """Decode a baseline JPEG → (width, height, rgb_bytes). dc_only → 1/8 scale."""
    qt, ht = {}, {}
    frame = None
    dri = 0
    adobe_transform = None
    segs = jpeg_segments(data)
    scan = None
    for m, s, en in segs:
        p = data[s + 4:en]
        if m == 0xDB:
            i = 0
            while i < len(p):
                pq, tq = p[i] >> 4, p[i] & 15
                i += 1
                if pq:
                    q = list(struct.unpack(">64H", p[i:i + 128]))
                    i += 128
                else:
                    q = list(p[i:i + 64])
                    i += 64
                qt[tq] = q
        elif m == 0xC4:
            i = 0
            while i < len(p):
                tc, th = p[i] >> 4, p[i] & 15
                counts = list(p[i + 1:i + 17])
                total = sum(counts)
                syms = list(p[i + 17:i + 17 + total])
                ht[(tc, th)] = _build_huff(counts, syms)
                i += 17 + total
        elif m in (0xC0, 0xC1):
            prec, h, w, nc = struct.unpack(">BHHB", p[:6])
            comps = []
            for k in range(nc):
                cid, hv, tq = p[6 + k * 3:9 + k * 3]
                comps.append({"id": cid, "h": hv >> 4, "v": hv & 15, "tq": tq})
            frame = (w, h, comps)
        elif m in (0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            raise JpegError("Progressive/lossless/arithmetic JPEG not supported by the built-in decoder")
        elif m == 0xDD:
            dri = struct.unpack(">H", p[:2])[0]
        elif m == 0xEE and p[:5] == b"Adobe":
            adobe_transform = p[11] if len(p) > 11 else None
        elif m == 0xDA:
            ns = p[0]
            sel = {}
            for k in range(ns):
                cid, t = p[1 + k * 2], p[2 + k * 2]
                sel[cid] = (t >> 4, t & 15)
            scan = (sel, en)
    if frame is None or scan is None:
        raise JpegError("Missing frame or scan header")
    W, H, comps = frame
    if W * H > max_pixels:
        raise JpegError("Image too large for the built-in decoder")
    sel, scan_start = scan
    if len(sel) != len(comps):
        raise JpegError("Non-interleaved multi-scan JPEG not supported")
    if len(comps) == 1:
        comps[0]["h"] = comps[0]["v"] = 1
    hmax = max(c["h"] for c in comps)
    vmax = max(c["v"] for c in comps)
    mcux = (W + 8 * hmax - 1) // (8 * hmax)
    mcuy = (H + 8 * vmax - 1) // (8 * vmax)

    # entropy-coded data: split at RST markers, un-stuff FF00
    segments = []
    buf = bytearray()
    i, n = scan_start, len(data)
    while True:
        j = data.find(b"\xff", i)
        if j < 0 or j + 1 >= n:
            buf += data[i:]
            break
        buf += data[i:j]
        nb = data[j + 1]
        if nb == 0:
            buf.append(0xFF)
            i = j + 2
        elif 0xD0 <= nb <= 0xD7:
            segments.append(bytes(buf))
            buf = bytearray()
            i = j + 2
        elif nb == 0xFF:
            i = j + 1
        else:
            break
    segments.append(bytes(buf))

    for c in comps:
        c["dc"], c["ac"] = sel.get(c["id"], (0, 0))
        if (0, c["dc"]) not in ht or (1, c["ac"]) not in ht or c["tq"] not in qt:
            raise JpegError("Missing Huffman/quant table")
        c["q"] = qt[c["tq"]]
        c["cw"] = mcux * c["h"] * (1 if dc_only else 8)
        c["ch"] = mcuy * c["v"] * (1 if dc_only else 8)
        c["plane"] = bytearray(c["cw"] * c["ch"])
        c["pred"] = 0

    seg_i = 0
    br = _Bits(segments[0])
    mcu_count = 0
    ZZ = _ZZ
    CL = _CLAMP

    def decode_block(br, comp):
        maxcode, mincode, valptr, syms = ht[(0, comp["dc"])]
        code, l = br.bit(), 1
        while code > maxcode[l]:
            code = (code << 1) | br.bit()
            l += 1
            if l > 16:
                raise JpegError("Bad Huffman code")
        t = syms[valptr[l] + code - mincode[l]]
        diff = 0
        if t:
            v = br.bits(t)
            diff = v - (1 << t) + 1 if v < (1 << (t - 1)) else v
        comp["pred"] += diff
        q = comp["q"]
        coefs = [0] * 64
        coefs[0] = comp["pred"] * q[0]
        maxcode, mincode, valptr, syms = ht[(1, comp["ac"])]
        k = 1
        has_ac = False
        while k < 64:
            code, l = br.bit(), 1
            while code > maxcode[l]:
                code = (code << 1) | br.bit()
                l += 1
                if l > 16:
                    raise JpegError("Bad Huffman code")
            rs = syms[valptr[l] + code - mincode[l]]
            r, s = rs >> 4, rs & 15
            if s == 0:
                if r == 15:
                    k += 16
                    continue
                break
            k += r
            if k > 63:
                break
            v = br.bits(s)
            coefs[ZZ[k]] = (v - (1 << s) + 1 if v < (1 << (s - 1)) else v) * q[k]
            has_ac = True
            k += 1
        return coefs, has_ac

    for my in range(mcuy):
        for mx in range(mcux):
            if dri and mcu_count and mcu_count % dri == 0:
                seg_i += 1
                if seg_i < len(segments):
                    br = _Bits(segments[seg_i])
                for c in comps:
                    c["pred"] = 0
            for c in comps:
                plane, cw = c["plane"], c["cw"]
                for by in range(c["v"]):
                    for bx in range(c["h"]):
                        coefs, has_ac = decode_block(br, c)
                        if dc_only:
                            plane[(my * c["v"] + by) * cw + mx * c["h"] + bx] = CL[int(coefs[0] / 8) + 128 + 512]
                            continue
                        px = (mx * c["h"] + bx) * 8
                        py = (my * c["v"] + by) * 8
                        if not has_ac:
                            row = bytes([CL[int(coefs[0] / 8) + 128 + 512]]) * 8
                            for yy in range(8):
                                o = (py + yy) * cw + px
                                plane[o:o + 8] = row
                        else:
                            out = _idct_block(coefs)
                            for yy in range(8):
                                o = (py + yy) * cw + px
                                r = out[yy * 8:yy * 8 + 8]
                                plane[o:o + 8] = bytes([CL[int(v) + 640] for v in r])
            mcu_count += 1

    if dc_only:
        OW, OH = (W + 7) // 8, (H + 7) // 8
    else:
        OW, OH = W, H
    out = bytearray(OW * OH * 3)
    if len(comps) == 1:
        c = comps[0]
        for y in range(OH):
            row = c["plane"][y * c["cw"]:y * c["cw"] + OW]
            out[y * OW * 3:(y + 1) * OW * 3] = bytes(v for v in row for _ in (0, 1, 2))
        return OW, OH, bytes(out)
    if len(comps) != 3:
        raise JpegError("CMYK JPEG not supported by the built-in decoder")
    cY, cB, cR = comps
    xsB = [x * cB["h"] // hmax for x in range(OW)]
    xsR = [x * cR["h"] // hmax for x in range(OW)]
    rgb_direct = adobe_transform == 0 or (cY["id"], cB["id"], cR["id"]) == (ord("R"), ord("G"), ord("B"))
    for y in range(OH):
        yY = y * cY["v"] // vmax
        yB = y * cB["v"] // vmax
        yR = y * cR["v"] // vmax
        Yrow = cY["plane"][yY * cY["cw"]:yY * cY["cw"] + OW] if cY["h"] == hmax else \
            bytes(cY["plane"][yY * cY["cw"] + x * cY["h"] // hmax] for x in range(OW))
        Brow_full = cB["plane"][yB * cB["cw"]:(yB + 1) * cB["cw"]]
        Rrow_full = cR["plane"][yR * cR["cw"]:(yR + 1) * cR["cw"]]
        o = y * OW * 3
        if rgb_direct:
            for x in range(OW):
                out[o] = Yrow[x]
                out[o + 1] = Brow_full[xsB[x]]
                out[o + 2] = Rrow_full[xsR[x]]
                o += 3
        else:
            for x in range(OW):
                yv = Yrow[x]
                cb = Brow_full[xsB[x]]
                cr = Rrow_full[xsR[x]]
                out[o] = CL[yv + _CR_R[cr] + 512]
                out[o + 1] = CL[yv - int(_CB_G[cb] + _CR_G[cr]) + 512]
                out[o + 2] = CL[yv + _CB_B[cb] + 512]
                o += 3
    return OW, OH, bytes(out)


def apply_orientation(w, h, rgb, orient):
    """Rotate/flip raw RGB bytes according to EXIF orientation 1-8."""
    if orient in (0, 1) or orient not in range(2, 9):
        return w, h, rgb
    mv = memoryview(rgb)
    px = [mv[i * 3:i * 3 + 3] for i in range(w * h)]
    if orient == 2:
        nw, nh = w, h
        src = lambda x, y: (w - 1 - x, y)
    elif orient == 3:
        nw, nh = w, h
        src = lambda x, y: (w - 1 - x, h - 1 - y)
    elif orient == 4:
        nw, nh = w, h
        src = lambda x, y: (x, h - 1 - y)
    elif orient == 5:
        nw, nh = h, w
        src = lambda x, y: (y, x)
    elif orient == 6:
        nw, nh = h, w
        src = lambda x, y: (y, h - 1 - x)
    elif orient == 7:
        nw, nh = h, w
        src = lambda x, y: (w - 1 - y, h - 1 - x)
    else:  # 8
        nw, nh = h, w
        src = lambda x, y: (w - 1 - y, x)
    out = bytearray()
    for y in range(nh):
        for x in range(nw):
            sx, sy = src(x, y)
            out += px[sy * w + sx]
    return nw, nh, bytes(out)


def rgb_to_ppm(w, h, rgb):
    return b"P6 %d %d 255\n" % (w, h) + rgb


# ─────────────────────────────────────────────
# MEDIA INFO (cheap header read per file)
# ─────────────────────────────────────────────
def read_media_info(path):
    """Header-only scan: dims, orientation, EXIF, 'taken' date + its source, progressive flag."""
    ext = os.path.splitext(path)[1].lower()
    info = {"width": None, "height": None, "orientation": 1, "exif": None, "taken": None,
            "taken_src": None, "progressive": False, "has_thumb": False, "error": None,
            "kind": "video" if ext in VIDEO_EXT else "image"}
    try:
        if ext in JPEG_EXT:
            data, segs = read_jpeg_header(path)
            for m, s, en in segs:
                if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    _, h, w, _ = struct.unpack(">BHHB", data[s + 4:s + 10])
                    info["width"], info["height"] = w, h
                    info["progressive"] = m not in (0xC0, 0xC1)
                    break
            ex = exif_from_jpeg_header(data, segs)
            if ex:
                info["exif"] = ex
                o = ex.get("Orientation")
                if isinstance(o, int) and 1 <= o <= 8:
                    info["orientation"] = o
                info["has_thumb"] = bool(ex.thumb)
                dt, src = exif_datetime(ex)
                if dt:
                    info["taken"], info["taken_src"] = dt, "EXIF " + src
        elif ext == ".png":
            pi = png_info(path)
            info["width"], info["height"] = pi["width"], pi["height"]
        elif ext in (".mp4", ".mov", ".m4v", ".3gp"):
            mi = mp4_info(path)
            info["width"], info["height"] = mi["width"], mi["height"]
            if mi["created"]:
                info["taken"], info["taken_src"] = mi["created"], "video header"
    except Exception as e:  # never let one odd file break the scan
        info["error"] = str(e)
    if not info["taken"]:
        dt = date_from_filename(os.path.splitext(os.path.basename(path))[0])
        if dt:
            info["taken"], info["taken_src"] = dt, "file name"
    return info


# ─────────────────────────────────────────────
# NAME MODEL   {date}_{label}_{label}_{core}{ext}
# ─────────────────────────────────────────────
DATE_TOKEN_RE = re.compile(r"^(\d{8}|\d{6}XX)$")
CORE_RES = [re.compile(p, re.I) for p in (
    r"IMG[_-]?E?\d{3,}(?:[_-].*)?", r"DSC[_-]?[A-Z]*\d{3,}(?:[_-].*)?", r"DSCN\d+.*",
    r"PXL_\d{8}_\d{6,}.*", r"P\d{7,}.*", r"MVI[_-]?\d+.*", r"VID[_-]?\d{3,}.*", r"MOV[_-]?\d+.*",
    r"\d{8}_\d{6}.*", r"\d{4}-\d{2}-\d{2}.*", r"Screenshot.*", r"IMG-\d{8}-WA\d+.*", r"VID-\d{8}-WA\d+.*",
    r"GOPR\d+.*", r"G[HXP]\d{6,}.*", r"signal-\d{4}.*", r"WIN_\d{8}_\d{2}_\d{2}_\d{2}.*",
    r"image\d*", r"photo\d*", r"picture\d*", r"\d{3,}", r"[A-Z]{2,4}\d{4,}(?:[_-].*)?",
)]


def is_date_token(tok):
    if not DATE_TOKEN_RE.match(tok):
        return False
    if tok.endswith("XX"):
        return True
    try:
        datetime.datetime.strptime(tok, "%Y%m%d")
        return True
    except ValueError:
        return False


def parse_name(stem):
    """stem → (date, [labels], core). The core is the camera's original name (IMG_1234…)."""
    tokens = stem.split("_")
    n = len(tokens)
    core_i = None
    for i in range(n):
        cand = "_".join(tokens[i:])
        if any(r.fullmatch(cand) for r in CORE_RES):
            core_i = i
            break
    if core_i is None:
        # No camera pattern: only trust the {date}_{labels}_{core} split when the
        # name already starts with a date prefix (i.e. was made by this scheme).
        core_i = n - 1 if (n > 1 and is_date_token(tokens[0])) else 0
    head = tokens[:core_i]
    core = "_".join(tokens[core_i:])
    date = ""
    if head and is_date_token(head[0]):
        date = head[0]
        head = head[1:]
    labels = [t for t in head if t]
    return date, labels, core


def sanitize_label(s):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s)
    s = re.sub(r"[\s_]+", "-", s.strip())
    return s.strip("-")


def sanitize_core(s):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s).strip()
    return s


class Photo:
    def __init__(self, folder, name):
        self.folder = folder
        self.name = name
        self.path = os.path.join(folder, name)
        self.stem, self.ext = os.path.splitext(name)
        ext = self.ext.lower()
        self.kind = "video" if ext in VIDEO_EXT else "image"
        try:
            st = os.stat(self.path)
            self.size, self.mtime = st.st_size, st.st_mtime
        except OSError:
            self.size, self.mtime = 0, 0
        self.key = None
        self.info = None
        self.sugg_date = ""          # YYYYMMDD suggested from metadata / name
        self.sugg_src = ""
        self.o_date, self.o_labels, self.o_core = parse_name(self.stem)
        self.date, self.labels, self.core = self.o_date, list(self.o_labels), self.o_core
        self.thumb_py = None
        self.thumb_wic = None
        self.preview = None
        self.thumb_failed = False

    def refresh_from_disk_name(self):
        self.stem, self.ext = os.path.splitext(self.name)
        self.path = os.path.join(self.folder, self.name)
        self.o_date, self.o_labels, self.o_core = parse_name(self.stem)
        self.date, self.labels, self.core = self.o_date, list(self.o_labels), self.o_core

    def proposed(self):
        parts = ([self.date] if self.date else []) + list(self.labels) + [self.core or self.o_core or "file"]
        return "_".join(parts) + self.ext

    def pending(self):
        return self.proposed() != self.name

    def reset(self):
        self.date, self.labels, self.core = self.o_date, list(self.o_labels), self.o_core

    def file_date(self):
        return datetime.datetime.fromtimestamp(self.mtime).strftime("%Y%m%d") if self.mtime else ""

    def best_thumb(self):
        return self.thumb_wic or self.thumb_py

    def compute_key(self):
        try:
            with open(self.path, "rb") as fh:
                head = fh.read(4096)
            st = os.stat(self.path)
            h = hashlib.sha1(f"{st.st_size}:{st.st_mtime_ns}".encode())
            h.update(head)
            self.key = h.hexdigest()[:20]
        except OSError:
            self.key = None
        return self.key


# ─────────────────────────────────────────────
# THUMBNAIL SERVICE
# ─────────────────────────────────────────────
PS_HELPER = r'''
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName PresentationCore
$ErrorActionPreference = 'Stop'
function Load-Bitmap($src, $max) {
  $fs = [System.IO.File]::Open($src, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
  try {
    $dec = [System.Windows.Media.Imaging.BitmapDecoder]::Create($fs, [System.Windows.Media.Imaging.BitmapCreateOptions]::IgnoreColorProfile, [System.Windows.Media.Imaging.BitmapCacheOption]::None)
    $w = $dec.Frames[0].PixelWidth; $h = $dec.Frames[0].PixelHeight
  } finally { $fs.Dispose() }
  $fs = [System.IO.File]::Open($src, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
  try {
    $bi = New-Object System.Windows.Media.Imaging.BitmapImage
    $bi.BeginInit()
    $bi.StreamSource = $fs
    $bi.CacheOption = [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad
    $bi.CreateOptions = [System.Windows.Media.Imaging.BitmapCreateOptions]::IgnoreColorProfile
    if ($w -ge $h) { if ($w -gt $max) { $bi.DecodePixelWidth = $max } } else { if ($h -gt $max) { $bi.DecodePixelHeight = $max } }
    $bi.EndInit()
    $bi.Freeze()
  } finally { $fs.Dispose() }
  return $bi
}
[Console]::Out.WriteLine('READY')
[Console]::Out.Flush()
while ($true) {
  $line = [Console]::In.ReadLine()
  if ($null -eq $line -or $line -eq 'QUIT') { break }
  $p = $line.Split('|')
  if ($p.Length -lt 4) { continue }
  $src = $p[0]; $dst = $p[1]; $max = [int]$p[2]; $orient = [int]$p[3]
  try {
    $bi = Load-Bitmap $src $max
    $img = $bi
    $tg = New-Object System.Windows.Media.TransformGroup
    switch ($orient) {
      2 { $tg.Children.Add((New-Object System.Windows.Media.ScaleTransform(-1, 1))) }
      3 { $tg.Children.Add((New-Object System.Windows.Media.RotateTransform(180))) }
      4 { $tg.Children.Add((New-Object System.Windows.Media.ScaleTransform(1, -1))) }
      5 { $tg.Children.Add((New-Object System.Windows.Media.ScaleTransform(-1, 1))); $tg.Children.Add((New-Object System.Windows.Media.RotateTransform(270))) }
      6 { $tg.Children.Add((New-Object System.Windows.Media.RotateTransform(90))) }
      7 { $tg.Children.Add((New-Object System.Windows.Media.ScaleTransform(-1, 1))); $tg.Children.Add((New-Object System.Windows.Media.RotateTransform(90))) }
      8 { $tg.Children.Add((New-Object System.Windows.Media.RotateTransform(270))) }
    }
    if ($tg.Children.Count -gt 0) { $img = New-Object System.Windows.Media.Imaging.TransformedBitmap($bi, $tg) }
    $enc = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
    $enc.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($img))
    $tmp = $dst + '.tmp'
    $out = [System.IO.File]::Create($tmp)
    try { $enc.Save($out) } finally { $out.Dispose() }
    Move-Item -LiteralPath $tmp -Destination $dst -Force
    [Console]::Out.WriteLine('OK|' + $dst)
  } catch {
    [Console]::Out.WriteLine('ERR|' + $dst + '|' + $_.Exception.Message.Replace("`r"," ").Replace("`n"," "))
  }
  [Console]::Out.Flush()
}
'''


class ThumbService:
    """Background thumbnail/preview production. Results are posted to app.q as tuples."""

    def __init__(self, app):
        self.app = app
        self.lock = threading.Lock()
        self.photos = []
        self.gen = 0
        self.order = []
        self.done = {"py": set(), "wic": set()}
        self.inflight = {"py": set(), "wic": set()}
        self.preview_req = None
        self.wake = threading.Event()
        self.wic_ok = sys.platform == "win32" and shutil.which("powershell") is not None
        self.wic_state = "starting" if self.wic_ok else "unavailable"
        self.proc = None
        os.makedirs(CACHE_DIR, exist_ok=True)
        threading.Thread(target=self._py_worker, daemon=True).start()
        if self.wic_ok:
            threading.Thread(target=self._wic_worker, daemon=True).start()

    # ── UI-thread API ──
    def set_photos(self, photos, gen):
        with self.lock:
            self.photos = photos
            self.gen = gen
            self.order = list(range(len(photos)))
            for k in self.done:
                self.done[k].clear()
                self.inflight[k].clear()
            self.preview_req = None
        self.wake.set()

    def set_order(self, order):
        with self.lock:
            self.order = order
        self.wake.set()

    def request_preview(self, idx):
        with self.lock:
            self.preview_req = idx
        self.wake.set()

    def stop(self):
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.stdin.write("QUIT\n")
                self.proc.stdin.flush()
        except Exception:
            pass

    # ── worker helpers ──
    def _pop(self, kind):
        with self.lock:
            done, infl = self.done[kind], self.inflight[kind]
            for i in self.order:
                if i in done or i in infl:
                    continue
                if i >= len(self.photos):
                    continue
                p = self.photos[i]
                ext = p.ext.lower()
                if kind == "py" and ext not in JPEG_EXT:
                    done.add(i)
                    continue
                if kind == "wic" and (p.kind == "video" or ext not in IMAGE_EXT):
                    done.add(i)
                    continue
                infl.add(i)
                return self.gen, i, p
        return None

    def _finish(self, kind, i):
        with self.lock:
            self.inflight[kind].discard(i)
            self.done[kind].add(i)

    def _py_worker(self):
        while True:
            job = self._pop("py")
            if job is None:
                self.wake.wait(0.3)
                self.wake.clear()
                continue
            gen, i, p = job
            path = None
            try:
                path = self._make_py_thumb(p)
            except Exception:
                path = None
            self._finish("py", i)
            self.app.q.put(("py_thumb", gen, i, path))

    def _make_py_thumb(self, p):
        if p.key is None:
            p.compute_key()
        if p.key is None:
            return None
        out = os.path.join(CACHE_DIR, f"{p.key}_py.ppm")
        if os.path.exists(out):
            return out
        data, segs = read_jpeg_header(p.path)
        ex = exif_from_jpeg_header(data, segs)
        orient = p.info["orientation"] if p.info else 1
        rgb = None
        if ex and ex.thumb:
            try:
                w, h, rgb = decode_jpeg(ex.thumb)
            except Exception:
                rgb = None
        if rgb is None and not self.wic_ok:
            with open(p.path, "rb") as fh:
                full = fh.read()
            w, h, rgb = decode_jpeg(full, dc_only=True)
        if rgb is None:
            return None
        w, h, rgb = apply_orientation(w, h, rgb, orient)
        tmp = out + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(rgb_to_ppm(w, h, rgb))
        os.replace(tmp, out)
        return out

    def _start_proc(self):
        script = os.path.join(CACHE_DIR, "zfa_wic_helper.ps1")
        with open(script, "w", encoding="utf-8-sig") as fh:
            fh.write(PS_HELPER)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            ["powershell", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", script],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1, creationflags=flags)
        line = self.proc.stdout.readline()
        if line.strip() != "READY":
            raise RuntimeError("helper did not start")

    def _wic_worker(self):
        try:
            self._start_proc()
            self.wic_state = "ok"
        except Exception:
            self.wic_ok = False
            self.wic_state = "failed"
            self.app.q.put(("wic_state", "failed"))
            return
        self.app.q.put(("wic_state", "ok"))
        while True:
            # previews jump the queue
            with self.lock:
                pv = self.preview_req
                self.preview_req = None
                gen = self.gen
                p = self.photos[pv] if pv is not None and pv < len(self.photos) else None
            if p is not None:
                self._run_job(gen, pv, p, PREVIEW_PX, "wic_preview")
                continue
            job = self._pop("wic")
            if job is None:
                self.wake.wait(0.3)
                self.wake.clear()
                continue
            gen, i, p = job
            self._run_job(gen, i, p, THUMB_PX, "wic_thumb")
            self._finish("wic", i)

    def _run_job(self, gen, i, p, px, tag):
        if p.key is None:
            p.compute_key()
        if p.key is None:
            self.app.q.put((tag, gen, i, None))
            return
        dst = os.path.join(CACHE_DIR, f"{p.key}_{px}.png")
        if os.path.exists(dst):
            self.app.q.put((tag, gen, i, dst))
            return
        orient = p.info["orientation"] if p.info else 1
        try:
            self.proc.stdin.write(f"{p.path}|{dst}|{px}|{orient}\n")
            self.proc.stdin.flush()
            resp = self.proc.stdout.readline()
        except Exception:
            resp = ""
        if not resp:
            self.wic_ok = False
            self.wic_state = "died"
            self.app.q.put(("wic_state", "died"))
            self.app.q.put((tag, gen, i, None))
            return
        ok = resp.startswith("OK|") and os.path.exists(dst)
        self.app.q.put((tag, gen, i, dst if ok else None))


# ─────────────────────────────────────────────
# SMALL GUI HELPERS
# ─────────────────────────────────────────────
PAD = 8
SEL_COLOR = "#0a64c8"
SEL_FILL = "#dce9fb"
PEND_COLOR = "#d97706"
TILE_FILL = "#f7f7f7"
TILE_LINE = "#d0d0d0"


def fit_photo(src, box):
    """Scale a PhotoImage down to fit `box` px using zoom/subsample (never upscales)."""
    w, h = src.width(), src.height()
    m = max(w, h, 1)
    if m <= box:
        return src
    best = None
    for z in (1, 2, 3):
        s = -(-m * z // box)
        size = m * z / s
        if best is None or size > best[0] + 0.5:
            best = (size, z, s)
        if size >= box * 0.92:
            break
    _, z, s = best
    img = src.zoom(z, z) if z > 1 else src
    return img.subsample(s, s)


def load_photoimage(path):
    return tk.PhotoImage(file=path)


def fit_text(s, max_chars):
    if len(s) <= max_chars:
        return s
    keep = max(4, max_chars - 1)
    return s[:keep // 2] + "…" + s[-(keep - keep // 2):]


class ScrollFrame(ttk.Frame):
    """A vertically scrollable frame (canvas + inner frame)."""

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.inner_id, width=e.width))
        for w in (self.canvas, self.inner):
            w.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
            w.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), "units")


class ReportWindow(tk.Toplevel):
    """Read-only text report with Find + Save (the v2 console printouts live here)."""

    def __init__(self, master, title, text, save_name=None, save_dir=None):
        super().__init__(master)
        self.title(title)
        self.geometry("900x640")
        self.save_name, self.save_dir = save_name, save_dir
        bar = ttk.Frame(self, padding=(6, 4))
        bar.pack(fill="x")
        ttk.Label(bar, text="Find:").pack(side="left")
        self.find_var = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.find_var, width=28)
        ent.pack(side="left", padx=4)
        ent.bind("<Return>", lambda e: self.find())
        ttk.Button(bar, text="Find next", command=self.find).pack(side="left")
        self.count_lbl = ttk.Label(bar, text="")
        self.count_lbl.pack(side="left", padx=8)
        ttk.Button(bar, text="Close", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="Copy all", command=self.copy_all).pack(side="right", padx=4)
        ttk.Button(bar, text="Save…", command=self.save).pack(side="right")
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True)
        self.text = tk.Text(frame, wrap="none", font=("Consolas", 10), undo=False)
        vs = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        hs = ttk.Scrollbar(frame, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.text.tag_configure("h", font=("Consolas", 11, "bold"), foreground="#0a5ea8")
        self.text.tag_configure("dim", foreground="#777")
        self.text.tag_configure("hit", background="#ffe88a")
        self.set_text(text)
        self._last = "1.0"

    def set_text(self, text):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for line in text.split("\n"):
            if line.startswith("## "):
                self.text.insert("end", line[3:] + "\n", "h")
            elif line.startswith("~~ "):
                self.text.insert("end", line[3:] + "\n", "dim")
            else:
                self.text.insert("end", line + "\n")
        self.text.configure(state="disabled")

    def get_text(self):
        return self.text.get("1.0", "end-1c")

    def find(self):
        term = self.find_var.get()
        self.text.tag_remove("hit", "1.0", "end")
        if not term:
            return
        pos = self.text.search(term, self._last, nocase=True, stopindex="end")
        if not pos:
            pos = self.text.search(term, "1.0", nocase=True, stopindex="end")
            if not pos:
                self.count_lbl.configure(text="not found")
                return
        end = f"{pos}+{len(term)}c"
        self.text.tag_add("hit", pos, end)
        self.text.see(pos)
        self._last = end
        self.count_lbl.configure(text="")

    def copy_all(self):
        self.clipboard_clear()
        self.clipboard_append(self.get_text())

    def save(self):
        path = filedialog.asksaveasfilename(parent=self, initialdir=self.save_dir or os.getcwd(),
                                            initialfile=self.save_name or "report.txt",
                                            defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.get_text())
            messagebox.showinfo("Saved", f"Saved to:\n{path}", parent=self)


class ConfirmRenameDialog(tk.Toplevel):
    """Shows every old → new rename with conflict checks. Nothing is renamed until OK."""

    def __init__(self, master, pairs, title="Confirm renames", extra_widget=None):
        super().__init__(master)
        self.title(title)
        self.geometry("980x560")
        self.transient(master)
        self.result = False
        self.pairs = pairs
        problems = self._check(pairs)
        ttk.Label(self, text=f"{len(pairs)} file(s) will be renamed. Nothing has been changed yet.",
                  font=("Segoe UI", 10, "bold"), padding=(8, 6)).pack(anchor="w")
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8)
        cols = ("old", "new", "status")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        self.tree.heading("old", text="Current name")
        self.tree.heading("new", text="New name")
        self.tree.heading("status", text="Check")
        self.tree.column("old", width=380)
        self.tree.column("new", width=420)
        self.tree.column("status", width=130)
        vs = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("bad", foreground="#c00000")
        for (old, new), prob in zip(pairs, problems):
            self.tree.insert("", "end", values=(os.path.basename(old), os.path.basename(new), prob or "ok"),
                             tags=("bad",) if prob else ())
        n_bad = sum(1 for p in problems if p)
        if extra_widget:
            extra_widget(self).pack(anchor="w", padx=8, pady=(6, 0))
        bar = ttk.Frame(self, padding=8)
        bar.pack(fill="x")
        if n_bad:
            ttk.Label(bar, text=f"{n_bad} conflict(s) — fix them before applying.", foreground="#c00000").pack(side="left")
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right")
        self.ok_btn = ttk.Button(bar, text="Apply renames", command=self._ok, state="disabled" if n_bad else "normal")
        self.ok_btn.pack(side="right", padx=6)
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.wait_window()

    @staticmethod
    def _check(pairs):
        problems = []
        targets = {}
        for old, new in pairs:
            targets.setdefault(os.path.normcase(new), []).append(old)
        olds = {os.path.normcase(o) for o, _ in pairs}
        for old, new in pairs:
            base = os.path.basename(new)
            prob = ""
            if not base or base in (".", ".."):
                prob = "empty name"
            elif re.search(r'[<>:"/\\|?*\x00-\x1f]', base):
                prob = "invalid character"
            elif base.endswith((" ", ".")):
                prob = "ends with space/dot"
            elif len(targets[os.path.normcase(new)]) > 1:
                prob = "duplicate target"
            elif os.path.normcase(new) != os.path.normcase(old) and os.path.exists(new) \
                    and os.path.normcase(new) not in olds:
                prob = "target exists"
            elif not os.path.exists(old):
                prob = "source missing"
            problems.append(prob)
        return problems

    def _ok(self):
        self.result = True
        self.destroy()


def perform_renames(pairs):
    """Rename [(old_path, new_path)]. Two-phase when targets overlap sources. Returns (done_pairs, errors)."""
    olds = {os.path.normcase(o) for o, _ in pairs}
    overlap = any(os.path.normcase(n) in olds and os.path.normcase(n) != os.path.normcase(o) for o, n in pairs)
    done, errors = [], []
    if overlap:
        temps = []
        for old, new in pairs:
            tmp = old + f".zfa_{os.getpid()}_{len(temps)}.tmp"
            try:
                os.rename(old, tmp)
                temps.append((old, tmp, new))
            except OSError as e:
                errors.append(f"{os.path.basename(old)}: {e}")
        for old, tmp, new in temps:
            try:
                os.rename(tmp, new)
                done.append((old, new))
            except OSError as e:
                errors.append(f"{os.path.basename(old)}: {e}")
                try:
                    os.rename(tmp, old)
                except OSError:
                    errors.append(f"  !! could not restore {os.path.basename(old)} from {tmp}")
        return done, errors
    for old, new in pairs:
        if os.path.normcase(old) == os.path.normcase(new) and old == new:
            continue
        try:
            os.rename(old, new)
            done.append((old, new))
        except OSError as e:
            errors.append(f"{os.path.basename(old)}: {e}")
    return done, errors


# ─────────────────────────────────────────────
# FILE SELECTION DIALOG  (v2's selection gate, as a dialog)
# ─────────────────────────────────────────────
def _norm_ext(token):
    token = token.strip().lower()
    if not token:
        return ""
    return token if token.startswith(".") else "." + token


def _expand_number_spec(tokens, count):
    picked = []
    for part in tokens:
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            return None
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if not (1 <= start <= count) or not (1 <= end <= count):
            return None
        step = 1 if end >= start else -1
        for n in range(start, end + step, step):
            if n - 1 not in picked:
                picked.append(n - 1)
    return picked or None


def _apply_ext_filter(files, tokens):
    include, exclude = set(), set()
    for t in tokens:
        if t.startswith("!"):
            ext = _norm_ext(t[1:])
            if ext:
                exclude.add(ext)
        else:
            ext = _norm_ext(t)
            if ext:
                include.add(ext)
    if not include and not exclude:
        return None
    chosen = []
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if include and ext not in include:
            continue
        if ext in exclude:
            continue
        chosen.append(f)
    return chosen


def select_by_spec(files, raw):
    """Apply the v2 selection syntax to a list of names. Returns (chosen, how) or (None, error)."""
    raw = raw.strip()
    if not raw:
        return list(files), "all"
    tokens = [t for t in re.split(r"[,\s]+", raw) if t]
    if any("*" in t or "?" in t for t in tokens):
        chosen = [f for f in files if any(fnmatch.fnmatch(f.lower(), t.lower()) for t in tokens)]
        return chosen, "wildcard"
    if all(re.fullmatch(r"\d+(?:-\d+)?", t) for t in tokens):
        idx = _expand_number_spec(tokens, len(files))
        if idx is None:
            return None, f"Numbers must be between 1 and {len(files)} — e.g. 1,3,5-8"
        return [files[i] for i in idx], "by number"
    chosen = _apply_ext_filter(files, tokens)
    if chosen is None:
        return None, "Could not read that selection. Use .jpg / !.txt / 1,3,5-8 / *name*"
    return chosen, "by extension"


class FileSelectDialog(tk.Toplevel):
    def __init__(self, master, files, title, action="this action", preselect=None):
        super().__init__(master)
        self.title(title)
        self.geometry("720x560")
        self.transient(master)
        self.files = list(files)
        self.result = None
        ttk.Label(self, text=f"Which files should {action} apply to?", font=("Segoe UI", 10, "bold"),
                  padding=(8, 6)).pack(anchor="w")
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8)
        self.lb = tk.Listbox(frame, selectmode="extended", font=("Consolas", 10), activestyle="none")
        vs = ttk.Scrollbar(frame, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=vs.set)
        self.lb.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        width = len(str(len(self.files)))
        for i, f in enumerate(self.files, 1):
            self.lb.insert("end", f"[{i:>{width}}] {f}")
        pre = set(preselect or [])
        for i, f in enumerate(self.files):
            if not pre or f in pre:
                self.lb.selection_set(i)
        spec = ttk.Frame(self, padding=(8, 6))
        spec.pack(fill="x")
        ttk.Label(spec, text="Selection:").pack(side="left")
        self.spec_var = tk.StringVar()
        ent = ttk.Entry(spec, textvariable=self.spec_var, width=34)
        ent.pack(side="left", padx=4)
        ent.bind("<Return>", lambda e: self.apply_spec())
        ttk.Button(spec, text="Apply", command=self.apply_spec).pack(side="left")
        ttk.Button(spec, text="All", command=lambda: self.lb.selection_set(0, "end")).pack(side="left", padx=(12, 2))
        ttk.Button(spec, text="None", command=lambda: self.lb.selection_clear(0, "end")).pack(side="left")
        ttk.Label(self, foreground="#666", padding=(8, 0), justify="left",
                  text="Enter = all   ·   .jpg .png = only these extensions   ·   !.txt !.py = everything except\n"
                       "1,3,5-8 = pick by number   ·   *report* = wildcard on the name   ·   or just click in the list "
                       "(Ctrl/Shift for multi)").pack(anchor="w")
        self.msg = ttk.Label(self, foreground="#c00000", padding=(8, 2))
        self.msg.pack(anchor="w")
        bar = ttk.Frame(self, padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="OK", command=self._ok).pack(side="right", padx=6)
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        ent.focus_set()
        self.wait_window()

    def apply_spec(self):
        chosen, how = select_by_spec(self.files, self.spec_var.get())
        if chosen is None:
            self.msg.configure(text="✗ " + how)
            return
        self.msg.configure(text="")
        self.lb.selection_clear(0, "end")
        idx = {f: i for i, f in enumerate(self.files)}
        for f in chosen:
            self.lb.selection_set(idx[f])
        if not chosen:
            self.msg.configure(text="✗ That selection matched no files.")

    def _ok(self):
        sel = [self.files[i] for i in self.lb.curselection()]
        if not sel:
            self.msg.configure(text="✗ Nothing selected.")
            return
        self.result = sel
        self.destroy()


# ─────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────
SORT_OPTIONS = ("Name", "Date taken", "File date", "Size", "Pending first")


class App(tk.Tk):
    def __init__(self, start_folder=None):
        super().__init__()
        self.title(APP_NAME)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1440, sw - 60)}x{min(880, sh - 140)}+20+20")
        self.minsize(960, 600)
        self.settings = load_settings()
        self.folder = ""
        self.photos = []
        self.view = []                 # indices into self.photos after filter/sort
        self.selected = set()
        self.anchor = None
        self.gen = 0
        self.q = queue.Queue()
        self.undo_stack = []
        self.tiles = {}                # idx -> dict(rect, img, t1, t2, badge, x, y)
        self.scaled = {}               # idx -> PhotoImage currently shown in the grid
        self.preview_img = None
        self.preview_for = None
        self.scan_thread = None
        self._relayout_job = None
        self._panel_photo = None
        self.thumbs = ThumbService(self)
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Big.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Pend.TLabel", foreground=PEND_COLOR, font=("Segoe UI", 10, "bold"))
        style.configure("Hint.TLabel", foreground="#666")
        style.configure("H.TLabel", font=("Segoe UI", 10, "bold"))
        self._build_menu()
        self._build_toolbar()
        self._build_status()
        self._build_body()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(60, self._poll_queue)
        folder = start_folder or self.settings.get("last_folder") or os.getcwd()
        if not os.path.isdir(folder):
            folder = os.getcwd()
        self.after(100, lambda: self.open_folder(folder))

    # ═══════════════ UI construction ═══════════════
    def _build_menu(self):
        mb = tk.Menu(self)
        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="Open folder…", accelerator="Ctrl+O", command=self.browse_folder)
        m.add_command(label="Rescan folder", accelerator="F5", command=lambda: self.open_folder(self.folder))
        m.add_command(label="Go to parent folder", accelerator="Backspace", command=self.go_up)
        m.add_command(label="Open folder in Explorer", command=lambda: self._startfile(self.folder))
        m.add_separator()
        m.add_command(label="Clear thumbnail cache", command=self.clear_cache)
        m.add_separator()
        m.add_command(label="Exit", command=self.on_close)
        mb.add_cascade(label="File", menu=m)

        e = tk.Menu(mb, tearoff=0)
        e.add_command(label="Apply staged renames…", accelerator="Ctrl+S", command=self.apply_pending)
        e.add_command(label="Undo last applied batch…", accelerator="Ctrl+Z", command=self.undo_last)
        e.add_separator()
        e.add_command(label="Select all", accelerator="Ctrl+A", command=self.select_all)
        e.add_command(label="Select none", accelerator="Esc", command=self.select_none)
        e.add_command(label="Select pending only", command=self.select_pending)
        e.add_separator()
        e.add_command(label="Reset staged changes on selected", command=self.reset_selected)
        e.add_command(label="Reset ALL staged changes", command=self.reset_all)
        e.add_separator()
        e.add_command(label="Auto-date: stage metadata date on every undated file", command=self.autodate_all)
        e.add_command(label="Remove date prefix from selected", command=lambda: self.set_date_selected(""))
        mb.add_cascade(label="Edit", menu=e)

        v = tk.Menu(mb, tearoff=0)
        v.add_command(label="More columns (smaller thumbnails)", accelerator="+", command=lambda: self.change_columns(1))
        v.add_command(label="Fewer columns (bigger thumbnails)", accelerator="-", command=lambda: self.change_columns(-1))
        v.add_separator()
        self.var_videos = tk.BooleanVar(value=self.settings.get("include_videos", True))
        v.add_checkbutton(label="Show video files", variable=self.var_videos, command=lambda: self.open_folder(self.folder))
        self.var_autodate = tk.BooleanVar(value=self.settings.get("auto_date", True))
        v.add_checkbutton(label="Auto-stage metadata date on undated files when opening a folder",
                          variable=self.var_autodate, command=self._save_prefs)
        mb.add_cascade(label="View", menu=v)

        self.tools_menu = tk.Menu(mb, tearoff=0)
        self._build_tools_menu(self.tools_menu)
        mb.add_cascade(label="Tools", menu=self.tools_menu)

        lm = tk.Menu(mb, tearoff=0)
        lm.add_command(label="Manage quick labels…", command=self.manage_labels)
        lm.add_command(label="Add labels found in this folder's file names to quick labels…", command=self.harvest_labels)
        mb.add_cascade(label="Labels", menu=lm)

        h = tk.Menu(mb, tearoff=0)
        h.add_command(label="How naming works", command=self.show_help)
        h.add_command(label="Keyboard shortcuts", command=self.show_shortcuts)
        h.add_command(label="About", command=lambda: messagebox.showinfo(
            "About", f"{APP_NAME}\n\nStandard-library Python + tkinter.\nThumbnail helper: "
                     f"{'Windows WIC (PowerShell)' if self.thumbs.wic_ok else 'built-in decoder only'}\n"
                     f"Cache: {CACHE_DIR}\nSettings: {SETTINGS_FILE}", parent=self))
        mb.add_cascade(label="Help", menu=h)
        self.config(menu=mb)

    def _build_toolbar(self):
        tb = ttk.Frame(self, padding=(6, 4))
        tb.pack(fill="x")
        ttk.Label(tb, text="Folder:").pack(side="left")
        self.folder_var = tk.StringVar()
        ent = ttk.Entry(tb, textvariable=self.folder_var, width=52)
        ent.pack(side="left", padx=4)
        ent.bind("<Return>", lambda e: self.open_folder(self.folder_var.get()))
        ttk.Button(tb, text="Browse…", command=self.browse_folder).pack(side="left")
        ttk.Button(tb, text="↑ Up", width=5, command=self.go_up).pack(side="left", padx=(2, 0))
        self.sub_var = tk.StringVar()
        self.sub_combo = ttk.Combobox(tb, textvariable=self.sub_var, width=22, state="readonly")
        self.sub_combo.pack(side="left", padx=4)
        self.sub_combo.bind("<<ComboboxSelected>>", self._enter_subfolder)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(tb, text="Thumbs/row:").pack(side="left")
        ttk.Button(tb, text="−", width=2, command=lambda: self.change_columns(-1)).pack(side="left")
        self.cols_var = tk.IntVar(value=int(self.settings.get("columns", 5)))
        ttk.Label(tb, textvariable=self.cols_var, width=3, anchor="center").pack(side="left")
        ttk.Button(tb, text="+", width=2, command=lambda: self.change_columns(1)).pack(side="left")
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(tb, text="Sort:").pack(side="left")
        self.sort_var = tk.StringVar(value=self.settings.get("sort", "Name"))
        sc = ttk.Combobox(tb, textvariable=self.sort_var, values=SORT_OPTIONS, width=13, state="readonly")
        sc.pack(side="left", padx=2)
        sc.bind("<<ComboboxSelected>>", lambda e: self.rebuild_view())
        ttk.Label(tb, text="Filter:").pack(side="left", padx=(8, 0))
        self.filter_var = tk.StringVar()
        fe = ttk.Entry(tb, textvariable=self.filter_var, width=16)
        fe.pack(side="left", padx=2)
        fe.bind("<KeyRelease>", lambda e: self.rebuild_view())
        self.pending_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(tb, text="pending only", variable=self.pending_only, command=self.rebuild_view).pack(side="left")
        self.apply_btn = ttk.Button(tb, text="Apply 0 renames…", style="Big.TButton", command=self.apply_pending,
                                    state="disabled")
        self.apply_btn.pack(side="right")
        ttk.Button(tb, text="Undo", command=self.undo_last).pack(side="right", padx=4)

    def _build_body(self):
        self.paned = ttk.Panedwindow(self, orient="horizontal")
        self.paned.pack(fill="both", expand=True)
        left = ttk.Frame(self.paned)
        self.paned.add(left, weight=4)
        self.canvas = tk.Canvas(left, background="#ffffff", highlightthickness=0)
        self.vsb = ttk.Scrollbar(left, orient="vertical", command=self._on_scrollbar)
        self.canvas.configure(yscrollcommand=self._on_yscroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Double-Button-1>", self._on_double)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<MouseWheel>", lambda e: (self.canvas.yview_scroll(int(-e.delta / 120), "units"),
                                                   self._schedule_visible()))
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())

        right = ttk.Frame(self.paned, width=430)
        self.paned.add(right, weight=0)
        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True)
        self.tab_label = ttk.Frame(self.nb, padding=6)
        self.tab_meta = ttk.Frame(self.nb, padding=6)
        self.nb.add(self.tab_label, text="  Label & rename  ")
        self.nb.add(self.tab_meta, text="  Metadata  ")
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._refresh_meta_if_visible())
        self._build_label_tab()
        self._build_meta_tab()

    def _build_label_tab(self):
        t = self.tab_label
        self.sel_lbl = ttk.Label(t, text="No photo selected", style="H.TLabel")
        self.sel_lbl.pack(anchor="w")
        self.preview = tk.Canvas(t, height=210, background="#e9e9e9", highlightthickness=1,
                                 highlightbackground="#cfcfcf", cursor="hand2")
        self.preview.pack(fill="x", pady=(4, 6))
        self.preview.bind("<Button-1>", lambda e: self.open_selected())
        self.preview.bind("<Configure>", lambda e: self._show_preview(force=True))

        # ── date row ──
        df = ttk.Frame(t)
        df.pack(fill="x", pady=(0, 4))
        ttk.Label(df, text="Date prefix:", style="H.TLabel").pack(side="left")
        self.date_var = tk.StringVar()
        self.date_entry = ttk.Entry(df, textvariable=self.date_var, width=11, font=("Consolas", 11))
        self.date_entry.pack(side="left", padx=4)
        self.date_entry.bind("<Return>", lambda e: self._date_typed())
        self.date_entry.bind("<FocusOut>", lambda e: self._date_typed())
        self.btn_date_meta = ttk.Button(df, text="Use metadata", command=self.use_meta_date)
        self.btn_date_meta.pack(side="left")
        ttk.Button(df, text="File date", command=self.use_file_date).pack(side="left", padx=2)
        ttk.Button(df, text="None", width=5, command=lambda: self.set_date_selected("")).pack(side="left")
        self.date_hint = ttk.Label(t, text="", style="Hint.TLabel")
        self.date_hint.pack(anchor="w")

        # ── quick labels ──
        qh = ttk.Frame(t)
        qh.pack(fill="x", pady=(6, 0))
        ttk.Label(qh, text="Quick labels  (keys 1-9 toggle the first nine)", style="H.TLabel").pack(side="left")
        ttk.Button(qh, text="Manage…", command=self.manage_labels).pack(side="right")
        self.quick = ScrollFrame(t)
        self.quick_vars = {}     # label -> (IntVar, Checkbutton)
        self._build_quick_labels()

        # ── bottom section (packed to the bottom so it never gets cut off) ──
        bot = ttk.Frame(t)
        bot.pack(side="bottom", fill="x")
        t = bot
        cf = ttk.Frame(t)
        cf.pack(fill="x")
        ttk.Label(cf, text="Other label:").pack(side="left")
        self.custom_var = tk.StringVar()
        ce = ttk.Entry(cf, textvariable=self.custom_var, width=22)
        ce.pack(side="left", padx=4)
        ce.bind("<Return>", lambda e: self.add_custom_label())
        ttk.Button(cf, text="Add", command=self.add_custom_label).pack(side="left")
        self.remember_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cf, text="remember", variable=self.remember_var).pack(side="left", padx=4)

        # ── labels on this photo ──
        lf = ttk.Frame(t)
        lf.pack(fill="x", pady=(6, 0))
        ttk.Label(lf, text="Labels on selected (in name order):", style="H.TLabel").pack(anchor="w")
        row = ttk.Frame(lf)
        row.pack(fill="x")
        self.lab_list = tk.Listbox(row, height=4, activestyle="none", exportselection=False)
        self.lab_list.pack(side="left", fill="x", expand=True)
        btns = ttk.Frame(row)
        btns.pack(side="left", padx=4)
        ttk.Button(btns, text="▲", width=3, command=lambda: self.move_label(-1)).pack()
        ttk.Button(btns, text="▼", width=3, command=lambda: self.move_label(1)).pack()
        ttk.Button(btns, text="✕", width=3, command=self.remove_label_btn).pack()

        # ── core + proposed ──
        cr = ttk.Frame(t)
        cr.pack(fill="x", pady=(6, 0))
        ttk.Label(cr, text="Original part:").pack(side="left")
        self.core_var = tk.StringVar()
        self.core_entry = ttk.Entry(cr, textvariable=self.core_var)
        self.core_entry.pack(side="left", fill="x", expand=True, padx=4)
        self.core_entry.bind("<Return>", lambda e: self._core_typed())
        self.core_entry.bind("<FocusOut>", lambda e: self._core_typed())
        ttk.Label(t, text="New name:", style="H.TLabel").pack(anchor="w", pady=(6, 0))
        self.proposed_lbl = ttk.Label(t, text="", wraplength=400, font=("Consolas", 10))
        self.proposed_lbl.pack(anchor="w")
        bb = ttk.Frame(t)
        bb.pack(fill="x", pady=(6, 0))
        ttk.Button(bb, text="Reset selected", command=self.reset_selected).pack(side="left")
        ttk.Button(bb, text="Open in viewer", command=self.open_selected).pack(side="left", padx=4)
        ttk.Button(bb, text="Apply renames…", style="Big.TButton", command=self.apply_pending).pack(side="right")
        self.quick.pack(fill="both", expand=True, pady=(2, 4))

    def _build_meta_tab(self):
        t = self.tab_meta
        self.meta_title = ttk.Label(t, text="Select one photo to see its metadata", style="H.TLabel")
        self.meta_title.pack(anchor="w")
        frame = ttk.Frame(t)
        frame.pack(fill="both", expand=True, pady=4)
        self.meta_tree = ttk.Treeview(frame, columns=("field", "value"), show="tree headings")
        self.meta_tree.heading("#0", text="Section")
        self.meta_tree.heading("field", text="Field")
        self.meta_tree.heading("value", text="Value")
        self.meta_tree.column("#0", width=90, stretch=False)
        self.meta_tree.column("field", width=150, stretch=False)
        self.meta_tree.column("value", width=200)
        vs = ttk.Scrollbar(frame, orient="vertical", command=self.meta_tree.yview)
        self.meta_tree.configure(yscrollcommand=vs.set)
        self.meta_tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.meta_tree.bind("<<TreeviewSelect>>", self._meta_pick)
        bb = ttk.Frame(t)
        bb.pack(fill="x")
        ttk.Button(bb, text="Print all (report)", command=self.meta_report).pack(side="left")
        ttk.Button(bb, text="Copy", command=self.meta_copy).pack(side="left", padx=4)
        ttk.Button(bb, text="Refresh", command=lambda: self.refresh_meta(True)).pack(side="left")

        ed = ttk.LabelFrame(t, text="Edit EXIF field (JPEG only — writes to the file after confirmation)", padding=6)
        ed.pack(fill="x", pady=(8, 0))
        r1 = ttk.Frame(ed)
        r1.pack(fill="x")
        ttk.Label(r1, text="Field:").pack(side="left")
        self.meta_field = tk.StringVar(value="DateTimeOriginal")
        fc = ttk.Combobox(r1, textvariable=self.meta_field, values=list(EDITABLE_TAGS), width=20, state="readonly")
        fc.pack(side="left", padx=4)
        fc.bind("<<ComboboxSelected>>", lambda e: self._meta_field_changed())
        self.meta_cur = ttk.Label(ed, text="", style="Hint.TLabel", wraplength=400)
        self.meta_cur.pack(anchor="w", pady=2)
        r2 = ttk.Frame(ed)
        r2.pack(fill="x")
        ttk.Label(r2, text="New value:").pack(side="left")
        self.meta_val = tk.StringVar()
        ttk.Entry(r2, textvariable=self.meta_val).pack(side="left", fill="x", expand=True, padx=4)
        r3 = ttk.Frame(ed)
        r3.pack(fill="x", pady=(4, 0))
        ttk.Button(r3, text="Write field", command=self.meta_write).pack(side="left")
        ttk.Button(r3, text="Remove field", command=self.meta_remove).pack(side="left", padx=4)
        ttk.Button(r3, text="Date ← name prefix", command=self.meta_date_from_name).pack(side="left")
        ttk.Button(r3, text="Keywords ← labels", command=self.meta_keywords_from_labels).pack(side="left", padx=4)
        ttk.Label(ed, style="Hint.TLabel", wraplength=400,
                  text="Dates use  YYYY:MM:DD HH:MM:SS.  Keywords (XPKeywords) are what Windows Explorer shows as "
                       "'Tags'; separate with ; ").pack(anchor="w", pady=(4, 0))

    def _build_status(self):
        self.status = ttk.Label(self, text="", anchor="w", padding=(8, 3), relief="sunken")
        self.status.pack(fill="x", side="bottom")

    def _bind_keys(self):
        self.bind("<Control-o>", lambda e: self.browse_folder())
        self.bind("<F5>", lambda e: self.open_folder(self.folder))
        self.bind("<Control-s>", lambda e: self.apply_pending())
        self.bind("<Control-z>", lambda e: self.undo_last())
        c = self.canvas
        c.bind("<Control-a>", lambda e: self.select_all())
        c.bind("<Escape>", lambda e: self.select_none())
        c.bind("<BackSpace>", lambda e: self.go_up())
        c.bind("<plus>", lambda e: self.change_columns(1))
        c.bind("<equal>", lambda e: self.change_columns(1))
        c.bind("<minus>", lambda e: self.change_columns(-1))
        c.bind("<Return>", lambda e: self.open_selected())
        c.bind("<Delete>", lambda e: self.reset_selected())
        for k in "123456789":
            c.bind(k, lambda e, k=k: self.toggle_quick_by_number(int(k)))
        c.bind("<KeyPress-d>", lambda e: self.use_meta_date())
        c.bind("<KeyPress-n>", lambda e: self.set_date_selected(""))
        for key, dx, dy in (("<Left>", -1, 0), ("<Right>", 1, 0), ("<Up>", 0, -1), ("<Down>", 0, 1),
                            ("<Home>", None, -1), ("<End>", None, 1)):
            c.bind(key, lambda e, dx=dx, dy=dy: self._nav(e, dx, dy))
        c.bind("<Prior>", lambda e: (self.canvas.yview_scroll(-1, "pages"), self._schedule_visible()))
        c.bind("<Next>", lambda e: (self.canvas.yview_scroll(1, "pages"), self._schedule_visible()))

    # ═══════════════ folder scanning ═══════════════
    def browse_folder(self):
        d = filedialog.askdirectory(parent=self, initialdir=self.folder or os.getcwd(), mustexist=True)
        if d:
            self.open_folder(d)

    def go_up(self):
        if self.folder:
            parent = os.path.dirname(self.folder.rstrip("\\/"))
            if parent and parent != self.folder:
                self.open_folder(parent)

    def _enter_subfolder(self, _e=None):
        name = self.sub_var.get()
        if name and name != "(subfolders)":
            self.open_folder(os.path.join(self.folder, name))

    def open_folder(self, folder):
        folder = os.path.abspath(folder.strip().strip('"')) if folder else ""
        if not os.path.isdir(folder):
            messagebox.showerror("Folder", f"Not a folder:\n{folder}", parent=self)
            return
        if self.pending_count() and folder != self.folder:
            if not messagebox.askyesno("Staged renames", "You have staged renames that were not applied.\n"
                                       "Discard them and open the other folder?", parent=self):
                return
        self.folder = folder
        self.folder_var.set(folder)
        self.settings["last_folder"] = folder
        self._save_prefs()
        self.gen += 1
        self.photos = []
        self.view = []
        self.selected = set()
        self.anchor = None
        self.scaled = {}
        self.tiles = {}
        self.canvas.delete("all")
        self.preview_for = None
        self._set_status("Scanning folder…")
        try:
            names = sorted(os.listdir(folder), key=str.lower)
        except OSError as e:
            messagebox.showerror("Folder", str(e), parent=self)
            return
        subs = [n for n in names if os.path.isdir(os.path.join(folder, n))]
        self.sub_combo["values"] = ["(subfolders)"] + subs
        self.sub_var.set("(subfolders)")
        include_videos = self.var_videos.get()
        media = [n for n in names if os.path.isfile(os.path.join(folder, n)) and
                 (os.path.splitext(n)[1].lower() in IMAGE_EXT or
                  (include_videos and os.path.splitext(n)[1].lower() in VIDEO_EXT))]
        gen = self.gen
        auto = self.var_autodate.get()

        def work():
            photos = []
            for i, n in enumerate(media):
                p = Photo(folder, n)
                p.info = read_media_info(p.path)
                if p.info["taken"]:
                    p.sugg_date = p.info["taken"].strftime("%Y%m%d")
                    p.sugg_src = p.info["taken_src"]
                if auto and not p.o_date and p.sugg_date:
                    p.date = p.sugg_date
                photos.append(p)
                if i % 40 == 39:
                    self.q.put(("scan_progress", gen, i + 1, len(media)))
            self.q.put(("scan_done", gen, photos))

        self.scan_thread = threading.Thread(target=work, daemon=True)
        self.scan_thread.start()

    def _scan_done(self, photos):
        self.photos = photos
        self.thumbs.set_photos(photos, self.gen)
        self.rebuild_view()
        self._refresh_panel()
        self._update_status()

    # ═══════════════ view (filter / sort) ═══════════════
    def rebuild_view(self):
        self.settings["sort"] = self.sort_var.get()
        term = self.filter_var.get().strip().lower()
        pend = self.pending_only.get()
        idx = []
        for i, p in enumerate(self.photos):
            if pend and not p.pending():
                continue
            if term and term not in p.name.lower() and term not in p.proposed().lower():
                continue
            idx.append(i)
        mode = self.sort_var.get()
        P = self.photos
        if mode == "Date taken":
            idx.sort(key=lambda i: (P[i].sugg_date or P[i].date or "99999999", P[i].name.lower()))
        elif mode == "File date":
            idx.sort(key=lambda i: P[i].mtime)
        elif mode == "Size":
            idx.sort(key=lambda i: -P[i].size)
        elif mode == "Pending first":
            idx.sort(key=lambda i: (not P[i].pending(), P[i].name.lower()))
        else:
            idx.sort(key=lambda i: P[i].name.lower())
        self.view = idx
        self.selected &= set(idx)
        self.relayout()

    # ═══════════════ grid layout ═══════════════
    def _cols(self):
        return max(1, min(20, int(self.cols_var.get())))

    def change_columns(self, delta):
        self.cols_var.set(max(1, min(20, self._cols() + delta)))
        self.settings["columns"] = self._cols()
        self._save_prefs()
        self.scaled = {}
        self.relayout()

    def _on_canvas_configure(self, _e):
        if self._relayout_job:
            self.after_cancel(self._relayout_job)
        self._relayout_job = self.after(120, self.relayout)

    def _tile_geometry(self):
        cw = max(self.canvas.winfo_width(), 200)
        cols = self._cols()
        tile_w = (cw - PAD) // cols
        box = tile_w - 2 * PAD
        text_h = 46
        tile_h = box + text_h + PAD * 2
        return cols, tile_w, tile_h, box

    def relayout(self):
        self._relayout_job = None
        self.canvas.delete("all")
        self.tiles = {}
        self.scaled = {}
        cols, tile_w, tile_h, box = self._tile_geometry()
        max_chars = max(8, int((tile_w - 10) / 6.3))
        for pos, idx in enumerate(self.view):
            p = self.photos[idx]
            r, c = divmod(pos, cols)
            x = PAD + c * tile_w
            y = PAD + r * tile_h
            rect = self.canvas.create_rectangle(x, y, x + tile_w - PAD, y + tile_h - PAD, fill=TILE_FILL,
                                                outline=TILE_LINE, width=1)
            img = self.canvas.create_image(x + (tile_w - PAD) // 2, y + PAD + box // 2, anchor="center")
            ph = self.canvas.create_text(x + (tile_w - PAD) // 2, y + PAD + box // 2, text="",
                                         fill="#999", font=("Segoe UI", 9), justify="center")
            t1 = self.canvas.create_text(x + (tile_w - PAD) // 2, y + PAD + box + 6, anchor="n",
                                         text="", font=("Segoe UI", 8), fill="#333")
            t2 = self.canvas.create_text(x + (tile_w - PAD) // 2, y + PAD + box + 22, anchor="n",
                                         text="", font=("Segoe UI", 8, "bold"), fill=PEND_COLOR)
            self.tiles[idx] = dict(rect=rect, img=img, ph=ph, t1=t1, t2=t2, x=x, y=y, pos=pos)
            self._refresh_tile(idx, max_chars)
        rows = (len(self.view) + cols - 1) // cols
        self.canvas.configure(scrollregion=(0, 0, cols * tile_w + PAD, rows * tile_h + PAD))
        self._update_visible()

    def _refresh_tile(self, idx, max_chars=None):
        t = self.tiles.get(idx)
        if not t:
            return
        p = self.photos[idx]
        if max_chars is None:
            _, tile_w, _, _ = self._tile_geometry()
            max_chars = max(8, int((tile_w - 10) / 6.3))
        pending = p.pending()
        self.canvas.itemconfigure(t["t1"], text=fit_text(p.name, max_chars))
        self.canvas.itemconfigure(t["t2"], text=("→ " + fit_text(p.proposed(), max_chars - 2)) if pending else "")
        sel = idx in self.selected
        self.canvas.itemconfigure(t["rect"], outline=SEL_COLOR if sel else (PEND_COLOR if pending else TILE_LINE),
                                  width=3 if sel else (2 if pending else 1),
                                  fill=SEL_FILL if sel else TILE_FILL)
        if idx not in self.scaled:
            if p.kind == "video":
                self.canvas.itemconfigure(t["ph"], text="▶\nVIDEO\n" + (p.ext.upper()[1:]), font=("Segoe UI", 12))
            elif p.thumb_failed:
                self.canvas.itemconfigure(t["ph"], text="no\npreview")
            else:
                self.canvas.itemconfigure(t["ph"], text="…")

    def _visible_positions(self):
        cols, tile_w, tile_h, box = self._tile_geometry()
        top = self.canvas.canvasy(0)
        bottom = top + self.canvas.winfo_height()
        first_row = max(0, int(top // tile_h) - 1)
        last_row = int(bottom // tile_h) + 1
        return range(first_row * cols, min(len(self.view), (last_row + 1) * cols))

    def _schedule_visible(self):
        if getattr(self, "_vis_job", None):
            self.after_cancel(self._vis_job)
        self._vis_job = self.after(80, self._update_visible)

    def _on_scrollbar(self, *args):
        self.canvas.yview(*args)
        self._schedule_visible()

    def _on_yscroll(self, first, last):
        self.vsb.set(first, last)
        self._schedule_visible()

    def _update_visible(self):
        self._vis_job = None
        if not self.view:
            return
        vis = self._visible_positions()
        vis_idx = [self.view[pos] for pos in vis]
        keep = set(vis_idx)
        # drop scaled images of tiles far away
        for idx in list(self.scaled):
            if idx not in keep:
                del self.scaled[idx]
                t = self.tiles.get(idx)
                if t:
                    self.canvas.itemconfigure(t["img"], image="")
                    self._refresh_tile(idx)
        _, _, _, box = self._tile_geometry()
        for idx in vis_idx:
            if idx not in self.scaled:
                self._load_tile_image(idx, box)
        # thumbnail production order: visible first, then the rest of the view
        order = vis_idx + [i for i in self.view if i not in keep]
        self.thumbs.set_order(order)

    def _load_tile_image(self, idx, box):
        p = self.photos[idx]
        t = self.tiles.get(idx)
        if not t:
            return
        src_path = p.best_thumb()
        try:
            if src_path:
                src = load_photoimage(src_path)
            elif p.ext.lower() in TK_NATIVE_EXT and not self.thumbs.wic_ok and p.size < 30_000_000:
                src = load_photoimage(p.path)
            else:
                return
            img = fit_photo(src, box)
        except Exception:
            return
        self.scaled[idx] = img
        self.canvas.itemconfigure(t["img"], image=img)
        self.canvas.itemconfigure(t["ph"], text="")

    # ═══════════════ selection ═══════════════
    def _hit(self, event):
        cols, tile_w, tile_h, box = self._tile_geometry()
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        c = int((x - PAD) // tile_w)
        r = int((y - PAD) // tile_h)
        if c < 0 or c >= cols or r < 0:
            return None
        pos = r * cols + c
        if pos >= len(self.view):
            return None
        return pos

    def _on_click(self, event):
        self.canvas.focus_set()
        pos = self._hit(event)
        if pos is None:
            self.select_none()
            return
        idx = self.view[pos]
        ctrl = event.state & 0x0004
        shift = event.state & 0x0001
        old = set(self.selected)
        if shift and self.anchor is not None and self.anchor in self.view:
            a = self.view.index(self.anchor)
            lo, hi = sorted((a, pos))
            rng = set(self.view[lo:hi + 1])
            self.selected = (self.selected | rng) if ctrl else rng
        elif ctrl:
            if idx in self.selected:
                self.selected.discard(idx)
            else:
                self.selected.add(idx)
            self.anchor = idx
        else:
            self.selected = {idx}
            self.anchor = idx
        for i in old ^ self.selected:
            self._refresh_tile(i)
        self._refresh_panel()

    def _on_double(self, event):
        pos = self._hit(event)
        if pos is not None:
            self._startfile(self.photos[self.view[pos]].path)

    def _on_right_click(self, event):
        pos = self._hit(event)
        if pos is None:
            return
        idx = self.view[pos]
        if idx not in self.selected:
            self.selected = {idx}
            self.anchor = idx
            self.relayout_selection()
            self._refresh_panel()
        p = self.photos[idx]
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Open in default viewer", command=lambda: self._startfile(p.path))
        m.add_command(label="Show in Explorer", command=lambda: self._show_in_explorer(p.path))
        m.add_separator()
        m.add_command(label="Use metadata date", command=self.use_meta_date)
        m.add_command(label="Use this photo's date for all selected",
                      command=lambda: self.set_date_selected(p.date or p.sugg_date))
        m.add_command(label="Copy labels of this photo to all selected", command=lambda: self.copy_labels_from(p))
        m.add_separator()
        m.add_command(label="Reset staged changes", command=self.reset_selected)
        m.add_command(label="Copy current name", command=lambda: (self.clipboard_clear(), self.clipboard_append(p.name)))
        m.tk_popup(event.x_root, event.y_root)

    def relayout_selection(self):
        for i in self.view:
            self._refresh_tile(i)

    def select_all(self):
        self.selected = set(self.view)
        self.relayout_selection()
        self._refresh_panel()

    def select_none(self):
        old = set(self.selected)
        self.selected = set()
        for i in old:
            self._refresh_tile(i)
        self._refresh_panel()

    def select_pending(self):
        self.selected = {i for i in self.view if self.photos[i].pending()}
        self.relayout_selection()
        self._refresh_panel()

    def _nav(self, event, dx, dy):
        if not self.view:
            return
        cols = self._cols()
        if self.anchor in self.view:
            pos = self.view.index(self.anchor)
        else:
            pos = 0
        if dx is None:
            pos = 0 if dy < 0 else len(self.view) - 1
        else:
            pos = pos + dx + dy * cols
        pos = max(0, min(len(self.view) - 1, pos))
        idx = self.view[pos]
        old = set(self.selected)
        if event.state & 0x0001:
            self.selected.add(idx)
        else:
            self.selected = {idx}
        self.anchor = idx
        for i in old ^ self.selected:
            self._refresh_tile(i)
        self._refresh_tile(idx)
        self._scroll_to(idx)
        self._refresh_panel()

    def _scroll_to(self, idx):
        t = self.tiles.get(idx)
        if not t:
            return
        _, _, tile_h, _ = self._tile_geometry()
        region = self.canvas.bbox("all")
        if not region:
            return
        total = region[3]
        top = self.canvas.canvasy(0)
        h = self.canvas.winfo_height()
        if t["y"] < top:
            self.canvas.yview_moveto(max(0, t["y"] - PAD) / total)
        elif t["y"] + tile_h > top + h:
            self.canvas.yview_moveto(max(0, t["y"] + tile_h - h) / total)
        self._schedule_visible()

    def selected_photos(self):
        return [self.photos[i] for i in self.view if i in self.selected]

    # ═══════════════ right panel ═══════════════
    def _refresh_panel(self):
        sel = self.selected_photos()
        n = len(sel)
        if n == 0:
            self.sel_lbl.configure(text="No photo selected — click a thumbnail (Ctrl/Shift for several)")
            self.date_var.set("")
            self.date_hint.configure(text="")
            self.core_var.set("")
            self.core_entry.configure(state="disabled")
            self.proposed_lbl.configure(text="", style="TLabel")
            self.lab_list.delete(0, "end")
            self._set_quick_states([])
            self._show_preview()
            self._refresh_meta_if_visible()
            return
        if n == 1:
            p = sel[0]
            self.sel_lbl.configure(text=p.name)
            self.date_var.set(p.date)
            src = f"metadata says {p.sugg_date} ({p.sugg_src})" if p.sugg_date else "no date in metadata or name"
            self.date_hint.configure(text=src + f"   ·   file date {p.file_date()}")
            self.core_entry.configure(state="normal")
            self.core_var.set(p.core)
            self.proposed_lbl.configure(text=p.proposed(), style="Pend.TLabel" if p.pending() else "TLabel")
            self.lab_list.delete(0, "end")
            for l in p.labels:
                self.lab_list.insert("end", l)
        else:
            self.sel_lbl.configure(text=f"{n} files selected")
            dates = {p.date for p in sel}
            self.date_var.set(dates.pop() if len(dates) == 1 else "(mixed)")
            self.date_hint.configure(text=f"{sum(1 for p in sel if p.sugg_date)} of {n} have a metadata date")
            self.core_var.set("")
            self.core_entry.configure(state="disabled")
            npend = sum(1 for p in sel if p.pending())
            self.proposed_lbl.configure(text=f"{npend} of {n} selected have a staged rename",
                                        style="Pend.TLabel" if npend else "TLabel")
            self.lab_list.delete(0, "end")
            counts = {}
            order = []
            for p in sel:
                for l in p.labels:
                    if l not in counts:
                        order.append(l)
                    counts[l] = counts.get(l, 0) + 1
            for l in order:
                self.lab_list.insert("end", f"{l}   ({counts[l]}/{n})")
        self._set_quick_states(sel)
        self._show_preview()
        self._refresh_meta_if_visible()

    def _set_quick_states(self, sel):
        n = len(sel)
        for label, (var, cb) in self.quick_vars.items():
            have = sum(1 for p in sel if label in p.labels) if n else 0
            cb.state(["!alternate"])
            if n and have == n:
                var.set(1)
            elif have:
                var.set(0)
                cb.state(["alternate"])
            else:
                var.set(0)
            cb.state(["!disabled"] if n else ["disabled"])

    def _build_quick_labels(self):
        for w in self.quick.inner.winfo_children():
            w.destroy()
        self.quick_vars = {}
        num = 0
        for g in self.settings.get("label_groups", []):
            hdr = ttk.Frame(self.quick.inner)
            hdr.pack(fill="x", pady=(4, 0))
            ttk.Label(hdr, text=g["name"], font=("Segoe UI", 9, "bold"), foreground="#0a5ea8").pack(side="left")
            ttk.Button(hdr, text="+", width=2, command=lambda g=g: self.add_label_to_group(g)).pack(side="right")
            grid = ttk.Frame(self.quick.inner)
            grid.pack(fill="x")
            for k, label in enumerate(g["labels"]):
                num += 1
                var = tk.IntVar(value=0)
                txt = f"{num} {label}" if num <= 9 else label
                cb = ttk.Checkbutton(grid, text=txt, variable=var,
                                     command=lambda l=label, v=var: self.toggle_quick(l, v))
                cb.grid(row=k // 3, column=k % 3, sticky="w", padx=(0, 8))
                cb.bind("<Button-3>", lambda e, l=label, g=g: self._quick_context(e, l, g))
                self.quick_vars[label] = (var, cb)
        self.quick_order = list(self.quick_vars)
        self._set_quick_states(self.selected_photos())

    def _quick_context(self, event, label, group):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label=f"Rename '{label}'…", command=lambda: self.rename_quick_label(group, label))
        m.add_command(label=f"Remove '{label}' from quick labels", command=lambda: self.remove_quick_label(group, label))
        m.tk_popup(event.x_root, event.y_root)

    def rename_quick_label(self, group, label):
        new = simpledialog.askstring("Rename label", "New label text:", initialvalue=label, parent=self)
        if not new:
            return
        new = sanitize_label(new)
        if new and new != label:
            group["labels"] = [new if l == label else l for l in group["labels"]]
            self._save_prefs()
            self._build_quick_labels()

    def remove_quick_label(self, group, label):
        group["labels"] = [l for l in group["labels"] if l != label]
        self._save_prefs()
        self._build_quick_labels()

    def add_label_to_group(self, group):
        new = simpledialog.askstring("Add quick label", f"New label for group '{group['name']}':", parent=self)
        if not new:
            return
        new = sanitize_label(new)
        if new and new not in group["labels"]:
            group["labels"].append(new)
            self._save_prefs()
            self._build_quick_labels()

    def toggle_quick(self, label, var):
        sel = self.selected_photos()
        if not sel:
            var.set(0)
            return
        if var.get():
            for p in sel:
                if label not in p.labels:
                    p.labels.append(label)
        else:
            for p in sel:
                p.labels = [l for l in p.labels if l != label]
        self._after_edit(sel)

    def toggle_quick_by_number(self, n):
        if n - 1 < len(self.quick_order):
            label = self.quick_order[n - 1]
            var, cb = self.quick_vars[label]
            var.set(0 if var.get() else 1)
            cb.state(["!alternate"])
            self.toggle_quick(label, var)

    def add_custom_label(self):
        raw = self.custom_var.get()
        label = sanitize_label(raw)
        sel = self.selected_photos()
        if not label:
            return
        if not sel:
            messagebox.showinfo("Label", "Select one or more photos first.", parent=self)
            return
        for p in sel:
            if label not in p.labels:
                p.labels.append(label)
        if self.remember_var.get():
            groups = self.settings.setdefault("label_groups", [])
            if not any(label in g["labels"] for g in groups):
                if not groups:
                    groups.append({"name": "Labels", "labels": []})
                groups[-1]["labels"].append(label)
                self._save_prefs()
                self._build_quick_labels()
        self.custom_var.set("")
        self._after_edit(sel)

    def remove_label_btn(self):
        cur = self.lab_list.curselection()
        sel = self.selected_photos()
        if not cur or not sel:
            return
        text = self.lab_list.get(cur[0])
        label = text.split("   (")[0]
        for p in sel:
            p.labels = [l for l in p.labels if l != label]
        self._after_edit(sel)

    def move_label(self, delta):
        cur = self.lab_list.curselection()
        sel = self.selected_photos()
        if not cur or len(sel) != 1:
            return
        p = sel[0]
        i = cur[0]
        j = i + delta
        if 0 <= j < len(p.labels):
            p.labels[i], p.labels[j] = p.labels[j], p.labels[i]
            self._after_edit(sel)
            self.lab_list.selection_set(j)

    def copy_labels_from(self, src):
        sel = self.selected_photos()
        for p in sel:
            p.labels = list(src.labels)
        self._after_edit(sel)

    def _date_typed(self):
        raw = self.date_var.get().strip().upper()
        if raw == "(MIXED)":
            return
        if raw and not is_date_token(raw):
            m = re.fullmatch(r"(\d{4})[-./]?(\d{2})[-./]?(\d{2})", raw)
            if m and is_date_token("".join(m.groups())):
                raw = "".join(m.groups())
            else:
                self.date_hint.configure(text="✗ Use YYYYMMDD (or YYYYMMXX when the day is unknown)")
                return
        self.set_date_selected(raw)

    def set_date_selected(self, date):
        sel = self.selected_photos()
        if not sel:
            return
        for p in sel:
            p.date = date
        self._after_edit(sel)

    def use_meta_date(self):
        sel = self.selected_photos()
        for p in sel:
            if p.sugg_date:
                p.date = p.sugg_date
        self._after_edit(sel)

    def use_file_date(self):
        sel = self.selected_photos()
        for p in sel:
            p.date = p.file_date()
        self._after_edit(sel)

    def _core_typed(self):
        sel = self.selected_photos()
        if len(sel) != 1:
            return
        core = sanitize_core(self.core_var.get())
        if core and core != sel[0].core:
            sel[0].core = core
            self._after_edit(sel)

    def autodate_all(self):
        n = 0
        for p in self.photos:
            if not p.date and p.sugg_date:
                p.date = p.sugg_date
                n += 1
        self._after_edit(self.photos)
        self._set_status(f"Staged a date prefix on {n} file(s).")

    def reset_selected(self):
        sel = self.selected_photos()
        for p in sel:
            p.reset()
        self._after_edit(sel)

    def reset_all(self):
        for p in self.photos:
            p.reset()
        self._after_edit(self.photos)

    def _after_edit(self, photos):
        idx = {id(p): i for i, p in enumerate(self.photos)}
        for p in photos:
            i = idx.get(id(p))
            if i is not None:
                self._refresh_tile(i)
        if self.pending_only.get():
            self.rebuild_view()
        self._refresh_panel()
        self._update_status()

    # ═══════════════ preview ═══════════════
    def _show_preview(self, force=False):
        sel = self.selected_photos()
        c = self.preview
        if len(sel) != 1:
            c.delete("all")
            self.preview_for = None
            if len(sel) > 1:
                c.create_text(c.winfo_width() // 2, c.winfo_height() // 2, text=f"{len(sel)} selected",
                              fill="#777", font=("Segoe UI", 14))
            return
        p = sel[0]
        i = self.photos.index(p)
        if self.preview_for == p.path and not force and self.preview_img is not None:
            return
        self.preview_for = p.path
        c.delete("all")
        w, h = max(c.winfo_width(), 100), max(c.winfo_height(), 100)
        src_path = p.preview or p.best_thumb()
        if p.kind == "video":
            c.create_text(w // 2, h // 2, text="▶  video file\n(double-click a tile or press Enter to play)",
                          fill="#555", font=("Segoe UI", 11), justify="center")
            return
        if src_path:
            try:
                src = load_photoimage(src_path)
                self.preview_img = fit_photo(src, min(w, h) if w < h else min(w, h * 100))
                # fit to both dimensions
                self.preview_img = self._fit_both(src, w - 4, h - 4)
                c.create_image(w // 2, h // 2, image=self.preview_img)
            except Exception:
                c.create_text(w // 2, h // 2, text="preview failed", fill="#777")
        else:
            c.create_text(w // 2, h // 2, text="loading preview…", fill="#777")
        if not p.preview and self.thumbs.wic_ok and p.ext.lower() in IMAGE_EXT:
            self.thumbs.request_preview(i)
        if p.info and p.info.get("width"):
            txt = f"{p.info['width']} × {p.info['height']}   {fmt_size(p.size)}"
            tid = c.create_text(6, 4, anchor="nw", fill="#fff", font=("Segoe UI", 8), text=txt)
            x1, y1, x2, y2 = c.bbox(tid)
            rid = c.create_rectangle(x1 - 4, y1 - 2, x2 + 4, y2 + 2, fill="#222", outline="")
            c.tag_lower(rid, tid)

    @staticmethod
    def _fit_both(src, w, h):
        sw, sh = src.width(), src.height()
        if sw <= w and sh <= h:
            return src
        scale = min(w / sw, h / sh)
        best = None
        for z in (1, 2, 3):
            s = math.ceil(z / scale)
            size = z / s
            if best is None or size > best[0]:
                best = (size, z, s)
            if size >= scale * 0.92:
                break
        _, z, s = best
        img = src.zoom(z, z) if z > 1 else src
        return img.subsample(s, s)

    def open_selected(self):
        sel = self.selected_photos()
        if len(sel) == 1:
            self._startfile(sel[0].path)

    def _startfile(self, path):
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("Open", str(e), parent=self)

    def _show_in_explorer(self, path):
        try:
            subprocess.Popen(["explorer", "/select,", path])
        except Exception:
            self._startfile(os.path.dirname(path))

    # ═══════════════ metadata tab ═══════════════
    def _refresh_meta_if_visible(self):
        if self.nb.index(self.nb.select()) == 1:
            self.refresh_meta()

    def meta_rows(self, p, full=True):
        """[(section, field, value)] for a photo."""
        rows = []
        st = os.stat(p.path)
        rows.append(("File", "Name", p.name))
        rows.append(("File", "Folder", p.folder))
        rows.append(("File", "Size", f"{fmt_size(st.st_size)}  ({st.st_size:,} bytes)"))
        rows.append(("File", "Modified", datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")))
        rows.append(("File", "Created", datetime.datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S")))
        info = p.info or {}
        if info.get("width"):
            rows.append(("Image", "Dimensions", f"{info['width']} × {info['height']}"))
        if info.get("taken"):
            rows.append(("Image", "Date taken", f"{info['taken']:%Y-%m-%d %H:%M:%S}  (from {info['taken_src']})"))
        ext = p.ext.lower()
        if ext in JPEG_EXT:
            try:
                data, segs = read_jpeg_header(p.path)
                kinds = []
                for m, s, en in segs:
                    if m in (0xC0, 0xC1, 0xC2):
                        prec, h, w, nc = struct.unpack(">BHHB", data[s + 4:s + 10])
                        kinds.append(f"{'progressive' if m == 0xC2 else 'baseline'}, {nc} component(s), {prec}-bit")
                    elif m == 0xE0 and data[s + 4:s + 8] == b"JFIF":
                        kinds.append(f"JFIF {data[s + 9]}.{data[s + 10]:02d}")
                    elif m == 0xE1 and data[s + 4:s + 33].startswith(b"http://ns.adobe.com/xap/1.0/"):
                        kinds.append(f"XMP packet ({en - s} bytes)")
                    elif m == 0xE2 and data[s + 4:s + 15] == b"ICC_PROFILE":
                        kinds.append(f"ICC profile ({en - s} bytes)")
                rows.append(("Image", "JPEG", "; ".join(kinds)))
                ex = exif_from_jpeg_header(data, segs)
                p.info["exif"] = ex
                if ex is None:
                    rows.append(("EXIF", "(none)", "This file has no EXIF block"))
                else:
                    if ex.error:
                        rows.append(("EXIF", "error", ex.error))
                    for e in ex.entries:
                        if e["name"] in ("ExifIFDPointer", "GPSInfoIFDPointer", "InteropIFDPointer"):
                            continue
                        sec = {"IFD0": "EXIF IFD0", "ExifIFD": "EXIF", "GPS": "GPS", "Interop": "Interop",
                               "IFD1": "Thumbnail"}.get(e["ifd"], e["ifd"])
                        rows.append((sec, e["name"], pretty_exif(e["name"], e["value"])))
                    if ex.thumb:
                        rows.append(("Thumbnail", "Embedded JPEG", f"{len(ex.thumb):,} bytes"))
            except Exception as e:
                rows.append(("EXIF", "error", str(e)))
        elif ext == ".png":
            try:
                pi = png_info(p.path)
                rows.append(("Image", "PNG", f"bit depth {pi.get('bit_depth')}, colour type {pi.get('color_type')}"))
                for k, v in pi["text"]:
                    rows.append(("PNG text", k, v if len(v) < 500 else v[:500] + "…"))
            except Exception as e:
                rows.append(("PNG", "error", str(e)))
        elif ext in (".mp4", ".mov", ".m4v", ".3gp"):
            try:
                mi = mp4_info(p.path)
                if mi["created"]:
                    rows.append(("Video", "Created", f"{mi['created']:%Y-%m-%d %H:%M:%S}"))
                if mi["duration"]:
                    rows.append(("Video", "Duration", f"{mi['duration']:.1f} s"))
                if mi["width"]:
                    rows.append(("Video", "Dimensions", f"{mi['width']} × {mi['height']}"))
                rows.append(("Video", "Boxes", ", ".join(mi["boxes"])))
            except Exception as e:
                rows.append(("Video", "error", str(e)))
        return rows

    def refresh_meta(self, force=False):
        tree = self.meta_tree
        tree.delete(*tree.get_children())
        sel = self.selected_photos()
        if len(sel) != 1:
            self.meta_title.configure(text="Select one photo to see its metadata")
            self.meta_cur.configure(text="")
            return
        p = sel[0]
        self.meta_title.configure(text=p.name)
        try:
            rows = self.meta_rows(p)
        except Exception as e:
            rows = [("Error", "", str(e))]
        sections = {}
        for sec, field, val in rows:
            if sec not in sections:
                sections[sec] = tree.insert("", "end", text=sec, open=True)
            tree.insert(sections[sec], "end", text="", values=(field, val))
        self._meta_field_changed()

    def _meta_pick(self, _e=None):
        item = self.meta_tree.focus()
        if not item:
            return
        vals = self.meta_tree.item(item, "values")
        if vals and vals[0] in EDITABLE_TAGS:
            self.meta_field.set(vals[0])
            self._meta_field_changed()

    def _meta_field_changed(self):
        sel = self.selected_photos()
        name = self.meta_field.get()
        if len(sel) != 1 or not sel[0].info or not sel[0].info.get("exif"):
            self.meta_cur.configure(text="current: (no EXIF)")
            return
        v = sel[0].info["exif"].get(name)
        self.meta_cur.configure(text=f"current: {v if v is not None else '(not set)'}")
        if isinstance(v, (str, int)):
            self.meta_val.set(str(v))

    def meta_report(self):
        sel = self.selected_photos()
        if not sel:
            return
        out = []
        for p in sel:
            out.append(f"## {p.name}")
            try:
                rows = self.meta_rows(p)
            except Exception as e:
                rows = [("Error", "", str(e))]
            last = None
            for sec, field, val in rows:
                if sec != last:
                    out.append(f"~~ [{sec}]")
                    last = sec
                out.append(f"  {field:<28} {val}")
            out.append("")
        ReportWindow(self, "Metadata", "\n".join(out), save_name="zFileAnal_Metadata.txt", save_dir=self.folder)

    def meta_copy(self):
        sel = self.selected_photos()
        if len(sel) != 1:
            return
        lines = [f"{sec} / {field}: {val}" for sec, field, val in self.meta_rows(sel[0])]
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))

    def _meta_target(self):
        sel = self.selected_photos()
        if len(sel) != 1:
            messagebox.showinfo("Metadata", "Select exactly one photo.", parent=self)
            return None
        p = sel[0]
        if p.ext.lower() not in JPEG_EXT:
            messagebox.showinfo("Metadata", "EXIF editing is only supported for JPEG files.", parent=self)
            return None
        return p

    def _meta_apply(self, p, fields, remove=()):
        desc = "\n".join(f"  {k} = {v}" for k, v in fields.items()) + "".join(f"\n  remove {k}" for k in remove)
        if not messagebox.askyesno("Write EXIF", f"Write into\n{p.name}\n\n{desc}\n\nThe file itself will be "
                                   "modified (its picture data stays untouched). Continue?", parent=self):
            return
        try:
            write_exif_fields(p.path, fields, remove)
        except Exception as e:
            messagebox.showerror("Write EXIF", f"Could not write:\n{e}", parent=self)
            return
        p.info = read_media_info(p.path)
        p.size = os.path.getsize(p.path)
        p.key = None
        p.thumb_py = p.thumb_wic = p.preview = None
        if p.info["taken"]:
            p.sugg_date = p.info["taken"].strftime("%Y%m%d")
            p.sugg_src = p.info["taken_src"]
        self.refresh_meta()
        self._refresh_panel()
        self._set_status(f"EXIF written to {p.name}")

    def meta_write(self):
        p = self._meta_target()
        if not p:
            return
        name = self.meta_field.get()
        val = self.meta_val.get().strip()
        typ = EDITABLE_TAGS[name][2]
        if name.startswith("DateTime"):
            m = re.fullmatch(r"(\d{4})[:\-/]?(\d{2})[:\-/]?(\d{2})(?:[ T](\d{2}):?(\d{2}):?(\d{2}))?", val)
            if not m:
                messagebox.showerror("Date", "Use  YYYY:MM:DD HH:MM:SS", parent=self)
                return
            g = [x or "00" for x in m.groups()]
            val = f"{g[0]}:{g[1]}:{g[2]} {g[3]}:{g[4]}:{g[5]}"
        if typ == 3:
            if not val.isdigit():
                messagebox.showerror("Value", f"{name} must be a whole number.", parent=self)
                return
            val = int(val)
        self._meta_apply(p, {name: val})

    def meta_remove(self):
        p = self._meta_target()
        if p:
            self._meta_apply(p, {}, remove=(self.meta_field.get(),))

    def meta_date_from_name(self):
        p = self._meta_target()
        if not p:
            return
        d = p.date or p.o_date
        if not d or d.endswith("XX"):
            messagebox.showinfo("Date", "This file has no full YYYYMMDD prefix to copy from.", parent=self)
            return
        val = f"{d[:4]}:{d[4:6]}:{d[6:8]} 12:00:00"
        self._meta_apply(p, {"DateTimeOriginal": val, "DateTimeDigitized": val})

    def meta_keywords_from_labels(self):
        p = self._meta_target()
        if not p:
            return
        if not p.labels:
            messagebox.showinfo("Keywords", "This photo has no labels.", parent=self)
            return
        self._meta_apply(p, {"XPKeywords": ";".join(p.labels)})

    # ═══════════════ apply / undo ═══════════════
    def pending_count(self):
        return sum(1 for p in self.photos if p.pending())

    def apply_pending(self):
        pend = [p for p in self.photos if p.pending()]
        if not pend:
            messagebox.showinfo("Apply", "Nothing is staged — tick some labels or add a date first.", parent=self)
            return
        pairs = [(p.path, os.path.join(p.folder, p.proposed())) for p in pend]
        kw_var = tk.BooleanVar(value=self.settings.get("write_exif_keywords", False))

        def extra(dlg):
            return ttk.Checkbutton(dlg, variable=kw_var,
                                   text="Also write the labels into each JPEG's EXIF keywords (Explorer 'Tags')")

        dlg = ConfirmRenameDialog(self, pairs, "Confirm renames", extra_widget=extra)
        if not dlg.result:
            return
        self.settings["write_exif_keywords"] = kw_var.get()
        self._save_prefs()
        done, errors = perform_renames(pairs)
        done_set = {os.path.normcase(o) for o, _ in done}
        kw_errors = []
        for p in pend:
            if os.path.normcase(p.path) in done_set:
                p.name = p.proposed()
                p.refresh_from_disk_name()
                if kw_var.get() and p.ext.lower() in JPEG_EXT:
                    try:
                        write_exif_fields(p.path, {"XPKeywords": ";".join(p.labels)} if p.labels else {},
                                          remove=() if p.labels else ("XPKeywords",))
                        p.info = read_media_info(p.path)
                        p.size = os.path.getsize(p.path)
                        p.key = None
                        p.thumb_py = p.thumb_wic = p.preview = None
                    except Exception as e:
                        kw_errors.append(f"{p.name}: {e}")
        if done:
            self.undo_stack.append(done)
        self.rebuild_view()
        self._refresh_panel()
        self._update_status()
        msg = f"Renamed {len(done)} file(s)."
        if errors:
            msg += "\n\nErrors:\n" + "\n".join(errors[:20])
        if kw_errors:
            msg += "\n\nEXIF keyword errors:\n" + "\n".join(kw_errors[:20])
        (messagebox.showwarning if errors or kw_errors else messagebox.showinfo)("Apply", msg, parent=self)

    def undo_last(self):
        if not self.undo_stack:
            messagebox.showinfo("Undo", "Nothing to undo in this session.", parent=self)
            return
        batch = self.undo_stack[-1]
        pairs = [(new, old) for old, new in batch]
        dlg = ConfirmRenameDialog(self, pairs, "Undo — rename back")
        if not dlg.result:
            return
        done, errors = perform_renames(pairs)
        self.undo_stack.pop()
        if errors:
            messagebox.showwarning("Undo", "Some files could not be renamed back:\n" + "\n".join(errors[:20]), parent=self)
        self.open_folder(self.folder)

    def record_batch(self, done):
        """Tools call this after renaming so Undo covers them too."""
        if done:
            self.undo_stack.append(done)

    # ═══════════════ labels management ═══════════════
    def manage_labels(self):
        LabelManager(self)

    def harvest_labels(self):
        found = {}
        for p in self.photos:
            for l in p.o_labels:
                found[l] = found.get(l, 0) + 1
        known = {l for g in self.settings["label_groups"] for l in g["labels"]}
        cands = sorted((l for l in found if l not in known and not is_date_token(l)), key=lambda l: (-found[l], l))
        if not cands:
            messagebox.showinfo("Labels", "No new labels found in the file names of this folder.", parent=self)
            return
        dlg = FileSelectDialog(self, [f"{l}   ({found[l]} file(s))" for l in cands], "Labels found in file names",
                               action="adding to quick labels")
        if not dlg.result:
            return
        picked = [s.split("   (")[0] for s in dlg.result]
        groups = self.settings["label_groups"]
        if not groups:
            groups.append({"name": "Labels", "labels": []})
        names = [g["name"] for g in groups]
        target = simpledialog.askstring("Group", f"Add to which group? {', '.join(names)}",
                                        initialvalue=names[-1], parent=self)
        g = next((g for g in groups if g["name"].lower() == (target or "").lower()), None)
        if g is None:
            g = {"name": target or "Labels", "labels": []}
            groups.append(g)
        for l in picked:
            if l not in g["labels"]:
                g["labels"].append(l)
        self._save_prefs()
        self._build_quick_labels()

    # ═══════════════ misc ═══════════════
    def _save_prefs(self):
        self.settings["auto_date"] = self.var_autodate.get()
        self.settings["include_videos"] = self.var_videos.get()
        save_settings(self.settings)

    def _set_status(self, text):
        self.status.configure(text=text)

    def _update_status(self):
        n_img = sum(1 for p in self.photos if p.kind == "image")
        n_vid = len(self.photos) - n_img
        pend = self.pending_count()
        thumbs = sum(1 for p in self.photos if p.best_thumb())
        wic = {"ok": "WIC helper on", "starting": "WIC helper starting…", "failed": "WIC helper failed — built-in decoder only",
               "died": "WIC helper stopped", "unavailable": "built-in decoder only"}.get(self.thumbs.wic_state, "")
        self._set_status(f"{n_img} image(s) · {n_vid} video(s) · {pend} staged rename(s) · thumbnails {thumbs}/{n_img} · {wic}")
        self.apply_btn.configure(text=f"Apply {pend} rename{'s' if pend != 1 else ''}…",
                                 state="normal" if pend else "disabled")

    def clear_cache(self):
        n = 0
        for f in os.listdir(CACHE_DIR) if os.path.isdir(CACHE_DIR) else []:
            if f.endswith((".png", ".ppm")):
                try:
                    os.remove(os.path.join(CACHE_DIR, f))
                    n += 1
                except OSError:
                    pass
        messagebox.showinfo("Cache", f"Removed {n} cached thumbnail(s) from\n{CACHE_DIR}", parent=self)

    def on_close(self):
        if self.pending_count():
            if not messagebox.askyesno("Quit", f"{self.pending_count()} staged rename(s) were not applied.\nQuit anyway?",
                                       parent=self):
                return
        self._save_prefs()
        self.thumbs.stop()
        self.destroy()

    def _poll_queue(self):
        try:
            for _ in range(200):
                msg = self.q.get_nowait()
                self._handle(msg)
        except queue.Empty:
            pass
        self.after(60, self._poll_queue)

    def _handle(self, msg):
        kind = msg[0]
        if kind == "scan_progress":
            if msg[1] == self.gen:
                self._set_status(f"Scanning… {msg[2]}/{msg[3]}")
        elif kind == "scan_done":
            if msg[1] == self.gen:
                self._scan_done(msg[2])
        elif kind in ("py_thumb", "wic_thumb"):
            _, gen, i, path = msg
            if gen != self.gen or i >= len(self.photos):
                return
            p = self.photos[i]
            if kind == "py_thumb":
                p.thumb_py = path
            else:
                p.thumb_wic = path
                if path is None and p.thumb_py is None:
                    p.thumb_failed = True
            if path is None and p.thumb_py is None and p.thumb_wic is None and not self.thumbs.wic_ok:
                p.thumb_failed = True
            if path or p.thumb_failed:
                self.scaled.pop(i, None)
                pos = self.view.index(i) if i in self.tiles else -1
                if pos >= 0 and pos in self._visible_positions():
                    _, _, _, box = self._tile_geometry()
                    self._load_tile_image(i, box)
                self._refresh_tile(i)
                if self.preview_for == p.path and kind == "wic_thumb" and not p.preview:
                    self._show_preview(force=True)
            if not getattr(self, "_status_job", None):
                self._status_job = self.after(400, self._status_tick)
        elif kind == "wic_preview":
            _, gen, i, path = msg
            if gen != self.gen or i >= len(self.photos):
                return
            p = self.photos[i]
            p.preview = path
            if path and self.preview_for == p.path:
                self._show_preview(force=True)
        elif kind == "wic_state":
            self._update_status()

    def _status_tick(self):
        self._status_job = None
        self._update_status()

    # ═══════════════ help ═══════════════
    def show_help(self):
        ReportWindow(self, "How naming works", HELP_TEXT)

    def show_shortcuts(self):
        ReportWindow(self, "Keyboard shortcuts", SHORTCUT_TEXT)


HELP_TEXT = """## How zFileAnal v3 builds a file name

  {date}_{label}_{label}_…_{original}{ext}

  20260627_Elliot_Alice_butterfly_IMG_135135.JPG
  └─date──┘ └────── labels ──────┘ └─original─┘

## Date
  · Suggested automatically from the photo's EXIF "date taken" (DateTimeOriginal),
    else the video header, else a date already written in the file name.
  · With "Auto-stage metadata date" on (View menu) every undated file gets its
    metadata date staged as soon as the folder opens. Files whose only date is the
    file-system modification time are NOT auto-staged (that date is unreliable) —
    use the "File date" button for those.
  · Type a date by hand as YYYYMMDD, or YYYYMMXX when the day is unknown.
  · "None" removes the date prefix.

## Labels
  · Tick quick labels (or press 1-9 with the grid focused) to add them to every
    selected file; untick to remove. A half-filled box means only some of the
    selected files carry that label.
  · "Other label" adds a one-off word; "remember" also stores it as a quick label.
  · The list "Labels on selected" shows the order they appear in the name — use
    ▲ ▼ to reorder, ✕ to remove.
  · Spaces and underscores inside a label become dashes (Grandma Jo → Grandma-Jo)
    so every underscore in a name stays a separator.

## Original part
  · The app recognises typical camera names (IMG_1234, DSC_0001, PXL_2024…, 20240627_123456,
    WIN_…, Screenshot…, GOPR…, IMG-20240627-WA0001 …) and keeps them as the "original"
    part. When a name has no recognisable pattern the last underscore-token is used.
    You can always correct it in the "Original part" box.

## Nothing is renamed until you say so
  · Every change is only STAGED: orange tiles show "→ new name".
  · "Apply N renames…" lists every old → new pair, checks for clashes, and only
    renames after you press Apply. "Undo" reverses the last applied batch.

## Metadata
  · The Metadata tab prints everything found: file info, JPEG structure, every EXIF /
    GPS / thumbnail tag, PNG text chunks, MP4 header fields.
  · JPEG EXIF text fields can be edited (dates, description, artist, keywords…).
    The picture data is never re-encoded; the file's modified-time is preserved.
"""

SHORTCUT_TEXT = """## Global
  Ctrl+O        Open folder
  F5            Rescan folder
  Ctrl+S        Apply staged renames (asks for confirmation)
  Ctrl+Z        Undo the last applied batch (asks for confirmation)

## Thumbnail grid (click a tile first so the grid has focus)
  Click / Ctrl+click / Shift+click    select / toggle / range
  Arrows, Home, End, PgUp, PgDn       move the selection
  Ctrl+A / Esc                        select all / none
  1 … 9                               toggle the first nine quick labels
  d                                   use the metadata date
  n                                   remove the date prefix
  Delete                              reset staged changes on the selection
  Enter / double-click                open in the default viewer
  + / -                               more / fewer columns
  Backspace                           go to the parent folder
  Right-click                         context menu
"""


# ─────────────────────────────────────────────
# QUICK-LABEL MANAGER
# ─────────────────────────────────────────────
class LabelManager(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Manage quick labels")
        self.geometry("620x460")
        self.transient(app)
        self.groups = app.settings.setdefault("label_groups", [])
        body = ttk.Frame(self, padding=8)
        body.pack(fill="both", expand=True)
        gl = ttk.Frame(body)
        gl.pack(side="left", fill="both", expand=True)
        ttk.Label(gl, text="Groups", style="H.TLabel").pack(anchor="w")
        self.glist = tk.Listbox(gl, exportselection=False, activestyle="none")
        self.glist.pack(fill="both", expand=True)
        self.glist.bind("<<ListboxSelect>>", lambda e: self.fill_labels())
        gb = ttk.Frame(gl)
        gb.pack(fill="x", pady=4)
        ttk.Button(gb, text="Add", command=self.add_group).pack(side="left")
        ttk.Button(gb, text="Rename", command=self.rename_group).pack(side="left", padx=2)
        ttk.Button(gb, text="Delete", command=self.del_group).pack(side="left")
        ttk.Button(gb, text="▲", width=3, command=lambda: self.move_group(-1)).pack(side="left", padx=(8, 0))
        ttk.Button(gb, text="▼", width=3, command=lambda: self.move_group(1)).pack(side="left")
        ll = ttk.Frame(body)
        ll.pack(side="left", fill="both", expand=True, padx=(12, 0))
        ttk.Label(ll, text="Labels in group", style="H.TLabel").pack(anchor="w")
        self.llist = tk.Listbox(ll, exportselection=False, activestyle="none")
        self.llist.pack(fill="both", expand=True)
        lb = ttk.Frame(ll)
        lb.pack(fill="x", pady=4)
        ttk.Button(lb, text="Add", command=self.add_label).pack(side="left")
        ttk.Button(lb, text="Rename", command=self.rename_label).pack(side="left", padx=2)
        ttk.Button(lb, text="Delete", command=self.del_label).pack(side="left")
        ttk.Button(lb, text="▲", width=3, command=lambda: self.move_label(-1)).pack(side="left", padx=(8, 0))
        ttk.Button(lb, text="▼", width=3, command=lambda: self.move_label(1)).pack(side="left")
        ttk.Label(self, style="Hint.TLabel", padding=(8, 0),
                  text="The first nine labels (in group order) get the 1-9 hotkeys.").pack(anchor="w")
        ttk.Button(self, text="Close", command=self.close).pack(side="right", padx=8, pady=8)
        self.fill_groups()
        self.grab_set()

    def gi(self):
        s = self.glist.curselection()
        return s[0] if s else None

    def li(self):
        s = self.llist.curselection()
        return s[0] if s else None

    def fill_groups(self, select=0):
        self.glist.delete(0, "end")
        for g in self.groups:
            self.glist.insert("end", f"{g['name']}  ({len(g['labels'])})")
        if self.groups:
            self.glist.selection_set(min(select, len(self.groups) - 1))
        self.fill_labels()

    def fill_labels(self, select=0):
        self.llist.delete(0, "end")
        i = self.gi()
        if i is None:
            return
        for l in self.groups[i]["labels"]:
            self.llist.insert("end", l)
        if self.groups[i]["labels"]:
            self.llist.selection_set(min(select, len(self.groups[i]["labels"]) - 1))

    def add_group(self):
        name = simpledialog.askstring("Group", "Group name:", parent=self)
        if name:
            self.groups.append({"name": name.strip(), "labels": []})
            self.fill_groups(len(self.groups) - 1)

    def rename_group(self):
        i = self.gi()
        if i is None:
            return
        name = simpledialog.askstring("Group", "New name:", initialvalue=self.groups[i]["name"], parent=self)
        if name:
            self.groups[i]["name"] = name.strip()
            self.fill_groups(i)

    def del_group(self):
        i = self.gi()
        if i is None:
            return
        if messagebox.askyesno("Delete group", f"Delete group '{self.groups[i]['name']}' and its labels?", parent=self):
            del self.groups[i]
            self.fill_groups(max(0, i - 1))

    def move_group(self, d):
        i = self.gi()
        if i is None or not (0 <= i + d < len(self.groups)):
            return
        self.groups[i], self.groups[i + d] = self.groups[i + d], self.groups[i]
        self.fill_groups(i + d)

    def add_label(self):
        i = self.gi()
        if i is None:
            return
        name = simpledialog.askstring("Label", "Label text:", parent=self)
        if name:
            lab = sanitize_label(name)
            if lab and lab not in self.groups[i]["labels"]:
                self.groups[i]["labels"].append(lab)
                self.fill_groups(i)
                self.fill_labels(len(self.groups[i]["labels"]) - 1)

    def rename_label(self):
        i, j = self.gi(), self.li()
        if i is None or j is None:
            return
        name = simpledialog.askstring("Label", "New text:", initialvalue=self.groups[i]["labels"][j], parent=self)
        if name:
            lab = sanitize_label(name)
            if lab:
                self.groups[i]["labels"][j] = lab
                self.fill_labels(j)

    def del_label(self):
        i, j = self.gi(), self.li()
        if i is None or j is None:
            return
        del self.groups[i]["labels"][j]
        self.fill_groups(i)
        self.fill_labels(max(0, j - 1))

    def move_label(self, d):
        i, j = self.gi(), self.li()
        if i is None or j is None:
            return
        labs = self.groups[i]["labels"]
        if 0 <= j + d < len(labs):
            labs[j], labs[j + d] = labs[j + d], labs[j]
            self.fill_labels(j + d)

    def close(self):
        self.app._save_prefs()
        self.app._build_quick_labels()
        self.destroy()


# ─────────────────────────────────────────────
# TOOLS — the v2.1.1 functions, GUI-driven
# ─────────────────────────────────────────────
TAG_PATTERN = re.compile(r"\[([^\[\]]+)\]")
STUDY_ID_PATTERN = re.compile(r"TSA-\d{5,6}-[a-zA-Z]{3}|TPC\d{1,3}-\d{5}-[a-zA-Z]{2,3}")
MAX_SCAN_SIZE = 100 * 1024 * 1024


def _dir_size(path):
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def _tags_of(name):
    return TAG_PATTERN.findall(os.path.splitext(name)[0])


class Tools:
    """Mixin-style helper bound to the App: every method opens dialogs / reports on app.folder."""

    def __init__(self, app):
        self.app = app

    # helpers
    def folder(self):
        return self.app.folder

    def files(self):
        path = self.folder()
        me = os.path.abspath(__file__)
        return sorted(f for f in os.listdir(path)
                      if os.path.isfile(os.path.join(path, f)) and os.path.abspath(os.path.join(path, f)) != me)

    def report(self, title, text, save_name=None):
        ReportWindow(self.app, title, text, save_name=save_name, save_dir=self.folder())

    def preselect(self):
        return [p.name for p in self.app.selected_photos()]

    def do_renames(self, pairs, title):
        if not pairs:
            messagebox.showinfo(title, "Nothing to rename.", parent=self.app)
            return
        dlg = ConfirmRenameDialog(self.app, pairs, title)
        if not dlg.result:
            return
        done, errors = perform_renames(pairs)
        self.app.record_batch(done)
        msg = f"Renamed {len(done)} item(s)."
        if errors:
            msg += "\n\nErrors:\n" + "\n".join(errors[:20])
        (messagebox.showwarning if errors else messagebox.showinfo)(title, msg, parent=self.app)
        self.app.open_folder(self.folder())

    # 1 — list files alphabetically
    def list_alpha(self):
        path = self.folder()
        lines = ["## Files — Alphabetical", f"~~ Location: {path}", ""]
        for f in sorted(os.listdir(path), key=str.lower):
            full = os.path.join(path, f)
            if os.path.isdir(full):
                lines.append(f"  ▶ {f}/")
            else:
                lines.append(f"    {f}")
        self.report("Files — Alphabetical", "\n".join(lines))

    # 2 — files & folder structure
    def structure(self):
        path = self.folder()
        folders = []
        for item in os.listdir(path):
            ip = os.path.join(path, item)
            if os.path.isdir(ip):
                folders.append((item, _dir_size(ip)))
        folders.sort(key=lambda x: x[1], reverse=True)
        lines = ["## Subfolders (largest first)", f"~~ Location: {path}", "", f"  {'Folder Name':<50} {'Size':>12}", "  " + "─" * 64]
        for name, size in folders:
            lines.append(f"  {name:<50} {fmt_size(size):>12}")
        file_items, total = [], 0
        for item in os.listdir(path):
            ip = os.path.join(path, item)
            if os.path.isfile(ip):
                s = os.path.getsize(ip)
                total += s
                file_items.append((item, s))
        file_items.sort(key=lambda x: x[1], reverse=True)
        lines += ["", "## Files — Current Directory", "", f"  {'File Name':<50} {'Size':>10}   {'Share':>6}", "  " + "─" * 80]
        for name, size in file_items:
            pct = (size / total * 100) if total else 0
            lines.append(f"  {fit_text(name, 50):<50} {fmt_size(size):>10}   {pct:>5.1f}%  {'█' * int(pct / 4)}")
        lines += ["", "## Folder Tree", ""]
        for folder, size in folders:
            lines.append(f"  ▶ {folder}  ({fmt_size(size)})")
            for root, dirs, fs in os.walk(os.path.join(path, folder)):
                for f in sorted(fs):
                    fp = os.path.join(root, f)
                    try:
                        fsize = os.path.getsize(fp)
                    except OSError:
                        fsize = 0
                    lines.append(f"      {os.path.relpath(fp, path)}  {fmt_size(fsize)}")
        self.report("Files & Folder Structure", "\n".join(lines))

    # 3 — add prefix
    def add_prefix(self):
        files = self.files()
        if not files:
            messagebox.showinfo("Add prefix", "No files in this folder.", parent=self.app)
            return
        dlg = FileSelectDialog(self.app, files, "Rename — add prefix", action="the prefix", preselect=self.preselect())
        if not dlg.result:
            return
        prefix = simpledialog.askstring("Prefix", "Prefix (YYYYMMDD or YYYYMMXX):", parent=self.app)
        if prefix is None:
            return
        prefix = prefix.strip().upper()
        if not re.fullmatch(r"\d{6}(?:\d{2}|XX)", prefix):
            messagebox.showerror("Prefix", "Invalid prefix format — use YYYYMMDD or YYYYMMXX.", parent=self.app)
            return
        desc = simpledialog.askstring("Description", "Description (goes after the date):", parent=self.app)
        if desc is None:
            return
        desc = sanitize_label(desc)
        path = self.folder()
        pairs = []
        for f in dlg.result:
            stem, ext = os.path.splitext(f)
            new = f"{prefix}_{desc}_{stem}{ext}" if desc else f"{prefix}_{stem}{ext}"
            pairs.append((os.path.join(path, f), os.path.join(path, new)))
        self.do_renames(pairs, "Rename — add prefix")

    # 4 — remove prefix
    def remove_prefix(self):
        files = self.files()
        prefix = simpledialog.askstring("Remove prefix", "Prefix to remove (YYYYMMDD or YYYYMMXX):", parent=self.app)
        if prefix is None:
            return
        prefix = prefix.strip().upper()
        if not re.fullmatch(r"\d{6}(?:\d{2}|XX)", prefix):
            messagebox.showerror("Prefix", "Invalid prefix format.", parent=self.app)
            return
        pattern = re.compile(r"^" + re.escape(prefix) + r"_(?:[^_]+_)?")
        matched = [f for f in files if pattern.search(f)]
        if not matched:
            messagebox.showinfo("Remove prefix", "No files carry that prefix.", parent=self.app)
            return
        dlg = FileSelectDialog(self.app, matched, "Rename — remove prefix", action="the prefix removal")
        if not dlg.result:
            return
        path = self.folder()
        pairs = [(os.path.join(path, f), os.path.join(path, pattern.sub("", f, count=1))) for f in dlg.result]
        pairs = [(o, n) for o, n in pairs if os.path.basename(n)]
        self.do_renames(pairs, "Rename — remove prefix")

    # 5 — replace spaces
    def replace_spaces(self):
        path = self.folder()
        me = os.path.abspath(__file__)
        spaced = sorted(f for f in os.listdir(path) if " " in f and os.path.abspath(os.path.join(path, f)) != me)
        if not spaced:
            messagebox.showinfo("Replace spaces", "No names with spaces in this folder.", parent=self.app)
            return
        dlg = FileSelectDialog(self.app, spaced, "Replace spaces with underscores", action="the space replacement")
        if not dlg.result:
            return
        pairs = [(os.path.join(path, f), os.path.join(path, f.replace(" ", "_"))) for f in dlg.result]
        self.do_renames(pairs, "Replace spaces")

    # 6 — tags
    def tags_view(self):
        files = self.files()
        counts, owners = {}, {}
        for f in files:
            for t in _tags_of(f):
                counts[t] = counts.get(t, 0) + 1
                owners.setdefault(t, []).append(f)
        if not counts:
            messagebox.showinfo("Tags", "No [tags] found on any file in this folder.", parent=self.app)
            return
        lines = ["## Tags — View All", f"~~ {self.folder()}", "", f"  {'Tag':<30} {'Files':>6}", "  " + "─" * 40]
        for tag, n in sorted(counts.items(), key=lambda x: (-x[1], x[0].lower())):
            lines.append(f"  [{tag}]{'':<{max(0, 28 - len(tag))}} {n:>6}")
        lines.append("")
        for tag in sorted(owners, key=str.lower):
            lines.append(f"## [{tag}]")
            for f in owners[tag]:
                lines.append(f"    · {f}")
        self.report("Tags", "\n".join(lines))

    def tags_edit(self):
        files = self.files()
        counts = {}
        for f in files:
            for t in _tags_of(f):
                counts[t] = counts.get(t, 0) + 1
        if not counts:
            messagebox.showinfo("Tags", "No [tags] found in this folder.", parent=self.app)
            return
        opts = sorted(counts, key=lambda t: (-counts[t], t.lower()))
        old = ChoiceDialog(self.app, "Edit a tag across the folder", "Tag to edit:",
                           [f"{t}   ({counts[t]} file(s))" for t in opts]).result
        if not old:
            return
        old = old.split("   (")[0]
        new = simpledialog.askstring("Edit tag", f"New value for [{old}]:", initialvalue=old, parent=self.app)
        if not new:
            return
        new = new.strip()
        if "[" in new or "]" in new:
            messagebox.showerror("Tag", "Tag cannot contain [ or ].", parent=self.app)
            return
        path = self.folder()
        pairs = []
        for f in files:
            if old in _tags_of(f):
                stem, ext = os.path.splitext(f)
                pairs.append((os.path.join(path, f), os.path.join(path, stem.replace(f"[{old}]", f"[{new}]") + ext)))
        self.do_renames(pairs, "Tags — edit across folder")

    def tags_add(self):
        files = self.files()
        if not files:
            return
        dlg = FileSelectDialog(self.app, files, "Add a [tag] to files", action="the new tag", preselect=self.preselect())
        if not dlg.result:
            return
        tag = simpledialog.askstring("Add tag", "Tag text (without brackets):", parent=self.app)
        if not tag:
            return
        tag = tag.strip()
        if "[" in tag or "]" in tag:
            messagebox.showerror("Tag", "Tag cannot contain [ or ].", parent=self.app)
            return
        path = self.folder()
        pairs = []
        for f in dlg.result:
            stem, ext = os.path.splitext(f)
            sep = "" if (not stem or stem.endswith("_")) else "_"
            pairs.append((os.path.join(path, f), os.path.join(path, f"{stem}{sep}[{tag}]{ext}")))
        self.do_renames(pairs, "Tags — add")

    def tags_reorder(self):
        tagged = [f for f in self.files() if len(_tags_of(f)) >= 2]
        if not tagged:
            messagebox.showinfo("Tags", "No file in this folder has two or more [tags].", parent=self.app)
            return
        f = ChoiceDialog(self.app, "Reorder tags on one file", "File:", tagged).result
        if not f:
            return
        stem, ext = os.path.splitext(f)
        parts = re.split(r"(\[[^\[\]]+\])", stem)
        slots = [i for i, p in enumerate(parts) if TAG_PATTERN.fullmatch(p)]
        tags = [TAG_PATTERN.fullmatch(parts[i]).group(1) for i in slots]
        new_order = OrderDialog(self.app, f"Reorder tags — {f}", tags).result
        if not new_order:
            return
        for slot, tag in zip(slots, new_order):
            parts[slot] = f"[{tag}]"
        new = "".join(parts) + ext
        path = self.folder()
        self.do_renames([(os.path.join(path, f), os.path.join(path, new))], "Tags — reorder")

    # 7 — group media by date
    def group_by_date(self):
        path = self.folder()
        groups = {}
        for f in sorted(os.listdir(path)):
            fp = os.path.join(path, f)
            if not os.path.isfile(fp):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in IMAGE_EXT and ext not in VIDEO_EXT:
                continue
            m = re.search(r"(\d{8}|\d{6}XX)", f)
            if not m:
                continue
            g = groups.setdefault(m.group(1), {"images": [], "videos": [], "size": 0, "tags": set()})
            g["images" if ext in IMAGE_EXT else "videos"].append(f)
            g["size"] += os.path.getsize(fp)
            g["tags"].update(re.findall(r"_(.*?)_", f))
        if not groups:
            messagebox.showinfo("Media by date", "No dated media files found.", parent=self.app)
            return
        lines = ["## Media — Group by Date", f"~~ {path}", ""]
        for pfx, d in sorted(groups.items()):
            lines.append(f"## Date block: {pfx}")
            lines.append(f"  Images: {len(d['images'])}   Videos: {len(d['videos'])}   Total size: {fmt_size(d['size'])}")
            if d["tags"]:
                lines.append(f"  Tags: {', '.join(sorted(d['tags']))}")
            for f in sorted(d["images"] + d["videos"]):
                lines.append(f"    · {f}")
            lines.append("")
        self.report("Media — Group by Date", "\n".join(lines))

    # 8 — list subfolders / files & save
    def list_and_save(self, mode):
        path = self.folder()
        me = os.path.abspath(__file__)
        if mode == "folders":
            items = sorted(os.path.join(r, d) for r, ds, _ in os.walk(path) for d in ds)
            noun, tag = "subfolders", "subfolders"
        else:
            items = sorted(os.path.join(r, f) for r, _, fs in os.walk(path) for f in fs
                           if os.path.abspath(os.path.join(r, f)) != me)
            noun, tag = "files", "files"
        lines = [f"## {noun.capitalize()} — List & Save", f"~~ Found {len(items):,} {noun} under: {path}", ""]
        for it in items:
            rel = os.path.relpath(it, path)
            depth = rel.count(os.sep)
            lines.append("  " + "    " * depth + ("▶ " if mode == "folders" else "· ") + os.path.basename(it))
        lines += ["", "## Full paths", ""] + items
        ts = datetime.datetime.now().strftime("%Y%m%d%H%M")
        self.report(f"{noun.capitalize()} — List & Save", "\n".join(lines), save_name=f"zfileanaloutput_{tag}_list_{ts}.txt")

    # 9 — find study IDs
    def find_study_ids(self):
        base = self.folder()
        win = ReportWindow(self.app, "Scanning — Find Study IDs", "Scanning…  (this window fills in when done)",
                           save_name=f"zFileAnal_Studies_{datetime.datetime.now():%Y%m%d%H%M}.txt", save_dir=base)

        def work():
            found = {}
            dir_count = 0
            for root, dirs, files in os.walk(base):
                dir_count += 1
                for name in dirs:
                    for m in STUDY_ID_PATTERN.finditer(name):
                        found.setdefault(m.group(), set()).add(("in Folder Name", os.path.join(root, name)))
                for name in files:
                    fp = os.path.join(root, name)
                    for m in STUDY_ID_PATTERN.finditer(name):
                        found.setdefault(m.group(), set()).add(("in File Name", fp))
                    try:
                        if os.path.getsize(fp) <= MAX_SCAN_SIZE:
                            with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                                for line in fh:
                                    for m in STUDY_ID_PATTERN.finditer(line):
                                        found.setdefault(m.group(), set()).add(("in File Content", fp))
                    except (IOError, OSError):
                        pass
            lines = ["## Study ID Scan Report", f"~~ Generated : {datetime.datetime.now()}", f"~~ Base path : {base}",
                     f"~~ {dir_count:,} folders scanned", ""]
            if not found:
                lines.append("  No Study IDs found.")
            else:
                lines.append(f"## {len(found)} unique Study IDs located")
                for sid, locs in sorted(found.items()):
                    lines.append(f"\n  {sid}")
                    for ctx, fp in sorted(locs):
                        lines.append(f"    · {ctx}: {os.path.relpath(fp, base)}")
            text = "\n".join(lines)
            self.app.after(0, lambda: win.winfo_exists() and win.set_text(text))

        threading.Thread(target=work, daemon=True).start()

    # 10 — compare two folders
    def compare_folders(self):
        dlg = CompareDialog(self.app, self.folder())
        if not dlg.result:
            return
        path_a, path_b, hash_mode = dlg.result
        win = ReportWindow(self.app, "Compare Two Folders", "Scanning…  (this window fills in when done)",
                           save_name=f"zFileAnal_FolderCompare_{datetime.datetime.now():%Y%m%d%H%M}.txt",
                           save_dir=self.folder())

        def sha256(fp, chunk=1024 * 1024):
            h = hashlib.sha256()
            with open(fp, "rb") as f:
                while True:
                    d = f.read(chunk)
                    if not d:
                        break
                    h.update(d)
            return h.hexdigest()

        def scan_tree(base):
            files, folders = {}, set()
            for root, dirs, filenames in os.walk(base):
                rel_root = os.path.relpath(root, base)
                rel_root = "" if rel_root == "." else rel_root
                for d in dirs:
                    folders.add(os.path.normcase(os.path.join(rel_root, d)))
                for fn in filenames:
                    rel = os.path.join(rel_root, fn)
                    full = os.path.join(root, fn)
                    try:
                        st = os.stat(full)
                        files[os.path.normcase(rel)] = {"rel": os.path.normpath(rel), "full": full,
                                                        "size": st.st_size, "mtime": st.st_mtime}
                    except OSError:
                        continue
            return files, folders

        def ts(t):
            return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")

        def work():
            fa, da = scan_tree(path_a)
            fb, db = scan_tree(path_b)
            common = sorted(set(fa) & set(fb))
            only_a, only_b = sorted(set(fa) - set(fb)), sorted(set(fb) - set(fa))
            only_a_d, only_b_d = sorted(da - db), sorted(db - da)
            identical, different, hashed = [], [], 0
            for k in common:
                a, b = fa[k], fb[k]
                size_eq = a["size"] == b["size"]
                mtime_eq = abs(a["mtime"] - b["mtime"]) <= 2.0
                if size_eq and mtime_eq and hash_mode != 2:
                    identical.append((a, b, "size+mtime"))
                    continue
                if hash_mode == 0:
                    different.append((a, b, "size/mtime differs"))
                    continue
                try:
                    if sha256(a["full"]) == sha256(b["full"]):
                        identical.append((a, b, "sha256"))
                        hashed += 1
                    else:
                        different.append((a, b, "sha256 differs"))
                except OSError:
                    different.append((a, b, "hash error"))
            L = ["## FOLDER COMPARISON REPORT", f"~~ Generated : {datetime.datetime.now()}", f"~~ Folder A  : {path_a}",
                 f"~~ Folder B  : {path_b}", f"~~ Hash mode : {hash_mode}", "", "## SUMMARY",
                 f"  Common folders    : {len(da & db)}", f"  Folders only in A : {len(only_a_d)}",
                 f"  Folders only in B : {len(only_b_d)}", "", f"  Common files      : {len(common)}",
                 f"  Identical         : {len(identical)} (hash-verified: {hashed})",
                 f"  Different         : {len(different)}", f"  Only in A         : {len(only_a)}",
                 f"  Only in B         : {len(only_b)}"]
            for title, items in (("FOLDERS ONLY IN A", only_a_d), ("FOLDERS ONLY IN B", only_b_d),
                                 ("FILES ONLY IN A", [fa[k]["rel"] for k in only_a]),
                                 ("FILES ONLY IN B", [fb[k]["rel"] for k in only_b])):
                L += ["", f"## {title}"] + ([f"  • {x}" for x in items] or ["  (none)"])
            L += ["", "## DIFFERENT / MODIFIED FILES"]
            for a, b, reason in different:
                nw = "Same mtime" if abs(a["mtime"] - b["mtime"]) <= 2 else ("A newer" if a["mtime"] > b["mtime"] else "B newer")
                L.append(f"  • {a['rel']}  [{reason}]  [{nw}]")
                L.append(f"      A: size={a['size']}  mtime={ts(a['mtime'])}")
                L.append(f"      B: size={b['size']}  mtime={ts(b['mtime'])}")
            if not different:
                L.append("  (none)")
            L += ["", "## IDENTICAL FILES"] + [f"  • {a['rel']}  [{how}]" for a, b, how in identical]
            text = "\n".join(L)
            self.app.after(0, lambda: win.winfo_exists() and win.set_text(text))

        threading.Thread(target=work, daemon=True).start()


class ChoiceDialog(tk.Toplevel):
    def __init__(self, master, title, prompt, options):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.result = None
        ttk.Label(self, text=prompt, padding=8).pack(anchor="w")
        fr = ttk.Frame(self)
        fr.pack(fill="both", expand=True, padx=8)
        self.lb = tk.Listbox(fr, height=min(20, max(5, len(options))), width=70, exportselection=False, activestyle="none")
        vs = ttk.Scrollbar(fr, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=vs.set)
        self.lb.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for o in options:
            self.lb.insert("end", o)
        self.lb.selection_set(0)
        self.lb.bind("<Double-Button-1>", lambda e: self._ok())
        bar = ttk.Frame(self, padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="OK", command=self._ok).pack(side="right", padx=6)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.wait_window()

    def _ok(self):
        s = self.lb.curselection()
        if s:
            self.result = self.lb.get(s[0])
        self.destroy()


class OrderDialog(tk.Toplevel):
    def __init__(self, master, title, items):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.result = None
        self.items = list(items)
        ttk.Label(self, text="Use ▲ ▼ to put the tags in the order you want:", padding=8).pack(anchor="w")
        fr = ttk.Frame(self)
        fr.pack(fill="both", expand=True, padx=8)
        self.lb = tk.Listbox(fr, height=max(4, len(items)), width=50, exportselection=False, activestyle="none")
        self.lb.pack(side="left", fill="both", expand=True)
        for it in self.items:
            self.lb.insert("end", f"[{it}]")
        self.lb.selection_set(0)
        b = ttk.Frame(fr)
        b.pack(side="left", padx=6)
        ttk.Button(b, text="▲", width=3, command=lambda: self.move(-1)).pack()
        ttk.Button(b, text="▼", width=3, command=lambda: self.move(1)).pack()
        bar = ttk.Frame(self, padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="OK", command=self._ok).pack(side="right", padx=6)
        self.grab_set()
        self.wait_window()

    def move(self, d):
        s = self.lb.curselection()
        if not s:
            return
        i = s[0]
        j = i + d
        if 0 <= j < len(self.items):
            self.items[i], self.items[j] = self.items[j], self.items[i]
            self.lb.delete(0, "end")
            for it in self.items:
                self.lb.insert("end", f"[{it}]")
            self.lb.selection_set(j)

    def _ok(self):
        self.result = list(self.items)
        self.destroy()


class CompareDialog(tk.Toplevel):
    def __init__(self, master, default_a):
        super().__init__(master)
        self.title("Compare two folders")
        self.transient(master)
        self.result = None
        self.a = tk.StringVar(value=default_a)
        self.b = tk.StringVar()
        self.mode = tk.IntVar(value=1)
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        for r, (lab, var) in enumerate((("Folder A:", self.a), ("Folder B:", self.b))):
            ttk.Label(body, text=lab).grid(row=r, column=0, sticky="w", pady=3)
            ttk.Entry(body, textvariable=var, width=70).grid(row=r, column=1, padx=4)
            ttk.Button(body, text="Browse…", command=lambda v=var: self._browse(v)).grid(row=r, column=2)
        ttk.Label(body, text="Hash options:", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", pady=(10, 2))
        for k, txt in ((0, "No hashing — fast, size + mtime only"), (1, "Hash differing files only (recommended)"),
                       (2, "Hash all common files (slowest, most accurate)")):
            ttk.Radiobutton(body, text=txt, variable=self.mode, value=k).grid(row=3 + k, column=0, columnspan=3, sticky="w")
        bar = ttk.Frame(self, padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="Compare", command=self._ok).pack(side="right", padx=6)
        self.grab_set()
        self.wait_window()

    def _browse(self, var):
        d = filedialog.askdirectory(parent=self, initialdir=var.get() or os.getcwd())
        if d:
            var.set(d)

    def _ok(self):
        a, b = self.a.get().strip().strip('"'), self.b.get().strip().strip('"')
        for lab, p in (("A", a), ("B", b)):
            if not os.path.isdir(p):
                messagebox.showerror("Compare", f"Folder {lab} is not a valid directory:\n{p}", parent=self)
                return
        self.result = (a, b, self.mode.get())
        self.destroy()


def _build_tools_menu(self, m):
    """Attached to App: the Tools menu mirrors the v2 main menu (categories kept)."""
    t = self.tools = Tools(self)
    m.add_command(label="FILES / FOLDERS", state="disabled")
    m.add_command(label="  1  List files alphabetically", command=t.list_alpha)
    m.add_command(label="  2  List files & folder structure (sizes)", command=t.structure)
    m.add_separator()
    m.add_command(label="NAMING", state="disabled")
    m.add_command(label="  3  Rename files — add prefix", command=t.add_prefix)
    m.add_command(label="  4  Rename files — remove prefix", command=t.remove_prefix)
    m.add_command(label="  5  Replace spaces in names", command=t.replace_spaces)
    m.add_separator()
    m.add_command(label="TAGGING  [tag]", state="disabled")
    m.add_command(label="  6a View all tags (counts + files)", command=t.tags_view)
    m.add_command(label="  6b Edit a tag across the folder", command=t.tags_edit)
    m.add_command(label="  6c Add a tag to specific files", command=t.tags_add)
    m.add_command(label="  6d Reorder tags on one file", command=t.tags_reorder)
    m.add_separator()
    m.add_command(label="MEDIA", state="disabled")
    m.add_command(label="  7  Group image/video files by date", command=t.group_by_date)
    m.add_separator()
    m.add_command(label="SCANNING", state="disabled")
    m.add_command(label="  8a List subfolders (recursive) & save", command=lambda: t.list_and_save("folders"))
    m.add_command(label="  8b List files (recursive) & save", command=lambda: t.list_and_save("files"))
    m.add_command(label="  9  Find Study IDs in files & folders", command=t.find_study_ids)
    m.add_separator()
    m.add_command(label="COMPARISON", state="disabled")
    m.add_command(label="  10 Compare two folders (recursive)", command=t.compare_folders)


App._build_tools_menu = _build_tools_menu


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else None
    app = App(start)
    app.mainloop()
