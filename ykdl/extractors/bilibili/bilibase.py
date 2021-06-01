#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ykdl.extractor import VideoExtractor
from ykdl.videoinfo import VideoInfo
from ykdl.util.html import get_content, fake_headers
from ykdl.util.match import match1, matchall
from ykdl.compact import compact_bytes

import hashlib
import json


def sign_api_url(api_url, params_str, skey):
    chksum = hashlib.md5(compact_bytes(params_str + skey, 'utf8')).hexdigest()
    return '{}?{}&sign={}'.format(api_url, params_str, chksum)

def parse_cid_playurl(xml):
    urls = []
    size = 0
    doc = json.loads(xml)["data"]
    
    fmt = doc["format"]
    qlt = doc["quality"]
    if fmt == 'hdflv2' and qlt == 120:
        fmt = 'flv4k'
    aqlts = doc["accept_quality"]
    for durl in doc["durl"]:
        urls.append(durl["url"])
        size += int(durl["size"])
    return urls, size, fmt, qlt, aqlts

class BiliBase(VideoExtractor):
    format_2_type_profile = {
        'flv4k' : ('QHD', u'高清 4K'), #120
        'flv_p60': ('F60',u'高清 1080P60'), #116
        'hdflv2': ('FD', u'高清 1080P+'), #112
        'flv':    ('BD', u'高清 1080P'),  #80
        'flv720_p60': ('T60', u'高清 720P60'), #64
        'flv720': ('TD', u'高清 720P'),   #64
        'hdmp4':  ('TD', u'高清 720P'),   #48
        'flv480': ('HD', u'清晰 480P'),   #32
        'mp4':    ('SD', u'流畅 360P'),   #16
        'flv360': ('SD', u'流畅 360P'),   #15
        }

    sorted_format = ['QHD','F60','FD','BD','T60', 'TD', 'HD', 'SD']

    def prepare(self):
        info = VideoInfo(self.name)
        info.extra['referer'] = 'https://www.bilibili.com/'
        info.extra['ua'] = fake_headers['User-Agent']
        if fake_headers['Cookie']:
            info.extra['cookie'] = fake_headers['Cookie']

        self.bvid, self.vid, info.title, info.artist = self.get_page_info()

        assert self.vid, "can't play this video: {}".format(self.url)

        def get_video_info(qn=120):
            api_url = self.get_api_url(qn)
            html = get_content(api_url)
            self.logger.debug('HTML> ' + html)
            code = match1(html, '<code>([^<])')
            if code:
                return

            urls, size, fmt, qlt, aqlts = parse_cid_playurl(html)
            if 'mp4' in fmt:
                ext = 'mp4'
            elif 'flv' in fmt:
                ext = 'flv'
            st, prf = self.format_2_type_profile[fmt]
            if urls and st not in info.streams:
                info.stream_types.append(st)
                info.streams[st] = {'container': ext, 'video_profile': prf, 'src' : urls, 'size': size}

            if qn == 120:
                aqlts.remove(qlt)
                for aqlt in aqlts:
                    get_video_info(aqlt)

        get_video_info()

        assert len(info.stream_types), "can't play this video!!"
        info.stream_types = sorted(info.stream_types, key=self.sorted_format.index)
        return info
