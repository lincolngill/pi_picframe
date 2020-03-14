#!/usr/bin/env python3

from __future__ import absolute_import, division, print_function, unicode_literals

"""This demo shows the use of special transition shaders on the Canvas 
shape for 2D drawing. Also threading is used to allow the file access to 
be done in the background.
"""
import os
import random
import time
import glob
import threading
import pi3d

from six_mod.moves import queue

# these are needed for getting exif data from images
from PIL import Image, ExifTags, ImageFilter

THIS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
FONT_FILE = os.path.join(THIS_DIR, 'fonts', 'NotoSans-Regular.ttf')

PIC_DIR = '/home/pi/Pictures'
FPS = 20
FIT = True
EDGE_ALPHA = 0.5  # see background colour at edge. 1.0 would show reflection of image
BACKGROUND = (0.2, 0.2, 0.2, 1.0)
BG_IMAGE = os.path.join(THIS_DIR, 'background.jpg')
FONT_COLOUR = (255, 255, 255, 255)

LOGGER = pi3d.Log(__name__, level='INFO', format='%(message)s')
LOGGER.info('''#########################################################
press ESC to escape, S to go back, any key for next slide
#########################################################''')

# Setup display and initialise pi3d
DISPLAY = pi3d.Display.create(x=0, y=0, frames_per_second=FPS,
                              display_config=pi3d.DISPLAY_CONFIG_HIDE_CURSOR, background=BACKGROUND)
LOGGER.info('Display W: {}   H: {}'.format(DISPLAY.width, DISPLAY.height))
CAMERA = pi3d.Camera.instance()
shader = [
    #    pi3d.Shader(os.path.join(THIS_DIR, "shaders", "blend_new")),
    pi3d.Shader(os.path.join(THIS_DIR, "shaders", "blend_holes")),
    pi3d.Shader(os.path.join(THIS_DIR, "shaders", "blend_false")),
    pi3d.Shader(os.path.join(THIS_DIR, "shaders", "blend_burn")),
    pi3d.Shader(os.path.join(THIS_DIR, "shaders", "blend_bump"))
]

iFiles = glob.glob(os.path.join(PIC_DIR, "2020*/*.jpg"))
iFiles.sort()
nFi = len(iFiles)
fileQ = queue.Queue()  # queue for loading new texture files

FADE_STEP = 0.025
nSli = 8

def tex_load():
    """ This function runs all the time in a background thread. It checks the
    fileQ for images to load that have been inserted by Carousel.next() or prev()

    here the images are scaled to fit the Display size, if they were to be
    rendered pixel for pixel as the original then the mipmap=False argument would
    be used, which is faster, and w and h values set to the Texture size i.e.

    tex = pi3d.Texture(f, mipmap=False)
    ...
    wi, hi = tex.ix, tex.iy

    mipmap=False can also be used to speed up Texture loading and reduce the work
    required of the cpu
    """
    while True:
        slide = fileQ.get()
        try:
            im = Image.open(slide.fname)
            # this will convert to RGBA and set alpha to opaque
            im.putalpha(255)
            slide.orientation = 1
            if EXIF_DATID is not None and EXIF_ORIENTATION is not None:
                try:
                    exif_data = im._getexif()
                    slide.dt = time.mktime(
                        time.strptime(exif_data[EXIF_DATID], '%Y:%m:%d %H:%M:%S'))
                    slide.orientation = int(exif_data[EXIF_ORIENTATION])
                except Exception as e:  # NB should really check error here but it's almost certainly due to lack of exif data
                    LOGGER.warning('exif read error. File: {} Error: {}'.format(slide.fname,e))
                    # so use file last modified date
                    slide.dt = os.path.getmtime(slide.fname)
            if slide.orientation == 2:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            if slide.orientation == 3:
                im = im.transpose(Image.ROTATE_180)  # rotations are clockwise
            if slide.orientation == 4:
                im = im.transpose(Image.FLIP_TOP_BOTTOM)
            if slide.orientation == 5:
                im = im.transpose(Image.FLIP_LEFT_RIGHT).transpose(
                    Image.ROTATE_270)
            if slide.orientation == 6:
                im = im.transpose(Image.ROTATE_270)
            if slide.orientation == 7:
                im = im.transpose(Image.FLIP_LEFT_RIGHT).transpose(
                    Image.ROTATE_90)
            if slide.orientation == 8:
                im = im.transpose(Image.ROTATE_90)
                do_resize = False
            else:
                do_resize = True
            
            # tex = pi3d.Texture(item[0], blend=True, mipmap=False) #pixelly but faster 3.3MB in 3s
            # nicer but slower 3.3MB in 4.5s
            #tex = pi3d.Texture(fname, blend=True, mipmap=True)
            tex = pi3d.Texture(im, blend=True, mipmap=True, m_repeat=True, automatic_resize=do_resize, free_after_load=True)
            xrat = DISPLAY.width/tex.ix
            yrat = DISPLAY.height/tex.iy
            if yrat < xrat:
                xrat = yrat
            wi, hi = tex.ix * xrat, tex.iy * xrat
            #wi, hi = tex.ix, tex.iy
            xi = (DISPLAY.width - wi)/2
            yi = (DISPLAY.height - hi)/2
            slide.tex = tex
            slide.dimensions = (wi, hi, xi, yi)
        except Exception as e:
            LOGGER.error("Failed to load. File: {} Error: {}".format(slide.fname, e))
            slide.error = True
        fileQ.task_done()


class Slide(object):
    def reset(self, fname=None):
        self.tex = None
        self.dimensions = None
        self.orientation = 1
        self.dt = None
        self.fname = fname
        self.error = False
        self.shader = random.choice(shader)

    def __init__(self, fname=None):
        self.reset(fname)

class Frame(pi3d.Canvas):
    def __init__(self, slide, fade=1.0):
        super(Frame, self).__init__()
        self.set_tex(slide, fade=fade)

    def set_fade(self, fade):
        self.fade = fade
        self.unif[44] = fade

    def inc_fade(self, fade_step=FADE_STEP):
        if self.fade < 1.0:
            self.set_fade(self.fade + fade_step)

    def set_tex(self, sbg, sfg=None, fade=0.0):
        self.set_fade(fade)
        if sfg is None:
            sfg = sbg
        self.set_shader(sbg.shader)
        self.set_draw_details(self.shader, [sfg.tex, sbg.tex])
        self.set_2d_size(sbg.dimensions[0], sbg.dimensions[1], sbg.dimensions[2], sbg.dimensions[3])
        # need to pass shader dimensions for both textures
        self.unif[48:54] = self.unif[42:48]
        self.set_2d_size(sfg.dimensions[0], sfg.dimensions[1], sfg.dimensions[2], sfg.dimensions[3])


class Carousel:
    def __init__(self):
        self.canvas = pi3d.Canvas()
        self.canvas.set_shader(shader[0])
        self.fade = 0.0
        self.slides = []
        #half = 0
        for i in range(nSli):
            s = Slide(iFiles[i % nFi])
            self.slides.append(s)
            fileQ.put(s)

        self.focus = nSli - 1
        self.focus_fi = nFi - 1

    def next(self, step=1):
        self.fade = 0.0
        sfg = self.slides[self.focus]  # foreground
        self.focus = (self.focus + step) % nSli
        self.focus_fi = (self.focus_fi + step) % nFi
        sbg = self.slides[self.focus]  # background
        self.canvas.set_shader(sbg.shader)
        self.canvas.set_draw_details(self.canvas.shader, [sfg.tex, sbg.tex])
        self.canvas.set_2d_size(
            sbg.dimensions[0], sbg.dimensions[1], sbg.dimensions[2], sbg.dimensions[3])
        # need to pass shader dimensions for both textures
        self.canvas.unif[48:54] = self.canvas.unif[42:48]
        self.canvas.set_2d_size(
            sfg.dimensions[0], sfg.dimensions[1], sfg.dimensions[2], sfg.dimensions[3])
        # get thread to put one in end of pipe
        s = self.slides[(self.focus + int(0.5 - 4.5 * step)) % nSli]
        s.reset(iFiles[(self.focus_fi + int(0.5 + 3.5 * step)) % nFi])
        fileQ.put(s)
        # fileQ.join()

    def prev(self):
        self.next(step=-1)

    def update(self):
        if self.fade < 1.0:
            self.fade += fade_step

    def draw(self):
        self.update()
        self.canvas.unif[44] = self.fade
        self.canvas.draw()

XIF_DATID = None  # this needs to be set before tex_load() above can extract exif date info
EXIF_ORIENTATION = None
for k in ExifTags.TAGS:
    if ExifTags.TAGS[k] == 'DateTimeOriginal':
        EXIF_DATID = k
    if ExifTags.TAGS[k] == 'Orientation':
        EXIF_ORIENTATION = k

class TextAttr():
    dir = ''
    fname = ''
    date = ''
    status = ''

text_attr = TextAttr()
font = pi3d.Font(FONT_FILE, FONT_COLOUR, codepoints = list(range(32, 128)), shadow_radius=4.0, shadow=(0,0,0,128))
colourGradient = pi3d.TextBlockColourGradient((1.0, 0.0, 0.0, 1.0), (0.0, 1.0, 0.0, 1.0))

file_pt = pi3d.PointText(font, CAMERA, max_chars = 216, point_size = 80)
dir_tb = pi3d.TextBlock(x = DISPLAY.width * -0.5 + 50,  y = DISPLAY.height * -0.5 + 100, z = 0.1, rot = 0.0, char_count = 100, text_format = '{:100}', data_obj=text_attr, attr="dir",
                           size = 0.5, spacing = "F", space = 0.02, colour = colourGradient)
file_pt.add_text_block(dir_tb)

file_tb = pi3d.TextBlock(x = DISPLAY.width * -0.5 + 50,  y = DISPLAY.height * -0.5 + 50, z = 0.1, rot = 0.0, char_count = 100, text_format = '{:100}', data_obj=text_attr, attr="fname",
                           size = 0.5, spacing = "F", space = 0.02, colour = colourGradient)
file_pt.add_text_block(file_tb)

date_tb = pi3d.TextBlock(x = DISPLAY.width * 0.5 -340,  y = DISPLAY.height * -0.5 + 50, z = 0.1, rot = 0.0, char_count = 15, text_format = '{:15}', data_obj=text_attr, attr="date",
                           size = 0.5, spacing = "F", space = 0.02, colour = colourGradient)
file_pt.add_text_block(date_tb)

title_pt = pi3d.PointText(font, CAMERA, max_chars = 26, point_size = 100)
title_tb = pi3d.TextBlock(x = DISPLAY.width * -0.25,  y = DISPLAY.height * 0.5 - 50, z = 0.1, rot = 0.0, char_count = 25, text_format = "Gills Picture Frame v2.0",
                           size = 0.99, spacing = "F", space = 0.02, colour = colourGradient)
title_pt.add_text_block(title_tb)

status_pt = pi3d.PointText(font, CAMERA, max_chars = 26, point_size = 80)
status_tb = pi3d.TextBlock(x = DISPLAY.width * -0.15,  y = DISPLAY.height * -0.5 + 200, z = 0.1, rot = 0.0, char_count = 25, text_format = '{:25}', data_obj=text_attr, attr="status",
                           size = 0.99, spacing = "F", space = 0.02, colour = (1.0, 0.0, 0.0, 1.0))
status_pt.add_text_block(status_tb)

crsl = Carousel()

t = threading.Thread(target=tex_load)
t.daemon = True
t.start()

bg = Slide(BG_IMAGE)
fileQ.put(bg)

# block the world, for now, until all the initial textures are in.
# later on, if the UI overruns the thread, there will be no crashola since the
# old texture should still be there.
fileQ.join()
frame = Frame(bg)

crsl.next()  # use to set up draw details for canvas
crsl.fade = 1.0  # so doesnt transition to slide #1

# Fetch key presses
mykeys = pi3d.Keyboard()
CAMERA.was_moved = False  # to save a tiny bit of work each loop
pictr = 0  # to do shader changing
shnum = 0
lasttm = time.time()
tmdelay = 8.0

display_elements = [frame]
while DISPLAY.loop_running():
    for e in display_elements:
        e.draw()
    #crsl.update()
    #crsl.draw()
    tm = time.time()
    if tm > (lasttm + tmdelay):
        lasttm = tm
        crsl.next()

    k = mykeys.read()
    #k = -1
    if k > -1:
        pictr += 1
        # shader change only happens after 4 button presses (ie not auto changes)
        if pictr > 3:
            pictr = 0
            shnum = (shnum + 1) % 4
            crsl.canvas.set_shader(shader[shnum])
        if k == 27:  # ESC
            mykeys.close()
            DISPLAY.stop()
            break
        if k == 115:  # S go back a picture
            crsl.prev()
        # all other keys load next picture
        else:
            crsl.next()

DISPLAY.destroy()
