# -*- coding: utf-8 -*-

import os
from os.path import basename
import sys
import xbmc
import urllib
import urllib2
import xbmcvfs
import xbmcaddon
import xbmcgui
import xbmcplugin
import unicodedata
import chardet
import shutil
import hashlib
from httplib import HTTPConnection, OK
import struct
from cStringIO import StringIO
import zlib
import random
from urlparse import urlparse
from urlparse import urlsplit
from bs4 import BeautifulSoup
import html5lib

__addon__ = xbmcaddon.Addon()
__author__     = __addon__.getAddonInfo('author')
__scriptid__   = __addon__.getAddonInfo('id')
__scriptname__ = __addon__.getAddonInfo('name')
__version__    = __addon__.getAddonInfo('version')
__language__   = __addon__.getLocalizedString

__cwd__        = xbmc.translatePath( __addon__.getAddonInfo('path') ).decode("utf-8")
__profile__    = xbmc.translatePath( __addon__.getAddonInfo('profile') ).decode("utf-8")
__resource__   = xbmc.translatePath( os.path.join( __cwd__, 'resources', 'lib' ) ).decode("utf-8")
__temp__       = xbmc.translatePath( os.path.join( __profile__, 'temp') ).decode("utf-8")

sys.path.append (__resource__)
from langconv import *

SVP_REV_NUMBER = 1543
CLIENTKEY = "SP,aerSP,aer %d &e(\xd7\x02 %s %s"
RETRY = 3

class AppURLopener(urllib.FancyURLopener):
    version = "XBMC(Kodi)-subtitle/%s" % __version__ #cf block default ua
urllib._urlopener = AppURLopener()

def log(module, msg):
    xbmc.log((u"%s::%s - %s" % (__scriptname__,module,msg,)).encode('utf-8'),level=xbmc.LOGDEBUG )

def getShortNameByFileName(fpath):
    fpath = os.path.basename(fpath).rsplit(".",1)[0]
    fpath = fpath.lower()

    for stop in ["blueray","bluray","dvdrip","xvid","cd1","cd2","cd3","cd4","cd5","cd6","vc1","vc-1","hdtv","1080p","720p","1080i","x264","stv","limited","ac3","xxx","hddvd"]:
        i = fpath.find(stop)
        if i >= 0:
            fpath = fpath[:i]

    for c in "[].-#_=+<>,":
        fpath = fpath.replace(c, " ")

    return fpath.strip()

def getShortName(fpath):
    for i in range(3):
        shortname = getShortNameByFileName(os.path.basename(fpath))
        if not shortname:
            fpath = os.path.dirname(fpath)
        else:
            return shortname

class Package(object):
    def __init__(self, s):
        self.parse(s)
    def parse(self, s):
        c = s.read(1)
        self.SubPackageCount = struct.unpack("!B", c)[0]
        log(sys._getframe().f_code.co_name, "SubPackageCount: %d" % (self.SubPackageCount))
        self.SubPackages = []
        for i in range(self.SubPackageCount):
            try:
                sub = SubPackage(s)
            except:
                break
            self.SubPackages.append(sub)

class SubPackage(object):
    def __init__(self, s):
        self.parse(s)
    def parse(self, s):
        c = s.read(8)
        self.PackageLength, self.DescLength = struct.unpack("!II", c)
        self.DescData = s.read(self.DescLength)
        c = s.read(5)
        self.FileDataLength, self.FileCount = struct.unpack("!IB", c)
        self.Files = []
        for i in range(self.FileCount):
            file = SubFile(s)
            self.Files.append(file)

class SubFile(object):
    def __init__(self, s):
        self.parse(s)
    def parse(self, s):
        c = s.read(8)
        self.FilePackLength, self.ExtNameLength = struct.unpack("!II", c)
        self.ExtName = s.read(self.ExtNameLength)
        c = s.read(4)
        self.FileDataLength = struct.unpack("!I", c)[0]
        self.FileData = s.read(self.FileDataLength)
        if self.FileData.startswith("\x1f\x8b"):
            d = zlib.decompressobj(16+zlib.MAX_WBITS)
            self.FileData = d.decompress(self.FileData)

def getSubByTitle(title, langs):
    subtitles_list = []
    url = 'http://sub.makedie.me/sub/?searchword=%s&utm_source=xbmc&utm_medium=xbmc&utm_campaign=search' % title
    socket = urllib.urlopen( url )
    data = socket.read()
    soup = BeautifulSoup(data, 'html5lib')
    socket.close()
    results = soup.find_all("div", attrs={"class":"subitem"})
    for it in results:
            name = it.find("a", attrs={"class":"introtitle"})['title'].encode('utf-8').strip()
            href = it.find("a", attrs={"class":"introtitle"})['href']
            subtype = re.findall("格式：\s*([^\(]+)(?:\(\?\))*".decode('utf-8'), it.ul.li.text.strip())
            if subtype and subtype[0] and subtype[0]!=u'\u4e0d\u660e':#不明
                name = '[' + subtype[0].encode('utf-8') + '] ' + name
            rating = str(int(it.ul.img['src'].split('/')[-1].split('.')[0])/20)
            match = it.find(text=re.compile("语言：".decode('utf-8')))
            if match:
                match = match.encode('utf-8')
            else:
                match = ''

            xmlhref = "http://sub.makedie.me" + href
            xmlhref = urllib.quote(xmlhref)

            if 'chi' in langs:
                if '简' in match or '繁' in match or '双语' in match:
                    subtitles_list.append({"language_name":"Chinese", "filename":name, "xmlhref": xmlhref, "language_flag":'zh', "rating":rating})
                else:
                    subtitles_list.append({"language_name":"", "filename":name, "xmlhref": xmlhref, "language_flag":'zh', "rating":rating})#default to chinese
            elif 'eng' in langs and '英' in match:
                subtitles_list.append({"language_name":"English", "filename":name, "xmlhref": xmlhref, "language_flag":'en', "rating":rating})

    if subtitles_list:
        for it in subtitles_list:
            listitem = xbmcgui.ListItem(label=it["language_name"],
                                  label2=it["filename"],
                                  iconImage=it["rating"],
                                  thumbnailImage=it["language_flag"]
                                  )
            listitem.setProperty( "sync", "false" )
            listitem.setProperty( "hearing_imp", "false" )
            url = "plugin://%s/?action=download&xmlhref=%s" % (__scriptid__, it["xmlhref"])
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=url,listitem=listitem,isFolder=False)

def Search(item):
    try: shutil.rmtree(__temp__)
    except: pass
    try: os.makedirs(__temp__)
    except: pass

    if item['mansearch']:
        title = item['mansearchstr']
        getSubByTitle(title, item['3let_language'])
    else:
        title = '%s %s' % (item['title'], item['year'])
        getSubByTitle(title, item['3let_language'])#use shooter fake

def ChangeFileEndcoding(filepath):
    if __addon__.getSetting("transUTF8") == "true" and os.path.splitext(filepath)[1] in [".srt", ".ssa", ".ass", ".smi"]:
        data = open(filepath, 'rb').read()
        enc = chardet.detect(data)['encoding']
        if enc:
            data = data.decode(enc, 'ignore')
            if __addon__.getSetting("transJianFan") == "1":   # translate to Simplified
                data = Converter('zh-hans').convert(data)
            elif __addon__.getSetting("transJianFan") == "2": # translate to Traditional
                data = Converter('zh-hant').convert(data)
            data = data.encode('utf-8', 'ignore')
        try:
            local_file_handle = open(filepath, "wb")
            local_file_handle.write(data)
            local_file_handle.close()
        except:
            log(sys._getframe().f_code.co_name, "Failed to save subtitles to '%s'" % (filename))

def Download(filename):
    subtitle_list = []
    ChangeFileEndcoding(filename.decode('utf-8'))
    subtitle_list.append(filename)
    return subtitle_list

def CheckSubList(files):
    list = []
    for subfile in files:
        if os.path.splitext(subfile)[1] in [".srt", ".ssa", ".ass", ".smi", ".sub"]:
            list.append(subfile)
    return list

def DownloadID(url):
    try: shutil.rmtree(__temp__)
    except: pass
    try: os.makedirs(__temp__)
    except: pass

    subtitle_list = []
    url = urllib.unquote(url)
    socket = urllib2.urlopen( url )
    data = socket.read()
    socket.close()

    soup = BeautifulSoup(data)
    href = soup.find(id="btn_download")['href']

    url= ('http://sub.makedie.me%s' % href)
    socket = urllib.urlopen( url )
    data = socket.read()
    socket.close()

    zipname = urllib.unquote(os.path.basename(url))
    zip = os.path.join( __temp__, zipname)
    with open(zip, "wb") as subFile:
        subFile.write(data)
    subFile.close()
    xbmc.sleep(500)

    if data[:4] == 'Rar!' or data[:2] == 'PK':
        xbmc.executebuiltin(('XBMC.Extract("%s","%s")' % (zip,__temp__,)).encode('utf-8'), True)

    path = __temp__
    dirs, files = xbmcvfs.listdir(path)
    list = CheckSubList(files)
    if not list and len(dirs) > 0:
        path = os.path.join(__temp__, dirs[0].decode('utf-8'))
        dirs, files = xbmcvfs.listdir(path)
        list = CheckSubList(files)
    if list:
        filename = list[0].decode('utf-8')
    else:
        filename = ''
    if len(list) > 1:
        dialog = xbmcgui.Dialog()
        sel = dialog.select(__language__(32006), list)
        if sel != -1:
            filename = list[sel].decode('utf-8')
    if filename:
        filepath = os.path.join(path, filename)
        ChangeFileEndcoding(filepath)
        subtitle_list.append(filepath)

    return subtitle_list

def get_params():
    param=[]
    paramstring=sys.argv[2]
    if len(paramstring)>=2:
        params=paramstring
        cleanedparams=params.replace('?','')
        if (params[len(params)-1]=='/'):
            params=params[0:len(params)-2]
        pairsofparams=cleanedparams.split('&')
        param={}
        for i in range(len(pairsofparams)):
            splitparams={}
            splitparams=pairsofparams[i].split('=')
            if (len(splitparams))==2:
                param[splitparams[0]]=splitparams[1]

    return param

params = get_params()
if params['action'] == 'search' or params['action'] == 'manualsearch':
    item = {}
    item['temp']               = False
    item['rar']                = False
    item['mansearch']          = False
    item['year']               = xbmc.getInfoLabel("VideoPlayer.Year")                           # Year
    item['season']             = str(xbmc.getInfoLabel("VideoPlayer.Season"))                    # Season
    item['episode']            = str(xbmc.getInfoLabel("VideoPlayer.Episode"))                   # Episode
    item['tvshow']             = xbmc.getInfoLabel("VideoPlayer.TVshowtitle")   # Show
    item['title']              = xbmc.getInfoLabel("VideoPlayer.OriginalTitle") # try to get original title
    item['file_original_path'] = urllib.unquote(xbmc.Player().getPlayingFile().decode('utf-8'))  # Full path of a playing file
    item['3let_language']      = []

    if 'searchstring' in params:
        item['mansearch'] = True
        item['mansearchstr'] = params['searchstring']

    for lang in urllib.unquote(params['languages']).decode('utf-8').split(","):
        item['3let_language'].append(xbmc.convertLanguage(lang,xbmc.ISO_639_2))

    if item['title'] == "":
        item['title'] = xbmc.getInfoLabel("VideoPlayer.Title")                       # no original title, get just Title
        if item['title'] == os.path.basename(xbmc.Player().getPlayingFile()):         # get movie title and year if is filename
            title, year = xbmc.getCleanMovieTitle(item['title'])
            item['title'] = title.replace('[','').replace(']','')
            item['year'] = year

    if item['episode'].lower().find("s") > -1:                                        # Check if season is "Special"
        item['season'] = "0"                                                          #
        item['episode'] = item['episode'][-1:]

    if ( item['file_original_path'].find("http") > -1 ):
        item['temp'] = True

    elif ( item['file_original_path'].find("rar://") > -1 ):
        item['rar']  = True
        item['file_original_path'] = os.path.dirname(item['file_original_path'][6:])

    elif ( item['file_original_path'].find("stack://") > -1 ):
        stackPath = item['file_original_path'].split(" , ")
        item['file_original_path'] = stackPath[0][8:]

    Search(item)

elif params['action'] == 'download':
    if 'xmlhref' in params:
        subs = DownloadID(params["xmlhref"])
    else:
        subs = Download(params["filename"])
    for sub in subs:
        listitem = xbmcgui.ListItem(label=sub)
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=sub,listitem=listitem,isFolder=False)

xbmcplugin.endOfDirectory(int(sys.argv[1]))
