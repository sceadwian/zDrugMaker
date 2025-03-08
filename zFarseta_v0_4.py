import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import time
import datetime
import os

# Mapping (unchanged from Version 0.3, with space added for padding)
mapping = {
    'a': 'b', 'b': 'q', 'c': 'w', 'd': 'e', 'e': 'o', 'f': 'l', 'g': 'g', 'h': 'n',
    'i': 'c', 'j': 'r', 'k': 'x', 'l': 'z', 'm': 't', 'n': 'y', 'o': 'a', 'p': 'u',
    'q': 'p', 'r': 'i', 's': 'd', 't': 's', 'u': 'f', 'v': 'h', 'w': 'j', 'x': 'k',
    'y': 'm', 'z': 'v', '0': '!', '!': '0', ' ': ' '
}

def encrypt_text(text):
    encrypted_text = ''
    block_size = 5  # Fixed block size of 5 characters
    i = 0
    while i < len(text):
        # Take a block of up to 5 characters, pad with spaces if needed
        block = text[i:i + block_size].ljust(block_size, ' ')
        encrypted_block = ''
        # Process each character in the block without reversal
        for char in block:
            if char.lower() in mapping:
                if char.islower():
                    encrypted_block += mapping[char.lower()]
                else:
                    encrypted_block += mapping[char.lower()].upper()
            else:
                encrypted_block += char
        encrypted_text += encrypted_block
        i += block_size
    return encrypted_text

def decrypt_text(encrypted_text):
    reverse_mapping = {v: k for k, v in mapping.items()}
    decrypted_text = ''
    block_size = 5
    i = 0
    while i < len(encrypted_text):
        # Take a block of up to 5 characters
        block = encrypted_text[i:i + block_size]
        decrypted_block = ''
        # Process each character in the block without reversal
        for char in block:
            if char.lower() in reverse_mapping:
                if char.islower():
                    decrypted_block += reverse_mapping[char.lower()]
                else:
                    decrypted_block += reverse_mapping[char.lower()].upper()
            else:
                decrypted_block += char
        decrypted_text += decrypted_block
        i += block_size
    return decrypted_text.rstrip()  # Remove trailing padding spaces

class EncryptionApp:
    def __init__(self, master):
        self.master = master
        master.title("Encryption/Decryption App")
        
        # Double the width of the app interface
        app_width = 100  # Double the original width of 50
        
        self.label_input = tk.Label(master, text="Input Text (Plain or Encrypted):")
        self.label_input.pack()

        self.text_input = scrolledtext.ScrolledText(master, height=10, width=app_width)
        self.text_input.pack()

        self.label_encrypted = tk.Label(master, text="Encrypted Text:")
        self.label_encrypted.pack()

        self.text_encrypted = scrolledtext.ScrolledText(master, height=10, width=app_width)
        self.text_encrypted.pack()

        self.copy_encrypted_button = tk.Button(master, text="Copy Encrypted", command=self.copy_encrypted)
        self.copy_encrypted_button.pack()

        self.label_decrypted = tk.Label(master, text="Decrypted Text:")
        self.label_decrypted.pack()

        self.text_decrypted = scrolledtext.ScrolledText(master, height=10, width=app_width)
        self.text_decrypted.pack()

        self.copy_decrypted_button = tk.Button(master, text="Copy Decrypted", command=self.copy_decrypted)
        self.copy_decrypted_button.pack()

        # New button for exporting to a text file
        self.export_button = tk.Button(master, text="Export to Text File", command=self.export_to_file)
        self.export_button.pack(pady=10)

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
        self.master.update()

    def copy_decrypted(self):
        self.master.clipboard_clear()
        self.master.clipboard_append(self.text_decrypted.get("1.0", tk.END).strip())
        self.master.update()
        
    def export_to_file(self):
        # Get the current date and time for the filename
        now = datetime.datetime.now()
        filename = now.strftime("%Y%m%d_%H%M%S_v4.txt")
        
        # Get the text content
        original_text = self.text_input.get("1.0", tk.END).strip()
        encrypted_text = self.text_encrypted.get("1.0", tk.END).strip()
        decrypted_text = self.text_decrypted.get("1.0", tk.END).strip()
        
        # Create the file content with all three text fields
        file_content = f"Original Text:\n{original_text}\n\nEncrypted Text:\n{encrypted_text}\n\nDecrypted Text:\n{decrypted_text}"
        
        try:
            # Write to the file
            with open(filename, "w") as file:
                file.write(file_content)
            messagebox.showinfo("Export Successful", f"File saved as {filename}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not save file: {str(e)}")

    def close_app(self):
        self.master.quit()

def main():
    root = tk.Tk()
    app = EncryptionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()