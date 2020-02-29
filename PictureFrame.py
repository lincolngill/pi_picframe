#!/usr/bin/env python3
from __future__ import absolute_import, division, print_function, unicode_literals
'''
pi3d Picture Frame
'''
import os
import time
import random
import pi3d
from enum import Enum
import PicLibrary as PLib

# these are needed for getting exif data from images
from PIL import Image, ExifTags, ImageFilter

THIS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
FONT_FILE = os.path.join(THIS_DIR, 'fonts', 'NotoSans-Regular.ttf')

# ####################################################
# these variables are constants
# ####################################################
PIC_DIR = '/home/pi/Pictures'  # 'textures'
FPS = 20
FIT = True
EDGE_ALPHA = 0.5  # see background colour at edge. 1.0 would show reflection of image
BACKGROUND = (0.2, 0.2, 0.2, 1.0)
BG_IMAGE = os.path.join(THIS_DIR, 'background.jpg')
RESHUFFLE_NUM = 5  # times through before reshuffling
# limit to 49 ie 7x7 grid_size
CODEPOINTS = '1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ., _-/'
USE_MQTT = False
RECENT_N = 4  # shuffle the most recent ones to play before the rest
SHOW_NAMES = False
CHECK_DIR_TM = 60.0  # seconds to wait between checking if directory has changed
FONT_COLOUR = (255, 255, 255, 255)
# ####################################################
BLUR_EDGES = False  # use blurred version of image to fill edges - will override FIT = False
BLUR_AMOUNT = 12  # larger values than 12 will increase processing load quite a bit
BLUR_ZOOM = 1.0  # must be >= 1.0 which expands the backgorund to just fill the space around the image
KENBURNS = False  # will set FIT- > False and BLUR_EDGES- > False
# set to False when running headless to avoid curses error. True for debugging
KEYBOARD = False
# ####################################################
# these variables can be altered using MQTT messaging
# ####################################################
time_delay = 10.0  # between slides
fade_time = 3.0
shuffle = True  # shuffle on reloading
date_from = None
date_to = None
quit = False
paused = False  # NB must be set to True after the first iteration of the show!
# ####################################################
# only alter below here if you're keen to experiment!
# ####################################################
if KENBURNS:
    kb_up = True
    FIT = False
    BLUR_EDGES = False
if BLUR_ZOOM < 1.0:
    BLUR_ZOOM = 1.0
delta_alpha = 1.0 / (FPS * fade_time)  # delta alpha
last_file_change = 0.0  # holds last change time in directory structure
# check if new file or directory every hour
next_check_tm = time.time() + CHECK_DIR_TM
# ####################################################
# some functions to tidy subsequent code
# ####################################################


def tex_load(fname, orientation, size = None):
    try:
        im = Image.open(fname)
        im.putalpha(255)  # this will convert to RGBA and set alpha to opaque
        if orientation == 2:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        if orientation == 3:
            im = im.transpose(Image.ROTATE_180)  # rotations are clockwise
        if orientation == 4:
            im = im.transpose(Image.FLIP_TOP_BOTTOM)
        if orientation == 5:
            im = im.transpose(Image.FLIP_LEFT_RIGHT).transpose(
                Image.ROTATE_270)
        if orientation == 6:
            im = im.transpose(Image.ROTATE_270)
        if orientation == 7:
            im = im.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_90)
        if orientation == 8:
            im = im.transpose(Image.ROTATE_90)
        if BLUR_EDGES and size is not None:
            wh_rat = (size[0] * im.size[1]) / (size[1] * im.size[0])
            if abs(wh_rat - 1.0) > 0.01:  # make a blurred background
                (sc_b, sc_f) = (size[1] / im.size[1], size[0] / im.size[0])
                if wh_rat > 1.0:
                    (sc_b, sc_f) = (sc_f, sc_b)  # swap round
                (w, h) = (round(size[0] / sc_b / BLUR_ZOOM), 
                          round(size[1] / sc_b / BLUR_ZOOM))
                (x, y) = (
                    round(0.5 * (im.size[0] - w)), round(0.5 * (im.size[1] - h)))
                box = (x, y, x + w, y + h)
                blr_sz = (int(x * 512 / size[0]) for x in size)
                im_b = im.resize(size, resample = 0, box = box).resize(blr_sz)
                im_b = im_b.filter(ImageFilter.GaussianBlur(BLUR_AMOUNT))
                im_b = im_b.resize(size, resample = Image.BICUBIC)
                # to apply the same EDGE_ALPHA as the no blur method.
                im_b.putalpha(round(255 * EDGE_ALPHA))
                im = im.resize((int(x * sc_f)
                                for x in im.size), resample = Image.BICUBIC)
                im_b.paste(im, box = (round(0.5 * (im_b.size[0] - im.size[0])), 
                                    round(0.5 * (im_b.size[1] - im.size[1]))))
                im = im_b  # have to do this as paste applies in place
            do_resize = False
        else:
            do_resize = True
        tex = pi3d.Texture(im, blend = True, m_repeat = True, automatic_resize = do_resize, 
                           free_after_load = True)
    except Exception as e:
        print('''Couldn't load file {} giving error: {}'''.format(fname, e))
        tex = None
    return tex


def tidy_name(path_name):
    name = os.path.basename(path_name).upper()
    name = ''.join([c for c in name if c in CODEPOINTS])
    return name


def check_changes():
    global last_file_change
    update = False
    for root, _, _ in os.walk(PIC_DIR):
        mod_tm = os.stat(root).st_mtime
        if mod_tm > last_file_change:
            last_file_change = mod_tm
            update = True
    return update


EXIF_DATID = None  # this needs to be set before get_files() above can extract exif date info
EXIF_ORIENTATION = None
for k in ExifTags.TAGS:
    if ExifTags.TAGS[k] == 'DateTimeOriginal':
        EXIF_DATID = k
    if ExifTags.TAGS[k] == 'Orientation':
        EXIF_ORIENTATION = k

DISPLAY = pi3d.Display.create(x = 0, y = 0, frames_per_second = FPS, 
                              display_config = pi3d.DISPLAY_CONFIG_HIDE_CURSOR, background = BACKGROUND)
print('Display W: {}   H: {}'.format(DISPLAY.width, DISPLAY.height))
CAMERA = pi3d.Camera(is_3d = False)
print('OpenGL ID: {}'.format(DISPLAY.opengl.gl_id))
shader = pi3d.Shader(os.path.abspath(
    os.path.join(THIS_DIR, 'shaders', 'blend_new')))
slide = pi3d.Sprite(camera = CAMERA, w = DISPLAY.width, h = DISPLAY.height, z = 10.0)
slide.set_shader(shader)
slide.unif[47] = EDGE_ALPHA

if KEYBOARD:
    kbd = pi3d.Keyboard()

# images in iFiles list
nexttm = 0.0
pl = PLib.PicLibrary(PIC_DIR)
next_pic_num = 0
sfg = None  # slide for background
sbg = None  # slide for foreground

# PointText and TextBlock. If SHOW_NAMES is False then this is just used for no images message
# font = pi3d.Font(FONT_FILE, codepoints=CODEPOINTS, grid_size=7, shadow_radius=4.0,
#                shadow=(0,0,0,128))
# text = pi3d.PointText(font, CAMERA, max_chars=200, point_size=50)
# textblock = pi3d.TextBlock(x=-DISPLAY.width * 0.5 + 50, y=-DISPLAY.height * 0.4,
#                          z=0.1, rot=0.0, char_count=199,
#                          text_format="{}".format(" "), size=0.99,
#                          spacing="F", space=0.02, colour=(1.0, 1.0, 1.0, 1.0))
# text.add_text_block(textblock)

font = pi3d.Font(FONT_FILE, FONT_COLOUR, codepoints = list(range(32, 128)), shadow_radius=4.0, shadow=(0,0,0,128))
text = pi3d.PointText(font, CAMERA, max_chars = 250, point_size = 80)
colourGradient = pi3d.TextBlockColourGradient((1.0, 0.0, 0.0, 1.0), (0.0, 1.0, 0.0, 1.0))

dir_tb = pi3d.TextBlock(x = -DISPLAY.width * 0.5 + 50,  y = -DISPLAY.height * 0.5 + 100, z = 0.1, rot = 0.0, char_count = 100, text_format = '{:100}'.format(''),
                           size = 0.5, spacing = "F", space = 0.02, colour = colourGradient)
text.add_text_block(dir_tb)

file_tb = pi3d.TextBlock(x = -DISPLAY.width * 0.5 + 50,  y = -DISPLAY.height * 0.5 + 50, z = 0.1, rot = 0.0, char_count = 100, text_format = '{:100}'.format(''),
                           size = 0.5, spacing = "F", space = 0.02, colour = colourGradient)
text.add_text_block(file_tb)
 
title_tb = pi3d.TextBlock(x = -DISPLAY.width * 0.25,  y = DISPLAY.height * 0.5 - 50, z = 0.1, rot = 0.0, char_count = 25, text_format = 'Gills Picture Frame v1.0', 
                           size = 0.99, spacing = "F", space = 0.02, colour = colourGradient)
text.add_text_block(title_tb)


def pad(s):
    return '{:100}'.format(s)


def display_init_libupdate():
    global slide, sfg, sbg, display_state
    if os.path.isfile(BG_IMAGE):
        sfg = tex_load(BG_IMAGE, 1, (DISPLAY.width, DISPLAY.height))
        if sbg is None: # first time through
            sbg = sfg
        slide.set_textures([sfg,])
        #slide.unif[45:47] = slide.unif[42:44] # transfer front width and height factors to back
        #slide.unif[51:53] = slide.unif[48:50] # transfer front width and height offsets
        wh_rat = (DISPLAY.width * sfg.iy) / (DISPLAY.height * sfg.ix)
        if (wh_rat > 1.0 and FIT) or (wh_rat <= 1.0 and not FIT):
            sz1, sz2, os1, os2 = 42, 43, 48, 49
        else:
            sz1, sz2, os1, os2 = 43, 42, 49, 48
            wh_rat = 1.0 / wh_rat
        slide.unif[sz1] = wh_rat
        slide.unif[sz2] = 1.0
        slide.unif[os1] = (wh_rat - 1.0) * 0.5
        slide.unif[os2] = 0.0
        slide.unif[44] = 1.0
        slide.draw()
        text.draw()
    pl.update()
    display_state = DisplayState.LIBUPDATING

def display_libupdating():
    global slide, sfg, sbg, display_state
    if pl.update_thread.is_alive():
        if pl.cur_pic is None:
            dir_tb.set_text(pad(''))
            file_tb.set_text(pad('No Picture!'))
        else:
            dir_tb.set_text(pad(pl.cur_pic.pic_dir.rel_dir_name))
            file_tb.set_text(pad((pl.cur_pic.file_name)))
        text.regen()
        slide.draw()
        text.draw()
    else:
        if pl.file_cnt == 0:
            display_state = DisplayState.NOSLIDES
        else:
            # Initiise next slide
            pl.next_pic()
            # stop dislaying the Title
            title_tb.set_text('{:25}'.format(''))
            display_state = DisplayState.NEXTSLIDE


def display_noslides():
    global slide, sfg, sbg, display_state
    dir_tb.set_text(pad(''))
    file_tb.set_text(pad('No images selected!'))
    text.regen()
    slide.draw()
    text.draw()


def display_nextslide():
    global slide, sfg, sbg, display_state
    dir_tb.set_text(pad(pl.cur_pic.pic_dir.rel_dir_name))
    file_tb.set_text(pad((pl.cur_pic.file_name)))
    text.regen()
    slide.draw()
    text.draw()


class DisplayState(Enum):
    INIT_LIBUPDATE = 1
    LIBUPDATING = 2
    NOSLIDES = 3
    NEXTSLIDE = 4


def display_function(state):
    # print(state)
    switch = {
        DisplayState.INIT_LIBUPDATE: display_init_libupdate, 
        DisplayState.LIBUPDATING:    display_libupdating, 
        DisplayState.NOSLIDES:       display_noslides, 
        DisplayState.NEXTSLIDE:      display_nextslide, 
    }
    func = switch.get(state, lambda: 'Invalid')
    return func()


display_state = DisplayState.INIT_LIBUPDATE

num_run_through = 0
while DISPLAY.loop_running():
    tm = time.time()
    display_function(display_state)
    if KEYBOARD:
        k = kbd.read()
        if k != -1:
            nexttm = time.time() - 86400.0
        if k == 27 or quit:  # ESC
            break
        if k == ord(' '):
            paused = not paused
        if k == ord('s'):  # go back a picture
            next_pic_num -= 2
            if next_pic_num < -1:
                next_pic_num = -1

try:
    client.loop_stop()
except Exception as e:
    print("this was going to fail if previous try failed!")
if KEYBOARD:
    kbd.close()
DISPLAY.destroy()
