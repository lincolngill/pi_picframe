#!/usr/bin/python3
import logging
import logging.config
import PicLibrary as pl
import os
from shutil import copyfile
from pathlib import Path

log = logging.getLogger(__name__)

SRC_DIR = '/media/links/SAMSUNG/Pictures'
DST_DIR = '/media/links/rootfs/home/pi/Pictures'

PATH_REGXS = {
    'inc_dirs': [
        #r'2020[^/]*$',
        r'\d{4}[^/]*$',
        r'2016-10-01 Emmas Travel/Emmas Travels',
        r'2013-07-25 Hammer Springs/Quad Bikes',
    ],
    'exc_dirs': [
        r'2005-04-17 chch visit and Moeraki boulders/Originals',
        r'2008-11-16 Seattle Originals$',
        r'.*Emmas Fashion',
        r'.*Emmas egg experiments',
        r'.*Callums Assignment',
        r'.*rachels project',
        r'.*new camera testshots',
        r'.*Rachels Mould',
        r'.*Emmas Photo Assignment',
        r'2011 fashiiiooon',
        r'2004-07-26 Google pictures',
        r'2006-02-06 001$',
        r'2008-01-01 \d{3} Emmas$',
        r'2008-09-\d{2} 001$',
        r'2012-12-25 textures',
    ],
}

def main():
    prog_name = Path(__file__).stem
    logging.config.fileConfig(prog_name+'.ini', disable_existing_loggers=False)
    log.info('Start')
    pic_lib = pl.PicLibrary(SRC_DIR, PATH_REGXS)
    log.info('Total Dirs: %s   Total Files: %s' % (pic_lib.dir_cnt, pic_lib.file_cnt))
    for pic_dir in pic_lib.pic_dirs:
        dst_dir = os.path.join(DST_DIR, pic_dir.rel_dir_name)
        if not os.path.isdir(dst_dir):
            log.info('mkdir: %s' % dst_dir)
            os.makedirs(dst_dir)
    for pic_file in pic_lib.pic_files:
        src_file = os.path.join(pic_lib.src_dir, pic_file.pic_dir.rel_dir_name, pic_file.file_name)
        dst_file = os.path.join(DST_DIR, pic_file.pic_dir.rel_dir_name, pic_file.file_name)
        if os.path.exists(dst_file):
            log.warning('File Exists: %s' % dst_file)
            continue
        log.info('CP %-120s %-120s' % (src_file, dst_file))
        copyfile(src_file, dst_file)
    log.info('End')

if __name__ == "__main__":
    main()