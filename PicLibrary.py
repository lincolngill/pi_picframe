#!/usr/bin/python3

import os
import logging
from pathlib import Path
from enum import Enum
import re
from threading import Thread
import time
import random

log = logging.getLogger(__name__)

SRC_DIR = '/media/links/SAMSUNG/Pictures'

# Default PicLibrary regx setting
PATH_REGXS = {
    'inc_dirs': [
        r'.*',
    ],
    'exc_dirs': [
    ],
    'inc_files': [
        r'.*\.(jpg|png|jpeg)$',
    ],
    'exc_files': [
        r'.*- ?Copy\.',
        r'.*\(\d+\)\.',
        r'.*-\d+\.',
    ]
}

class PathStatus(Enum):
    INCLUDE = 1
    EXCLUDE = 2
    SKIP = 3

class PicDir():
    '''
    A relative directory name and an array of PicFile objects in the directory
    '''
    def __init__(self, rel_dir_name):
        self.rel_dir_name = rel_dir_name
        self.pic_files = []
        self.file_cnt = 0

    def add_file(self, fname):
        new_pic_file = PicFile(self,fname)
        self.pic_files.append(new_pic_file)
        self.file_cnt = len(self.pic_files)
        return new_pic_file

class PicFile():
    '''
    A base file name and a referrence back to the PicDir instance of the directory it's in 
    '''
    def __init__(self, pic_dir, fname):
        self.file_name = fname
        self.pic_dir = pic_dir
        time.sleep(0.0001)

class PicLibrary ():
    '''
    Class to hold a list of included PicDir directories and PicFile files
    The library is a two way linked list. PicDir objects have a list of PicFile objects
    Each PicFile object has a reference back to it's PicDir object.
    This allows navigating the library via directories or by individual files.
    '''

    def __status(self, path, regx_prefix, inc_regx_list, exc_regx_list, file_cnt=1):
        '''
        Determine include/Exclude status of path
        '''
        for inc_regx in inc_regx_list:
            if re.match(regx_prefix+inc_regx, path, re.IGNORECASE):
                for exc_regx in exc_regx_list:
                    if re.match(regx_prefix+exc_regx, path, re.IGNORECASE):
                        path_status = PathStatus.EXCLUDE
                        log.debug('%-7s %-120s %s %s' %(path_status.name, path, exc_regx, file_cnt))
                        return path_status
                path_status = PathStatus.INCLUDE
                log.debug('%-7s %-120s %s %s' %(path_status.name, path, inc_regx, file_cnt))
                return path_status
        path_status = PathStatus.SKIP
        log.debug('%-7s %-120s %s' %(path_status.name, path, file_cnt))
        return path_status

    def get_file_list(self, shuffle):
        '''
        Generate a list of included PicDir directories and PicFile files, based on a set of include/exclude regular expressions
        '''
        log.info('Directory Scan: %s' % self.src_dir)
        self.pic_dirs = []
        self.pic_files = []
        self.file_cnt = 0
        self.dir_cnt = 0
        self.cur_pos = -1
        for dirpath, __dirnames, filenames in sorted(os.walk(self.src_dir)):
            src_dir_prefix = self.src_dir+'/'
            path_status = self.__status(dirpath, src_dir_prefix, self.path_regxs['inc_dirs'], self.path_regxs['exc_dirs'], len(filenames))
            if path_status == PathStatus.INCLUDE:
                rel_dir_path = dirpath.lstrip(src_dir_prefix)
                cur_pic_dir = PicDir(rel_dir_path)
                for fname in sorted(filenames):
                    file_status = self.__status(fname, '', self.path_regxs['inc_files'], self.path_regxs['exc_files'])
                    if file_status == PathStatus.INCLUDE:
                        self.cur_pic = cur_pic_dir.add_file(fname)
                        self.pic_files.append(self.cur_pic)
                        self.file_cnt += 1
                if cur_pic_dir.file_cnt > 0:
                    self.pic_dirs.append(cur_pic_dir)
                    self.dir_cnt += 1
        self.dir_cnt = len(self.pic_dirs)
        self.file_cnt = len(self.pic_files)
        if shuffle:
            random.shuffle(self.pic_files)

    def update(self,shuffle=True):
        self.update_thread = Thread(name='PicLibrary update', target=self.get_file_list, args=(shuffle,))
        self.update_thread.start()

    def __init__(self, src_dir, path_regxs=PATH_REGXS):
        self.src_dir = src_dir
        # Take defaults and merge in whatever is past in as argument.
        # So you can pass in a partial regx config
        self.path_regxs = PATH_REGXS
        self.path_regxs.update(path_regxs)
        self.cur_pic = None
        self.pic_dirs = []
        self.pic_files = []
        self.cur_pos = -1
        self.file_cnt = 0
        self.dir_cnt = 0

    def next_pic(self):
        if self.file_cnt == 0:
            return None
        self.cur_pos += 1
        if self.cur_pos >= self.file_cnt:
            self.cur_pos = 0
        self.cur_pic = self.pic_files[self.cur_pos]
        return self.cur_pic
        
    def dump_dirs(self):
        '''
        Dump the picture library structure to the log/console. Navigated from the PicDir list
        '''
        log.info('Dump Dirs for: %-120s   %s' % (self.src_dir, self.dir_cnt))
        for d in self.pic_dirs:
            log.info('   %-120s   %s' % (d.rel_dir_name, d.file_cnt))
            for f in d.pic_files:
                log.info('      %s' % f.file_name)
                pass

    def dump_files(self):
        '''
        Dump the picture library strucutre to the log/console. Navigate from the PicFile list
        '''
        log.info('Dump Files for: %-120s   %s' % (self.src_dir, self.file_cnt))
        for f in self.pic_files:
            log.info('   %-120s %s' % (f.pic_dir.rel_dir_name, f.file_name))

def main():
    log.info('Start')
    pic_lib = PicLibrary(SRC_DIR)
    #pic_lib.dump_dirs()
    #pic_lib.dump_files()
    log.info('Total Files: %s' % pic_lib.file_cnt)
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
    log.info(prog_name)
    main()
