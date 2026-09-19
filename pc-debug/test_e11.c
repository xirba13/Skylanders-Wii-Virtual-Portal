#include <stdint.h>
#include <string.h>
static int os_open(const char*,unsigned);
static int os_close(int);
static int os_read(int,void*,unsigned);
static int os_write(int,void*,unsigned);
static int os_ioctlv(int,unsigned,unsigned,unsigned,void*);
static unsigned char mailbox[512];
static int fat_thread=-1, rights_error, open_calls;
static unsigned fat_rights;
static int Swi_AddThreadRights(int thread,unsigned rights){
 if(rights_error)return rights_error;
 fat_thread=thread;fat_rights|=rights;return 0;
}
#define E11_MAP mailbox
#define E11_MENU
#define E09_STORAGE
#define main baseline_main
#include "test_e07.c"
#undef main
#include "../overlay/menu.h"
static u8 files[8][16416];static unsigned sizes[8];static int io_error;
static int os_open(const char *p,unsigned mode){
 int fd;open_calls++;
 /* d2x running-title stealth gate, before the FAT resource manager. */
 if(fat_thread!=os_get_thread_id()||!(fat_rights&2))return -6;
 if(!strcmp(p,"fat"))return 9;
 if(strstr(p,"catalog"))fd=0;
 else if(strstr(p,"fig")){unsigned id=(unsigned)strtoul(strstr(p,"fig")+3,0,10);if(id>1)return -106;fd=1+id;}
 else {unsigned id=(unsigned)strtoul(strstr(p,"save")+4,0,10);if(id>1)return -106;fd=3+id*2+(strstr(p,".sav1")!=0);}
 if(mode==1&&!sizes[fd])return -106;return fd;
}
static int os_close(int fd){(void)fd;return io_error==2?-12:0;}
static int os_read(int fd,void *p,unsigned n){if(n>sizes[fd])n=sizes[fd];memcpy(p,files[fd],n);return n;}
static int os_write(int fd,void *p,unsigned n){if(io_error==1)n/=2;memcpy(files[fd],p,n);sizes[fd]=n;return n;}
static int os_ioctlv(int fd,unsigned c,unsigned a,unsigned b,void*p){(void)fd;(void)c;(void)a;(void)b;(void)p;return 0;}
static void finish(void){CHECK(e09_busy);e11_result=e11_op==1?e11_catalog_load():e11_op==2?e11_load():e11_save();e09_complete();}
static void command(unsigned seq,unsigned op,unsigned arg){put_be32(mailbox,0x4531314d);put_be32(mailbox+4,seq);put_be32(mailbox+8,op);put_be32(mailbox+12,arg);put_be32(mailbox+16,0x534b595a);put_be32(mailbox+20,seq);e11_mailbox();}
int main(void){unsigned i;ipcmessage m;u8 original[1024];
 for(i=0;i<1024;i++){files[1][i]=(u8)(i*13);files[2][i]=(u8)(i*7);original[i]=files[1][i];}
 sizes[1]=sizes[2]=1024;sizes[0]=sizeof(e11_catalog);
 put_be32(files[0],0x45313143);put_be32(files[0]+4,2);
 put_be32(files[0]+32,0);put_be32(files[0]+36,e11_hash(files[1],1024));memcpy(files[0]+40,"FIRST",6);
 put_be32(files[0]+96,1);put_be32(files[0]+100,e11_hash(files[2],1024));memcpy(files[0]+104,"SECOND",7);
 put_be32(files[0]+8,e11_hash(files[0]+32,128));
 CHECK(os_open("fat",0)==-6);
 rights_error=-2;int before=open_calls;CHECK(e11_catalog_load()==-2&&open_calls==before);
 CHECK(fat_thread==-1);rights_error=0;
 CHECK(e11_catalog_load()==0&&fat_thread==12&&fat_rights==2);
 CHECK(os_open("fat0:/skylanders/e11/fig255.bin",1)==-106);
 fat_thread=11;CHECK(os_open("fat",0)==-6); /* Parent/other thread rights do not suffice. */
 v4_route[0]=1;e09_start();finish();CHECK(e11_count==2&&e11_swap&&!e09_loaded);
 v4_ticks=249;e09_poll();CHECK(!e09_busy);v4_ticks=250;e09_poll();finish();CHECK(e09_loaded&&e09_slot==0&&!memcmp(e09_live,files[1],1024));
 command(1,1,0);CHECK(v4_be32(mailbox+32)==1&&v4_be32(mailbox+40)==2);CHECK(!strcmp((char*)mailbox+64,"FIRST"));CHECK(!(v4_be32(mailbox+448)&1));
 command(2,2,999);CHECK(e09_error==-4&&e09_loaded&&e09_slot==0);
 /* Real protocol write, then removal, journal save and load in order. */
 m=control('W',19);payload[1]=0x10;payload[2]=4;memset(payload+3,0xaa,16);v4_process(&m);CHECK(m.result==27&&e09_generation==1);
 command(3,2,1);CHECK(e11_swap&&!e09_loaded);e09_poll();CHECK(e11_op==3);finish();CHECK(e09_saved==1&&e09_sequence==1);
 v4_ticks+=250;e09_poll();CHECK(e11_op==2);finish();CHECK(e09_loaded&&e09_slot==1&&!memcmp(e09_live,files[2],1024));CHECK(!memcmp(files[1],original,1024));
 command(4,2,0);v4_ticks+=250;e09_poll();finish();CHECK(e09_slot==0&&e09_live[64]==0xaa);
 /* Save failure keeps all progress and restores current figure. */
 e09_live[64]=0xbb;e09_generation++;command(5,2,1);io_error=1;e09_poll();finish();CHECK(e09_error<0&&e09_slot==0&&e09_loaded&&!e11_swap&&e09_live[64]==0xbb&&e09_generation!=e09_saved);io_error=0;
 /* Missing/corrupt destination cannot replace the live figure. */
 command(6,2,1);e09_poll();finish();files[2][0]^=1;v4_ticks+=250;e09_poll();finish();CHECK(e09_error<0&&e09_slot==0&&e09_loaded&&e09_live[64]==0xbb);files[2][0]^=1;
 /* A torn newer journal falls back to the older valid copy. */
 e11_job_slot=0;e11_job_source=e11_hash(files[1],1024);CHECK(e11_load()==0&&e11_job[96]==0xbb);
 files[3][40]^=1;CHECK(e11_load()==0&&e11_job[96]==0xaa);
 /* Snapshot completion never marks later writes as saved. */
 e11_snapshot=7;e09_generation=8;e11_op=3;e11_result=0;e09_complete();CHECK(e09_saved==7&&e09_generation==8);
 /* Unknown mailbox version does nothing. */
 put_be32(mailbox,0);put_be32(mailbox+4,100);e11_mailbox();CHECK(e11_request_seq==6);
 /* Catalogue integrity, bounds and missing files. */
 files[0][40]^=1;CHECK(e11_catalog_load()==-4);files[0][40]^=1;
 sizes[0]--;CHECK(e11_catalog_load()==-4);sizes[0]++;
 e11_name(255,-1);CHECK(!strcmp(e11_path,"fat0:/skylanders/e11/fig255.bin"));
 /* UI chord edge, wrap, pending state, zero rows, closing-key suppression. */
 struct menu_state ui={0};CHECK(menu_input(&ui,MENU_CHORD,169)==1&&ui.visible);
 CHECK(menu_input(&ui,MENU_CHORD,169)==0&&ui.visible);menu_input(&ui,0,169);
 CHECK(menu_input(&ui,MENU_UP,169)==1&&ui.selected==168);ui.page=168;menu_input(&ui,0,169);
 CHECK(menu_input(&ui,MENU_DOWN,169)==1&&ui.selected==0);ui.page=0;menu_input(&ui,0,169);
 CHECK(menu_input(&ui,MENU_A,169)==2);ui.pending=1;menu_input(&ui,0,169);CHECK(menu_input(&ui,MENU_DOWN,169)==0&&ui.selected==0);
 menu_input(&ui,MENU_B,169);CHECK(!ui.visible&&ui.swallow);menu_input(&ui,0,169);CHECK(!ui.swallow);
 ui.pending=0;menu_input(&ui,MENU_CHORD,0);menu_input(&ui,0,0);CHECK(menu_input(&ui,MENU_A,0)==0);
 /* Short error records must never write extension bytes past the copy. */
 u8 shortpad[52];memset(shortpad,0xa5,sizeof(shortpad));shortpad[40]=1;ui.visible=1;
 menu_mask(&ui,shortpad,42);CHECK(shortpad[0]==0&&shortpad[1]==0&&shortpad[48]==0xa5&&shortpad[49]==0xa5);
 menu_mask(&ui,shortpad,50);CHECK(shortpad[48]==0&&shortpad[49]==0&&shortpad[50]==0xa5);
 /* No mailbox writes after closing HID or losing the PPC heartbeat. */
 command(7,1,0);u32 revision=e11_revision;v4_route[0]=0;command(8,1,0);CHECK(e11_revision==revision);
 v4_route[0]=1;v4_ticks+=501;put_be32(mailbox+20,e11_heartbeat);e11_mailbox();CHECK(e11_revision==revision);
 char error_text[24];menu_error_code((unsigned)-4,error_text);CHECK(!strcmp(error_text,"ERROR -4"));
 menu_error_code((unsigned)-106,error_text);CHECK(!strcmp(error_text,"ERROR -106"));
 menu_error_code(0x80000000u,error_text);CHECK(!strcmp(error_text,"ERROR -2147483648"));
 menu_error_code(0,error_text);CHECK(!strcmp(error_text,"ERROR 0"));
 CHECK(!strcmp(menu_error_status(0,0,0),"LIBRARY LOAD FAILED"));
 CHECK(!strcmp(menu_error_status(169,0,0),"FIGURE LOAD FAILED"));
 CHECK(!strcmp(menu_error_status(169,1,0),"SD ERROR - CURRENT FIGURE RETAINED"));
 CHECK(!strcmp(menu_error_status(169,1,1),"SAVE ERROR - PROGRESS STILL IN RAM"));
 printf("PASS: %u E11 assertions\n",checks);return 0;
}
