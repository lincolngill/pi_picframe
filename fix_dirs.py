#!/usr/bin/python3

import os
import logging
from pathlib import Path
import shutil

SRC_DIR = '/media/links/SAMSUNG/Pictures'

DIR_MV = {
    '18-09-2011': '2011-09-18 Emmas fashion and party pics',
    '18-09-2011(1)': '2011-09-18 Sports & Emmas ball gown',
    '2013-03-26': '2013-03-26 Dragon Boating',
    '2013-11': '2013-11 Rachels 15th birthday',
    '2014-02-02 Nexus': '2014-02-02 Nexus Panarama',
    '2015-07-03 001': '2015-07-03 Fiji underwater',
    '2017-01-27 White Water Rafting/2018-01 Chch Xmas Ohope Rotoma/2018 Ohope Rotoma/2016-04': '2016-04 Pets',
    '2017-01-27 White Water Rafting/2018-01 Chch Xmas Ohope Rotoma/2018 Ohope Rotoma/2014-12': '2018-01 Ohope Holiday',
    '2018-11-28': '2018-11-28 xmas 2017 Ohope Rotoma',
    '25-12-2012': '2012-12-25 textures',
    '26-03-2012 hayden cookin with bob marly': '2012-03-02 hayden cookin with bob marly',
    '31-03-2012': '2012-03-31 Waterpolo and Emma and Mary',
}

DIR_RM = [
    '2015-04 Ruby/New folder',
    '2015-07-03 002',
    '2017-01-27 White Water Rafting/2018-01 Chch Xmas Ohope Rotoma',
    'rons photos/New Folder',
    'Nana/New folder',
    'EMMA/New folder',
]

def move_dirs():
    log.info('Dir move...')
    for src_dir_name in DIR_MV.keys():
        src_dir = os.path.join(SRC_DIR, src_dir_name)
        dst_dir = os.path.join(SRC_DIR, DIR_MV[src_dir_name])
        if not os.path.isdir(src_dir):
            log.warning('Src does not exist: %s' % src_dir)
            continue
        if os.path.exists(dst_dir):
            log.error('Dst exists: %s' % dst_dir)
            continue
        log.info('MV %-130s %-130s' % (src_dir, dst_dir))
        try:
            os.rename(src_dir, dst_dir)
            pass
        except:
            log.critical('MV Failed: %s' % src_dir)
            exit(1)

def del_dirs():
    log.info('Dir delete...')
    for src_dir_name in DIR_RM:
        src_dir = os.path.join(SRC_DIR, src_dir_name)
        if not os.path.isdir(src_dir):
            log.warning('Src does not exist: %s' % src_dir)
            continue
        path_cnt = len(os.listdir(src_dir))
        log.info('RM %-130s   %s' % (src_dir, path_cnt))
        try:
            shutil.rmtree(src_dir)
            pass
        except:
            log.critical('RM Failed: %s' % src_dir)
            exit(1)

def main():
    log.info('Start')
    #move_dirs()
    del_dirs()
    log.info('End')

if __name__ == "__main__":
    # setup logging
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s', 
        datefmt='%Y-%m-%d_%H:%M:%S', 
        level=logging.DEBUG
        )
    prog_name = Path(__file__).stem
    log = logging.getLogger(name=prog_name)
    main()