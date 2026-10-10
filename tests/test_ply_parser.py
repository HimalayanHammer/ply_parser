import os
import struct
import unittest
from ply_parser import *

CUBE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cube.ply')


class TestPLYParsing(unittest.TestCase):
    def assertParseError(self, data, message):
        with self.assertRaises(ValueError) as context:
            parse_ply_file_data(data.splitlines())
        self.assertIn(message, str(context.exception))

    def test_parse_ply_data_with_vertices_and_faces(self):
        data = """ply
    format ascii 1.0
    comment Some comment
    element vertex 3
    property float x
    property float y
    property float z
    element face 1
    property list uchar int vertex_indices
    end_header
    1.0 2.0 3.0
    4.0 5.0 6.0
    7.0 8.0 9.0
    3 0 1 2"""

        result = parse_ply_file_data(data.splitlines())
        vertices, faces, colors = result[0], result[1], result[2]
        self.assertEqual(len(vertices), 3)
        self.assertEqual(len(faces), 1)
        self.assertEqual(len(colors), 0)

    def test_parse_ply_data_with_vertices_colors_and_faces(self):
        data = """ply
    format ascii 1.0
    element vertex 3
    property float x
    property float y
    property float z
    property uchar red
    property uchar green
    property uchar blue
    element face 1
    property list uchar int vertex_indices
    end_header
    1.0 2.0 3.0 255 0 0
    4.0 5.0 6.0 0 255 0
    7.0 8.0 9.0 0 0 255
    3 0 1 2"""

        result = parse_ply_file_data(data.splitlines())
        vertices, faces, colors = result[0], result[1], result[2]
        self.assertEqual(len(vertices), 3)
        self.assertEqual(len(faces), 1)
        self.assertEqual(len(colors), 3)

    def test_distinguish_and_count_lines_for_vertices_and_faces(self):
        data = """ply
format ascii 1.0
element vertex 3
property float x
property float y
property float z
element face 3
property list uchar int vertex_indices
end_header
1.0 2.0 3.0
4.0 5.0 6.0
7.0 8.0 9.0
3 2 1 0
3 2 0 1
3 1 2 0"""

        vertices, faces, colors = parse_ply_file_data(data.splitlines())
        self.assertEqual(vertices, [[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        self.assertEqual(faces, [[2, 1, 0], [2, 0, 1], [1, 2, 0]])
        self.assertEqual(len(colors), 0)

    def test_handle_face_lines_starting_with_4(self):
        data = """ply
    format ascii 1.0
    element vertex 4
    property float x
    property float y
    property float z
    element face 3
    property list uchar int vertex_indices
    end_header
    1.0 2.0 3.0
    4.0 5.0 6.0
    7.0 8.0 9.0
    3.0 4.0 5.0
    4 2 1 0 3
    4 2 0 3 1
    4 1 2 3 0"""

        vertices, faces, colors = parse_ply_file_data(data.splitlines())
        self.assertEqual(vertices, [[1, 2, 3], [4, 5, 6], [7, 8, 9], [3, 4, 5]])
        self.assertEqual(faces, [[2, 1, 0, 3], [2, 0, 3, 1], [1, 2, 3, 0]])
        self.assertEqual(len(colors), 0)

    def test_faces_with_any_number_of_vertices(self):
        data = """ply
format ascii 1.0
element vertex 6
property float x
property float y
property float z
element face 2
property list uchar int vertex_indices
end_header
0 0 0
1 0 0
2 1 0
1 2 0
0 2 0
-1 1 0
6 0 1 2 3 4 5
5 5 4 3 2 1"""

        _, faces, _ = parse_ply_file_data(data.splitlines())
        self.assertEqual(faces, [[0, 1, 2, 3, 4, 5], [5, 4, 3, 2, 1]])

    def test_parse_ply_data_with_no_vertices_or_faces(self):
        data = """ply
format ascii 1.0
element vertex 0
element face 0
end_header"""

        result = parse_ply_file_data(data.splitlines())
        vertices, faces, colors = result[0], result[1], result[2]
        self.assertEqual(len(vertices), 0)
        self.assertEqual(len(faces), 0)
        self.assertEqual(len(colors), 0)

    def test_point_cloud_with_no_face_element(self):
        data = """ply
format ascii 1.0
element vertex 2
property float x
property float y
property float z
end_header
1 2 3
4 5 6"""

        vertices, faces, _ = parse_ply_file_data(data.splitlines())
        self.assertEqual(vertices, [[1, 2, 3], [4, 5, 6]])
        self.assertEqual(faces, [])

    def test_handle_invalid_ply_format(self):
        invalid_format_data = """ply
format binary 1.0
element vertex 3
property float x
property float y
property float z
end_header
1.0 2.0 3.0
4.0 5.0 6.0
7.0 8.0 9.0"""

        with self.assertRaises(ValueError) as context:
            parse_ply_file_data(invalid_format_data.splitlines())
        self.assertEqual(str(context.exception), 'PLY: unsupported format "binary"')

    def test_reject_data_that_is_not_ply(self):
        self.assertParseError('hello world', 'PLY: missing "end_header"')
        self.assertParseError('format ascii 1.0\nend_header\n', 'PLY: file does not start with "ply"')

    def test_handle_incomplete_vertex_data(self):
        incomplete_vertex_data = """ply
    format ascii 1.0
    element vertex 3
    property float x
    property float y
    property float z
    end_header
    1.0 2.0 3.0
    4.0 5.0 6.0"""

        with self.assertRaises(ValueError) as context:
            parse_ply_file_data(incomplete_vertex_data.splitlines())
        self.assertEqual(str(context.exception), 'PLY: unexpected end of file in vertex 2')

    def test_handle_incomplete_face_data(self):
        incomplete_face_data = """ply
format ascii 1.0
element vertex 3
property float x
property float y
property float z
element face 2
property list uchar int vertex_indices
end_header
1.0 2.0 3.0
4.0 5.0 6.0
7.0 8.0 9.0
3 0 1 2"""

        with self.assertRaises(ValueError) as context:
            parse_ply_file_data(incomplete_face_data.splitlines())
        self.assertEqual(str(context.exception), 'PLY: unexpected end of file in face 1')

    def test_reject_extra_data_after_last_element(self):
        self.assertParseError("""ply
format ascii 1.0
element vertex 3
property float x
property float y
property float z
end_header
1.0 2.0 3.0 255 0 0
4.0 5.0 6.0 0 255 0
7.0 8.0 9.0 0 0 255""", 'PLY: extra data after the last element')

    def test_reject_face_indices_out_of_range(self):
        self.assertParseError("""ply
format ascii 1.0
element vertex 3
property float x
property float y
property float z
element face 1
property list uchar int vertex_indices
end_header
1 2 3
4 5 6
7 8 9
3 0 1 3""", 'PLY: vertex index 3 out of range (only 3 vertices) in face 0')

    def test_reject_invalid_numbers(self):
        self.assertParseError("""ply
format ascii 1.0
element vertex 1
property float x
property float y
property float z
end_header
1 abc 3""", 'PLY: invalid number "abc" in vertex 0')

    def test_parse_ply_colors_data_if_described_in_header(self):
        data = """ply
format ascii 1.0
element vertex 3
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
element face 1
property list uchar int vertex_indices
end_header
1.0 2.0 3.0 255 0 0
4.0 5.0 6.0 0 255 0
7.0 8.0 9.0 0 0 255
3 0 1 2"""

        result = parse_ply_file_data(data.splitlines())
        vertices, faces, colors = result[0], result[1], result[2]
        self.assertEqual(len(vertices), 3)
        self.assertEqual(len(faces), 1)
        self.assertEqual(len(colors), 3)
        self.assertEqual(colors, [[255, 0, 0], [0, 255, 0], [0, 0, 255]])

    def test_not_parse_colors_if_color_property_not_described(self):
        data = """ply
format ascii 1.0
element vertex 3
property float x
property float y
property float z
property uchar alpha
property uchar red
property uchar green
element face 1
property list uchar int vertex_indices
end_header
1.0 2.0 3.0 255 0 0
4.0 5.0 6.0 0 255 0
7.0 8.0 9.0 0 0 255
3 0 1 2"""

        vertices, faces, colors = parse_ply_file_data(data.splitlines())
        self.assertEqual(vertices, [[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        self.assertEqual(len(faces), 1)
        self.assertEqual(len(colors), 0)

    def test_parse_ply_data_with_negative_coordinates(self):
        data = """ply
format ascii 1.0
element vertex 3
property float x
property float y
property float z
element face 1
property list uchar int vertex_indices
end_header
-1.0 -2.0 -3.0
-4.0 -5.0 -6.0
-7.0 -8.0 -9.0
3 0 1 2"""

        vertices, faces, colors = parse_ply_file_data(data.splitlines())
        self.assertEqual(vertices, [[-1, -2, -3], [-4, -5, -6], [-7, -8, -9]])
        self.assertEqual(len(faces), 1)
        self.assertEqual(len(colors), 0)

    def test_scientific_notation_and_no_leading_digit(self):
        data = """ply
format ascii 1.0
element vertex 1
property float x
property float y
property float z
end_header
1e-3 .5 -2.5E+2"""

        vertices, _, _ = parse_ply_file_data(data.splitlines())
        self.assertEqual(vertices, [[0.001, 0.5, -250]])

    def test_any_vertex_layout_normals_and_extra_properties_and_elements(self):
        data = """ply
format ascii 1.0
element vertex 3
property float confidence
property float z
property float nx
property float ny
property float nz
property float x
property uchar blue
property float y
property uchar green
property uchar red
property list uchar int extra_list
element face 1
property uchar flags
property list uchar int vertex_indices
property float quality
element edge 1
property int vertex1
property int vertex2
end_header
0.9 3 0 0 1 1 30 2 20 10 2 7 7
0.8 6 0 1 0 4 31 5 21 11 0
0.7 9 1 0 0 7 32 8 22 12 1 5
1 3 0 1 2 0.5
0 1"""

        result = parse_ply(data)
        self.assertEqual(result.vertices, [[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        self.assertEqual(result.normals, [[0, 0, 1], [0, 1, 0], [1, 0, 0]])
        self.assertEqual(result.colors, [[10, 20, 30], [11, 21, 31], [12, 22, 32]])
        self.assertEqual(result.faces, [[0, 1, 2]])

    def test_crlf_and_cr_line_endings(self):
        lines = ['ply', 'format ascii 1.0', 'element vertex 3', 'property float x', 'property float y',
                 'property float z', 'element face 1', 'property list uchar int vertex_indices', 'end_header',
                 '1 2 3', '4 5 6', '7 8 9', '3 0 1 2']
        for eol in ('\r\n', '\r'):
            for data in (eol.join(lines), eol.join(lines).encode()):
                result = parse_ply(data)
                self.assertEqual(result.vertices, [[1, 2, 3], [4, 5, 6], [7, 8, 9]])
                self.assertEqual(result.faces, [[0, 1, 2]])

    def test_binary_formats(self):
        for fmt, endian in (('binary_little_endian', '<'), ('binary_big_endian', '>')):
            for vertex_props, vertex_fmt in (
                ('property float x\nproperty float y\nproperty float z\n'
                 'property uchar red\nproperty uchar green\nproperty uchar blue\n', 'fffBBB'),
                ('property double x\nproperty double y\nproperty double z\n'
                 'property uchar red\nproperty uchar green\nproperty uchar blue\n'
                 'property list uchar int extra\n', 'dddBBBB'),
            ):
                with self.subTest(fmt=fmt, vertex_fmt=vertex_fmt):
                    header = ('ply\nformat %s 1.0\nelement vertex 3\n%selement face 1\n'
                              'property list uchar int vertex_indices\nend_header\n' % (fmt, vertex_props))
                    body = b''.join(struct.pack(endian + vertex_fmt, *row) for row in (
                        (1, 2, 3, 255, 0, 0, 0)[:len(vertex_fmt)],
                        (4, 5, 6, 0, 255, 0, 0)[:len(vertex_fmt)],
                        (7, 8, 9, 0, 0, 255, 0)[:len(vertex_fmt)],
                    ))
                    body += struct.pack(endian + 'Biii', 3, 0, 1, 2)
                    data = header.encode() + body

                    result = parse_ply(data)
                    self.assertEqual(result.vertices, [[1, 2, 3], [4, 5, 6], [7, 8, 9]])
                    self.assertEqual(result.colors, [[255, 0, 0], [0, 255, 0], [0, 0, 255]])
                    self.assertEqual(result.faces, [[0, 1, 2]])
                    with self.assertRaises(ValueError) as context:
                        parse_ply(data[:-2])
                    self.assertEqual(str(context.exception), 'PLY: unexpected end of file in face 0')

    def test_binary_files_must_be_passed_as_bytes(self):
        self.assertParseError('ply\nformat binary_little_endian 1.0\nelement vertex 0\nend_header\n',
                              'must be passed as bytes')

    def test_parse_ply_file(self):
        result = parse_ply_file(CUBE)
        self.assertIsInstance(result, PLYObject)
        self.assertEqual(result.name, CUBE)
        self.assertEqual(len(result.vertices), 8)
        self.assertEqual(len(result.faces), 12)
        self.assertEqual(result.vertices[0], [-1, -1, 1])
        self.assertEqual(result.faces[0], [0, 1, 2])
        self.assertEqual(result.colors, [])
        self.assertEqual(result.normals, [])


if __name__ == '__main__':
    unittest.main()
