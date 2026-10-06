"""
gui.py - the Tkinter window. It only handles the interface: all real work is
done by compressor.py / decompressor.py in a background thread.
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import file_utils
from compressor import compress_file
from decompressor import FORMAT_BINARY, FORMAT_TAGS, decompress_file
from lz77 import LZ77Error

COMPRESS = "compress"
DECOMPRESS = "decompress"

FORMAT_LABELS = {FORMAT_TAGS: "LZ77 Text Tags", FORMAT_BINARY: "LZ77 Binary"}

POLL_INTERVAL_MS = 100
PREVIEW_CHARS = 3000


def describe_compress(result, source, target):
    percent = (result.compressed_size / result.original_size * 100
               if result.original_size else 0)
    text = "Compressed (%s): %s -> %s bytes (%.1f%% of the original size, %d tokens)" % (
        FORMAT_LABELS[result.output_format], format(result.original_size, ","),
        format(result.compressed_size, ","), percent, result.token_count)
    if result.verified:
        text += "\nLossless verification passed: the output reconstructs the exact original."
    return text + "\nSaved to: " + target


def describe_decompress(result, source, target):
    return ("Decompressed (detected: %s): %s -> %s bytes\n"
            "Checksum verified: the restored data matches the original.\n"
            "Saved to: %s") % (FORMAT_LABELS[result.detected_format],
                               format(result.compressed_size, ","),
                               format(result.restored_size, ","), target)


class LZ77App:
    def __init__(self, root):
        self.root = root
        root.title("LZ77 Compressor")

        self.mode = tk.StringVar(value=COMPRESS)
        self.output_format = tk.StringVar(value=FORMAT_TAGS)
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.verify = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Choose an input file to begin.")

        # While True, the output name follows the input name automatically.
        # It becomes False once the user picks or types an output name.
        self._auto_output = True
        self._last_suggestion = ""
        self._results = queue.Queue()      # worker thread -> GUI thread

        self._build_widgets()
        self.input_path.trace_add("write", lambda *_: self._refresh_output_suggestion())

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_widgets(self):
        frame = ttk.Frame(self.root, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(9, weight=1)

        mode_box = ttk.LabelFrame(frame, text="What do you want to do?", padding=8)
        mode_box.grid(row=0, column=0, columnspan=3, sticky="ew")
        ttk.Radiobutton(mode_box, text="Compress", value=COMPRESS,
                        variable=self.mode, command=self._on_mode_changed
                        ).grid(row=0, column=0, padx=(0, 16))
        ttk.Radiobutton(mode_box, text="Decompress", value=DECOMPRESS,
                        variable=self.mode, command=self._on_mode_changed
                        ).grid(row=0, column=1)

        format_box = ttk.LabelFrame(frame, text="Output Format (Compress)", padding=8)
        format_box.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.tags_radio = ttk.Radiobutton(
            format_box, text="LZ77 Text Tags  <position, length, nextSymbol>",
            value=FORMAT_TAGS, variable=self.output_format,
            command=self._on_format_changed)
        self.tags_radio.grid(row=0, column=0, padx=(0, 16))
        self.binary_radio = ttk.Radiobutton(
            format_box, text="Binary (real compressed file)",
            value=FORMAT_BINARY, variable=self.output_format,
            command=self._on_format_changed)
        self.binary_radio.grid(row=0, column=1)

        ttk.Label(frame, text="Input File:").grid(row=2, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(frame, textvariable=self.input_path, width=55
                  ).grid(row=2, column=1, sticky="ew", padx=6, pady=(12, 0))
        ttk.Button(frame, text="Browse...", command=self._browse_input
                   ).grid(row=2, column=2, pady=(12, 0))

        ttk.Label(frame, text="Output File:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        output_entry = ttk.Entry(frame, textvariable=self.output_path, width=55)
        output_entry.grid(row=3, column=1, sticky="ew", padx=6, pady=(8, 0))
        output_entry.bind("<KeyRelease>", self._on_output_typed)
        ttk.Button(frame, text="Choose Output...", command=self._browse_output
                   ).grid(row=3, column=2, pady=(8, 0))

        self.verify_check = ttk.Checkbutton(
            frame, text="Verify the result after compressing (recommended)",
            variable=self.verify)
        self.verify_check.grid(row=4, column=1, columnspan=2, sticky="w", pady=(8, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        buttons.columnconfigure(0, weight=1)
        self.start_button = ttk.Button(buttons, text="Start", command=self._start)
        self.start_button.grid(row=0, column=0, sticky="ew")
        self.open_button = ttk.Button(buttons, text="Open Output",
                                      command=self._open_output, state="disabled")
        self.open_button.grid(row=0, column=1, padx=(8, 0))

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        ttk.Label(frame, textvariable=self.status, wraplength=520, justify="left"
                  ).grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 0))

        ttk.Label(frame, text="Output preview:").grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.preview = tk.Text(frame, height=8, width=70, wrap="char",
                               state="disabled")
        self.preview.grid(row=9, column=0, columnspan=3, sticky="nsew")

    # ------------------------------------------------------------------
    # Input / output name handling
    # ------------------------------------------------------------------
    def _refresh_output_suggestion(self):
        if self._auto_output:
            self._last_suggestion = file_utils.suggest_output_path(
                self.input_path.get().strip(), self.mode.get(),
                self.output_format.get())
            self.output_path.set(self._last_suggestion)

    def _on_output_typed(self, _event):
        self._auto_output = (self.output_path.get() == self._last_suggestion)

    def _on_mode_changed(self):
        self._auto_output = True
        self._refresh_output_suggestion()
        compressing = self.mode.get() == COMPRESS
        state = "normal" if compressing else "disabled"
        self.tags_radio.configure(state=state)
        self.binary_radio.configure(state=state)
        self.verify_check.configure(state=state)
        self._reset_result("Choose an input file to begin." if compressing else
                           "Choose a compressed file. Its format is detected automatically.")

    def _on_format_changed(self):
        self._auto_output = True
        self._refresh_output_suggestion()
        self._reset_result("Choose an input file to begin.")

    def _reset_result(self, message):
        self.status.set(message)
        self.open_button.configure(state="disabled")
        self._set_preview("")

    def _browse_input(self):
        if self.mode.get() == DECOMPRESS:
            file_types = [("Compressed files", "*.lz77 *.txt"), ("All files", "*.*")]
        else:
            file_types = [("Text files", "*.txt"), ("All files", "*.*")]
        path = filedialog.askopenfilename(title="Choose the input file",
                                          filetypes=file_types)
        if path:
            self.input_path.set(os.path.normpath(path))

    def _browse_output(self):
        current = self.output_path.get().strip()
        options = {"title": "Choose where to save the output file",
                   "confirmoverwrite": False}      # _start() asks about overwriting
        if current:
            options["initialdir"] = os.path.dirname(current) or os.getcwd()
            options["initialfile"] = os.path.basename(current)
        path = filedialog.asksaveasfilename(**options)
        if path:
            self._auto_output = False
            self.output_path.set(os.path.normpath(path))

    def _open_output(self):
        try:
            file_utils.open_with_default_app(self.output_path.get().strip())
        except LZ77Error as error:
            messagebox.showerror("Cannot open output", str(error))

    def _set_preview(self, text):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _show_preview(self, target, binary_output):
        if binary_output:
            self._set_preview("(binary file - not shown as text)")
            return
        try:
            with open(target, "rb") as handle:
                raw = handle.read(PREVIEW_CHARS * 4)
            text = raw.decode("utf-8", errors="replace")[:PREVIEW_CHARS]
            if os.path.getsize(target) > len(raw) or len(text) == PREVIEW_CHARS:
                text += "\n..."
            self._set_preview(text)
        except OSError:
            self._set_preview("")

    # ------------------------------------------------------------------
    # Running the job
    # ------------------------------------------------------------------
    def _start(self):
        source = self.input_path.get().strip()
        target = self.output_path.get().strip()

        if not source:
            messagebox.showerror("No input file", "Please choose an input file first.")
            return
        if not os.path.isfile(source):
            messagebox.showerror("File not found", "This file does not exist:\n" + source)
            return
        if not target:
            messagebox.showerror("No output file", "Please choose where to save the output.")
            return
        if file_utils.same_file(source, target):
            messagebox.showerror("Same file", "The output file must be different from the input file.")
            return
        if os.path.exists(target) and not messagebox.askyesno(
                "Overwrite?", "This file already exists:\n%s\n\nOverwrite it?" % target):
            return

        self._set_busy(True)
        worker = threading.Thread(
            target=self._worker,
            args=(self.mode.get(), source, target,
                  self.verify.get(), self.output_format.get()),
            daemon=True)
        worker.start()
        self.root.after(POLL_INTERVAL_MS, self._poll_worker)

    def _worker(self, mode, source, target, verify, output_format):
        """Runs in a background thread so the window never freezes."""
        try:
            if mode == COMPRESS:
                result = compress_file(source, target, output_format, verify=verify)
                message = describe_compress(result, source, target)
                binary_output = output_format == FORMAT_BINARY
            else:
                result = decompress_file(source, target)
                message = describe_decompress(result, source, target)
                binary_output = False
            self._results.put(("ok", message, target, binary_output))

        except LZ77Error as error:
            prefix = "Compression failed: " if mode == COMPRESS else "Decompression failed: "
            text = str(error)
            if text.startswith(("Lossless", "Invalid", "Unable", "File not found")):
                prefix = ""
            self._results.put(("error", prefix + text, target, False))
        except Exception as error:     # never crash the window
            self._results.put(("error", "Unexpected error: %s" % error, target, False))

    def _poll_worker(self):
        try:
            kind, message, target, binary_output = self._results.get_nowait()
        except queue.Empty:
            self.root.after(POLL_INTERVAL_MS, self._poll_worker)
            return

        self._set_busy(False)
        if kind == "ok":
            self.status.set(message)
            self.open_button.configure(state="normal")
            self._show_preview(target, binary_output)
        else:
            self.status.set("Failed: " + message)
            self.open_button.configure(state="disabled")
            messagebox.showerror("Something went wrong", message)

    def _set_busy(self, busy):
        if busy:
            self.start_button.configure(state="disabled")
            self.progress.start(12)
            self.status.set("Working...")
        else:
            self.start_button.configure(state="normal")
            self.progress.stop()


def run():
    root = tk.Tk()
    LZ77App(root)
    root.mainloop()
