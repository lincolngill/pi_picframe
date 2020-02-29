#!/usr/bin/env python3

import logging
import pi3d
from threading import Thread
import math
import time
from PIL import Image, ExifTags, ImageFilter # these are needed for getting exif data from images

log = logging.getLogger(__name__)

class Slide():

    def __init__(self, display, camera, shader_path, edge_alpha):
        self.sprite = pi3d.Sprite(camera = camera, w = display.width, h = display.height, z = 5.0)
        self.sprite.set_shader(shader_path)
        self.sprite.unif[47] = edge_alpha
        self.fg_tex = None
        self.bg_tex = None
        self.display = display

    def __tex_load(self, fname, orientation=1, size = None):
        try:
            im = Image.open(fname)
            im.putalpha(255) # this will convert to RGBA and set alpha to opaque
            if orientation == 2:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            if orientation == 3:
                im = im.transpose(Image.ROTATE_180) # rotations are clockwise
            if orientation == 4:
                im = im.transpose(Image.FLIP_TOP_BOTTOM)
            if orientation == 5:
                im = im.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_270)
            if orientation == 6:
                im = im.transpose(Image.ROTATE_270)
            if orientation == 7:
                im = im.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_90)
            if orientation == 8:
                im = im.transpose(Image.ROTATE_90)
                do_resize = False
            else:
                do_resize = True
            tex = pi3d.Texture(im, blend = True, m_repeat = True, automatic_resize = do_resize, free_after_load = True)
        except Exception as e:
            print('''Couldn't load file {} giving error: {}'''.format(fname, e))
            tex = None
        return tex

    def load_image(self, fname, fit=True):
        self.sprite.fg_tex = self.__tex_load(fname, size=(self.display.width, self.display.height))
        if self.sprite.fg_tex is not None:
            if self.sprite.bg_tex is None:
                self.sprite.bg_tex = self.sprite.fg_tex
            self.sprite.set_textures([self.fg_tex, self.bg_tex,])
            self.sprite.unif[45:47] = self.sprite.unif[42:44] # Transfer front w,h to back
            self.sprite.unif[51:53] = self.sprite.unif[48:50] # Transfer front w,h offsets to back
            wh_rat = (self.display.width * self.fg_tex.iy) / (self.display.height * self.fg_tex.ix)
            if (wh_rat > 1.0 and fit) or (wh_rat <= 1.0 and not fit):
                sz1, sz2, os1, os2 = 42, 43, 48, 49
            else:
                sz1, sz2, os1, os2 = 43, 42, 49, 48
                wh_rat = 1.0 / wh_rat
            self.sprite.unif[sz1] = wh_rat
            self.sprite.unif[sz2] = 1.0
            self.sprite.unif[os1] = (wh_rat - 1.0) * 0.5
            self.sprite.unif[os2] = 0.0

    def transition_to_image(self, fname, fit=True, start_delay=0, trans_secs=0):
        self.load_thread = Thread(name='Slide Load', target=self.load_image, args=(fname, fit))
        self.load_thread.start()
        time.sleep(start_delay)
        # Wait (if required) for image to load into fg_tex
        self.load_thread.join()
        alpha = 0.0
        # Do the alpha transition
        tick_cnt = math.ceil(trans_secs/0.2)
        if tick_cnt > 0:
            alpha_delta = 1.0/tick_cnt
            for tick in range(tick_cnt):
                alpha += alpha_delta
                self.sprite.unif[44] = alpha
                time.sleep(0.2)
        # set alpha to complete
        self.sprite.unif[44] = 1.0

    def start_trans_to_file(self, fname, fit=True, start_delay=0, trans_secs=0):
        self.trans_thread = Thread(name='Slide Transition', target=self.transition_to_image, args=(fname, fit, start_delay, trans_secs))
        self.update_thread.start()

    def draw(self):
        self.sprite.draw()
