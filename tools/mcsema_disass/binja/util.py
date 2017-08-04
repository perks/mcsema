import binaryninja as binja
from binaryninja.enums import (
    Endianness, SegmentFlag
)
import logging
import magic
import re
import struct

ENDIAN_TO_STRUCT = {
    Endianness.LittleEndian: '<',
    Endianness.BigEndian: '>'
}


def read_dword(bv, addr):
    # type: (binja.BinaryView, int) -> int
    data = bv.read(addr, 4)
    fmt = '{}L'.format(ENDIAN_TO_STRUCT[bv.endianness])
    return struct.unpack(fmt, data)[0]


def read_qword(bv, addr):
    # type: (binja.BinaryView, int) -> int
    data = bv.read(addr, 8)
    fmt = '{}Q'.format(ENDIAN_TO_STRUCT[bv.endianness])
    return struct.unpack(fmt, data)[0]


def load_binary(path):
    magic_type = magic.from_file(path)
    if 'ELF' in magic_type:
        bv_type = binja.BinaryViewType['ELF']
    elif 'PE32' in magic_type:
        bv_type = binja.BinaryViewType['PE']
    elif 'Mach-O' in magic_type:
        bv_type = binja.BinaryViewType['Mach-O']
    else:
        bv_type = binja.BinaryViewType['Raw']

        # Can't do anything with Raw type
        logging.fatal('Unknown binary type: "{}", exiting'.format(magic_type))
        exit(1)

    logging.debug('Loading binary in binja...')
    bv = bv_type.open(path)
    bv.update_analysis_and_wait()

    # NOTE: at the moment binja will not load a binary
    # that doesn't have an entry point
    if len(bv) == 0:
        logging.error('Binary could not be loaded in binja, is it linked?')
        exit(1)

    return bv


def find_symbol_name(bv, addr):
    """Attempt to find a symbol for a given address

    Args:
        bv (binja.BinaryView)
        addr (int): Address the symbol should point to

    Returns:
        (str): Symbol name if found, empty string otherwise

    """
    sym = bv.get_symbol_at(addr)
    if sym is not None:
        return sym.name
    return ''


def is_code(bv, addr):
    """Returns `True` if the given address lies in an executable segment"""
    return (bv.get_segment_at(addr).flags & SegmentFlag.SegmentExecutable) != 0


def is_readable(bv, addr):
    """Returns `True` if the given address lies in a readable segment"""
    return (bv.get_segment_at(addr).flags & SegmentFlag.SegmentReadable) != 0


def is_writeable(bv, addr):
    """Returns `True` if the given address lies in a writable segment"""
    return (bv.get_segment_at(addr).flags & SegmentFlag.SegmentWritable) != 0


def is_ELF(bv):
    return bv.view_type == 'ELF'


def is_PE(bv):
    return bv.view_type == 'PE'


def clamp(val, vmin, vmax):
    return min(vmax, max(vmin, val))


# Caching results of is_section_external
_EXT_SECTIONS = set()
_INT_SECTIONS = set()


def is_section_external(bv, sect):
    """Returns `True` if the given section contains only external references

    Args:
        bv (binja.BinaryView)
        sect (binja.binaryview.Section)
    """
    if sect.start in _EXT_SECTIONS:
        return True

    if sect.start in _INT_SECTIONS:
        return False

    if is_ELF(bv):
        if re.search(r'\.(got|plt)', sect.name):
            _EXT_SECTIONS.add(sect.start)
            return True

    if is_PE(bv):
        if '.idata' in sect.name:
            _EXT_SECTIONS.add(sect.start)
            return True

    _INT_SECTIONS.add(sect.start)
    return False
