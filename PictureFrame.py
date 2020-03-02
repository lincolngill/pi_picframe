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
from Slide import Slide
from threading import Thread

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

DISPLAY = pi3d.Display.create(x = 0, y = 0, frames_per_second = FPS, 
                              display_config = pi3d.DISPLAY_CONFIG_HIDE_CURSOR, background = BACKGROUND)
print('Display W: {}   H: {}'.format(DISPLAY.width, DISPLAY.height))
CAMERA = pi3d.Camera(is_3d = False)
print('OpenGL ID: {}'.format(DISPLAY.opengl.gl_id))
slide = Slide(DISPLAY, CAMERA, shader_path=os.path.join(THIS_DIR, 'shaders', 'blend_new'), edge_alpha=EDGE_ALPHA)

if KEYBOARD:
    kbd = pi3d.Keyboard()

# images in iFiles list
nexttm = 0.0
pl = PLib.PicLibrary(PIC_DIR)
next_pic_num = 0

font = pi3d.Font(FONT_FILE, FONT_COLOUR, codepoints = list(range(32, 128)), shadow_radius=4.0, shadow=(0,0,0,128))
text = pi3d.PointText(font, CAMERA, max_chars = 250, point_size = 80)
colourGradient = pi3d.TextBlockColourGradient((1.0, 0.0, 0.0, 1.0), (0.0, 1.0, 0.0, 1.0))

dir_tb = pi3d.TextBlock(x = DISPLAY.width * -0.5 + 50,  y = DISPLAY.height * -0.5 + 100, z = 0.1, rot = 0.0, char_count = 100, text_format = '{:100}'.format(''),
                           size = 0.5, spacing = "F", space = 0.02, colour = colourGradient)
text.add_text_block(dir_tb)

file_tb = pi3d.TextBlock(x = DISPLAY.width * -0.5 + 50,  y = DISPLAY.height * -0.5 + 50, z = 0.1, rot = 0.0, char_count = 100, text_format = '{:100}'.format(''),
                           size = 0.5, spacing = "F", space = 0.02, colour = colourGradient)
text.add_text_block(file_tb)
 
title_tb = pi3d.TextBlock(x = DISPLAY.width * -0.25,  y = DISPLAY.height * 0.5 - 50, z = 0.1, rot = 0.0, char_count = 25, text_format = '{:25}'.format(''),
                           size = 0.99, spacing = "F", space = 0.02, colour = colourGradient)
text.add_text_block(title_tb)

date_tb = pi3d.TextBlock(x = DISPLAY.width * 0.5 -340,  y = DISPLAY.height * -0.5 + 50, z = 0.1, rot = 0.0, char_count = 15, text_format = '{:15}'.format(''),
                           size = 0.5, spacing = "F", space = 0.02, colour = colourGradient)
text.add_text_block(date_tb)


def pad(s):
    return '{:100}'.format(s)

def process_thread(display_elements, time_delay=10, trans_secs=3):
    global slide, run_proc
    try:
        run_proc = True
        slide.load_image(BG_IMAGE)
        display_elements.append(slide)
        display_elements.append(text)
        #for __i in range(2):
        while run_proc:
            slide.load_image(BG_IMAGE)
            title_tb.set_text('{:25}'.format('Gills Picture Frame v1.1'))
            date_tb.set_text('{:15}'.format(''))
            dir_tb.set_text(pad(''))
            file_tb.set_text(pad(''))
            text.regen()
            pl.update()
            while pl.update_thread.is_alive():
                if pl.cur_pic is None:
                    dir_tb.set_text(pad(''))
                    file_tb.set_text(pad('No Picture!'))
                else:
                    dir_tb.set_text(pad(pl.cur_pic.pic_dir.rel_dir_name))
                    file_tb.set_text(pad((pl.cur_pic.file_name)))
                text.regen()
                time.sleep(0.05)
            if pl.file_cnt == 0:
                dir_tb.set_text(pad(''))
                file_tb.set_text(pad('No images selected!'))
                text.regen()
                while run_proc: # go to sleep
                    time.sleep(10)
                return
            title_tb.set_text('{:25}'.format(''))
            text.regen()
            piclist = iter(pl.pic_files)
            slide.load_next_image(pl.src_dir, piclist) # prime first image
            while run_proc and slide.next_pic is not None:
                slide.transition_to_next(trans_secs=trans_secs)
                slide.start_load_next_image(pl.src_dir, piclist)
                dir_tb.set_text(pad(slide.fg_pic.rel_dir_name))
                file_tb.set_text(pad(slide.fg_pic.fname))
                date_tb.set_text(time.strftime("%a %d %b %Y", time.localtime(slide.fg_pic.dt)))
                text.regen()
                time.sleep(time_delay)
                # Wait (if required) for next image to load
                slide.load_thread.join()
    except KeyboardInterrupt:
        print ('Bye')
        return

display_elements = []
run_proc = True
proc_thread = Thread(target=process_thread, args=(display_elements, time_delay, fade_time))
proc_thread.start()

# Main thread
while DISPLAY.loop_running() and proc_thread.is_alive():
    for e in display_elements:
        e.draw()
    if KEYBOARD:
        k = kbd.read()
        if k != -1:
            nexttm = time.time() - 86400.0
        if k == 27 or quit:  # ESC
            run_proc = False
            break
        if k == ord(' '):
            paused = not paused

if KEYBOARD:
    kbd.close()
DISPLAY.destroy()