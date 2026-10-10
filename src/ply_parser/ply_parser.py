#!/usr/bin/env python3
# Krishna Bhattarai
# Nov 23
"""
PLY (Polygon File Format) parser for ascii, binary_little_endian and binary_big_endian files.

The header drives parsing, so any vertex layout (extra properties, any order) and any extra
elements are handled. Faces are returned as polygons with any number of vertices.
Raises ValueError with a readable message on malformed input.
"""
__all__ = ['PLYObject', 'get_file_data', 'parse_ply', 'parse_ply_file', 'parse_ply_file_data']

import math
import re
import struct

# name -> (struct format character, is integer)
TYPES = {}
for _names, _fmt, _integer in [
    (('char', 'int8'), 'b', True),
    (('uchar', 'uint8'), 'B', True),
    (('short', 'int16'), 'h', True),
    (('ushort', 'uint16'), 'H', True),
    (('int', 'int32'), 'i', True),
    (('uint', 'uint32'), 'I', True),
    (('float', 'float32'), 'f', False),
    (('double', 'float64'), 'd', False),
]:
    for _n in _names:
        TYPES[_n] = (_fmt, _integer)

FORMATS = ('ascii', 'binary_little_endian', 'binary_big_endian')
NORMAL_NAMES = (('nx', 'ny', 'nz'), ('normal_x', 'normal_y', 'normal_z'))
COLOR_NAMES = (('red', 'green', 'blue'), ('r', 'g', 'b'), ('diffuse_red', 'diffuse_green', 'diffuse_blue'))
FACE_LIST_NAMES = ('vertex_indices', 'vertex_index')

END_HEADER = re.compile(r'(?:^|(?<=[\r\n]))[ \t]*end_header[ \t]*(?:\r\n|\r|\n|$)')


class PLYObject:
    def __init__(self, vertices, faces, colors, name=None, normals=None):
        self.name = name
        self.vertices = vertices
        self.faces = faces
        self.colors = colors
        self.normals = normals if normals is not None else []


class _Property:
    def __init__(self, name, type_name=None, count_type=None, item_type=None):
        self.name = name
        self.list = count_type is not None
        self.type = TYPES[type_name] if type_name else None
        self.count_type = TYPES[count_type] if count_type else None
        self.item_type = TYPES[item_type] if item_type else None


class _Element:
    def __init__(self, name, count):
        self.name = name
        self.count = count
        self.props = []


def get_file_data(file_name):
    with open(file_name, 'r') as file:
        data = file.readlines()
    return data


def _parse_header(header_text):
    lines = [l.strip() for l in re.split(r'\r\n|\r|\n', header_text) if l.strip()]
    if not lines or lines[0].split()[0] != 'ply':
        raise ValueError('PLY: file does not start with "ply"')
    fmt, el, elements = None, None, []

    for line in lines[1:]:
        tok = line.split()
        if tok[0] == 'format':
            fmt = tok[1] if len(tok) > 1 else ''
            if fmt not in FORMATS:
                raise ValueError('PLY: unsupported format "%s"' % fmt)
        elif tok[0] == 'element':
            if len(tok) < 3 or not tok[2].isdigit():
                raise ValueError('PLY: bad element line "%s"' % line)
            el = _Element(tok[1], int(tok[2]))
            elements.append(el)
        elif tok[0] == 'property':
            if el is None:
                raise ValueError('PLY: property before any element: "%s"' % line)
            is_list = len(tok) > 1 and tok[1] == 'list'
            type_names = tok[2:4] if is_list else tok[1:2]
            name_index = 4 if is_list else 2
            if len(tok) <= name_index or len(type_names) != (2 if is_list else 1):
                raise ValueError('PLY: bad property line "%s"' % line)
            for t in type_names:
                if t not in TYPES:
                    raise ValueError('PLY: unknown type "%s"' % t)
            if is_list:
                if not TYPES[type_names[0]][1]:
                    raise ValueError('PLY: list count type must be integer in "%s"' % line)
                el.props.append(_Property(tok[name_index], count_type=type_names[0], item_type=type_names[1]))
            else:
                el.props.append(_Property(tok[name_index], type_name=type_names[0]))
        # comments, obj_info and unknown keywords are ignored
    if fmt is None:
        raise ValueError('PLY: missing "format" line')

    vertex_el = next((e for e in elements if e.name == 'vertex'), None)
    if vertex_el is None:
        raise ValueError('PLY: no "vertex" element')
    if vertex_el.count > 0:
        for c in ('x', 'y', 'z'):
            p = next((q for q in vertex_el.props if q.name == c), None)
            if p is None:
                raise ValueError('PLY: vertex element has no "%s" property' % c)
            if p.list:
                raise ValueError('PLY: vertex property "%s" must not be a list' % c)

    vnames = {p.name for p in vertex_el.props if not p.list}
    triple = lambda sets: next((s for s in sets if all(n in vnames for n in s)), None)
    face_el = next((e for e in elements if e.name == 'face'), None)
    face_list = None
    if face_el is not None:
        face_list = next((p for p in face_el.props if p.list and p.name in FACE_LIST_NAMES), None)
        if face_el.count > 0 and face_list is None:
            raise ValueError('PLY: face element has no "vertex_indices" list property')

    return {
        'format': fmt, 'elements': elements, 'vertex_el': vertex_el, 'face_list': face_list,
        'normal_names': triple(NORMAL_NAMES), 'color_names': triple(COLOR_NAMES),
    }


class _AsciiReader:
    """Whitespace-separated tokens (any line endings)."""

    def __init__(self, body):
        self.toks = body.split()
        self.i = 0

    def num(self, type_):
        if self.i >= len(self.toks):
            raise ValueError('unexpected end of file')
        s = self.toks[self.i]
        self.i += 1
        try:
            v = float(s)
        except ValueError:
            raise ValueError('invalid number "%s"' % s[:40]) from None
        return int(v) if type_[1] and v.is_integer() else v

    def skip(self, type_, count):
        self.i += count
        if self.i > len(self.toks):
            raise ValueError('unexpected end of file')

    def finish(self):
        if self.i < len(self.toks):
            raise ValueError('PLY: extra data after the last element (element counts in the header may be wrong)')


class _BinaryReader:
    def __init__(self, data, offset, little_endian):
        self.data = data
        self.off = offset
        self.endian = '<' if little_endian else '>'
        self.structs = {}

    def _struct(self, fmt):
        s = self.structs.get(fmt)
        if s is None:
            s = self.structs[fmt] = struct.Struct(self.endian + fmt)
        return s

    def num(self, type_):
        s = self._struct(type_[0])
        if self.off + s.size > len(self.data):
            raise ValueError('unexpected end of file')
        v = s.unpack_from(self.data, self.off)[0]
        self.off += s.size
        return v

    def skip(self, type_, count):
        self.off += count * self._struct(type_[0]).size
        if self.off > len(self.data):
            raise ValueError('unexpected end of file')

    def rows(self, fmt, count):
        """Unpack `count` fixed-size records at once (elements without list properties)."""
        s = self._struct(fmt)
        end = self.off + s.size * count
        if end > len(self.data):
            raise ValueError('unexpected end of file')
        rows = s.iter_unpack(self.data[self.off:end]) if s.size else iter([()] * count)
        self.off = end
        return rows

    def finish(self):
        pass


def _read_body(h, r):
    vertex_el = h['vertex_el']
    n = vertex_el.count
    vertices, normals, colors, faces = [], [], [], []
    # Destination (list, component) for each vertex property, or None to discard it.
    slots = []
    for p in vertex_el.props:
        slot = None
        if not p.list:
            for arr, names in ((vertices, ('x', 'y', 'z')), (normals, h['normal_names']), (colors, h['color_names'])):
                if names and p.name in names:
                    slot = (arr, names.index(p.name))
                    break
        slots.append(slot)

    el, e = None, 0
    try:
        for el in h['elements']:
            is_vertex = el is vertex_el
            props = el.props
            if is_vertex:
                vertices.extend([0.0, 0.0, 0.0] for _ in range(n))
                if h['normal_names']:
                    normals.extend([0.0, 0.0, 0.0] for _ in range(n))
                if h['color_names']:
                    colors.extend([0.0, 0.0, 0.0] for _ in range(n))

            if isinstance(r, _BinaryReader) and not any(p.list for p in props):
                rows = r.rows(''.join(p.type[0] for p in props), el.count)
                if is_vertex:
                    targets = [(k, s[0], s[1]) for k, s in enumerate(slots) if s]
                    for e, row in enumerate(rows):
                        for k, arr, c in targets:
                            arr[e][c] = float(row[k])
                e = el.count
                continue

            for e in range(el.count):
                for k, p in enumerate(props):
                    if not p.list:
                        v = r.num(p.type)
                        s = is_vertex and slots[k]
                        if s:
                            s[0][e][s[1]] = float(v)
                        continue
                    count = r.num(p.count_type)
                    if not isinstance(count, int) or count < 0:
                        raise ValueError('invalid list length %s' % count)
                    if p is not h['face_list']:
                        r.skip(p.item_type, count)
                        continue
                    face = [r.num(p.item_type) for _ in range(count)]
                    for v in face:
                        if not isinstance(v, int) or not 0 <= v < n:
                            raise ValueError('vertex index %s out of range (only %d vertices)' % (v, n))
                    faces.append(face)
    except ValueError as err:
        raise ValueError('PLY: %s in %s %d' % (err, el.name, e)) from None
    r.finish()

    for i, v in enumerate(vertices):
        if not all(math.isfinite(c) for c in v):
            raise ValueError('PLY: vertex %d has a non-finite coordinate' % i)

    return vertices, faces, colors, normals


def parse_ply(data, name=None):
    """Parse PLY data (str for ascii files, or bytes for any format) into a PLYObject."""
    if isinstance(data, (bytes, bytearray, memoryview)):
        raw = bytes(data)
        text = raw.decode('latin-1')  # one char per byte, so string offsets == byte offsets
    elif isinstance(data, str):
        raw, text = None, data
    else:
        raise ValueError('PLY: input must be str or bytes')

    end = END_HEADER.search(text)
    if not end:
        raise ValueError('PLY: missing "end_header" (not a PLY file?)')
    h = _parse_header(text[:end.start()])

    if h['format'] == 'ascii':
        reader = _AsciiReader(text[end.end():])
    elif raw is not None:
        reader = _BinaryReader(raw, end.end(), h['format'] == 'binary_little_endian')
    else:
        raise ValueError('PLY: %s files must be passed as bytes, not str' % h['format'])

    vertices, faces, colors, normals = _read_body(h, reader)
    return PLYObject(vertices, faces, colors, name, normals)


def parse_ply_file_data(lines):
    """Parse PLY data given as a list of lines, a str or bytes. Returns [vertices, faces, colors]."""
    if isinstance(lines, (list, tuple)):
        lines = '\n'.join(line.rstrip('\r\n') for line in lines)
    obj = parse_ply(lines)
    return [obj.vertices, obj.faces, obj.colors]


def parse_ply_file(file_name):
    with open(file_name, 'rb') as file:
        data = file.read()
    return parse_ply(data, file_name.strip())
