#!/usr/bin/env python3

import logging
import pi3d
from threading import Thread
import math
import time
import os
from PIL import Image, ExifTags, ImageFilter # these are needed for getting exif data from images

log = logging.getLogger(__name__)

EXIF_DATID = None  # this needs to be set before get_files() above can extract exif date info
EXIF_ORIENTATION = None
for k in ExifTags.TAGS:
    if ExifTags.TAGS[k] == 'DateTimeOriginal':
        EXIF_DATID = k
    if ExifTags.TAGS[k] == 'Orientation':
        EXIF_ORIENTATION = k

class Pic():
    def __init__(self, path, rel_dir_name=None, fname=None):
        self.path = path
        self.rel_dir_name = rel_dir_name
        self.fname = fname
        self.load_tex()

    def load_tex(self):
        self.tex = None
        try:
            im = Image.open(self.path)
            im.putalpha(255) # this will convert to RGBA and set alpha to opaque
            self.orientation = 1
            if EXIF_DATID is not None and EXIF_ORIENTATION is not None:
                try:
                    exif_data = im._getexif()
                    #print('orientation is {}'.format(exif_data[EXIF_ORIENTATION]))
                    self.dt = time.mktime(
                        time.strptime(exif_data[EXIF_DATID], '%Y:%m:%d %H:%M:%S'))
                    self.orientation = int(exif_data[EXIF_ORIENTATION])
                except Exception as e: # NB should really check error here but it's almost certainly due to lack of exif data
                    print('trying to read exif', e)
                    self.dt = os.path.getmtime(self.path) # so use file last modified date
            if self.orientation == 2:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            if self.orientation == 3:
                im = im.transpose(Image.ROTATE_180) # rotations are clockwise
            if self.orientation == 4:
                im = im.transpose(Image.FLIP_TOP_BOTTOM)
            if self.orientation == 5:
                im = im.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_270)
            if self.orientation == 6:
                im = im.transpose(Image.ROTATE_270)
            if self.orientation == 7:
                im = im.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_90)
            if self.orientation == 8:
                im = im.transpose(Image.ROTATE_90)
                do_resize = False
            else:
                do_resize = True
            self.tex = pi3d.Texture(im, blend = True, m_repeat = True, automatic_resize = do_resize, free_after_load = True)
        except Exception as e:
            print('''Couldn't load file {} giving error: {}'''.format(self.path, e))

class Slide():

    def __init__(self, display, camera, shader_path, edge_alpha):
        self.sprite = pi3d.Sprite(camera = camera, w = display.width, h = display.height, z = 5.0)
        self.sprite.set_shader(pi3d.Shader(shader_path))
        self.sprite.unif[47] = edge_alpha
        self.bg_pic = None
        self.fg_pic = None
        self.next_pic = None
        self.display = display

    def set_next_texture(self, fit=True):
        if self.next_pic is None: # have not get a new pic
            return
        # Re texture sprite
        self.bg_pic = self.fg_pic
        self.fg_pic = self.next_pic
        if self.bg_pic is None: # First pic - Make bg = fg = next
            self.bg_pic = self.next_pic
        self.sprite.set_textures([self.fg_pic.tex, self.bg_pic.tex,])
        self.sprite.unif[45:47] = self.sprite.unif[42:44] # Transfer front w,h to back
        self.sprite.unif[51:53] = self.sprite.unif[48:50] # Transfer front w,h offsets to back
        wh_rat = (self.display.width * self.fg_pic.tex.iy) / (self.display.height * self.fg_pic.tex.ix)
        if (wh_rat > 1.0 and fit) or (wh_rat <= 1.0 and not fit):
            sz1, sz2, os1, os2 = 42, 43, 48, 49
        else:
            sz1, sz2, os1, os2 = 43, 42, 49, 48
            wh_rat = 1.0 / wh_rat
        self.sprite.unif[sz1] = wh_rat
        self.sprite.unif[sz2] = 1.0
        self.sprite.unif[os1] = (wh_rat - 1.0) * 0.5
        self.sprite.unif[os2] = 0.0

    def load_image(self, path, fit=True):
        self.next_pic = Pic(path, os.path.dirname(path), os.path.basename(path))
        self.next_pic.dt = None
        self.sprite.unif[44] = 1.0
        self.set_next_texture(fit)

    def load_lib_image(self, piclib, fit=True):
        for __i in range(10): # max files to check
            np = piclib.next_pic()
            np_path = os.path.join(piclib.src_dir, np.pic_dir.rel_dir_name, np.file_name)
            self.next_pic = Pic(np_path, np.pic_dir.rel_dir_name, np.file_name)
            if self.next_pic.tex is not None:
                return

    def transition_to_image(self, piclib, fit=True, start_delay=0, trans_secs=0):
        self.load_thread = Thread(name='Slide Load', target=self.load_lib_image, args=(piclib, fit))
        self.load_thread.start()
        time.sleep(start_delay)
        # Wait (if required) for image to load into next_tex
        self.load_thread.join()
        self.set_next_texture(fit)
        # Do the alpha transition
        alpha = 0.0
        tick_cnt = math.ceil(trans_secs/0.2)
        if tick_cnt > 0:
            alpha_delta = 1.0/tick_cnt
            for __tick in range(tick_cnt):
                alpha += alpha_delta
                self.sprite.unif[44] = alpha
                time.sleep(0.2)
        # set alpha to complete
        self.sprite.unif[44] = 1.0

    def start_trans_to_next(self, piclib, fit=True, start_delay=10, trans_secs=3):
        self.trans_thread = Thread(name='Slide Transition', target=self.transition_to_image, args=(piclib, fit, start_delay, trans_secs))
        self.trans_thread.start()

    def draw(self):
        self.sprite.draw()
