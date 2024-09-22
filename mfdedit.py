#!/usr/bin/env python3

import codecs
import curses
import argparse
import sys
from typing import List
from bitstring import BitArray


class Data:
    def __init__(self):
        self.UID_LEN = 8
        self.BCC_LEN = 2
        self.SAK_LEN = 2
        self.ATQA_LEN = 4
        self.edited = False
        return

    def read_dump(self, file_name: str):
        self.file_name = file_name
        self.blocks = []
        with open(self.file_name, "rb") as f:
            file_data = f.read()

        data_size = len(file_data)

        if data_size not in {320, 1024, 4096}:
            sys.exit("Wrong file size: %d bytes.\nOnly 320, 1024 or 4096 bytes allowed." % len(file_data))

        sector_number = 0
        start = 0
        end = 64

        while True:
            sector = file_data[start:end]
            sector = codecs.encode(sector, 'hex')
            if not isinstance(sector, str):
                sector = str(sector, 'ascii')
            sectors = [sector[x:x + 32] for x in range(0, len(sector), 32)]

            self.blocks.append(sectors)

            sector_number += 1
            if sector_number < 32:
                start += 64
                end += 64
            elif sector_number == 32:
                start += 64
                end += 256
            else:
                start += 256
                end += 256

            if start == data_size:
                break
        f.closed
        self.__fill_acc()
        self.__check_data()

    def __fill_acc(self):
        self.acc = []
        for s in range(0, len(self.blocks)):
            acc_bytes = BitArray('0x' + self.blocks[s][len(self.blocks[s]) - 1][12:20])
            acc_bits = []
            if len(self.blocks[s]) == 4:
                for i in range(0, 4):
                    acc_bits.append(self.__decode_acc_bytes_to_bits_per_block(acc_bytes, i))
            elif len(self.blocks[s]) == 16:
                for i in range(0, 4):
                    for j in range(0, 5):
                        if (i * 5 + j >= len(self.blocks[s])):
                            break
                        acc_bits.append(self.__decode_acc_bytes_to_bits_per_block(acc_bytes, i))
            self.acc.append(acc_bits)
        self.__fill_acc_err()

    def __fill_acc_err(self):
        self.acc_err = []
        for s in range(0, len(self.blocks)):
            acc_bits_err = []
            for b in range(0, len(self.blocks[s])):
                acc_bits_err.append("OK" if self.acc[s][b].isdigit() else "ERR")
            self.acc_err.append(acc_bits_err)

    @staticmethod
    def __decode_acc_bytes_to_bits_per_block(acc_bytes: BitArray, block_index: int) -> str:
        bits = BitArray([0])
        inverted = BitArray([0])

        bits = BitArray([acc_bytes[11 - block_index], acc_bytes[23 - block_index], acc_bytes[19 - block_index]])
        inverted = BitArray([acc_bytes[7 - block_index], acc_bytes[3 - block_index], acc_bytes[15 - block_index]])

        inverted.invert()
        if bits.bin == inverted.bin:
            return bits.bin
        else:
            return "ERR"

    def __check_data(self):
        self.data_warn = []
        for s in range(0, len(self.blocks)):
            self.data_warn.append([])
            for b in range(0, len(self.blocks[s]) - 1):
                if self.acc[s][b] in ["000", "001", "110"]:
                    if s == 0 and b == 0:
                        self.data_warn[s].append("OK")
                    else:
                        self.data_warn[s].append(self.__check_block(self.blocks[s][b]))
                else:
                    self.data_warn[s].append("OK")
            self.data_warn[s].append("OK")

    @staticmethod
    def __check_block(block: str) -> str:
        block_bin = BitArray('0x' + block)

        value = BitArray(block_bin[0:32])
        value_inverted = BitArray(block_bin[32:64])
        value_repeat = BitArray(block_bin[64:96])

        addr = BitArray(block_bin[96:104])
        addr_inverted = BitArray(block_bin[104:112])
        addr_repeat = BitArray(block_bin[112:120])
        addr_inverted_repeat = BitArray(block_bin[120:128])

        value_inverted.invert()
        addr_inverted.invert()
        addr_inverted_repeat.invert()

        if value.bin != value_inverted.bin:
            return "WARN"
        if value.bin != value_repeat.bin:
            return "WARN"
        if addr.bin != addr_inverted.bin:
            return "WARN"
        if addr.bin != addr_repeat.bin:
            return "WARN"
        if addr.bin != addr_inverted_repeat.bin:
            return "WARN"
        return "OK"

    def update_acc_bit(self, s: int, b: int, index: int, c: chr):
        acc_list = list(self.acc[s][b])
        acc_list[index] = c
        self.acc[s][b] = "".join(acc_list)
        self.__update_blocks_from_acc(s, b, index)
        self.__fill_acc_err()
        self.__check_data()

    def __update_blocks_from_acc(self, s: int, b: int, index: int):
        if len(self.blocks[s]) == 4:
            self.__update_accbytes_from_accbits(s, b, index)
        elif len(self.blocks[s]) == 16:
            self.__update_accbytes_from_accbits(s, b // 5, index)

    def __update_accbytes_from_accbits(self, s: int, b: int, index: int):
        acc_bytes = BitArray('0x' + self.blocks[s][len(self.blocks[s]) - 1][12:20])

        if index == 0:
            acc_bytes[11 - b] = ord(self.acc[s][b][0]) - ord('0')
            acc_bytes[7 - b] = not ord(self.acc[s][b][0]) - ord('0')
        elif index == 1:
            acc_bytes[23 - b] = ord(self.acc[s][b][1]) - ord('0')
            acc_bytes[3 - b] = not ord(self.acc[s][b][1]) - ord('0')
        elif index == 2:
            acc_bytes[19 - b] = ord(self.acc[s][b][2]) - ord('0')
            acc_bytes[15 - b] = not ord(self.acc[s][b][2]) - ord('0')

        block_list = list(self.blocks[s][len(self.blocks[s]) - 1])

        for i in range(0, 8):
            block_list[i+12] = acc_bytes.hex[i]
        self.blocks[s][len(self.blocks[s]) - 1] = "".join(block_list)

    def update_blocks_hex(self, s: int, b: int, index: int, c: chr):
        block_list = list(self.blocks[s][b])
        block_list[index] = c
        self.blocks[s][b] = "".join(block_list)
        if s == 0 and b == 0 and index in range(0, 8):
            self.__update_bcc()
        self.__fill_acc()
        self.__check_data()
        self.edited = True

    def __update_bcc(self):
        xor_current = self.blocks[0][0][0:2]
        for i in range(2, self.UID_LEN, 2):
            xor_current = self.__xor_str(xor_current, self.blocks[0][0][i:i+2])
        block_list = list(self.blocks[0][0])
        block_list[8] = xor_current[0]
        block_list[9] = xor_current[1]
        self.blocks[0][0] = "".join(block_list)

    @staticmethod
    def __xor_str(a: str, b: str) -> str:
        return "".join(["%x" % (int(x,16) ^ int(y,16)) for (x, y) in zip(a, b)])

    def save_dump(self):
        with open(self.file_name, "wb") as f:
            for s in range(0, len(self.blocks)):
                for b in range(0, len(self.blocks[s])):
                    f.write(codecs.decode(self.blocks[s][b].encode('ascii'), 'hex'))
        f.closed
        self.edited = False
        return


class View:
    def __init__(self, data: Data):
        self.COLS = 125
        self.BLOCKS_BEGIN = 19
        self.BLOCKS_END = 51
        self.KEY_A_BEGIN = self.BLOCKS_BEGIN
        self.ACC_BYTES_BEGIN = 31
        self.KEY_B_BEGIN = 39
        self.KEY_A_END = self.ACC_BYTES_BEGIN
        self.ACC_BYTES_END = self.KEY_B_BEGIN
        self.KEY_B_END = self.BLOCKS_END
        self.ACC_BITS_BEGIN = 56
        self.ACC_BITS_END = 59
        self.sectors_fill(data)

    def sectors_fill(self, data: Data):
        self.view = []
        self.view_to_blocks = []
        block_number = 0
        for s in range(0, len(data.blocks)):
            blocks_count = len(data.blocks[s])
            for b in range(0, len(data.blocks[s])):
                if s == 0 and b == 0:
                    acc_help_for_block_view = "manufacturer block"
                elif b != blocks_count - 1:
                    acc_help_for_block_view = self.__acc_help_per_block_data(data.acc[s][b])
                else:
                    acc_help_for_block_view = self.__acc_help_per_block_sector_trailer(data.acc[s][b])

                if b == 2:
                    s_view = s
                else:
                    s_view = ''

                self.view.append("|{sector: >5}   |{block: >5}  | {block_data} |   {acc}  | {acc_help: <61}|".format(
                    sector=s_view,
                    block=block_number,
                    block_data=data.blocks[s][b],
                    acc=data.acc[s][b],
                    acc_help=acc_help_for_block_view
                    )
                    )
                self.view_to_blocks.append({'s': s, 'b': b})
                block_number += 1

            if s < (len(data.blocks) - 1):
                self.view.append(self.line_fill())
                self.view_to_blocks.append({'s': -1, 'b': -1})

    @staticmethod
    def __acc_help_per_block_data(acc: str) -> str:
        permissions = {
            '000': " A/B  |  A/B  |  A/B  |  A/B  | all all (transport mode)",
            '001': " A/B  |   -   |   -   |  A/B  | read and d/t/r all",
            '010': " A/B  |   -   |   -   |   -   | read all",
            '011': "   B  |   B   |   -   |   -   | read and write B only",
            '100': " A/B  |   B   |   -   |   -   | read all and write B only",
            '101': "   B  |   -   |   -   |   -   | read only B",
            '110': " A/B  |   B   |   B   |  A/B  | read and d/t/r all, w/i B",
            '111': "  -   |   -   |   -   |   -   | none",
        }
        if acc.isdigit():
            return permissions.get(acc, "unknown")
        else:
            return ""

    @staticmethod
    def __acc_help_per_block_sector_trailer(acc: str) -> str:
        permissions = {
            '000': "- | A | A | - | A | A | read all by A and write B by A",
            '001': "- | A | A | A | A | A | all all by A (transport mode)",
            '010': "- | - | A | - | A | - | read ACC and B by A",
            '011': "- | B |A/B| B | - | B | read ACC by all and write all by B",
            '100': "- | B |A/B| - | - | B | read ACC by all and write keys by B",
            '101': "- | - |A/B| B | - | - | read ACC by all and write ACC by B",
            '110': "- | - |A/B| - | - | - | read ACC by all",
            '111': "- | - |A/B| - | - | - | read ACC by all",
        }
        if acc.isdigit():
            return permissions.get(acc, "unknown")
        else:
            return ""

    def line_fill(self) -> str:
        return ('-' * self.COLS)

    @staticmethod
    def header_fill() -> List[str]:
        return [
            "| Sector | Block |               Data               | Access | Access bits help                                             |",
            "|        |       |                                  |        |   r   |   w   |   i   | d/t/r | operations for data block    |",
            "|        |       |                                  |        | Key A |  ACC  | Key B | operation on part of sector trailer  |",
            "|        |       |                                  |        | r | w | r | w | r | w | operation for part of sector trailer |"
        ]

    def check_raw(self, index: int):
        if index < 160:
            if (index + 1) % 5 == 0:
                return True, False, False
            elif (index + 1) % 5 == 4:
                return False, True, False
            elif index == 0:
                return False, False, True
        else:
            if index % 17 == 6:
                return True, False, False
            elif index % 17 == 5:
                return False, True, False
        return False, False, False


class Bash:
    def __init__(self):
        self.RED = '\033[31m'
        self.GREEN = '\033[32m'
        self.BLUE = '\033[34m'
        self.PURPLE = '\033[35m'
        self.CYAN = '\033[36m'
        self.YELLOW = '\033[33m'
        self.INVERSE = '\033[47;30m'
        self.ERROR = '\033[41;30m'
        self.WARNING = '\033[43;30m'
        self.ENDC = '\033[0m'
        self.colored_view = []

    def print(self, view: View, data: Data):
        self.__colored(view, data)
        print(self.__legend_fill())
        print(view.line_fill())
        for i in range(0, len(view.header_fill())):
            print(view.header_fill()[i])
        print(view.line_fill())
        for i in range(0, len(self.colored_view)):
            print(self.colored_view[i])
        print(view.line_fill())

    def __legend_fill(self):
        return "| Legeng: " + \
                self.INVERSE + "UID" + self.ENDC + ", " + \
                self.YELLOW + "BCC" + self.ENDC + ", " + \
                self.CYAN + "SAK" + self.ENDC + ", " + \
                self.PURPLE + "ATQA" + self.ENDC + ", " + \
                self.RED + "Key A" + self.ENDC + ", " + \
                self.GREEN + "Access Bits" + self.ENDC + ", " + \
                self.BLUE + "Key B" + self.ENDC + ", " + \
                self.WARNING + "Warning" + self.ENDC + ", " + \
                self.ERROR + "Error" + self.ENDC + \
                ' ' * 52 + '|'

    def __colored(self, view: View, data: Data):
        for i in range(0, len(view.view)):
            self.colored_view.append(view.view[i])
            skip, sector_trailer, manufacturer = view.check_raw(i)
            if skip:
                continue
            self.__colored_acc_bits(i,
                data.acc_err[view.view_to_blocks[i]['s']][view.view_to_blocks[i]['b']],
                view.ACC_BITS_BEGIN, view.ACC_BITS_END)

            if sector_trailer:
                self.__colored_sector_trailer(i, view.KEY_A_BEGIN, view.KEY_A_END,
                        view.ACC_BYTES_BEGIN, view.ACC_BYTES_END, view.KEY_B_BEGIN, view.KEY_B_END)
            elif manufacturer:
                self.__colored_manufacturer(i,
                        view.BLOCKS_BEGIN, data.UID_LEN,
                        data.BCC_LEN, data.SAK_LEN, data.ATQA_LEN)
            else:
                self.__colored_data(i,
                        data.data_warn[view.view_to_blocks[i]['s']][view.view_to_blocks[i]['b']],
                        view.BLOCKS_BEGIN, view.BLOCKS_END)

    def __colored_acc_bits(self, index: int, err: str, ACC_BITS_BEGIN: int, ACC_BITS_END: int):
        if err == "OK":
            self.colored_view[index] = self.colored_view[index][:ACC_BITS_BEGIN] + \
                self.GREEN + self.colored_view[index][ACC_BITS_BEGIN:ACC_BITS_END] + \
                self.ENDC + self.colored_view[index][ACC_BITS_END:]
        elif err == "ERR":
            self.colored_view[index] = self.colored_view[index][:ACC_BITS_BEGIN] + \
                self.ERROR + self.colored_view[index][ACC_BITS_BEGIN:ACC_BITS_END] + \
                self.ENDC + self.colored_view[index][ACC_BITS_END:]

    def __colored_sector_trailer(self, index: int, KEY_A_BEGIN: int, KEY_A_END: int, ACC_BYTES_BEGIN: int, ACC_BYTES_END: int,
            KEY_B_BEGIN: int, KEY_B_END: int):
        self.colored_view[index] = self.colored_view[index][:KEY_B_BEGIN] + \
                self.BLUE + self.colored_view[index][KEY_B_BEGIN:KEY_B_END] + \
                self.ENDC + self.colored_view[index][KEY_B_END:]
        self.colored_view[index] = self.colored_view[index][:ACC_BYTES_BEGIN] + \
                self.GREEN + self.colored_view[index][ACC_BYTES_BEGIN:ACC_BYTES_END] + \
                self.ENDC + self.colored_view[index][ACC_BYTES_END:]
        self.colored_view[index] = self.colored_view[index][:KEY_A_BEGIN] + \
                self.RED + self.colored_view[index][KEY_A_BEGIN:KEY_A_END] + \
                self.ENDC + self.colored_view[index][KEY_A_END:]

    def __colored_manufacturer(self, index: int,
            BLOCKS_BEGIN: int, UID_LEN: int, BCC_LEN: int, SAK_LEN: int, ATQA_LEN: int):
        UID_BEGIN = BLOCKS_BEGIN
        UID_END = UID_BEGIN + UID_LEN
        BCC_BEGIN = UID_END
        BCC_END = BCC_BEGIN + BCC_LEN
        SAK_BEGIN = BCC_END
        SAK_END = SAK_BEGIN + SAK_LEN
        ATQA_BEGIN = SAK_END
        ATQA_END = ATQA_BEGIN + ATQA_LEN
        self.colored_view[index] = self.colored_view[index][:ATQA_BEGIN] + \
                self.PURPLE + self.colored_view[index][ATQA_BEGIN:ATQA_END] + \
                self.ENDC + self.colored_view[index][ATQA_END:]
        self.colored_view[index] = self.colored_view[index][:SAK_BEGIN] + \
                self.CYAN + self.colored_view[index][SAK_BEGIN:SAK_END] + \
                self.ENDC + self.colored_view[index][SAK_END:]
        self.colored_view[index] = self.colored_view[index][:BCC_BEGIN] + \
                self.YELLOW + self.colored_view[index][BCC_BEGIN:BCC_END] + \
                self.ENDC + self.colored_view[index][BCC_END:]
        self.colored_view[index] = self.colored_view[index][:UID_BEGIN] + \
                self.INVERSE + self.colored_view[index][UID_BEGIN:UID_END] + \
                self.ENDC + self.colored_view[index][UID_END:]

    def __colored_data(self, index: int, data_warn: str, BLOCKS_BEGIN: int, BLOCKS_END: int):
        if data_warn == "WARN":
            self.colored_view[index] = self.colored_view[index][:BLOCKS_BEGIN] + \
                self.WARNING + self.colored_view[index][BLOCKS_BEGIN:BLOCKS_END] + \
                self.ENDC + self.colored_view[index][BLOCKS_END:]

class TUI:
    def __init__(self, view: View, data: Data):
        self.__init_curses()
        self.__init_coors(view)
        self.__check_terminal()
        self.__init_colors()
        self.__init_objects()
        self.__fill_objects(view, data)

    def __init_curses(self):
        self.stdscr = curses.initscr()
        curses.start_color()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(1)
        self.stdscr.keypad(True)

    def __init_coors(self, view: View):
        self.PAD_MAIN_BEGIN_X, self.PAD_MAIN_BEGIN_Y = 0, 7
        self.PAD_MAIN_SIZE_X, self.PAD_MAIN_SIZE_Y = view.COLS + 1, len(view.view)
        self.PAD_MAIN_END_Y = min(len(view.view) - 1, curses.LINES - 3)
        self.pad_pos_y = 0

        self.CURSOR_POS_MIN_X, self.CURSOR_POS_MIN_Y = view.BLOCKS_BEGIN, self.PAD_MAIN_BEGIN_Y
        self.CURSOR_POS_MAX_X, self.CURSOR_POS_MAX_Y = view.ACC_BITS_END - 1, self.PAD_MAIN_END_Y - self.PAD_MAIN_BEGIN_Y
        self.cursor_pos_x, self.cursor_pos_y = self.CURSOR_POS_MIN_X, 0

        self.MIN_LINES = 11

    def __check_terminal(self):
        if (curses.COLS < self.PAD_MAIN_SIZE_X - 1) or (curses.LINES < self.MIN_LINES):
            curses.endwin()
            sys.exit("Too small terminal (need {}x{} or bigger)".format(self.PAD_MAIN_SIZE_X - 1, self.MIN_LINES))

    def __init_colors(self):
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_RED)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(7, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(8, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(9, curses.COLOR_MAGENTA, curses.COLOR_BLACK)

    def __init_objects(self):
        self.win_header = curses.newwin(1, self.PAD_MAIN_SIZE_X, 0, 0)
        self.win_splitter_header = curses.newwin(1, self.PAD_MAIN_SIZE_X, 1, 0)
        self.pad_second_header = curses.newpad(4, self.PAD_MAIN_SIZE_X)
        self.win_splitter_headerAndMain = curses.newwin(1, self.PAD_MAIN_SIZE_X, 6, 0)
        self.pad_main = curses.newpad(self.PAD_MAIN_SIZE_Y, self.PAD_MAIN_SIZE_X)
        self.win_splitter_footer = curses.newwin(1, self.PAD_MAIN_SIZE_X, curses.LINES - 2, 0)
        self.win_footer = curses.newwin(1, self.PAD_MAIN_SIZE_X, curses.LINES - 1, 0)

    def __fill_objects(self, view: View, data: Data):
        self.__legend_fill()
        self.win_splitter_header.addstr(0, 0, view.line_fill())
        for i in range(0, len(view.header_fill())):
            self.pad_second_header.addstr(i, 0, view.header_fill()[i])
        self.win_splitter_headerAndMain.addstr(0, 0, view.line_fill())
        self.__pad_fill(view, data)
        self.win_splitter_footer.addstr(0, 0, view.line_fill())
        self.win_footer.addstr(0, 0, "| H/J/K/L/Arrows/Home/End/PgUp/PgDown - Move; 0-F - Edit; S - Save; Q - quit" + 48 * ' ' + '|')

    def __pad_fill(self, view: View, data: Data):
        for i in range(0, len(view.view)):
            self.pad_main.addstr(i, 0, view.view[i])
            skip, sector_trailer, manufacturer = view.check_raw(i)
            if skip:
                continue
            self.__colored_acc_bits(view.view[i], i, view.ACC_BITS_BEGIN, view.ACC_BITS_END,
                    data.acc_err[view.view_to_blocks[i]['s']][view.view_to_blocks[i]['b']])

            if sector_trailer:
                self.__colored_sector_trailer(view.view[i], i,
                        view.KEY_A_BEGIN, view.KEY_A_END,
                        view.ACC_BYTES_BEGIN, view.ACC_BYTES_END,
                        view.KEY_B_BEGIN, view.KEY_B_END)
            elif manufacturer:
                self.__colored_manufacturer(view.view[i], i,
                        view.BLOCKS_BEGIN, data.UID_LEN,
                        data.BCC_LEN, data.SAK_LEN, data.ATQA_LEN)
            else:
                self.__colored_data(view.view[i], i, view.BLOCKS_BEGIN, view.BLOCKS_END,
                    data.data_warn[view.view_to_blocks[i]['s']][view.view_to_blocks[i]['b']])

    def __colored_data(self, original: str, i: int, BLOCKS_BEGIN: int, BLOCKS_END: int, warn: str):
        if warn == "WARN":
            self.pad_main.addstr(i, BLOCKS_BEGIN, original[BLOCKS_BEGIN:BLOCKS_END], curses.color_pair(5))

    def __colored_acc_bits(self, original:str , i: int, ACC_BITS_BEGIN: int, ACC_BITS_END: int, err: str):
        if err == "OK":
            self.pad_main.addstr(i, ACC_BITS_BEGIN, original[ACC_BITS_BEGIN:ACC_BITS_END], curses.color_pair(2))
        elif err == "ERR":
            self.pad_main.addstr(i, ACC_BITS_BEGIN, original[ACC_BITS_BEGIN:ACC_BITS_END], curses.color_pair(4))

    def __colored_sector_trailer(self, original: str, i: int,
            KEY_A_BEGIN: int, KEY_A_END: int,
            ACC_BYTES_BEGIN: int, ACC_BYTES_END: int,
            KEY_B_BEGIN: int, KEY_B_END: int):
        self.pad_main.addstr(i, KEY_A_BEGIN, original[KEY_A_BEGIN:KEY_A_END], curses.color_pair(1))
        self.pad_main.addstr(i, ACC_BYTES_BEGIN, original[ACC_BYTES_BEGIN:ACC_BYTES_END], curses.color_pair(2))
        self.pad_main.addstr(i, KEY_B_BEGIN, original[KEY_B_BEGIN:KEY_B_END], curses.color_pair(3))

    def __colored_manufacturer(self, original: str, i: int,
            BLOCKS_BEGIN: int, UID_LEN: int, BCC_LEN: int, SAK_LEN: int, ATQA_LEN: int):
        UID_BEGIN = BLOCKS_BEGIN
        UID_END = UID_BEGIN + UID_LEN
        BCC_BEGIN = UID_END
        BCC_END = BCC_BEGIN + BCC_LEN
        SAK_BEGIN = BCC_END
        SAK_END = SAK_BEGIN + SAK_LEN
        ATQA_BEGIN = SAK_END
        ATQA_END = ATQA_BEGIN + ATQA_LEN
        self.pad_main.addstr(i, UID_BEGIN, original[UID_BEGIN:UID_END], curses.color_pair(6))
        self.pad_main.addstr(i, BCC_BEGIN, original[BCC_BEGIN:BCC_END], curses.color_pair(7))
        self.pad_main.addstr(i, SAK_BEGIN, original[SAK_BEGIN:SAK_END], curses.color_pair(8))
        self.pad_main.addstr(i, ATQA_BEGIN, original[ATQA_BEGIN:ATQA_END], curses.color_pair(9))

    def __legend_fill(self):
        self.win_header.addstr(0, 0, "| Legend: ")
        self.win_header.addstr("UID", curses.color_pair(6))
        self.win_header.addstr(", ")
        self.win_header.addstr("BCC", curses.color_pair(7))
        self.win_header.addstr(", ")
        self.win_header.addstr("SAK", curses.color_pair(8))
        self.win_header.addstr(", ")
        self.win_header.addstr("ATQA", curses.color_pair(9))
        self.win_header.addstr(", ")
        self.win_header.addstr("Key A", curses.color_pair(1))
        self.win_header.addstr(", ")
        self.win_header.addstr("Access Bits", curses.color_pair(2))
        self.win_header.addstr(", ")
        self.win_header.addstr("Key B", curses.color_pair(3))
        self.win_header.addstr(", ")
        self.win_header.addstr("Warning", curses.color_pair(5))
        self.win_header.addstr(", ")
        self.win_header.addstr("Error", curses.color_pair(4))
        self.win_header.addstr(' ' * 52 + '|')

    def loop(self, stdscr, view: View, data: Data):
        self.stdscr = stdscr
        while True:
            self.__refresh()

            if not self.__handle_key(view, data):
                break

    def __refresh(self):
        self.stdscr.move(self.cursor_pos_y + self.CURSOR_POS_MIN_Y, self.cursor_pos_x)

        self.win_header.refresh()
        self.win_splitter_header.refresh()
        # maybe decrease last arg
        self.pad_second_header.refresh(0, 0, 2, 0, 5, self.PAD_MAIN_SIZE_X - 2)
        self.win_splitter_headerAndMain.refresh()
        # maybe decrease last arg
        self.pad_main.refresh(self.pad_pos_y, 0, self.PAD_MAIN_BEGIN_Y, self.PAD_MAIN_BEGIN_X, self.PAD_MAIN_END_Y, self.PAD_MAIN_SIZE_X - 2)
        self.win_splitter_footer.refresh()
        self.win_footer.refresh()
        self.stdscr.refresh()

    def __handle_key(self, view: View, data: Data) -> bool:
        c = self.__lower_char(self.stdscr.getch())
        if c == ord('q'):
            quit = self.__quit(data)
            self.__fill_objects(view, data)
            return not quit
        elif c == curses.KEY_UP or c == ord('k'):
            self.__move_y(-1, view)
        elif c == curses.KEY_DOWN or c == ord('j'):
            self.__move_y(1, view)
        elif c == curses.KEY_LEFT or c == ord('h'):
            self.__move_x(view.BLOCKS_END, view.ACC_BITS_BEGIN, -1)
        elif c == curses.KEY_RIGHT or c == ord('l'):
            self.__move_x(view.BLOCKS_END, view.ACC_BITS_BEGIN, 1)
        elif c == curses.KEY_HOME:
            self.cursor_pos_x = self.CURSOR_POS_MIN_X
        elif c == curses.KEY_END:
            self.cursor_pos_x = self.CURSOR_POS_MAX_X
        elif c == curses.KEY_PPAGE:
            self.__move_y(-self.CURSOR_POS_MAX_Y - 1, view)
        elif c == curses.KEY_NPAGE:
            self.__move_y(self.CURSOR_POS_MAX_Y + 1, view)
        elif c in range(ord('0'), ord('9') + 1) or c in range(ord('a'), ord('f') + 1):
            if self.__edit_hex(c, view, data):
                self.__move_x(view.BLOCKS_END, view.ACC_BITS_BEGIN, 1)
        elif c == ord('s'):
            self.__save(data)
            self.__fill_objects(view, data)
        return True

    @staticmethod
    def __lower_char(c: int) -> int:
        if 'A' <= chr(c) <= 'Z':
            return chr(c - ord('A') + ord('a'))
        else:
            return c

    def __quit(self, data: Data) -> bool:
        if data.edited:
            return self.__bool_dialog("Are you sure to exit (edit will be lost)?")
        return True

    def __bool_dialog(self, message: str) -> bool:
        self.win_footer.addstr(0, 0, "| ")
        self.win_footer.addstr("{message: <121}".format(message=message + " (Y/n):"), curses.A_BLINK)
        self.win_footer.addstr(" |")
        self.__refresh()
        c = self.__lower_char(self.stdscr.getch())
        while True:
            if c == ord('y'):
                return True
            elif c == ord('n'):
                return False
            c = self.__lower_char(self.stdscr.getch())

    def __move_y(self, add: int, view: View):
        future_abs_pos_y = self.cursor_pos_y + self.pad_pos_y + add
        skip, sector_trailer, manufacturer = view.check_raw(future_abs_pos_y)
        if skip:
            self.__add_pos_y(add + (1 if add > 0 else -1))
            return
        self.__add_pos_y(add)

    def __add_pos_y(self, add: int):
        if self.cursor_pos_y + add < 0:
            while add < 0:
                if self.cursor_pos_y + self.pad_pos_y == 0:
                    break
                self.pad_pos_y -= 1
                add += 1
            if add < 0:
                self.cursor_pos_y, self.pad_pos_y = 0, 0
            return
        elif self.cursor_pos_y + add > self.CURSOR_POS_MAX_Y:
            scrolled = False
            while add > 0:
                if self.CURSOR_POS_MAX_Y + self.pad_pos_y + 1 == self.PAD_MAIN_SIZE_Y:
                    break
                self.pad_pos_y += 1
                add -= 1
                scrolled = True
            if add > 0:
                if not scrolled:
                    self.cursor_pos_y = self.CURSOR_POS_MAX_Y
            return
        self.cursor_pos_y += add

    def __move_x(self, BLOCKS_END: int, ACC_BITS_BEGIN:int, add: int):
        future_abs_pos_x = self.cursor_pos_x + add
        if future_abs_pos_x < self.CURSOR_POS_MIN_X:
            return
        elif future_abs_pos_x > self.CURSOR_POS_MAX_X:
            return
        elif future_abs_pos_x in range(BLOCKS_END, ACC_BITS_BEGIN):
            self.cursor_pos_x += add * 6
            return
        self.cursor_pos_x += add

    def __edit_hex(self, c: int, view: View, data: Data) -> bool:
        if self.cursor_pos_x in range(view.ACC_BITS_BEGIN, view.ACC_BITS_END):
            if c not in range(ord('0'), ord('1') + 1):
                return False
            else:
                # maybe need use list
                data.update_acc_bit(view.view_to_blocks[self.cursor_pos_y + self.pad_pos_y]['s'],
                        view.view_to_blocks[self.cursor_pos_y + self.pad_pos_y]['b'],
                        self.cursor_pos_x - view.ACC_BITS_BEGIN, chr(c))
        elif self.cursor_pos_x in range(view.BLOCKS_BEGIN, view.BLOCKS_END):
            if self.cursor_pos_y + self.pad_pos_y == 0:
                if self.cursor_pos_x in range(view.BLOCKS_BEGIN + 8, view.BLOCKS_BEGIN + 10):
                    return False
            data.update_blocks_hex(view.view_to_blocks[self.cursor_pos_y + self.pad_pos_y]['s'],
                    view.view_to_blocks[self.cursor_pos_y + self.pad_pos_y]['b'],
                    self.cursor_pos_x - view.BLOCKS_BEGIN, chr(c))

        view.sectors_fill(data)
        self.__pad_fill(view, data)

        return True

    def __save(self, data: Data):
        if self.__bool_dialog("Are you sure to save dump?"):
            data.save_dump()


def main():
    VERBOSE = False
    data = Data()

    parser = argparse.ArgumentParser(description="MFDedit - editor and viewer for Mifare cards")
    parser.add_argument("--view", '-v', action='store_true', help="print content of dump without TUI interface")
    parser.add_argument("file_name", metavar="filename", type=str, help="filename for Mifare card dump")
    args = parser.parse_args()

    data.read_dump(args.file_name)
    VERBOSE = args.view

    view = View(data)

    if VERBOSE:
        bash = Bash()
        bash.print(view, data)
    else:
        tui = TUI(view, data)
        curses.wrapper(tui.loop, view, data)


if __name__ == "__main__":
    main()
