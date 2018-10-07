from time import sleep
import requests
import re
import subprocess
import threading
import sys
import os

def runFuncAsyncThread(target_func, args):
    t = threading.Thread(target=target_func, args=args)
    t.start()


K_MAIN_M3U8 = "Main.m3u8"
K_SUB_M3U8 = "Sub.m3u8"

_g_IsUsingMainM3u8 = True
_g_split_mark = "#EXTM3U"
def refreshM3u8(channel_name, uri_path):
    global _g_IsUsingMainM3u8
    global _g_split_mark
    while True:
        pl = requests.get("https://linear-abematv.akamaized.net/channel/{}/1080/playlist.m3u8".format(channel_name)).text
        cur_pl = re.sub('URI=.*?\,', 'URI=\"{}\",'.format(uri_path), pl)
        next_pl = None

        tmp_cur_mark = None
        tmp_list = cur_pl.partition('#EXT-X-DISCONTINUITY\n')
        if tmp_list[2] != '':   # if has next m3u8
            # set the split mark as the *.ts name
            tmp_cur_mark = tmp_list[0].partition('#EXT-X-DISCONTINUITY\n')[0].split('\n')[-2]
            cur_pl = tmp_list[0] + '#EXT-X-ENDLIST'     # make current m3u8 end playing the old list
            next_pl = '#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:5\n' + tmp_list[2]     # make the new list
        else:
            tmp_cur_mark = "#EXTM3U"

        if _g_split_mark not in cur_pl:
            _g_IsUsingMainM3u8 = False if _g_IsUsingMainM3u8 else True

        if tmp_cur_mark != _g_split_mark:
            _g_split_mark = tmp_cur_mark


        if _g_IsUsingMainM3u8:
            curFile = K_MAIN_M3U8
            nextFile = K_SUB_M3U8
        else:
            curFile = K_SUB_M3U8
            nextFile = K_MAIN_M3U8

        with open(curFile, "w") as f:
            f.write(cur_pl)
        print('-CURRENT-{} m3u8:\n{}\n'.format(curFile, cur_pl))

        if next_pl: # write the next file
            with open(nextFile, "w") as f:
                f.write(next_pl)
            print('-NEXT-{} m3u8:\n{}\n'.format(nextFile, next_pl))

        sleep(10)   #the m3u8 has 4 segments, it can hold 20 secounds, Default is updated every 5 secounds


def startFFMPEG(rtmp_link):
    while True:
        if os.path.exists(K_MAIN_M3U8):
            break
        sleep(0.1)    # wait for the m3u8
    m3u8_file = K_MAIN_M3U8
    while True:
        print("====\nUsing the m3u8 File. -->{}".format(m3u8_file))
        p = subprocess.Popen(
            'ffmpeg -loglevel error \
            -re \
            -protocol_whitelist file,http,https,tcp,tls,crypto -allowed_extensions ALL \
            -i "{}" \
            -vcodec copy -acodec aac -strict -2 -ac 2 -bsf:a aac_adtstoasc \
            -f flv "{}"'.format(m3u8_file, rtmp_link), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        pid = p.pid
        out, err = p.communicate()
        errcode = p.returncode

        if errcode == 0:
            # filp the File
            m3u8_file = K_MAIN_M3U8 if m3u8_file == K_SUB_M3U8 else K_SUB_M3U8
            print("----\nChanging the m3u8 File. \nChanging File To===>{}".format(m3u8_file))
        else:
            print("CMD RUN END with PID:{}\nOUT: {}\nERR: {}\nERRCODE: {}".format(pid, out, err, errcode))
            print('RETRYING___________THIS: startFFMPEG')
            sleep(5)


if __name__ == '__main__':
    if os.path.exists(K_MAIN_M3U8):
        os.remove(K_MAIN_M3U8)
    if os.path.exists(K_SUB_M3U8):
        os.remove(K_SUB_M3U8)

    channel_name = 'ultra-games'
    rtmp_link = 'test.mp4'
    if len(sys.argv) >= 2:
        channel_name = sys.argv[1]
        rtmp_link = sys.argv[2]

    print('RUNNING with channel:{} to {}'.format(channel_name, rtmp_link))
    runFuncAsyncThread(refreshM3u8, (channel_name, './myfile.dat'))
    startFFMPEG(rtmp_link)
