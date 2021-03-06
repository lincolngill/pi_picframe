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

class Slide(pi3d.Sprite):

    def __init__(self, display, camera, shader_path, edge_alpha):
        super(Slide, self).__init__(camera = camera, w = display.width, h = display.height, z = 5.0)
        #self.sprite = pi3d.Sprite(camera = camera, w = display.width, h = display.height, z = 5.0)
        self.set_shader(pi3d.Shader(shader_path))
        self.unif[47] = edge_alpha
        self.bg_pic = None
        self.fg_pic = None
        self.next_pic = None
        self.display = display

    def set_fg_to_next(self, fit=True):
        # Re texture sprite
        self.bg_pic = self.fg_pic
        self.fg_pic = self.next_pic
        if self.bg_pic is None: # First pic - Make bg = fg = next
            self.bg_pic = self.next_pic
        self.set_textures([self.fg_pic.tex, self.bg_pic.tex,])
        self.unif[45:47] = self.unif[42:44] # Transfer front w,h to back
        self.unif[51:53] = self.unif[48:50] # Transfer front w,h offsets to back
        wh_rat = (self.display.width * self.fg_pic.tex.iy) / (self.display.height * self.fg_pic.tex.ix)
        if (wh_rat > 1.0 and fit) or (wh_rat <= 1.0 and not fit):
            sz1, sz2, os1, os2 = 42, 43, 48, 49
        else:
            sz1, sz2, os1, os2 = 43, 42, 49, 48
            wh_rat = 1.0 / wh_rat
        self.unif[sz1] = wh_rat
        self.unif[sz2] = 1.0
        self.unif[os1] = (wh_rat - 1.0) * 0.5
        self.unif[os2] = 0.0

    def load_image(self, path, fit=True):
        self.next_pic = Pic(path, os.path.dirname(path), os.path.basename(path))
        self.next_pic.dt = None
        self.transition_to_next(fit)

    def load_next_image(self, root_path, piclist, fit=True):
        try:
            for __i in range(10): # max files to check
                np = next(piclist)
                np_path = os.path.join(root_path, np.pic_dir.rel_dir_name, np.file_name)
                self.next_pic = Pic(np_path, np.pic_dir.rel_dir_name, np.file_name)
                if self.next_pic.tex is not None:
                    break
        except StopIteration:
            self.next_pic = None

    def start_load_next_image(self, root_path, piclist, fit=True):
        self.load_thread = Thread(name='Slide Load', target=self.load_next_image, args=(root_path, piclist, fit))
        self.load_thread.start()

    def transition_to_next(self, fit=True, trans_secs=0):
        self.set_fg_to_next(fit)
        # Do the alpha transition. Fade in fg
        alpha = 0.0
        tick_cnt = math.ceil(trans_secs/0.2)
        if tick_cnt > 0:
            alpha_delta = 1.0/tick_cnt
            for __tick in range(tick_cnt):
                alpha += alpha_delta
                self.unif[44] = alpha
                time.sleep(0.2)
        # set alpha to complete
        self.unif[44] = 1.0
