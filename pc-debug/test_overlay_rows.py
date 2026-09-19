"""Differential framebuffer check against the prior renderer (no console timing claim)."""
import argparse, subprocess
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--cc',required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
def adapt(source,name):
    source=source.replace('GAME_MEMCPY','0x80005f34u').replace('GAME_WPAD_TABLE','0x805b5630u')
    source=source.replace('#include "menu.h"', '#include "'+(root/'overlay/menu.h').as_posix()+'"')
    source=source.replace('#define BOX ((volatile u32 *)0xc0002c00u)', 'static volatile u32 box[256];\n#define BOX box')
    source=source.replace('__asm__ volatile("sync":::"memory");','')
    source=source.replace('*(volatile u32*)0x805b5630u','0')
    source=source.replace('*(volatile u16*)0xcc002048u','((test_width/16)<<8)|(test_width/16)')
    source=source.replace('*(volatile u16*)0xcc002000u','480u<<4')
    source=source.replace('addr=(u32)buffer','addr=0x4000u')
    source=source.replace('fb=(volatile u32 *)(addr|0xc0000000u);','fb=test_fb;')
    source=source.replace('SKYLANDERS E12A - SLOT','SKYLANDERS E12C - SLOT')
    prefix='#include <string.h>\n#define E12_MENU\nstatic unsigned test_width; static unsigned *test_fb;\n'
    suffix=r"""
void original_read(int c,void *p){(void)c;memset(p,0,96);}
void original_vi(void *p){(void)p;}
void RUN(unsigned *fb,unsigned width,unsigned scenario){
 test_width=width;test_fb=fb;memset(&state,0,sizeof(state));memset(reply,0,sizeof(reply));memset((void*)box,0,sizeof(box));
 box[112]=1;state.visible=1;state.slot=15;state.selected=3;state.seq=9;
 reply[2]=8;reply[4]=3;reply[5]=1;
 for(unsigned i=0;i<8;i++)memcpy((char*)(reply+8+i*12),"SSA DARK SPYRO - 0123456789 /:>. abcdefghijklmnop",47);
 memcpy(reply+104,"SSA DARK SPYRO",15);
 switch(scenario){
 case 1:reply[2]=0;break;
 case 2:reply[2]=0;reply[1]=(unsigned)-6;break;
 case 3:reply[1]=(unsigned)-17;break;
 case 4:reply[6]=2;break;
 case 5:reply[7]=2;break;
 case 6:state.pending=1;state.frames=181;break;
 case 7:state.visible=0;break;
 case 8:reply[5]=0;break;
 case 9:reply[1]=(unsigned)-4;break;
 }
 draw_menu(0);
}
""".replace('RUN',name)
    # Give stubs unique external names in each translation unit.
    return (prefix+source+suffix).replace('original_read',name+'_read').replace('original_vi',name+'_vi').replace('read_hook',name+'_read_hook').replace('sample_hook',name+'_sample_hook').replace('vi_hook',name+'_vi_hook')
td=a.output.resolve()
td.mkdir(parents=True,exist_ok=True)
for name,source in [('old',a.baseline.read_text()),('new',(root/'overlay/menu.c').read_text())]:
    (td/(name+'.c')).write_text(adapt(source,name))
(td/'test.c').write_text(r"""
#include <stdio.h>
#include <string.h>
unsigned a[720*480/2],b[720*480/2];
void old(unsigned*,unsigned,unsigned);void new(unsigned*,unsigned,unsigned);
int main(void){unsigned tests=0;
 for(unsigned w=512;w<=720;w+=16)for(unsigned s=0;s<10;s++){
  memset(a,0x5a,sizeof(a));memset(b,0x5a,sizeof(b));old(a,w,s);new(b,w,s);
  if(memcmp(a,b,sizeof(a))){fprintf(stderr,"Pixel mismatch width %u scenario %u\n",w,s);return 1;}tests++;
 }
 printf("%u full-frame pixel comparisons passed (including untouched borders).\n",tests);return 0;
}
""")
exe=td/'test.exe'
subprocess.run([a.cc,'-O2',str(td/'old.c'),str(td/'new.c'),str(td/'test.c'),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)

