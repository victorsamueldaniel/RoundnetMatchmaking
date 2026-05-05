# %% création de lettres affichées en #
def char_to_list(my_char):
    if my_char == "A":
        return [" ##### ", "#     #", "#######", "#     #", "#     #"]

    if my_char == "B":
        return ["###### ", "#     #", "###### ", "#     #", "###### "]

    if my_char == "C":
        return [" ######", "#      ", "#      ", "#      ", " ######"]

    if my_char == "D":
        return ["#####  ", "#    # ", "#     #", "#    # ", "#####  "]

    if my_char == "E":
        return ["#######", "#      ", "#######", "#      ", "#######"]

    if my_char == "F":
        return ["#######", "#      ", "#####  ", "#      ", "#      "]

    if my_char == "G":
        return ["#######", "#      ", "#  ####", "#     #", "#######"]

    if my_char == "H":
        return ["#     #", "#     #", "#######", "#     #", "#     #"]

    if my_char == "I":
        return ["#######", "   #   ", "   #   ", "   #   ", "#######"]

    if my_char == "J":
        return [" ######", "      #", "      #", " ##   #", "  #### "]

    if my_char == "K":
        return ["#    ##", "#  ##  ", "###    ", "#  ##  ", "#    ##"]

    if my_char == "L":
        return ["#      ", "#      ", "#      ", "#      ", " ######"]

    if my_char == "M":
        return ["#     #", "##   ##", "#  #  #", "#     #", "#     #"]

    if my_char == "N":
        return ["##    #", "# #   #", "#  #  #", "#   # #", "#    ##"]

    if my_char == "O":
        return ["#######", "#     #", "#     #", "#     #", "#######"]

    if my_char == "P":
        return ["#######", "#     #", "#######", "#      ", "#      "]

    if my_char == "Q":
        return ["#######", "#     #", "#     #", "###### ", "     ##"]

    if my_char == "R":
        return ["###### ", "#     #", "###### ", "#   ## ", "#    ##"]

    if my_char == "S":
        return [" ######", "#      ", " ####  ", "      #", "###### "]

    if my_char == "T":
        return ["#######", "   #   ", "   #   ", "   #   ", "   #   "]

    if my_char == "U":
        return ["#     #", "#     #", "#     #", "#     #", "#######"]

    if my_char == "V":
        return ["#     #", "#     #", "#     #", " #   # ", "   #   "]

    if my_char == "W":
        return ["#     #", "#     #", "#  #  #", "##   ##", "#     #"]

    if my_char == "X":
        return ["#     #", " #   # ", "   #   ", " #   # ", "#     #"]

    if my_char == "Y":
        return ["#     #", "#     #", "  ###  ", "   #   ", "   #   "]

    if my_char == "Z":
        return ["######", "    ##", "  ##  ", "##    ", "######"]

    if my_char == " ":
        return ["    ", "    ", "    ", "    ", "    "]

    if my_char == "!":
        return ["##", "##", "##", "  ", "##"]

    if my_char == ".":
        return ["  ", "  ", "  ", "  ", "##"]
    if my_char == "_":
        return ["     ", "     ", "     ", "     ", "#####"]

    if my_char == "-":
        return ["     ", "     ", "#####", "     ", "     "]
    if my_char == "#":
        return ["  #  #", " #####", " #  # ", "##### ", "#  #  "]
    if my_char == ">":
        return ["#    ", "  #  ", "    #", "  #  ", "#    "]
    if my_char == "<":
        return ["    #", "  #  ", "#    ", "  #  ", "    #"]
    if my_char == "?":
        return ["######", "#    #", "   #  ", "      ", "  #   "]
    if my_char == "0":
        return [" #### ", "#   ##", "#  # #", "# #  #", " #### "]
    if my_char == "1":
        return ["  ##  ", " #  # ", "    # ", "    # ", " ######"]
    if my_char == "2":
        return [" #### ", "#    #", "   ## ", " ##   ", "######"]
    if my_char == "3":
        return ["##### ", "    ##", " #### ", "    ##", "##### "]
    if my_char == "4":
        return ["#   # ", "#   # ", "##### ", "    # ", "    # "]
    if my_char == "5":
        return ["##### ", "#     ", "##### ", "    # ", "##### "]
    if my_char == "6":
        return [" #### ", "#     ", "##### ", "#    #", " #### "]
    if my_char == "7":
        return ["##### ", "    # ", "   #  ", "  #   ", " #    "]
    if my_char == "8":
        return [" #### ", "#    #", " #### ", "#    #", " #### "]
    if my_char == "9":
        return [" #### ", "#    #", " #####", "    # ", " #### "]
    if my_char == "(":
        return ["   ##", "  #  ", " #   ", "  #  ", "   ##"]
    if my_char == ")":
        return ["##   ", "  #  ", "   # ", "  #  ", "##   "]


# %% conversion d'un texte en gros commentaire pour script python
def str_to_ascii(string_to_convert):
    # si le texte est écrit en majuscule, ça rajoute des lignes de hashtag en dessous et en dessus
    import math
    from unidecode import unidecode

    string_to_convert_copy = string_to_convert

    # make all uppercase and remove accents
    string_to_convert_copy = unidecode(string_to_convert_copy.upper())
    list_of_char = []

    big_title = string_to_convert == string_to_convert_copy

    for char in string_to_convert_copy:
        list_of_char.append(char_to_list(char))

    list_of_lines = []

    for n in range(5):
        if len(string_to_convert) != 0:
            temp_line = "# "
        else:
            temp_line = "##"

        for k in range(len(string_to_convert_copy)):
            temp_line += list_of_char[k][n] + " "
        list_of_lines.append(temp_line)
    line_length = max(len(list_of_lines[0]) + 1, 80) - 1

    if line_length > 79:
        print("texte trop long!")

    left_hashtags = int(math.floor((line_length - len(list_of_lines[4])) / 2))
    right_hashtags = int(math.ceil((line_length - len(list_of_lines[4])) / 2))

    str_out = (
        "#" * line_length
        + "#\n#"
        + "#" * left_hashtags
        + " " * (len(list_of_lines[n]) - 1)
        + "#" * right_hashtags
        + "#\n"
    )

    for n in range(5):
        str_out += "#" * left_hashtags + list_of_lines[n] + "#" * right_hashtags + "#\n"

    str_out += (
        "#" * left_hashtags
        + "#"
        + " " * (len(list_of_lines[n]) - 1)
        + "#" * right_hashtags
        + "#\n"
        + "#" * (line_length + 1)
    )

    if big_title == True:
        str_out = ("#" * line_length + "#\n") * 4 + str_out
        str_out = str_out + "\n" + ("#" * line_length + "#\n") * 4

    print(str_out)


# %%
