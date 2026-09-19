#include <stdint.h>
#include <string.h>
static int os_open(const char*,unsigned);
static int os_close(int);
static int os_read(int,void*,unsigned);
static int os_write(int,void*,unsigned);
static int os_ioctlv(int,unsigned,unsigned,unsigned,void*);
#define E09_STORAGE
#define main old_main
#include "test_e07.c"
#undef main
static u8 files[6][1056];static unsigned sizes[6];static int disk_error;
static int os_open(const char *p,unsigned mode){
 int fd=strstr(p,"selected")?3:strstr(p,".bin")?2:strstr(p,".sav0")?4:strstr(p,".sav1")?5:1;
 if(mode==1&&!sizes[fd]&&fd!=1)return -6;
 return fd;
}
static int os_close(int fd){(void)fd;return disk_error==2?-12:0;}
static int os_read(int fd,void *p,unsigned n){if(n>sizes[fd])n=sizes[fd];memcpy(p,files[fd],n);return n;}
static int os_write(int fd,void *p,unsigned n){if(disk_error==1)n/=2;memcpy(files[fd],p,n);sizes[fd]=n;return n;}
static int os_ioctlv(int fd,unsigned c,unsigned a,unsigned b,void*p){(void)fd;(void)c;(void)a;(void)b;(void)p;return 0;}
static void save_now(void){
 v4_copy(e09_job+32,e09_live,1024);e09_snapshot=e09_generation;e09_operation=2;
 e09_result=e09_save();e09_complete();
}
int main(void){
 unsigned i;u8 original[1024];ipcmessage m;
 for(i=0;i<1024;i++)original[i]=files[2][i]=(u8)(i*13);sizes[2]=1024;
 put_be32(files[3],0x45303953);put_be32(files[3]+4,0);put_be32(files[3]+8,e09_hash(files[3],8));sizes[3]=32;
 CHECK(e09_load()==0);CHECK(!memcmp(e09_job+32,original,1024));
 e09_operation=1;e09_result=0;e09_complete();CHECK(e09_loaded&&v4_sessions[0].figure_added);
 m=control('W',19);payload[1]=0x10;payload[2]=4;memset(payload+3,0xaa,16);
 v4_process(&m);CHECK(m.result==27&&e09_generation==1);
 save_now();CHECK(e09_error==0&&e09_saved==1&&e09_sequence==1);CHECK(e09_valid(files[5]));
 CHECK(!memcmp(files[2],original,1024));
 memset(e09_live,0,1024);CHECK(e09_load()==0);CHECK(e09_job[32+64]==0xaa);
 e09_operation=1;e09_result=0;e09_complete();
 e09_live[64]=0xbb;e09_generation++;disk_error=1;save_now();CHECK(e09_error<0&&e09_saved==1&&e09_sequence==1);
 disk_error=0;CHECK(e09_load()==0);CHECK(e09_job[32+64]==0xaa); /* torn newer copy ignored */
 e09_operation=1;e09_result=0;e09_complete();
 e09_live[64]=0xcc;e09_generation++;save_now();CHECK(e09_sequence==2&&e09_valid(files[4]));
 CHECK(e09_load()==0&&e09_job[32+64]==0xcc);
 files[4][40]^=1;CHECK(e09_load()==0&&e09_job[32+64]==0xaa); /* corrupt newest -> previous */
 files[2][0]^=1;CHECK(e09_load()==0&&e09_job[32]==files[2][0]); /* replaced source -> ignore saves */
 e09_snapshot=7;e09_generation=8;e09_operation=2;e09_result=0;e09_complete();CHECK(e09_saved==7&&e09_generation==8);
 disk_error=2;e09_generation++;save_now();CHECK(e09_error<0);disk_error=0;
 sizes[2]=1023;CHECK(e09_load()==-4);sizes[2]=1024;
 sizes[2]=0;CHECK(e09_load()==-6);sizes[2]=1024;
 files[3][8]^=1;CHECK(e09_load()==-4); /* invalid selector never silently selects */
 /* E09a: failed startup retries without requiring the diagnostic ioctl. */
 e09_loaded=0;e09_busy=0;e09_queue=10;e09_last_tick=100;e09_trace_tick=100;
 v4_ticks=599;e09_poll();CHECK(!e09_busy);
 v4_ticks=600;e09_poll();CHECK(e09_busy&&e09_operation==1);
 e09_result=-6;e09_complete();CHECK(!e09_loaded&&!e09_busy&&e09_error==-6);
 v4_ticks=1100;e09_poll();CHECK(e09_busy&&e09_operation==1);
 e09_result=0;e09_complete();CHECK(e09_loaded&&v4_sessions[0].figure_added);
 e09_generation=e09_saved;v4_ticks=2600;e09_poll();CHECK(e09_busy&&e09_operation==3);
 CHECK(v4_be32(e09_trace)==0x45303931&&v4_be32(e09_trace+4)==1);
 e09_error=-12;e09_result=0;e09_complete();CHECK(e09_error==-12&&!e09_busy);
 e09_generation++;v4_ticks=6000;e09_poll();CHECK(e09_operation==2); /* dirty data wins */
 printf("PASS: %u persistence assertions\n",checks);return 0;
}
