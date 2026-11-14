# render88.py cues.json src.mp4 out.mp4 "Nadpis" [preview_dir t1,t2,...]
# Hodnoty změřené ze vzoru E_Delay LFO / Ukočíruj Ping-Pong delay (1080x1920):
#  nadpis: FreeSans Bold, bílý, zarovnaný vlevo x=60, POSLEDNÍ účaří y=440, max šířka 971 px,
#          krátký nadpis 162 px (Delay LFO), delší se zalomí na 2 řádky a zmenší, řádkování 1.03; tmavý měkký stín.
#  titulky: jedno slovo, FreeSans Bold 35 px, bílé, vycentrované x=540, účaří y=1209, jemný stín.
import sys, json, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H=1080,1920
import os
BOLD=os.environ.get('FONT','/System/Library/Fonts/HelveticaNeue.ttc'); FIDX=int(os.environ.get('FIDX','1'))
cues=json.load(open(sys.argv[1])); src=sys.argv[2]; out=sys.argv[3]; title=sys.argv[4]
TMAX,TLEFT,TBASE,TWIDTH,TLEAD=162,49,440,971,1.03
SS,SBASE=35,1209
def shadow_comp(lay,blur,off,gain):
    a=lay.split()[3]; sh=Image.new('RGBA',(W,H),(0,0,0,0))
    soft=a.filter(ImageFilter.GaussianBlur(blur)).point(lambda v:min(255,int(v*gain)))
    sh.putalpha(soft); sh=Image.new('RGBA',(W,H),(0,0,0,0)).__class__.alpha_composite(Image.new('RGBA',(W,H),(0,0,0,0)),sh) if False else sh
    moved=Image.new('RGBA',(W,H),(0,0,0,0)); moved.alpha_composite(sh,(0,off)); moved.alpha_composite(lay); return moved
def best_title(txt):
    ws=txt.split()
    for size in range(TMAX,40,-2):
        f=ImageFont.truetype(BOLD,size,index=FIDX)
        if f.getlength(txt)<=TWIDTH: return f,[txt]
        best=None
        for i in range(1,len(ws)):
            if len(ws[i-1])==1: continue
            a=' '.join(ws[:i]); b=' '.join(ws[i:]); m=max(f.getlength(a),f.getlength(b))
            if m<=TWIDTH and (best is None or m<best[0]): best=(m,[a,b])
        if best: return f,best[1]
f,lines=best_title(title)
lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
for k,l in enumerate(lines):
    base=TBASE-(len(lines)-1-k)*round(f.size*TLEAD)
    x=TLEFT-f.getbbox(l,anchor='ls')[0]
    d.text((x,base),l,font=f,fill=(255,255,255,255),anchor='ls')
titleL=shadow_comp(lay,7,5,1.6)
fs=ImageFont.truetype(BOLD,SS,index=FIDX); cache={}
def sub(i):
    if i not in cache:
        w=cues[i]['words'][0]['w']; l=Image.new('RGBA',(W,H),(0,0,0,0))
        ImageDraw.Draw(l).text((W/2,SBASE),w,font=fs,fill=(255,255,255,255),anchor='ms')
        cache[i]=shadow_comp(l,3,2,1.2)
    return cache[i]
def idx(t):
    for i,c in enumerate(cues):
        if c['start']<=t<c['end']: return i
    return -1
def frame(t):
    img=titleL.copy(); i=idx(t)
    if i>=0: img.alpha_composite(sub(i))
    return img
if len(sys.argv)>5:
    import os; os.makedirs(sys.argv[5],exist_ok=True)
    for t in map(float,sys.argv[6].split(',')):
        bg=subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',src,'-frames:v','1','-f','rawvideo','-pix_fmt','rgba','-'],capture_output=True).stdout
        im=Image.frombytes('RGBA',(W,H),bg); im.alpha_composite(frame(t)); im.convert('RGB').save(f"{sys.argv[5]}/p_{t:05.1f}.png")
    sys.exit()
FPS=30; dur=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',src]))
N=int(round(dur*FPS))
p=subprocess.Popen(['ffmpeg','-v','error','-y','-i',src,'-f','rawvideo','-pix_fmt','rgba','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
  '-filter_complex','[0:v][1:v]overlay=0:0:format=auto,format=yuv420p','-map','0:a?','-c:v','libx264','-crf','21','-preset','medium','-r',str(FPS),'-c:a','copy','-shortest','-movflags','+faststart',out],stdin=subprocess.PIPE)
last=None;lk=None
for n in range(N):
    t=n/FPS; k=idx(t)
    if k!=lk: last=frame(t).tobytes(); lk=k
    p.stdin.write(last)
p.stdin.close(); p.wait()
