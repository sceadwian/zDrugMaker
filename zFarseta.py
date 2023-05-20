mapping = {
    'a': 'b',
    'b': 'q',
    'c': 'w',
    'd': 'e',
    'e': 'u',
    'f': 'l',
    'g': 'g',
    'h': 'n',
    'i': 'c',
    'j': 'z',
    'k': 'x',
    'l': 'r',
    'm': 't',
    'n': 'y',
    'o': 'i',
    'p': 'o',
    'q': 'p',
    'r': 'a',
    's': 's',
    't': 'd',
    'u': 'f',
    'v': 'h',
    'w': 'j',
    'x': 'k',
    'y': 'm',
    'z': 'v',
}


def encrypt_text(text):
    encrypted_text = ''
    for char in text:
        if char.lower() in mapping:
            encrypted_text += mapping[char.lower()]
        else:
            encrypted_text += char

    return encrypted_text


def decrypt_text(encrypted_text):
    reverse_mapping = {v: k for k, v in mapping.items()}

    decrypted_text = ''
    for char in encrypted_text:
        if char.lower() in reverse_mapping:
            decrypted_text += reverse_mapping[char.lower()]
        else:
            decrypted_text += char

    return decrypted_text


def main():
    # Get the input file name from the user
    file_name = input("Enter the name of the input file: ")

    # Prompt the user to choose encryption or decryption
    operation = input("Choose operation:\n1. Encrypt\n2. Decrypt\n")

    # Read the input file
    file_path = file_name.strip()
    with open(file_path, 'r') as file:
        text = file.read()

    # Perform encryption or decryption based on user's choice
    if operation == "1":
        processed_text = encrypt_text(text)
        output_file_path = file_name.strip().split('.')[0] + "_encrypted.txt"
    elif operation == "2":
        processed_text = decrypt_text(text)
        output_file_path = file_name.strip().split('.')[0] + "_decrypted.txt"
    else:
        print("Invalid operation choice. Exiting...")
        return

    # Write the processed text to an output file
    with open(output_file_path, 'w') as file:
        file.write(processed_text)

    print(f"Operation completed. Processed text written to {output_file_path}")


if __name__ == '__main__':
    main()
