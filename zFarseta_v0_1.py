#v0.1 is the safer option that does not convert nubmers
# this version may be better to use with really important documents
# to prevent potential loss
# "potential" bug noted when copying just encrypted text into a text file it produced a broken version of the text.

mapping = {
    'a': 'b',
    'b': 'q',
    'c': 'w',
    'd': 'e',
    'e': 'o',
    'f': 'l',
    'g': 'g',
    'h': 'n',
    'i': 'c',
    'j': 'r',
    'k': 'x',
    'l': 'z',
    'm': 't',
    'n': 'y',
    'o': 'a',
    'p': 'u',
    'q': 'p',
    'r': 'i',
    's': 'd',
    't': 's',
    'u': 'f',
    'v': 'h',
    'w': 'j',
    'x': 'k',
    'y': 'm',
    'z': 'v',
    '0': '!',
    '!': '0',
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
#maybe add to the code so that numbers are converted to # and ad the end of the file there is a -- followed by every single number in the document in the order that they appear
#


