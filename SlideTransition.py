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
import PicLibrary as PLib

#from six_mod.moves import queue
import queue

# these are needed for getting exif data from images
from PIL import Image, ExifTags, ImageFilter

PATH_REGXS = {
    'inc_dirs': [
        r'2020.*',
    ],
}

THIS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
FONT_FILE = os.path.join(THIS_DIR, 'fonts', 'NotoSans-Regular.ttf')

PIC_DIR = '/home/pi/Pictures'
FPS = 20
FIT = True
EDGE_ALPHA = 0.5  # see background colour at edge. 1.0 would show reflection of image
BACKGROUND = (0.2, 0.2, 0.2, 1.0)
BG_IMAGE = os.path.join(THIS_DIR, 'background.jpg')
FONT_COLOUR = (255, 255, 255, 255)

NUM_SLIDES = 8
TIME_DELAY = 6.0
FADE_TIME = 3.0

LOGGER = pi3d.Log(__name__, level='INFO', format='%(asctime)s %(levelname)-8s %(message)s')
LOGGER.info('#########################################################')
LOGGER.info('press ESC to escape, S to go back, any key for next slide')
LOGGER.info('#########################################################')

# Setup display and initialise pi3d
DISPLAY = pi3d.Display.create(x=0, y=0, frames_per_second=FPS,
                              display_config=pi3d.DISPLAY_CONFIG_HIDE_CURSOR, background=BACKGROUND)
LOGGER.info('Display W: {}   H: {}'.format(DISPLAY.width, DISPLAY.height))
LOGGER.info('OpenGL ID: {}'.format(DISPLAY.opengl.gl_id))
#CAMERA = pi3d.Camera.instance()
CAMERA = pi3d.Camera(is_3d = False)
shader = [
    #    pi3d.Shader(os.path.join(THIS_DIR, "shaders", "blend_new")),
    pi3d.Shader(os.path.join(THIS_DIR, "shaders", "blend_holes")),
    pi3d.Shader(os.path.join(THIS_DIR, "shaders", "blend_false")),
    pi3d.Shader(os.path.join(THIS_DIR, "shaders", "blend_burn")),
    pi3d.Shader(os.path.join(THIS_DIR, "shaders", "blend_bump"))
]

fileQ = queue.Queue()  # queue for loading new texture files

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
            im = Image.open(slide.path)
            # this will convert to RGBA and set alpha to opaque
            im.putalpha(255)
            slide.orientation = 1
            if EXIF_DATID is not None and EXIF_ORIENTATION is not None:
                try:
                    exif_data = im._getexif()
                    if exif_data is not None:
                        if exif_data[EXIF_DATID] != '0000:00:00 00:00:00':
                            slide.dt = time.mktime(time.strptime(exif_data[EXIF_DATID], '%Y:%m:%d %H:%M:%S'))
                        else:
                            slide.dt = os.path.getmtime(slide.path)
                        slide.orientation = int(exif_data[EXIF_ORIENTATION])
                except Exception as e:  # NB should really check error here but it's almost certainly due to lack of exif data
                    LOGGER.warning('exif read error. File: {} Error: {}'.format(slide.path, e))
                    # so use file last modified date
                    slide.dt = os.path.getmtime(slide.path)
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
            slide.state = 'Loaded'
        except Exception as e:
            LOGGER.error("Failed to load. File: {} Error: {}".format(slide.path, e))
            slide.error = True
            slide.state = 'Error'
        slide.log_debug()
        fileQ.task_done()


class Slide(object):
    def reset(self, path=None, pfile=None):
        # Set path from pfile if required.
        if path is None and pfile is not None:
            self.path = os.path.join(PIC_DIR, pfile.pic_dir.rel_dir_name, pfile.file_name)
        else:
            self.path = path
        # create pfile from path if required
        if pfile is None and self.path is not None:
            pd = PLib.PicDir(os.path.relpath(os.path.dirname(self.path), PIC_DIR))
            self.pfile = pd.add_file(os.path.basename(self.path))
        else:
            self.pfile = pfile
        self.dir_name = self.pfile.pic_dir.rel_dir_name
        self.fname = self.pfile.file_name
        self.tex = None
        self.dimensions = None
        self.orientation = 1
        self.dt = None
        self.error = False
        self.shader = random.choice(shader)
        self.state = 'Reset'
        self.log_debug()

    def __init__(self, path=None, pfile=None, buf_num=None):
        self.buf_num = buf_num
        self.reset(path, pfile)

    def log_debug(self):
        LOGGER.debug('{} {} {}'.format(self.buf_num, self.state, self.path))

class Frame(pi3d.Canvas):
    def __init__(self, slide, fade=1.0):
        super(Frame, self).__init__()
        if slide.error:
            LOGGER.warning('Slide {} no good for creating Frame'.format(slide.path))
        else:
            self.set_tex(slide, fade=fade)

    def set_fade(self, fade):
        if fade > 1.0:
            fade = 1.0
        self.fade = fade
        self.unif[44] = fade

    def inc_fade(self, fade_step):
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
    def __init__(self, piclist, frame, nSli=NUM_SLIDES):
        self.iFiles = piclist
        self.nFi = len(self.iFiles)
        self.nSli = nSli
        self.slides = []
        for i in range(self.nSli):
            s = Slide(pfile=self.iFiles[i % self.nFi], buf_num=i)
            self.slides.append(s)
            fileQ.put(s)
        self.focus = self.nSli - 1
        self.focus_fi = self.nFi - 1
        self.frame = frame

    def next(self, step=1):
        sfg = self.slides[self.focus]  # foreground
        self.focus = (self.focus + step) % self.nSli
        self.focus_fi = (self.focus_fi + step) % self.nFi
        self.sbg = self.slides[self.focus]  # background
        self.sbg.state = self.sbg.state+' B'
        self.sbg.log_debug()
        self.frame.set_tex(self.sbg, sfg)
        # get thread to put one in end of pipe
        s = self.slides[(self.focus + int(0.5 - 4.5 * step)) % self.nSli]
        s.reset(pfile=self.iFiles[(self.focus_fi + int(0.5 + 3.5 * step)) % self.nFi])
        fileQ.put(s)
        # fileQ.join()

    def prev(self):
        self.next(step=-1)

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

t = threading.Thread(target=tex_load)
t.daemon = True
t.start()

# Fetch key presses
mykeys = pi3d.Keyboard()
CAMERA.was_moved = False  # to save a tiny bit of work each loop

pl = PLib.PicLibrary(src_dir=PIC_DIR, path_regxs=PATH_REGXS)
#pl = PLib.PicLibrary(src_dir=PIC_DIR)

def process_thread(time_delay=10, trans_secs=3):
    global pl, run_proc, display_elements
    try:
        run_proc = True
        frame_sleep = 1.0/FPS
        fade_inc = frame_sleep/trans_secs
        #for __i in range(2):
        while run_proc:
            # Splash background image
            bg = Slide(path=BG_IMAGE)
            fileQ.put(bg)
            fileQ.join() # wait for load to complete
            frame = Frame(bg)
            text_attr.status = 'No Pictures!'
            status_pt.regen()
            display_elements = [frame, title_pt, status_pt]
            # Update pic library list
            pl.update()
            while pl.update_thread.is_alive():
                if pl.cur_pic is not None:
                    text_attr.dir = pl.cur_pic.pic_dir.rel_dir_name
                    text_attr.fname = pl.cur_pic.file_name
                    file_pt.regen()
                    display_elements = [frame, title_pt, file_pt]
                time.sleep(frame_sleep)
            # No pictures found
            if pl.file_cnt == 0:
                text_attr.status = 'No images selected!'
                status_pt.regen()
                display_elements = [frame, title_pt, status_pt]
                while run_proc: # go to sleep
                    time.sleep(10)
                return
            # Create slide carousel
            text_attr.status = 'Buffering Slides...'
            status_pt.regen()
            display_elements = [frame, title_pt, status_pt]
            crsl = Carousel(pl.pic_files, frame)
            fileQ.join() # wait for slides to load
            # Start with first 
            display_elements = [frame]
            crsl.next()
            frame.set_fade(1.0)
            display_elements = [frame, file_pt, status_pt]
            while run_proc:
                text_attr.dir = crsl.sbg.dir_name
                text_attr.fname = crsl.sbg.fname
                text_attr.date = time.strftime("%a %d %b %Y", time.localtime(crsl.sbg.dt))
                file_pt.regen()
                text_attr.status = '{} {} {}'.format(crsl.sbg.buf_num, crsl.sbg.state, crsl.sbg.orientation)
                status_pt.regen()
                # transistion to background slide
                while run_proc and frame.fade < 1.0:
                    time.sleep(frame_sleep)
                    frame.inc_fade(fade_inc)
                time.sleep(time_delay)
                # switch bg to fg and load new bg with fade = 0.0
                crsl.next()
                # Wrapped back to start of file list
                if crsl.focus_fi == 0:
                    break
    except KeyboardInterrupt:
        return

display_elements = []
run_proc = True
proc_thread = threading.Thread(target=process_thread, args=(TIME_DELAY, FADE_TIME,))
proc_thread.start()

#time.sleep(15)
try:
    while DISPLAY.loop_running() and proc_thread.is_alive():
        for e in display_elements:
            e.draw()

        k = mykeys.read()
        #k = -1
        if k > -1:
            if k == 27:  # ESC
                break
finally:
    LOGGER.info('Stopping...')
#    time.sleep(60)
    DISPLAY.stop()
    run_proc = False
    proc_thread.join()
    mykeys.close()
    DISPLAY.destroy()
    LOGGER.info('Bye')
