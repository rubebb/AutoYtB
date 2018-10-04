import utitls
import time
import traceback
import os
import signal

from bilibiliProxy import BilibiliProxy
from subprocessOp import _forwardStream_sync, _getYoutube_m3u8_sync
import questInfo
from myRequests import subscribe

def bilibiliStartLive(channelId, room_title, area_id=None):
    curSub = utitls.getSubInfoWithSubChannelId(channelId)
    curBiliAccCookie = curSub['bilibili_cookiesStr']

    tmp_area_id = area_id
    if tmp_area_id == None:
        tmp_area_id = curSub['bilibili_areaid']

    b = BilibiliProxy(curBiliAccCookie)
    if b.getAccInfo() == None:
        #relogin
        from login import login
        if curSub['login_type'] == 'account':
            tmp_username, tmp_password = curSub.get('username'), curSub.get('password')
            if tmp_username and tmp_password:
                curSub['bilibili_cookiesStr'] = login(tmp_username, tmp_password)
                utitls.setSubInfoWithSubChannelId(channelId, curSub)
                bilibiliStartLive(channelId, room_title, area_id)
                return #retry the StartLive. TODO Maybe limit the retry time?

    t_room_id = b.getLiveRoomId()
    # b.stopLive(t_room_id)   #Just don't care the Live status, JUST STARTLIVE
    # b.updateRoomTitle(t_room_id, room_title) #Maybe just ignore changing the title
    rtmp_link = b.startLive(t_room_id, tmp_area_id)

    if curSub.get('auto_send_dynamic') and rtmp_link and questInfo._getObjWithRTMPLink(rtmp_link) is None:
        if curSub.get('dynamic_template'):
            b.send_dynamic(curSub['dynamic_template']).replace('${roomUrl}', 'https://live.bilibili.com/' + t_room_id)
        else:
            b.send_dynamic('转播开始了哦~')
    return b, t_room_id, rtmp_link


def Async_forwardToBilibili(channelId, link, room_title='Testing Title', area_id=None, isSubscribeQuest=True):
    utitls.runFuncAsyncThread(_forwardToBilibili_Sync, (channelId, link, room_title, area_id, isSubscribeQuest))
def _forwardToBilibili_Sync(channelId, link, room_title, area_id=None, isSubscribeQuest=True):
    resloveURLOK = False
    tmp_retryTime = 30
    while tmp_retryTime > 0:
        if 'youtube.com/' in link or 'youtu.be/' in link:
            m3u8Link, title, err, errcode = _getYoutube_m3u8_sync(link)
            if errcode == 0:
                # link = m3u8Link   #just to check is can use, _forwardStream_sync will access the title and questInfo
                resloveURLOK = True
                break
            else:
                tmp_retryTime -= 1
                time.sleep(10)
        else:
            utitls.myLogger('_forwardToBilibili_Sync LOG: Unsupport ForwardLink:' + link)
            return

    if resloveURLOK:
        b, t_room_id, rtmp_link = bilibiliStartLive(channelId, room_title, area_id)
        if rtmp_link:   #kill the old proccess
            tmp_quest = questInfo._getObjWithRTMPLink(rtmp_link)
            if tmp_quest != None:
                try:
                    os.kill(tmp_quest.get('pid', None), signal.SIGKILL)
                except Exception:
                    utitls.myLogger(traceback.format_exc())
                questInfo.removeQuest(rtmp_link)
            # force stream
            _forwardStream_sync(link, rtmp_link, isSubscribeQuest)



def Async_subscribeTheList():
    utitls.runFuncAsyncThread(subscribeTheList_sync, ())
def subscribeTheList_sync():
    time.sleep(10)   #wait the server start preparing
    while True:
        subscribeList = utitls.configJson().get('subscribeList', [])
        ip = utitls.configJson().get('serverIP')
        port = utitls.configJson().get('serverPort')
        for item in subscribeList:
            tmp_subscribeId = item.get('youtubeChannelId', "")
            if tmp_subscribeId != "":
                port = '' if port == '80' else ':' + port
                tmp_callback_url = 'http://' + ip + port + '/subscribe'
                subscribe(tmp_callback_url, tmp_subscribeId)
        time.sleep(3600 * 24 * 4)   #update the subscribe every 4 Days
