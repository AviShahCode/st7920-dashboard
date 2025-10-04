from PIL import ImageFont, ImageDraw, Image
import numpy as np
from enum import Enum, auto


# ON -> selected pixels will turn ON pixels
# OFF -> selected pixels will turn OFF pixels
# XOR -> selected pixels will INVERT pixels
class BlendMode(Enum):
    ON = auto()
    OFF = auto()
    XOR = auto()


# specifically designed for st7920, using 16 bit words
# _parent -> if child gets, dirty, so does parent
class Bitmap:
    __slots__ = "width", "height", "words", "_is_dirty", "_parent", "_blend_mode"

    def __init__(self, width=128, height=64, parent=None, blend_mode=BlendMode.ON):
        self.width = width
        self.height = height
        self.words = np.zeros((height, width // 16), dtype=np.uint16)
        self._is_dirty = True
        self._parent = parent
        self._blend_mode = blend_mode

    def reset(self):
        self.words.fill(0)

    def set_pixel(self, x, y, value=True):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        word = x // 16
        bit = 15 - (x % 16)
        mask = 1 << bit
        if value:
            self.words[y, word] |= mask
        else:
            self.words[y, word] &= ~mask
        self.dirty()

    def get_pixel(self, x, y):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return 0
        word = x // 16
        bit = 15 - (x % 16)
        return (self.words[y, word] >> bit) & 1

    def set_word(self, v, h, value=0x0000):
        if 0 <= v < self.height and 0 <= h < self.width // 16:
            self.words[v, h] = value & 0xFFFF
            self.dirty()

    def draw(self, parent_width, parent_height):
        raise NotImplementedError

    def dirty(self):
        self._is_dirty = True
        if self._parent:
            self._parent.dirty()

    def reverse(self):
        self.words ^= 0xFFFF


# children are drawn in same order as they were added,
# so blend mode of a child will affect all pixels
# drawn before that child
class GraphicsBuffer(Bitmap):
    def __init__(self, width=128, height=64):
        Bitmap.__init__(self, width, height)
        self.children = []

    def add(self, drawable):
        drawable._parent = self
        self.children.append(drawable)

    def draw(self):
        if not self._is_dirty:
            return self

        self.reset()
        for c in self.children:
            bm = c._blend_mode
            drawn = c.draw(self.width, self.height)
            if bm == BlendMode.ON:
                self.words |= drawn.words
            elif bm == BlendMode.OFF:
                self.words &= ~drawn.words
            elif bm == BlendMode.XOR:
                self.words ^= drawn.words
        return self

    def reverse(self):
        for h in range(self.height):
            for w in range(self.width // 16):
                self.words[h][w] ^= 0xFFFF


class Line(Bitmap):
    def __init__(self, x1, y1, x2, y2, blend_mode=BlendMode.ON, width=128, height=64):
        Bitmap.__init__(self, width, height)
        self._x1, self._y1, self._x2, self._y2 = x1, y1, x2, y2
        self._blend_mode = blend_mode

    @property
    def x1(self):
        return self._x1

    @x1.setter
    def x1(self, v):
        self._x1 = v
        self.dirty()

    @property
    def y1(self):
        return self._y1

    @y1.setter
    def y1(self, v):
        self._y1 = v
        self.dirty()

    @property
    def x2(self):
        return self._x2

    @x2.setter
    def x2(self, v):
        self._x2 = v
        self.dirty()

    @property
    def y2(self):
        return self._y2

    @y2.setter
    def y2(self, v):
        self._y2 = v
        self.dirty()

    def draw(self, width, height):
        if not self._is_dirty:
            return self

        self.reset()

        x1, y1, x2, y2 = self._x1, self._y1, self._x2, self._y2
        dx, dy = abs(x2 - x1), -abs(y2 - y1)
        sx, sy = (1 if x1 < x2 else -1), (1 if y1 < y2 else -1)
        err = dx + dy
        while True:
            self.set_pixel(x1, y1)
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x1 += sx
            if e2 <= dx:
                err += dx
                y1 += sy

        self._is_dirty = False
        return self


class Circle(Bitmap):
    def __init__(
        self, xc, yc, radius, fill=False, blend_mode=BlendMode.ON, width=128, height=64
    ):
        Bitmap.__init__(self, width, height)
        self._xc, self._yc, self._radius, self._fill = xc, yc, radius, fill
        self._blend_mode = blend_mode

    @property
    def xc(self):
        return self._xc

    @xc.setter
    def xc(self, v):
        self._xc = v
        self.dirty()

    @property
    def yc(self):
        return self._yc

    @yc.setter
    def yc(self, v):
        self._yc = v
        self.dirty()

    @property
    def radius(self):
        return self._radius

    @radius.setter
    def radius(self, v):
        self._radius = v
        self.dirty()

    @property
    def fill(self):
        return self._fill

    @fill.setter
    def fill(self, v):
        self._fill = v
        self.dirty()

    def draw(self, width, height):
        if not self._is_dirty:
            return self

        self.reset()

        x0, y0, r = self._xc, self._yc, self._radius
        x, y, d = 0, r, 1 - r

        def circle_points(xc, yc, x, y):
            for px, py in [
                (xc + x, yc + y),
                (xc - x, yc + y),
                (xc + x, yc - y),
                (xc - x, yc - y),
                (xc + y, yc + x),
                (xc - y, yc + x),
                (xc + y, yc - x),
                (xc - y, yc - x),
            ]:
                self.set_pixel(px, py)

        def circle_fill(xc, yc, x, y):
            for px in range(xc - x, xc + x + 1):
                self.set_pixel(px, yc + y)
                self.set_pixel(px, yc - y)
            for px in range(xc - y, xc + y + 1):
                self.set_pixel(px, yc + x)
                self.set_pixel(px, yc - x)

        while x <= y:
            if self._fill:
                circle_fill(x0, y0, x, y)
            else:
                circle_points(x0, y0, x, y)
            if d < 0:
                d += 2 * x + 3
            else:
                d += 2 * (x - y) + 5
                y -= 1
            x += 1

        self._is_dirty = False
        return self


class Triangle(Bitmap):
    def __init__(
        self,
        x1,
        y1,
        x2,
        y2,
        x3,
        y3,
        fill=False,
        blend_mode=BlendMode.ON,
        width=128,
        height=64,
    ):
        Bitmap.__init__(self, width, height)
        self._x1, self._y1, self._x2, self._y2, self._x3, self._y3, self._fill = (
            x1,
            y1,
            x2,
            y2,
            x3,
            y3,
            fill,
        )
        self._blend_mode = blend_mode

    # Properties for each vertex + fill
    def _make_prop(name):
        def getter(self):
            return getattr(self, "_" + name)

        def setter(self, v):
            setattr(self, "_" + name, v)
            self.dirty()

        return property(getter, setter)

    x1 = _make_prop("x1")
    y1 = _make_prop("y1")
    x2 = _make_prop("x2")
    y2 = _make_prop("y2")
    x3 = _make_prop("x3")
    y3 = _make_prop("y3")
    fill = _make_prop("fill")

    def draw(self, width, height):
        if not self._is_dirty:
            return self

        self.reset()

        if not self._fill:
            l1 = Line(
                self._x1, self._y1, self._x2, self._y2, self._blend_mode, width, height
            ).draw(width, height)
            l2 = Line(
                self._x2, self._y2, self._x3, self._y3, self._blend_mode, width, height
            ).draw(width, height)
            l3 = Line(
                self._x3, self._y3, self._x1, self._y1, self._blend_mode, width, height
            ).draw(width, height)
            self.words |= l1.words | l2.words | l3.words
        else:
            vertices = [
                (self._x1, self._y1),
                (self._x2, self._y2),
                (self._x3, self._y3),
            ]
            ymin, ymax = min(y for _, y in vertices), max(y for _, y in vertices)
            for y in range(ymin, ymax + 1):
                xints = []
                for (x0, y0), (x1, y1) in [
                    (vertices[0], vertices[1]),
                    (vertices[1], vertices[2]),
                    (vertices[2], vertices[0]),
                ]:
                    if y0 == y1:
                        continue
                    if (y >= min(y0, y1)) and (y <= max(y0, y1)):
                        t = (y - y0) / (y1 - y0)
                        x = x0 + t * (x1 - x0)
                        xints.append(x)
                if len(xints) >= 2:
                    xL, xR = sorted(xints)[:2]
                    for x in range(int(round(xL)), int(round(xR)) + 1):
                        self.set_pixel(x, y)
        self._is_dirty = False
        return self


class Rectangle(Bitmap):
    def __init__(
        self, x, y, w, h, fill=False, blend_mode=BlendMode.ON, width=128, height=64
    ):
        Bitmap.__init__(self, width, height)
        self._x, self._y, self._w, self._h, self._fill = x, y, w, h, fill
        self._blend_mode = blend_mode

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, v):
        self._x = v
        self.dirty()

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, v):
        self._y = v
        self.dirty()

    @property
    def w(self):
        return self._w

    @w.setter
    def w(self, v):
        self._w = v
        self.dirty()

    @property
    def h(self):
        return self._h

    @h.setter
    def h(self, v):
        self._h = v
        self.dirty()

    @property
    def fill(self):
        return self._fill

    @fill.setter
    def fill(self, v):
        self._fill = v
        self.dirty()

    def draw(self, width, height):
        if not self._is_dirty:
            return self

        self.reset()

        if not self._fill:
            top = Line(
                self._x,
                self._y,
                self._x + self._w - 1,
                self._y,
                blend_mode=self._blend_mode,
                width=width,
                height=height,
            ).draw(width, height)
            left = Line(
                self._x,
                self._y,
                self._x,
                self._y + self._h - 1,
                blend_mode=self._blend_mode,
                width=width,
                height=height,
            ).draw(width, height)
            right = Line(
                self._x + self._w - 1,
                self._y,
                self._x + self._w - 1,
                self._y + self._h - 1,
                blend_mode=self._blend_mode,
                width=width,
                height=height,
            ).draw(width, height)
            bottom = Line(
                self._x,
                self._y + self._h - 1,
                self._x + self._w - 1,
                self._y + self._h - 1,
                blend_mode=self._blend_mode,
                width=width,
                height=height,
            ).draw(width, height)

            # Merge line bitmaps into rectangle
            self.words |= top.words | left.words | right.words | bottom.words
        else:
            for yy in range(self._y, self._y + self._h):
                for xx in range(self._x, self._x + self._w):
                    self.set_pixel(xx, yy)

        self._is_dirty = False
        return self


class DrawableText(Bitmap):
    def __init__(
        self,
        text,
        font_path,
        size,
        x=0,
        y=0,
        blend_mode=BlendMode.ON,
        width=128,
        height=64,
    ):
        Bitmap.__init__(self, width, height)
        self._text = text
        self._font = ImageFont.truetype(font_path, size)
        self._x, self._y = x, y
        self._blend_mode = blend_mode

    # properties
    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, v):
        self._text = v
        self.dirty()

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, v):
        self._x = v
        self.dirty()

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, v):
        self._y = v
        self.dirty()

    def draw(self, width, height):
        if not self._is_dirty:
            return self

        self.reset()

        img = Image.new("1", (width, height), 1)
        d = ImageDraw.Draw(img)
        d.text((self._x, self._y), self._text, font=self._font, fill=0)
        pixels = img.load()
        for j in range(height):
            for i in range(width):
                if pixels[i, j] == 0:
                    self.set_pixel(i, j, True)
        self._is_dirty = False
        return self
