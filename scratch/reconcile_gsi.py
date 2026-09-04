"""
Deep reconciliation script for GSI PDF parser vs Source.
"""
import re
import zlib
import collections

pdf_path = "/Users/yashgautam/Desktop/risksetu/database/landslide_report.pdf"

with open(pdf_path, 'rb') as f:
    data = f.read()

stream_pattern = re.compile(rb"<<(.*?)>>\s*stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
all_streams = []
cmaps = {}
for m in stream_pattern.finditer(data):
    dict_part = m.group(1)
    stream_bytes = m.group(2)
    try:
        decomp = zlib.decompress(stream_bytes)
        all_streams.append((dict_part, decomp))
        if b"/CIDInit" in decomp or b"beginbfchar" in decomp or b"beginbfrange" in decomp:
            cmap_dict = {}
            for block in re.finditer(rb"beginbfchar\s*(.*?)\s*endbfchar", decomp, re.DOTALL):
                lines = block.group(1).split()
                for i in range(0, len(lines)-1, 2):
                    src = lines[i].strip(b"<>")
                    dst = lines[i+1].strip(b"<>")
                    try:
                        cmap_dict[int(src, 16)] = bytes.fromhex(dst.decode('ascii')).decode('utf-16-be', errors='ignore')
                    except Exception:
                        pass
            for block in re.finditer(rb"beginbfrange\s*(.*?)\s*endbfrange", decomp, re.DOTALL):
                tokens = block.group(1).split()
                idx = 0
                while idx < len(tokens) - 2:
                    src_start = int(tokens[idx].strip(b"<>"), 16)
                    src_end = int(tokens[idx+1].strip(b"<>"), 16)
                    dst_token = tokens[idx+2]
                    idx += 3
                    if dst_token.startswith(b"<"):
                        dst_hex = dst_token.strip(b"<>")
                        try:
                            dst_val = int(dst_hex, 16)
                            for offset in range(src_end - src_start + 1):
                                cmap_dict[src_start + offset] = chr(dst_val + offset)
                        except Exception:
                            pass
            cmaps[len(all_streams)-1] = cmap_dict
    except Exception:
        pass

global_cmap = {}
for c in cmaps.values():
    global_cmap.update(c)

raw_lines = []
for s_idx, (dict_part, content) in enumerate(all_streams):
    if b"BT" in content and b"ET" in content:
        for tm in re.finditer(rb"<([0-9a-fA-F]+)>\s*Tj", content):
            hex_str = tm.group(1).decode('ascii')
            line = "".join([global_cmap.get(int(hex_str[i:i+4], 16), '') for i in range(0, len(hex_str), 4)]).strip()
            if line:
                raw_lines.append(line)
                
        for tm in re.finditer(rb"\[(.*?)\]\s*TJ", content, re.DOTALL):
            tj_content = tm.group(1)
            chars = []
            for hex_part in re.findall(rb"<([0-9a-fA-F]+)>", tj_content):
                h = hex_part.decode('ascii')
                for i in range(0, len(h), 4):
                    chars.append(global_cmap.get(int(h[i:i+4], 16), ''))
            line = "".join(chars).strip()
            if line:
                raw_lines.append(line)

print(f"Total extracted raw lines: {len(raw_lines)}")

# Let's check headers, page titles, table headers
header_lines = [l for l in raw_lines if l.startswith("Sl.No.") or "National Landslide Susceptibility Mapping" in l or "GEOLOGICAL SURVEY OF INDIA" in l]
print(f"Header/Title lines: {len(header_lines)}")

# Lines with serial numbers or coordinates
coord_pattern = re.compile(r'(\d{1,2}\.\d{2,7})\s*(\d{2,3}\.\d{2,7})')

valid_coord_lines = []
invalid_coord_lines = []
no_coord_lines = []

for l in raw_lines:
    if l.startswith("Sl.No.") or "National Landslide" in l or "GEOLOGICAL SURVEY" in l:
        continue
    m = coord_pattern.search(l)
    if m:
        lat = float(m.group(1))
        lon = float(m.group(2))
        if 6.0 <= lat <= 38.0 and 68.0 <= lon <= 98.0:
            valid_coord_lines.append((l, lat, lon))
        else:
            invalid_coord_lines.append((l, lat, lon))
    else:
        no_coord_lines.append(l)

print(f"Valid coordinate records: {len(valid_coord_lines)}")
print(f"Invalid coordinate records (out of India bounds): {len(invalid_coord_lines)}")
print(f"Non-coordinate lines (wrapped text, headers, remarks): {len(no_coord_lines)}")

# Let's inspect serial numbers if available
# Check highest serial number or total unique serials
serial_pattern = re.compile(r'^(\d{1,6})([A-Z])')
serials = []
for l in raw_lines:
    m = serial_pattern.match(l)
    if m:
        serials.append(int(m.group(1)))

print(f"Matched serial numbers count: {len(serials)}")
if serials:
    print(f"Max serial number: {max(serials)}, Min serial number: {min(serials)}")

print("\nSample no-coord lines:")
for l in no_coord_lines[:20]:
    print("  ", repr(l))

if invalid_coord_lines:
    print("\nInvalid coord lines:")
    for l in invalid_coord_lines[:10]:
        print("  ", repr(l))
