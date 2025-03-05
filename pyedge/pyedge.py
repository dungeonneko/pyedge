import struct
from PIL import Image
import numpy as np

EDGELIB_CANNOT_OPEN = -1
EDGELIB_NOT_EDGE_FILE = -2
EDGELIB_OK = 0

class EdgeFileError(Exception):
    pass

class EdgeFile:
    def __init__(self, filename):
        self.width = 0
        self.height = 0
        self.transColor = 0
        self.palette = bytearray(768)  # 256 * 3
        self.layers = []
        self.images = []
        self._read_file(filename)
        self._make_images()

    def _read_file(self, filename):
        try:
            with open(filename, "rb") as fp:
                # ファイルヘッダー読み込み
                szHeader = fp.read(10)
                if len(szHeader) != 10 or not szHeader.startswith(b"EDGE"):
                    raise EdgeFileError("Invalid EDGE file header")
                
                # 横幅・縦幅・レイヤ数・透明色の読み込み
                try:
                    self.width, self.height = struct.unpack("ii", fp.read(8))
                    num_of_layers = struct.unpack("H", fp.read(2))[0]
                    self.transColor = struct.unpack("B", fp.read(1))[0]
                except struct.error:
                    raise EdgeFileError("Failed to read file dimensions")
                
                # カラーパレット読み込み
                self.palette = fp.read(768)  # 256 * 3
                if len(self.palette) != 768:
                    raise EdgeFileError("Failed to read color palette")
                
                # データを展開しながら読み込む
                nImageSize = self.width * self.height
                
                for _ in range(num_of_layers):
                    # レイヤ名の取得
                    szTemp = fp.read(EdgeLayer.NAME_MAX)
                    if len(szTemp) != EdgeLayer.NAME_MAX:
                        raise EdgeFileError("Failed to read layer name")
                    
                    # 表示・非表示の読み込み
                    bShow = fp.read(1)
                    if len(bShow) != 1:
                        raise EdgeFileError("Failed to read layer visibility")
                    bShow = bool(struct.unpack("B", bShow)[0])
                    
                    # イメージの展開しながら読み込み
                    pbtImage = bytearray(nImageSize)
                    compressor = EdgeCompress()
                    if not compressor.read(fp, pbtImage, nImageSize):
                        raise EdgeFileError("Failed to decompress image data")
                    
                    # レイヤを追加
                    pLayer = EdgeLayer()
                    pLayer.set_name(szTemp.decode("utf-8", "ignore"))
                    pLayer.set_show(bShow)
                    pLayer.set_image(pbtImage)
                    self.layers.append(pLayer)

        except FileNotFoundError:
            raise EdgeFileError("File not found: " + filename)

        except Exception as e:
            raise EdgeFileError(f"Error reading EDGE file: {e}")

    def _make_images(self):
        self.images = []
        for layer in self.layers:
            image_data = np.zeros((self.height, self.width, 4), dtype=np.uint8)
            for i, color_index in enumerate(layer.image):
                y = i // self.width
                x = i % self.width
                b = self.palette[color_index * 3]
                g = self.palette[color_index * 3 + 1]
                r = self.palette[color_index * 3 + 2]
                a = 0 if color_index == self.transColor else 255
                image_data[y, x] = [r, g, b, a]
            self.images.append(Image.fromarray(image_data, mode='RGBA'))


class EdgeLayer:
    NAME_MAX = 80
    
    def __init__(self):
        self.name = ""
        self.show = False
        self.image = bytearray()
    
    def set_name(self, name):
        self.name = name.strip('\x00')
    
    def set_show(self, show):
        self.show = show
    
    def set_image(self, image):
        self.image = image


class EdgeCompress:
    class EdgeCompList:
        def __init__(self, position=None, length=None, value=None, next_node=None):
            self.position = position
            self.length = length
            self.value = value
            self.next = next_node

    def read(self, fp, data_dest, dest_max):
        comp_max = int.from_bytes(fp.read(4), byteorder='little')
        position = []
        length = []
        value = []

        for _ in range(comp_max):
            position.append(int.from_bytes(fp.read(4), byteorder='little'))
            length.append(int.from_bytes(fp.read(4), byteorder='little'))
            value.append(ord(fp.read(1)))

        src_max = int.from_bytes(fp.read(4), byteorder='little')
        data_src = bytearray(fp.read(src_max))

        comp = 0
        dest = 0
        i = 0
        while i <= src_max:
            if comp < comp_max and i == position[comp]:
                for j in range(length[comp]):
                    if dest + j < dest_max:
                        data_dest[dest + j] = value[comp]
                dest += length[comp]
                comp += 1
                i -= 1
            elif i < src_max:
                data_dest[dest] = data_src[i]
                dest += 1
            i += 1

        return True
