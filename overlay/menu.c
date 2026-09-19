/* Freestanding PPC overlay for the explicitly fingerprinted game DOL.
 * No IOS calls, allocations or floating point. Optional render-thread fence;
 * the VI interrupt path never waits.
 */
typedef unsigned u32;typedef unsigned short u16;typedef unsigned char u8;
#include "menu.h"
#ifdef GAME_GX_DATA_POINTER
#include "copy_target.h"
#endif
static struct menu_state state;
static struct menu_players players;
static u8 pad[96];
#ifdef E12_MENU
#define REPLY_WORDS 116
#else
#define REPLY_WORDS 104
#endif
static u32 reply[REPLY_WORDS];
#define BOX ((volatile u32 *)0xc0002c00u)
extern void original_vi(void *);
extern void original_read(int,void *);
static void mask(void *p,u32 n){menu_mask(&state,p,n);}
void read_hook(int chan,void *p){original_read(chan,p);mask(p,96);}
void *sample_hook(void *dst,const void *src,u32 n){
 void *(*copy)(void*,const void*,u32)=(void*)GAME_MEMCPY;copy(dst,src,n);if(n>=42)mask(dst,n);return dst;
}
static const char alphabet[]=" ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-./:>";
static const u8 glyph[][5]={
 {0,0,0,0,0},{126,17,17,17,126},{127,73,73,73,54},{62,65,65,65,34},{127,65,65,34,28},
 {127,73,73,73,65},{127,9,9,9,1},{62,65,73,73,122},{127,8,8,8,127},{0,65,127,65,0},
 {32,64,65,63,1},{127,8,20,34,65},{127,64,64,64,64},{127,2,12,2,127},{127,4,8,16,127},
 {62,65,65,65,62},{127,9,9,9,6},{62,65,81,33,94},{127,9,25,41,70},{38,73,73,73,50},
 {1,1,127,1,1},{63,64,64,64,63},{31,32,64,32,31},{63,64,56,64,63},{99,20,8,20,99},
 {3,4,120,4,3},{97,81,73,69,67},{62,81,73,69,62},{0,66,127,64,0},{66,97,81,73,70},
 {33,65,69,75,49},{24,20,18,127,16},{39,69,69,69,57},{60,74,73,73,48},{1,113,9,5,3},
 {54,73,73,73,54},{6,73,73,41,30},{8,8,8,8,8},{0,96,96,0,0},{32,16,8,4,2},
 {0,54,54,0,0},{0,65,34,20,8}
};
static void text(volatile u32 *fb,u32 width,u32 x,u32 y,const char *p,u32 color){
 u32 i,c,row,col,j;
 for(i=0;i<47&&i<(width-x-24)/12&&p[i];i++){
  c=(u8)p[i];if(c>='a'&&c<='z')c-=32;
  for(j=0;alphabet[j]&&alphabet[j]!=c;j++) {}
  if(!alphabet[j])j=0;
  for(col=0;col<5;col++)for(row=0;row<7;row++)if(glyph[j][col]&(1u<<row)){
   fb[(y+row*2)*width/2+x/2+i*6+col]=color;
   fb[(y+row*2+1)*width/2+x/2+i*6+col]=color;
  }
 }
}
static void request(u32 op){
 state.page=state.selected/8*8;state.seq++;if(!state.seq)state.seq=1;
 BOX[2]=op;
#ifdef E12_MENU
 BOX[3]=op==2||op==3?(state.slot<<16)|state.selected:op==4?state.slot:state.page;
#else
 BOX[3]=op==2?state.selected:state.page;
#endif
 BOX[4]=0x534b595a;
 __asm__ volatile("sync":::"memory");BOX[1]=state.seq;
#ifdef E12_MENU
 BOX[0]=0x4531324d;
#else
 BOX[0]=0x4531314d;
#endif
 __asm__ volatile("sync":::"memory");state.pending=1;state.frames=0;
}
#ifdef E13_SYNC_COPY
static void update_menu(void){
 u32 keys[2]={0,0},n,action,i,version,snapshot[REPLY_WORDS];
#else
static void draw_menu(void *buffer){
 u32 keys[2]={0,0},n,action,i,x,y,width,addr=(u32)buffer,version,height,picture;
 u32 snapshot[REPLY_WORDS];volatile u32 *fb;char error[24];
#endif

 BOX[5]++;
 version=BOX[112];
 if(!(version&1)){
  for(i=0;i<104;i++)snapshot[i]=BOX[8+i];
#ifdef E12_MENU
  for(i=0;i<12;i++)snapshot[104+i]=BOX[120+i];
#endif
  __asm__ volatile("sync":::"memory");
  if(version==BOX[112])for(i=0;i<REPLY_WORDS;i++)reply[i]=snapshot[i];
 }
 n=reply[2];
 /* WPADRead's control table must exist before its first call. */
 for(i=0;i<2;i++)if(((volatile u32*)GAME_WPAD_TABLE)[i]){
  original_read(i,pad);if(!pad[41]&&pad[40]<=1)keys[i]=(u32)pad[0]<<8|pad[1];
 }
 if(n>640)n=0;
 if(state.pending){state.frames++;if(reply[0]==state.seq)state.pending=0;}
 action=menu_input_players(&state,&players,keys,n);if(action)request(action);
#ifdef E13_SYNC_COPY
}
static void draw_menu(void *buffer){
 u32 n=reply[2],i,x,y,width,addr=(u32)buffer,height,picture;
 volatile u32 *fb;char error[24];
 if(n>640)n=0;
#endif
 if(!state.visible)return;
 /* SDK XFB pitch: WPL is the seven-bit field in VI picture configuration. */
 picture=*(volatile u16*)0xcc002048u;
 width=(picture>>8&127)*16;
 height=(*(volatile u16*)0xcc002000u>>4)&1023;
 if((picture&255)*16==width*2)height*=2;
 else if((picture&255)*16!=width)return;
 if(width<512||width>720||height<320)return;
 addr&=0x3fffffffu;
#ifdef E12_MENU
 if(addr&31u)return;
#endif
 if(!((addr>=0x4000&&addr<=0x01800000u-width*320*2)||
      (addr>=0x10000000&&addr<=0x14000000u-width*320*2)))return;
 /* E12a: restore the hardware-visible E11 uncached rendering path. */
 fb=(volatile u32 *)(addr|0xc0000000u);
 for(y=36;y<316;y++)for(x=24;x<width-24;x+=2)fb[y*(width/2)+x/2]=0x20802080;
#ifdef E12_MENU
#ifdef E13_SYNC_COPY
 char title[]="SKYLANDERS MENU - SLOT 00 OF 16";
#else
 char title[]="SKYLANDERS MENU - SLOT 00 OF 16";
#endif
 title[23]='0'+(state.slot+1)/10;title[24]='0'+(state.slot+1)%10;
 text(fb,width,40,48,title,0xeb80eb80);
 text(fb,width,40,66,reply[5]?(const char*)(reply+104):"EMPTY SLOT",0xb880b880);
#else
 text(fb,width,40,48,"SKYLANDERS - SD FIGURES",0xeb80eb80);
#endif
 if(state.pending&&state.frames>180)text(fb,width,40,82,"PORTAL MENU NOT RESPONDING",0xd080d080);
 else if(!n){
  text(fb,width,40,82,reply[1]?"LIBRARY LOAD FAILED":"WAITING FOR SD LIBRARY",0xd080d080);
  if(reply[1]){
   menu_error_code(reply[1],error);text(fb,width,40,112,error,0xeb80eb80);
   text(fb,width,40,142,"CHECK SD CARD AND REOPEN THE MENU  ",0xd080d080);
  }
 }
 else for(i=0;i<8&&state.page+i<n;i++){
  u32 color=state.page+i==state.selected?0xeb80eb80:0x98809880;
  if(state.page+i==state.selected)text(fb,width,40,84+i*19,">",color);
  text(fb,width,56,84+i*19,(const char*)(reply+8+i*12),color);
 }
 if(n&&reply[1]){menu_error_code(reply[1],error);text(fb,width,40,236,error,0xeb80eb80);}
#ifdef E12_MENU
 text(fb,width,40,254,"C Z SLOT  A LOAD  MINUS REMOVE  B CLOSE",0xeb80eb80);
 text(fb,width,40,274,"1 SAVE NOW  2 RESCAN  LEFT RIGHT PAGE",0xb880b880);
#else
 text(fb,width,40,266,"UP DOWN CHOOSE  A SELECT  B CLOSE",0xeb80eb80);
#endif
 text(fb,width,40,290,
#ifdef E12_MENU
      reply[1]==(u32)-17?"FIGURE ALREADY IN ANOTHER SLOT":
#endif
      reply[1]?menu_error_status(n,reply[5],reply[6]):
      reply[7]==2?"SWAPPING FIGURE":reply[6]?"SAVING PROGRESS":state.pending?"LOADING MENU":reply[5]&&reply[4]==state.selected?
#ifdef E12_MENU
      "HIGHLIGHTED FIGURE ON PORTAL - SAVED":
#else
      "HIGHLIGHTED FIGURE IS ON THE PORTAL":
#endif
#ifdef E12_MENU
      reply[5]?"SLOT LOADED - ALL PROGRESS SAVED":"EMPTY SLOT - ALL PROGRESS SAVED"
#else
      "PLUS MINUS TO OPEN - LEFT RIGHT PAGE"
#endif
      ,0xb880b880);
 __asm__ volatile("sync":::"memory");
}
#ifdef E13_SYNC_COPY
/* Profiles hook inspected rendering call sites or the SDK copy entry.
 * Never wait in VI or in an interrupts-disabled caller. The original GPU copy
 * is always queued, including when the menu is closed. */
void copy_hook(void *buffer,u32 clear){
#ifdef GAME_COPY_ENTRY
 extern void original_copy(void*,u32);
 void (*copy)(void*,u32)=original_copy;
#else
 void (*copy)(void*,u32)=(void*)GAME_COPY_DISP;
#endif
#ifdef GAME_GX_DATA_POINTER
 /* Filter before polling or suppressing copies: the clear-only copy must still
  * execute, and its 0x520-byte junk buffer cannot hold a screen-sized menu. */
 u32 gx=*(volatile u32*)GAME_GX_DATA_POINTER;
 if(gx<0x80004000u||gx>0x817ffdc4u||(gx&3u)||
    !menu_display_copy(*(volatile u32*)(gx+0x238u),
                       *(volatile u16*)0xcc002048u)){
  copy(buffer,clear);return;
 }
#endif
#ifdef GAME_HOLD_FRAME
 u32 msr;
 __asm__ volatile("mfmsr %0":"=r"(msr));
 if(msr&0x8000u)update_menu();
 /* No completion callbacks or waits inside the engine's copy operation.
  * Every target is painted while open; suppress GPU copies that erase it.
  * Keep the original copy/clear behavior immediately on menu close. */
 if(state.visible){draw_menu(buffer);return;}
 copy(buffer,clear);
#else
 void (*done)(void)=(void*)GAME_DRAW_DONE;u32 msr;
 copy(buffer,clear);
 __asm__ volatile("mfmsr %0":"=r"(msr));
#ifdef GAME_RENDER_POLL
 if(!(msr&0x8000u))return;
 /* Poll even while closed: VI framebuffer changes need not occur each frame.
  * VI does not update this state on these profiles, avoiding IRQ reentrancy. */
 update_menu();
 if(!state.visible)return;
#else
 if(!state.visible||!(msr&0x8000u))return;
#endif
 done();draw_menu(buffer);
#endif
}
#endif
void vi_hook(void *buffer){
 original_vi(buffer);
#ifdef E13_SYNC_COPY
#ifndef GAME_RENDER_POLL
 update_menu();
#endif
#else
 draw_menu(buffer);
#endif
}


