import tkinter as tk
from tkinter import scrolledtext

# Extended mapping to handle more characters
mapping = {
    'a': 'b', 'b': 'q', 'c': 'w', 'd': 'e', 'e': 'o', 'f': 'l', 'g': 'g', 'h': 'n',
    'i': 'c', 'j': 'r', 'k': 'x', 'l': 'z', 'm': 't', 'n': 'y', 'o': 'a', 'p': 'u',
    'q': 'p', 'r': 'i', 's': 'd', 't': 's', 'u': 'f', 'v': 'h', 'w': 'j', 'x': 'k',
    'y': 'm', 'z': 'v', '0': '!', '!': '0',
    'A': 'B', 'B': 'Q', 'C': 'W', 'D': 'E', 'E': 'O', 'F': 'L', 'G': 'G', 'H': 'N',
    'I': 'C', 'J': 'R', 'K': 'X', 'L': 'Z', 'M': 'T', 'N': 'Y', 'O': 'A', 'P': 'U',
    'Q': 'P', 'R': 'I', 'S': 'D', 'T': 'S', 'U': 'F', 'V': 'H', 'W': 'J', 'X': 'K',
    'Y': 'M', 'Z': 'V', '1': '@', '@': '1', '2': '#', '#': '2', '3': '$', '$': '3',
    '4': '%', '%': '4', '5': '^', '^': '5', '6': '&', '&': '6', '7': '*', '*': '7',
    '8': '(', '(': '8', '9': ')', ')': '9',
}

def encrypt_text(text):
    try:
        encrypted_text = ''
        for char in text:
            if char.lower() in mapping:
                if char.islower():
                    encrypted_text += mapping[char.lower()]
                else:
                    encrypted_text += mapping[char.lower()].upper()
            else:
                encrypted_text += char
        return encrypted_text
    except Exception as e:
        return f"Encryption Error: {str(e)}"

def decrypt_text(encrypted_text):
    try:
        reverse_mapping = {v: k for k, v in mapping.items()}
        decrypted_text = ''
        for char in encrypted_text:
            if char.lower() in reverse_mapping:
                if char.islower():
                    decrypted_text += reverse_mapping[char.lower()]
                else:
                    decrypted_text += reverse_mapping[char.lower()].upper()
            else:
                decrypted_text += char
        return decrypted_text
    except Exception as e:
        return f"Decryption Error: {str(e)}"

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

        self.clear_button = tk.Button(master, text="Clear", command=self.clear_fields)
        self.clear_button.pack()

        self.close_button = tk.Button(master, text="Close", command=self.close_app)
        self.close_button.pack()

        self.text_input.bind("<<Modified>>", self.on_input_change)

    def on_input_change(self, event):
        if self.text_input.edit_modified():
            input_text = self.text_input.get("1.0", tk.END).strip()
            if not input_text:
                self.text_encrypted.delete("1.0", tk.END)
                self.text_decrypted.delete("1.0", tk.END)
            else:
                encrypted = encrypt_text(input_text)
                decrypted = decrypt_text(input_text)
                self.text_encrypted.delete("1.0", tk.END)
                self.text_encrypted.insert(tk.END, encrypted)
                self.text_decrypted.delete("1.0", tk.END)
                self.text_decrypted.insert(tk.END, decrypted)
            self.text_input.edit_modified(False)

    def copy_encrypted(self):
        self.master.clipboard_clear()
        self.master.clipboard_append(self.text_encrypted.get("1.0", tk.END).strip())
        self.master.update()

    def copy_decrypted(self):
        self.master.clipboard_clear()
        self.master.clipboard_append(self.text_decrypted.get("1.0", tk.END).strip())
        self.master.update()

    def clear_fields(self):
        self.text_input.delete("1.0", tk.END)
        self.text_encrypted.delete("1.0", tk.END)
        self.text_decrypted.delete("1.0", tk.END)

    def close_app(self):
        self.master.quit()

def main():
    root = tk.Tk()
    app = EncryptionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()