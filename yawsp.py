# -*- coding: utf-8 -*-
# Module: default
# Author: cache-sk
# Created on: 10.5.2020
# License: AGPL v.3 https://www.gnu.org/licenses/agpl-3.0.html

import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import requests
from urllib import urlencode
from urlparse import parse_qsl, urlparse
from xml.etree import ElementTree as ET
import hashlib
import md5crypt
import traceback

API = 'https://webshare.cz/api/'
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36"
REALM = ':Webshare:'

_url = sys.argv[0]
_handle = int(sys.argv[1])
_addon = xbmcaddon.Addon()
_session = requests.Session()
_session.headers.update({'User-Agent': UA})


def get_url(**kwargs):
    return '{0}?{1}'.format(_url, urlencode(kwargs, 'utf-8'))

def api(fnct, data):
    print fnct
    print data
    response = _session.post(API + fnct + "/", data=data)
    print response.content
    return response

def is_ok(xml):
    status = xml.find('status').text
    return status == 'OK'

def info(message, heading=_addon.getAddonInfo('name'), icon=xbmcgui.NOTIFICATION_INFO, time=3000, sound=False): #NOTIFICATION_WARNING NOTIFICATION_ERROR
    xbmcgui.Dialog().notification(heading, message, icon, time, sound=sound)

def login():
    username = _addon.getSetting('wsuser')
    password = _addon.getSetting('wspass')
    if username == '' or password == '':
        info(_addon.getLocalizedString(30101), sound=True)
        _addon.openSettings()
        return
    response = api('salt', {'username_or_email': username})
    xml = ET.fromstring(response.content)
    if is_ok(xml):
        salt = xml.find('salt').text
        encrypted_pass = hashlib.sha1(md5crypt(password.encode('utf-8'), salt.encode('utf-8'))).hexdigest()
        pass_digest = hashlib.md5(username.encode('utf-8') + REALM + encrypted_pass.encode('utf-8')).hexdigest()
        response = api('login', {'username_or_email': username, 'password': encrypted_pass, 'digest': pass_digest, 'keep_logged_in': 1})
        xml = ET.fromstring(response.content)
        if is_ok(xml):
            token = xml.find('token').text
            _addon.setSetting('token', token)
            return token
        else:
            info(_addon.getLocalizedString(30102), icon=xbmcgui.NOTIFICATION_ERROR, sound=True)
            _addon.openSettings()
    else:
        info(_addon.getLocalizedString(30102), icon=xbmcgui.NOTIFICATION_ERROR, sound=True)
        _addon.openSettings()

def revalidate():
    token = _addon.getSetting('token')
    if len(token) == 0:
        if login():
            return revalidate()
    else:
        response = api('user_data', { 'wst': token })
        xml = ET.fromstring(response.content)
        status = xml.find('status').text
        if is_ok(xml):
            vip = xml.find('vip').text
            if vip != '1':
                info(_addon.getLocalizedString(30103), icon=xbmcgui.NOTIFICATION_WARNING)
            return token
        else:
            if login():
                return revalidate()

def get_stream_url(ident):
	token = _addon.getSetting('token')
	if len(token) == 0:
		token = login()
	if token:
		req = ws_api_request('/file_link/', { 'wst': token, 'ident': ident })
		link = ET.fromstring(req.text).find('link').text
		return link
        
def labelize(file):
    size = float(file['size'])
    if size < 1024:
        size = str(size) + 'B'
    else:
        size = size / 1024
        if size < 1024:
            size = str(int(round(size))) + 'KB'
        else:
            size = size / 1024
            if size < 1024:
                size = str(int(round(size))) + 'MB'
            else:
                size = size / 1024
                size = str(round(size,2)) + 'GB'
    return file['name'] + ' (' + size + ')'

def search(params):
    token = revalidate()
    xbmcplugin.endOfDirectory(_handle)

def queue(params):
    token = revalidate()
    response = api('queue',{'wst':token})
    xml = ET.fromstring(response.content)
    if is_ok(xml):
        for file in xml.iter('file'):
            item = {'ident':file.find('ident').text,'name':file.find('name').text,'size':int(file.find('size').text), 'img':file.find('img').text}
            listitem = xbmcgui.ListItem(label=labelize(item))
            listitem.setArt({'thumb': item['img']})
            xbmcplugin.addDirectoryItem(_handle, get_url(action='file',ident=item['ident']), listitem, True)
    xbmcplugin.endOfDirectory(_handle)

def history(params):
    token = revalidate()
    response = api('history',{'wst':token})
    xml = ET.fromstring(response.content)
    files = []
    if is_ok(xml):
        for file in xml.iter('file'):
            item = {'ident':file.find('ident').text,'name':file.find('name').text,'size':int(file.find('size').text)}
            if item not in files:
                files.append(item)
        for file in files:
            xbmcplugin.addDirectoryItem(_handle, get_url(action='file',ident=file['ident']), xbmcgui.ListItem(label=labelize(file)), True)
    xbmcplugin.endOfDirectory(_handle)
    
def settings(params):
    _addon.openSettings()
    xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())

def file(params):
    token = revalidate()
    response = api('file_info',{'ident':params['ident'],'wst': token})
    xml = ET.fromstring(response.content)
    if is_ok(xml):
        info = {'name':xml.find('name').text} #TODO
        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30211))
        #TODO
        listitem.setInfo('video', {'title': info['name']})
        listitem.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(_handle, get_url(action='play',ident=params['ident'],name=info['name']), listitem, False)
        xbmcplugin.addDirectoryItem(_handle, get_url(action='download',ident=params['ident'],name=info['name']), xbmcgui.ListItem(label=_addon.getLocalizedString(30212)), False)
    xbmcplugin.endOfDirectory(_handle)

def play(params):
    token = revalidate()
    data = {'ident':params['ident'],'wst': token}
    #response = api('file_protected',data) #protected
    #xml = ET.fromstring(response.content)
    #if is_ok(xml) and xml.find('protected').text != 0:
    #    pass #ask for password
    response = api('file_link',data)
    xml = ET.fromstring(response.content)
    if is_ok(xml):
        xbmcplugin.setResolvedUrl(_handle, True, xbmcgui.ListItem(label=params['name'],path=xml.find('link').text))
    else:
        xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())

def download(params):
    token = revalidate()
    xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())

def menu():
    revalidate()
    #xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name'))
    listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30201))
    listitem.setArt({'icon': 'DefaultAddonsSearch.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='search'), listitem, True)
    
    listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30202))
    listitem.setArt({'icon': 'DefaultPlaylist.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='queue'), listitem, True)
    
    listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30203))
    listitem.setArt({'icon': 'DefaultAddonsUpdates.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='history'), listitem, True)
    
    listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30204))
    listitem.setArt({'icon': 'DefaultAddonService.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='settings'), listitem, False)
    xbmcplugin.endOfDirectory(_handle)

def router(paramstring):
    params = dict(parse_qsl(paramstring))
    if params:
        if params['action'] == 'search':
            search(params)
        elif params['action'] == 'queue':
            queue(params)
        elif params['action'] == 'history':
            history(params)
        elif params['action'] == 'settings':
            settings(params)
        elif params['action'] == 'file':
            file(params)
        elif params['action'] == 'play':
            play(params)
        elif params['action'] == 'download':
            download(params)
        else:
            menu()
    else:
        menu()
