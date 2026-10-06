import json
import os


def lz77_compress(data, window=255, lookahead=25):
    i, out = 0, []
    while i < len(data):
        best_len, best_off = 0, 0
        for j in range(max(0, i - window), i):
            k = 0
            while k < lookahead and i + k < len(data) and data[j + k] == data[i + k]:
                k += 1
            if k > best_len or (k == best_len and k > 0):
                best_len, best_off = k, i - j
        nxt = data[i + best_len] if i + best_len < len(data) else ""
        out.append((best_off, best_len, nxt))
        i += best_len + 1
    return out


def lz77_decompress(tokens):
    out = []
    for off, length, ch in tokens:
        for _ in range(length):
            out.append(out[-off])
        if ch:
            out.append(ch)
    return "".join(out)


def choose_file(title):
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


def compress_file():
    path = choose_file("Select a text file to compress")
    if not path or not os.path.isfile(path):
        print("No valid file selected.")
        return
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    tokens = lz77_compress(text)
    root, ext = os.path.splitext(path)
    out_path = f"{root}_compressed{ext or '.txt'}"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False)

    print(f"Done! {len(text)} chars -> {len(tokens)} tokens")
    print(f"Saved to: {out_path}")


def decompress_file():
    path = choose_file("Select a .lz77 file to decompress")
    if not path or not os.path.isfile(path):
        print("No valid file selected.")
        return
    with open(path, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    text = lz77_decompress(tokens)
    base = path[:-5] if path.endswith(".lz77") else path
    root, ext = os.path.splitext(base)
    out_path = f"{root}_decompressed{ext or '.txt'}"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Done! Restored {len(text)} chars")
    print(f"Saved to: {out_path}")


def main():
    while True:
        print("\n=== LZ77 Tool ===")
        print("1) Compress a file")
        print("2) Decompress a file")
        print("3) Exit")
        choice = input("Choose: ").strip()
        if choice == "1":
            compress_file()
        elif choice == "2":
            decompress_file()
        elif choice == "3":
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
