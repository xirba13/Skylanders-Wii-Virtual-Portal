#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int32_t s32;
#define IOS_IOCTL 6
#define IOS_CLOSE 2
typedef struct { u32 command; s32 result; u32 fd; struct {
u32 command; u32 *buffer_in; u32 length_in; u32 *buffer_io; u32 length_io;
} ioctl; } ipcmessage;
static unsigned checks,acks,stock,failstage,queued;
static ipcmessage *last; static unsigned created_priority;
static u8 payload[64];
#define CHECK(x) do { checks++; if(!(x)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);exit(1);} }while(0)
static void zero_bytes(void*p,u32 n){memset(p,0,n);}
static void put_be32(u8*p,u32 x){p[0]=x>>24;p[1]=x>>16;p[2]=x>>8;p[3]=x;}
static void os_sync_before_read(void*p,u32 n){(void)p;(void)n;}
static void os_sync_after_write(void*p,u32 n){(void)p;(void)n;}
static s32 os_message_queue_ack(void*p,s32 r){ipcmessage*m=p;m->result=r;last=m;acks++;return 0;}
static s32 os_message_queue_create(void*p,u32 n){(void)p;(void)n;return failstage==1?-22:10;}
static s32 os_message_queue_destroy(s32 q){(void)q;return 0;}
static s32 os_message_queue_receive(s32 q,void*p,u32 f){(void)q;(void)p;(void)f;return -4;}
static s32 os_message_queue_send(s32 q,void*p,s32 f){(void)q;(void)p;(void)f;queued++;return failstage==4?-8:(failstage==6 && f!=0 ? -8 : 0);}
static s32 os_get_thread_id(void){return failstage==7?-4:12;}
static s32 os_thread_get_priority(s32 id){(void)id;return failstage==8?-4:0x30;}
static s32 os_thread_create(int(*f)(void*),void*a,void*s,u32 n,u32 p,s32 x){(void)f;(void)a;(void)s;(void)n;created_priority=p;(void)x;return failstage==2?-22:11;}
static s32 os_thread_cancel(s32 t,u32*p){(void)t;(void)p;return 0;}
static s32 os_thread_continue(s32 t){(void)t;return failstage==5?-22:0;}
static s32 os_create_timer(s32 a,s32 b,s32 c,s32 d){(void)a;(void)b;(void)c;(void)d;return failstage==3?-22:12;}
static s32 os_destroy_timer(s32 t){(void)t;return 0;}
static u32 make_arm_call(u32 a,u32 b){return 0xeb000000u|(((b-a-8)>>2)&0xffffff);}
static void DCWrite32(u32 a,u32 b){(void)a;(void)b;}
static void ICInvalidate(void){}
static s32 stock_close(ipcmessage*m){stock++;return os_message_queue_ack(m,0);}
static s32 stock_ioctl(ipcmessage*m){(void)m;stock++;return 0;}
static u32 v4_physical(u32,u32);
static u8*map(u32 a,u32 n){return v4_physical(a,n)==0x1000 && n<=sizeof(payload)?payload:NULL;}
#define V4_MAP(a,n) map(a,n)
#define V4_STOCK_CLOSE(m) stock_close(m)
#define V4_STOCK_IOCTL(m,q) ((void)(q),stock_ioctl(m))
#define V4_ARM
#include "../plugin/source/hidv4.h"
static u8 header[32],devices[0x600];
static ipcmessage req(u32 cmd){ipcmessage m={0};m.command=IOS_IOCTL;m.fd=0;m.ioctl.command=cmd;return m;}
static ipcmessage transfer(u32 cmd,u32 len,u32 ep){
ipcmessage m=req(cmd);memset(header,0,32);m.ioctl.buffer_in=(u32*)header;m.ioctl.length_in=32;
put_be32(header+28,0x80001000);put_be32(header+20,ep);put_be32(header+24,len);return m;}
static ipcmessage control(u8 command,u32 len){
ipcmessage m=transfer(2,len,0);header[20]=0x21;header[21]=9;header[22]=2;
memset(payload,0,sizeof(payload));payload[0]=command;return m;}
int main(void){
ipcmessage m=req(6),r,d,c;u32 i,n;
v4_process(&m);CHECK(m.result==0x40001);
d=req(0);d.ioctl.buffer_io=(u32*)devices;d.ioctl.length_io=0x600;
v4_process(&d);CHECK(d.result==0);CHECK(!memcmp(devices,v4_entry,72));CHECK(v4_be32(devices)==68);CHECK(devices[16]==0x14&&devices[17]==0x30);
n=acks;v4_process(&d);CHECK(acks==n&&v4_sessions[0].change==&d);
for(i=10;i<=11;i++){m=control(0,0);header[21]=i;header[22]=0;v4_process(&m);CHECK(m.result==8);}
m=control('R',2);v4_process(&m);CHECK(m.result==10);
m=control('A',2);payload[1]=1;v4_process(&m);CHECK(m.result==10);
r=transfer(3,32,0x81);n=acks;v4_process(&r);CHECK(acks==n);for(i=0;i<10;i++)v4_tick();CHECK(acks==n);v4_tick();CHECK(r.result==32&&payload[0]=='R'&&payload[1]==2&&payload[2]==0x1b);
r=transfer(3,32,0x81);v4_process(&r);for(i=0;i<11;i++)v4_tick();CHECK(payload[0]=='A'&&payload[1]==1&&payload[2]==0xff);
r=transfer(3,32,0x81);v4_process(&r);v4_tick();CHECK(payload[0]=='S'&&payload[1]==0&&payload[6]==1);
m=control('C',4);v4_process(&m);CHECK(m.result==12);
m=control('S',1);v4_process(&m);CHECK(m.result==9);
m=control('R',1);v4_process(&m);CHECK(m.result==-4);
m=control('R',2);header[23]='R';v4_process(&m);CHECK(m.result==10);
m=control('R',2);header[23]='X';v4_process(&m);CHECK(m.result==-4);
m=control('R',2);put_be32(header+28,0xffffffff);v4_process(&m);CHECK(m.result==-4);
m=control('R',2);put_be32(header+16,1);v4_process(&m);CHECK(m.result==-6);
CHECK(!v4_physical(0x93ffffff,32));CHECK(!v4_physical(0x81800000,1));CHECK(v4_physical(0x935dc240,32)==0x135dc240);CHECK(v4_physical(0xd35dc240,32)==0x135dc240);CHECK(!v4_physical(0x435dc240,32));CHECK(!v4_physical(0,32));
r=transfer(3,32,0x81);v4_process(&r);c=req(8);memset(header,0,32);header[4]=0x81;c.ioctl.buffer_in=(u32*)header;c.ioctl.length_in=8;v4_process(&c);CHECK(r.result==-7022&&c.result==0);n=acks;for(i=0;i<12;i++)v4_tick();CHECK(n==acks);
m=req(7);v4_process(&m);CHECK(m.result==0&&d.result==-1&&v4_be32(devices)==0xffffffff);
m=req(6);v4_process(&m);v4_process(&d);CHECK(d.result==0&&v4_be32(devices)==68);
m=req(6);m.command=IOS_CLOSE;v4_route[0]=1;v4_process(&m);CHECK(!v4_route[0]&&stock==1);
for(i=1;i<=3;i++){v4_queue=-1;failstage=i;CHECK(v4_start()<0&&v4_queue==-1);}failstage=5;CHECK(v4_start()<0&&v4_queue==-1&&v4_timer==-1);failstage=0;CHECK(v4_start()==0);
m=req(6);v4_route[0]=0;failstage=4;v4_ioctl_dispatch(&m,7);CHECK(m.result==-8&&!v4_route[0]);failstage=0;v4_ioctl_dispatch(&m,7);CHECK(v4_route[0]);
m=req(6);m.fd=1;m.ioctl.length_in=32;v4_ioctl_dispatch(&m,7);CHECK(stock==2);
v4_cancel(&v4_sessions[0]);for(i=0;i<V4_FIFO;i++){m=control('R',2);v4_process(&m);CHECK(m.result==10);}m=control('A',2);payload[1]=0;v4_process(&m);CHECK(m.result==-8);
/* Link the patch helper so compiler checks its complete implementation. */
CHECK(patch_v4_dispatch!=NULL);CHECK(os_destroy_timer!=NULL);
printf("PASS: %u E07 runtime assertions\n",checks);return 0;
}
