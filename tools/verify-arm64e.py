#!/usr/bin/env python3
"""Check native arm64e ABI and reachable authenticated ObjC metadata fixups."""
import struct


def inspect_arm64e(data):
    def u32(offset):
        return struct.unpack_from('<I', data, offset)[0]

    def u64(offset):
        return struct.unpack_from('<Q', data, offset)[0]

    if u32(8) != 0x80000002:
        raise ValueError('Expected native versioned arm64e ABI, not legacy/conversion output')
    segments, sections, fixups = [], {}, None
    cursor = 32
    for _ in range(u32(16)):
        cmd, size = struct.unpack_from('<II', data, cursor)
        if cmd == 0x19:
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from('<4Q', data, cursor + 24)
            segments.append((vmaddr, vmsize, fileoff, filesize))
            for j in range(u32(cursor + 64)):
                name, segment, addr, length, offset = struct.unpack_from(
                    '<16s16sQQI', data, cursor + 72 + j * 80)
                sections[name.rstrip(b'\0').decode()] = (addr, length, offset)
        elif cmd == 0x80000034:
            fixups = u32(cursor + 8)
        cursor += size
    if fixups is None or '__objc_data' not in sections:
        raise ValueError('Missing chained fixups or Objective-C classes')
    image_base = segments[0][0]
    starts = fixups + u32(fixups + 4)
    reachable, formats = set(), set()
    if u32(starts) > len(segments):
        raise ValueError('Invalid fixup segment count')
    for index in range(u32(starts)):
        relative = u32(starts + 4 + index * 4)
        if not relative:
            continue
        info = starts + relative
        _, page_size, pointer_format, segment_offset, _, pages = struct.unpack_from('<IHHQIH', data, info)
        if pointer_format not in (1, 9, 12):
            raise ValueError('Unsupported arm64e chained pointer format')
        formats.add(pointer_format)
        vmaddr, _, fileoff, filesize = segments[index]
        if segment_offset != vmaddr - image_base:
            raise ValueError('Invalid chained segment offset')
        for page in range(pages):
            start = struct.unpack_from('<H', data, info + 22 + page * 2)[0]
            if start == 0xffff:
                continue
            if start & 0x8000:
                raise ValueError('Multiple chain starts per page are unsupported by this verifier')
            pos = fileoff + page * page_size + start
            page_end = min(fileoff + (page + 1) * page_size, fileoff + filesize)
            while True:
                if pos + 8 > page_end or pos in reachable:
                    raise ValueError('Invalid chained pointer bounds or cycle')
                reachable.add(pos)
                step = (u64(pos) >> 51) & 0x7ff
                if not step:
                    break
                pos += step * 8

    def auth(offset, discriminator, allow_bind=False):
        word = u64(offset)
        if offset not in reachable:
            raise ValueError('Authenticated pointer is not reachable from a dyld fixup chain')
        if (word >> 63) != 1 or ((word >> 49) & 3) != 2 or not ((word >> 48) & 1):
            raise ValueError('Missing address-diversified DA authentication')
        if (word >> 32) & 0xffff != discriminator:
            raise ValueError('Wrong Objective-C authentication discriminator')
        if not allow_bind and (word >> 62) & 1:
            raise ValueError('Unexpected external Objective-C metadata pointer')
        return word & 0xffffffff

    def vm_to_file(address, size=1):
        for vmaddr, _, offset, length in segments:
            if vmaddr <= address and address + size <= vmaddr + length:
                return offset + address - vmaddr
        raise ValueError('Objective-C metadata target is outside file-backed segments')

    _, size, offset = sections['__objc_data']
    if not size or size % 40:
        raise ValueError('Unexpected Objective-C class section layout')
    names, method_lists = [], 0
    for pos in range(offset, offset + size, 40):
        auth(pos, 0x6ae1, allow_bind=True)
        if u64(pos + 8):
            auth(pos + 8, 0xb5ab, allow_bind=True)
        ro = vm_to_file(image_base + auth(pos + 32, 0x61f8), 72)
        name_pointer = u64(ro + 24)
        if name_pointer >> 63:
            raise ValueError('Unexpected authenticated class name')
        name_offset = vm_to_file(image_base + (name_pointer & ((1 << 43) - 1)))
        end = data.index(b'\0', name_offset)
        names.append(data[name_offset:end].decode())
        if u64(ro + 32):
            auth(ro + 32, 0xc310)
            method_lists += 1
    return dict(class_and_metaclass_count=len(names), class_names=sorted(set(names)),
                authenticated_class_ro_pointers=len(names),
                authenticated_method_list_pointers=method_lists,
                chained_pointer_formats=sorted(formats), reachable_fixups=len(reachable))
