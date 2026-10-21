import heapq
import json
import math
import os
 
 

def choose_open_file(title):
    """Open a file picker; fall back to typing the path if tkinter isn't available."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(title=title)
        root.destroy()
        return path
    except Exception:
        return input(f"{title} (type path): ").strip().strip('"')
 
 
def choose_save_file(title, extension):
    """Open a save dialog; fall back to typing the path if tkinter isn't available."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.asksaveasfilename(title=title, defaultextension=extension)
        root.destroy()
        return path
    except Exception:
        return input(f"{title} (type path): ").strip().strip('"')
 
 

def huffman(probs):
    """probs {symbol: probability} -> {symbol: code}"""
    if len(probs) == 1:
        return {s: "0" for s in probs}
    heap = [(p, i, {s: ""}) for i, (s, p) in enumerate(probs.items())]
    heapq.heapify(heap)
    n = len(heap)
    while len(heap) > 1:
        p1, _, a = heapq.heappop(heap)
        p2, _, b = heapq.heappop(heap)
        merged = {s: "0" + c for s, c in a.items()}
        merged.update({s: "1" + c for s, c in b.items()})
        heapq.heappush(heap, (p1 + p2, n, merged))
        n += 1
    return heap[0][2]
 
 
def count_symbols(text):
    """text -> {symbol: count}"""
    counts = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    return counts
 
 
def make_codes(counts, limit):
    """counts {symbol: count} -> {symbol: final code}"""
    total = sum(counts.values())
    probs = {s: c / total for s, c in counts.items()}
 
    # original codes: number every symbol in binary (9 symbols -> 0000..1000)
    symbols = sorted(probs)
    width = max(1, math.ceil(math.log2(len(symbols))))
    original = {s: format(i, "0%db" % width) for i, s in enumerate(symbols)}
 
    # group the rare symbols into "Others" (key is 6 chars, symbols are 1 char)
    table = {s: p for s, p in probs.items() if p > limit}
    others = [s for s in probs if probs[s] <= limit]
    if others:
        table["Others"] = sum(probs[s] for s in others)
 
    huff = huffman(table)
 
    codes = {}
    for s in probs:
        if s in others:
            codes[s] = huff["Others"] + original[s]
        else:
            codes[s] = huff[s]
    return codes
 
 

def compress(text, limit):
    """text -> bytes (overhead line + bits packed 8 per byte)"""
    counts = count_symbols(text)
    codes = make_codes(counts, limit)
 
    bits = "".join(codes[ch] for ch in text)
    nbits = len(bits)
    bits += "0" * (-nbits % 8)                       # pad to full bytes
    data = int(bits, 2).to_bytes(len(bits) // 8, "big")
 
    overhead = json.dumps({"limit": limit, "counts": counts, "no_bits": nbits})
    return overhead.encode("utf-8") + b"\n" + data
 
 
def decompress(raw):
    """bytes (overhead line + packed bits) -> text"""
    line, data = raw.split(b"\n", 1)
    info = json.loads(line.decode("utf-8"))
 
    codes = make_codes(info["counts"], info["limit"])
    decode = {c: s for s, c in codes.items()}
 
    bits = bin(int.from_bytes(data, "big"))[2:].zfill(len(data) * 8)[:info["nbits"]]
    text, current = [], ""
    for b in bits:
        current += b
        if current in decode:
            text.append(decode[current])
            current = ""
    return "".join(text)
 
 

def compress_file(limit):
    path = choose_open_file("Select a text file to compress")
    if not path or not os.path.isfile(path):
            print("No valid file selected.")
            return
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
 
    compressed = compress(text, limit)
    root, ext = os.path.splitext(path)
    out_path = f"{root}_compressed{ext or '.bin'}"
    with open(out_path, "wb") as f:
        f.write(compressed)
 
    return len(text.encode("utf-8")), len(compressed)
 
 

def decompress_file():
    path = choose_open_file("Select a binary file to decompress")
    if not path or not os.path.isfile(path):
            print("No valid file selected.")
            return
    with open(path, "rb") as f:
        raw = f.read()
 
    text = decompress(raw)
    root, ext = os.path.splitext(path)
    out_path = f"{root}_decompressed{ext or '.txt'}"
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
 
 

def main():
    while True:   
        print("\n===Modified Huffman Coding===")
        print("1) Compress") 
        print("2) Deompress")
        print("3) Exit")  
        choice = input("Choose: ").strip()
 
        if choice == "1":
            limit = float(input("Minimum probability limit (e.g. 0.05): "))
      
            old, new = compress_file(limit)
            print("Done: %d bytes -> %d bytes" % (old, new))
        elif choice == "2":
    
            decompress_file()
            print("Done.")
        elif choice == "3":
            break   
        else:
            print("Invalid choice.")    
 
 
if __name__ == "__main__":
    main()





