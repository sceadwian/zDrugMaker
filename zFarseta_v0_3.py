# Encryption/Decryption GUI Application
#
# This script provides a graphical user interface for encrypting and decrypting text using a custom substitution cipher.
#
# The GUI has three main text fields:
#    - Input: Where users can paste plain or encrypted text
#    - Encrypted: Displays the encrypted version of the input
#    - Decrypted: Displays the decrypted version of the input
#
# Key features:
# - Real-time processing: The input is encrypted and decrypted every 5 seconds.
# - Bidirectional operation: Works with both plain text and encrypted text inputs.
# - Case preservation: Maintains the case (upper/lower) of the original text.
# - Non-alphabet character preservation: Characters not in the mapping remain unchanged.
#
# Usage:
# 1. Run the script to open the GUI.
# 2. Paste or type text into the input field.
# 3. The encrypted and decrypted versions will appear in their respective fields after a short delay.
# 4. For encrypted input, the correct decryption will appear in the "Decrypted Text" field.
#
# Note: This script uses a custom encryption method and is not suitable for securing sensitive information.
# It's designed for educational purposes and simple text obfuscation.
#
# Version: 0.3

import tkinter as tk
from tkinter import scrolledtext
import threading
import time

mapping = {
    'a': 'b', 'b': 'q', 'c': 'w', 'd': 'e', 'e': 'o', 'f': 'l', 'g': 'g', 'h': 'n',
    'i': 'c', 'j': 'r', 'k': 'x', 'l': 'z', 'm': 't', 'n': 'y', 'o': 'a', 'p': 'u',
    'q': 'p', 'r': 'i', 's': 'd', 't': 's', 'u': 'f', 'v': 'h', 'w': 'j', 'x': 'k',
    'y': 'm', 'z': 'v', '0': '!', '!': '0',
}

def encrypt_text(text):
    encrypted_text = ''
    i = 0
    while i < len(text):
        block = text[i:i+5]
        reversed_block = block[::-1]
        encrypted_block = ''
        for char in reversed_block:
            if char.lower() in mapping:
                if char.islower():
                    encrypted_block += mapping[char.lower()]
                else:
                    encrypted_block += mapping[char.lower()].upper()
            else:
                encrypted_block += char
        encrypted_text += encrypted_block
        i += 5
    return encrypted_text

def decrypt_text(encrypted_text):
    reverse_mapping = {v: k for k, v in mapping.items()}
    decrypted_text = ''
    i = 0
    while i < len(encrypted_text):
        block = encrypted_text[i:i+5]
        decrypted_block = ''
        for char in block:
            if char.lower() in reverse_mapping:
                if char.islower():
                    decrypted_block += reverse_mapping[char.lower()]
                else:
                    decrypted_block += reverse_mapping[char.lower()].upper()
            else:
                decrypted_block += char
        decrypted_text += decrypted_block[::-1]
        i += 5
    return decrypted_text

class EncryptionApp:
    def __init__(self, master):
        self.master = master
        master.title("Encryption/Decryption App")

        self.label_input = tk.Label(master, text="Input Text (Plain or Encrypted):")
        self.label_input.pack()

        self.text_input = scrolledtext.ScrolledText(master, height=10, width=50)
        self.text_input.pack()

        self.label_encrypted = tk.Label(master, text="Encrypted Text:")
        self.label_encrypted.pack()

        self.text_encrypted = scrolledtext.ScrolledText(master, height=10, width=50)
        self.text_encrypted.pack()

        self.copy_encrypted_button = tk.Button(master, text="Copy Encrypted", command=self.copy_encrypted)
        self.copy_encrypted_button.pack()

        self.label_decrypted = tk.Label(master, text="Decrypted Text:")
        self.label_decrypted.pack()

        self.text_decrypted = scrolledtext.ScrolledText(master, height=10, width=50)
        self.text_decrypted.pack()

        self.copy_decrypted_button = tk.Button(master, text="Copy Decrypted", command=self.copy_decrypted)
        self.copy_decrypted_button.pack()

        self.close_button = tk.Button(master, text="Close", command=self.close_app)
        self.close_button.pack()

        self.update_thread = threading.Thread(target=self.update_texts, daemon=True)
        self.update_thread.start()

    def update_texts(self):
        while True:
            input_text = self.text_input.get("1.0", tk.END).strip()
            
            if not input_text:
                # If input is empty, clear both output fields
                self.text_encrypted.delete("1.0", tk.END)
                self.text_decrypted.delete("1.0", tk.END)
            else:
                # Always attempt both encryption and decryption
                encrypted = encrypt_text(input_text)
                decrypted = decrypt_text(input_text)

                self.text_encrypted.delete("1.0", tk.END)
                self.text_encrypted.insert(tk.END, encrypted)

                self.text_decrypted.delete("1.0", tk.END)
                self.text_decrypted.insert(tk.END, decrypted)

            time.sleep(5)

    def copy_encrypted(self):
        self.master.clipboard_clear()
        self.master.clipboard_append(self.text_encrypted.get("1.0", tk.END).strip())
        self.master.update()  # To make sure the clipboard is updated

    def copy_decrypted(self):
        self.master.clipboard_clear()
        self.master.clipboard_append(self.text_decrypted.get("1.0", tk.END).strip())
        self.master.update()  # To make sure the clipboard is updated

    def close_app(self):
        self.master.quit()

def main():
    root = tk.Tk()
    app = EncryptionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()