import struct 

def compress_lz77(input_path , output_path ,window_size=2048, lookahead_size=32):
    with open(input_path , "r" , encoding='utf-8') as file:
        data = file.read()



    compressed_tags = []
    i = 0
    n = len(data)

    while i < n:
        best_distance = 0
        best_length = 0
        # Define search window start position
        search_start = max(0, i - window_size)

        # Search for the longest match (supports overlapping repetitions)
        for j in range(search_start, i):
            length = 0
            while (i + length < n) and (data[j + length] == data[i + length]) and (length < lookahead_size):
                length += 1

            if length > best_length:
                best_length = length
                best_distance = i - j

        if best_length == 0:
            best_distance = 0

        # Extract next character
        if i + best_length < n:
            next_char = data[i + best_length]
        else:
            next_char = ''

        # Format special characters to keep tags clean and readable in the txt file
        display_char = next_char
        if next_char == '\n':
            display_char = '\\n'
        elif next_char == '\t':
            display_char = '\\t'
        elif next_char == ' ':
            display_char = 'SPACE'

        # Format Tag as a readable string: (Distance, Length, 'Char')
        tag = f"<{best_distance}, {best_length}, '{display_char}'>"
        compressed_tags.append(tag)

        i += best_length + 1

    # Save formatted tags as plain text in .txt file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(" ".join(compressed_tags))

    print(f"Compression successful! Output tags saved to: {output_path}")


def decompress_lz77(input_path, output_path):
    """
    Reads text tags from input_path (.txt file) and decompresses them into output_path.
    """
    #if not os.path.exists(input_path):
     #   print(f"Error: File '{input_path}' does not exist.")
      #  return

    with open(input_path, 'r', encoding='utf-8') as file:
        content = file.read().strip()

    if not content:
        print("File is empty.")
        return

    decompressed_text = []

    # Separate individual tags split by closing parenthesis followed by space
    raw_tags = content.split(") ")

    for tag_str in raw_tags:
        tag_str = tag_str.strip()
        if not tag_str:
            continue

        # Clean parentheses
        if tag_str.endswith(')'):
            tag_str = tag_str[:-1]
        if tag_str.startswith('('):
            tag_str = tag_str[1:]

        # Extract elements: Distance, Length, Next_Char
        parts = tag_str.split(',', 2)
        distance = int(parts[0])
        length = int(parts[1])
        char_part = parts[2].strip()

        # Unquote character
        if char_part.startswith("'") and char_part.endswith("'"):
            char_part = char_part[1:-1]

        # Revert special formatted characters
        if char_part == '\\n':
            next_char = '\n'
        elif char_part == '\\t':
            next_char = '\t'
        elif char_part == 'SPACE':
            next_char = ' '
        else:
            next_char = char_part

        # Reconstruct original text
        if distance > 0:
            start_pos = len(decompressed_text) - distance
            for i in range(length):
                decompressed_text.append(decompressed_text[start_pos + i])

        if next_char != '':
            decompressed_text.append(next_char)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("".join(decompressed_text))

    print(f"Decompression successful! Output saved to: {output_path}")


def main_menu():
    """Interactive User Menu"""
    while True:
        print("\n" + "=" * 35)
        print("      LZ77 Compression Tool        ")
        print("=" * 35)
        print("1. Compress File")
        print("2. Decompress File")
        print("3. Exit")
        print("=" * 35)

        choice = input("Select an option (1-3): ").strip()

        if choice == '1':
            input_file = input("Enter input text filename [default: text.txt]: ").strip() or "text.txt"
            output_file = input("Enter output tags filename [default: compressed_tags.txt]: ").strip() or "compressed_tags.txt"
            compress_lz77(input_file, output_file)

        elif choice == '2':
            input_file = input("Enter compressed tags filename [default: compressed_tags.txt]: ").strip() or "compressed_tags.txt"
            output_file = input("Enter decompressed output filename [default: decompressed.txt]: ").strip() or "decompressed.txt"
            decompress_lz77(input_file, output_file)

        elif choice == '3':
            print("Exiting program. Goodbye!")
            break
        else:
            print("Invalid option. Please enter a number between 1 and 3.")


if __name__ == '__main__':
    main_menu()    

