"""Exercise the actual optional hook with mocked GPU and rendering operations."""
from pathlib import Path
import argparse,subprocess
p=argparse.ArgumentParser();p.add_argument('--cc',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
s=(Path(__file__).resolve().parents[1]/'overlay/menu.c').read_text()
start=s.index('void copy_hook(');end=s.index('\n}\n#endif',start)+2
hook=s[start:end].replace('__asm__ volatile("mfmsr %0":"=r"(msr));','msr=test_msr;')
source=r'''#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned u32;
static struct {unsigned visible;} state;
static unsigned test_msr,n;static char trace[8];static void *expected;
static void gpu_copy(void *p,u32 clear){assert(p==expected&&clear==1);trace[n++]='C';}
static void gpu_done(void){trace[n++]='F';}
static void draw_menu(void *p){assert(p==expected);trace[n++]='D';}
#define GAME_COPY_DISP gpu_copy
#define GAME_DRAW_DONE gpu_done
'''+hook+r'''
int main(void){
 expected=trace;
 for(unsigned visible=0;visible<2;visible++)for(unsigned ee=0;ee<2;ee++){
  n=0;memset(trace,0,sizeof(trace));state.visible=visible;test_msr=ee?0x8000:0;
  copy_hook(expected,1);assert(!strcmp(trace,visible&&ee?"CFD":"C"));
 }
 puts("Copy hook: original arguments/order and no wait when hidden or interrupts disabled passed");
}
'''
a.output.mkdir(parents=True,exist_ok=True);c=a.output/'copy-test.c';c.write_text(source);exe=a.output/'copy-test.exe'
subprocess.run([a.cc,'-O2',str(c),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
